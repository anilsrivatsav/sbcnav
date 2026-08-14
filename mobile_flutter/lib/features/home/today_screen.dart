import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/local/app_database.dart';
import '../../data/sync/sync_service.dart';
import '../../core/theme/app_theme.dart';
import '../../shared/widgets.dart';
import '../notifications/notifications_screen.dart';
import '../settings/settings_screen.dart';

class TodayScreen extends ConsumerStatefulWidget {
  const TodayScreen({required this.onNavigate, super.key});

  final ValueChanged<int> onNavigate;

  @override
  ConsumerState<TodayScreen> createState() => _TodayScreenState();
}

class _PortfolioData {
  const _PortfolioData({
    required this.stations,
    required this.units,
    required this.contracts,
    required this.works,
    required this.amenities,
    required this.openWorks,
    required this.expiringContracts,
    required this.pendingSync,
    required this.unreadNotifications,
    required this.profileName,
  });

  final int stations;
  final int units;
  final int contracts;
  final int works;
  final int amenities;
  final int openWorks;
  final int expiringContracts;
  final int pendingSync;
  final int unreadNotifications;
  final String profileName;
}

class _TodayScreenState extends ConsumerState<TodayScreen> {
  late Future<_PortfolioData> _data;

  @override
  void initState() {
    super.initState();
    _data = _load();
  }

  Future<_PortfolioData> _load() async {
    final database = ref.read(databaseProvider);
    final rows = await database.stationOverviewRows();
    var units = 0;
    var contracts = 0;
    var works = 0;
    var amenities = 0;
    var openWorks = 0;
    var expiringContracts = 0;
    final today = DateTime.now();
    final threshold = today.add(const Duration(days: 30));

    for (final row in rows) {
      final detail = row['_station_detail'];
      if (detail is! Map) continue;
      final unitRows = detail['units'];
      final contractRows = [
        ..._asList(detail['contracts']),
        ..._asList(detail['commercial_contracts']),
      ];
      final workRows = _asList(detail['works']);
      units += unitRows is List ? unitRows.length : 0;
      contracts += contractRows.length;
      works += workRows.length;
      openWorks += workRows.where((item) {
        final status = '${item is Map ? item['status'] : ''}'.toLowerCase();
        return !status.contains('complete') && !status.contains('done');
      }).length;
      for (final item in contractRows) {
        if (item is! Map) continue;
        final date = _date(item['valid_to'] ?? item['contract_to']);
        if (date != null && !date.isBefore(today) && date.isBefore(threshold)) {
          expiringContracts++;
        }
      }
      final amenityMap = detail['amenities'];
      if (amenityMap is Map) {
        amenities += _asList(amenityMap['platforms']).length;
        amenities += _asList(amenityMap['norms']).length;
        if (amenityMap['infra'] is Map) amenities++;
        if (amenityMap['pf_extension_status'] is Map) amenities++;
      }
    }

    final totals = await database.portfolioTotals();
    final profile = await database.metadata('profile_name');
    return _PortfolioData(
      stations: (totals['stations'] as num?)?.toInt() ?? rows.length,
      units: units,
      contracts: contracts,
      works: (totals['works'] as num?)?.toInt() ?? works,
      amenities: amenities,
      openWorks: openWorks,
      expiringContracts: expiringContracts,
      pendingSync: await database.pendingCount(),
      unreadNotifications: await database.unreadNotificationCount(),
      profileName:
          profile?.trim().isNotEmpty == true ? profile! : 'Rail officer',
    );
  }

  void _refresh() => setState(() => _data = _load());

  @override
  Widget build(BuildContext context) {
    ref.listen(syncControllerProvider, (_, __) => _refresh());
    final sync = ref.watch(syncControllerProvider);
    final busy = sync.isLoading || sync.asData?.value.busy == true;
    return RefreshIndicator(
      onRefresh: () async {
        _refresh();
        await _data;
      },
      child: FutureBuilder<_PortfolioData>(
        future: _data,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting &&
              !snapshot.hasData) {
            return const GlassLoadingList(itemCount: 6);
          }
          if (snapshot.hasError)
            return ErrorPane(error: snapshot.error!, retry: _refresh);
          final data = snapshot.data!;
          return ListView(
            physics: const ClampingScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(
                AppSpacing.page, 18, AppSpacing.page, 32),
            children: [
              _PortfolioHeader(
                name: data.profileName,
                notifications: data.unreadNotifications,
                onMenu: () => showGlassBottomSheet<void>(
                  context,
                  builder: (_) => HomeActionsSheet(
                    onFetchLatest: () => ref
                        .read(syncControllerProvider.notifier)
                        .refreshFromServer(),
                    onSync: () =>
                        ref.read(syncControllerProvider.notifier).synchronize(),
                  ),
                ).then((_) => _refresh()),
                onNotifications: () => showGlassBottomSheet<void>(
                  context,
                  builder: (_) => const NotificationsSheet(),
                ).then((_) => _refresh()),
              ),
              const SizedBox(height: 22),
              const _PortfolioHero(),
              const SizedBox(height: 18),
              _SectionTitle(
                  title: 'Portfolio at a glance',
                  action: 'Reports',
                  onTap: () => widget.onNavigate(3)),
              const SizedBox(height: 10),
              _KpiGrid(data: data),
              const SizedBox(height: 22),
              _AttentionPanel(
                  data: data, onReports: () => widget.onNavigate(3)),
              const SizedBox(height: 22),
              AppButton(
                expand: true,
                loading: busy,
                onPressed: busy
                    ? null
                    : () => ref
                        .read(syncControllerProvider.notifier)
                        .refreshFromServer(),
                icon: Icons.sync_rounded,
                label: 'Refresh portfolio data',
              ),
              const SizedBox(height: 10),
              Text(
                data.pendingSync == 0
                    ? 'All local changes are synced.'
                    : '${data.pendingSync} local changes waiting to sync.',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          );
        },
      ),
    );
  }
}

