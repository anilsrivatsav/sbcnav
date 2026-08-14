import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/local/app_database.dart';
import '../../core/theme/app_theme.dart';
import '../../shared/widgets.dart';
import '../findings/findings_screen.dart';
import 'report_pdf_export.dart';

class ReportsScreen extends ConsumerStatefulWidget {
  const ReportsScreen({super.key});

  @override
  ConsumerState<ReportsScreen> createState() => _ReportsScreenState();
}

class _ReportsScreenState extends ConsumerState<ReportsScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabs;
  late Future<_ReportData> _report;

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 4, vsync: this);
    _report = _load();
  }

  Future<_ReportData> _load() async {
    final database = ref.read(databaseProvider);
    final stations = await database.stationOverviewRows();
    final contracts = <Map<String, dynamic>>[];
    final works = <Map<String, dynamic>>[];
    final amenities = <Map<String, dynamic>>[];
    for (final row in stations) {
      final detail = row['_station_detail'];
      if (detail is! Map) continue;
      final code = '${row['station_code'] ?? detail['station_code'] ?? ''}'
          .trim()
          .toUpperCase();
      final name =
          '${row['station_name'] ?? detail['station_name'] ?? ''}'.trim();
      final stationRecord = _map(detail['station']);
      final srDen =
          _first(row, ['sr_den', 'sr den', 'Sr DEN', 'SR DEN', 'sr.den']) ??
              _first(stationRecord,
                  ['sr_den', 'sr den', 'Sr DEN', 'SR DEN', 'sr.den']);
      final cmi = _first(row, ['cmi', 'CMI', 'commercial_inspector']) ??
          _first(stationRecord, ['cmi', 'CMI', 'commercial_inspector']);
      final section = _first(row, ['section', 'Section', 'block_section']) ??
          _first(stationRecord, ['section', 'Section', 'block_section']);
      final abss = _truthy(_first(row, ['abss_flag', 'ABSS']) ??
          _first(stationRecord, ['abss_flag', 'ABSS']));
      final contractRows = [
        ..._list(detail['contracts']),
        ..._list(detail['commercial_contracts']),
      ];
      for (final raw in contractRows) {
        if (raw is! Map) continue;
        final item = Map<String, dynamic>.from(raw);
        item['station_code'] = code;
        item['station_name'] = name;
        item['report_group'] = _contractGroup(item);
        contracts.add(item);
      }
      for (final raw in _list(detail['works'])) {
        if (raw is! Map) continue;
        final item = Map<String, dynamic>.from(raw);
        item['station_code'] = code;
        item['station_name'] = name;
        item['sr_den'] = srDen;
        item['cmi'] = cmi;
        item['section'] = section;
        item['report_group'] = _workGroup(item, abss: abss);
        item['work_section'] = _workSection(item);
        item['deletion_recommended'] = _deletionRecommended(item);
        works.add(item);
      }
      _addAmenities(amenities, code, name, detail['amenities']);
    }
    final globalWorks = await database.portfolioWorks();
    final reportWorks = globalWorks.isEmpty
        ? works
        : globalWorks.asMap().entries.map((entry) {
            final raw = entry.value;
            final item = Map<String, dynamic>.from(raw);
            item['sl_no'] = item['source_sn'] ?? entry.key + 1;
            item['report_group'] = _workGroup(item);
            item['work_section'] = _workSection(item);
            item['deletion_recommended'] = _deletionRecommended(item);
            item['sr_den'] = item['sr_den'] ?? item['sr den'] ?? item['Sr DEN'];
            item['cmi'] = item['cmi'] ?? item['CMI'];
            item['section'] = item['section'] ?? item['Section'];
            return item;
          }).toList();
    return _ReportData(
      stations: stations.length,
      contracts: contracts,
      works: reportWorks,
      amenities: amenities,
    );
  }

  void _addAmenities(List<Map<String, dynamic>> target, String code,
      String name, Object? raw) {
    if (raw is! Map) return;
    final amenities = Map<String, dynamic>.from(raw);
    void add(String group, String title, Object? value) {
      if (value == null ||
          '$value'.trim().isEmpty ||
          '$value'.toLowerCase() == 'na') return;
      target.add({
        'station_code': code,
        'station_name': name,
        'report_group': group,
        'amenity': title,
        'details': value
      });
    }

    final infra = _map(amenities['infra']);
    add('Station infrastructure', 'FOB', infra['fob_details']);
    add('Station infrastructure', 'Shelters', infra['shelter_details']);
    for (final rawPlatform in _list(amenities['platforms'])) {
      final platform = _map(rawPlatform);
      add('Platforms', '${platform['platform'] ?? 'Platform'}',
          'Length ${platform['length_m'] ?? '-'} m');
    }
    final wheelchair = _map(amenities['wheelchairs']);
    add('Accessibility', 'Wheelchairs', wheelchair['available_good_condition']);
    final trolley = _map(amenities['trolley']);
    add('Accessibility', 'Trolley path', trolley['trolley_path']);
    final access = _map(amenities['pf_extension_status']);
    add('Accessibility', 'Lifts', access['lift_details']);
    add('Accessibility', 'Ramps', access['ramp_details']);
    add('Accessibility', 'Escalators', access['escalator_details']);
    for (final rawNorm in _list(amenities['norms'])) {
      final norm = _map(rawNorm);
      final detail = '${norm['norm'] ?? ''}'.trim();
      if (detail.isEmpty) continue;
      final quantity = '${norm['norm_quantity'] ?? ''}'.trim();
      add('Norms: ${norm['amenity'] ?? 'Other'}', detail,
          quantity.isEmpty ? 'Norm recorded' : quantity);
    }
  }

  void _reload() => setState(() => _report = _load());

  @override
  void dispose() {
    _tabs.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<_ReportData>(
      future: _report,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting)
          return const GlassLoadingList(itemCount: 6);
        if (snapshot.hasError)
          return ErrorPane(error: snapshot.error!, retry: _reload);
        final data = snapshot.data!;
        return Column(
          children: [
            const Padding(
              padding: EdgeInsets.fromLTRB(AppSpacing.page, AppSpacing.x3,
                  AppSpacing.page, AppSpacing.x1),
              child: PageHeading(
                  title: 'Reports',
                  subtitle:
                      'Portfolio reports - v1.0.3 - stations, contracts and amenities.'),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.page),
              child: NeoPanel(
                padding: const EdgeInsets.all(5),
                child: TabBar(
                  controller: _tabs,
                  isScrollable: true,
                  tabs: const [
                    Tab(icon: Icon(Icons.dashboard_rounded), text: 'Overview'),
                    Tab(icon: Icon(Icons.handshake_rounded), text: 'Contracts'),
                    Tab(
                        icon: Icon(Icons.accessibility_new_rounded),
                        text: 'Amenities'),
                    Tab(icon: Icon(Icons.fact_check_rounded), text: 'Findings'),
                  ],
                ),
              ),
            ),
            const SizedBox(height: AppSpacing.x2),
            Expanded(
              child: TabBarView(
                controller: _tabs,
                children: [
                  _OverviewReport(data: data),
                  _ReportRegister(
                      title: 'Contracts register',
                      rows: data.contracts,
                      groups: _groups(data.contracts),
                      columns: const [
                        'station_code',
                        'unit_no',
                        'report_group',
                        'licensee_name',
                        'contract_to'
                      ]),
                  _ReportRegister(
                      title: 'Passenger amenities register',
                      rows: data.amenities,
                      groups: _groups(data.amenities),
                      columns: const [
                        'station_code',
                        'report_group',
                        'amenity',
                        'details'
                      ]),
                  const FindingsScreen(embedded: true),
                ],
              ),
            ),
          ],
        );
      },
    );
  }
}

