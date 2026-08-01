import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/local/app_database.dart';
import '../../data/sync/sync_service.dart';
import '../../shared/widgets.dart';
import 'inspection_field_log.dart';
import 'inspection_logic.dart';
import 'inspection_review_sheet.dart';

class InspectionFormScreen extends ConsumerStatefulWidget {
  const InspectionFormScreen({required this.inspectionId, super.key});

  final String inspectionId;

  @override
  ConsumerState<InspectionFormScreen> createState() =>
      _InspectionFormScreenState();
}

class _InspectionFormState {
  const _InspectionFormState({
    required this.inspection,
    required this.template,
    required this.responses,
    required this.findings,
    required this.evidence,
    required this.notes,
  });

  final Map<String, dynamic> inspection;
  final Map<String, dynamic> template;
  final Map<String, Map<String, dynamic>> responses;
  final List<Map<String, dynamic>> findings;
  final List<Map<String, dynamic>> evidence;
  final List<Map<String, dynamic>> notes;
}

class _InspectionFormScreenState extends ConsumerState<InspectionFormScreen> {
  late Future<_InspectionFormState> _state;
  int _sectionIndex = 0;

  @override
  void initState() {
    super.initState();
    _state = _load();
    WidgetsBinding.instance.addPostFrameCallback((_) => _recoverLostPhotos());
  }

  Future<void> _recoverLostPhotos() async {
    try {
      final count = await InspectionFieldActions.recoverLostEvidence(
        database: ref.read(databaseProvider),
        inspectionId: widget.inspectionId,
      );
      if (count == 0 || !mounted) return;
      await ref.read(syncControllerProvider.notifier).refreshPending();
      if (!mounted) return;
      _reload();
      showAppNotice(
        context,
        message: '$count interrupted photo${count == 1 ? '' : 's'} recovered.',
        kind: AppNoticeKind.success,
      );
    } catch (_) {
      // Recovery is best-effort; normal inspection loading must continue.
    }
  }

  Future<_InspectionFormState> _load() async {
    final database = ref.read(databaseProvider);
    final inspection = await database.inspection(widget.inspectionId);
    if (inspection == null) {
      throw StateError('Inspection is no longer available');
    }
    final template = await database.template('${inspection['template_id']}');
    if (template == null) {
      throw StateError('Inspection template is not available offline');
    }
    final rows = await database.responses(widget.inspectionId);
    final findings = await database.findingsForInspection(widget.inspectionId);
    final evidence = await database.evidenceForInspection(widget.inspectionId);
    final notes = await database.notesForInspection(widget.inspectionId);
    return _InspectionFormState(
      inspection: inspection,
      template: template,
      responses: {for (final row in rows) '${row['question_code']}': row},
      findings: findings,
      evidence: evidence,
      notes: notes,
    );
  }

  void _reload() => setState(() => _state = _load());

  Future<void> _addPhoto({
    required _InspectionFormState state,
    required String sectionCode,
    Map<String, dynamic>? question,
  }) async {
    final response =
        question == null ? null : state.responses['${question['code']}'];
    final added = await InspectionFieldActions.captureEvidence(
      context: context,
      database: ref.read(databaseProvider),
      inspectionId: widget.inspectionId,
      responseId: response?['response_id'] as String?,
      questionCode: question == null ? null : '${question['code']}',
      defaultContext:
          question == null ? sectionCode : '$sectionCode | ${question['text']}',
    );
    if (!added) return;
    await ref.read(syncControllerProvider.notifier).refreshPending();
    _reload();
  }

  Future<void> _addNote({
    required String sectionCode,
    Map<String, dynamic>? question,
  }) async {
    final added = await InspectionFieldActions.addNote(
      context: context,
      database: ref.read(databaseProvider),
      inspectionId: widget.inspectionId,
      sectionCode: sectionCode,
      questionCode: question == null ? null : '${question['code']}',
      defaultContext:
          question == null ? sectionCode : '$sectionCode | ${question['text']}',
    );
    if (!added) return;
    await ref.read(syncControllerProvider.notifier).refreshPending();
    _reload();
  }

  Future<void> _showFieldLog(_InspectionFormState state) {
    return showGlassBottomSheet<void>(
      context,
      builder: (_) => FractionallySizedBox(
        heightFactor: 0.94,
        child: InspectionFieldLog(
          evidence: state.evidence,
          notes: state.notes,
        ),
      ),
    );
  }

