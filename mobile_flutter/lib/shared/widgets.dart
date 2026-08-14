import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';

import '../core/theme/app_theme.dart';

abstract final class AppSpacing {
  static const x1 = 8.0;
  static const x2 = 16.0;
  static const x3 = 24.0;
  static const x4 = 32.0;
  static const page = 24.0;
}

abstract final class AppRadius {
  static const control = 16.0;
  static const card = 22.0;
  static const sheet = 28.0;
}

String displayText(Object? value, {String fallback = 'Not recorded'}) {
  final text = value?.toString().trim() ?? '';
  return text.isEmpty ? fallback : text;
}

String shortDate(Object? value) {
  final parsed = DateTime.tryParse('${value ?? ''}');
  if (parsed == null) return displayText(value);
  return DateFormat('dd MMM yyyy, HH:mm').format(parsed.toLocal());
}

Color statusTone(String status, [Color? fallback]) {
  final value = status.toLowerCase().replaceAll('_', ' ').trim();
  if (value.contains('complete') ||
      value.contains('submitted') ||
      value.contains('closed') ||
      value.contains('active') ||
      value.contains('pass')) {
    return AppPalette.emerald;
  }
  if (value.contains('progress') ||
      value.contains('ongoing') ||
      value.contains('current')) {
    return AppPalette.cyan;
  }
  if (value.contains('pending') ||
      value.contains('sanction') ||
      value.contains('draft') ||
      value.contains('tender') ||
      value.contains('attention') ||
      value.contains('due')) {
    return AppPalette.amber;
  }
  if (value.contains('critical') ||
      value.contains('fail') ||
      value.contains('expired') ||
      value.contains('overdue')) {
    return AppPalette.red;
  }
  return fallback ?? AppPalette.royalBlue;
}

class RailBackground extends StatelessWidget {
  const RailBackground({required this.child, super.key});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final visual = Theme.of(context).extension<AppVisualTheme>()!;
    final base = dark ? const Color(0xFF111B27) : null;
    return Stack(
      fit: StackFit.expand,
      children: [
        DecoratedBox(
          decoration: BoxDecoration(
            gradient: base == null
                ? const LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    colors: [
                      Color(0xFFEDE6FF),
                      Color(0xFFF8F2FF),
                      Color(0xFFFFEDE8),
                    ],
                  )
                : null,
            color: base,
          ),
        ),
        IgnorePointer(
          child: Align(
            alignment: Alignment.topCenter,
            child: Container(
              height: 90,
              decoration: BoxDecoration(
                color: visual.glassHighlight
                    .withValues(alpha: dark ? 0.025 : 0.07),
              ),
            ),
          ),
        ),
        child,
      ],
    );
  }
}

class GlassPanel extends StatefulWidget {
  const GlassPanel({
    required this.child,
    this.padding = const EdgeInsets.all(16),
    this.onTap,
    this.semanticLabel,
    super.key,
  });

  final Widget child;
  final EdgeInsets padding;
  final VoidCallback? onTap;
  final String? semanticLabel;

  @override
  State<GlassPanel> createState() => _GlassPanelState();
}

class NeoPanel extends StatelessWidget {
  const NeoPanel(
      {required this.child,
      this.padding = const EdgeInsets.all(16),
      this.onTap,
      super.key});

  final Widget child;
  final EdgeInsets padding;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final surface = Theme.of(context).colorScheme.surface;
    final panel = AnimatedContainer(
      duration: const Duration(milliseconds: 180),
      padding: padding,
      decoration: BoxDecoration(
        color: surface,
        borderRadius: BorderRadius.circular(AppRadius.card),
        border: Border.all(color: dark ? Colors.white10 : Colors.white),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: dark ? 0.32 : 0.12),
            blurRadius: 18,
            offset: const Offset(8, 9),
          ),
          BoxShadow(
            color: dark ? Colors.white.withValues(alpha: 0.025) : Colors.white,
            blurRadius: 14,
            offset: const Offset(-7, -7),
          ),
        ],
      ),
      child: child,
    );
    return onTap == null
        ? panel
        : InkWell(
            borderRadius: BorderRadius.circular(AppRadius.card),
            onTap: onTap,
            child: panel);
  }
}

