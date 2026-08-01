import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/local/app_database.dart';
import '../../data/remote/mobile_api.dart';
import '../../shared/widgets.dart';
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

class _StationProfile extends StatelessWidget {
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
  Widget build(BuildContext context) {
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
    final amenityGroups = buildAmenityCategories(station, amenities);
    final fobAccess = _fobAccessModes(amenities);
    final code = cleanText(station['station_code'], fallback: fallbackCode);
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

    return CustomScrollView(
      slivers: [
        SliverAppBar(
          expandedHeight: 300,
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
              onTap: onRefresh,
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
                  _StationDetails(station: station, amenities: amenities),
                  const SizedBox(height: 24),
                  _SectionHeading(
                    title: 'Passenger amenities',
                    count: amenityGroups.values
                        .fold<int>(0, (sum, rows) => sum + rows.length),
                  ),
                  const SizedBox(height: 12),
                  _AmenityGrid(groups: amenityGroups),
                  if (fobAccess.isNotEmpty) ...[
                    const SizedBox(height: 16),
                    _FobAccessCard(modes: fobAccess),
                  ],
                  if (norms.isNotEmpty) ...[
                    const SizedBox(height: 16),
                    _NormsCard(norms: norms),
                  ],
                  const SizedBox(height: 25),
                  _SectionHeading(
                    title: 'Platforms',
                    count: totalPlatforms,
                  ),
                  const SizedBox(height: 12),
                  _PlatformList(
                    platforms: platforms,
                    stationLevel: station['platform_type'],
                  ),
                  const SizedBox(height: 25),
                  if (contracts.isNotEmpty) ...[
                    _SectionHeading(
                      title: 'Contracts',
                      count: contracts.length,
                    ),
                    const SizedBox(height: 12),
                    _ContractList(contracts: contracts),
                    const SizedBox(height: 25),
                  ],
                  if (works.isNotEmpty) ...[
                    _SectionHeading(
                      title: 'Sanctioned works',
                      count: works.length,
                    ),
                    const SizedBox(height: 12),
                    _WorkList(works: works),
                  ],
                  const SizedBox(height: 26),
                  SizedBox(
                    width: double.infinity,
                    height: 58,
                    child: FilledButton.icon(
                      onPressed: () => onStartInspection(code),
                      icon: const Icon(Icons.fact_check_outlined),
                      label: const Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Text(
                            'Start inspection',
                            style: TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w900,
                            ),
                          ),
                          SizedBox(width: 12),
                          Icon(Icons.arrow_forward_rounded),
                        ],
                      ),
                      style: FilledButton.styleFrom(
                        backgroundColor: const Color(0xFF1C54C7),
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(17),
                        ),
                        elevation: 5,
                        shadowColor:
                            const Color(0xFF1C54C7).withValues(alpha: 0.35),
                      ),
                    ),
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
        ],
      ),
    );
  }
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

class _AmenityGrid extends StatelessWidget {
  const _AmenityGrid({required this.groups});

  final Map<String, List<AmenityItem>> groups;

  @override
  Widget build(BuildContext context) {
    final items = <({String category, AmenityItem item})>[
      for (final entry in groups.entries)
        for (final item in entry.value) (category: entry.key, item: item),
    ];
    if (items.isEmpty) {
      return const _EmptySection(
        icon: Icons.chair_alt_outlined,
        text: 'Amenity details are not available offline yet.',
      );
    }
    return LayoutBuilder(
      builder: (context, constraints) {
        final columns = constraints.maxWidth >= 720 ? 4 : 2;
        return GridView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          itemCount: items.length,
          gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: columns,
            crossAxisSpacing: 10,
            mainAxisSpacing: 10,
            childAspectRatio: 1.72,
          ),
          itemBuilder: (context, index) {
            final entry = items[index];
            final visual = _amenityVisual(entry.item.label, entry.category);
            return Container(
              padding: const EdgeInsets.all(12),
              decoration: _softCard(context, radius: 18),
              child: Row(
                children: [
                  Container(
                    width: 38,
                    height: 38,
                    decoration: BoxDecoration(
                      color: visual.$2.withValues(alpha: 0.11),
                      shape: BoxShape.circle,
                    ),
                    child: Icon(visual.$1, color: visual.$2, size: 20),
                  ),
                  const SizedBox(width: 9),
                  Expanded(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          entry.item.label,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                        if (entry.item.quantity != null)
                          Text(
                            '${entry.item.quantity} available',
                            style: TextStyle(
                              color: visual.$2,
                              fontSize: 11,
                              fontWeight: FontWeight.w900,
                            ),
                          ),
                      ],
                    ),
                  ),
                ],
              ),
            );
          },
        );
      },
    );
  }
}

class _FobAccessCard extends StatelessWidget {
  const _FobAccessCard({required this.modes});