class _ReportData {
  const _ReportData(
      {required this.stations,
      required this.contracts,
      required this.works,
      required this.amenities});
  final int stations;
  final List<Map<String, dynamic>> contracts;
  final List<Map<String, dynamic>> works;
  final List<Map<String, dynamic>> amenities;
}

class _OverviewReport extends StatelessWidget {
  const _OverviewReport({required this.data});
  final _ReportData data;

  @override
  Widget build(BuildContext context) {
    final openWorks =
        data.works.where((row) => !_isComplete(row['status'])).length;
    final groups = <String, int>{};
    for (final row in data.contracts)
      groups['${row['report_group']}'] =
          (groups['${row['report_group']}'] ?? 0) + 1;
    return ListView(
      padding:
          const EdgeInsets.fromLTRB(AppSpacing.page, 0, AppSpacing.page, 28),
      children: [
        Text('Application overview',
            style: Theme.of(context)
                .textTheme
                .titleLarge
                ?.copyWith(fontWeight: FontWeight.w900)),
        const SizedBox(height: 10),
        Wrap(spacing: 10, runSpacing: 10, children: [
          _Metric('Stations', data.stations, Icons.train_rounded),
          _Metric('Contracts', data.contracts.length, Icons.handshake_rounded),
          _Metric('Amenities', data.amenities.length,
              Icons.accessibility_new_rounded),
          _Metric('Works', data.works.length, Icons.construction_rounded),
          _Metric('Open works', openWorks, Icons.pending_actions_rounded),
        ]),
        const SizedBox(height: AppSpacing.x2),
        NeoPanel(
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('Contract portfolio',
                style: TextStyle(fontWeight: FontWeight.w900, fontSize: 16)),
            const SizedBox(height: 12),
            for (final entry in groups.entries)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(children: [
                  Expanded(child: Text(entry.key)),
                  StatusBadge('${entry.value}')
                ]),
              ),
          ]),
        ),
        const SizedBox(height: AppSpacing.x2),
        const NeoPanel(
            child: Row(children: [
          Icon(Icons.storage_rounded),
          SizedBox(width: 10),
          Expanded(
              child: Text(
                  'This report is generated from the latest station data stored offline on this device. Use Sync to refresh PostgreSQL data.'))
        ])),
      ],
    );
  }
}

