import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/local/app_database.dart';
import '../../data/remote/mobile_api.dart';
import '../../data/sync/sync_service.dart';
import '../../shared/widgets.dart';
import '../findings/findings_screen.dart';
import '../inspections/start_station_inspection.dart';
import 'station_presentation.dart';

class Station360Screen extends ConsumerStatefulWidget {
  const Station360Screen({required this.stationCode, super.key});

  final String stationCode;

  @override
  ConsumerState<Station360Screen> createState() => _Station360ScreenState();
}

class StationDetailBottomSheet extends ConsumerStatefulWidget {
  const StationDetailBottomSheet({required this.stationCode, super.key});

  final String stationCode;

  @override
  ConsumerState<StationDetailBottomSheet> createState() =>
      _StationDetailBottomSheetState();
}

class _StationDetailBottomSheetState
    extends ConsumerState<StationDetailBottomSheet> {
  late Future<Map<String, dynamic>> _detail;

  @override
  void initState() {
    super.initState();
    _detail = _load();
    WidgetsBinding.instance.addPostFrameCallback((_) => _refreshCachedDetail());
  }

  Future<void> _refreshCachedDetail() async {
    try {
      final fresh = await _load(preferCache: false);
      if (!mounted) return;
      setState(() => _detail = Future.value(fresh));
    } catch (_) {
      // Cached station details remain available when the device is offline.
    }
  }

  Future<Map<String, dynamic>> _load({bool preferCache = true}) async {
    final database = ref.read(databaseProvider);
    if (preferCache) {
      final cached = await database.stationDetail(widget.stationCode);
      if (cached != null) return cached;
    }
    try {
      final detail =
          await ref.read(mobileApiProvider).station360(widget.stationCode);
      await database.cacheStationDetail(widget.stationCode, detail);
      return detail;
    } catch (_) {
      final cached = await database.stationDetail(widget.stationCode);
      if (cached != null) return cached;
      rethrow;
    }
  }

  void _refresh() => setState(() => _detail = _load(preferCache: false));

  @override
  Widget build(BuildContext context) {
    final height = MediaQuery.sizeOf(context).height * 0.94;
    return Material(
      color: Theme.of(context).colorScheme.surfaceContainerLowest,
      borderRadius: const BorderRadius.vertical(top: Radius.circular(28)),
      clipBehavior: Clip.antiAlias,
      child: SizedBox(
        height: height,
        child: FutureBuilder<Map<String, dynamic>>(
          future: _detail,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting &&
                !snapshot.hasData) {
              return const SafeArea(child: GlassLoadingList(itemCount: 6));
            }
            if (snapshot.hasError) {
              return SafeArea(
                child: ErrorPane(error: snapshot.error!, retry: _refresh),
              );
            }
            return _StationProfile(
              detail: snapshot.data!,
              fallbackCode: widget.stationCode,
              onRefresh: _refresh,
              onStartInspection: (code) =>
                  startStationInspection(context, ref, stationCode: code),
            );
          },
        ),
      ),
    );
  }
}

class _Station360ScreenState extends ConsumerState<Station360Screen> {
  late Future<Map<String, dynamic>> _detail;

  @override
  void initState() {
    super.initState();
    _detail = _load();
    WidgetsBinding.instance.addPostFrameCallback((_) => _refreshCachedDetail());
  }

  Future<void> _refreshCachedDetail() async {
    try {
      final fresh = await _load(preferCache: false);
      if (!mounted) return;
      setState(() => _detail = Future.value(fresh));
    } catch (_) {
      // Cached station details remain available when the device is offline.
    }
  }

  Future<Map<String, dynamic>> _load({bool preferCache = true}) async {
    final database = ref.read(databaseProvider);
    if (preferCache) {
      final cached = await database.stationDetail(widget.stationCode);
      if (cached != null) return cached;
    }
    try {
      final detail =
          await ref.read(mobileApiProvider).station360(widget.stationCode);
      await database.cacheStationDetail(widget.stationCode, detail);
      return detail;
    } catch (_) {
      final cached = await database.stationDetail(widget.stationCode);
      if (cached != null) return cached;
      final station = await database.station(widget.stationCode);
      if (station != null) return {'station': station};
      rethrow;
    }
  }

  void _refresh() => setState(() => _detail = _load(preferCache: false));

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Theme.of(context).colorScheme.surfaceContainerLowest,
      body: FutureBuilder<Map<String, dynamic>>(
        future: _detail,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting &&
              !snapshot.hasData) {
            return const SafeArea(child: GlassLoadingList(itemCount: 6));
          }
          if (snapshot.hasError) {
            return SafeArea(
              child: ErrorPane(error: snapshot.error!, retry: _refresh),
            );
          }
          return _StationProfile(
            detail: snapshot.data!,
            fallbackCode: widget.stationCode,
            onRefresh: _refresh,
            onStartInspection: (code) =>
                startStationInspection(context, ref, stationCode: code),
          );
        },
      ),
    );
  }
}

enum _StationWorkspace {
  overview,
  amenities,
  contracts,
  works,
  inspection,
}

class _StationProfile extends ConsumerStatefulWidget {
  const _StationProfile({
    required this.detail,
    required this.fallbackCode,
    required this.onRefresh,
    required this.onStartInspection,
  });

  final Map<String, dynamic> detail;
  final String fallbackCode;
  final VoidCallback onRefresh;
  final ValueChanged<String> onStartInspection;

  @override
  ConsumerState<_StationProfile> createState() => _StationProfileState();
}

class _StationProfileState extends ConsumerState<_StationProfile> {
  _StationWorkspace _workspace = _StationWorkspace.overview;

