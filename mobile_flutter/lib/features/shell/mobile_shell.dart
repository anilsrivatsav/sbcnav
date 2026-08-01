import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../shared/widgets.dart';
import '../assistant/assistant_screen.dart';
import '../findings/findings_screen.dart';
import '../home/today_screen.dart';
import '../inspections/inspections_screen.dart';
import '../stations/stations_screen.dart';

class MobileShell extends StatefulWidget {
  const MobileShell({super.key});

  @override
  State<MobileShell> createState() => _MobileShellState();
}

class _MobileShellState extends State<MobileShell> {
  int _index = 0;
  var _exitDialogOpen = false;

  static const _destinations = [
    _Destination(
      label: 'Home',
      icon: Icons.home_outlined,
      selectedIcon: Icons.home_rounded,
    ),
    _Destination(
      label: 'Stations',
      icon: Icons.train_outlined,
      selectedIcon: Icons.train_rounded,
    ),
    _Destination(
      label: 'Inspect',
      icon: Icons.fact_check_outlined,
      selectedIcon: Icons.fact_check_rounded,
    ),
    _Destination(
      label: 'Findings',
      icon: Icons.bar_chart_outlined,
      selectedIcon: Icons.bar_chart_rounded,
    ),
    _Destination(
      label: 'AI',
      icon: Icons.auto_awesome_outlined,
      selectedIcon: Icons.auto_awesome_rounded,
    ),
  ];

  Future<void> _handleBack(bool didPop) async {
    if (didPop || _exitDialogOpen) return;
    _exitDialogOpen = true;
    final exit = await showAppConfirmation(
      context,
      title: 'Exit application?',
      subtitle:
          'Your offline work is already saved. Do you want to close Rail Inspect?',
      confirmLabel: 'Exit',
      danger: true,
    );
    _exitDialogOpen = false;
    if (exit) await SystemNavigator.pop();
  }

  void _select(int value) {
    if (value == _index) return;
    HapticFeedback.selectionClick();
    setState(() => _index = value);
  }

  @override
  Widget build(BuildContext context) {
    final pages = [
      TodayScreen(onNavigate: _select),
      const StationsScreen(),
      const InspectionsScreen(),
      const FindingsScreen(),
      const AssistantScreen(),
    ];
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) => _handleBack(didPop),
      child: RailBackground(
        child: LayoutBuilder(
          builder: (context, constraints) {
            final wide = constraints.maxWidth >= 800;
            return Scaffold(
              backgroundColor: Colors.transparent,
              body: SafeArea(
                child: Row(
                  children: [
                    if (wide)
                      Padding(
                        padding: const EdgeInsets.fromLTRB(16, 16, 0, 16),
                        child: _SideNavigation(
                          selectedIndex: _index,
                          destinations: _destinations,
                          onSelected: _select,
                        ),
                      ),
                    Expanded(
                      child: AnimatedSwitcher(
                        duration: const Duration(milliseconds: 240),
                        switchInCurve: Curves.easeOutCubic,
                        switchOutCurve: Curves.easeInCubic,
                        transitionBuilder: (child, animation) =>
                            FadeTransition(opacity: animation, child: child),
                        child: KeyedSubtree(
                          key: ValueKey(_index),
                          child: pages[_index],
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              bottomNavigationBar: wide
                  ? null
                  : _SoftNavigationBar(
                      selectedIndex: _index,
                      destinations: _destinations,
                      onSelected: _select,
                    ),
            );
          },
        ),
      ),
    );
  }
}

class _Destination {
  const _Destination({
    required this.label,
    required this.icon,
    required this.selectedIcon,
  });

  final String label;
  final IconData icon;
  final IconData selectedIcon;
}

class _SoftNavigationBar extends StatelessWidget {
  const _SoftNavigationBar({
    required this.selectedIndex,
    required this.destinations,
    required this.onSelected,
  });

  final int selectedIndex;
  final List<_Destination> destinations;
  final ValueChanged<int> onSelected;

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    return SafeArea(
      top: false,
      minimum: const EdgeInsets.fromLTRB(12, 0, 12, 10),
      child: Container(
        height: 78,
        padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 8),
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surface,
          borderRadius: BorderRadius.circular(22),
          border: Border.all(color: Colors.white.withValues(alpha: 0.78)),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: dark ? 0.32 : 0.12),
              blurRadius: 28,
              spreadRadius: -8,
              offset: const Offset(0, 12),
            ),
          ],
        ),
        child: Row(
          children: [
            for (var index = 0; index < destinations.length; index++)
              Expanded(
                child: _NavItem(
                  destination: destinations[index],
                  selected: index == selectedIndex,
                  onTap: () => onSelected(index),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _SideNavigation extends StatelessWidget {
  const _SideNavigation({
    required this.selectedIndex,
    required this.destinations,
    required this.onSelected,
  });

  final int selectedIndex;
  final List<_Destination> destinations;
  final ValueChanged<int> onSelected;

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 16),
      child: SizedBox(
        width: 92,
        child: Column(
          children: [
            Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    Theme.of(context).colorScheme.primary,
                    Theme.of(context).colorScheme.tertiary,
                  ],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(16),
                boxShadow: [
                  BoxShadow(
                    color: Theme.of(context)
                        .colorScheme
                        .tertiary
                        .withValues(alpha: 0.24),
                    blurRadius: 18,
                    offset: const Offset(0, 8),
                  ),
                ],
              ),
              child: Icon(
                Icons.directions_railway_rounded,
                color: Theme.of(context).colorScheme.onPrimary,
              ),
            ),
            const SizedBox(height: 24),
            for (var index = 0; index < destinations.length; index++) ...[
              _NavItem(
                destination: destinations[index],
                selected: index == selectedIndex,
                onTap: () => onSelected(index),
              ),
              const SizedBox(height: 8),
            ],
            const Spacer(),
            Text(
              'RAIL\nINSPECT',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    fontWeight: FontWeight.w800,
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
            ),
          ],
        ),
      ),
    );
  }
}

class _NavItem extends StatelessWidget {
  const _NavItem({
    required this.destination,
    required this.selected,
    required this.onTap,
  });

  final _Destination destination;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Tooltip(
      message: destination.label,
      child: Semantics(
        selected: selected,
        button: true,
        label: destination.label,
        child: GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTap: onTap,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 220),
            curve: Curves.easeOutCubic,
            constraints: const BoxConstraints(minHeight: 54),
            padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
            decoration: const BoxDecoration(),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                AnimatedContainer(
                  duration: const Duration(milliseconds: 220),
                  curve: Curves.easeOutCubic,
                  width: selected ? 54 : 44,
                  height: 32,
                  decoration: BoxDecoration(
                    color:
                        selected ? const Color(0xFFEDE4FF) : Colors.transparent,
                    borderRadius: BorderRadius.circular(18),
                  ),
                  child: Icon(
                    selected ? destination.selectedIcon : destination.icon,
                    color: selected
                        ? colors.primary
                        : _navigationTone(destination.label, colors),
                    size: 21,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  destination.label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: colors.onSurface,
                        fontWeight:
                            selected ? FontWeight.w900 : FontWeight.w700,
                      ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Color _navigationTone(String label, ColorScheme colors) {
    return switch (label) {
      'Home' => colors.tertiary,
      'Stations' => colors.primary,
      'Inspect' => colors.secondary,
      'Findings' => statusTone('pending'),
      _ => colors.primary,
    };
  }
}
