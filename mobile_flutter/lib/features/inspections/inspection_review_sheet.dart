import 'package:flutter/material.dart';

import '../../shared/widgets.dart';
import 'inspection_logic.dart';

class InspectionReviewResult {
  const InspectionReviewResult.submit(this.remarks) : sectionIndex = null;
  const InspectionReviewResult.openSection(this.sectionIndex) : remarks = null;

  final int? sectionIndex;
  final String? remarks;
  bool get shouldSubmit => sectionIndex == null;
}

class InspectionReviewSheet extends StatefulWidget {
  const InspectionReviewSheet({
    required this.sections,
    required this.responses,
    required this.findings,
    required this.evidenceCount,
    required this.noteCount,
    required this.initialRemarks,
    super.key,
  });

  final List<dynamic> sections;
  final Map<String, Map<String, dynamic>> responses;
  final List<Map<String, dynamic>> findings;
  final int evidenceCount;
  final int noteCount;
  final String initialRemarks;

  @override
  State<InspectionReviewSheet> createState() => _InspectionReviewSheetState();
}

class _InspectionReviewSheetState extends State<InspectionReviewSheet> {
  late final TextEditingController _remarks;

  @override
  void initState() {
    super.initState();
    _remarks = TextEditingController(text: widget.initialRemarks);
  }

  @override
  void dispose() {
    _remarks.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final progress = InspectionLogic.evaluate(
      widget.sections,
      widget.responses,
    );
    final activeFindings = widget.findings
        .where((finding) => finding['status'] != 'closed')
        .toList();
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.fromLTRB(
          16,
          12,
          16,
          16 + MediaQuery.viewInsetsOf(context).bottom,
        ),
        child: Column(
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    'Review inspection',
                    style: Theme.of(context)
                        .textTheme
                        .headlineSmall
                        ?.copyWith(fontWeight: FontWeight.w900),
                  ),
                ),
                AppIconButton(
                  tooltip: 'Close review',
                  onPressed: () => Navigator.pop(context),
                  icon: Icons.close_rounded,
                ),
              ],
            ),
            const SizedBox(height: 8),
            Expanded(
              child: ListView(
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: _ReviewMetric(
                          label: 'Score',
                          value: '${progress.score}%',
                          icon: Icons.speed_rounded,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: _ReviewMetric(
                          label: 'Passed',
                          value: '${progress.passed}',
                          icon: Icons.check_circle_rounded,
                          color: const Color(0xFF078766),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: _ReviewMetric(
                          label: 'Findings',
                          value: '${activeFindings.length}',
                          icon: Icons.report_problem_rounded,
                          color: const Color(0xFFCE3A3A),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  GlassPanel(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Icon(
                              progress.canSubmit
                                  ? Icons.verified_rounded
                                  : Icons.pending_actions_rounded,
                              color: progress.canSubmit
                                  ? const Color(0xFF078766)
                                  : const Color(0xFFD97706),
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                progress.canSubmit
                                    ? 'All required items are complete'
                                    : '${progress.missingRequiredCodes.length} required items need answers',
                                style: const TextStyle(
                                  fontWeight: FontWeight.w900,
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Text(
                          '${progress.requiredAnswered}/${progress.requiredTotal} required · '
                          '${progress.answered}/${progress.total} total answered · '
                          '${progress.notApplicable} not applicable',
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 12),
                  GlassPanel(
                    padding: const EdgeInsets.all(13),
                    child: Row(
                      children: [
                        Icon(
                          Icons.collections_bookmark_outlined,
                          color: Theme.of(context).colorScheme.primary,
                        ),
                        const SizedBox(width: 9),
                        Expanded(
                          child: Text(
                            '${widget.evidenceCount} photos | '
                            '${widget.noteCount} contextual notes attached',
                            style: const TextStyle(fontWeight: FontWeight.w800),
                          ),
                        ),
                      ],
                    ),
                  ),
                  if (activeFindings.isNotEmpty) ...[
                    const SizedBox(height: 12),
                    Text(
                      'Open findings',
                      style: Theme.of(context)
                          .textTheme
                          .titleMedium
                          ?.copyWith(fontWeight: FontWeight.w900),
                    ),
                    const SizedBox(height: 8),
                    for (final finding in activeFindings)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: GlassPanel(
                          padding: const EdgeInsets.all(12),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              StatusBadge('${finding['severity']}'),
                              const SizedBox(width: 9),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      '${finding['title']}',
                                      style: const TextStyle(
                                        fontWeight: FontWeight.w800,
                                      ),
                                    ),
                                    if ('${finding['description'] ?? ''}'
                                        .trim()
                                        .isNotEmpty)
                                      Text(
                                        '${finding['description']}',
                                        maxLines: 2,
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                  ],
                  const SizedBox(height: 4),
                  TextField(
                    controller: _remarks,
                    minLines: 3,
                    maxLines: 6,
                    decoration: const InputDecoration(
                      labelText: 'Overall inspection remarks',
                      hintText: 'Record the overall condition and key action.',
                      alignLabelWithHint: true,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: progress.canSubmit
                  ? AppButton(
                      expand: true,
                      onPressed: () => Navigator.pop(
                        context,
                        InspectionReviewResult.submit(_remarks.text.trim()),
                      ),
                      icon: Icons.send_rounded,
                      label: 'Submit inspection',
                    )
                  : AppButton(
                      expand: true,
                      kind: AppButtonKind.secondary,
                      onPressed: () => Navigator.pop(
                        context,
                        InspectionReviewResult.openSection(
                          InspectionLogic.sectionForQuestion(
                            widget.sections,
                            progress.missingRequiredCodes.first,
                          ),
                        ),
                      ),
                      icon: Icons.edit_note_rounded,
                      label: 'Complete missing items',
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ReviewMetric extends StatelessWidget {
  const _ReviewMetric({
    required this.label,
    required this.value,
    required this.icon,
    this.color,
  });

  final String label;
  final String value;
  final IconData icon;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final tone = color ?? Theme.of(context).colorScheme.primary;
    return GlassPanel(
      padding: const EdgeInsets.all(12),
      child: Column(
        children: [
          Icon(icon, color: tone),
          const SizedBox(height: 5),
          Text(
            value,
            style: Theme.of(
              context,
            ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900),
          ),
          Text(label, style: Theme.of(context).textTheme.labelMedium),
        ],
      ),
    );
  }
}