  @override
  Widget build(BuildContext context) {
    final detail = widget.detail;
    final rawStation =
        _map(detail['station']).isEmpty ? detail : _map(detail['station']);
    // The Stations source sheet is authoritative for officer assignments.
    final station = rawStation;
    final amenities = _map(detail['amenities']);
    final platforms = _platformRows(station, amenities);
    final catering = _list(detail['contracts']).isNotEmpty
        ? _list(detail['contracts'])
        : _list(detail['units']);
    final contracts =
        buildContracts(catering, _list(detail['commercial_contracts']));
    final works = buildWorks([
      ..._list(detail['works']),
      ..._list(amenities['pa_works']),
    ]);
    final norms = _list(amenities['norms']).isNotEmpty
        ? _list(amenities['norms'])
        : _list(detail['norms']);
    final fobAccess = _fobAccessModes(amenities);
    final amenityGroups = {
      for (final entry in buildAmenityCategories(station, amenities).entries)
        entry.key: entry.value
            .where((item) =>
                fobAccess.isEmpty || item.label.toLowerCase() != 'fob')
            .toList(),
    };
    final code =
        cleanText(station['station_code'], fallback: widget.fallbackCode);
    final name =
        cleanText(station['station_name'], fallback: 'Unnamed station');
    final section = cleanText(station['section']);
    final zone = cleanText(station['zone']);
    final category =
        cleanText(station['categorisation'], fallback: 'Unclassified');
    final abssFlag = station['abss_flag'] == true ||
        abssStationCodes.contains(code.toUpperCase());
    final redevelopmentFlag = station['redevelopment_flag'] == true ||
        redevelopmentStationCodes.contains(code.toUpperCase());
    final totalPlatforms = highestPlatformNumber(
      platforms,
      stationPlatforms: station['platforms'],
      declaredPlatforms: station['number_of_platforms'],
    );
    final passengerAmenityRecordCount =
        amenityGroups.values.fold<int>(0, (sum, rows) => sum + rows.length) +
            totalPlatforms +
            norms.length +
            (fobAccess.isEmpty ? 0 : 1);
    final availableWorkspaces = <_StationWorkspace>[
      _StationWorkspace.overview,
      _StationWorkspace.amenities,
      if (contracts.isNotEmpty) _StationWorkspace.contracts,
      if (works.isNotEmpty) _StationWorkspace.works,
      _StationWorkspace.inspection,
    ];
    final selectedWorkspace = availableWorkspaces.contains(_workspace)
        ? _workspace
        : _StationWorkspace.overview;

    return CustomScrollView(
      slivers: [
        SliverAppBar(
          expandedHeight: 248,
          pinned: true,
          stretch: true,
          backgroundColor: const Color(0xFF143D8F),
          leadingWidth: 68,
          leading: Padding(
            padding: const EdgeInsets.only(left: 14, top: 6, bottom: 6),
            child: _HeroButton(
              icon: Icons.arrow_back_ios_new_rounded,
              onTap: () => Navigator.of(context).pop(),
              tooltip: 'Back',
            ),
          ),
          actions: [
            _HeroButton(
              icon: Icons.refresh_rounded,
              onTap: widget.onRefresh,
              tooltip: 'Refresh',
            ),
            const SizedBox(width: 14),
          ],
          flexibleSpace: FlexibleSpaceBar(
            collapseMode: CollapseMode.parallax,
            stretchModes: const [StretchMode.zoomBackground],
            background: Stack(
              fit: StackFit.expand,
              children: [
                Image.asset(
                  'assets/stations/station_heritage_hero.png',
                  fit: BoxFit.cover,
                ),
                const DecoratedBox(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [
                        Color(0x22000000),
                        Color(0x18000000),
                        Color(0xE6001024),
                      ],
                      stops: [0, 0.46, 1],
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                    ),
                  ),
                ),
                Positioned(
                  left: 22,
                  right: 22,
                  bottom: 24,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Wrap(
                        spacing: 9,
                        runSpacing: 8,
                        crossAxisAlignment: WrapCrossAlignment.center,
                        children: [
                          Text(
                            '$code Station',
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 29,
                              fontWeight: FontWeight.w900,
                              shadows: [
                                Shadow(color: Colors.black45, blurRadius: 12),
                              ],
                            ),
                          ),
                          if (category.toLowerCase() != 'unclassified')
                            _HeroBadge(category),
                          if (abssFlag) const _HeroBadge('ABSS'),
                          if (redevelopmentFlag)
                            const _HeroBadge('Redevelopment'),
                        ],
                      ),
                      const SizedBox(height: 5),
                      Text(
                        name,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: Color(0xFFEAF2FF),
                          fontSize: 16,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
        SliverToBoxAdapter(
          child: Transform.translate(
            offset: const Offset(0, -12),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 30),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _StationFacts(
                    dailyFootfall:
                        formatDailyFootfall(station['passenger_footfall']),
                    platforms: totalPlatforms,
                    zone: zone,
                  ),
                  const SizedBox(height: 16),
                  _StationActions(
                    section: section,
                    division: cleanText(station['division']),
                  ),
                  const SizedBox(height: 16),
                  _StationWorkspaceNav(
                    selected: selectedWorkspace,
                    available: availableWorkspaces,
                    counts: {
                      _StationWorkspace.amenities: passengerAmenityRecordCount,
                      _StationWorkspace.contracts: contracts.length,
                      _StationWorkspace.works: works.length,
                    },
                    onSelected: (value) => setState(() => _workspace = value),
                  ),
                  const SizedBox(height: 20),
                  AnimatedSwitcher(
                    duration: const Duration(milliseconds: 260),
                    switchInCurve: Curves.easeOutCubic,
                    switchOutCurve: Curves.easeInCubic,
                    transitionBuilder: (child, animation) => FadeTransition(
                      opacity: animation,
                      child: SlideTransition(
                        position: Tween<Offset>(
                          begin: const Offset(0.025, 0),
                          end: Offset.zero,
                        ).animate(animation),
                        child: child,
                      ),
                    ),
                    child: switch (selectedWorkspace) {
                      _StationWorkspace.overview => _StationOverviewWorkspace(
                          key: const ValueKey('overview'),
                          station: station,
                          amenities: amenities,
                          amenityCount: passengerAmenityRecordCount,
                          platformCount: totalPlatforms,
                          contractCount: contracts.length,
                          workCount: works.length,
                          onOpen: (value) => setState(() => _workspace = value),
                        ),
                      _StationWorkspace.amenities => Column(
                          key: const ValueKey('amenities'),
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            _SectionHeading(
                              title: 'Passenger amenities',
                              count: passengerAmenityRecordCount,
                            ),
                            const SizedBox(height: 12),
                            _AmenitySummary(groups: amenityGroups),
                            const SizedBox(height: 18),
                            _AmenitySubheading(
                              title: 'Platforms',
                              count: totalPlatforms,
                            ),
                            const SizedBox(height: 9),
                            _PlatformList(
                              platforms: platforms,
                              stationLevel: station['platform_type'],
                            ),
                            if (fobAccess.isNotEmpty ||
                                _hasCombinedAccessibility(amenities)) ...[
                              const SizedBox(height: 12),
                              _FobAccessCard(
                                modes: fobAccess,
                                status: _map(amenities['pf_extension_status']),
                              ),
                            ],
                            if (norms.isNotEmpty) ...[
                              const SizedBox(height: 12),
                              _NormsCard(norms: norms),
                            ],
                          ],
                        ),
                      _StationWorkspace.contracts => Column(
                          key: const ValueKey('contracts'),
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            _SectionHeading(
                              title: 'Contracts',
                              count: contracts.length,
                            ),
                            const SizedBox(height: 12),
                            _ContractList(contracts: contracts),
                          ],
                        ),
                      _StationWorkspace.works => Column(
                          key: const ValueKey('works'),
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            _SectionHeading(
                              title: 'Sanctioned works',
                              count: works.length,
                            ),
                            const SizedBox(height: 12),
                            _WorkList(works: works),
                          ],
                        ),
                      _StationWorkspace.inspection => Column(
                          key: const ValueKey('inspection'),
                          children: [
                            _StationActionCenter(stationCode: code),
                            const SizedBox(height: 18),
                            SizedBox(
                              width: double.infinity,
                              height: 56,
                              child: FilledButton.icon(
                                onPressed: () => widget.onStartInspection(code),
                                icon: const Icon(Icons.fact_check_outlined),
                                label: const Text(
                                  'Start inspection',
                                  style: TextStyle(
                                    fontSize: 16,
                                    fontWeight: FontWeight.w900,
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ),
                    },
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _HeroButton extends StatelessWidget {
  const _HeroButton({
    required this.icon,
    required this.onTap,
    required this.tooltip,
  });

  final IconData icon;
  final VoidCallback onTap;
  final String tooltip;

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: tooltip,
      child: Material(
        color: Colors.white.withValues(alpha: 0.88),
        borderRadius: BorderRadius.circular(14),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(14),
          child: SizedBox(
            width: 44,
            height: 44,
            child: Icon(icon, color: const Color(0xFF102A56), size: 21),
          ),
        ),
      ),
    );
  }
}

class _HeroBadge extends StatelessWidget {
  const _HeroBadge(this.label);
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 6),
      decoration: BoxDecoration(
        color: const Color(0xFF2468F2),
        borderRadius: BorderRadius.circular(9),
      ),
      child: Text(
        label,
        style: const TextStyle(
          color: Colors.white,
          fontWeight: FontWeight.w900,
          fontSize: 12,
        ),
      ),
    );
  }
}

class _StationWorkspaceNav extends StatelessWidget {
  const _StationWorkspaceNav({
    required this.selected,
    required this.available,
    required this.counts,
    required this.onSelected,
  });

  final _StationWorkspace selected;
  final List<_StationWorkspace> available;
  final Map<_StationWorkspace, int> counts;
  final ValueChanged<_StationWorkspace> onSelected;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 52,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 2, vertical: 2),
        itemCount: available.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (context, index) {
          final item = available[index];
          final active = item == selected;
          final visual = _workspaceVisual(item);
          final count = counts[item];
          return Material(
            color: Colors.transparent,
            child: InkWell(
              onTap: () => onSelected(item),
              borderRadius: BorderRadius.circular(18),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 220),
                curve: Curves.easeOutCubic,
                padding: const EdgeInsets.symmetric(horizontal: 14),
                decoration: BoxDecoration(
                  color: active
                      ? visual.$3.withValues(alpha: 0.16)
                      : Theme.of(context).colorScheme.surface,
                  borderRadius: BorderRadius.circular(18),
                  border: Border.all(
                    color: active
                        ? visual.$3.withValues(alpha: 0.38)
                        : Theme.of(context).colorScheme.outlineVariant,
                  ),
                  boxShadow: active
                      ? [
                          BoxShadow(
                            color: visual.$3.withValues(alpha: 0.14),
                            blurRadius: 14,
                            offset: const Offset(0, 5),
                          ),
                        ]
                      : null,
                ),
                child: Row(
                  children: [
                    Icon(visual.$2, size: 18, color: visual.$3),
                    const SizedBox(width: 7),
                    Text(
                      visual.$1,
                      style: TextStyle(
                        color: active
                            ? visual.$3
                            : Theme.of(context).colorScheme.onSurface,
                        fontSize: 12,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    if (count != null) ...[
                      const SizedBox(width: 6),
                      Text(
                        '$count',
                        style: TextStyle(
                          color: visual.$3,
                          fontSize: 10,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}

class _StationOverviewWorkspace extends StatelessWidget {
  const _StationOverviewWorkspace({
    super.key,
    required this.station,
    required this.amenities,
    required this.amenityCount,
    required this.platformCount,
    required this.contractCount,
    required this.workCount,
    required this.onOpen,
  });

  final Map<String, dynamic> station;
  final Map<String, dynamic> amenities;
  final int amenityCount;
  final int platformCount;
  final int contractCount;
  final int workCount;
  final ValueChanged<_StationWorkspace> onOpen;

  @override
  Widget build(BuildContext context) {
    final modules = <({
      _StationWorkspace workspace,
      String title,
      String subtitle,
      IconData icon,
      Color tone,
    })>[
      (
        workspace: _StationWorkspace.amenities,
        title: 'Passenger amenities',
        subtitle: '$amenityCount records · $platformCount platforms',
        icon: Icons.accessible_forward_rounded,
        tone: const Color(0xFF12A594),
      ),
      if (contractCount > 0)
        (
          workspace: _StationWorkspace.contracts,
          title: 'Contracts',
          subtitle: '$contractCount linked contracts',
          icon: Icons.storefront_rounded,
          tone: const Color(0xFF7C4DDE),
        ),
      if (workCount > 0)
        (
          workspace: _StationWorkspace.works,
          title: 'Sanctioned works',
          subtitle: '$workCount linked works',
          icon: Icons.engineering_rounded,
          tone: const Color(0xFFEA8A1A),
        ),
      (
        workspace: _StationWorkspace.inspection,
        title: 'Inspection',
        subtitle: 'Findings, alerts and field checks',
        icon: Icons.fact_check_rounded,
        tone: const Color(0xFF2670E8),
      ),
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _StationDetails(station: station, amenities: amenities),
        const SizedBox(height: 20),
        Text(
          'Explore this station',
          style: Theme.of(context)
              .textTheme
              .titleLarge
              ?.copyWith(fontWeight: FontWeight.w900),
        ),
        const SizedBox(height: 10),
        LayoutBuilder(
          builder: (context, constraints) {
            final width = (constraints.maxWidth - 10) / 2;
            return Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [
                for (final module in modules)
                  SizedBox(
                    width: width,
                    child: _WorkspaceCard(
                      title: module.title,
                      subtitle: module.subtitle,
                      icon: module.icon,
                      tone: module.tone,
                      onTap: () => onOpen(module.workspace),
                    ),
                  ),
              ],
            );
          },
        ),
      ],
    );
  }
}

class _WorkspaceCard extends StatelessWidget {
  const _WorkspaceCard({
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.tone,
    required this.onTap,
  });

  final String title;
  final String subtitle;
  final IconData icon;
  final Color tone;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(21),
        child: Ink(
          height: 128,
          padding: const EdgeInsets.all(15),
          decoration: _softCard(context, radius: 21),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 38,
                height: 38,
                decoration: BoxDecoration(
                  color: tone.withValues(alpha: 0.13),
                  borderRadius: BorderRadius.circular(13),
                ),
                child: Icon(icon, color: tone, size: 21),
              ),
              const Spacer(),
              Text(
                title,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style:
                    const TextStyle(fontSize: 13, fontWeight: FontWeight.w900),
              ),
              const SizedBox(height: 3),
              Text(
                subtitle,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                  fontSize: 10,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

(String, IconData, Color) _workspaceVisual(_StationWorkspace workspace) =>
    switch (workspace) {
      _StationWorkspace.overview => (
          'Overview',
          Icons.dashboard_rounded,
          const Color(0xFF2670E8),
        ),
      _StationWorkspace.amenities => (
          'Amenities',
          Icons.accessible_forward_rounded,
          const Color(0xFF12A594),
        ),
      _StationWorkspace.contracts => (
          'Contracts',
          Icons.storefront_rounded,
          const Color(0xFF7C4DDE),
        ),
      _StationWorkspace.works => (
          'Works',
          Icons.engineering_rounded,
          const Color(0xFFEA8A1A),
        ),
      _StationWorkspace.inspection => (
          'Inspection',
          Icons.fact_check_rounded,
          const Color(0xFFE15478),
        ),
    };

class _StationFacts extends StatelessWidget {
  const _StationFacts({
    required this.dailyFootfall,
    required this.platforms,
    required this.zone,
  });

  final String dailyFootfall;
  final int platforms;
  final String zone;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 20),
      decoration: _softCard(context, radius: 24),
      child: Row(
        children: [
          _Fact(
            icon: Icons.groups_2_outlined,
            label: 'Footfall (daily)',
            value: dailyFootfall,
            tone: const Color(0xFF2268E8),
          ),
          _Fact(
            icon: Icons.train_outlined,
            label: 'Platforms',
            value: platforms == 0 ? 'Not recorded' : '$platforms',
            tone: const Color(0xFF0EA5B7),
          ),
          _Fact(
            icon: Icons.hub_outlined,
            label: 'Zone',
            value: zone,
            tone: const Color(0xFF0A9B67),
          ),
        ],
      ),
    );
  }
}

class _Fact extends StatelessWidget {
  const _Fact({
    required this.icon,
    required this.label,
    required this.value,
    required this.tone,
  });

  final IconData icon;
  final String label;
  final String value;
  final Color tone;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        constraints: const BoxConstraints(minHeight: 78),
        padding: const EdgeInsets.symmetric(horizontal: 6),
        decoration: BoxDecoration(
          border: Border(
            right: BorderSide(
              color: Theme.of(context).colorScheme.outlineVariant,
              width: 0.6,
            ),
          ),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 34,
              height: 34,
              decoration: BoxDecoration(
                color: tone.withValues(alpha: 0.11),
                shape: BoxShape.circle,
              ),
              child: Icon(icon, color: tone, size: 18),
            ),
            const SizedBox(height: 7),
            Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
                fontSize: 9,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              value,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w900),
            ),
          ],
        ),
      ),
    );
  }
}

class _StationActions extends StatelessWidget {
  const _StationActions({required this.section, required this.division});

  final String section;
  final String division;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        _ActionTile(
          icon: Icons.route_outlined,
          label: 'Section',
          value: section,
          tone: const Color(0xFF0A9B67),
        ),
        _ActionTile(
          icon: Icons.account_tree_outlined,
          label: 'Division',
          value: division,
          tone: const Color(0xFF6558E8),
        ),
      ],
    );
  }
}