class _Metric extends StatelessWidget {
  const _Metric(this.label, this.value, this.icon);
  final String label;
  final int value;
  final IconData icon;
  @override
  Widget build(BuildContext context) => SizedBox(
      width: 145,
      child: NeoPanel(
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Icon(icon, color: Theme.of(context).colorScheme.primary),
        const SizedBox(height: 8),
        Text('$value',
            style: Theme.of(context)
                .textTheme
                .headlineSmall
                ?.copyWith(fontWeight: FontWeight.w900)),
        Text(label)
      ])));
}

class _ReportRegister extends StatefulWidget {
  const _ReportRegister(
      {required this.title,
      required this.rows,
      required this.groups,
      this.workFilters = false,
      this.dimensions = const ['report_group'],
      required this.columns});
  final String title;
  final List<Map<String, dynamic>> rows;
  final List<String> groups;
  final bool workFilters;
  final List<String> dimensions;
  final List<String> columns;
  @override
  State<_ReportRegister> createState() => _ReportRegisterState();
}

class _ReportRegisterState extends State<_ReportRegister> {
  String _group = 'All';
  String _dimension = 'report_group';
  String _dimensionValue = 'All';
  String _section = 'All';
  String _type = 'All';
  String _query = '';
  bool _exporting = false;

  List<Map<String, dynamic>> get _filtered {
    final q = _query.trim().toLowerCase();
    return widget.rows.where((row) {
      final groupOk = widget.workFilters
          ? (_type == 'All' || '${row['report_group']}' == _type)
          : _dimension == 'report_group'
              ? (_group == 'All' || '${row['report_group']}' == _group)
              : (_dimensionValue == 'All' ||
                  '${row[_dimension] ?? 'Unassigned'}' == _dimensionValue);
      final sectionOk = !widget.workFilters ||
          _section == 'All' ||
          '${row['work_section'] ?? 'Other'}' == _section;
      final queryOk = q.isEmpty ||
          row.values.any((value) => '$value'.toLowerCase().contains(q));
      return groupOk && sectionOk && queryOk;
    }).toList();
  }

