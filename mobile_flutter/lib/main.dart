import 'package:flutter/material.dart';

import 'api_client.dart';
import 'widgets/dashboard_widgets.dart';

void main() {
  runApp(const RailDashboardMobileApp());
}

class RailDashboardMobileApp extends StatelessWidget {
  const RailDashboardMobileApp({super.key});

  @override
  Widget build(BuildContext context) {
    final seed = const Color(0xFF0F766E);
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Rail Dashboard',
      themeMode: ThemeMode.system,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(seedColor: seed, brightness: Brightness.light),
        scaffoldBackgroundColor: const Color(0xFFEAF2F4),
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: Colors.white.withOpacity(0.75),
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(18), borderSide: BorderSide.none),
          focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(18), borderSide: const BorderSide(color: Color(0xFF0F766E))),
        ),
      ),
      darkTheme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(seedColor: seed, brightness: Brightness.dark),
        scaffoldBackgroundColor: const Color(0xFF08131A),
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: const Color(0xFF122431).withOpacity(0.78),
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(18), borderSide: BorderSide.none),
          focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(18), borderSide: const BorderSide(color: Color(0xFF2DD4BF))),
        ),
      ),
      home: const MobileShell(),
    );
  }
}

class MobileShell extends StatefulWidget {
  const MobileShell({super.key});

  @override
  State<MobileShell> createState() => _MobileShellState();
}

class _MobileShellState extends State<MobileShell> {
  final api = RailApiClient();
  var selectedIndex = 0;

  @override
  Widget build(BuildContext context) {
    final destinations = [
      _Destination('Home', Icons.dashboard_rounded, DashboardScreen(api: api)),
      _Destination('Stations', Icons.train_rounded, StationsScreen(api: api)),
      _Destination('Contracts', Icons.storefront_rounded, ContractsScreen(api: api)),
      _Destination('Amenities', Icons.accessible_forward_rounded, AmenitiesScreen(api: api)),
      _Destination('Reports', Icons.query_stats_rounded, ReportsScreen(api: api)),
    ];
    final destination = destinations[selectedIndex];

    return Scaffold(
      body: Stack(
        children: [
          const _Background(),
          SafeArea(
            child: Column(
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
                  child: _TopBar(title: destination.label),
                ),
                Expanded(child: destination.screen),
              ],
            ),
          ),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: selectedIndex,
        onDestinationSelected: (index) => setState(() => selectedIndex = index),
        destinations: [
          for (final item in destinations)
            NavigationDestination(icon: Icon(item.icon), label: item.label),
        ],
      ),
    );
  }
}

class _Destination {
  const _Destination(this.label, this.icon, this.screen);

  final String label;
  final IconData icon;
  final Widget screen;
}

class _Background extends StatelessWidget {
  const _Background();

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return DecoratedBox(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: isDark
              ? const [Color(0xFF071219), Color(0xFF0E2430), Color(0xFF10251F)]
              : const [Color(0xFFEAF2F4), Color(0xFFF8FBFC), Color(0xFFDDEEEF)],
        ),
      ),
      child: const SizedBox.expand(),
    );
  }
}

class _TopBar extends StatelessWidget {
  const _TopBar({required this.title});