class _StationActionData {
  const _StationActionData({
    required this.findings,
    required this.inspections,
    required this.contractAlerts,
    required this.openWorks,
    required this.amenityGaps,
  });

  final List<Map<String, dynamic>> findings;
  final List<Map<String, dynamic>> inspections;
  final List<Map<String, dynamic>> contractAlerts;
  final int openWorks;
  final int amenityGaps;
}

class _StationActionCenter extends ConsumerStatefulWidget {
  const _StationActionCenter({required this.stationCode});

  final String stationCode;

  @override
  ConsumerState<_StationActionCenter> createState() =>
      _StationActionCenterState();
}

class _StationActionCenterState extends ConsumerState<_StationActionCenter> {
  late Future<_StationActionData> _data;

  @override
  void initState() {
    super.initState();
    _data = _load();
  }

  Future<_StationActionData> _load() async {
    final database = ref.read(databaseProvider);
    final rows = await Future.wait<dynamic>([
      database.findingsForStation(widget.stationCode, openOnly: true),
      database.inspectionsForStation(widget.stationCode),
      database.contractNotificationsForStation(widget.stationCode),
      database.stationDetail(widget.stationCode),
    ]);
    final detail = rows[3] is Map
        ? Map<String, dynamic>.from(rows[3] as Map)
        : <String, dynamic>{};
    final works = detail['works'] is List ? detail['works'] as List : const [];
    final amenities = detail['amenities'] is Map
        ? Map<String, dynamic>.from(detail['amenities'] as Map)
        : <String, dynamic>{};
    final summary = detail['amenity_summary'] is Map
        ? Map<String, dynamic>.from(detail['amenity_summary'] as Map)
        : <String, dynamic>{};
    final action = detail['action_centre'] is Map
        ? Map<String, dynamic>.from(detail['action_centre'] as Map)
        : <String, dynamic>{};
    final calculatedOpenWorks = works.where((raw) {
      if (raw is! Map) return false;
      final status = '${raw['status'] ?? ''}'.toLowerCase();
      return !status.contains('complete') && !status.contains('done');
    }).length;
    final paWorksOpen = (summary['open_pa_works'] as num?)?.toInt() ?? 0;
    final calculatedAmenityGaps = paWorksOpen +
        (amenities['infra'] == null ? 1 : 0) +
        ((amenities['platforms'] as List?)?.isEmpty ?? true ? 1 : 0);
    final openWorks =
        (action['open_works'] as List?)?.length ?? calculatedOpenWorks;
    final amenityGaps =
        (action['amenity_flags'] as List?)?.length ?? calculatedAmenityGaps;
    return _StationActionData(
      findings: rows[0],
      inspections: rows[1],
      contractAlerts: rows[2],
      openWorks: openWorks,
      amenityGaps: amenityGaps,
    );
  }

  void _reload() => setState(() => _data = _load());

  @override
  Widget build(BuildContext context) {
    final sync = ref.watch(syncControllerProvider).valueOrNull;
    return FutureBuilder<_StationActionData>(
      future: _data,
      builder: (context, snapshot) {
        final data = snapshot.data;
        return Container(
          padding: const EdgeInsets.all(14),
          decoration: _solidCard(context, radius: 20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Text(
                    'Action centre',
                    style: Theme.of(context)
                        .textTheme
                        .titleMedium
                        ?.copyWith(fontWeight: FontWeight.w900),
                  ),
                  const Spacer(),
                  if (snapshot.connectionState == ConnectionState.waiting)
                    const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                ],
              ),
              const SizedBox(height: 12),
              GridView.count(
                crossAxisCount: 2,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                childAspectRatio: 2.35,
                crossAxisSpacing: 9,
                mainAxisSpacing: 9,
                children: [
                  _ActionMetric(
                    icon: Icons.report_problem_outlined,
                    label: 'Deficiencies',
                    value: '${data?.findings.length ?? 0}',
                    tone: const Color(0xFFB91C1C),
                    onTap: data == null
                        ? null
                        : () async {
                            final selected = await _showStationFindings(
                              context,
                              data.findings,
                            );
                            if (selected == null || !context.mounted) return;
                            final changed = await showFindingEditor(
                              context,
                              ref,
                              selected,
                            );
                            if (changed) _reload();
                          },
                  ),
                  _ActionMetric(
                    icon: Icons.history_rounded,
                    label: 'Inspections',
                    value: '${data?.inspections.length ?? 0}',
                    tone: const Color(0xFF2563EB),
                    onTap: data == null
                        ? null
                        : () => _showInspectionHistory(
                              context,
                              data.inspections,
                            ),
                  ),
                  _ActionMetric(
                    icon: Icons.notifications_active_outlined,
                    label: 'Contract alerts',
                    value: '${data?.contractAlerts.length ?? 0}',
                    tone: const Color(0xFFD97706),
                    onTap: data == null
                        ? null
                        : () => _showContractAlerts(
                              context,
                              data.contractAlerts,
                            ),
                  ),
                  _ActionMetric(
                    icon: Icons.construction_outlined,
                    label: 'Open works',
                    value: '${data?.openWorks ?? 0}',
                    tone: const Color(0xFF7C3AED),
                    onTap: null,
                  ),
                  _ActionMetric(
                    icon: Icons.accessibility_new_rounded,
                    label: 'Amenity gaps',
                    value: '${data?.amenityGaps ?? 0}',
                    tone: const Color(0xFF0891B2),
                    onTap: null,
                  ),
                  _ActionMetric(
                    icon: sync?.failed == 0
                        ? Icons.cloud_done_outlined
                        : Icons.sync_problem_rounded,
                    label: 'Sync',
                    value: sync == null
                        ? 'Ready'
                        : sync.failed > 0
                            ? '${sync.failed} failed'
                            : '${sync.pending} pending',
                    tone: sync?.failed == 0
                        ? const Color(0xFF0A8F62)
                        : const Color(0xFFB91C1C),
                    onTap: () => _showStationSync(context, ref),
                  ),
                ],
              ),
            ],
          ),
        );
      },
    );
  }
}

class _ActionMetric extends StatelessWidget {
  const _ActionMetric({
    required this.icon,
    required this.label,
    required this.value,
    required this.tone,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final String value;
  final Color tone;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: tone.withValues(alpha: 0.08),
      borderRadius: BorderRadius.circular(15),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(15),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
          child: Row(
            children: [
              Icon(icon, color: tone, size: 22),
              const SizedBox(width: 8),
              Expanded(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      value,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: tone,
                        fontSize: 13,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    Text(
                      label,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

Future<Map<String, dynamic>?> _showStationFindings(
  BuildContext context,
  List<Map<String, dynamic>> rows,
) {
  return showModalBottomSheet<Map<String, dynamic>>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    backgroundColor: Theme.of(context).colorScheme.surface,
    barrierColor: Colors.black54,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(26)),
    ),
    builder: (context) => _StationListSheet(
      title: 'Open deficiencies',
      emptyIcon: Icons.task_alt_rounded,
      emptyText: 'No open deficiencies at this station.',
      children: [
        for (final row in rows)
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: Icon(
              Icons.report_problem_outlined,
              color: _severityTone('${row['severity']}'),
            ),
            title: Text(
              '${row['title']}',
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
            subtitle: Text(
              '${row['responsible_party'] ?? 'Unassigned'} · ${_findingStatus('${row['status']}')}',
            ),
            trailing: const Icon(Icons.chevron_right_rounded),
            onTap: () => Navigator.of(context).pop(row),
          ),
      ],
    ),
  );
}

Future<void> _showInspectionHistory(
  BuildContext context,
  List<Map<String, dynamic>> rows,
) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    backgroundColor: Theme.of(context).colorScheme.surface,
    barrierColor: Colors.black54,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(26)),
    ),
    builder: (context) => _StationListSheet(
      title: 'Inspection history',
      emptyIcon: Icons.fact_check_outlined,
      emptyText: 'No inspections have been recorded for this station.',
      children: [
        for (final row in rows)
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.fact_check_outlined),
            title: Text('${row['inspection_type']} · ${row['status']}'),
            subtitle: Text(
              '${row['inspector_name']} · ${shortDate(row['started_at'])}',
            ),
            trailing: StatusBadge(
              '${row['open_finding_count'] ?? 0} open',
              tone: (row['open_finding_count'] as num?)?.toInt() == 0
                  ? const Color(0xFF0A8F62)
                  : const Color(0xFFB91C1C),
            ),
          ),
      ],
    ),
  );
}