class _GlassPanelState extends State<GlassPanel> {
  var _hovered = false;
  var _pressed = false;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final interactive = widget.onTap != null;
    final surface = colors.surface;
    return Semantics(
      button: interactive,
      label: widget.semanticLabel,
      child: MouseRegion(
        onEnter: interactive ? (_) => setState(() => _hovered = true) : null,
        onExit: interactive ? (_) => setState(() => _hovered = false) : null,
        child: Listener(
          onPointerDown:
              interactive ? (_) => setState(() => _pressed = true) : null,
          onPointerUp:
              interactive ? (_) => setState(() => _pressed = false) : null,
          onPointerCancel:
              interactive ? (_) => setState(() => _pressed = false) : null,
          child: GestureDetector(
            behavior: HitTestBehavior.opaque,
            onTap: widget.onTap == null
                ? null
                : () {
                    HapticFeedback.selectionClick();
                    widget.onTap!();
                  },
            child: AnimatedScale(
              scale: _pressed ? 0.985 : (_hovered ? 1.006 : 1),
              duration: const Duration(milliseconds: 160),
              curve: Curves.easeOutCubic,
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 180),
                padding: widget.padding,
                decoration: BoxDecoration(
                  color: surface,
                  borderRadius: BorderRadius.circular(AppRadius.card),
                  border: Border.all(
                    color: dark ? Colors.white10 : Colors.white,
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withValues(
                        alpha: dark
                            ? (_hovered ? 0.3 : 0.22)
                            : (_hovered ? 0.14 : 0.09),
                      ),
                      blurRadius: _hovered ? 20 : 16,
                      offset: Offset(_hovered ? 6 : 8, _hovered ? 8 : 10),
                    ),
                    BoxShadow(
                      color: dark ? Colors.white10 : Colors.white,
                      blurRadius: 13,
                      offset: const Offset(-7, -7),
                    ),
                  ],
                ),
                child: widget.child,
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class PageHeading extends StatelessWidget {
  const PageHeading({
    required this.title,
    required this.subtitle,
    this.action,
    super.key,
  });

  final String title;
  final String subtitle;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
              ),
              const SizedBox(height: 3),
              Text(
                subtitle,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
              ),
            ],
          ),
        ),
        if (action != null) action!,
      ],
    );
  }
}

class StatusBadge extends StatelessWidget {
  const StatusBadge(this.label, {this.tone, super.key});

  final String label;
  final Color? tone;

  @override
  Widget build(BuildContext context) {
    final color =
        tone ?? statusTone(label, Theme.of(context).colorScheme.primary);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withValues(alpha: 0.28)),
      ),
      child: Text(
        label.toUpperCase(),
        style: TextStyle(
          color: color,
          fontSize: 10,
          fontWeight: FontWeight.w800,
          letterSpacing: 0,
        ),
      ),
    );
  }
}

class SoftActionButton extends StatelessWidget {
  const SoftActionButton({
    required this.icon,
    required this.label,
    required this.onPressed,
    this.selected = false,
    super.key,
  });

  final IconData icon;
  final String label;
  final VoidCallback? onPressed;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    return _GlassTapSurface(
      onTap: onPressed,
      selected: selected,
      semanticLabel: label,
      padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 11),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            icon,
            size: 19,
            color: selected
                ? Theme.of(context).colorScheme.onPrimaryContainer
                : Theme.of(context).colorScheme.primary,
          ),
          const SizedBox(width: 7),
          Flexible(
            child: Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontWeight: FontWeight.w800),
            ),
          ),
        ],
      ),
    );
  }
}

enum AppButtonKind { primary, secondary, ghost, danger }

class AppButton extends StatefulWidget {
  const AppButton({
    required this.label,
    required this.onPressed,
    this.icon,
    this.kind = AppButtonKind.primary,
    this.expand = false,
    this.loading = false,
    super.key,
  });

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final AppButtonKind kind;
  final bool expand;
  final bool loading;

  @override
  State<AppButton> createState() => _AppButtonState();
}