  Future<void> _answer({
    required _InspectionFormState state,
    required String sectionCode,
    required Map<String, dynamic> question,
    required String value,
  }) async {
    String? remarks;
    String? severity;
    String? platform;
    String? responsibleParty;
    String? targetDate;
    int? financialImplication;
    var repeatObservation = false;
    final existingResponse = state.responses['${question['code']}'];
    if (value == 'fail') {
      Map<String, dynamic>? existingFinding;
      for (final finding in state.findings) {
        if ('${finding['response_id']}' ==
            '${existingResponse?['response_id']}') {
          existingFinding = finding;
          break;
        }
      }
      final detail = await showDialog<_FindingDetail>(
        context: context,
        builder: (_) => _FindingDialog(
          question: '${question['text']}',
          initialFinding: existingFinding,
          initialPlatform: '${existingResponse?['platform'] ?? ''}',
        ),
      );
      if (detail == null) return;
      remarks = detail.description;
      severity = detail.severity;
      platform = detail.platform;
      responsibleParty = detail.responsibleParty;
      targetDate = detail.targetDate;
      financialImplication = detail.financialImplication;
      repeatObservation = detail.repeatObservation;
    }
    final database = ref.read(databaseProvider);
    final responseId = await database.saveResponse(
      inspectionId: widget.inspectionId,
      sectionCode: sectionCode,
      questionCode: '${question['code']}',
      value: value,
      remarks: remarks,
      severity: severity,
      platform: platform,
    );
    if (value == 'fail') {
      await database.createFinding(
        inspectionId: widget.inspectionId,
        responseId: responseId,
        stationCode: '${state.inspection['station_code']}',
        title: '${question['text']}',
        description: remarks!,
        severity: severity!,
        responsibleParty: responsibleParty,
        targetDate: targetDate,
        financialImplication: financialImplication,
        repeatObservation: repeatObservation,
      );
    } else {
      await database.resolveFindingForResponse(responseId);
    }
    await ref.read(syncControllerProvider.notifier).refreshPending();
    _reload();
  }