Future<void> _showContractAlerts(
  BuildContext context,
  List<Map<String, dynamic>> rows,
) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    backgroundColor: Theme.of(context).colorScheme.surface,
    barrierColor: Colors.black54,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(26)),
    ),
    builder: (context) => _StationListSheet(
      title: 'Contract alerts',
      emptyIcon: Icons.verified_outlined,
      emptyText: 'No contracts expire within the next 50 days.',
      children: [
        for (final row in rows)
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: Icon(
              Icons.event_busy_outlined,
              color: row['severity'] == 'critical'
                  ? const Color(0xFFB91C1C)
                  : const Color(0xFFD97706),
            ),
            title: Text(
              '${row['contract_code'] ?? row['related_id']} · ${row['contract_name'] ?? 'Contract'}',
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
            subtitle: Text('${row['body']}'),
            trailing: const Icon(Icons.notifications_active_outlined),
          ),
      ],
    ),
  );
}

Future<void> _showStationSync(BuildContext context, WidgetRef ref) {
  final state = ref.read(syncControllerProvider).valueOrNull;
  return showModalBottomSheet<void>(
    context: context,
    useSafeArea: true,
    backgroundColor: Theme.of(context).colorScheme.surface,
    barrierColor: Colors.black54,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(26)),
    ),
    builder: (context) => _StationListSheet(
      title: 'Sync status',
      emptyIcon: Icons.cloud_done_outlined,
      emptyText: state == null
          ? 'Sync status is loading.'
          : '${state.pending} pending · ${state.failed} failed\n${state.message}',
      footer: Column(
        children: [
          AppButton(
            expand: true,
            onPressed: () async {
              await ref.read(syncControllerProvider.notifier).synchronize();
              if (context.mounted) Navigator.of(context).pop();
            },
            icon: Icons.sync_rounded,
            label: 'Sync now',
          ),
          if ((state?.failed ?? 0) > 0) ...[
            const SizedBox(height: 8),
            AppButton(
              expand: true,
              kind: AppButtonKind.secondary,
              onPressed: () async {
                await ref.read(syncControllerProvider.notifier).retryFailed();
                if (context.mounted) Navigator.of(context).pop();
              },
              icon: Icons.replay_rounded,
              label: 'Retry failed',
            ),
          ],
        ],
      ),
    ),
  );
}

class _StationListSheet extends StatelessWidget {
  const _StationListSheet({
    required this.title,
    required this.emptyIcon,
    required this.emptyText,
    this.children = const [],
    this.footer,
  });

  final String title;
  final IconData emptyIcon;
  final String emptyText;
  final List<Widget> children;
  final Widget? footer;

  @override
  Widget build(BuildContext context) {
    return FractionallySizedBox(
      heightFactor: children.isEmpty ? 0.42 : 0.72,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 42,
                height: 4,
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.outlineVariant,
                  borderRadius: BorderRadius.circular(4),
                ),
              ),
            ),
            const SizedBox(height: 16),
            Text(
              title,
              style: Theme.of(context)
                  .textTheme
                  .titleLarge
                  ?.copyWith(fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 10),
            Expanded(
              child: children.isEmpty
                  ? Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(emptyIcon, size: 36),
                          const SizedBox(height: 10),
                          Text(emptyText, textAlign: TextAlign.center),
                        ],
                      ),
                    )
                  : ListView.separated(
                      itemCount: children.length,
                      separatorBuilder: (_, __) => const Divider(height: 1),
                      itemBuilder: (_, index) => children[index],
                    ),
            ),
            if (footer != null) ...[
              const SizedBox(height: 10),
              footer!,
            ],
          ],
        ),
      ),
    );
  }
}

Color _severityTone(String severity) => switch (severity) {
      'critical' => const Color(0xFFB91C1C),
      'high' => const Color(0xFFEA580C),
      'medium' => const Color(0xFFD97706),
      _ => const Color(0xFF2563EB),
    };

String _findingStatus(String value) => value
    .split('_')
    .map((part) =>
        part.isEmpty ? part : '${part[0].toUpperCase()}${part.substring(1)}')
    .join(' ');

class _StationDetails extends StatelessWidget {
  const _StationDetails({required this.station, required this.amenities});

  final Map<String, dynamic> station;
  final Map<String, dynamic> amenities;

  @override
  Widget build(BuildContext context) {
    final infra = _map(amenities['infra']);
    final trolley = _map(amenities['trolley']);
    final wheelchair = _map(amenities['wheelchairs']);
    final rows = <({String label, String value, IconData icon})>[
      (
        label: 'Toilets / pay & use',
        value: cleanText(station['pay_and_use']),
        icon: Icons.wc_outlined
      ),
      (
        label: 'Shelter',
        value: cleanText(infra['shelter_details']),
        icon: Icons.roofing_outlined
      ),
      (
        label: 'Wheelchairs',
        value: cleanText(wheelchair['available_good_condition']),
        icon: Icons.accessible_outlined
      ),
      (
        label: 'Trolley path',
        value: cleanText(trolley['trolley_path']),
        icon: Icons.accessible_forward_outlined
      ),
      (
        label: 'Parking',
        value: cleanText(station['parking']),
        icon: Icons.local_parking_outlined
      ),
      (
        label: 'CMI',
        value: cleanText(station['cmi']),
        icon: Icons.badge_outlined
      ),
      (
        label: 'DEN / Sr DEN',
        value: '${cleanText(station['den'])} / ${cleanText(station['sr_den'])}',
        icon: Icons.supervisor_account_outlined
      ),
    ];
    final visible = rows.where((row) => row.value != '—').toList();
    if (visible.isEmpty) return const SizedBox.shrink();
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: _softCard(context, radius: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Station details',
              style: Theme.of(context)
                  .textTheme
                  .titleMedium
                  ?.copyWith(fontWeight: FontWeight.w900)),
          const SizedBox(height: 12),
          for (final row in visible)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(row.icon,
                      size: 18, color: Theme.of(context).colorScheme.primary),
                  const SizedBox(width: 10),
                  SizedBox(
                    width: 116,
                    child: Text(row.label,
                        style: TextStyle(
                            color:
                                Theme.of(context).colorScheme.onSurfaceVariant,
                            fontSize: 11,
                            fontWeight: FontWeight.w700)),
                  ),
                  Expanded(
                      child: Text(row.value,
                          style: const TextStyle(
                              fontSize: 12, fontWeight: FontWeight.w800))),
                ],
              ),
            ),
          const Divider(height: 20),
          Align(
            alignment: Alignment.centerRight,
            child: TextButton.icon(
              onPressed: () =>
                  _showCompleteStationRecord(context, station, amenities),
              icon: const Icon(Icons.open_in_new_rounded, size: 17),
              label: const Text('Complete station record'),
            ),
          ),
        ],
      ),
    );
  }
}

Future<void> _showCompleteStationRecord(
  BuildContext context,
  Map<String, dynamic> station,
  Map<String, dynamic> amenities,
) {
  final stationRows = _flattenDetailRows(station);
  final amenityRows = _flattenDetailRows(amenities);
  return _showDetailSheet(
    context,
    title: cleanText(station['station_name'], fallback: 'Station record'),
    icon: Icons.account_balance_rounded,
    status: cleanText(station['station_code'], fallback: ''),
    sections: [
      if (stationRows.isNotEmpty)
        _DetailGroup(title: 'Station master', rows: stationRows),
      if (amenityRows.isNotEmpty)
        _DetailGroup(title: 'Passenger amenity details', rows: amenityRows),
    ],
  );
}

List<MapEntry<String, dynamic>> _flattenDetailRows(
  Object? value, {
  String prefix = '',
}) {
  final rows = <MapEntry<String, dynamic>>[];
  if (value is Map) {
    for (final entry in value.entries) {
      final key = entry.key.toString();
      if (_internalDetailKey(key)) continue;
      final label =
          prefix.isEmpty ? _prettyKey(key) : '$prefix · ${_prettyKey(key)}';
      rows.addAll(_flattenDetailRows(entry.value, prefix: label));
    }
  } else if (value is List) {
    for (var index = 0; index < value.length; index++) {
      rows.addAll(
        _flattenDetailRows(value[index], prefix: '$prefix ${index + 1}'),
      );
    }
  } else if (_hasDetailValue(value)) {
    rows.add(MapEntry(prefix, value));
  }
  return rows;
}

class _ActionTile extends StatelessWidget {
  const _ActionTile({
    required this.icon,
    required this.label,
    required this.value,
    required this.tone,
  });

  final IconData icon;
  final String label;
  final String value;
  final Color tone;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        height: 82,
        margin: const EdgeInsets.symmetric(horizontal: 4),
        padding: const EdgeInsets.all(10),
        decoration: _softCard(context, radius: 18),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, color: tone, size: 22),
            const SizedBox(height: 6),
            Text(
              label,
              style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w700),
            ),
            Text(
              value,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w900),
            ),
          ],
        ),
      ),
    );
  }
}

class _SectionHeading extends StatelessWidget {
  const _SectionHeading({required this.title, required this.count});

  final String title;
  final int count;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Text(
            title,
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.w900,
                ),
          ),
        ),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(20),
          ),
          child: Text(
            '$count',
            style: TextStyle(
              color: Theme.of(context).colorScheme.primary,
              fontWeight: FontWeight.w900,
            ),
          ),
        ),
      ],
    );
  }
}

class _AmenitySubheading extends StatelessWidget {
  const _AmenitySubheading({required this.title, required this.count});