  Future<void> _export(bool pdf) async {
    setState(() => _exporting = true);
    try {
      final rows = _filtered;
      if (pdf) {
        await exportReportPdf(
            title: widget.title,
            subtitle: '${rows.length} records · filter: $_group',
            rows: rows,
            columns: widget.columns);
      } else {
        final file = await exportReportCsv(
            title: widget.title, rows: rows, columns: widget.columns);
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
                content: Text('Excel-compatible CSV saved to ${file.path}')),
          );
        }
      }
    } catch (error) {
      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Export failed: $error')));
    } finally {
      if (mounted) setState(() => _exporting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final rows = _filtered;
    final dimensionValues = _dimension == 'report_group'
        ? widget.groups
        : (widget.rows
            .map((row) => '${row[_dimension] ?? 'Unassigned'}')
            .where((value) => value.trim().isNotEmpty && value != 'null')
            .toSet()
            .toList()
          ..sort());
    return Column(children: [
      Padding(
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.page),
          child: TextField(
              decoration: const InputDecoration(
                  prefixIcon: Icon(Icons.search_rounded),
                  hintText: 'Search this report'),
              onChanged: (value) => setState(() => _query = value))),
      const SizedBox(height: 10),
      if (widget.workFilters)
        _WorkFilterPanel(
          rows: widget.rows,
          groups: widget.groups,
          section: _section,
          type: _type,
          onSection: (value) => setState(() => _section = value),
          onType: (value) => setState(() => _type = value),
        )
      else ...[
        SizedBox(
            height: 38,
            child: ListView.separated(
                padding:
                    const EdgeInsets.symmetric(horizontal: AppSpacing.page),
                scrollDirection: Axis.horizontal,
                itemCount: widget.dimensions.length,
                separatorBuilder: (_, __) => const SizedBox(width: 7),
                itemBuilder: (_, index) {
                  final label = _label(widget.dimensions[index]);
                  return _ReportChip(
                      label: label,
                      selected: _dimension == widget.dimensions[index],
                      onTap: () => setState(() {
                            _dimension = widget.dimensions[index];
                            _dimensionValue = 'All';
                            _group = 'All';
                          }));
                })),
        const SizedBox(height: 7),
        SizedBox(
            height: 38,
            child: ListView.separated(
                padding:
                    const EdgeInsets.symmetric(horizontal: AppSpacing.page),
                scrollDirection: Axis.horizontal,
                itemCount: dimensionValues.length + 1,
                separatorBuilder: (_, __) => const SizedBox(width: 7),
                itemBuilder: (_, index) {
                  final label = index == 0 ? 'All' : dimensionValues[index - 1];
                  final selected = (_dimension == 'report_group'
                          ? _group
                          : _dimensionValue) ==
                      label;
                  return _ReportChip(
                      label: label,
                      selected: selected,
                      onTap: () => setState(() {
                            if (_dimension == 'report_group') {
                              _group = label;
                            } else {
                              _dimensionValue = label;
                            }
                          }));
                })),
      ],
      Padding(
          padding: const EdgeInsets.fromLTRB(
              AppSpacing.page, 10, AppSpacing.page, 6),
          child: Row(children: [
            Expanded(
                child: Text('${rows.length} records',
                    style: const TextStyle(fontWeight: FontWeight.w900))),
            if (_exporting)
              const SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(strokeWidth: 2))
            else ...[
              AppIconButton(
                  tooltip: 'Export PDF',
                  icon: Icons.picture_as_pdf_rounded,
                  onPressed: () => _export(true)),
              AppIconButton(
                  tooltip: 'Export Excel CSV',
                  icon: Icons.table_view_rounded,
                  onPressed: () => _export(false))
            ]
          ])),
      Expanded(
          child: rows.isEmpty
              ? const EmptyState(
                  icon: Icons.filter_alt_off_rounded,
                  title: 'No matching records',
                  message: 'Try another category or search term.')
              : ListView.separated(
                  padding: const EdgeInsets.fromLTRB(
                      AppSpacing.page, 0, AppSpacing.page, 28),
                  itemCount: rows.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 8),
                  itemBuilder: (_, index) => _ReportRow(
                      row: rows[index],
                      columns: widget.columns,
                      onTap: () => showGlassBottomSheet<void>(context,
                          builder: (_) => _ReportDetailSheet(
                              title: widget.title, row: rows[index]))))),
    ]);
  }
}

class _WorkFilterPanel extends StatelessWidget {
  const _WorkFilterPanel({
    required this.rows,
    required this.groups,
    required this.section,
    required this.type,
    required this.onSection,
    required this.onType,
  });

  final List<Map<String, dynamic>> rows;
  final List<String> groups;
  final String section;
  final String type;
  final ValueChanged<String> onSection;
  final ValueChanged<String> onType;