class _PortfolioHeader extends StatelessWidget {
  const _PortfolioHeader(
      {required this.name,
      required this.notifications,
      required this.onMenu,
      required this.onNotifications});

  final String name;
  final int notifications;
  final VoidCallback onMenu;
  final VoidCallback onNotifications;

  @override
  Widget build(BuildContext context) {
    return Row(children: [
      AppIconButton(
          tooltip: 'Menu and settings',
          icon: Icons.tune_rounded,
          onPressed: onMenu),
      const SizedBox(width: 14),
      Expanded(
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('RAIL PORTFOLIO',
            style: Theme.of(context).textTheme.labelMedium?.copyWith(
                letterSpacing: 2,
                fontWeight: FontWeight.w900,
                color: AppPalette.teal)),
        const SizedBox(height: 3),
        Text('Welcome, $name',
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context)
                .textTheme
                .headlineSmall
                ?.copyWith(fontWeight: FontWeight.w900)),
        const SizedBox(height: 2),
        Text('Station portfolio dashboard - v1.0.3',
            style: Theme.of(context).textTheme.bodySmall),
      ])),
      Stack(clipBehavior: Clip.none, children: [
        AppIconButton(
            tooltip: 'Notifications',
            icon: Icons.notifications_none_rounded,
            onPressed: onNotifications),
        if (notifications > 0)
          Positioned(
              right: -1,
              top: -2,
              child: Container(
                  padding: const EdgeInsets.all(4),
                  decoration: const BoxDecoration(
                      color: AppPalette.red, shape: BoxShape.circle),
                  child: Text(notifications > 9 ? '9+' : '$notifications',
                      style: const TextStyle(
                          color: Colors.white,
                          fontSize: 9,
                          fontWeight: FontWeight.w900)))),
      ]),
    ]);
  }
}

class _PortfolioHero extends StatelessWidget {
  const _PortfolioHero();

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 18),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Container(
              width: 46,
              height: 46,
              decoration: BoxDecoration(
                  color: AppPalette.teal.withValues(alpha: .12),
                  borderRadius: BorderRadius.circular(16)),
              child: const Icon(Icons.account_tree_rounded,
                  color: AppPalette.teal)),
          const SizedBox(width: 12),
          const Expanded(
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                Text('Station portfolio',
                    style:
                        TextStyle(fontSize: 19, fontWeight: FontWeight.w900)),
                SizedBox(height: 3),
                Text(
                    'A single view of your railway commercial and infrastructure data.')
              ]))
        ]),
      ]),
    );
  }
}

class _KpiGrid extends StatelessWidget {
  const _KpiGrid({required this.data});
  final _PortfolioData data;
  @override
  Widget build(BuildContext context) =>
      Wrap(spacing: 10, runSpacing: 10, children: [
        _Kpi(
            icon: Icons.train_rounded,
            label: 'Stations',
            value: data.stations,
            tone: AppPalette.royalBlue),
        _Kpi(
            icon: Icons.storefront_rounded,
            label: 'Units',
            value: data.units,
            tone: AppPalette.indigo),
        _Kpi(
            icon: Icons.handshake_rounded,
            label: 'Contracts',
            value: data.contracts,
            tone: AppPalette.teal),
        _Kpi(
            icon: Icons.accessibility_new_rounded,
            label: 'Amenities',
            value: data.amenities,
            tone: AppPalette.cyan),
        _Kpi(
            icon: Icons.construction_rounded,
            label: 'Works',
            value: data.works,
            tone: AppPalette.amber),
        _Kpi(
            icon: Icons.pending_actions_rounded,
            label: 'Open works',
            value: data.openWorks,
            tone: AppPalette.red),
      ]);
}

