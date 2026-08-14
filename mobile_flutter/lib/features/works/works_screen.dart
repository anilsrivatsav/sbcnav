import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/local/app_database.dart';
import '../../data/sync/sync_service.dart';
import '../../core/theme/app_theme.dart';
import '../../shared/widgets.dart';
import '../reports/report_pdf_export.dart';

class WorksScreen extends ConsumerStatefulWidget {
  const WorksScreen({super.key});

  @override
  ConsumerState<WorksScreen> createState() => _WorksScreenState();
}

class _WorksScreenState extends ConsumerState<WorksScreen> {
  late Future<_WorksData> _future;
  String _search = '';
  String _sectionFilter = 'All';
  String _categoryFilter = 'All';
  String _filterMode = 'section';
  bool _exporting = false;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<_WorksData> _load() async {
    final database = ref.read(databaseProvider);
    final source = _deduplicateWorks(await database.portfolioWorks());
    final rows = source.asMap().entries.map((entry) {
      final row = Map<String, dynamic>.from(entry.value);
      row['sl_no'] = entry.key + 1;
      row['work_section'] = workSection(row);
      row['work_category'] = workCategory(row);
      row['deletion_recommended'] = deletionRecommended(row);
      return row;
    }).toList();
    return _WorksData(rows: rows);
  }

  void _reload() => setState(() => _future = _load());

  List<Map<String, dynamic>> _filtered(List<Map<String, dynamic>> rows) {
    final query = _search.trim().toLowerCase();
    final filtered = rows.where((row) {
      final text = row.values.map((value) => '$value').join(' ').toLowerCase();
      return (query.isEmpty || text.contains(query)) &&
          (_sectionFilter == 'All' || row['work_section'] == _sectionFilter) &&
          (_categoryFilter == 'All' || row['work_category'] == _categoryFilter);
    }).toList();
    return filtered.asMap().entries.map((entry) {
      return {...entry.value, 'sl_no': entry.key + 1};
    }).toList();
  }

