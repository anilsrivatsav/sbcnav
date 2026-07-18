import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

String textOf(dynamic value, {String fallback = 'NA'}) {
  if (value == null) return fallback;
  final text = value.toString().trim();
  return text.isEmpty ? fallback : text;
}

String moneyOf(dynamic value) {
  final number = num.tryParse(textOf(value, fallback: '0').replaceAll(',', '')) ?? 0;
  return NumberFormat.currency(locale: 'en_IN', symbol: 'INR ', decimalDigits: 0).format(number);
}

class GlassSurface extends StatelessWidget {
  const GlassSurface({
    required this.child,
    this.padding = const EdgeInsets.all(16),
    this.margin,
    super.key,
  });

  final Widget child;
  final EdgeInsets padding;
  final EdgeInsets? margin;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      margin: margin,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(28),
        border: Border.all(color: theme.colorScheme.outlineVariant.withOpacity(0.55)),
        color: theme.colorScheme.surface.withOpacity(0.72),
        boxShadow: [
          BoxShadow(
            color: theme.colorScheme.shadow.withOpacity(0.08),
            blurRadius: 28,
            offset: const Offset(0, 16),
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(28),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 14, sigmaY: 14),
          child: Padding(padding: padding, child: child),
        ),
      ),
    );
  }
}

class MetricCard extends StatelessWidget {
  const MetricCard({
    required this.label,
    required this.value,
    required this.icon,
    required this.color,
    this.subtitle,
    super.key,
  });

  final String label;
  final String value;
  final String? subtitle;
  final IconData icon;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return GlassSurface(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: color.withOpacity(0.14),
                  borderRadius: BorderRadius.circular(18),
                ),
                child: Icon(icon, color: color, size: 22),
              ),
              const Spacer(),
              Icon(Icons.chevron_right_rounded, color: theme.colorScheme.onSurfaceVariant),
            ],
          ),
          const SizedBox(height: 14),
          Text(
            value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: theme.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 4),
          Text(label, style: theme.textTheme.labelLarge?.copyWith(fontWeight: FontWeight.w800)),
          if (subtitle != null) ...[
            const SizedBox(height: 4),
            Text(subtitle!, maxLines: 2, overflow: TextOverflow.ellipsis, style: theme.textTheme.bodySmall),
          ],
        ],
      ),
    );
  }
}

class SearchBox extends StatelessWidget {
  const SearchBox({
    required this.value,
    required this.onChanged,
    this.hint = 'Search',
    super.key,
  });

  final String value;
  final ValueChanged<String> onChanged;
  final String hint;

  @override
  Widget build(BuildContext context) {
    return TextField(
      onChanged: onChanged,
      decoration: InputDecoration(
        hintText: hint,
        prefixIcon: const Icon(Icons.search_rounded),
        suffixIcon: value.isEmpty
            ? null
            : IconButton(
                icon: const Icon(Icons.close_rounded),
                onPressed: () => onChanged(''),
              ),
      ),
    );
  }
}

class SectionTitle extends StatelessWidget {
  const SectionTitle({
    required this.title,
    this.subtitle,
    this.action,
    super.key,
  });

  final String title;
  final String? subtitle;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900)),
              if (subtitle != null) Text(subtitle!, style: theme.textTheme.bodySmall),
            ],
          ),
        ),
        if (action != null) action!,
      ],
    );
  }
}

class InfoChip extends StatelessWidget {
  const InfoChip({
    required this.label,
    this.icon,
    this.tone,
    super.key,
  });

  final String label;
  final IconData? icon;
  final Color? tone;

  @override
  Widget build(BuildContext context) {
    final color = tone ?? Theme.of(context).colorScheme.primary;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withOpacity(0.25)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 15, color: color),
            const SizedBox(width: 5),
          ],
          ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 150),
            child: Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w800),
            ),
          ),
        ],
      ),
    );
  }
}

class KeyValueGrid extends StatelessWidget {
  const KeyValueGrid({required this.rows, super.key});

  final List<(String, dynamic)> rows;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Wrap(
      spacing: 10,
      runSpacing: 10,
      children: rows.map((row) {
        return Container(
          width: 155,
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: theme.colorScheme.surfaceContainerHighest.withOpacity(0.55),
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: theme.colorScheme.outlineVariant.withOpacity(0.6)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(row.$1.toUpperCase(), style: theme.textTheme.labelSmall?.copyWith(fontWeight: FontWeight.w900, letterSpacing: 0.7)),
              const SizedBox(height: 6),
              Text(textOf(row.$2), maxLines: 3, overflow: TextOverflow.ellipsis, style: theme.textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w800)),
            ],
          ),
        );
      }).toList(),
    );
  }
}

class LoadingPane extends StatelessWidget {
  const LoadingPane({super.key});

  @override
  Widget build(BuildContext context) {
    return const Center(child: CircularProgressIndicator());
  }
}

class EmptyPane extends StatelessWidget {
  const EmptyPane({required this.title, this.message, super.key});

  final String title;
  final String? message;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.inbox_rounded, size: 38, color: theme.colorScheme.onSurfaceVariant),
            const SizedBox(height: 10),
            Text(title, style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w900)),
            if (message != null) ...[
              const SizedBox(height: 4),
              Text(message!, textAlign: TextAlign.center, style: theme.textTheme.bodySmall),
            ],
          ],
        ),
      ),
    );
  }
}