class _AppButtonState extends State<AppButton> {
  var _pressed = false;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final enabled = widget.onPressed != null && !widget.loading;
    final foreground = switch (widget.kind) {
      AppButtonKind.primary => colors.onPrimary,
      AppButtonKind.danger => colors.onError,
      _ => colors.onSurface,
    };
    final button = AnimatedScale(
      scale: _pressed ? 0.97 : 1,
      duration: const Duration(milliseconds: 100),
      child: Semantics(
        button: true,
        enabled: enabled,
        label: widget.label,
        child: Listener(
          onPointerDown:
              enabled ? (_) => setState(() => _pressed = true) : null,
          onPointerUp: enabled ? (_) => setState(() => _pressed = false) : null,
          onPointerCancel:
              enabled ? (_) => setState(() => _pressed = false) : null,
          child: GestureDetector(
            onTap: !enabled
                ? null
                : () {
                    HapticFeedback.lightImpact();
                    widget.onPressed!();
                  },
            child: ClipRRect(
              borderRadius: BorderRadius.circular(AppRadius.control),
              child: BackdropFilter(
                filter: ImageFilter.blur(sigmaX: 24, sigmaY: 24),
                child: Container(
                  constraints: const BoxConstraints(minHeight: 52),
                  padding:
                      const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(AppRadius.control),
                    border: Border.all(
                      color: widget.kind == AppButtonKind.primary
                          ? Colors.white.withValues(alpha: 0.2)
                          : Colors.white.withValues(alpha: 0.1),
                    ),
                    gradient: _buttonGradient(
                      widget.kind,
                      colors,
                      enabled,
                    ),
                    boxShadow: widget.kind == AppButtonKind.primary && enabled
                        ? [
                            BoxShadow(
                              color: colors.primary.withValues(alpha: 0.24),
                              blurRadius: 22,
                              offset: const Offset(0, 9),
                            ),
                          ]
                        : null,
                  ),
                  child: Row(
                    mainAxisSize:
                        widget.expand ? MainAxisSize.max : MainAxisSize.min,
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      if (widget.loading)
                        SizedBox.square(
                          dimension: 19,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: foreground,
                          ),
                        )
                      else if (widget.icon != null)
                        Icon(widget.icon, size: 20, color: foreground),
                      if (widget.loading || widget.icon != null)
                        const SizedBox(width: 9),
                      Flexible(
                        child: Text(
                          widget.label,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            color: enabled ? foreground : colors.outline,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
    return widget.expand
        ? SizedBox(width: double.infinity, child: button)
        : button;
  }

  LinearGradient _buttonGradient(
    AppButtonKind kind,
    ColorScheme colors,
    bool enabled,
  ) {
    if (!enabled) {
      return LinearGradient(
        colors: [
          colors.surfaceContainerHighest.withValues(alpha: 0.44),
          colors.surface.withValues(alpha: 0.3),
        ],
      );
    }
    return switch (kind) {
      AppButtonKind.primary => LinearGradient(
          colors: [colors.primary, AppPalette.royalBlue],
        ),
      AppButtonKind.danger => LinearGradient(
          colors: [colors.error, const Color(0xFFB92646)],
        ),
      AppButtonKind.secondary => LinearGradient(
          colors: [
            colors.surface.withValues(alpha: 0.62),
            colors.secondaryContainer.withValues(alpha: 0.5),
          ],
        ),
      AppButtonKind.ghost => LinearGradient(
          colors: [
            Colors.white.withValues(alpha: 0.04),
            colors.surface.withValues(alpha: 0.2),
          ],
        ),
    };
  }
}

class AppIconButton extends StatelessWidget {
  const AppIconButton({
    required this.icon,
    required this.tooltip,
    required this.onPressed,
    this.selected = false,
    super.key,
  });

  final IconData icon;
  final String tooltip;
  final VoidCallback? onPressed;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: tooltip,
      child: _GlassTapSurface(
        onTap: onPressed,
        selected: selected,
        semanticLabel: tooltip,
        padding: const EdgeInsets.all(12),
        child: Icon(
          icon,
          size: 21,
          color: onPressed == null
              ? Theme.of(context).colorScheme.outline
              : selected
                  ? Theme.of(context).colorScheme.onPrimaryContainer
                  : Theme.of(context).colorScheme.primary,
        ),
      ),
    );
  }
}

class AppSearchField extends StatelessWidget {
  const AppSearchField({
    required this.hint,
    required this.onChanged,
    this.controller,
    super.key,
  });

  final String hint;
  final ValueChanged<String> onChanged;
  final TextEditingController? controller;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      textField: true,
      label: hint,
      child: Container(
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surface,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: Theme.of(context).colorScheme.outlineVariant.withValues(alpha: .34)),
          boxShadow: [
            BoxShadow(color: Colors.black.withValues(alpha: .08), blurRadius: 14, offset: const Offset(5, 7)),
            const BoxShadow(color: Colors.white, blurRadius: 10, offset: Offset(-5, -5)),
          ],
        ),
        child: TextField(
              controller: controller,
              onChanged: onChanged,
              textInputAction: TextInputAction.search,
              decoration: InputDecoration(
                filled: false,
                border: InputBorder.none,
                enabledBorder: InputBorder.none,
                focusedBorder: InputBorder.none,
                hintText: hint,
                prefixIcon: const Icon(Icons.search_rounded),
                suffixIcon: controller?.text.isNotEmpty == true
                    ? IconButton(
                        tooltip: 'Clear search',
                        onPressed: () {
                          controller!.clear();
                          onChanged('');
                        },
                        icon: const Icon(Icons.close_rounded),
                      )
                    : null,
              ),
            ),
      ),
    );
  }
}

class GlassFilterChip extends StatelessWidget {
  const GlassFilterChip({
    required this.label,
    required this.selected,
    required this.onTap,
    this.icon,
    super.key,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    return _GlassTapSurface(
      onTap: onTap,
      selected: selected,
      semanticLabel: label,
      padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 9),
      radius: 18,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(
              icon,
              size: 16,
              color: selected
                  ? Theme.of(context).colorScheme.onPrimaryContainer
                  : Theme.of(context).colorScheme.primary,
            ),
            const SizedBox(width: 6),
          ],
          Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
      ),
    );
  }
}