  Future<void> _export(List<Map<String, dynamic>> rows, bool pdf) async {
    setState(() => _exporting = true);
    const columns = [
      'sl_no',
      'project_id',
      'date_of_sanction',
      'short_name_of_work',
      'cost',
      'remarks',
    ];
    try {
      if (pdf) {
        await exportReportPdf(
          title: 'Sanctioned Works Report',
          subtitle: '${rows.length} works - section: $_sectionFilter',
          rows: rows,
          columns: columns,
        );
      } else {
        final file = await exportReportCsv(
          title: 'Sanctioned Works Report',
          rows: rows,
          columns: columns,
        );
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
                content: Text('Excel-compatible CSV saved to ${file.path}')),
          );
        }
      }
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Export failed: $error')),
        );
      }
    } finally {
      if (mounted) setState(() => _exporting = false);
    }
  }

  Future<void> _exportSummaryPdf(List<Map<String, dynamic>> rows) async {
    final sectionRows = _pendingSummary(rows).map((row) => {
          'group': 'Section',
          'name': row['authority'],
          'total': row['total'],
          'completed': row['completed'],
          'open': (row['tender'] as int) + (row['wip'] as int) + (row['other'] as int),
          'tender': row['tender'],
          'wip': row['wip'],
        });
    final yearRows = _yearSummary(rows).map((row) => {
          'group': 'Year',
          'name': row['year'],
          'total': row['sanctioned'],
          'completed': row['completed'],
          'open': (row['wip'] as int) + (row['tender'] as int),
          'tender': row['tender'],
          'wip': row['wip'],
        });
    await exportReportPdf(
      title: 'Sanctioned Works Summary',
      subtitle: 'Calculated from ${rows.length} works in the current database snapshot',
      rows: [...sectionRows, ...yearRows],
      columns: const ['group', 'name', 'total', 'completed', 'open', 'tender', 'wip'],
    );
  }

  @override
  Widget build(BuildContext context) {
    ref.listen(syncControllerProvider, (_, __) => _reload());
    return FutureBuilder<_WorksData>(
      future: _future,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting &&
            !snapshot.hasData) {
          return const GlassLoadingList(itemCount: 6);
        }
        if (snapshot.hasError) {
          return ErrorPane(error: snapshot.error!, retry: _reload);
        }
        final allRows = snapshot.data?.rows ?? const <Map<String, dynamic>>[];
        final rows = _filtered(allRows);
        final sections = _orderedWorkOptions(
          allRows.map((row) => '${row['work_section'] ?? 'Not specified'}'),
          const ['North', 'South', 'East', 'West', 'GSU/SBC', 'Division', 'CAO/CN', 'Sr.DCM', 'Sr.DSTE', 'Sr.DEE'],
        );
        final categories = _orderedWorkOptions(
          allRows.map((row) => '${row['work_category'] ?? 'Other works'}'),
          const ['ABSS works', 'Passenger amenity works', 'FOB works', 'Platform extension works', 'Platform shelter works', 'Divyangjan works', 'Goods / CSGR works', 'CAO/CN works', 'Other works'],
        );
        final completed =
            allRows.where((row) => isComplete(row['status'])).length;
        final deletion =
            allRows.where((row) => row['deletion_recommended'] == true).length;
        final open = allRows.length - completed;
        final completedRows = allRows.where((row) => isComplete(row['status'])).toList();
        final openRows = allRows.where((row) => !isComplete(row['status'])).toList();
        final deletionRows = allRows.where((row) => row['deletion_recommended'] == true).toList();
        return Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(AppSpacing.page, AppSpacing.x3,
                  AppSpacing.page, AppSpacing.x2),
              child: Column(
                children: [
                  const PageHeading(
                    title: 'Works',
                    subtitle:
                        'Sanctioned works grouped from the source register.',
                  ),
                  const SizedBox(height: AppSpacing.x2),
                  AppSearchField(
                    hint: 'Search PID, work name, section or remarks',
                    onChanged: (value) => setState(() => _search = value),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.page),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                _WorksFilterRail(
                  selected: _filterMode,
                  onSelected: (value) => setState(() {
                    _filterMode = value;
                    if (value == 'section') {
                      _sectionFilter = 'All';
                    } else {
                      _categoryFilter = 'All';
                    }
                  }),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _WorksFilterTabs(
                    values: _filterMode == 'section' ? sections : categories,
                    selected: _filterMode == 'section' ? _sectionFilter : _categoryFilter,
                    onSelected: (value) => setState(() {
                      if (_filterMode == 'section') {
                        _sectionFilter = value;
                      } else {
                        _categoryFilter = value;
                      }
                    }),
                  ),
                ),
              ]),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(
                  AppSpacing.page, 10, AppSpacing.page, 6),
              child: Row(
                children: [
                  Expanded(
                    child: Text('${rows.length} works',
                        style: const TextStyle(fontWeight: FontWeight.w900)),
                  ),
                  if (_exporting)
                    const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2))
                  else ...[
                    AppIconButton(
                        tooltip: 'Export PDF',
                        icon: Icons.picture_as_pdf_rounded,
                        onPressed: () => _export(rows, true)),
                    AppIconButton(
                        tooltip: 'Export Excel CSV',
                        icon: Icons.table_view_rounded,
                        onPressed: () => _export(rows, false)),
                  ],
                ],
              ),
            ),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.fromLTRB(
                    AppSpacing.page, 0, AppSpacing.page, 28),
                children: [
                  if (rows.isEmpty)
                    const EmptyState(
                        icon: Icons.construction_rounded,
                        title: 'No works found',
                        message: 'Try another section, category or search term.')
                  else
                    ...rows.expand((row) => [
                          _WorkRow(
                            row: row,
                            onTap: () => showGlassBottomSheet<void>(
                              context,
                              builder: (_) => _WorkDetailSheet(row: row),
                            ),
                          ),
                          const SizedBox(height: 8),
                        ]),
                ],
              ),
            ),
            _WorksFloatingActions(
              total: allRows.length,
              completed: completed,
              open: open,
              deletion: deletion,
              onTotal: () => showGlassBottomSheet<void>(
                context,
                builder: (_) => _WorksSubsetSheet(title: 'All works · ${allRows.length}', rows: allRows),
              ),
              onCompleted: () => showGlassBottomSheet<void>(
                context,
                builder: (_) => _WorksSubsetSheet(title: 'Completed works · $completed', rows: completedRows),
              ),
              onOpen: () => showGlassBottomSheet<void>(
                context,
                builder: (_) => _WorksSubsetSheet(title: 'Open works · $open', rows: openRows),
              ),
              onDeletion: () => showGlassBottomSheet<void>(
                context,
                builder: (_) => _WorksSubsetSheet(title: 'Deletion recommended · $deletion', rows: deletionRows),
              ),
              onSummary: () => showGlassBottomSheet<void>(
                context,
                builder: (_) => _WorksSummarySheet(
                  rows: allRows,
                  onExportPdf: () => _exportSummaryPdf(allRows),
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}

class _WorksData {
  const _WorksData({required this.rows});
  final List<Map<String, dynamic>> rows;
}

class _WorksFloatingActions extends StatelessWidget {
  const _WorksFloatingActions({
    required this.total,
    required this.completed,
    required this.open,
    required this.deletion,
    required this.onTotal,
    required this.onCompleted,
    required this.onOpen,
    required this.onDeletion,
    required this.onSummary,
  });
  final int total;
  final int completed;
  final int open;
  final int deletion;
  final VoidCallback onTotal;
  final VoidCallback onCompleted;
  final VoidCallback onOpen;
  final VoidCallback onDeletion;
  final VoidCallback onSummary;

  @override
  Widget build(BuildContext context) => SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(AppSpacing.page, 4, AppSpacing.page, 10),
          child: Align(
            alignment: Alignment.centerRight,
            child: IconButton(
              tooltip: 'Open work views and summary',
              onPressed: () => showGlassBottomSheet<void>(
                context,
                builder: (_) => _WorksActionSheet(
                  total: total,
                  completed: completed,
                  open: open,
                  deletion: deletion,
                  onTotal: onTotal,
                  onCompleted: onCompleted,
                  onOpen: onOpen,
                  onDeletion: onDeletion,
                  onSummary: onSummary,
                ),
              ),
              style: IconButton.styleFrom(
                backgroundColor: Colors.transparent,
                foregroundColor: Theme.of(context).colorScheme.primary,
                shadowColor: Colors.transparent,
                padding: const EdgeInsets.all(8),
              ),
              icon: const Icon(Icons.summarize_rounded),
            ),
          ),
        ),
      );
}

