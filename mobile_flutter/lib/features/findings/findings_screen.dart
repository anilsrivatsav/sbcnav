import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/local/app_database.dart';
import '../../data/sync/sync_service.dart';
import '../../shared/widgets.dart';

class FindingsScreen extends ConsumerStatefulWidget {
  const FindingsScreen({this.embedded = false, super.key});

  final bool embedded;

  @override
  ConsumerState<FindingsScreen> createState() => _FindingsScreenState();
}

class _FindingsScreenState extends ConsumerState<FindingsScreen> {
  late Future<List<Map<String, dynamic>>> _rows;
  final _searchController = TextEditingController();
  String _search = '';
  String _severity = 'all';
  String _status = 'active';

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
            AppSpacing.x1,
            AppSpacing.page,
            AppSpacing.x2,
          ),
          child: Column(
            children: [
              if (!widget.embedded) ...[
                const PageHeading(
                  title: 'Deficiencies',
                  subtitle:
                      'Assign, track, verify and close inspection issues.',
                ),
                const SizedBox(height: AppSpacing.x2),
              ],
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
              const SizedBox(height: AppSpacing.x1),
              SizedBox(
                height: 40,
                child: ListView(
                  scrollDirection: Axis.horizontal,
                  children: [
                    for (final status in [
                      'active',
                      'verification_due',
                      'verified',
                      'closed',
                      'all',
                    ])
                      Padding(
                        padding: const EdgeInsets.only(right: AppSpacing.x1),
                        child: GlassFilterChip(
                          selected: _status == status,
                          label: _statusLabel(status),
                          onTap: () => setState(() => _status = status),
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
                final rowStatus = '${row['status']}';
                final statusMatches = _status == 'all' ||
                    (_status == 'active'
                        ? rowStatus != 'verified' && rowStatus != 'closed'
                        : rowStatus == _status);
                final haystack = '${row['station_code']} ${row['title']} '
                        '${row['description']} ${row['responsible_party']}'
                    .toLowerCase();
                return severityMatches &&
                    statusMatches &&
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
                  return GestureDetector(
                    behavior: HitTestBehavior.opaque,
                    onTap: () async {
                      final changed = await showFindingEditor(
                        context,
                        ref,
                        row,
                      );
                      if (changed) _reload();
                    },
                    child: GlassPanel(
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
                              StatusBadge(_statusLabel('${row['status']}')),
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
                                    text: _dueLabel(row['target_date']),
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
                          const SizedBox(height: 10),
                          Row(
                            children: [
                              Text(
                                'Open details',
                                style: Theme.of(context)
                                    .textTheme
                                    .labelMedium
                                    ?.copyWith(fontWeight: FontWeight.w900),
                              ),
                              const Spacer(),
                              const Icon(Icons.chevron_right_rounded, size: 20),
                            ],
                          ),
                        ],
                      ),
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

Future<bool> showFindingEditor(
  BuildContext context,
  WidgetRef ref,
  Map<String, dynamic> row,
) async {
  final owner =
      TextEditingController(text: '${row['responsible_party'] ?? ''}');
  final target = TextEditingController(text: '${row['target_date'] ?? ''}');
  final formKey = GlobalKey<FormState>();
  var status = '${row['status'] ?? 'open'}';
  var saving = false;
  final changed = await showModalBottomSheet<bool>(
        context: context,
        isScrollControlled: true,
        useSafeArea: true,
        backgroundColor: Colors.transparent,
        builder: (sheetContext) => StatefulBuilder(
          builder: (context, setSheetState) => Container(
            padding: EdgeInsets.fromLTRB(
              20,
              12,
              20,
              20 + MediaQuery.viewInsetsOf(context).bottom,
            ),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surface,
              borderRadius:
                  const BorderRadius.vertical(top: Radius.circular(26)),
            ),
            child: Form(
              key: formKey,
              child: SingleChildScrollView(
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
                          borderRadius: BorderRadius.circular(4),
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),
                    Row(
                      children: [
                        StatusBadge('${row['station_code']}'),
                        const SizedBox(width: 8),
                        StatusBadge('${row['severity']}'),
                      ],
                    ),
                    const SizedBox(height: 10),
                    Text(
                      '${row['title']}',
                      style: Theme.of(context)
                          .textTheme
                          .titleLarge
                          ?.copyWith(fontWeight: FontWeight.w900),
                    ),
                    if ('${row['description'] ?? ''}'.trim().isNotEmpty) ...[
                      const SizedBox(height: 6),
                      Text('${row['description']}'),
                    ],
                    const SizedBox(height: 18),
                    DropdownButtonFormField<String>(
                      initialValue: status,
                      dropdownColor: Theme.of(context).colorScheme.surface,
                      decoration: _fieldDecoration(context, 'Status'),
                      items: const [
                        'open',
                        'assigned',
                        'action_taken',
                        'verification_due',
                        'returned',
                        'verified',
                        'closed',
                      ]
                          .map(
                            (value) => DropdownMenuItem(
                              value: value,
                              child: Text(_statusLabel(value)),
                            ),
                          )
                          .toList(),
                      onChanged: (value) {
                        if (value != null) {
                          setSheetState(() => status = value);
                        }
                      },
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: owner,
                      decoration: _fieldDecoration(
                        context,
                        'Responsible officer / department',
                      ),
                      validator: (value) {
                        if (status == 'assigned' &&
                            (value == null || value.trim().isEmpty)) {
                          return 'Add the responsible officer or department';
                        }
                        return null;
                      },
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: target,
                      readOnly: true,
                      decoration: _fieldDecoration(
                        context,
                        'Target date',
                        suffixIcon: Icons.calendar_today_rounded,
                      ),
                      onTap: () async {
                        final initial = DateTime.tryParse(target.text) ??
                            DateTime.now().add(const Duration(days: 7));
                        final selected = await showDatePicker(
                          context: context,
                          initialDate: initial,
                          firstDate: DateTime.now()
                              .subtract(const Duration(days: 365)),
                          lastDate:
                              DateTime.now().add(const Duration(days: 3650)),
                        );
                        if (selected != null) {
                          target.text =
                              selected.toIso8601String().split('T').first;
                        }
                      },
                    ),
                    const SizedBox(height: 18),
                    AppButton(
                      expand: true,
                      loading: saving,
                      onPressed: saving
                          ? null
                          : () async {
                              if (formKey.currentState?.validate() != true) {
                                return;
                              }
                              setSheetState(() => saving = true);
                              try {
                                await ref
                                    .read(databaseProvider)
                                    .updateFindingLifecycle(
                                      findingId: '${row['finding_id']}',
                                      status: status,
                                      responsibleParty: owner.text,
                                      targetDate: target.text,
                                    );
                                await ref
                                    .read(syncControllerProvider.notifier)
                                    .refreshPending();
                                if (sheetContext.mounted) {
                                  Navigator.of(sheetContext).pop(true);
                                }
                              } catch (error) {
                                if (!sheetContext.mounted) return;
                                setSheetState(() => saving = false);
                                ScaffoldMessenger.of(sheetContext).showSnackBar(
                                  SnackBar(
                                    content: Text('Could not save: $error'),
                                  ),
                                );
                              }
                            },
                      icon: Icons.save_outlined,
                      label: 'Save deficiency',
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ) ??
      false;
  owner.dispose();
  target.dispose();
  return changed;
}

InputDecoration _fieldDecoration(
  BuildContext context,
  String label, {
  IconData? suffixIcon,
}) {
  return InputDecoration(
    labelText: label,
    filled: true,
    fillColor: Theme.of(context).colorScheme.surfaceContainerHighest,
    suffixIcon: suffixIcon == null ? null : Icon(suffixIcon),
    border: OutlineInputBorder(borderRadius: BorderRadius.circular(16)),
  );
}

String _statusLabel(String value) {
  if (value == 'active') return 'Active';
  return value
      .split('_')
      .map((part) =>
          part.isEmpty ? part : '${part[0].toUpperCase()}${part.substring(1)}')
      .join(' ');
}

String _dueLabel(Object? value) {
  final text = '${value ?? ''}'.trim();
  final date = DateTime.tryParse(text);
  if (date == null) return 'Due $text';
  final now = DateTime.now();
  final today = DateTime(now.year, now.month, now.day);
  final due = DateTime(date.year, date.month, date.day);
  final days = due.difference(today).inDays;
  if (days < 0) return 'Overdue by ${-days}d';
  if (days == 0) return 'Due today';
  return 'Due in ${days}d';
}