  @override
  Widget build(BuildContext context) {
    final sections = rows
        .map((row) => '${row['work_section'] ?? 'Other'}')
        .where((value) => value.trim().isNotEmpty)
        .toSet()
        .toList()
      ..sort();
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.page),
      child: NeoPanel(
        padding: const EdgeInsets.fromLTRB(12, 12, 12, 10),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Section', style: TextStyle(fontWeight: FontWeight.w900)),
          const SizedBox(height: 8),
          _chipList(
              values: ['All', ...sections],
              selected: section,
              onSelected: onSection),
          const SizedBox(height: 12),
          const Text('Work type',
              style: TextStyle(fontWeight: FontWeight.w900)),
          const SizedBox(height: 8),
          _chipList(
              values: ['All', ...groups], selected: type, onSelected: onType),
        ]),
      ),
    );
  }
}

Widget _chipList({
  required List<String> values,
  required String selected,
  required ValueChanged<String> onSelected,
}) =>
    SizedBox(
        height: 38,
        child: ListView.separated(
          scrollDirection: Axis.horizontal,
          itemCount: values.length,
          separatorBuilder: (_, __) => const SizedBox(width: 7),
          itemBuilder: (_, index) {
            final value = values[index];
            return _ReportChip(
                label: value,
                selected: selected == value,
                onTap: () => onSelected(value));
          },
        ));

class _ReportRow extends StatelessWidget {
  const _ReportRow(
      {required this.row, required this.columns, required this.onTap});
  final Map<String, dynamic> row;
  final List<String> columns;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) => NeoPanel(
      onTap: onTap,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(
              child: Text('${row[columns.first] ?? '-'}',
                  style: const TextStyle(fontWeight: FontWeight.w900))),
          StatusBadge('${row['report_group'] ?? ''}'),
          if (row['deletion_recommended'] == true)
            const Padding(
              padding: EdgeInsets.only(left: 6),
              child: StatusBadge('Deletion recommended', tone: AppPalette.red),
            )
        ]),
        const SizedBox(height: 6),
        for (final column in columns.skip(1))
          if ('${row[column] ?? ''}'.trim().isNotEmpty &&
              '${row[column]}' != 'null')
            Padding(
                padding: const EdgeInsets.only(bottom: 3),
                child: Text('${_label(column)}: ${row[column]}',
                    maxLines: 3, overflow: TextOverflow.ellipsis))
      ]));
}

class _ReportDetailSheet extends StatelessWidget {
  const _ReportDetailSheet({required this.title, required this.row});

  final String title;
  final Map<String, dynamic> row;