  final String title;
  final int count;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Text(
            title,
            style: Theme.of(context)
                .textTheme
                .titleMedium
                ?.copyWith(fontWeight: FontWeight.w900),
          ),
        ),
        StatusBadge('$count'),
      ],
    );
  }
}

class _AmenitySummary extends StatelessWidget {
  const _AmenitySummary({required this.groups});

  final Map<String, List<AmenityItem>> groups;

  @override
  Widget build(BuildContext context) {
    final visible = groups.entries.where((entry) => entry.value.isNotEmpty);
    final entries = visible.toList();
    if (entries.isEmpty) {
      return const _EmptySection(
        icon: Icons.chair_alt_outlined,
        text: 'Amenity details are not available offline yet.',
      );
    }
    return Container(
      height: 92,
      decoration: _solidCard(context, radius: 20),
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 7),
        itemCount: entries.length,
        separatorBuilder: (_, __) => VerticalDivider(
          width: 1,
          color: Theme.of(context).colorScheme.outlineVariant,
        ),
        itemBuilder: (context, index) {
          final entry = entries[index];
          final visual = _amenityVisual('', entry.key);
          return SizedBox(
            width: 142,
            child: InkWell(
              onTap: () => _showAmenityDetails(
                context,
                entry.key,
                entry.value,
              ),
              borderRadius: BorderRadius.circular(15),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 10),
                child: Row(
                  children: [
                    Container(
                      width: 35,
                      height: 35,
                      decoration: BoxDecoration(
                        color: visual.$2.withValues(alpha: 0.12),
                        shape: BoxShape.circle,
                      ),
                      child: Icon(visual.$1, color: visual.$2, size: 19),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            entry.key,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              fontSize: 10,
                              fontWeight: FontWeight.w800,
                              height: 1.1,
                            ),
                          ),
                          const SizedBox(height: 3),
                          Text(
                            '${entry.value.length} items',
                            style: TextStyle(
                              color: visual.$2,
                              fontSize: 10,
                              fontWeight: FontWeight.w900,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}

Future<void> _showAmenityDetails(
  BuildContext context,
  String category,
  List<AmenityItem> items,
) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    backgroundColor: Theme.of(context).colorScheme.surface,
    barrierColor: Colors.black54,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(26)),
    ),
    builder: (context) => FractionallySizedBox(
      heightFactor: 0.72,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const _SheetHandle(),
            const SizedBox(height: 16),
            Text(
              category,
              style: Theme.of(context)
                  .textTheme
                  .titleLarge
                  ?.copyWith(fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 4),
            Text('${items.length} passenger amenity records'),
            const SizedBox(height: 12),
            Expanded(
              child: ListView.separated(
                itemCount: items.length,
                separatorBuilder: (_, __) => const Divider(height: 1),
                itemBuilder: (context, index) {
                  final item = items[index];
                  final visual = _amenityVisual(item.label, category);
                  return ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: Container(
                      width: 40,
                      height: 40,
                      decoration: BoxDecoration(
                        color: visual.$2.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(13),
                      ),
                      child: Icon(visual.$1, color: visual.$2, size: 20),
                    ),
                    title: Text(
                      item.label,
                      style: const TextStyle(fontWeight: FontWeight.w800),
                    ),
                    trailing: item.quantity == null
                        ? const Icon(Icons.check_circle_outline_rounded)
                        : StatusBadge('${item.quantity} available'),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    ),
  );
}

class _FobAccessCard extends StatelessWidget {
  const _FobAccessCard({required this.modes, required this.status});

  final List<String> modes;
  final Map<String, dynamic> status;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: () => _showFobDetails(context, modes, status),
        borderRadius: BorderRadius.circular(18),
        child: Ink(
          height: 66,
          padding: const EdgeInsets.symmetric(horizontal: 13),
          decoration: _solidCard(context, radius: 18),
          child: Row(
            children: [
              Container(
                width: 38,
                height: 38,
                decoration: BoxDecoration(
                  color: const Color(0xFFE4F7F2),
                  borderRadius: BorderRadius.circular(13),
                ),
                child: const Icon(
                  Icons.stairs_outlined,
                  color: Color(0xFF149A83),
                ),
              ),
              const SizedBox(width: 11),
              Expanded(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Foot over bridge',
                      style: TextStyle(fontWeight: FontWeight.w900),
                    ),
                    Text(
                      modes.isEmpty
                          ? 'Accessibility details available'
                          : modes.join(' · '),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right_rounded),
            ],
          ),
        ),
      ),
    );
  }
}

bool _hasCombinedAccessibility(Map<String, dynamic> amenities) {
  final status = _map(amenities['pf_extension_status']);
  return ['lift_details', 'ramp_details', 'escalator_details']
      .any((key) => _meaningfulAccessibilityValue(status[key]));
}

class _AccessibilityDetailRow extends StatelessWidget {
  const _AccessibilityDetailRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: _solidCard(context, radius: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontWeight: FontWeight.w900)),
          const SizedBox(height: 5),
          Text(value, style: Theme.of(context).textTheme.bodyMedium),
        ],
      ),
    );
  }
}

Future<void> _showFobDetails(
  BuildContext context,
  List<String> modes,
  Map<String, dynamic> status,
) {
  final details = _accessibilityDetails(status);
  return showModalBottomSheet<void>(
    context: context,
    useSafeArea: true,
    backgroundColor: Theme.of(context).colorScheme.surface,
    barrierColor: Colors.black54,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(26)),
    ),
    builder: (context) => SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SheetHandle(),
          const SizedBox(height: 16),
          Text(
            'Foot over bridge',
            style: Theme.of(context)
                .textTheme
                .titleLarge
                ?.copyWith(fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 6),
          const Text(
              'Access and connectivity details recorded for this station.'),
          const SizedBox(height: 12),
          for (final mode in modes)
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(
                Icons.check_circle_outline_rounded,
                color: Color(0xFF149A83),
              ),
              title: Text(
                mode,
                style: const TextStyle(fontWeight: FontWeight.w800),
              ),
            ),
          if (details.isNotEmpty) ...[
            const SizedBox(height: 8),
            const Text(
              'Lift, ramp and escalator details',
              style: TextStyle(fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 8),
            for (final detail in details)
              _AccessibilityDetailRow(label: detail.$1, value: detail.$2),
          ],
        ],
      ),
    ),
  );
}

List<(String, String)> _accessibilityDetails(Map<String, dynamic> status) {
  const fields = [
    ('Lifts', 'lift_details'),
    ('Ramps', 'ramp_details'),
    ('Escalators', 'escalator_details'),
  ];
  return [
    for (final field in fields)
      if (_meaningfulAccessibilityValue(status[field.$2]))
        (field.$1, cleanText(status[field.$2])),
  ];
}

bool _meaningfulAccessibilityValue(Object? value) {
  final normalized = cleanText(value, fallback: '').trim().toLowerCase();
  return normalized.isNotEmpty &&
      normalized != 'na' &&
      normalized != 'n/a' &&
      normalized != '-' &&
      normalized != 'nil' &&
      normalized != 'none';
}

class _NormsCard extends StatelessWidget {
  const _NormsCard({required this.norms});

  final List<dynamic> norms;

  @override
  Widget build(BuildContext context) {
    final groups = _groupNorms(norms);
    final visibleGroups =
        groups.entries.where((entry) => entry.value.isNotEmpty).toList();
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: () => _showNormDetails(context, visibleGroups),
        borderRadius: BorderRadius.circular(18),
        child: Ink(
          height: 92,
          padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 10),
          decoration: _solidCard(context, radius: 18),
          child: Row(
            children: [
              Container(
                width: 38,
                height: 38,
                decoration: BoxDecoration(
                  color: const Color(0xFFEDE4FF),
                  borderRadius: BorderRadius.circular(13),
                ),
                child: const Icon(
                  Icons.rule_rounded,
                  color: Color(0xFF7650C9),
                  size: 20,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Passenger amenity norms',
                      style: TextStyle(fontWeight: FontWeight.w900),
                    ),
                    const SizedBox(height: 5),
                    SingleChildScrollView(
                      scrollDirection: Axis.horizontal,
                      child: Row(
                        children: [
                          for (final entry in visibleGroups) ...[
                            _NormCountChip(
                              label: entry.key,
                              count: entry.value.length,
                            ),
                            const SizedBox(width: 5),
                          ],
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 6),
              const Icon(Icons.chevron_right_rounded),
            ],
          ),
        ),
      ),
    );
  }
}

class _NormCountChip extends StatelessWidget {
  const _NormCountChip({required this.label, required this.count});

  final String label;
  final int count;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 4),
      decoration: BoxDecoration(
        color: const Color(0xFFEDE4FF),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(
        '$label $count',
        style: const TextStyle(
          color: Color(0xFF7650C9),
          fontSize: 9,
          fontWeight: FontWeight.w900,
        ),
      ),
    );
  }
}

Map<String, List<Map<String, dynamic>>> _groupNorms(List<dynamic> norms) {
  final groups = <String, List<Map<String, dynamic>>>{
    'MEA': [],
    'Recommended': [],
    'Desirable': [],
    'Divyangjan': [],
    'Other': [],
  };
  for (final raw in norms) {
    final row = _map(raw);
    final rawHead = cleanText(row['amenity'], fallback: '').toLowerCase();
    final heading = rawHead.contains('divyang')
        ? 'Divyangjan'
        : rawHead.contains('recommend')
            ? 'Recommended'
            : rawHead.contains('desirable')
                ? 'Desirable'
                : rawHead == 'mea'
                    ? 'MEA'
                    : 'Other';
    groups[heading]!.add(row);
  }
  return groups;
}