class _Kpi extends StatelessWidget {
  const _Kpi(
      {required this.icon,
      required this.label,
      required this.value,
      required this.tone});
  final IconData icon;
  final String label;
  final int value;
  final Color tone;
  @override
  Widget build(BuildContext context) => SizedBox(
      width: 150,
      child: GlassPanel(
          padding: const EdgeInsets.all(14),
          child: Row(children: [
            Icon(icon, size: 20, color: tone),
            const SizedBox(width: 9),
            Expanded(
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                  Text('$value',
                      style: const TextStyle(
                          fontSize: 19, fontWeight: FontWeight.w900)),
                  Text(label,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.bodySmall)
                ]))
          ])));
}

class _RegisterList extends StatelessWidget {
  const _RegisterList({required this.data, required this.onNavigate});
  final _PortfolioData data;
  final ValueChanged<int> onNavigate;
  @override
  Widget build(BuildContext context) => Column(children: [
        _RegisterTile(
            icon: Icons.train_rounded,
            title: 'Stations',
            subtitle: 'Station master and Station 360',
            tone: AppPalette.royalBlue,
            onTap: () => onNavigate(1)),
        _RegisterTile(
            icon: Icons.handshake_rounded,
            title: 'Contracts and earnings',
            subtitle: 'Units, catering, commercial and payments',
            tone: AppPalette.teal,
            onTap: () => onNavigate(3)),
        _RegisterTile(
            icon: Icons.accessibility_new_rounded,
            title: 'Passenger amenities',
            subtitle: 'Platforms, access, FOB and norms',
            tone: AppPalette.cyan,
            onTap: () => onNavigate(3)),
        _RegisterTile(
            icon: Icons.construction_rounded,
            title: 'Sanctioned works',
            subtitle: 'Progress, scope and station links',
            tone: AppPalette.amber,
            onTap: () => onNavigate(3)),
      ]);
}

class _RegisterTile extends StatelessWidget {
  const _RegisterTile(
      {required this.icon,
      required this.title,
      required this.subtitle,
      required this.tone,
      required this.onTap});
  final IconData icon;
  final String title;
  final String subtitle;
  final Color tone;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) => Padding(
      padding: const EdgeInsets.only(bottom: 9),
      child: GlassPanel(
          onTap: onTap,
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          child: Row(children: [
            Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                    color: tone.withValues(alpha: .12),
                    borderRadius: BorderRadius.circular(14)),
                child: Icon(icon, color: tone)),
            const SizedBox(width: 12),
            Expanded(
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                  Text(title,
                      style: const TextStyle(fontWeight: FontWeight.w900)),
                  const SizedBox(height: 3),
                  Text(subtitle, style: Theme.of(context).textTheme.bodySmall)
                ])),
            const Icon(Icons.chevron_right_rounded)
          ])));
}

class _AttentionPanel extends StatelessWidget {
  const _AttentionPanel({required this.data, required this.onReports});
  final _PortfolioData data;
  final VoidCallback onReports;
  @override
  Widget build(BuildContext context) => GlassPanel(
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Needs attention',
            style: TextStyle(fontSize: 17, fontWeight: FontWeight.w900)),
        const SizedBox(height: 10),
        _AttentionRow(
            icon: Icons.event_busy_rounded,
            label: 'Contracts expiring within 30 days',
            value: data.expiringContracts,
            tone: AppPalette.red),
        if (data.pendingSync > 0)
          _AttentionRow(
              icon: Icons.cloud_upload_rounded,
              label: 'Changes waiting to sync',
              value: data.pendingSync,
              tone: AppPalette.cyan),
        const SizedBox(height: 10),
        Align(
            alignment: Alignment.centerRight,
            child: TextButton(
                onPressed: onReports, child: const Text('Open reports')))
      ]));
}

class _AttentionRow extends StatelessWidget {
  const _AttentionRow(
      {required this.icon,
      required this.label,
      required this.value,
      required this.tone});
  final IconData icon;
  final String label;
  final int value;
  final Color tone;
  @override
  Widget build(BuildContext context) => Padding(
      padding: const EdgeInsets.only(bottom: 9),
      child: Row(children: [
        Icon(icon, size: 19, color: tone),
        const SizedBox(width: 9),
        Expanded(child: Text(label)),
        StatusBadge('$value', tone: tone)
      ]));
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle({required this.title, this.action, this.onTap});
  final String title;
  final String? action;
  final VoidCallback? onTap;
  @override
  Widget build(BuildContext context) => Row(children: [
        Expanded(
            child: Text(title,
                style: Theme.of(context)
                    .textTheme
                    .titleMedium
                    ?.copyWith(fontWeight: FontWeight.w900))),
        if (action != null) TextButton(onPressed: onTap, child: Text(action!))
      ]);
}

List<dynamic> _asList(Object? value) => value is List ? value : const [];
DateTime? _date(Object? value) => DateTime.tryParse('${value ?? ''}');
