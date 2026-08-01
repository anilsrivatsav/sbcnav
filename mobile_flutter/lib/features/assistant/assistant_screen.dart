import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/remote/mobile_api.dart';
import '../../shared/widgets.dart';

class AssistantScreen extends ConsumerStatefulWidget {
  const AssistantScreen({super.key});

  @override
  ConsumerState<AssistantScreen> createState() => _AssistantScreenState();
}

class _AssistantScreenState extends ConsumerState<AssistantScreen> {
  final _controller = TextEditingController();
  Map<String, dynamic>? _result;
  String? _error;
  var _loading = false;

  static const _suggestions = [
    'Tell me about SBC station',
    'Show open inspection findings',
    'Which stations have pending works?',
  ];

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _ask([String? suggestion]) async {
    final question = (suggestion ?? _controller.text).trim();
    if (question.isEmpty || _loading) return;
    setState(() {
      _controller.text = question;
      _loading = true;
      _error = null;
    });
    try {
      final result = await ref.read(mobileApiProvider).askAi(question);
      if (!mounted) return;
      setState(() => _result = result);
    } catch (error) {
      if (!mounted) return;
      setState(() => _error = '$error');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final rows = _result?['rows'] as List? ?? const [];
    return ListView(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.page,
        AppSpacing.x3,
        AppSpacing.page,
        AppSpacing.x4,
      ),
      children: [
        const PageHeading(
          title: 'AI Assistant',
          subtitle: 'Ask about stations, works, contracts and inspections.',
        ),
        const SizedBox(height: AppSpacing.x3),
        Container(
          padding: const EdgeInsets.all(16),
          decoration: _softDecoration(context),
          child: Column(
            children: [
              TextField(
                controller: _controller,
                minLines: 3,
                maxLines: 5,
                textInputAction: TextInputAction.done,
                onSubmitted: (_) => _ask(),
                decoration: const InputDecoration(
                  hintText: 'What would you like to know?',
                  prefixIcon: Icon(Icons.auto_awesome_rounded),
                ),
              ),
              const SizedBox(height: 12),
              AppButton(
                expand: true,
                loading: _loading,
                onPressed: _loading ? null : _ask,
                icon: Icons.arrow_upward_rounded,
                label: 'Ask Rail AI',
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final suggestion in _suggestions)
              ActionChip(
                label: Text(suggestion),
                onPressed: _loading ? null : () => _ask(suggestion),
              ),
          ],
        ),
        if (_error != null) ...[
          const SizedBox(height: 16),
          ErrorPane(error: _error!, retry: _ask),
        ],
        if (_result != null && _error == null) ...[
          const SizedBox(height: 20),
          Text(
            '${_result?['answer'] ?? _result?['message'] ?? 'Answer ready'}',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w800,
                  height: 1.45,
                ),
          ),
          if (rows.isNotEmpty) ...[
            const SizedBox(height: 14),
            for (final row in rows.take(8))
              Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(14),
                  decoration: _softDecoration(context),
                  child: Text(
                    (row as Map)
                        .entries
                        .take(5)
                        .map((entry) => '${entry.key}: ${entry.value}')
                        .join('\n'),
                  ),
                ),
              ),
          ],
        ],
      ],
    );
  }
}

BoxDecoration _softDecoration(BuildContext context) {
  final colors = Theme.of(context).colorScheme;
  return BoxDecoration(
    color: colors.surface,
    borderRadius: BorderRadius.circular(20),
    border: Border.all(color: colors.outlineVariant),
    boxShadow: [
      BoxShadow(
        color: Colors.black.withValues(alpha: 0.08),
        blurRadius: 22,
        offset: const Offset(0, 10),
      ),
    ],
  );
}