  final String title;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Row(
      children: [
        Container(
          padding: const EdgeInsets.all(11),
          decoration: BoxDecoration(
            color: theme.colorScheme.primaryContainer,
            borderRadius: BorderRadius.circular(18),
          ),
          child: Icon(Icons.railway_alert_rounded, color: theme.colorScheme.onPrimaryContainer),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Rail Dashboard'.toUpperCase(), style: theme.textTheme.labelSmall?.copyWith(fontWeight: FontWeight.w900, letterSpacing: 1.4)),
              Text(title, style: theme.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w900)),
            ],
          ),
        ),
      ],
    );
  }
}

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({required this.api, super.key});

  final RailApiClient api;

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  late Future<_DashboardData> future;

  @override
  void initState() {
    super.initState();
    future = _load();
  }

  Future<_DashboardData> _load() async {
    final results = await Future.wait([
      widget.api.stats(),
      widget.api.reports(),
      widget.api.amenityReports(),
      widget.api.works(),
    ]);
    return _DashboardData(
      stats: results[0] as Map<String, dynamic>,
      reports: results[1] as Map<String, dynamic>,
      amenityReports: results[2] as Map<String, dynamic>,
      works: List<Map<String, dynamic>>.from(results[3] as List).take(6).toList(),
    );
  }

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: () async => setState(() => future = _load()),
      child: FutureBuilder<_DashboardData>(
        future: future,
        builder: (context, snapshot) {
          if (!snapshot.hasData) return const LoadingPane();
          final data = snapshot.data!;
          return ListView(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
            children: [
              SectionTitle(
                title: 'Operational pulse',
                subtitle: 'Quick read of stations, contracts, works, earnings, and amenities.',
                action: IconButton.filledTonal(
                  onPressed: () => setState(() => future = _load()),
                  icon: const Icon(Icons.refresh_rounded),
                ),
              ),
              const SizedBox(height: 14),
              GridView.count(
                crossAxisCount: 2,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                mainAxisSpacing: 12,
                crossAxisSpacing: 12,
                childAspectRatio: 0.95,
                children: [
                  MetricCard(label: 'Stations', value: textOf(data.stats['stations'], fallback: '0'), icon: Icons.train_rounded, color: const Color(0xFF0F766E)),
                  MetricCard(label: 'Units', value: textOf(data.stats['units'], fallback: '0'), icon: Icons.storefront_rounded, color: const Color(0xFF2563EB)),
                  MetricCard(label: 'Works', value: textOf(data.stats['works'], fallback: '0'), icon: Icons.construction_rounded, color: const Color(0xFFF59E0B)),
                  MetricCard(label: 'Revenue', value: moneyOf(data.stats['earningsTotal']), icon: Icons.account_balance_wallet_rounded, color: const Color(0xFF7C3AED)),
                ],
              ),
              const SizedBox(height: 18),
              GlassSurface(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const SectionTitle(title: 'Passenger amenities', subtitle: 'Ramp, lift, PF extension and infra coverage.'),
                    const SizedBox(height: 12),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        InfoChip(label: '${textOf(data.amenityReports['pf_extension_statuses'], fallback: '0')} PF status rows', icon: Icons.analytics_rounded),
                        InfoChip(label: '${textOf(data.amenityReports['ramp_feasible'], fallback: '0')} ramp feasible', icon: Icons.accessible_forward_rounded),
                        InfoChip(label: '${textOf(data.amenityReports['lift_proposed'], fallback: '0')} lift proposed', icon: Icons.elevator_rounded),
                        InfoChip(label: '${textOf(data.amenityReports['open_pa_works'], fallback: '0')} open PA works', icon: Icons.pending_actions_rounded),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 18),
              GlassSurface(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const SectionTitle(title: 'Recent works', subtitle: 'Latest linked sanctioned work records.'),
                    const SizedBox(height: 10),
                    for (final work in data.works) WorkTile(work: work, onTap: null),
                  ],
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _DashboardData {
  const _DashboardData({
    required this.stats,
    required this.reports,
    required this.amenityReports,
    required this.works,
  });

  final Map<String, dynamic> stats;
  final Map<String, dynamic> reports;
  final Map<String, dynamic> amenityReports;
  final List<Map<String, dynamic>> works;
}

class StationsScreen extends StatefulWidget {
  const StationsScreen({required this.api, super.key});

  final RailApiClient api;

  @override
  State<StationsScreen> createState() => _StationsScreenState();
}

class _StationsScreenState extends State<StationsScreen> {
  var search = '';
  late Future<List<Map<String, dynamic>>> future;

  @override
  void initState() {
    super.initState();
    future = widget.api.stations();
  }

  void _search(String value) {
    setState(() {
      search = value;
      future = widget.api.stations(search: value);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
          child: SearchBox(value: search, onChanged: _search, hint: 'Search station, section, division, category'),
        ),
        Expanded(
          child: FutureBuilder<List<Map<String, dynamic>>>(
            future: future,
            builder: (context, snapshot) {
              if (!snapshot.hasData) return const LoadingPane();
              final rows = snapshot.data!;
              if (rows.isEmpty) return const EmptyPane(title: 'No stations found');
              return ListView.separated(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
                itemCount: rows.length,
                separatorBuilder: (_, __) => const SizedBox(height: 10),
                itemBuilder: (context, index) => StationTile(
                  station: rows[index],
                  onTap: () => showStationDetail(context, widget.api, textOf(rows[index]['station_code'])),
                ),
              );
            },
          ),
        ),
      ],
    );
  }
}

class ContractsScreen extends StatefulWidget {
  const ContractsScreen({required this.api, super.key});

  final RailApiClient api;

  @override
  State<ContractsScreen> createState() => _ContractsScreenState();
}

class _ContractsScreenState extends State<ContractsScreen> {
  var search = '';
  var showPayments = false;
  late Future<List<Map<String, dynamic>>> future;

  @override
  void initState() {
    super.initState();
    future = widget.api.units();
  }

  void _reload() {
    future = showPayments ? widget.api.earnings(search: search) : widget.api.units(search: search);
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
          child: Column(
            children: [
              SearchBox(
                value: search,
                onChanged: (value) => setState(() {
                  search = value;
                  _reload();
                }),
                hint: showPayments ? 'Search payments and licensee' : 'Search unit, licensee, station',
              ),
              const SizedBox(height: 10),
              SegmentedButton<bool>(
                segments: const [
                  ButtonSegment(value: false, label: Text('Units'), icon: Icon(Icons.storefront_rounded)),
                  ButtonSegment(value: true, label: Text('Payments'), icon: Icon(Icons.payments_rounded)),
                ],
                selected: {showPayments},
                onSelectionChanged: (selection) => setState(() {
                  showPayments = selection.first;
                  _reload();
                }),
              ),
            ],
          ),
        ),
        Expanded(
          child: FutureBuilder<List<Map<String, dynamic>>>(
            future: future,
            builder: (context, snapshot) {
              if (!snapshot.hasData) return const LoadingPane();
              final rows = snapshot.data!;
              if (rows.isEmpty) return const EmptyPane(title: 'No contract records found');
              return ListView.separated(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
                itemCount: rows.length,
                separatorBuilder: (_, __) => const SizedBox(height: 10),
                itemBuilder: (context, index) => showPayments
                    ? EarningTile(earning: rows[index])
                    : UnitTile(unit: rows[index], onTap: () => showStationDetail(context, widget.api, textOf(rows[index]['station_code']))),
              );
            },
          ),
        ),
      ],
    );
  }
}