class _WorksActionSheet extends StatelessWidget {
  const _WorksActionSheet({
    required this.total,
    required this.completed,
    required this.open,
    required this.deletion,
    required this.onTotal,
    required this.onCompleted,
    required this.onOpen,
    required this.onDeletion,
    required this.onSummary,
  });
  final int total;
  final int completed;
  final int open;
  final int deletion;
  final VoidCallback onTotal;
  final VoidCallback onCompleted;
  final VoidCallback onOpen;
  final VoidCallback onDeletion;
  final VoidCallback onSummary;

  @override
  Widget build(BuildContext context) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(AppSpacing.page, 8, AppSpacing.page, 24),
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('Work views', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w900)),
            const SizedBox(height: 12),
            _ActionRow(label: 'All works', value: total, icon: Icons.list_alt_rounded, onTap: onTotal),
            _ActionRow(label: 'Completed works', value: completed, icon: Icons.check_circle_outline_rounded, onTap: onCompleted),
            _ActionRow(label: 'Open works', value: open, icon: Icons.pending_actions_rounded, onTap: onOpen),
            _ActionRow(label: 'Deletion recommended', value: deletion, icon: Icons.delete_outline_rounded, onTap: onDeletion),
            _ActionRow(label: 'Summary + PDF', icon: Icons.picture_as_pdf_rounded, onTap: onSummary),
          ]),
        ),
      );
}