Future<void> _showNormDetails(
  BuildContext context,
  List<MapEntry<String, List<Map<String, dynamic>>>> groups,
) {
  if (groups.isEmpty) return Future.value();
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    backgroundColor: Theme.of(context).colorScheme.surface,
    barrierColor: Colors.black54,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(26)),
    ),
    builder: (context) => FractionallySizedBox(
      heightFactor: 0.84,
      child: DefaultTabController(
        length: groups.length,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(18, 12, 18, 20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const _SheetHandle(),
              const SizedBox(height: 15),
              Text(
                'Passenger amenity norms',
                style: Theme.of(context)
                    .textTheme
                    .titleLarge
                    ?.copyWith(fontWeight: FontWeight.w900),
              ),
              const SizedBox(height: 4),
              const Text('Requirements applicable to this station category.'),
              const SizedBox(height: 12),
              TabBar(
                isScrollable: true,
                tabAlignment: TabAlignment.start,
                tabs: [
                  for (final entry in groups)
                    Tab(text: '${entry.key} (${entry.value.length})'),
                ],
              ),
              const SizedBox(height: 10),
              Expanded(
                child: TabBarView(
                  children: [
                    for (final entry in groups)
                      ListView(
                        padding: const EdgeInsets.only(top: 4),
                        children: [
                          _NormGroup(title: entry.key, rows: entry.value),
                        ],
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    ),
  );
}

class _NormGroup extends StatelessWidget {
  const _NormGroup({required this.title, required this.rows});

  final String title;
  final List<Map<String, dynamic>> rows;

  @override
  Widget build(BuildContext context) {
    final color = Theme.of(context).colorScheme.primary;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.10),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Text(title,
                  style: TextStyle(color: color, fontWeight: FontWeight.w900)),
            ),
            const SizedBox(width: 8),
            Text('${rows.length} norms',
                style: TextStyle(
                    color: color.withValues(alpha: 0.72), fontSize: 11)),
          ],
        ),
        const SizedBox(height: 5),
        for (final row in rows)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 6),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.circle, size: 6, color: color),
                const SizedBox(width: 9),
                Expanded(
                  child: Text(
                      cleanText(row['norm'], fallback: 'Norm not recorded'),
                      style: const TextStyle(fontSize: 12, height: 1.25)),
                ),
                if (cleanText(row['norm_quantity']).isNotEmpty) ...[
                  const SizedBox(width: 8),
                  Container(
                    constraints: const BoxConstraints(maxWidth: 130),
                    padding:
                        const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: color.withValues(alpha: 0.08),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(cleanText(row['norm_quantity']),
                        textAlign: TextAlign.right,
                        style: TextStyle(
                            color: color,
                            fontSize: 10,
                            fontWeight: FontWeight.w900)),
                  ),
                ],
              ],
            ),
          ),
      ],
    );
  }
}

class _PlatformList extends StatelessWidget {
  const _PlatformList({required this.platforms, this.stationLevel});
  final List<dynamic> platforms;
  final Object? stationLevel;

  @override
  Widget build(BuildContext context) {
    if (platforms.isEmpty) {
      return const _EmptySection(
        icon: Icons.train_outlined,
        text: 'Platform details are not available offline yet.',
      );
    }
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: _softCard(context, radius: 22),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final columns = constraints.maxWidth >= 600 ? 3 : 2;
          return GridView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: platforms.length,
            gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: columns,
              crossAxisSpacing: 2,
              mainAxisSpacing: 2,
              childAspectRatio: 2.25,
            ),
            itemBuilder: (context, index) {
              final row = _map(platforms[index]);
              final number = cleanText(
                row['platform'] ?? row['platform_no'],
                fallback: 'PF',
              );
              final level = _platformLevel(row, stationLevel);
              final length = numericValue(row['length_m'] ?? row['length']);
              final extras = [
                if ((numericValue(row['lifts']) ?? 0) > 0)
                  'Lift ${cleanText(row['lifts'], fallback: '')}',
                if ((numericValue(row['escalators']) ?? 0) > 0)
                  'Escalator ${cleanText(row['escalators'], fallback: '')}',
                if (cleanText(row['ramp'], fallback: '').isNotEmpty)
                  'Ramp ${cleanText(row['ramp'], fallback: '')}',
              ];
              return Padding(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 7),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            number.toUpperCase().startsWith('PF')
                                ? number
                                : 'PF $number',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.w900,
                            ),
                          ),
                        ),
                        _LevelChip(level: level),
                      ],
                    ),
                    Text(
                      length == null
                          ? 'Length not recorded'
                          : 'Length ${length.round()} m',
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    if (extras.isNotEmpty)
                      Text(
                        extras.join('  |  '),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.primary,
                          fontSize: 10,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                  ],
                ),
              );
            },
          );
        },
      ),
    );
  }
}

class _LevelChip extends StatelessWidget {
  const _LevelChip({required this.level});

  final String level;

  @override
  Widget build(BuildContext context) {
    final high = level == 'High Level';
    final color = high ? const Color(0xFF18A995) : const Color(0xFF9859E8);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(
        high
            ? 'High level'
            : level == 'Low Level'
                ? 'Low level'
                : 'Level ?',
        style: TextStyle(
          color: color,
          fontSize: 9,
          fontWeight: FontWeight.w900,
        ),
      ),
    );
  }
}

String _platformLevel(Map<String, dynamic> row, Object? fallback) {
  final raw = cleanText(
    row['platform_level'] ?? row['level'] ?? fallback,
    fallback: '',
  ).toLowerCase();
  if (raw.contains('hl') || raw.contains('high')) return 'High Level';
  if (raw.contains('ll') || raw.contains('low') || raw.contains('ml')) {
    return 'Low Level';
  }
  return 'Level not recorded';
}

class _ContractList extends StatelessWidget {
  const _ContractList({required this.contracts});
  final List<ContractSummary> contracts;

  @override
  Widget build(BuildContext context) {
    if (contracts.isEmpty) {
      return const _EmptySection(
        icon: Icons.storefront_outlined,
        text: 'No contracts are linked to this station.',
      );
    }
    return Column(
      children: [
        for (final contract in contracts)
          Padding(
            padding: const EdgeInsets.only(bottom: 9),
            child: _InfoRow(
              icon: Icons.storefront_rounded,
              title: '${contract.name} · ${contractValidityLabel(contract)}',
              subtitle: contract.status.toLowerCase() == 'available'
                  ? cleanText(
                      contract.details['remarks'] ??
                          contract.details['availability_remarks'],
                      fallback: '${contract.type} available for allotment',
                    )
                  : '${contract.type}  •  ${formatCurrency(contract.earnings)}',
              trailing: contractRiskLabel(contract),
              onTap: () => _showContractDetails(context, contract),
            ),
          ),
      ],
    );
  }
}

class _WorkList extends StatelessWidget {
  const _WorkList({required this.works});
  final List<WorkSummary> works;

  @override
  Widget build(BuildContext context) {
    if (works.isEmpty) {
      return const _EmptySection(
        icon: Icons.engineering_outlined,
        text: 'No sanctioned works are linked to this station.',
      );
    }
    return _GroupedWorkList(works: works);
    /*
    return Column(
      children: [
        for (final work in works.take(8))
          Padding(
            padding: const EdgeInsets.only(bottom: 9),
            child: _InfoRow(
              icon: Icons.engineering_rounded,
              title: work.name,
              subtitle: [
                if (work.cost != '—') work.cost,
                if (work.progress != null) '${work.progress}% progress',
                if (work.targetCompletion != '—')
                  'TDC ${work.targetCompletion}',
              ].join('  |  '),
              trailing: work.status,
              onTap: () => _showWorkDetails(context, work),
            ),
          ),
      ],
    );
    */
  }
}

class _GroupedWorkList extends StatelessWidget {
  const _GroupedWorkList({required this.works});
  final List<WorkSummary> works;

  @override
  Widget build(BuildContext context) {
    final groups = <String, List<WorkSummary>>{};
    for (final work in works) {
      final status = work.status.toLowerCase();
      final group = (work.progress ?? 0) >= 100 ||
              status.contains('complete') ||
              status.contains('closed')
          ? 'Completed'
          : status.contains('tender')
              ? 'Under tender'
              : (work.progress ?? 0) > 0 ||
                      status.contains('progress') ||
                      status.contains('ongoing') ||
                      status.contains('started')
                  ? 'Work in progress'
                  : status.contains('sanction') || (work.progress ?? 0) == 0
                      ? 'Sanctioned / not started'
                      : 'Other works';
      groups.putIfAbsent(group, () => []).add(work);
    }
    const order = [
      'Work in progress',
      'Completed',
      'Under tender',
      'Sanctioned / not started',
      'Other works'
    ];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final group in order)
          if (groups[group]?.isNotEmpty == true) ...[
            Padding(
              padding: const EdgeInsets.only(top: 8, bottom: 8),
              child: Row(
                children: [
                  Text(group,
                      style: const TextStyle(fontWeight: FontWeight.w900)),
                  const SizedBox(width: 8),
                  _CountChip(count: groups[group]!.length),
                ],
              ),
            ),
            for (final work in groups[group]!)
              Padding(
                padding: const EdgeInsets.only(bottom: 9),
                child: _InfoRow(
                  icon: Icons.engineering_rounded,
                  title: work.name,
                  subtitle: [
                    if (work.cost != 'â€”') work.cost,
                    if (work.progress != null) '${work.progress}% progress',
                    if (work.targetCompletion != 'â€”')
                      'TDC ${work.targetCompletion}',
                  ].join('  |  '),
                  trailing: work.status,
                  onTap: () => _showSanctionedWorkDetails(context, work),
                ),
              ),
          ],
      ],
    );
  }
}

class _CountChip extends StatelessWidget {
  const _CountChip({required this.count});
  final int count;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.primaryContainer,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text('$count',
          style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w900)),
    );
  }
}