class AmenitiesScreen extends StatefulWidget {
  const AmenitiesScreen({required this.api, super.key});

  final RailApiClient api;

  @override
  State<AmenitiesScreen> createState() => _AmenitiesScreenState();
}

class _AmenitiesScreenState extends State<AmenitiesScreen> {
  var search = '';
  var kind = 'summary';
  late Future<List<Map<String, dynamic>>> future;

  final kinds = const [
    ('summary', 'Station'),
    ('platforms', 'PF'),
    ('pf_extension', 'PF Extn'),
    ('wheelchairs', 'Wheelchair'),
    ('trolley', 'Trolley'),
    ('pa_works', 'Works'),
  ];

  @override
  void initState() {
    super.initState();
    future = widget.api.amenities();
  }

  void _reload() {
    future = widget.api.amenities(kind: kind, search: search);
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
          child: Column(
            children: [
              SearchBox(
                value: search,
                onChanged: (value) => setState(() {
                  search = value;
                  _reload();
                }),
                hint: 'Search passenger amenities',
              ),
              const SizedBox(height: 10),
              SizedBox(
                height: 42,
                child: ListView.separated(
                  scrollDirection: Axis.horizontal,
                  itemCount: kinds.length,
                  separatorBuilder: (_, __) => const SizedBox(width: 8),
                  itemBuilder: (context, index) {
                    final item = kinds[index];
                    return ChoiceChip(
                      selected: kind == item.$1,
                      label: Text(item.$2),
                      onSelected: (_) => setState(() {
                        kind = item.$1;
                        _reload();
                      }),
                    );
                  },
                ),
              ),
            ],
          ),
        ),
        Expanded(
          child: FutureBuilder<List<Map<String, dynamic>>>(
            future: future,
            builder: (context, snapshot) {
              if (!snapshot.hasData) return const LoadingPane();
              final rows = snapshot.data!;
              if (rows.isEmpty) return const EmptyPane(title: 'No amenity records found');
              return ListView.separated(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
                itemCount: rows.length,
                separatorBuilder: (_, __) => const SizedBox(height: 10),
                itemBuilder: (context, index) => AmenityTile(
                  amenity: rows[index],
                  kind: kind,
                  onTap: () => showStationDetail(context, widget.api, textOf(rows[index]['station_code'])),
                ),
              );
            },
          ),
        ),
      ],
    );
  }
}

class ReportsScreen extends StatefulWidget {
  const ReportsScreen({required this.api, super.key});