class _ActionRow extends StatelessWidget {
  const _ActionRow({required this.label, required this.onTap, this.value, required this.icon});
  final String label;
  final int? value;
  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => ListTile(
        contentPadding: EdgeInsets.zero,
        leading: Icon(icon, color: Theme.of(context).colorScheme.primary),
        title: Text(label, style: const TextStyle(fontWeight: FontWeight.w800)),
        trailing: value == null
            ? const Icon(Icons.chevron_right_rounded)
            : Text('$value', style: const TextStyle(fontWeight: FontWeight.w900)),
        onTap: () {
          Navigator.of(context).pop();
          onTap();
        },
      );
}

class _BottomMetric extends StatelessWidget {
  const _BottomMetric({required this.label, required this.value, required this.onTap});
  final String label;
  final int value;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: Column(children: [
            Text('$value', style: const TextStyle(fontWeight: FontWeight.w900)),
            Text(label, style: const TextStyle(fontSize: 11)),
          ]),
        ),
      );
}

class _WorksTotalsSheet extends StatelessWidget {
  const _WorksTotalsSheet({required this.total, required this.completed, required this.open, required this.deletion});
  final int total;
  final int completed;
  final int open;
  final int deletion;

  @override
  Widget build(BuildContext context) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(AppSpacing.page, 8, AppSpacing.page, 24),
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('Works overview', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w900)),
            const SizedBox(height: 14),
            Wrap(spacing: 10, runSpacing: 10, children: [
              _WorkMetric(label: 'Total works', value: total),
              _WorkMetric(label: 'Completed', value: completed),
              _WorkMetric(label: 'Open', value: open),
              _WorkMetric(label: 'Deletion recommended', value: deletion),
            ]),
          ]),
        ),
      );
}

class _WorksSubsetSheet extends StatelessWidget {
  const _WorksSubsetSheet({required this.title, required this.rows});
  final String title;
  final List<Map<String, dynamic>> rows;

  @override
  Widget build(BuildContext context) => SafeArea(
        child: ListView.separated(
          padding: const EdgeInsets.fromLTRB(AppSpacing.page, 8, AppSpacing.page, 24),
          itemCount: rows.length + 1,
          separatorBuilder: (_, __) => const SizedBox(height: 8),
          itemBuilder: (_, index) {
            if (index == 0) {
              return Text(title,
                  style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w900));
            }
            final row = rows[index - 1];
            return _WorkRow(
              row: row,
              onTap: () => showGlassBottomSheet<void>(
                context,
                builder: (_) => _WorkDetailSheet(row: row),
              ),
            );
          },
        ),
      );
}

class _WorksSummarySheet extends StatelessWidget {
  const _WorksSummarySheet({required this.rows, required this.onExportPdf});
  final List<Map<String, dynamic>> rows;
  final VoidCallback onExportPdf;

  @override
  Widget build(BuildContext context) => SafeArea(
        child: ListView(padding: const EdgeInsets.fromLTRB(AppSpacing.page, 8, AppSpacing.page, 24), children: [
          Row(children: [
            const Expanded(child: Text('Works summary', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w900))),
            AppIconButton(tooltip: 'Export summary PDF', icon: Icons.picture_as_pdf_rounded, onPressed: onExportPdf),
          ]),
          const SizedBox(height: 4),
          Text('Calculated from ${rows.length} sanctioned works'),
          const SizedBox(height: 16),
          _SummaryTableSection(
            title: 'Works pending with · source Section column',
            columns: const ['Section', 'Total', 'Completed', 'Tender', 'WIP', 'Other'],
            rows: _pendingSummary(rows),
            fields: const ['authority', 'total', 'completed', 'tender', 'wip', 'other'],
          ),
          const SizedBox(height: 22),
          _SummaryTableSection(
            title: 'Year-wise progress',
            columns: const ['Year', 'Sanctioned', 'Completed', 'WIP', 'Tender'],
            rows: _yearSummary(rows),
            fields: const ['year', 'sanctioned', 'completed', 'wip', 'tender'],
          ),
        ]),
      );
}

class _WorksSummaryPanel extends StatelessWidget {
  const _WorksSummaryPanel({required this.rows});
  final List<Map<String, dynamic>> rows;