  @override
  Widget build(BuildContext context) {
    final entries = row.entries
        .where((entry) =>
            entry.value != null &&
            '${entry.value}'.trim().isNotEmpty &&
            '${entry.value}' != '[]' &&
            '${entry.value}' != '{}')
        .toList();
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
            Text('${row['station_code'] ?? 'Record'}',
                style: Theme.of(context).textTheme.labelLarge?.copyWith(
                    color: AppPalette.teal,
                    fontWeight: FontWeight.w900,
                    letterSpacing: 1.2)),
            const SizedBox(height: 4),
            Text(title.replaceFirst(' register', ''),
                style: Theme.of(context)
                    .textTheme
                    .headlineSmall
                    ?.copyWith(fontWeight: FontWeight.w900)),
            if (row['deletion_recommended'] == true) ...[
              const SizedBox(height: 8),
              const StatusBadge('Deletion recommended', tone: AppPalette.red),
            ],
            const SizedBox(height: 16),
            Flexible(
              child: ListView.separated(
                shrinkWrap: true,
                itemCount: entries.length,
                separatorBuilder: (_, __) => const Divider(height: 16),
                itemBuilder: (_, index) {
                  final entry = entries[index];
                  return Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        SizedBox(
                            width: 125,
                            child: Text(_label(entry.key),
                                style: Theme.of(context)
                                    .textTheme
                                    .bodySmall
                                    ?.copyWith(fontWeight: FontWeight.w800))),
                        const SizedBox(width: 12),
                        Expanded(child: Text('${entry.value}')),
                      ]);
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ReportChip extends StatelessWidget {
  const _ReportChip(
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

List<String> _groups(List<Map<String, dynamic>> rows) => rows
    .map((row) => '${row['report_group'] ?? 'Other'}')
    .where((value) => value.trim().isNotEmpty)
    .toSet()
    .toList()
  ..sort();
List<dynamic> _list(Object? value) => value is List ? value : const [];
Map<String, dynamic> _map(Object? value) =>
    value is Map ? Map<String, dynamic>.from(value) : <String, dynamic>{};
String _label(String value) => value
    .split('_')
    .map((part) =>
        part.isEmpty ? part : '${part[0].toUpperCase()}${part.substring(1)}')
    .join(' ');
bool _isComplete(Object? value) {
  final text = '$value'.toLowerCase();
  return text.contains('complete') || text.contains('done');
}

Object? _first(Map raw, List<String> keys) {
  for (final key in keys) {
    final value = raw[key];
    if (value != null && '$value'.trim().isNotEmpty && '$value' != 'null')
      return value;
  }
  return null;
}

bool _truthy(Object? value) {
  final text = '$value'.trim().toLowerCase();
  return text == 'true' || text == 'yes' || text == 'y' || text == '1';
}

String _contractGroup(Map<String, dynamic> row) {
  final text =
      '${row['type_of_unit'] ?? ''} ${row['sub_category'] ?? ''} ${row['policy'] ?? ''} ${row['contract_name'] ?? ''} ${row['remarks'] ?? ''}'
          .toLowerCase();
  if (text.contains('milk')) return 'Milk stalls';
  if (text.contains('mps')) return 'MPS stalls';
  if (text.contains('rdn')) return 'RDN';
  if (text.contains('train') ||
      text.contains('on board') ||
      text.contains('mobile')) return 'Train-based contracts';
  if (text.contains('nfr') || text.contains('non fare')) return 'NFR contracts';
  if (text.contains('catering') ||
      text.contains('stall') ||
      text.contains('unit')) return 'Catering units';
  return '${row['type_of_unit'] ?? row['policy'] ?? 'Other contracts'}'
          .trim()
          .isEmpty
      ? 'Other contracts'
      : '${row['type_of_unit'] ?? row['policy']}';
}

String _workGroup(Map<String, dynamic> row, {bool abss = false}) {
  final text =
      '${row['short_name_of_work'] ?? ''} ${row['work_name'] ?? ''} ${row['remarks'] ?? ''} ${row['category'] ?? ''} ${row['parent_work'] ?? ''} ${row['block_section_station'] ?? ''} ${row['scope_type'] ?? ''} ${row['scope_value'] ?? ''} ${row['match_status'] ?? ''} ${row['section'] ?? ''}'
          .toLowerCase();
  final scope =
      '${row['scope_type'] ?? ''} ${row['scope_value'] ?? ''} ${row['match_status'] ?? ''} ${row['block_section_station'] ?? ''}'
          .toLowerCase();
  if (abss || scope.contains('abss')) return 'ABSS works';
  if (text.contains('cao/cn') || text.contains('cao cn')) return 'CAO/CN works';
  if (text.contains('goods') ||
      text.contains('csgr') ||
      text.contains('goods shed')) {
    return 'Goods / CSGR works';
  }
  if (text.contains('fob') || text.contains('foot over')) return 'FOB works';
  if (text.contains('shelter') || text.contains('platform shelter')) {
    return 'Platform shelter works';
  }
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

String _workSection(Map<String, dynamic> row) {
  final raw = '${row['section'] ?? ''}'.trim();
  final text = raw.toLowerCase();
  if (text.contains('north')) return 'North';
  if (text.contains('south')) return 'South';
  if (text.contains('east')) return 'East';
  if (text.contains('west')) return 'West';
  if (text == 'div' || text.contains('division')) return 'Division';
  if (text.contains('cao/cn') || text.contains('cao cn')) return 'CAO/CN';
  if (text.contains('sr.dcm') || text.contains('sr dcm')) return 'Sr.DCM';
  if (text.contains('sr.dste') || text.contains('sr dste')) return 'Sr.DSTE';
  if (text.contains('sdee')) return 'SDEE';
  if (text.contains('gsu') || text.contains('gati sakthi')) return 'GSU/SBC';
  return raw.isEmpty ? 'Other' : raw;
}

bool _deletionRecommended(Map<String, dynamic> row) {
  final text =
      '${row['remarks'] ?? ''} ${row['engg_remarks'] ?? ''} ${row['status'] ?? ''}'
          .toLowerCase();
  return text.contains('proposal dropped') ||
      text.contains('proposed for deletion') ||
      text.contains('recommended for deletion') ||
      text.contains('work deleted') ||
      text.contains('deletion recommended');
}