  final RailApiClient api;

  @override
  State<ReportsScreen> createState() => _ReportsScreenState();
}

class _ReportsScreenState extends State<ReportsScreen> {
  late Future<Map<String, dynamic>> future;

  @override
  void initState() {
    super.initState();
    future = widget.api.reports();
  }

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: () async => setState(() => future = widget.api.reports()),
      child: FutureBuilder<Map<String, dynamic>>(
        future: future,
        builder: (context, snapshot) {
          if (!snapshot.hasData) return const LoadingPane();
          final data = snapshot.data!;
          final alerts = ((data['license_fee_alerts'] as Map?)?['rows'] as List? ?? const []);
          final actions = (data['needs_action'] as List? ?? const []);
          return ListView(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
            children: [
              const SectionTitle(title: 'Needs action', subtitle: 'License fee and operational records needing review.'),
              const SizedBox(height: 12),
              GridView.count(
                crossAxisCount: 2,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                mainAxisSpacing: 12,
                crossAxisSpacing: 12,
                childAspectRatio: 1.25,
                children: [
                  MetricCard(label: 'Alerts', value: '${alerts.length}', icon: Icons.notification_important_rounded, color: const Color(0xFFDC2626)),
                  MetricCard(label: 'Action Rows', value: '${actions.length}', icon: Icons.fact_check_rounded, color: const Color(0xFFF59E0B)),
                ],
              ),
              const SizedBox(height: 16),
              GlassSurface(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const SectionTitle(title: 'License fee alerts', subtitle: 'Upcoming, overdue and pending contract checks.'),
                    const SizedBox(height: 10),
                    if (alerts.isEmpty) const EmptyPane(title: 'No alerts found') else for (final row in alerts.take(30)) AlertTile(row: Map<String, dynamic>.from(row)),
                  ],
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

class StationTile extends StatelessWidget {
  const StationTile({required this.station, required this.onTap, super.key});

  final Map<String, dynamic> station;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GlassSurface(
      padding: EdgeInsets.zero,
      child: ListTile(
        onTap: onTap,
        leading: CircleAvatar(child: Text(textOf(station['station_code']).substring(0, 1))),
        title: Text(textOf(station['station_name']), maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w900)),
        subtitle: Text('${textOf(station['station_code'])} | ${textOf(station['division'])} | ${textOf(station['section'])}'),
        trailing: InfoChip(label: textOf(station['categorisation']), icon: Icons.label_rounded),
      ),
    );
  }
}

class UnitTile extends StatelessWidget {
  const UnitTile({required this.unit, required this.onTap, super.key});

  final Map<String, dynamic> unit;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GlassSurface(
      padding: const EdgeInsets.all(14),
      child: InkWell(
        onTap: onTap,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(child: Text(textOf(unit['unit_no']), style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w900))),
                InfoChip(label: textOf(unit['unit_status']), icon: Icons.verified_rounded),
              ],
            ),
            const SizedBox(height: 8),
            Text(textOf(unit['licensee_name']), maxLines: 1, overflow: TextOverflow.ellipsis),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                InfoChip(label: textOf(unit['station_code']), icon: Icons.train_rounded),
                InfoChip(label: textOf(unit['type_of_unit']), icon: Icons.store_rounded),
                InfoChip(label: moneyOf(unit['license_fee']), icon: Icons.currency_rupee_rounded),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class EarningTile extends StatelessWidget {
  const EarningTile({required this.earning, super.key});

  final Map<String, dynamic> earning;

  @override
  Widget build(BuildContext context) {
    return GlassSurface(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(child: Text(textOf(earning['unit_no']), style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w900))),
              Text(moneyOf(earning['amount']), style: const TextStyle(fontWeight: FontWeight.w900)),
            ],
          ),
          const SizedBox(height: 8),
          Text(textOf(earning['licensee_name']), maxLines: 1, overflow: TextOverflow.ellipsis),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              InfoChip(label: textOf(earning['station_code']), icon: Icons.train_rounded),
              InfoChip(label: textOf(earning['payment_head']), icon: Icons.receipt_long_rounded),
              InfoChip(label: textOf(earning['receipt_type']), icon: Icons.check_circle_rounded),
            ],
          ),
        ],
      ),
    );
  }
}

class WorkTile extends StatelessWidget {
  const WorkTile({required this.work, required this.onTap, super.key});