  @override
  Widget build(BuildContext context) {
    final pending = _pendingSummary(rows);
    final years = _yearSummary(rows);
    return NeoPanel(
      padding: EdgeInsets.zero,
      child: ExpansionTile(
        initiallyExpanded: false,
        tilePadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 2),
        childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
        leading: const Icon(Icons.summarize_rounded),
        title: const Text('Works summary',
            style: TextStyle(fontWeight: FontWeight.w900)),
        subtitle: Text('Calculated from ${rows.length} sanctioned works'),
        children: [
          _SummaryTableSection(
            title: 'Works pending with · source Section column',
            columns: const ['Section', 'Total', 'Completed', 'Tender', 'WIP', 'Other'],
            rows: pending,
            fields: const ['authority', 'total', 'completed', 'tender', 'wip', 'other'],
          ),
          const SizedBox(height: 16),
          _SummaryTableSection(
            title: 'Year-wise progress',
            columns: const ['Year', 'Sanctioned', 'Completed', 'WIP', 'Tender'],
            rows: years,
            fields: const ['year', 'sanctioned', 'completed', 'wip', 'tender'],
          ),
        ],
      ),
    );
  }
}

List<Map<String, dynamic>> _pendingSummary(List<Map<String, dynamic>> rows) {
  final groups = <String, Map<String, dynamic>>{};
  for (final row in rows) {
    final authority = workSection(row);
    final item = groups.putIfAbsent(authority, () => {
          'authority': authority,
          'total': 0,
          'completed': 0,
          'tender': 0,
          'wip': 0,
          'other': 0,
        });
    item['total'] = (item['total'] as int) + 1;
    final status = '${row['status'] ?? ''}'.toLowerCase();
    if (isComplete(status)) {
      item['completed'] = (item['completed'] as int) + 1;
    } else if (status.contains('tender')) {
      item['tender'] = (item['tender'] as int) + 1;
    } else if (status.trim().isEmpty) {
      item['other'] = (item['other'] as int) + 1;
    } else {
      item['wip'] = (item['wip'] as int) + 1;
    }
  }
  final result = groups.values.toList()
    ..sort((a, b) => a['authority'].toString().compareTo(b['authority'].toString()));
  final total = <String, dynamic>{
    'authority': 'Total Works',
    'total': rows.length,
    'completed': result.fold<int>(0, (sum, row) => sum + (row['completed'] as int)),
    'tender': result.fold<int>(0, (sum, row) => sum + (row['tender'] as int)),
    'wip': result.fold<int>(0, (sum, row) => sum + (row['wip'] as int)),
    'other': result.fold<int>(0, (sum, row) => sum + (row['other'] as int)),
  };
  return [...result, total];
}

List<Map<String, dynamic>> _yearSummary(List<Map<String, dynamic>> rows) {
  final groups = <String, Map<String, dynamic>>{};
  for (final row in rows) {
    final year = _displayYear('${row['year_of_sanction'] ?? 'Unknown'}');
    final item = groups.putIfAbsent(year, () => {
          'year': year,
          'sanctioned': 0,
          'completed': 0,
          'wip': 0,
          'tender': 0,
        });
    item['sanctioned'] = (item['sanctioned'] as int) + 1;
    final status = '${row['status'] ?? ''}'.toLowerCase();
    if (isComplete(status)) {
      item['completed'] = (item['completed'] as int) + 1;
    } else if (status.contains('tender')) {
      item['tender'] = (item['tender'] as int) + 1;
    } else if (status.trim().isEmpty) {
      item['wip'] = (item['wip'] as int) + 1;
    } else {
      item['wip'] = (item['wip'] as int) + 1;
    }
  }
  final result = groups.values.toList();
  result.sort((a, b) => a['year'].toString().compareTo(b['year'].toString()));
  final total = <String, dynamic>{
    'year': 'Total Works',
    'sanctioned': rows.length,
    'completed': result.fold<int>(0, (sum, row) => sum + (row['completed'] as int)),
    'wip': result.fold<int>(0, (sum, row) => sum + (row['wip'] as int)),
    'tender': result.fold<int>(0, (sum, row) => sum + (row['tender'] as int)),
  };
  return [...result, total];
}

