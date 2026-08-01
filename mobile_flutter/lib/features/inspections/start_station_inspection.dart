import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/local/app_database.dart';
import '../../shared/widgets.dart';
import 'inspection_form_screen.dart';

Future<bool> startStationInspection(
  BuildContext context,
  WidgetRef ref, {
  required String stationCode,
}) async {
  final database = ref.read(databaseProvider);
  final templates = await database.templates();
  if (!context.mounted) return false;
  if (templates.isEmpty) {
    showAppNotice(
      context,
      message: 'Download inspection templates before starting.',
      kind: AppNoticeKind.warning,
    );
    return false;
  }

  final setup = await showModalBottomSheet<_StationInspectionSetup>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    backgroundColor: Colors.transparent,
    builder: (_) => _StationInspectionSheet(
      stationCode: stationCode,
      templates: templates,
    ),
  );
  if (setup == null || !context.mounted) return false;

  final id = await database.createInspection(
    stationCode: stationCode,
    templateId: setup.templateId,
    inspectorName: setup.inspectorName,
    inspectionType: setup.inspectionType,
  );
  if (!context.mounted) return false;
  await Navigator.of(context).push(
    appRoute(InspectionFormScreen(inspectionId: id)),
  );
  return true;
}

class _StationInspectionSetup {
  const _StationInspectionSetup({
    required this.templateId,
    required this.inspectorName,
    required this.inspectionType,
  });

  final String templateId;
  final String inspectorName;
  final String inspectionType;
}

class _StationInspectionSheet extends StatefulWidget {
  const _StationInspectionSheet({
    required this.stationCode,
    required this.templates,
  });

  final String stationCode;
  final List<Map<String, dynamic>> templates;

  @override
  State<_StationInspectionSheet> createState() =>
      _StationInspectionSheetState();
}

class _StationInspectionSheetState extends State<_StationInspectionSheet> {
  final _inspector = TextEditingController();
  late String _templateId;
  String _type = 'scheduled';

  @override
  void initState() {
    super.initState();
    _templateId = '${widget.templates.first['template_id']}';
  }

  @override
  void dispose() {
    _inspector.dispose();
    super.dispose();
  }

  void _continue() {
    final name = _inspector.text.trim();
    if (name.isEmpty) {
      showAppNotice(
        context,
        message: 'Enter the inspector name.',
        kind: AppNoticeKind.warning,
      );
      return;
    }
    Navigator.of(context).pop(
      _StationInspectionSetup(
        templateId: _templateId,
        inspectorName: name,
        inspectionType: _type,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Padding(
      padding: EdgeInsets.only(
        left: 16,
        right: 16,
        bottom: MediaQuery.viewInsetsOf(context).bottom + 16,
      ),
      child: Material(
        color: colors.surface,
        borderRadius: BorderRadius.circular(28),
        clipBehavior: Clip.antiAlias,
        child: Padding(
          padding: const EdgeInsets.all(22),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 42,
                  height: 4,
                  decoration: BoxDecoration(
                    color: colors.outlineVariant,
                    borderRadius: BorderRadius.circular(4),
                  ),
                ),
              ),
              const SizedBox(height: 20),
              Text(
                'Inspect ${widget.stationCode}',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(height: 5),
              Text(
                'The inspection is saved offline until you synchronize.',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: colors.onSurfaceVariant,
                    ),
              ),
              const SizedBox(height: 20),
              DropdownButtonFormField<String>(
                initialValue: _templateId,
                decoration: const InputDecoration(
                  labelText: 'Inspection template',
                  prefixIcon: Icon(Icons.assignment_outlined),
                ),
                items: [
                  for (final template in widget.templates)
                    DropdownMenuItem(
                      value: '${template['template_id']}',
                      child: Text(
                        '${template['name'] ?? template['template_id']}',
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                ],
                onChanged: (value) {
                  if (value != null) setState(() => _templateId = value);
                },
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _inspector,
                textCapitalization: TextCapitalization.words,
                decoration: const InputDecoration(
                  labelText: 'Inspector name',
                  prefixIcon: Icon(Icons.person_outline_rounded),
                ),
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                initialValue: _type,
                decoration: const InputDecoration(
                  labelText: 'Visit type',
                  prefixIcon: Icon(Icons.route_outlined),
                ),
                items: const [
                  DropdownMenuItem(
                    value: 'scheduled',
                    child: Text('Scheduled inspection'),
                  ),
                  DropdownMenuItem(
                    value: 'surprise',
                    child: Text('Surprise inspection'),
                  ),
                  DropdownMenuItem(
                    value: 'follow_up',
                    child: Text('Follow-up inspection'),
                  ),
                ],
                onChanged: (value) {
                  if (value != null) setState(() => _type = value);
                },
              ),
              const SizedBox(height: 20),
              AppButton(
                expand: true,
                onPressed: _continue,
                icon: Icons.arrow_forward_rounded,
                label: 'Start inspection',
              ),
            ],
          ),
        ),
      ),
    );
  }
}