  final Map<String, dynamic> work;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      onTap: onTap,
      leading: const CircleAvatar(child: Icon(Icons.construction_rounded)),
      title: Text(textOf(work['short_name_of_work']), maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w800)),
      subtitle: Text('${textOf(work['project_id'])} | ${textOf(work['station_code'] ?? work['scope_value'])}'),
      trailing: InfoChip(label: textOf(work['status']), icon: Icons.timeline_rounded),
    );
  }
}

class AmenityTile extends StatelessWidget {
  const AmenityTile({required this.amenity, required this.kind, required this.onTap, super.key});

  final Map<String, dynamic> amenity;
  final String kind;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final title = kind == 'pa_works'
        ? textOf(amenity['work_name'])
        : '${textOf(amenity['station_code'])} ${textOf(amenity['station_name'], fallback: '')}'.trim();
    return GlassSurface(
      padding: EdgeInsets.zero,
      child: ListTile(
        onTap: textOf(amenity['station_code']) == 'NA' ? null : onTap,
        leading: const CircleAvatar(child: Icon(Icons.accessible_forward_rounded)),
        title: Text(title, maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w900)),
        subtitle: Text(_amenitySubtitle(amenity, kind), maxLines: 2, overflow: TextOverflow.ellipsis),
        trailing: const Icon(Icons.chevron_right_rounded),
      ),
    );
  }

  String _amenitySubtitle(Map<String, dynamic> row, String kind) {
    if (kind == 'pf_extension') {
      return 'Ramp feasible: ${row['ramp_feasible'] == true ? 'Yes' : 'No'} | Lift proposed: ${row['lift_proposed'] == true ? 'Yes' : 'No'}';
    }
    if (kind == 'platforms') {
      return 'Platform ${textOf(row['platform'])} | Length ${textOf(row['length_m'])} m';
    }
    if (kind == 'pa_works') {
      return '${textOf(row['work_type'])} | ${textOf(row['progress'])}';
    }
    return '${textOf(row['category'] ?? row['categorisation'])} | ${textOf(row['section'])}';
  }
}

class AlertTile extends StatelessWidget {
  const AlertTile({required this.row, super.key});

  final Map<String, dynamic> row;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: const CircleAvatar(child: Icon(Icons.warning_rounded)),
      title: Text('${textOf(row['unit_no'])} | ${textOf(row['licensee_name'])}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w900)),
      subtitle: Text('Station ${textOf(row['station_code'])} | Due ${textOf(row['contract_to'] ?? row['last_paid_through'])}'),
      trailing: InfoChip(label: textOf(row['alert_bucket']).replaceAll('_', ' ')),
    );
  }
}

Future<void> showStationDetail(BuildContext context, RailApiClient api, String stationCode) async {
  if (stationCode == 'NA') return;
  await showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    backgroundColor: Colors.transparent,
    builder: (context) => StationDetailSheet(api: api, stationCode: stationCode),
  );
}

class StationDetailSheet extends StatefulWidget {
  const StationDetailSheet({required this.api, required this.stationCode, super.key});

  final RailApiClient api;
  final String stationCode;

  @override
  State<StationDetailSheet> createState() => _StationDetailSheetState();
}

class _StationDetailSheetState extends State<StationDetailSheet> {
  late Future<Map<String, dynamic>> future;

  @override
  void initState() {
    super.initState();
    future = widget.api.stationFullDetail(widget.stationCode);
  }