  Future<void> _review(
    _InspectionFormState state,
    List<dynamic> sections,
  ) async {
    final result = await showGlassBottomSheet<InspectionReviewResult>(
      context,
      builder: (_) => FractionallySizedBox(
        heightFactor: 0.94,
        child: InspectionReviewSheet(
          sections: sections,
          responses: state.responses,
          findings: state.findings,
          evidenceCount: state.evidence.length,
          noteCount: state.notes.length,
          initialRemarks: '${state.inspection['remarks'] ?? ''}',
        ),
      ),
    );
    if (result == null) return;
    if (!result.shouldSubmit) {
      setState(() => _sectionIndex = result.sectionIndex ?? 0);
      return;
    }
    final progress = InspectionLogic.evaluate(sections, state.responses);
    if (!progress.canSubmit) return;
    await ref.read(databaseProvider).completeInspection(
          widget.inspectionId,
          progress.score,
          remarks: result.remarks,
        );
    await ref.read(syncControllerProvider.notifier).refreshPending();
    if (!mounted) return;
    Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) {
    return RailBackground(
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(title: const Text('Station inspection')),
        body: FutureBuilder<_InspectionFormState>(
          future: _state,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const GlassLoadingList();
            }
            if (snapshot.hasError) {
              return ErrorPane(error: snapshot.error!, retry: _reload);
            }
            final state = snapshot.data!;
            final definition = Map<String, dynamic>.from(
              state.template['definition'] as Map,
            );
            final sections = definition['sections'] as List? ?? const [];
            if (sections.isEmpty) {
              return const EmptyState(
                icon: Icons.list_alt_rounded,
                title: 'Template is empty',
                message: 'This inspection template has no sections.',
              );
            }
            if (_sectionIndex >= sections.length) {
              _sectionIndex = sections.length - 1;
            }
            final section = Map<String, dynamic>.from(
              sections[_sectionIndex] as Map,
            );
            final questions = section['questions'] as List? ?? const [];
            final progress = InspectionLogic.evaluate(
              sections,
              state.responses,
            );
            final isSubmitted = state.inspection['status'] == 'submitted';
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
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              '${state.inspection['station_code']} · ${definition['name']}',
                              style: const TextStyle(
                                fontWeight: FontWeight.w800,
                              ),
                              maxLines: 2,
                            ),
                          ),
                          StatusBadge(
                            isSubmitted
                                ? 'Submitted | ${progress.score}%'
                                : '${progress.answered}/${progress.total}',
                          ),
                        ],
                      ),
                      const SizedBox(height: AppSpacing.x2),
                      GlassProgressBar(
                        value: progress.completion.clamp(0.0, 1.0),
                      ),
                      const SizedBox(height: AppSpacing.x1),
                      SizedBox(
                        height: 40,
                        child: ListView.separated(
                          scrollDirection: Axis.horizontal,
                          itemCount: sections.length,
                          separatorBuilder: (_, __) => const SizedBox(width: 8),
                          itemBuilder: (context, index) {
                            final item = sections[index] as Map;
                            return GlassFilterChip(
                              selected: index == _sectionIndex,
                              label: '${item['title']}',
                              onTap: () =>
                                  setState(() => _sectionIndex = index),
                            );
                          },
                        ),
                      ),
                      const SizedBox(height: AppSpacing.x2),
                      Row(
                        children: [
                          if (!isSubmitted) ...[
                            Expanded(
                              child: SoftActionButton(
                                icon: Icons.photo_camera_outlined,
                                label: 'Photo',
                                onPressed: () => _addPhoto(
                                  state: state,
                                  sectionCode: '${section['title']}',
                                ),
                              ),
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: SoftActionButton(
                                icon: Icons.note_add_outlined,
                                label: 'Quick note',
                                onPressed: () => _addNote(
                                  sectionCode: '${section['title']}',
                                ),
                              ),
                            ),
                            const SizedBox(width: 8),
                          ],
                          Expanded(
                            child: SoftActionButton(
                              icon: Icons.collections_bookmark_outlined,
                              label:
                                  'Log ${state.evidence.length + state.notes.length}',
                              onPressed: () => _showFieldLog(state),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                Expanded(
                  child: ListView.separated(
                    padding: const EdgeInsets.fromLTRB(
                      AppSpacing.page,
                      AppSpacing.x1,
                      AppSpacing.page,
                      AppSpacing.x2,
                    ),
                    itemCount: questions.length,
                    separatorBuilder: (_, __) =>
                        const SizedBox(height: AppSpacing.x2),
                    itemBuilder: (context, index) {
                      final question = Map<String, dynamic>.from(
                        questions[index] as Map,
                      );
                      final response = state.responses['${question['code']}'];
                      return GlassPanel(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              '${question['text']}',
                              style: Theme.of(context)
                                  .textTheme
                                  .titleMedium
                                  ?.copyWith(fontWeight: FontWeight.w800),
                            ),
                            if (response?['remarks'] != null) ...[
                              const SizedBox(height: 7),
                              Text('${response!['remarks']}'),
                            ],
                            if ('${response?['platform'] ?? ''}'
                                .trim()
                                .isNotEmpty) ...[
                              const SizedBox(height: 5),
                              Text(
                                'Platform: ${response!['platform']}',
                                style: Theme.of(context).textTheme.bodySmall,
                              ),
                            ],
                            const SizedBox(height: 14),
                            Row(
                              children: [
                                Expanded(
                                  child: _AnswerButton(
                                    label: 'Pass',
                                    icon: Icons.check_rounded,
                                    selected:
                                        response?['response_value'] == 'pass',
                                    color: const Color(0xFF078766),
                                    onPressed: isSubmitted
                                        ? null
                                        : () => _answer(
                                              state: state,
                                              sectionCode: '${section['code']}',
                                              question: question,
                                              value: 'pass',
                                            ),
                                  ),
                                ),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: _AnswerButton(
                                    label: 'Fail',
                                    icon: Icons.close_rounded,
                                    selected:
                                        response?['response_value'] == 'fail',
                                    color: const Color(0xFFCE3A3A),
                                    onPressed: isSubmitted
                                        ? null
                                        : () => _answer(
                                              state: state,
                                              sectionCode: '${section['code']}',
                                              question: question,
                                              value: 'fail',
                                            ),
                                  ),
                                ),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: _AnswerButton(
                                    label: 'N/A',
                                    icon: Icons.remove_rounded,
                                    selected:
                                        response?['response_value'] == 'na',
                                    color: const Color(0xFF64748B),
                                    onPressed: isSubmitted
                                        ? null
                                        : () => _answer(
                                              state: state,
                                              sectionCode: '${section['code']}',
                                              question: question,
                                              value: 'na',
                                            ),
                                  ),
                                ),
                              ],
                            ),
                            if (!isSubmitted) ...[
                              const SizedBox(height: 10),
                              Row(
                                mainAxisAlignment: MainAxisAlignment.end,
                                children: [
                                  AppIconButton(
                                    tooltip: 'Attach photo to this item',
                                    onPressed: () => _addPhoto(
                                      state: state,
                                      sectionCode: '${section['title']}',
                                      question: question,
                                    ),
                                    icon: Icons.add_a_photo_outlined,
                                  ),
                                  const SizedBox(width: AppSpacing.x1),
                                  AppIconButton(
                                    tooltip: 'Add note to this item',
                                    onPressed: () => _addNote(
                                      sectionCode: '${section['title']}',
                                      question: question,
                                    ),
                                    icon: Icons.note_add_outlined,
                                  ),
                                ],
                              ),
                            ],
                          ],
                        ),
                      );
                    },
                  ),
                ),
                SafeArea(
                  top: false,
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(
                      AppSpacing.page,
                      AppSpacing.x1,
                      AppSpacing.page,
                      AppSpacing.x2,
                    ),
                    child: Row(
                      children: [
                        AppIconButton(
                          tooltip: 'Previous section',
                          onPressed: _sectionIndex == 0
                              ? null
                              : () => setState(() => _sectionIndex--),
                          icon: Icons.arrow_back_rounded,
                        ),
                        const SizedBox(width: AppSpacing.x1),
                        Expanded(
                          child: AppButton(
                            expand: true,
                            onPressed: isSubmitted
                                ? () => Navigator.pop(context)
                                : _sectionIndex == sections.length - 1
                                    ? () => _review(state, sections)
                                    : () => setState(() => _sectionIndex++),
                            icon: isSubmitted
                                ? Icons.close_rounded
                                : _sectionIndex == sections.length - 1
                                    ? Icons.fact_check_outlined
                                    : Icons.arrow_forward_rounded,
                            label: isSubmitted
                                ? 'Close'
                                : _sectionIndex == sections.length - 1
                                    ? 'Review and submit'
                                    : 'Next section',
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}

class _AnswerButton extends StatelessWidget {
  const _AnswerButton({
    required this.label,
    required this.icon,
    required this.selected,
    required this.color,
    required this.onPressed,
  });

  final String label;
  final IconData icon;
  final bool selected;
  final Color color;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    final disabled = onPressed == null;
    return Semantics(
      button: true,
      enabled: !disabled,
      selected: selected,
      label: label,
      child: GestureDetector(
        onTap: onPressed,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 220),
          padding: const EdgeInsets.symmetric(vertical: 11, horizontal: 6),
          decoration: BoxDecoration(
            color: selected && !disabled ? const Color(0xFFEDE4FF) : null,
            gradient: selected && !disabled
                ? null
                : LinearGradient(
                    colors: [
                      color.withValues(alpha: disabled ? 0.03 : 0.11),
                      Theme.of(context)
                          .colorScheme
                          .surface
                          .withValues(alpha: 0.22),
                    ],
                  ),
            borderRadius: BorderRadius.circular(15),
            border: Border.all(
              color: disabled
                  ? Theme.of(context).colorScheme.outlineVariant
                  : color.withValues(alpha: selected ? 0.82 : 0.24),
            ),
            boxShadow: null,
          ),
          child: Column(
            children: [
              Icon(
                icon,
                color: disabled
                    ? Theme.of(context).colorScheme.outline
                    : selected
                        ? Theme.of(context).colorScheme.primary
                        : color,
              ),
              const SizedBox(height: 3),
              Text(
                label,
                style: TextStyle(
                  color: disabled
                      ? Theme.of(context).colorScheme.outline
                      : selected
                          ? Theme.of(context).colorScheme.primary
                          : color,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _FindingDetail {
  const _FindingDetail({
    required this.description,
    required this.severity,
    required this.repeatObservation,
    this.platform,
    this.responsibleParty,
    this.targetDate,
    this.financialImplication,
  });

  final String description;
  final String severity;
  final String? platform;
  final String? responsibleParty;
  final String? targetDate;
  final int? financialImplication;
  final bool repeatObservation;
}

class _FindingDialog extends StatefulWidget {
  const _FindingDialog({
    required this.question,
    this.initialFinding,
    this.initialPlatform,
  });

  final String question;
  final Map<String, dynamic>? initialFinding;
  final String? initialPlatform;

  @override
  State<_FindingDialog> createState() => _FindingDialogState();
}

class _FindingDialogState extends State<_FindingDialog> {
  late final TextEditingController _description;
  late final TextEditingController _responsibleParty;
  late final TextEditingController _financialImplication;
  late final TextEditingController _platform;
  String _severity = 'medium';
  DateTime? _targetDate;
  bool _repeatObservation = false;

  @override
  void initState() {
    super.initState();
    final finding = widget.initialFinding;
    _description = TextEditingController(
      text: '${finding?['description'] ?? ''}',
    );
    _responsibleParty = TextEditingController(
      text: '${finding?['responsible_party'] ?? ''}',
    );
    _financialImplication = TextEditingController(
      text: finding?['financial_implication'] == null
          ? ''
          : '${finding!['financial_implication']}',
    );
    _platform = TextEditingController(text: widget.initialPlatform ?? '');
    _severity = '${finding?['severity'] ?? 'medium'}';
    _repeatObservation = finding?['repeat_observation'] == 1 ||
        finding?['repeat_observation'] == true;
    _targetDate = DateTime.tryParse('${finding?['target_date'] ?? ''}');
  }

  @override
  void dispose() {
    _description.dispose();
    _responsibleParty.dispose();
    _financialImplication.dispose();
    _platform.dispose();
    super.dispose();
  }

  Future<void> _selectTargetDate() async {
    var pending = _targetDate ?? DateTime.now().add(const Duration(days: 14));
    final selected = await showDialog<DateTime>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AppDialogShell(
          icon: Icons.event_outlined,
          title: 'Target date',
          subtitle: 'Choose when corrective action should be completed.',
          content: CalendarDatePicker(
            initialDate: pending,
            firstDate: DateTime.now(),
            lastDate: DateTime.now().add(const Duration(days: 3650)),
            onDateChanged: (value) => setDialogState(() => pending = value),
          ),
          actions: [
            AppButton(
              label: 'Cancel',
              kind: AppButtonKind.ghost,
              onPressed: () => Navigator.pop(context),
            ),
            AppButton(
              label: 'Use date',
              icon: Icons.check_rounded,
              onPressed: () => Navigator.pop(context, pending),
            ),
          ],
        ),
      ),
    );
    if (selected != null) setState(() => _targetDate = selected);
  }

  @override
  Widget build(BuildContext context) {
    return AppDialogShell(
      icon: Icons.report_problem_outlined,
      title: 'Record finding',
      subtitle: widget.question,
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            TextField(
              controller: _description,
              minLines: 3,
              maxLines: 6,
              onChanged: (_) => setState(() {}),
              decoration: const InputDecoration(
                labelText: 'Observation and required action',
                alignLabelWithHint: true,
              ),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              initialValue: _severity,
              decoration: const InputDecoration(labelText: 'Severity'),
              items: const [
                DropdownMenuItem(value: 'low', child: Text('Low')),
                DropdownMenuItem(value: 'medium', child: Text('Medium')),
                DropdownMenuItem(value: 'high', child: Text('High')),
                DropdownMenuItem(value: 'critical', child: Text('Critical')),
              ],
              onChanged: (value) =>
                  setState(() => _severity = value ?? 'medium'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _platform,
              decoration: const InputDecoration(
                labelText: 'Platform or location',
                prefixIcon: Icon(Icons.place_outlined),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _responsibleParty,
              decoration: const InputDecoration(
                labelText: 'Responsible department or person',
                prefixIcon: Icon(Icons.person_outline_rounded),
              ),
            ),
            const SizedBox(height: 12),
            InkWell(
              onTap: _selectTargetDate,
              borderRadius: BorderRadius.circular(12),
              child: InputDecorator(
                decoration: const InputDecoration(
                  labelText: 'Target date',
                  prefixIcon: Icon(Icons.event_outlined),
                ),
                child: Text(
                  _targetDate == null
                      ? 'Select date'
                      : _targetDate!.toIso8601String().split('T').first,
                ),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _financialImplication,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(
                labelText: 'Financial implication (INR)',
                prefixIcon: Icon(Icons.currency_rupee_rounded),
              ),
            ),
            const SizedBox(height: 6),
            GlassToggleRow(
              title: 'Repeat observation',
              subtitle: 'This issue was reported earlier.',
              value: _repeatObservation,
              onChanged: (value) => setState(() => _repeatObservation = value),
            ),
          ],
        ),
      ),
      actions: [
        AppButton(
          label: 'Cancel',
          kind: AppButtonKind.ghost,
          onPressed: () => Navigator.pop(context),
        ),
        AppButton(
          label: 'Save finding',
          icon: Icons.save_outlined,
          onPressed: _description.text.trim().isEmpty
              ? null
              : () => Navigator.pop(
                    context,
                    _FindingDetail(
                      description: _description.text.trim(),
                      severity: _severity,
                      platform: _nullableText(_platform.text),
                      responsibleParty: _nullableText(_responsibleParty.text),
                      targetDate:
                          _targetDate?.toIso8601String().split('T').first,
                      financialImplication: int.tryParse(
                        _financialImplication.text.replaceAll(',', '').trim(),
                      ),
                      repeatObservation: _repeatObservation,
                    ),
                  ),
        ),
      ],
    );
  }

  String? _nullableText(String value) {
    final trimmed = value.trim();
    return trimmed.isEmpty ? null : trimmed;
  }
}