class _InfoRow extends StatelessWidget {
  const _InfoRow({
    required this.icon,
    required this.title,
    required this.subtitle,
    this.trailing,
    this.onTap,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final String? trailing;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(18),
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: _softCard(context, radius: 18),
          child: Row(
            children: [
              Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(
                  color: colors.primary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(icon, color: colors.primary, size: 21),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontWeight: FontWeight.w900),
                    ),
                    if (subtitle.isNotEmpty) ...[
                      const SizedBox(height: 3),
                      Text(
                        subtitle,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          color: colors.onSurfaceVariant,
                          fontSize: 11,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              if (trailing != null && trailing!.isNotEmpty) ...[
                const SizedBox(width: 8),
                Container(
                  constraints: const BoxConstraints(maxWidth: 86),
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
                  decoration: BoxDecoration(
                    color: statusTone(trailing!).withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    trailing!,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: statusTone(trailing!),
                      fontSize: 9,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _EmptySection extends StatelessWidget {
  const _EmptySection({required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: _softCard(context, radius: 18),
      child: Column(
        children: [
          Icon(
            icon,
            color: Theme.of(context).colorScheme.primary,
            size: 30,
          ),
          const SizedBox(height: 8),
          Text(
            text,
            textAlign: TextAlign.center,
            style: TextStyle(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
        ],
      ),
    );
  }
}

BoxDecoration _softCard(BuildContext context, {double radius = 20}) {
  final theme = Theme.of(context);
  final dark = theme.brightness == Brightness.dark;
  return BoxDecoration(
    color: theme.colorScheme.surface,
    borderRadius: BorderRadius.circular(radius),
    border: Border.all(color: theme.colorScheme.outlineVariant),
    boxShadow: [
      BoxShadow(
        color: Colors.black.withValues(alpha: dark ? 0.24 : 0.07),
        blurRadius: 24,
        spreadRadius: -8,
        offset: const Offset(0, 10),
      ),
    ],
  );
}

BoxDecoration _solidCard(BuildContext context, {double radius = 20}) {
  final theme = Theme.of(context);
  final surface = Color.alphaBlend(
    theme.colorScheme.primary.withValues(alpha: 0.035),
    theme.colorScheme.surface,
  );
  return BoxDecoration(
    color: surface,
    borderRadius: BorderRadius.circular(radius),
    border: Border.all(
      color: theme.colorScheme.outlineVariant.withValues(alpha: 0.9),
    ),
    boxShadow: [
      BoxShadow(
        color: Colors.black.withValues(
          alpha: theme.brightness == Brightness.dark ? 0.28 : 0.09,
        ),
        blurRadius: 20,
        spreadRadius: -7,
        offset: const Offset(0, 9),
      ),
    ],
  );
}

class _SheetHandle extends StatelessWidget {
  const _SheetHandle();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Container(
        width: 42,
        height: 4,
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.outlineVariant,
          borderRadius: BorderRadius.circular(4),
        ),
      ),
    );
  }
}

(IconData, Color) _amenityVisual(String label, String category) {
  final value = label.toLowerCase();
  if (value.contains('lift')) {
    return (Icons.elevator_outlined, const Color(0xFF00A878));
  }
  if (value.contains('escalator')) {
    return (Icons.escalator_outlined, const Color(0xFFE84855));
  }
  if (value.contains('wheel')) {
    return (Icons.accessible_forward_rounded, const Color(0xFF2268E8));
  }
  if (value.contains('toilet')) {
    return (Icons.wc_rounded, const Color(0xFF7C4DFF));
  }
  if (value.contains('fob')) {
    return (Icons.stairs_outlined, const Color(0xFF0EA5B7));
  }
  if (value.contains('ramp') || value.contains('trolley')) {
    return (Icons.accessible_rounded, const Color(0xFFF59E0B));
  }
  return switch (category) {
    'Waiting Facilities' => (Icons.chair_alt_outlined, const Color(0xFF2268E8)),
    'Passenger Convenience' => (
        Icons.local_convenience_store_outlined,
        const Color(0xFFF59E0B)
      ),
    'Accessibility' => (
        Icons.accessibility_new_rounded,
        const Color(0xFF0EA5B7)
      ),
    _ => (Icons.display_settings_outlined, const Color(0xFF7C4DFF)),
  };
}

Map<String, dynamic> _map(Object? value) =>
    value is Map ? Map<String, dynamic>.from(value) : <String, dynamic>{};

List<String> _fobAccessModes(Map<String, dynamic> amenities) {
  final existing = _list(amenities['fob_access'])
      .map((value) => cleanText(value, fallback: ''))
      .where((value) => value.isNotEmpty)
      .toList();
  if (existing.isNotEmpty) return existing;
  final infra = _map(amenities['infra']);
  final status = _map(amenities['pf_extension_status']);
  final fob = cleanText(infra['fob_details'], fallback: '').toLowerCase();
  if (fob.isEmpty || fob == '-' || fob == 'none' || fob == 'no') {
    return const [];
  }
  final modes = <String>['FOB'];
  final ramp =
      status['fob_ramp_available'] == true || status['ramp_feasible'] == true;
  final lift = status['lift_available'] == true;
  if (ramp) modes.add('Ramp available');
  if (lift) modes.add('Lift available');
  if (!ramp && !lift) modes.add('Stairs');
  if (status['fob_wip'] == true) modes.add('FOB work in progress');
  if (status['ramp_proposed'] == true) modes.add('Ramp proposed');
  if (status['lift_proposed'] == true) modes.add('Lift proposed');
  return modes;
}

List<dynamic> _list(Object? value) => value is List ? value : const [];

List<dynamic> _platformRows(
  Map<String, dynamic> station,
  Map<String, dynamic> amenities,
) {
  final rows = _list(amenities['platforms']);
  if (rows.isNotEmpty) return rows;
  final infra = _map(amenities['infra']);
  final raw = cleanText(
    infra['platform_list'] ?? station['platforms'],
    fallback: '',
  );
  final labels = raw
      .split(RegExp(r'[,;/]+'))
      .map((value) => value.trim())
      .where((value) => value.isNotEmpty)
      .toList();
  if (labels.isNotEmpty) {
    return [
      for (final label in labels) {'platform': label}
    ];
  }
  final declared = highestPlatformNumber(
    const [],
    stationPlatforms: station['number_of_platforms'],
  );
  return [
    for (var index = 1; index <= declared; index++) {'platform': 'PF-$index'},
  ];
}

Future<void> _showContractDetails(
  BuildContext context,
  ContractSummary contract,
) async {
  final detailKeys = [
    'unit_no',
    'licensee_name',
    'type_of_unit',
    'unit_status',
    'remarks',
    'availability_remarks',
    'station_code',
    'pf_no',
    'station_category',
    'policy',
    'sub_category',
    'allocation_code',
    'asset_scope',
    'license_fee',
    'annual_license_fee',
    'quarterly_license_fee',
    'total_license_fee_2026_2027',
  ];
  final details = <MapEntry<String, dynamic>>[];
  for (final key in detailKeys) {
    final value = contract.details[key];
    if (_hasDetailValue(value)) details.add(MapEntry(key, value));
  }
  final paymentTotal = contract.payments.fold<double>(
    0,
    (sum, payment) =>
        sum +
        (numericValue(payment['amount'] ??
                payment['amount_paid'] ??
                payment['paid_amount']) ??
            0),
  );
  final paidThrough = _latestPaymentValue(contract.payments, 'period_to');
  final lastReceipt = _latestPaymentValue(
      contract.payments, 'date_of_receipt', 'receipt_date', 'mr_date');
  final remainingDays = contract.daysToExpiry == null
      ? 'Not calculable - validity end date not recorded'
      : contract.daysToExpiry! < 0
          ? 'Expired ${-contract.daysToExpiry!} days ago'
          : contract.daysToExpiry == 0
              ? 'Expires today'
              : '${contract.daysToExpiry} days';
  final available = contract.status.toLowerCase() == 'available';
  await _showDetailSheet(
    context,
    title: contract.name,
    icon: Icons.storefront_rounded,
    status: contractRiskLabel(contract),
    sections: [
      _DetailGroup(title: 'Contract summary', rows: [
        MapEntry('Type', contract.type),
        MapEntry('Contract status', contract.status),
        if (available)
          MapEntry(
            'Remarks',
            cleanText(
              contract.details['remarks'] ??
                  contract.details['availability_remarks'] ??
                  contract.details['unit_status'],
              fallback: 'Available for allotment',
            ),
          )
        else ...[
          MapEntry('Risk level', contractRiskLabel(contract)),
          MapEntry('Renewal status', contract.renewalState),
          MapEntry(
              'Valid from',
              contract.validFrom == null
                  ? 'Not recorded'
                  : formatContractDate(contract.validFrom!)),
          MapEntry(
              'Valid till',
              contract.validTo == null
                  ? 'Not recorded'
                  : formatContractDate(contract.validTo!)),
          MapEntry('Remaining days', remainingDays),
          MapEntry('Validity', contractValidityLabel(contract)),
          MapEntry('Payment entries', contract.payments.length),
          MapEntry(
              'Payments recorded',
              formatCurrency(
                  paymentTotal > 0 ? paymentTotal : contract.earnings)),
          MapEntry('Last receipt', lastReceipt ?? 'Not recorded'),
          MapEntry('Paid through', paidThrough ?? 'Not recorded'),
        ],
      ]),
      if (details.isNotEmpty)
        _DetailGroup(
            title: 'Contract information',
            rows: details
                .map((e) => MapEntry(_prettyKey(e.key), e.value))
                .toList()),
      if (!available)
        _DetailGroup(
          title: 'Payments so far',
          rows: contract.payments.isEmpty
              ? const [
                  MapEntry('Payment history', 'No payment records available')
                ]
              : [
                  MapEntry(
                      'Total paid',
                      formatCurrency(
                          paymentTotal > 0 ? paymentTotal : contract.earnings)),
                  for (var i = 0; i < contract.payments.length; i++)
                    MapEntry(
                        cleanText(
                          contract.payments[i]['mr_no'],
                          fallback: 'Payment ${i + 1}',
                        ),
                        _paymentSummary(contract.payments[i])),
                ],
        ),
    ],
  );
}

String _paymentSummary(Map<String, dynamic> payment) {
  final date = payment['date_of_receipt'] ??
      payment['receipt_date'] ??
      payment['mr_date'] ??
      payment['payment_month'] ??
      payment['month'] ??
      payment['date'];
  final amount = payment['amount'] ??
      payment['amount_paid'] ??
      payment['paid_amount'] ??
      payment['earnings'];
  final periodFrom = payment['period_from'];
  final periodTo = payment['period_to'];
  final receiptType =
      payment['receipt_type'] ?? payment['payment_status'] ?? payment['status'];
  final gst = payment['gst'];
  return [
    if (_hasDetailValue(date)) 'Received ${cleanText(date)}',
    if (_hasDetailValue(amount))
      'Amount ${formatCurrency(numericValue(amount) ?? 0)}',
    if (_hasDetailValue(gst)) 'GST ${formatCurrency(numericValue(gst) ?? 0)}',
    if (_hasDetailValue(periodFrom) || _hasDetailValue(periodTo))
      'Period ${cleanText(periodFrom, fallback: '?')} to ${cleanText(periodTo, fallback: '?')}',
    if (_hasDetailValue(receiptType)) cleanText(receiptType),
  ].join('  |  ');
}

String? _latestPaymentValue(
  List<Map<String, dynamic>> payments,
  String primary, [
  String? secondary,
  String? tertiary,
]) {
  final values = <String>[];
  for (final payment in payments) {
    final value = payment[primary] ??
        (secondary == null ? null : payment[secondary]) ??
        (tertiary == null ? null : payment[tertiary]);
    if (_hasDetailValue(value)) values.add(cleanText(value));
  }
  if (values.isEmpty) return null;
  values.sort((a, b) => _sortableDate(a).compareTo(_sortableDate(b)));
  return values.last;
}

DateTime _sortableDate(String value) {
  final iso = DateTime.tryParse(value);
  if (iso != null) return iso;
  final match =
      RegExp(r'^(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})').firstMatch(value);
  if (match == null) return DateTime(1900);
  final yearValue = int.parse(match.group(3)!);
  return DateTime(
    yearValue < 100 ? 2000 + yearValue : yearValue,
    int.parse(match.group(2)!),
    int.parse(match.group(1)!),
  );
}

Future<void> _showSanctionedWorkDetails(
  BuildContext context,
  WorkSummary work,
) async {
  final row = work.details;
  await _showDetailSheet(
    context,
    title: work.name,
    icon: Icons.engineering_rounded,
    status: '',
    sections: [
      _DetailGroup(
        title: 'Sanctioned work details',
        rows: [
          MapEntry('Project ID',
              _firstDetailValue(row, ['project_id', 'project id'])),
          MapEntry(
              'Year of sanction',
              _firstDetailValue(row,
                  ['year_of_sanction', 'year of sanction', 'sanction_year'])),
          MapEntry('UB works',
              _firstDetailValue(row, ['ub_works', 'ub works', 'ub'])),
          MapEntry(
              'Date of sanction',
              _firstDetailValue(row,
                  ['sanction_date', 'date_of_sanction', 'date of sanction'])),
          MapEntry(
              'Allocation', _firstDetailValue(row, ['allocation', 'alloc'])),
          MapEntry('Cost', _firstDetailValue(row, ['cost'])),
          MapEntry('Remarks', _firstDetailValue(row, ['remarks', 'remark'])),
        ],
      ),
    ],
  );
}

String _firstDetailValue(Map<String, dynamic> row, List<String> keys) {
  for (final key in keys) {
    final value = row[key];
    if (_hasDetailValue(value)) return cleanText(value);
  }
  return 'Not recorded';
}

// ignore: unused_element
Future<void> _showWorkDetails(BuildContext context, WorkSummary work) async {
  final row = work.details;
  final used = <String>{};
  List<MapEntry<String, dynamic>> pick(List<String> keys) {
    final result = <MapEntry<String, dynamic>>[];
    for (final key in keys) {
      final value = row[key];
      if (_hasDetailValue(value)) {
        used.add(key);
        result.add(MapEntry(_prettyKey(key), value));
      }
    }
    return result;
  }

  final sections = <_DetailGroup>[
    _DetailGroup(
        title: 'Work identity',
        rows: pick([
          'project_id',
          'block_section_station',
          'station',
          'section',
          'allocation',
          'category',
          'work_type',
        ])),
    _DetailGroup(
        title: 'Schedule and cost',
        rows: pick([
          'sanction_date',
          'tdc',
          'target_completion',
          'cost',
          'physical_progress',
          'financial_progress',
          'expenditure_up_to_date',
          'anticipated_date',
        ])),
    _DetailGroup(
        title: 'Remarks and execution',
        rows: pick([
          'remarks',
          'engineering_remarks',
          'executive_agency',
          'tender_status',
          'loa_date',
          'status',
        ])),
  ];
  final remaining = row.entries
      .where((entry) =>
          !used.contains(entry.key) &&
          !_internalDetailKey(entry.key) &&
          _hasDetailValue(entry.value))
      .map((entry) => MapEntry(_prettyKey(entry.key), entry.value))
      .toList();
  if (remaining.isNotEmpty) {
    sections.add(_DetailGroup(title: 'Additional details', rows: remaining));
  }
  await _showDetailSheet(
    context,
    title: work.name,
    icon: Icons.engineering_rounded,
    status: work.status,
    progress: work.progress,
    sections: sections.where((section) => section.rows.isNotEmpty).toList(),
  );
}

bool _hasDetailValue(Object? value) {
  final text = value?.toString().trim() ?? '';
  return text.isNotEmpty &&
      text.toLowerCase() != 'null' &&
      text != '-' &&
      text != 'â€”';
}

bool _internalDetailKey(String key) {
  final normalized = key.trim().toLowerCase();
  return normalized.startsWith('source') ||
      normalized == 'created_at' ||
      normalized == 'updated_at' ||
      normalized == 'first_seen_at' ||
      normalized == 'last_seen_at' ||
      normalized == 'is_active';
}

class _DetailGroup {
  const _DetailGroup({required this.title, required this.rows});
  final String title;
  final List<MapEntry<String, dynamic>> rows;
}

Future<void> _showDetailSheet(
  BuildContext context, {
  required String title,
  required IconData icon,
  required String status,
  int? progress,
  required List<_DetailGroup> sections,
}) async {
  await showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    backgroundColor: Theme.of(context).colorScheme.surface,
    barrierColor: Colors.black54,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(26)),
    ),
    builder: (context) {
      final colors = Theme.of(context).colorScheme;
      return Padding(
        padding: const EdgeInsets.fromLTRB(12, 20, 12, 12),
        child: Material(
          color: colors.surface,
          borderRadius: BorderRadius.circular(26),
          clipBehavior: Clip.antiAlias,
          child: SizedBox(
            height: MediaQuery.sizeOf(context).height * 0.82,
            child: Column(
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 18, 14, 14),
                  child: Row(children: [
                    Icon(icon, color: colors.primary),
                    const SizedBox(width: 10),
                    Expanded(
                        child: Text(title,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: Theme.of(context)
                                .textTheme
                                .titleLarge
                                ?.copyWith(fontWeight: FontWeight.w900))),
                    if (status.isNotEmpty) _StatusChip(label: status),
                    IconButton(
                        tooltip: 'Close',
                        onPressed: () => Navigator.of(context).pop(),
                        icon: const Icon(Icons.close_rounded)),
                  ]),
                ),
                if (progress != null)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(20, 0, 20, 14),
                    child: Row(children: [
                      Text('Progress',
                          style: TextStyle(
                              color: colors.onSurfaceVariant,
                              fontWeight: FontWeight.w800)),
                      const Spacer(),
                      Text('$progress%',
                          style: const TextStyle(fontWeight: FontWeight.w900))
                    ]),
                  ),
                const Divider(height: 1),
                Expanded(
                    child:
                        ListView(padding: const EdgeInsets.all(20), children: [
                  for (final section in sections) ...[
                    Text(section.title,
                        style: TextStyle(
                            color: colors.primary,
                            fontWeight: FontWeight.w900)),
                    const SizedBox(height: 8),
                    Container(
                      padding: const EdgeInsets.all(14),
                      decoration: _softCard(context, radius: 18),
                      child: Column(children: [
                        for (final row in section.rows)
                          _DetailField(
                              label: row.key, value: row.value.toString())
                      ]),
                    ),
                    const SizedBox(height: 16),
                  ],
                ])),
              ],
            ),
          ),
        ),
      );
    },
  );
}

class _DetailField extends StatelessWidget {
  const _DetailField({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 7),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Expanded(
            flex: 2,
            child: Text(label,
                style: TextStyle(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                    fontSize: 11,
                    fontWeight: FontWeight.w800))),
        const SizedBox(width: 12),
        Expanded(
            flex: 3,
            child: Text(cleanText(value),
                textAlign: TextAlign.right,
                style: const TextStyle(
                    fontSize: 12, fontWeight: FontWeight.w700))),
      ]),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.label});
  final String label;

  @override
  Widget build(BuildContext context) {
    final color = statusTone(label);
    return Container(
      constraints: const BoxConstraints(maxWidth: 90),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
      decoration: BoxDecoration(
          color: color.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(12)),
      child: Text(label,
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
          textAlign: TextAlign.center,
          style: TextStyle(
              color: color, fontSize: 9, fontWeight: FontWeight.w900)),
    );
  }
}