  @override
  Widget build(BuildContext context) {
    return DraggableScrollableSheet(
      initialChildSize: 0.92,
      minChildSize: 0.55,
      maxChildSize: 0.96,
      builder: (context, controller) {
        return GlassSurface(
          margin: const EdgeInsets.all(10),
          padding: const EdgeInsets.fromLTRB(16, 10, 16, 16),
          child: FutureBuilder<Map<String, dynamic>>(
            future: future,
            builder: (context, snapshot) {
              if (!snapshot.hasData) return const LoadingPane();
              final data = snapshot.data!;
              final station = Map<String, dynamic>.from(data['station'] as Map);
              final amenities = Map<String, dynamic>.from(data['amenities'] as Map? ?? {});
              final summary = Map<String, dynamic>.from(data['amenity_summary'] as Map? ?? {});
              final pfStatus = Map<String, dynamic>.from(amenities['pf_extension_status'] as Map? ?? {});
              final contracts = (data['contracts'] as List? ?? const []);
              final works = (data['works'] as List? ?? const []);
              final platforms = (amenities['platforms'] as List? ?? const []);
              return ListView(
                controller: controller,
                children: [
                  Center(
                    child: Container(
                      width: 44,
                      height: 5,
                      margin: const EdgeInsets.only(bottom: 12),
                      decoration: BoxDecoration(color: Theme.of(context).colorScheme.outlineVariant, borderRadius: BorderRadius.circular(99)),
                    ),
                  ),
                  SectionTitle(
                    title: textOf(station['station_name']),
                    subtitle: '${textOf(station['station_code'])} | ${textOf(station['division'])} | ${textOf(station['section'])}',
                    action: IconButton.filledTonal(onPressed: () => Navigator.pop(context), icon: const Icon(Icons.close_rounded)),
                  ),
                  const SizedBox(height: 14),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      InfoChip(label: textOf(station['categorisation']), icon: Icons.label_rounded),
                      InfoChip(label: '${textOf(summary['platforms'], fallback: '0')} platforms', icon: Icons.view_week_rounded),
                      InfoChip(label: '${contracts.length} contracts', icon: Icons.storefront_rounded),
                      InfoChip(label: '${works.length} works', icon: Icons.construction_rounded),
                    ],
                  ),
                  const SizedBox(height: 16),
                  KeyValueGrid(
                    rows: [
                      ('Footfall', station['passenger_footfall']),
                      ('Platform Type', station['platform_type']),
                      ('Total PF Length', summary['total_platform_length'] == null ? null : '${summary['total_platform_length']} m'),
                      ('Wheel Chairs', summary['wheel_chairs']),
                      ('Trolley Path', summary['trolley_path']),
                      ('FOB / Access', summary['fob_details']),
                      ('Ramp Feasible', summary['ramp_feasible'] == true ? 'Yes' : 'No'),
                      ('Lift Proposed', summary['lift_proposed'] == true ? 'Yes' : 'No'),
                    ],
                  ),
                  const SizedBox(height: 18),
                  const SectionTitle(title: 'PF extension and access', subtitle: 'Workbook-linked status for platform extension, ramp and lift feasibility.'),
                  const SizedBox(height: 10),
                  KeyValueGrid(
                    rows: [
                      ('PF WIP', pfStatus['pf_extension_wip'] == true ? 'Yes' : 'No'),
                      ('PF Proposed', pfStatus['pf_extension_proposed'] == true ? 'Yes' : 'No'),
                      ('Raising Proposed', pfStatus['raising_extension_proposed'] == true ? 'Yes' : 'No'),
                      ('Ramp Feasible', pfStatus['ramp_feasible'] == true ? 'Yes' : 'No'),
                      ('Ramp Proposed', pfStatus['ramp_proposed'] == true ? 'Yes' : 'No'),
                      ('Source Rows', pfStatus['source_rows']),
                    ],
                  ),
                  const SizedBox(height: 18),
                  const SectionTitle(title: 'Platforms'),
                  const SizedBox(height: 8),
                  if (platforms.isEmpty) const EmptyPane(title: 'No platform rows') else for (final platform in platforms.take(12)) PlatformMiniTile(platform: Map<String, dynamic>.from(platform)),
                  const SizedBox(height: 18),
                  const SectionTitle(title: 'Contracts'),
                  const SizedBox(height: 8),
                  if (contracts.isEmpty) const EmptyPane(title: 'No contracts') else for (final contract in contracts.take(12)) UnitTile(unit: Map<String, dynamic>.from(contract), onTap: () {}),
                  const SizedBox(height: 18),
                  const SectionTitle(title: 'Works'),
                  const SizedBox(height: 8),
                  if (works.isEmpty) const EmptyPane(title: 'No works') else for (final work in works.take(12)) WorkTile(work: Map<String, dynamic>.from(work), onTap: null),
                ],
              );
            },
          ),
        );
      },
    );
  }
}

class PlatformMiniTile extends StatelessWidget {
  const PlatformMiniTile({required this.platform, super.key});

  final Map<String, dynamic> platform;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: const CircleAvatar(child: Icon(Icons.view_column_rounded)),
      title: Text('Platform ${textOf(platform['platform'])}', style: const TextStyle(fontWeight: FontWeight.w900)),
      subtitle: Text('Length ${textOf(platform['length_m'])} m | Lift ${textOf(platform['lifts'])} | Ramp ${textOf(platform['ramp'])}'),
    );
  }
}
