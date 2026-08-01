import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/local/app_database.dart';
import '../../data/sync/sync_service.dart';
import '../../shared/widgets.dart';
import 'station_360_screen.dart';
import 'station_presentation.dart';

class StationsScreen extends ConsumerStatefulWidget {
  const StationsScreen({super.key});

  @override
  ConsumerState<StationsScreen> createState() => _StationsScreenState();
}

class _StationsScreenState extends ConsumerState<StationsScreen> {
  String _search = '';
  final _searchController = TextEditingController();
  late Future<List<Map<String, dynamic>>> _stations;

  @override
  void initState() {
    super.initState();
    _stations = _load();
  }

  Future<List<Map<String, dynamic>>> _load() {
    return ref.read(databaseProvider).stationOverviewRows(search: _search);
  }

  void _reload() => setState(() => _stations = _load());

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    ref.listen(syncControllerProvider, (_, __) => _reload());
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(
            AppSpacing.page,
            AppSpacing.x3,
            AppSpacing.page,
            AppSpacing.x2,
          ),
          child: Column(
            children: [
              const PageHeading(
                title: 'Stations',
                subtitle: 'Passenger information, amenities and activity.',
              ),
              const SizedBox(height: AppSpacing.x2),
              AppSearchField(
                controller: _searchController,
                hint: 'Search code, name, division or section',
                onChanged: (value) {
                  _search = value;
                  _reload();
                },
              ),
            ],
          ),
        ),
        Expanded(
          child: FutureBuilder<List<Map<String, dynamic>>>(
            future: _stations,
            builder: (context, snapshot) {
              final rows = snapshot.data ?? const [];
              if (snapshot.connectionState == ConnectionState.waiting &&
                  rows.isEmpty) {
                return const GlassLoadingList();
              }
              if (rows.isEmpty) {
                return EmptyState(
                  icon: Icons.download_for_offline_rounded,
                  title: 'No stations on this device',
                  message:
                      'Download station data once, then it remains available offline.',
                  action: AppButton(
                    onPressed: () async {
                      await ref
                          .read(syncControllerProvider.notifier)
                          .bootstrap();
                      _reload();
                    },
                    icon: Icons.download_rounded,
                    label: 'Download stations',
                  ),
                );
              }
              return ListView.separated(
                padding: const EdgeInsets.fromLTRB(
                  AppSpacing.page,
                  AppSpacing.x1,
                  AppSpacing.page,
                  AppSpacing.x4,
                ),
                itemCount: rows.length,
                separatorBuilder: (_, __) =>
                    const SizedBox(height: AppSpacing.x2),
                itemBuilder: (context, index) {
                  final row = rows[index];
                  final detail = row['_station_detail'] is Map
                      ? Map<String, dynamic>.from(
                          row['_station_detail'] as Map,
                        )
                      : null;
                  final station = stationCardData(row, detail);
                  return GlassPanel(
                    semanticLabel:
                        'Open full station details for ${station.code}',
                    onTap: () => showModalBottomSheet<void>(
                      context: context,
                      isScrollControlled: true,
                      useSafeArea: true,
                      backgroundColor: Colors.transparent,
                      builder: (_) => StationDetailBottomSheet(
                        stationCode: station.code,
                      ),
                    ),
                    padding: const EdgeInsets.all(AppSpacing.x2),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.center,
                      children: [
                        Hero(
                          tag: 'station-${station.code}',
                          child: Material(
                            color: Colors.transparent,
                            child: Container(
                              width: 50,
                              height: 34,
                              alignment: Alignment.center,
                              decoration: BoxDecoration(
                                color: const Color(0xFFEDE4FF),
                                borderRadius: BorderRadius.circular(14),
                              ),
                              child: FittedBox(
                                fit: BoxFit.scaleDown,
                                child: Padding(
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: 5,
                                  ),
                                  child: Text(
                                    station.code,
                                    style: TextStyle(
                                      color:
                                          Theme.of(context).colorScheme.primary,
                                      fontSize: 12,
                                      fontWeight: FontWeight.w900,
                                    ),
                                  ),
                                ),
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(width: 13),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                station.name,
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                                style: Theme.of(context)
                                    .textTheme
                                    .titleMedium
                                    ?.copyWith(fontWeight: FontWeight.w900),
                              ),
                              const SizedBox(height: 7),
                              Row(
                                children: [
                                  Flexible(
                                    child: Text(
                                      station.section,
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                      style:
                                          Theme.of(context).textTheme.bodySmall,
                                    ),
                                  ),
                                  Container(
                                    width: 3,
                                    height: 3,
                                    margin: const EdgeInsets.symmetric(
                                      horizontal: 8,
                                    ),
                                    decoration: BoxDecoration(
                                      color:
                                          Theme.of(context).colorScheme.outline,
                                      shape: BoxShape.circle,
                                    ),
                                  ),
                                  Icon(
                                    Icons.groups_2_rounded,
                                    size: 15,
                                    color:
                                        Theme.of(context).colorScheme.tertiary,
                                  ),
                                  const SizedBox(width: 4),
                                  Text(
                                    station.dailyFootfall,
                                    style: TextStyle(
                                      color: Theme.of(context)
                                          .colorScheme
                                          .tertiary,
                                      fontSize: 12,
                                      fontWeight: FontWeight.w900,
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 7),
                              Wrap(
                                spacing: 6,
                                runSpacing: 5,
                                children: [
                                  StatusBadge(station.category),
                                  if (station.abssFlag)
                                    const _ProgramBadge(label: 'ABSS'),
                                  if (station.redevelopmentFlag)
                                    const _ProgramBadge(label: 'Redevelopment'),
                                ],
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(width: AppSpacing.x1),
                        Icon(
                          Icons.chevron_right_rounded,
                          size: 19,
                          color: Theme.of(context)
                              .colorScheme
                              .onSurfaceVariant
                              .withValues(alpha: 0.52),
                        ),
                      ],
                    ),
                  );
                },
              );
            },
          ),
        ),
      ],
    );
  }
}

class _ProgramBadge extends StatelessWidget {
  const _ProgramBadge({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
      decoration: BoxDecoration(
        color: const Color(0xFFEDE4FF),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: Theme.of(context).colorScheme.primary,
          fontSize: 10,
          fontWeight: FontWeight.w900,
        ),
      ),
    );
  }
}