class GlassProgressBar extends StatelessWidget {
  const GlassProgressBar({
    required this.value,
    this.tone,
    this.height = 6,
    super.key,
  });

  final double value;
  final Color? tone;
  final double height;

  @override
  Widget build(BuildContext context) {
    final color = tone ?? Theme.of(context).colorScheme.primary;
    return LayoutBuilder(
      builder: (context, constraints) => Container(
        height: height,
        decoration: BoxDecoration(
          color: Theme.of(context)
              .colorScheme
              .surfaceContainerHighest
              .withValues(alpha: 0.54),
          borderRadius: BorderRadius.circular(height),
        ),
        alignment: Alignment.centerLeft,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 650),
          curve: Curves.easeOutCubic,
          width: constraints.maxWidth * value.clamp(0, 1),
          decoration: BoxDecoration(
            gradient: LinearGradient(
              colors: [color, AppPalette.royalBlue],
            ),
            borderRadius: BorderRadius.circular(height),
            boxShadow: [
              BoxShadow(
                color: color.withValues(alpha: 0.3),
                blurRadius: 10,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class GlassToggleRow extends StatelessWidget {
  const GlassToggleRow({
    required this.title,
    required this.subtitle,
    required this.value,
    required this.onChanged,
    super.key,
  });

  final String title;
  final String subtitle;
  final bool value;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: () => onChanged(!value),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title,
                      style: const TextStyle(fontWeight: FontWeight.w800)),
                  const SizedBox(height: 2),
                  Text(subtitle, style: Theme.of(context).textTheme.bodySmall),
                ],
              ),
            ),
            const SizedBox(width: AppSpacing.x2),
            AnimatedContainer(
              duration: const Duration(milliseconds: 220),
              width: 48,
              height: 28,
              padding: const EdgeInsets.all(3),
              decoration: BoxDecoration(
                gradient: value
                    ? const LinearGradient(
                        colors: [AppPalette.teal, AppPalette.royalBlue],
                      )
                    : LinearGradient(
                        colors: [
                          colors.surfaceContainerHighest,
                          colors.surface.withValues(alpha: 0.55),
                        ],
                      ),
                borderRadius: BorderRadius.circular(18),
                border: Border.all(
                  color: Colors.white.withValues(alpha: 0.16),
                ),
              ),
              alignment: value ? Alignment.centerRight : Alignment.centerLeft,
              child: Container(
                width: 22,
                height: 22,
                decoration: BoxDecoration(
                  color: Colors.white,
                  shape: BoxShape.circle,
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.18),
                      blurRadius: 8,
                      offset: const Offset(0, 3),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _GlassTapSurface extends StatefulWidget {
  const _GlassTapSurface({
    required this.child,
    required this.onTap,
    required this.semanticLabel,
    required this.padding,
    this.selected = false,
    this.radius = AppRadius.control,
  });

  final Widget child;
  final VoidCallback? onTap;
  final String semanticLabel;
  final EdgeInsets padding;
  final bool selected;
  final double radius;

  @override
  State<_GlassTapSurface> createState() => _GlassTapSurfaceState();
}

class _GlassTapSurfaceState extends State<_GlassTapSurface> {
  var _pressed = false;
  var _hovered = false;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Semantics(
      button: true,
      enabled: widget.onTap != null,
      selected: widget.selected,
      label: widget.semanticLabel,
      child: MouseRegion(
        onEnter: (_) => setState(() => _hovered = true),
        onExit: (_) => setState(() => _hovered = false),
        child: Listener(
          onPointerDown: widget.onTap == null
              ? null
              : (_) => setState(() => _pressed = true),
          onPointerUp: widget.onTap == null
              ? null
              : (_) => setState(() => _pressed = false),
          onPointerCancel: widget.onTap == null
              ? null
              : (_) => setState(() => _pressed = false),
          child: GestureDetector(
            onTap: widget.onTap == null
                ? null
                : () {
                    HapticFeedback.selectionClick();
                    widget.onTap!();
                  },
            child: AnimatedScale(
              scale: _pressed ? 0.965 : (_hovered ? 1.025 : 1),
              duration: const Duration(milliseconds: 150),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(widget.radius),
                child: BackdropFilter(
                  filter: ImageFilter.blur(sigmaX: 24, sigmaY: 24),
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 190),
                    padding: widget.padding,
                    decoration: BoxDecoration(
                      color: widget.selected ? const Color(0xFFEDE4FF) : null,
                      gradient: widget.selected
                          ? null
                          : LinearGradient(
                              colors: [
                                Colors.white.withValues(
                                  alpha: Theme.of(context).brightness ==
                                          Brightness.dark
                                      ? 0.075
                                      : 0.5,
                                ),
                                colors.surface.withValues(alpha: 0.3),
                              ],
                            ),
                      borderRadius: BorderRadius.circular(widget.radius),
                      border: Border.all(
                        color: Colors.white.withValues(
                          alpha: Theme.of(context).brightness == Brightness.dark
                              ? 0.09
                              : 0.58,
                        ),
                      ),
                      boxShadow: _hovered
                          ? [
                              BoxShadow(
                                color: colors.primary.withValues(alpha: 0.12),
                                blurRadius: 18,
                                offset: const Offset(0, 7),
                              ),
                            ]
                          : null,
                    ),
                    child: widget.child,
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class SectionTitle extends StatelessWidget {
  const SectionTitle({
    required this.title,
    this.subtitle,
    this.trailing,
    super.key,
  });

  final String title;
  final String? subtitle;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: Theme.of(
                  context,
                ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800),
              ),
              if (subtitle != null) ...[
                const SizedBox(height: 2),
                Text(
                  subtitle!,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ],
          ),
        ),
        if (trailing != null) trailing!,
      ],
    );
  }
}

class EmptyState extends StatelessWidget {
  const EmptyState({
    required this.icon,
    required this.title,
    required this.message,
    this.action,
    super.key,
  });

  final IconData icon;
  final String title;
  final String message;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 48, color: Theme.of(context).colorScheme.primary),
            const SizedBox(height: 14),
            Text(
              title,
              textAlign: TextAlign.center,
              style: Theme.of(
                context,
              ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 6),
            Text(
              message,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            if (action != null) ...[const SizedBox(height: 18), action!],
          ],
        ),
      ),
    );
  }
}

class MetricTile extends StatelessWidget {
  const MetricTile({
    required this.label,
    required this.value,
    required this.icon,
    required this.color,
    super.key,
  });

  final String label;
  final String value;
  final IconData icon;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      padding: const EdgeInsets.all(14),
      child: Row(
        children: [
          Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  color.withValues(alpha: 0.22),
                  color.withValues(alpha: 0.08),
                ],
              ),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Icon(icon, color: color, size: 21),
          ),
          const SizedBox(width: 11),
          Expanded(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                TweenAnimationBuilder<double>(
                  tween: Tween(begin: 0, end: double.tryParse(value) ?? 0),
                  duration: const Duration(milliseconds: 650),
                  curve: Curves.easeOutCubic,
                  builder: (context, animated, _) => Text(
                    double.tryParse(value) == null
                        ? value
                        : '${animated.round()}',
                    style: Theme.of(context).textTheme.titleLarge?.copyWith(
                          fontWeight: FontWeight.w900,
                        ),
                  ),
                ),
                Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.labelSmall,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class ErrorPane extends StatelessWidget {
  const ErrorPane({required this.error, this.retry, super.key});

  final Object error;
  final VoidCallback? retry;

  @override
  Widget build(BuildContext context) {
    return EmptyState(
      icon: Icons.cloud_off_rounded,
      title: 'Could not reach the server',
      message: '$error\nYour offline records are still available.',
      action: retry == null
          ? null
          : AppButton(
              onPressed: retry,
              icon: Icons.refresh_rounded,
              label: 'Try again',
              kind: AppButtonKind.secondary,
            ),
    );
  }
}

class GlassLoadingList extends StatefulWidget {
  const GlassLoadingList({this.itemCount = 4, super.key});
  final int itemCount;

  @override
  State<GlassLoadingList> createState() => _GlassLoadingListState();
}

class _GlassLoadingListState extends State<GlassLoadingList>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1100),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.page,
        AppSpacing.x1,
        AppSpacing.page,
        AppSpacing.x3,
      ),
      itemCount: widget.itemCount,
      separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.x2),
      itemBuilder: (_, index) => GlassPanel(
        child: AnimatedBuilder(
          animation: _controller,
          builder: (_, __) {
            final color = Color.lerp(
              colors.surfaceContainerHighest.withValues(alpha: 0.45),
              colors.surfaceContainerHighest.withValues(alpha: 0.85),
              _controller.value,
            )!;
            return Row(
              children: [
                Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    color: color,
                    borderRadius: BorderRadius.circular(15),
                  ),
                ),
                const SizedBox(width: AppSpacing.x2),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      FractionallySizedBox(
                        widthFactor: 0.68,
                        child: Container(
                          height: 13,
                          decoration: BoxDecoration(
                            color: color,
                            borderRadius: BorderRadius.circular(7),
                          ),
                        ),
                      ),
                      const SizedBox(height: 10),
                      FractionallySizedBox(
                        widthFactor: 0.42,
                        child: Container(
                          height: 10,
                          decoration: BoxDecoration(
                            color: color,
                            borderRadius: BorderRadius.circular(6),
                          ),
                        ),
                      ),
                    ],
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

enum AppNoticeKind { success, warning, error, info }

void showAppNotice(
  BuildContext context, {
  required String message,
  AppNoticeKind kind = AppNoticeKind.info,
}) {
  final colors = Theme.of(context).colorScheme;
  final tone = switch (kind) {
    AppNoticeKind.success => const Color(0xFF087F5B),
    AppNoticeKind.warning => const Color(0xFFD97706),
    AppNoticeKind.error => colors.error,
    AppNoticeKind.info => colors.primary,
  };
  final icon = switch (kind) {
    AppNoticeKind.success => Icons.check_circle_outline_rounded,
    AppNoticeKind.warning => Icons.warning_amber_rounded,
    AppNoticeKind.error => Icons.error_outline_rounded,
    AppNoticeKind.info => Icons.info_outline_rounded,
  };
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(
      SnackBar(
        behavior: SnackBarBehavior.floating,
        backgroundColor: Colors.transparent,
        elevation: 0,
        margin: const EdgeInsets.all(AppSpacing.x2),
        padding: EdgeInsets.zero,
        content: ClipRRect(
          borderRadius: BorderRadius.circular(AppRadius.control),
          child: BackdropFilter(
            filter: ImageFilter.blur(sigmaX: 28, sigmaY: 28),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 15, vertical: 13),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    colors.surface.withValues(alpha: 0.88),
                    tone.withValues(alpha: 0.12),
                  ],
                ),
                borderRadius: BorderRadius.circular(AppRadius.control),
                border: Border.all(color: tone.withValues(alpha: 0.3)),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.2),
                    blurRadius: 24,
                    offset: const Offset(0, 10),
                  ),
                ],
              ),
              child: Row(
                children: [
                  Icon(icon, color: tone),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      message,
                      style: TextStyle(
                        color: colors.onSurface,
                        fontWeight: FontWeight.w700,
                      ),
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

class AppDialogShell extends StatelessWidget {
  const AppDialogShell({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.content,
    required this.actions,
    super.key,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final Widget content;
  final List<Widget> actions;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Dialog(
      insetPadding: const EdgeInsets.all(AppSpacing.page),
      backgroundColor: Colors.transparent,
      elevation: 0,
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 520),
        child: GlassPanel(
          padding: const EdgeInsets.all(AppSpacing.x3),
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    color: colors.primaryContainer,
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Icon(icon, color: colors.onPrimaryContainer),
                ),
                const SizedBox(height: AppSpacing.x2),
                Text(
                  title,
                  style: Theme.of(
                    context,
                  ).textTheme.headlineSmall?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                ),
                const SizedBox(height: 4),
                Text(
                  subtitle,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: colors.onSurfaceVariant,
                      ),
                ),
                const SizedBox(height: AppSpacing.x3),
                content,
                const SizedBox(height: AppSpacing.x3),
                Align(
                  alignment: Alignment.centerRight,
                  child: Wrap(
                    alignment: WrapAlignment.end,
                    spacing: AppSpacing.x1,
                    runSpacing: AppSpacing.x1,
                    children: actions,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

Future<T?> showGlassBottomSheet<T>(
  BuildContext context, {
  required WidgetBuilder builder,
  bool isScrollControlled = true,
}) {
  return showModalBottomSheet<T>(
    context: context,
    isScrollControlled: isScrollControlled,
    useSafeArea: true,
    barrierColor: Colors.black.withValues(alpha: 0.38),
    backgroundColor: Colors.transparent,
    builder: (context) => ClipRRect(
      borderRadius: const BorderRadius.vertical(
        top: Radius.circular(AppRadius.sheet),
      ),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 32, sigmaY: 32),
        child: Container(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                Colors.white.withValues(
                  alpha: Theme.of(context).brightness == Brightness.dark
                      ? 0.1
                      : 0.78,
                ),
                Theme.of(context).colorScheme.surface.withValues(
                      alpha: Theme.of(context).brightness == Brightness.dark
                          ? 0.76
                          : 0.62,
                    ),
              ],
            ),
            borderRadius: const BorderRadius.vertical(
              top: Radius.circular(AppRadius.sheet),
            ),
            border: Border(
              top: BorderSide(
                color: Colors.white.withValues(
                  alpha: Theme.of(context).brightness == Brightness.dark
                      ? 0.1
                      : 0.7,
                ),
              ),
            ),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const SizedBox(height: 10),
              Container(
                width: 42,
                height: 4,
                decoration: BoxDecoration(
                  color: Theme.of(context)
                      .colorScheme
                      .onSurfaceVariant
                      .withValues(alpha: 0.34),
                  borderRadius: BorderRadius.circular(4),
                ),
              ),
              Flexible(child: builder(context)),
            ],
          ),
        ),
      ),
    ),
  );
}

