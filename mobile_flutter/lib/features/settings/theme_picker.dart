import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme/app_theme.dart';
import '../../core/theme/theme_controller.dart';
import '../../shared/widgets.dart';

class ThemePickerButton extends ConsumerWidget {
  const ThemePickerButton({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return AppIconButton(
      icon: Icons.palette_outlined,
      tooltip: 'Choose appearance',
      onPressed: () => showGlassBottomSheet<void>(
        context,
        builder: (_) => const ThemePickerSheet(),
      ),
    );
  }
}

class ThemePickerSheet extends ConsumerWidget {
  const ThemePickerSheet({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final selected = ref.watch(themeControllerProvider);
    return ConstrainedBox(
      constraints: BoxConstraints(
        maxHeight: MediaQuery.sizeOf(context).height * 0.82,
      ),
      child: ListView(
        shrinkWrap: true,
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.page,
          AppSpacing.x2,
          AppSpacing.page,
          AppSpacing.x3,
        ),
        children: [
          const PageHeading(
            title: 'Appearance',
            subtitle: 'Choose a complete visual environment.',
          ),
          const SizedBox(height: AppSpacing.x3),
          LayoutBuilder(
            builder: (context, constraints) {
              final columns = constraints.maxWidth >= 560 ? 2 : 1;
              final width =
                  (constraints.maxWidth - (columns - 1) * AppSpacing.x1) /
                      columns;
              return Wrap(
                spacing: AppSpacing.x1,
                runSpacing: AppSpacing.x1,
                children: [
                  for (final preset in AppThemePreset.values)
                    SizedBox(
                      width: width,
                      child: _ThemeOption(
                        preset: preset,
                        selected: selected == preset,
                        onTap: () => ref
                            .read(themeControllerProvider.notifier)
                            .select(preset),
                      ),
                    ),
                ],
              );
            },
          ),
          const SizedBox(height: AppSpacing.x3),
          AppButton(
            expand: true,
            icon: Icons.check_rounded,
            label: 'Use ${selected.label}',
            onPressed: () => Navigator.pop(context),
          ),
        ],
      ),
    );
  }
}

class _ThemeOption extends StatefulWidget {
  const _ThemeOption({
    required this.preset,
    required this.selected,
    required this.onTap,
  });

  final AppThemePreset preset;
  final bool selected;
  final VoidCallback onTap;

  @override
  State<_ThemeOption> createState() => _ThemeOptionState();
}

class _ThemeOptionState extends State<_ThemeOption> {
  var _pressed = false;

  @override
  Widget build(BuildContext context) {
    final colors = widget.preset.previewColors;
    return Semantics(
      button: true,
      selected: widget.selected,
      label: '${widget.preset.label} theme',
      child: Listener(
        onPointerDown: (_) => setState(() => _pressed = true),
        onPointerUp: (_) => setState(() => _pressed = false),
        onPointerCancel: (_) => setState(() => _pressed = false),
        child: GestureDetector(
          onTap: widget.onTap,
          child: AnimatedScale(
            scale: _pressed ? 0.975 : 1,
            duration: const Duration(milliseconds: 130),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 260),
              padding: const EdgeInsets.all(13),
              decoration: BoxDecoration(
                color: widget.selected
                    ? const Color(0xFFEDE4FF)
                    : Theme.of(context)
                        .colorScheme
                        .surface
                        .withValues(alpha: 0.34),
                borderRadius: BorderRadius.circular(20),
                border: Border.all(
                  width: widget.selected ? 1.6 : 1,
                  color: widget.selected
                      ? Theme.of(context).colorScheme.primary
                      : Colors.white.withValues(alpha: 0.13),
                ),
                boxShadow: null,
              ),
              child: Row(
                children: [
                  Container(
                    width: 70,
                    height: 54,
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        colors: colors,
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                      ),
                      borderRadius: BorderRadius.circular(15),
                      border: Border.all(
                        color: Colors.white.withValues(alpha: 0.26),
                      ),
                    ),
                    child: Stack(
                      children: [
                        Positioned(
                          left: 8,
                          right: 19,
                          top: 9,
                          child: Container(
                            height: 8,
                            decoration: BoxDecoration(
                              color: Colors.white.withValues(alpha: 0.72),
                              borderRadius: BorderRadius.circular(6),
                            ),
                          ),
                        ),
                        Positioned(
                          left: 8,
                          right: 8,
                          bottom: 8,
                          child: Row(
                            children: [
                              for (final color in colors.skip(1))
                                Container(
                                  width: 14,
                                  height: 14,
                                  margin: const EdgeInsets.only(right: 5),
                                  decoration: BoxDecoration(
                                    color: color,
                                    borderRadius: BorderRadius.circular(5),
                                    border: Border.all(
                                      color:
                                          Colors.white.withValues(alpha: 0.4),
                                    ),
                                  ),
                                ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          widget.preset.label,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontWeight: FontWeight.w900),
                        ),
                        const SizedBox(height: 3),
                        Text(
                          widget.preset.description,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 8),
                  AnimatedSwitcher(
                    duration: const Duration(milliseconds: 180),
                    child: widget.selected
                        ? Icon(
                            Icons.check_circle_rounded,
                            key: const ValueKey('selected'),
                            color: Theme.of(context).colorScheme.primary,
                          )
                        : Icon(
                            Icons.circle_outlined,
                            key: const ValueKey('available'),
                            color: Theme.of(context).colorScheme.outline,
                          ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
