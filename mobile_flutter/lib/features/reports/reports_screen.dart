import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/local/app_database.dart';
import '../../shared/widgets.dart';

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
    for (final row in stations) {
      final detail = row['_station_detail'];
      if (detail is! Map) continue;
      final contractRows = [
        ...(detail['contracts'] is List
            ? detail['contracts'] as List
            : const []),
        ...(detail['commercial_contracts'] is List
            ? detail['commercial_contracts'] as List
            : const []),
      ];
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
                  _ContractReport(rows: data.notifications),
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
    required this.findings,
  });

  final int stations;
  final int units;
  final int contracts;
  final int works;
  final int openWorks;
  final List<Map<String, dynamic>> notifications;
  final List<Map<String, dynamic>> findings;
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

class _ContractReport extends StatelessWidget {
  const _ContractReport({required this.rows});
  final List<Map<String, dynamic>> rows;

  @override
  Widget build(BuildContext context) {
    final alerts =
        rows.where((row) => row['type'] == 'contract_expiry').toList();
    if (alerts.isEmpty) {
      return const EmptyState(
          icon: Icons.verified_rounded,
          title: 'No contract alerts',
          message:
              'No contracts are due within the current 90-day alert window.');
    }
    return ListView.separated(
      padding:
          const EdgeInsets.fromLTRB(AppSpacing.page, 0, AppSpacing.page, 28),
      itemCount: alerts.length,
      separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.x1),
      itemBuilder: (context, index) {
        final row = alerts[index];
        return GlassPanel(
          child: ListTile(
            contentPadding: EdgeInsets.zero,
            leading: Icon(
                row['severity'] == 'critical'
                    ? Icons.warning_rounded
                    : Icons.event_available_rounded,
                color:
                    row['severity'] == 'critical' ? Colors.red : Colors.orange),
            title: Text('${row['title']}',
                style: const TextStyle(fontWeight: FontWeight.w800)),
            subtitle: Text('${row['body']}'),
            trailing: row['is_read'] == 1 ? null : const StatusBadge('New'),
          ),
        );
      },
    );
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