Future<bool> showAppConfirmation(
  BuildContext context, {
  required String title,
  required String subtitle,
  String confirmLabel = 'Confirm',
  bool danger = false,
}) async {
  final result = await showGeneralDialog<bool>(
    context: context,
    barrierDismissible: true,
    barrierLabel: 'Dismiss dialog',
    barrierColor: Colors.black.withValues(alpha: 0.42),
    transitionDuration: const Duration(milliseconds: 220),
    pageBuilder: (context, _, __) => AppDialogShell(
      icon: danger ? Icons.warning_amber_rounded : Icons.help_outline_rounded,
      title: title,
      subtitle: subtitle,
      content: const SizedBox.shrink(),
      actions: [
        AppButton(
          label: 'Cancel',
          kind: AppButtonKind.ghost,
          onPressed: () => Navigator.pop(context, false),
        ),
        AppButton(
          label: confirmLabel,
          kind: danger ? AppButtonKind.danger : AppButtonKind.primary,
          onPressed: () => Navigator.pop(context, true),
        ),
      ],
    ),
    transitionBuilder: (_, animation, __, child) => FadeTransition(
      opacity: animation,
      child: ScaleTransition(
        scale: Tween(begin: 0.96, end: 1.0).animate(
          CurvedAnimation(parent: animation, curve: Curves.easeOutCubic),
        ),
        child: child,
      ),
    ),
  );
  return result ?? false;
}

Route<T> appRoute<T>(Widget page) {
  return PageRouteBuilder<T>(
    pageBuilder: (_, animation, __) => page,
    transitionDuration: const Duration(milliseconds: 280),
    reverseTransitionDuration: const Duration(milliseconds: 220),
    transitionsBuilder: (_, animation, secondaryAnimation, child) {
      final fade = CurvedAnimation(
        parent: animation,
        curve: Curves.easeOutCubic,
      );
      final slide = Tween<Offset>(
        begin: const Offset(0.04, 0),
        end: Offset.zero,
      ).animate(fade);
      return FadeTransition(
        opacity: fade,
        child: SlideTransition(position: slide, child: child),
      );
    },
  );
}