// ignore: unused_element
Future<void> _showRawWorkDetails(BuildContext context, WorkSummary work) async {
  final rows = work.details.entries
      .where((entry) => cleanText(entry.value, fallback: '') != '')
      .toList();
  await showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    backgroundColor: Theme.of(context).colorScheme.surface,
    barrierColor: Colors.black54,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(26)),
    ),
    builder: (context) {
      final colors = Theme.of(context).colorScheme;
      return Padding(
        padding: const EdgeInsets.fromLTRB(12, 20, 12, 12),
        child: Material(
          color: colors.surface,
          borderRadius: BorderRadius.circular(26),
          clipBehavior: Clip.antiAlias,
          child: SizedBox(
            height: MediaQuery.sizeOf(context).height * 0.82,
            child: Column(
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 20, 14, 16),
                  child: Row(
                    children: [
                      const Icon(Icons.engineering_rounded),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          work.name,
                          maxLines: 3,
                          overflow: TextOverflow.ellipsis,
                          style:
                              Theme.of(context).textTheme.titleLarge?.copyWith(
                                    fontWeight: FontWeight.w900,
                                  ),
                        ),
                      ),
                      IconButton(
                        tooltip: 'Close',
                        onPressed: () => Navigator.of(context).pop(),
                        icon: const Icon(Icons.close_rounded),
                      ),
                    ],
                  ),
                ),
                const Divider(height: 1),
                Expanded(
                  child: ListView.separated(
                    padding: const EdgeInsets.all(20),
                    itemCount: rows.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 14),
                    itemBuilder: (context, index) {
                      final row = rows[index];
                      return Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            _prettyKey(row.key),
                            style: TextStyle(
                              color: colors.onSurfaceVariant,
                              fontSize: 11,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          const SizedBox(height: 3),
                          Text(
                            cleanText(row.value),
                            style: const TextStyle(
                              fontSize: 13,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ],
                      );
                    },
                  ),
                ),
              ],
            ),
          ),
        ),
      );
    },
  );
}

String _prettyKey(String value) {
  final spaced = value
      .replaceAll('_', ' ')
      .replaceAll(RegExp(r'([a-z])([A-Z])'), r'$1 $2');
  return spaced.isEmpty
      ? value
      : '${spaced[0].toUpperCase()}${spaced.substring(1)}';
}
