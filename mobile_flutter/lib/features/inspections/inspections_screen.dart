import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/local/app_database.dart';
import '../../data/sync/sync_service.dart';
import '../../shared/widgets.dart';
import 'inspection_form_screen.dart';

class InspectionsScreen extends ConsumerStatefulWidget {
  const InspectionsScreen({super.key});

  @override
  ConsumerState<InspectionsScreen> createState() => _InspectionsScreenState();
}

class _InspectionsScreenState extends ConsumerState<InspectionsScreen> {
  late Future<List<Map<String, dynamic>>> _rows;
  final _searchController = TextEditingController();
  String _search = '';
  String _status = 'all';

  @override
  void initState() {
    super.initState();
    _rows = ref.read(databaseProvider).inspections();
  }

  void _reload() {
    setState(() => _rows = ref.read(databaseProvider).inspections());
    ref.read(syncControllerProvider.notifier).refreshPending();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _newInspection() async {
    final database = ref.read(databaseProvider);
    final stations = await database.stations();
    final templates = await database.templates();
    if (!mounted) return;
    if (stations.isEmpty || templates.isEmpty) {
      showAppNotice(
        context,
        message: 'Download station data before starting an inspection.',
        kind: AppNoticeKind.warning,
      );
      return;
    }
    final result = await showGlassBottomSheet<_InspectionSetup>(
      context,
      builder: (_) =>
          _NewInspectionSheet(stations: stations, templates: templates),
    );
    if (result == null) return;
    final id = await database.createInspection(
      stationCode: result.stationCode,
      templateId: result.templateId,
      inspectorName: result.inspectorName,
      inspectionType: result.inspectionType,
    );
    if (!mounted) return;
    await Navigator.of(context).push(
      appRoute(InspectionFormScreen(inspectionId: id)),
    );
    _reload();
  }

  @override
  Widget build(BuildContext context) {
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
              PageHeading(
                title: 'Inspections',
                subtitle: 'Drafts and submitted station inspections.',
                action: AppIconButton(
                  tooltip: 'New inspection',
                  onPressed: _newInspection,
                  icon: Icons.add_rounded,
                ),
              ),
              const SizedBox(height: AppSpacing.x2),
              AppSearchField(
                controller: _searchController,
                hint: 'Search station or inspector',
                onChanged: (value) =>
                    setState(() => _search = value.trim().toLowerCase()),
              ),
              const SizedBox(height: AppSpacing.x1),
              SizedBox(
                height: 40,
                child: ListView(
                  scrollDirection: Axis.horizontal,
                  children: [
                    for (final status in ['all', 'in_progress', 'submitted'])
                      Padding(
                        padding: const EdgeInsets.only(right: AppSpacing.x1),
                        child: GlassFilterChip(
                          selected: _status == status,
                          label: status == 'all'
                              ? 'All'
                              : status == 'in_progress'
                                  ? 'In progress'
                                  : 'Submitted',
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
                final matchesStatus =
                    _status == 'all' || row['status'] == _status;
                final haystack =
                    '${row['station_code']} ${row['inspector_name']} '
                            '${row['inspection_type']}'
                        .toLowerCase();
                return matchesStatus &&
                    (_search.isEmpty || haystack.contains(_search));
              }).toList();
              if (snapshot.connectionState == ConnectionState.waiting &&
                  rows.isEmpty) {
                return const GlassLoadingList();
              }
              if (source.isEmpty) {
                return EmptyState(
                  icon: Icons.fact_check_rounded,
                  title: 'No inspections yet',
                  message:
                      'Start an inspection and complete it even without a network.',
                  action: AppButton(
                    onPressed: _newInspection,
                    icon: Icons.add_rounded,
                    label: 'Start inspection',
                  ),
                );
              }
              if (rows.isEmpty) {
                return const EmptyState(
                  icon: Icons.search_off_rounded,
                  title: 'No matching inspections',
                  message: 'Try a different station, inspector or status.',
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
                  final submitted = row['status'] == 'submitted';
                  return GlassPanel(
                    semanticLabel: 'Open ${row['station_code']} inspection',
                    onTap: () async {
                      await Navigator.of(context).push(
                        appRoute(
                          InspectionFormScreen(
                            inspectionId: '${row['inspection_id']}',
                          ),
                        ),
                      );
                      _reload();
                    },
                    child: Row(
                      children: [
                        Container(
                          width: 48,
                          height: 48,
                          decoration: BoxDecoration(
                            color: submitted
                                ? const Color(0xFFD1FAE5)
                                : Theme.of(
                                    context,
                                  ).colorScheme.primaryContainer,
                            borderRadius: BorderRadius.circular(16),
                          ),
                          child: Icon(
                            submitted
                                ? Icons.check_rounded
                                : Icons.edit_note_rounded,
                            color: submitted
                                ? const Color(0xFF047857)
                                : Theme.of(context).colorScheme.primary,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Expanded(
                                    child: Text(
                                      '${row['station_code']} · '
                                      '${row['inspection_type']}',
                                      style: const TextStyle(
                                        fontWeight: FontWeight.w800,
                                      ),
                                    ),
                                  ),
                                  StatusBadge(
                                    '${row['status']}',
                                    tone: submitted
                                        ? const Color(0xFF047857)
                                        : null,
                                  ),
                                ],
                              ),
                              Text(
                                '${row['inspector_name']} · ${shortDate(row['started_at'])}',
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                              const SizedBox(height: 7),
                              Wrap(
                                spacing: 8,
                                runSpacing: 5,
                                children: [
                                  _InspectionCount(
                                    icon: Icons.checklist_rounded,
                                    value: '${row['response_count']} answers',
                                  ),
                                  _InspectionCount(
                                    icon: Icons.photo_outlined,
                                    value: '${row['evidence_count']} photos',
                                  ),
                                  _InspectionCount(
                                    icon: Icons.sticky_note_2_outlined,
                                    value: '${row['note_count']} notes',
                                  ),
                                  if ((row['open_finding_count'] as int? ?? 0) >
                                      0)
                                    _InspectionCount(
                                      icon: Icons.warning_amber_rounded,
                                      value:
                                          '${row['open_finding_count']} findings',
                                      tone: const Color(0xFFD97706),
                                    ),
                                ],
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
          ),
        ),
      ],
    );
  }
}

class _InspectionCount extends StatelessWidget {
  const _InspectionCount({
    required this.icon,
    required this.value,
    this.tone,
  });

  final IconData icon;
  final String value;
  final Color? tone;

  @override
  Widget build(BuildContext context) {
    final color = tone ?? Theme.of(context).colorScheme.onSurfaceVariant;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 14, color: color),
        const SizedBox(width: 3),
        Text(
          value,
          style: Theme.of(
            context,
          ).textTheme.labelSmall?.copyWith(color: color),
        ),
      ],
    );
  }
}

class _InspectionSetup {
  const _InspectionSetup({
    required this.stationCode,
    required this.templateId,
    required this.inspectorName,
    required this.inspectionType,
  });

  final String stationCode;
  final String templateId;
  final String inspectorName;
  final String inspectionType;
}

class _NewInspectionSheet extends StatefulWidget {
  const _NewInspectionSheet({required this.stations, required this.templates});

  final List<Map<String, dynamic>> stations;
  final List<Map<String, dynamic>> templates;

  @override
  State<_NewInspectionSheet> createState() => _NewInspectionSheetState();
}

class _NewInspectionSheetState extends State<_NewInspectionSheet> {
  final _inspector = TextEditingController();
  String? _stationCode;
  String? _templateId;
  String _type = 'scheduled';

  @override
  void dispose() {
    _inspector.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.fromLTRB(
        AppSpacing.page,
        AppSpacing.x1,
        AppSpacing.page,
        AppSpacing.x3 + MediaQuery.viewInsetsOf(context).bottom,
      ),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    color: Theme.of(context).colorScheme.primaryContainer,
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Icon(
                    Icons.fact_check_outlined,
                    color: Theme.of(context).colorScheme.onPrimaryContainer,
                  ),
                ),
                const SizedBox(width: AppSpacing.x2),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Start inspection',
                        style: Theme.of(
                          context,
                        ).textTheme.headlineSmall?.copyWith(
                              fontWeight: FontWeight.w800,
                            ),
                      ),
                      const Text('Choose the station and field checklist.'),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.x3),
            DropdownButtonFormField<String>(
              initialValue: _stationCode,
              isExpanded: true,
              decoration: const InputDecoration(labelText: 'Station'),
              items: [
                for (final station in widget.stations)
                  DropdownMenuItem(
                    value: '${station['station_code']}',
                    child: Text(
                      '${station['station_code']} · ${displayText(station['station_name'])}',
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
              ],
              onChanged: (value) => setState(() => _stationCode = value),
            ),
            const SizedBox(height: AppSpacing.x2),
            DropdownButtonFormField<String>(
              initialValue: _templateId,
              isExpanded: true,
              decoration: const InputDecoration(
                labelText: 'Inspection template',
              ),
              items: [
                for (final template in widget.templates)
                  DropdownMenuItem(
                    value: '${template['template_id']}',
                    child: Text(
                      '${template['name']}',
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
              ],
              onChanged: (value) => setState(() => _templateId = value),
            ),
            const SizedBox(height: AppSpacing.x2),
            TextField(
              controller: _inspector,
              textCapitalization: TextCapitalization.words,
              onChanged: (_) => setState(() {}),
              decoration: const InputDecoration(
                labelText: 'Inspector or officer name',
                prefixIcon: Icon(Icons.badge_outlined),
              ),
            ),
            const SizedBox(height: AppSpacing.x2),
            const SectionTitle(title: 'Inspection type'),
            const SizedBox(height: AppSpacing.x1),
            Wrap(
              spacing: AppSpacing.x1,
              runSpacing: AppSpacing.x1,
              children: [
                for (final type in ['scheduled', 'surprise', 'follow_up'])
                  GlassFilterChip(
                    selected: _type == type,
                    label: type == 'follow_up'
                        ? 'Follow-up'
                        : '${type[0].toUpperCase()}${type.substring(1)}',
                    onTap: () => setState(() => _type = type),
                  ),
              ],
            ),
            const SizedBox(height: AppSpacing.x3),
            AppButton(
              expand: true,
              onPressed: _stationCode == null ||
                      _templateId == null ||
                      _inspector.text.trim().isEmpty
                  ? null
                  : () => Navigator.pop(
                        context,
                        _InspectionSetup(
                          stationCode: _stationCode!,
                          templateId: _templateId!,
                          inspectorName: _inspector.text.trim(),
                          inspectionType: _type,
                        ),
                      ),
              icon: Icons.play_arrow_rounded,
              label: 'Begin inspection',
            ),
          ],
        ),
      ),
    );
  }
}