List<String> _orderedWorkOptions(Iterable<String> values, List<String> preferred) {
  final available = values.map((value) => value.trim()).where((value) => value.isNotEmpty).toSet();
  final ordered = <String>['All'];
  ordered.addAll(preferred.where(available.contains));
  final remaining = available.difference(ordered.toSet()).toList()..sort();
  ordered.addAll(remaining);
  return ordered;
}

String _displayYear(String value) {
  final match = RegExp(r'^(\d{4})-(\d{4})$').firstMatch(value.trim());
  if (match == null) return value.trim().isEmpty ? 'Unknown' : value.trim();
  return '${match.group(1)}-${match.group(2)!.substring(2)}';
}

class _SummaryTableSection extends StatelessWidget {
  const _SummaryTableSection({
    required this.title,
    required this.columns,
    required this.rows,
    required this.fields,
  });
  final String title;
  final List<String> columns;
  final List<Map<String, dynamic>> rows;
  final List<String> fields;

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(title, style: const TextStyle(fontWeight: FontWeight.w900)),
      const SizedBox(height: 8),
      SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: DataTable(
          headingRowHeight: 34,
          dataRowMinHeight: 34,
          dataRowMaxHeight: 46,
          columnSpacing: 18,
          horizontalMargin: 8,
          columns: columns
              .map((label) => DataColumn(
                  label: Text(label,
                      style: const TextStyle(fontWeight: FontWeight.w900))))
              .toList(),
          rows: rows
              .map((row) => DataRow(
                    cells: fields
                        .map((field) => DataCell(Text('${row[field] ?? 0}')))
                        .toList(),
                  ))
              .toList(),
        ),
      ),
    ]);
  }
}

class _WorkMetric extends StatelessWidget {
  const _WorkMetric({required this.label, required this.value});
  final String label;
  final int value;

  @override
  Widget build(BuildContext context) => NeoPanel(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Text('$value', style: const TextStyle(fontWeight: FontWeight.w900)),
          const SizedBox(width: 6),
          Text(label),
        ]),
      );
}

class _WorkChip extends StatelessWidget {
  const _WorkChip(
      {required this.label, required this.selected, required this.onTap});
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = Theme.of(context).colorScheme.primary;
    return InkWell(
      borderRadius: BorderRadius.circular(18),
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
        decoration: BoxDecoration(
          color: selected ? color : Theme.of(context).colorScheme.surface,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: selected ? color : Colors.white),
          boxShadow: selected
              ? [
                  BoxShadow(
                      color: color.withValues(alpha: .24),
                      blurRadius: 10,
                      offset: const Offset(0, 5))
                ]
              : [
                  BoxShadow(
                      color: Colors.black.withValues(alpha: .08),
                      blurRadius: 9,
                      offset: const Offset(3, 4)),
                  const BoxShadow(
                      color: Colors.white,
                      blurRadius: 7,
                      offset: Offset(-3, -3)),
                ],
        ),
        child: Text(label,
            style: TextStyle(
                color: selected ? Colors.white : null,
                fontWeight: FontWeight.w800,
                fontSize: 12)),
      ),
    );
  }
}

class _WorkDropdown extends StatelessWidget {
  const _WorkDropdown({
    required this.label,
    required this.value,
    required this.values,
    required this.onChanged,
  });
  final String label;
  final String value;
  final List<String> values;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) => DropdownButtonFormField<String>(
        value: value,
        isExpanded: true,
        decoration: InputDecoration(
          labelText: label,
          isDense: true,
          filled: true,
          fillColor: Theme.of(context).colorScheme.surface,
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(14)),
        ),
        items: values
            .map((item) => DropdownMenuItem<String>(
                  value: item,
                  child: Text(item, overflow: TextOverflow.ellipsis),
                ))
            .toList(),
        onChanged: (item) {
          if (item != null) onChanged(item);
        },
      );
}

class _WorksFilterRail extends StatelessWidget {
  const _WorksFilterRail({required this.selected, required this.onSelected});
  final String selected;
  final ValueChanged<String> onSelected;

