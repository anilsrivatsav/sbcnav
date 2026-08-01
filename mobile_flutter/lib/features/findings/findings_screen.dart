import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/local/app_database.dart';
import '../../data/sync/sync_service.dart';
import '../../shared/widgets.dart';

class FindingsScreen extends ConsumerStatefulWidget {
  const FindingsScreen({super.key});

  @override
  ConsumerState<FindingsScreen> createState() => _FindingsScreenState();
}

class _FindingsScreenState extends ConsumerState<FindingsScreen> {
  late Future<List<Map<String, dynamic>>> _rows;
  final _searchController = TextEditingController();
  String _search = '';
  String _severity = 'all';

  @override
  void initState() {
    super.initState();
    _rows = ref.read(databaseProvider).findings();
  }

  void _reload() =>
      setState(() => _rows = ref.read(databaseProvider).findings());

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
                title: 'Reports',
                subtitle: 'Inspection observations needing corrective action.',
              ),
              const SizedBox(height: AppSpacing.x2),
              AppSearchField(
                controller: _searchController,
                hint: 'Search station, issue or owner',
                onChanged: (value) =>
                    setState(() => _search = value.trim().toLowerCase()),
              ),
              const SizedBox(height: AppSpacing.x1),
              SizedBox(
                height: 40,
                child: ListView(
                  scrollDirection: Axis.horizontal,
                  children: [
                    for (final severity in [
                      'all',
                      'critical',
                      'high',
                      'medium',
                      'low',
                    ])
                      Padding(
                        padding: const EdgeInsets.only(right: AppSpacing.x1),
                        child: GlassFilterChip(
                          selected: _severity == severity,
                          label: '${severity[0].toUpperCase()}'
                              '${severity.substring(1)}',
                          onTap: () => setState(() => _severity = severity),
                        ),
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
        Expanded(
          child: FutureBuilder<List<Map<String, dynamic>>>(
            future: _rows,
            builder: (context, snapshot) {
              final source = snapshot.data ?? const [];
              final rows = source.where((row) {
                final severityMatches =
                    _severity == 'all' || row['severity'] == _severity;
                final haystack = '${row['station_code']} ${row['title']} '
                        '${row['description']} ${row['responsible_party']}'
                    .toLowerCase();
                return severityMatches &&
                    (_search.isEmpty || haystack.contains(_search));
              }).toList();
              if (snapshot.connectionState == ConnectionState.waiting &&
                  rows.isEmpty) {
                return const GlassLoadingList();
              }
              if (source.isEmpty) {
                return const EmptyState(
                  icon: Icons.task_alt_rounded,
                  title: 'No findings',
                  message:
                      'Failed inspection items will appear here automatically.',
                );
              }
              if (rows.isEmpty) {
                return const EmptyState(
                  icon: Icons.search_off_rounded,
                  title: 'No matching findings',
                  message: 'Try a different station, issue or severity.',
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
                  final severity = '${row['severity']}';
                  final tone = switch (severity) {
                    'critical' => const Color(0xFFB91C1C),
                    'high' => const Color(0xFFEA580C),
                    'medium' => const Color(0xFFD97706),
                    _ => const Color(0xFF2563EB),
                  };
                  return GlassPanel(
                    semanticLabel:
                        '${row['severity']} finding at ${row['station_code']}',
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            StatusBadge('${row['station_code']}'),
                            const SizedBox(width: 7),
                            StatusBadge(severity, tone: tone),
                            const Spacer(),
                            StatusBadge('${row['status']}'),
                          ],
                        ),
                        const SizedBox(height: 10),
                        Text(
                          '${row['title']}',
                          style: Theme.of(context)
                              .textTheme
                              .titleMedium
                              ?.copyWith(fontWeight: FontWeight.w800),
                        ),
                        if (row['description'] != null) ...[
                          const SizedBox(height: 5),
                          Text('${row['description']}'),
                        ],
                        if ('${row['responsible_party'] ?? ''}'
                                .trim()
                                .isNotEmpty ||
                            '${row['target_date'] ?? ''}'
                                .trim()
                                .isNotEmpty) ...[
                          const SizedBox(height: 10),
                          Wrap(
                            spacing: 12,
                            runSpacing: 7,
                            children: [
                              if ('${row['responsible_party'] ?? ''}'
                                  .trim()
                                  .isNotEmpty)
                                _FindingMeta(
                                  icon: Icons.person_outline_rounded,
                                  text: '${row['responsible_party']}',
                                ),
                              if ('${row['target_date'] ?? ''}'
                                  .trim()
                                  .isNotEmpty)
                                _FindingMeta(
                                  icon: Icons.event_outlined,
                                  text: 'Due ${row['target_date']}',
                                ),
                              if (row['financial_implication'] != null)
                                _FindingMeta(
                                  icon: Icons.currency_rupee_rounded,
                                  text: '${row['financial_implication']}',
                                ),
                              if (row['repeat_observation'] == 1 ||
                                  row['repeat_observation'] == true)
                                const _FindingMeta(
                                  icon: Icons.repeat_rounded,
                                  text: 'Repeat observation',
                                ),
                            ],
                          ),
                        ],
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

class _FindingMeta extends StatelessWidget {
  const _FindingMeta({required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 16, color: Theme.of(context).colorScheme.primary),
        const SizedBox(width: 4),
        Text(text, style: Theme.of(context).textTheme.bodySmall),
      ],
    );
  }
}
