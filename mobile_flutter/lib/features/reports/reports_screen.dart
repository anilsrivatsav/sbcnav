import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../data/local/app_database.dart';
import '../../shared/widgets.dart';
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
  int _contractWindow = 30;

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 3, vsync: this);
    _report = _load();
  }

  Future<_ReportData> _load() async {
    final database = ref.read(databaseProvider);
    final stations = await database.stationOverviewRows();
    final notifications = await database.notifications();
    final findings = await database.findings();
    var units = 0;
    var contracts = 0;
    var works = 0;
    var openWorks = 0;
    final contractValidity = <String, Map<String, dynamic>>{};
    for (final row in stations) {
      final detail = row['_station_detail'];
      if (detail is! Map) continue;
      final stationCode =
          '${row['station_code'] ?? detail['station_code'] ?? ''}'
              .trim()
              .toUpperCase();
      final stationName =
          '${row['station_name'] ?? detail['station_name'] ?? ''}'.trim();
      final cateringRows =
          detail['contracts'] is List ? detail['contracts'] as List : const [];
      final commercialRows = detail['commercial_contracts'] is List
          ? detail['commercial_contracts'] as List
          : const [];
      final contractRows = [...cateringRows, ...commercialRows];
      for (final value in cateringRows) {
        if (value is! Map) continue;
        _addContractValidity(
          contractValidity,
          value,
          stationCode: stationCode,
          stationName: stationName,
          sourceType: 'unit',
        );
      }
      for (final value in commercialRows) {
        if (value is! Map) continue;
        _addContractValidity(
          contractValidity,
          value,
          stationCode: stationCode,
          stationName: stationName,
          sourceType: 'commercial',
        );
      }
      final unitRows = detail['units'];
      final workRows = detail['works'];
      units += unitRows is List ? unitRows.length : 0;
      contracts += contractRows.length;
      if (workRows is List) {
        works += workRows.length;
        openWorks += workRows.where((work) {
          final status = '${work is Map ? work['status'] : ''}'.toLowerCase();
          return !status.contains('complete') && !status.contains('done');
        }).length;
      }
    }
    return _ReportData(
      stations: stations.length,
      units: units,
      contracts: contracts,
      works: works,
      openWorks: openWorks,
      notifications: notifications,
      contractValidity: contractValidity.values.toList()
        ..sort((a, b) =>
            (a['days_remaining'] as int).compareTo(b['days_remaining'] as int)),
      findings: findings,
    );
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
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const GlassLoadingList(itemCount: 5);
        }
        if (snapshot.hasError) {
          return ErrorPane(error: snapshot.error!, retry: _reload);
        }
        final data = snapshot.data!;
        return Column(
          children: [
            const Padding(
              padding: EdgeInsets.fromLTRB(
                AppSpacing.page,
                AppSpacing.x3,
                AppSpacing.page,
                AppSpacing.x1,
              ),
              child: PageHeading(
                title: 'Reports',
                subtitle:
                    'Actionable station, contract and inspection summaries.',
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.page),
              child: GlassPanel(
                padding: const EdgeInsets.all(6),
                child: TabBar(
                  controller: _tabs,
                  tabs: const [
                    Tab(text: 'Overview'),
                    Tab(text: 'Contracts'),
                    Tab(text: 'Findings'),
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
                  _ContractReport(
                    rows: data.contractValidity,
                    selectedDays: _contractWindow,
                    onSelected: (days) =>
                        setState(() => _contractWindow = days),
                  ),
                  _FindingReport(rows: data.findings),
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
  const _ReportData({
    required this.stations,
    required this.units,
    required this.contracts,
    required this.works,
    required this.openWorks,
    required this.notifications,
    required this.contractValidity,
    required this.findings,
  });

  final int stations;
  final int units;
  final int contracts;
  final int works;
  final int openWorks;
  final List<Map<String, dynamic>> notifications;
  final List<Map<String, dynamic>> contractValidity;
  final List<Map<String, dynamic>> findings;
}

void _addContractValidity(
  Map<String, Map<String, dynamic>> target,
  Map contract, {
  required String stationCode,
  required String stationName,
  required String sourceType,
}) {
  final validTo = _parseReportDate(contract['valid_to'] ??
      contract['contract_to'] ??
      contract['contract_upto'] ??
      contract['contract_period_to']);
  if (validTo == null) return;
  final now = DateTime.now();
  final today = DateTime(now.year, now.month, now.day);
  final due = DateTime(validTo.year, validTo.month, validTo.day);
  final days = due.difference(today).inDays;
  if (days < 0) return;

  final code =
      '${contract['unit_no'] ?? contract['allocation_code'] ?? contract['contract_key'] ?? ''}'
          .trim();
  final rawName =
      '${contract['contract_name'] ?? contract['licensee_name'] ?? ''}'.trim();
  final type =
      '${contract['type_of_unit'] ?? contract['sub_category'] ?? contract['policy'] ?? 'Contract'}'
          .trim();
  final name = rawName.isEmpty || rawName.toUpperCase() == 'NA'
      ? (type.isEmpty ? 'Contract' : type)
      : rawName;
  final identity = code.isNotEmpty ? code : name;
  final key = '$sourceType:$stationCode:${identity.toUpperCase()}';
  target[key] = {
    ...contract.map((key, value) => MapEntry('$key', value)),
    'key': key,
    'source_type': sourceType,
    'contract_code': code.isEmpty ? 'No code' : code,
    'contract_name': name,
    'contract_type': type,
    'station_code': stationCode,
    'station_name': stationName,
    'valid_to': due.toIso8601String(),
    'days_remaining': days,
  };
}

DateTime? _parseReportDate(Object? value) {
  final text = '${value ?? ''}'.trim();
  if (text.isEmpty || text.toLowerCase() == 'null') return null;
  final iso = DateTime.tryParse(text);
  if (iso != null) return iso;
  final parts = text.split(RegExp(r'[/\-.]'));
  if (parts.length != 3) return null;
  final first = int.tryParse(parts[0]);
  final month = int.tryParse(parts[1]);
  final last = int.tryParse(parts[2]);
  if (first == null || month == null || last == null) return null;
  final year = parts[2].length == 2 ? 2000 + last : last;
  try {
    return DateTime(year, month, first);
  } on ArgumentError {
    return null;
  }
}

class _OverviewReport extends StatelessWidget {
  const _OverviewReport({required this.data});
  final _ReportData data;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding:
          const EdgeInsets.fromLTRB(AppSpacing.page, 0, AppSpacing.page, 28),
      children: [
        Wrap(
          spacing: 10,
          runSpacing: 10,
          children: [
            _ReportMetric(
                label: 'Stations',
                value: data.stations,
                icon: Icons.train_rounded),
            _ReportMetric(
                label: 'Units',
                value: data.units,
                icon: Icons.storefront_rounded),
            _ReportMetric(
                label: 'Contracts',
                value: data.contracts,
                icon: Icons.assignment_rounded),
            _ReportMetric(
                label: 'Works',
                value: data.works,
                icon: Icons.construction_rounded),
            _ReportMetric(
                label: 'Open works',
                value: data.openWorks,
                icon: Icons.pending_actions_rounded),
          ],
        ),
        const SizedBox(height: AppSpacing.x2),
        GlassPanel(
          child: Row(
            children: [
              Icon(Icons.cloud_done_rounded,
                  color: Theme.of(context).colorScheme.primary),
              const SizedBox(width: 10),
              const Expanded(
                child: Text(
                    'Reports use the latest station details stored on this device. Refresh from PostgreSQL to update them.'),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _ReportMetric extends StatelessWidget {
  const _ReportMetric(
      {required this.label, required this.value, required this.icon});
  final String label;
  final int value;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 145,
      child: GlassPanel(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, color: Theme.of(context).colorScheme.primary),
            const SizedBox(height: 10),
            Text('$value',
                style: Theme.of(context)
                    .textTheme
                    .headlineSmall
                    ?.copyWith(fontWeight: FontWeight.w900)),
            Text(label),
          ],
        ),
      ),
    );
  }
}

class _ContractReport extends StatefulWidget {
  const _ContractReport({
    required this.rows,
    required this.selectedDays,
    required this.onSelected,
  });

  final List<Map<String, dynamic>> rows;
  final int selectedDays;
  final ValueChanged<int> onSelected;

  @override
  State<_ContractReport> createState() => _ContractReportState();
}

class _ContractReportState extends State<_ContractReport> {
  static const _rowsPerPage = 5;
  int _page = 0;
  bool _exporting = false;

  @override
  void didUpdateWidget(covariant _ContractReport oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.selectedDays != widget.selectedDays ||
        oldWidget.rows != widget.rows) {
      _page = 0;
    }
  }

  Future<void> _export(List<Map<String, dynamic>> alerts) async {
    if (_exporting) return;
    setState(() => _exporting = true);
    try {
      await exportContractExpiryPdf(
        rows: alerts,
        windowDays: widget.selectedDays,
        moreThanFiftyDays: widget.selectedDays == 51,
      );
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('PDF export failed: $error')),
      );
    } finally {
      if (mounted) setState(() => _exporting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final source = widget.rows
        .where((row) => row['days_remaining'] is int)
        .toList()
      ..sort((a, b) =>
          (a['days_remaining'] as int).compareTo(b['days_remaining'] as int));
    final alerts = widget.selectedDays == 51
        ? source.where((item) => (item['days_remaining'] as int) > 50).toList()
        : source
            .where((item) =>
                (item['days_remaining'] as int) <= widget.selectedDays)
            .toList();
    final pageCount =
        alerts.isEmpty ? 1 : (alerts.length / _rowsPerPage).ceil();
    final safePage = _page.clamp(0, pageCount - 1);
    final start = safePage * _rowsPerPage;
    final pageRows = alerts.skip(start).take(_rowsPerPage).toList();

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.page),
          child: Row(
            children: [
              for (final days in const [30, 10, 5, 51])
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 3),
                    child: GlassFilterChip(
                      label: days == 51 ? '50+' : '${days}d',
                      selected: widget.selectedDays == days,
                      onTap: () => widget.onSelected(days),
                    ),
                  ),
                ),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.x1),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.page),
          child: Row(
            children: [
              Expanded(
                child: Text(
                  widget.selectedDays == 51
                      ? '${alerts.length} contracts valid beyond 50 days'
                      : '${alerts.length} contracts within ${widget.selectedDays} days',
                  style: Theme.of(context)
                      .textTheme
                      .labelLarge
                      ?.copyWith(fontWeight: FontWeight.w900),
                ),
              ),
              AppIconButton(
                tooltip: 'Export all matching contracts to PDF',
                icon: _exporting
                    ? Icons.hourglass_top_rounded
                    : Icons.picture_as_pdf_rounded,
                onPressed: _exporting ? null : () => _export(alerts),
              ),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.x1),
        Expanded(
          child: alerts.isEmpty
              ? EmptyState(
                  icon: Icons.verified_rounded,
                  title: widget.selectedDays == 51
                      ? 'No contracts valid beyond 50 days'
                      : 'No contracts due within ${widget.selectedDays} days',
                  message:
                      'The list updates from actual contract validity dates after a PostgreSQL refresh.',
                )
              : Padding(
                  padding:
                      const EdgeInsets.symmetric(horizontal: AppSpacing.page),
                  child: Column(
                    children: [
                      for (final item in pageRows) ...[
                        SizedBox(
                          height: 62,
                          child: GlassPanel(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 10, vertical: 6),
                            child: Row(
                              children: [
                                Container(
                                  width: 42,
                                  height: 42,
                                  alignment: Alignment.center,
                                  decoration: BoxDecoration(
                                    color: _contractTone(
                                            item['days_remaining'] as int)
                                        .withValues(alpha: 0.12),
                                    borderRadius: BorderRadius.circular(14),
                                  ),
                                  child: Text(
                                    '${item['contract_code']}',
                                    maxLines: 2,
                                    textAlign: TextAlign.center,
                                    overflow: TextOverflow.ellipsis,
                                    style: TextStyle(
                                      fontSize: 10,
                                      fontWeight: FontWeight.w900,
                                      color: _contractTone(
                                          item['days_remaining'] as int),
                                    ),
                                  ),
                                ),
                                const SizedBox(width: 9),
                                Expanded(
                                  child: Column(
                                    mainAxisAlignment: MainAxisAlignment.center,
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        '${item['contract_name']}',
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                        style: const TextStyle(
                                            fontWeight: FontWeight.w900),
                                      ),
                                      const SizedBox(height: 2),
                                      Row(
                                        children: [
                                          Icon(Icons.location_on_rounded,
                                              size: 12,
                                              color: Theme.of(context)
                                                  .colorScheme
                                                  .primary),
                                          const SizedBox(width: 2),
                                          Text(
                                            '${item['station_code']}',
                                            style: Theme.of(context)
                                                .textTheme
                                                .bodySmall
                                                ?.copyWith(
                                                    fontWeight:
                                                        FontWeight.w800),
                                          ),
                                          const Text('  ·  '),
                                          Flexible(
                                            child: Text(
                                              _shortDate(item['valid_to']),
                                              maxLines: 1,
                                              overflow: TextOverflow.ellipsis,
                                              style: Theme.of(context)
                                                  .textTheme
                                                  .bodySmall,
                                            ),
                                          ),
                                        ],
                                      ),
                                    ],
                                  ),
                                ),
                                const SizedBox(width: 8),
                                StatusBadge(
                                  (item['days_remaining'] as int) == 0
                                      ? 'Today'
                                      : '${item['days_remaining']}d',
                                  tone: _contractTone(
                                      item['days_remaining'] as int),
                                ),
                              ],
                            ),
                          ),
                        ),
                        const SizedBox(height: AppSpacing.x1),
                      ],
                    ],
                  ),
                ),
        ),
        if (alerts.isNotEmpty)
          Padding(
            padding: const EdgeInsets.fromLTRB(
                AppSpacing.page, 4, AppSpacing.page, 8),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                AppIconButton(
                  tooltip: 'Previous page',
                  icon: Icons.chevron_left_rounded,
                  onPressed: safePage == 0
                      ? null
                      : () => setState(() => _page = safePage - 1),
                ),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 14),
                  child: Text(
                    'Page ${safePage + 1} of $pageCount',
                    style: const TextStyle(fontWeight: FontWeight.w900),
                  ),
                ),
                AppIconButton(
                  tooltip: 'Next page',
                  icon: Icons.chevron_right_rounded,
                  onPressed: safePage >= pageCount - 1
                      ? null
                      : () => setState(() => _page = safePage + 1),
                ),
              ],
            ),
          ),
      ],
    );
  }

  Color _contractTone(int days) {
    if (days <= 10) return Colors.red;
    if (days <= 30) return Colors.orange;
    return Colors.green;
  }

  String _shortDate(Object? value) {
    final date = DateTime.tryParse('${value ?? ''}');
    return date == null
        ? 'Date unavailable'
        : DateFormat('dd MMM yyyy').format(date);
  }
}

class _FindingReport extends StatelessWidget {
  const _FindingReport({required this.rows});
  final List<Map<String, dynamic>> rows;

  @override
  Widget build(BuildContext context) {
    if (rows.isEmpty) {
      return const EmptyState(
          icon: Icons.task_alt_rounded,
          title: 'No findings',
          message: 'Inspection observations needing action will appear here.');
    }
    return ListView.separated(
      padding:
          const EdgeInsets.fromLTRB(AppSpacing.page, 0, AppSpacing.page, 28),
      itemCount: rows.length,
      separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.x1),
      itemBuilder: (context, index) {
        final row = rows[index];
        return GlassPanel(
          child: ListTile(
            contentPadding: EdgeInsets.zero,
            title: Text('${row['title']}',
                style: const TextStyle(fontWeight: FontWeight.w800)),
            subtitle: Text(
                '${row['station_code'] ?? 'Station'} · ${row['status'] ?? 'Open'}'),
            trailing: StatusBadge('${row['severity'] ?? 'medium'}'),
          ),
        );
      },
    );
  }
}