  @override
  Widget build(BuildContext context) => NeoPanel(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          IconButton(
            tooltip: 'Filter by Section',
            onPressed: () => onSelected('section'),
            icon: Icon(Icons.account_tree_rounded,
                color: selected == 'section'
                    ? Theme.of(context).colorScheme.primary
                    : null),
          ),
          IconButton(
            tooltip: 'Filter by Work Type',
            onPressed: () => onSelected('category'),
            icon: Icon(Icons.category_rounded,
                color: selected == 'category'
                    ? Theme.of(context).colorScheme.primary
                    : null),
          ),
        ]),
      );
}

class _WorksFilterTabs extends StatelessWidget {
  const _WorksFilterTabs({required this.values, required this.selected, required this.onSelected});
  final List<String> values;
  final String selected;
  final ValueChanged<String> onSelected;

  @override
  Widget build(BuildContext context) => SizedBox(
        height: 48,
        child: ListView.separated(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: 2, vertical: 2),
          itemCount: values.length,
          separatorBuilder: (_, __) => const SizedBox(width: 8),
          itemBuilder: (_, index) {
            final value = values[index];
            final active = value == selected;
            return ChoiceChip(
              label: Text(value, overflow: TextOverflow.ellipsis),
              selected: active,
              onSelected: (_) => onSelected(value),
              showCheckmark: false,
              labelStyle: TextStyle(
                fontWeight: FontWeight.w800,
                color: active ? Theme.of(context).colorScheme.onPrimary : null,
              ),
              selectedColor: Theme.of(context).colorScheme.primary,
              backgroundColor: Theme.of(context).colorScheme.surface,
              side: BorderSide(
                color: active
                    ? Theme.of(context).colorScheme.primary
                    : Theme.of(context).colorScheme.outlineVariant,
              ),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
            );
          },
        ),
      );
}

class _WorkRow extends StatelessWidget {
  const _WorkRow({required this.row, required this.onTap});
  final Map<String, dynamic> row;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => NeoPanel(
        onTap: onTap,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(
              child: Text(
                  '${row['short_name_of_work'] ?? row['work_name'] ?? '-'}',
                  maxLines: 3,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontWeight: FontWeight.w900)),
            ),
            StatusBadge('${row['work_category'] ?? 'Other works'}'),
          ]),
          const SizedBox(height: 7),
          Wrap(spacing: 8, runSpacing: 5, children: [
            Text('PID: ${row['project_id'] ?? '-'}'),
            Text('Section: ${row['work_section'] ?? 'Other'}'),
            Text('Status: ${row['status'] ?? '-'}'),
            if (row['deletion_recommended'] == true)
              const StatusBadge('Deletion recommended', tone: AppPalette.red),
          ]),
        ]),
      );
}

class _WorkDetailSheet extends StatelessWidget {
  const _WorkDetailSheet({required this.row});
  final Map<String, dynamic> row;

  @override
  Widget build(BuildContext context) {
    final entries = row.entries.where((entry) {
      final value = '${entry.value}'.trim();
      return value.isNotEmpty &&
          value != 'null' &&
          value != '[]' &&
          value != '{}';
    }).toList();
    return SafeArea(
      child: Padding(
        padding:
            const EdgeInsets.fromLTRB(AppSpacing.page, 8, AppSpacing.page, 20),
        child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                  child: Container(
                      width: 42,
                      height: 4,
                      decoration: BoxDecoration(
                          color: Theme.of(context).colorScheme.outlineVariant,
                          borderRadius: BorderRadius.circular(4)))),
              const SizedBox(height: 18),
              Text('Work details',
                  style: Theme.of(context)
                      .textTheme
                      .headlineSmall
                      ?.copyWith(fontWeight: FontWeight.w900)),
              const SizedBox(height: 12),
              Flexible(
                child: ListView.separated(
                  shrinkWrap: true,
                  itemCount: entries.length,
                  separatorBuilder: (_, __) => const Divider(height: 16),
                  itemBuilder: (_, index) => Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        SizedBox(
                            width: 130,
                            child: Text(_workLabel(entries[index].key),
                                style: const TextStyle(
                                    fontWeight: FontWeight.w800))),
                        const SizedBox(width: 12),
                        Expanded(child: Text('${entries[index].value}')),
                      ]),
                ),
              ),
            ]),
      ),
    );
  }
}