  final List<String> modes;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: _softCard(context, radius: 22),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: const Color(0xFFE4F7F2),
              borderRadius: BorderRadius.circular(14),
            ),
            child: const Icon(Icons.stairs_outlined, color: Color(0xFF149A83)),
          ),
          const SizedBox(width: 11),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('FOB access',
                    style: TextStyle(fontWeight: FontWeight.w900)),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    for (final mode in modes)
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 9, vertical: 6),
                        decoration: BoxDecoration(
                          color: const Color(0xFFE4F7F2),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Text(mode,
                            style: const TextStyle(
                                color: Color(0xFF147D6D),
                                fontSize: 10,
                                fontWeight: FontWeight.w900)),
                      ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _NormsCard extends StatefulWidget {
  const _NormsCard({required this.norms});

  final List<dynamic> norms;

  @override
  State<_NormsCard> createState() => _NormsCardState();
}

class _NormsCardState extends State<_NormsCard> {
  var _expanded = false;

  @override
  Widget build(BuildContext context) {
    final groups = <String, List<Map<String, dynamic>>>{
      'MEA': [],
      'Recommended': [],
      'Desirable': [],
      'Divyangjan': [],
    };
    for (final raw in widget.norms) {
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
                      : null;
      if (heading != null) groups[heading]!.add(row);
    }
    final visibleGroups =
        groups.entries.where((entry) => entry.value.isNotEmpty).toList();
    return Container(
      decoration: _softCard(context, radius: 22),
      child: Column(
        children: [
          InkWell(
            onTap: () => setState(() => _expanded = !_expanded),
            borderRadius: BorderRadius.circular(22),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 14, 14, 14),
              child: Row(
                children: [
                  Container(
                    width: 38,
                    height: 38,
                    decoration: BoxDecoration(
                      color: const Color(0xFFEDE4FF),
                      borderRadius: BorderRadius.circular(13),
                    ),
                    child: const Icon(Icons.rule_rounded,
                        color: Color(0xFF7650C9), size: 20),
                  ),
                  const SizedBox(width: 11),
                  const Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Passenger amenities norms',
                            style: TextStyle(fontWeight: FontWeight.w900)),
                        SizedBox(height: 3),
                        Text('Based on this station category',
                            style: TextStyle(fontSize: 11)),
                      ],
                    ),
                  ),
                  Text('${widget.norms.length}',
                      style: TextStyle(
                          color: Theme.of(context).colorScheme.primary,
                          fontWeight: FontWeight.w900)),
                  const SizedBox(width: 6),
                  Icon(_expanded
                      ? Icons.keyboard_arrow_up_rounded
                      : Icons.keyboard_arrow_down_rounded),
                ],
              ),
            ),
          ),
          if (_expanded)
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 0, 14, 14),
              child: Column(
                children: [
                  for (var index = 0; index < visibleGroups.length; index++) ...[
                    if (index > 0) const Divider(height: 22),
                    _NormGroup(
                      title: visibleGroups[index].key,
                      rows: visibleGroups[index].value,
                    ),
                  ],
                ],
              ),
            ),
        ],
      ),
    );
  }
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
                style: TextStyle(color: color.withValues(alpha: 0.72), fontSize: 11)),
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
                  child: Text(cleanText(row['norm'], fallback: 'Norm not recorded'),
                      style: const TextStyle(fontSize: 12, height: 1.25)),
                ),
                if (cleanText(row['norm_quantity']).isNotEmpty) ...[
                  const SizedBox(width: 8),
                  Container(
                    constraints: const BoxConstraints(maxWidth: 130),
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: color.withValues(alpha: 0.08),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(cleanText(row['norm_quantity']),
                        textAlign: TextAlign.right,
                        style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.w900)),
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
              subtitle:
                  '${contract.type}  •  ${formatCurrency(contract.earnings)}',
              trailing: contract.status,
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
    'policy',
    'sub_category',
    'allocation',
    'station',
    'contract_period',
    'contract_upto',
    'license_fee',
    'annual_license_fee',
    'total_license_fee_2026_2027',
  ];
  final details = <MapEntry<String, dynamic>>[];
  for (final key in detailKeys) {
    final value = contract.details[key];
    if (_hasDetailValue(value)) details.add(MapEntry(key, value));
  }
  await _showDetailSheet(
    context,
    title: contract.name,
    icon: Icons.storefront_rounded,
    status: contract.status,
    sections: [
      _DetailGroup(title: 'Contract summary', rows: [
        MapEntry('Type', contract.type),
        MapEntry('Earnings / license fee', formatCurrency(contract.earnings)),
        MapEntry('Validity', contractValidityLabel(contract)),
        if (contract.validFrom != null)
          MapEntry('Valid from', formatContractDate(contract.validFrom!)),
        if (contract.validTo != null)
          MapEntry('Valid till', formatContractDate(contract.validTo!)),
      ]),
      if (details.isNotEmpty)
        _DetailGroup(
            title: 'Contract information',
            rows: details
                .map((e) => MapEntry(_prettyKey(e.key), e.value))
                .toList()),
      _DetailGroup(
        title: 'Payments so far',
        rows: contract.payments.isEmpty
            ? const [
                MapEntry('Payment history', 'No payment records available')
              ]
            : [
                for (var i = 0; i < contract.payments.length; i++)
                  MapEntry('Payment ${i + 1}',
                      _paymentSummary(contract.payments[i])),
              ],
      ),
    ],
  );
}

String _paymentSummary(Map<String, dynamic> payment) {
  final date = payment['date'] ?? payment['receipt_date'] ?? payment['month'];
  final amount =
      payment['amount'] ?? payment['paid_amount'] ?? payment['earnings'];
  final status = payment['status'] ?? payment['payment_status'];
  return [
    if (_hasDetailValue(date)) cleanText(date),
    if (_hasDetailValue(amount)) cleanText(amount),
    if (_hasDetailValue(status)) cleanText(status),
  ].join('  |  ');
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

bool _internalDetailKey(String key) =>
    key == 'source_hash' ||
    key == 'created_at' ||
    key == 'updated_at' ||
    key == 'is_active';

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
    backgroundColor: Colors.transparent,
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
    backgroundColor: Colors.transparent,
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