String _workLabel(String value) => value
    .split('_')
    .map((part) =>
        part.isEmpty ? part : '${part[0].toUpperCase()}${part.substring(1)}')
    .join(' ');

bool isComplete(Object? value) {
  final text = '$value'.toLowerCase();
  return text.contains('complete') || text.contains('done');
}

String workSection(Map<String, dynamic> row) {
  final raw = '${row['section'] ?? ''}'.trim();
  if (raw.isEmpty) return 'Not specified';
  const labels = <String, String>{
    'north': 'North',
    'south': 'South',
    'east': 'East',
    'west': 'West',
    'division': 'Division',
    'gsu/sbc': 'GSU/SBC',
    'cao/cn': 'CAO/CN',
    'sr.dcm': 'Sr.DCM',
    'sr.dste': 'Sr.DSTE',
    'sr.dee': 'Sr.DEE',
  };
  return labels[raw.toLowerCase()] ?? raw;
}

String workCategory(Map<String, dynamic> row) {
  final text =
      '${row['short_name_of_work'] ?? ''} ${row['work_name'] ?? ''} ${row['remarks'] ?? ''} ${row['parent_work'] ?? ''} ${row['block_section_station'] ?? ''} ${row['scope_type'] ?? ''} ${row['scope_value'] ?? ''} ${row['match_status'] ?? ''} ${row['section'] ?? ''}'
          .toLowerCase();
  final scope =
      '${row['scope_type'] ?? ''} ${row['scope_value'] ?? ''} ${row['match_status'] ?? ''} ${row['block_section_station'] ?? ''}'
          .toLowerCase();
  if (scope.contains('abss')) return 'ABSS works';
  if (text.contains('cao/cn') ||
      text.contains('cao cn') ||
      (text.contains('redevelopment') &&
          (text.contains('ypr') ||
              text.contains('bnc') ||
              text.contains('tk')))) return 'CAO/CN works';
  if (text.contains('goods') ||
      text.contains('csgr') ||
      text.contains('goods shed')) return 'Goods / CSGR works';
  if (text.contains('fob') || text.contains('foot over')) return 'FOB works';
  if (text.contains('platform shelter') || text.contains('shelter'))
    return 'Platform shelter works';
  if (text.contains('platform') ||
      text.contains('pf ext') ||
      text.contains('raising')) return 'Platform extension works';
  if (text.contains('divyang') ||
      text.contains('ramp') ||
      text.contains('accessible') ||
      text.contains('lift')) return 'Divyangjan works';
  if (text.contains('toilet') ||
      text.contains('water') ||
      text.contains('waiting hall') ||
      text.contains('amenit')) return 'Passenger amenity works';
  return 'Other works';
}

bool deletionRecommended(Map<String, dynamic> row) => RegExp(
        r'proposal dropped|proposed for deletion|recommended for deletion|work deleted|deletion recommended',
        caseSensitive: false)
    .hasMatch(
        '${row['remarks'] ?? ''} ${row['engg_remarks'] ?? ''} ${row['status'] ?? ''}');

List<Map<String, dynamic>> _deduplicateWorks(
    List<Map<String, dynamic>> source) {
  final seen = <String>{};
  final result = <Map<String, dynamic>>[];
  for (final row in source) {
    final projectId = '${row['project_id'] ?? ''}'.trim().toLowerCase();
    final name = '${row['short_name_of_work'] ?? row['work_name'] ?? ''}'
        .trim()
        .toLowerCase();
    final section = '${row['section'] ?? ''}'.trim().toLowerCase();
    final sanctionDate = '${row['date_of_sanction'] ?? ''}'.trim().toLowerCase();
    final key = projectId.isNotEmpty
        ? 'pid:$projectId'
        : 'fallback:$name|$section|$sanctionDate|${row['cost'] ?? ''}';
    if (key == 'fallback:|||') {
      result.add(Map<String, dynamic>.from(row));
      continue;
    }
    if (seen.add(key)) result.add(Map<String, dynamic>.from(row));
  }
  return result;
}
