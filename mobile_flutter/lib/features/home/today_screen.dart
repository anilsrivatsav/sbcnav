import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/local/app_database.dart';
import '../../data/sync/sync_service.dart';
import '../../shared/widgets.dart';
import '../inspections/inspection_form_screen.dart';
import '../notifications/notifications_screen.dart';
import '../settings/settings_screen.dart';

class TodayScreen extends ConsumerStatefulWidget {
  const TodayScreen({required this.onNavigate, super.key});

  final ValueChanged<int> onNavigate;

  @override
  ConsumerState<TodayScreen> createState() => _TodayScreenState();
}

class _TodayData {
  const _TodayData({
    required this.stations,
    required this.inspections,
    required this.openFindings,
    required this.pendingSync,
    required this.inspector,
    required this.unreadNotifications,
  });

  final int stations;
  final List<Map<String, dynamic>> inspections;
  final int openFindings;
  final int pendingSync;
  final String inspector;
  final int unreadNotifications;

  int get completed =>
      inspections.where((row) => row['status'] == 'submitted').length;
  int get pending => inspections.length - completed;
}

class _TodayScreenState extends ConsumerState<TodayScreen> {
  late Future<_TodayData> _data;

  @override
  void initState() {
    super.initState();
    _data = _load();
  }

  Future<_TodayData> _load() async {
    final database = ref.read(databaseProvider);
    final inspections = await database.inspections();
    final profileName = await database.metadata('profile_name');
    return _TodayData(
      stations: (await database.stations()).length,
      inspections: inspections,
      openFindings: (await database.findings())
          .where((row) => row['status'] != 'closed')
          .length,
      pendingSync: await database.pendingCount(),
      unreadNotifications: await database.unreadNotificationCount(),
      inspector: profileName ??
          (inspections.isEmpty
              ? 'Commercial Inspector'
              : '${inspections.first['inspector_name']}'),
    );
  }

  void _refresh() => setState(() => _data = _load());

  @override
  Widget build(BuildContext context) {
    ref.listen(syncControllerProvider, (_, __) => _refresh());
    final sync = ref.watch(syncControllerProvider);
    final syncBusy = sync.isLoading || sync.asData?.value.busy == true;
    return RefreshIndicator(
      onRefresh: () async {
        _refresh();
        await _data;
      },
      child: FutureBuilder<_TodayData>(
        future: _data,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting &&
              !snapshot.hasData) {
            return const GlassLoadingList(itemCount: 5);
          }
          if (snapshot.hasError) {
            return ErrorPane(error: snapshot.error!, retry: _refresh);
          }
          final data = snapshot.data!;
          final progress = data.inspections.isEmpty
              ? 0.0
              : data.completed / data.inspections.length;
          return ListView(
            physics: const ClampingScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(18, 18, 18, 28),
            children: [
      _HomeHeader(
                inspector: data.inspector,
                syncBusy: syncBusy,
                pendingSync: data.pendingSync,
                unreadNotifications: data.unreadNotifications,
                onSync: () =>
                    ref.read(syncControllerProvider.notifier).synchronize(),
                onFetchLatest: () => ref
                    .read(syncControllerProvider.notifier)
                    .refreshFromServer(),
                onNotifications: () => showGlassBottomSheet<void>(
                  context,
                  builder: (_) => const NotificationsSheet(),
                ),
              ),
              const SizedBox(height: 22),
              _InspectionPulse(data: data),
              const SizedBox(height: 18),
              Row(
                children: [
                  Expanded(
                    child: _InspectionMetric(
                      icon: Icons.assignment_outlined,
                      label: "Today's inspections",
                      value: '${data.inspections.length}',
                      caption: 'Scheduled',
                      tone: const Color(0xFF2268E8),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: _InspectionMetric(
                      icon: Icons.schedule_rounded,
                      label: 'Pending',
                      value: '${data.pending}',
                      caption: 'Inspections',
                      tone: const Color(0xFFF59E0B),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: _InspectionMetric(
                      icon: Icons.check_circle_outline_rounded,
                      label: 'Completed',
                      value: '${data.completed}',
                      caption: 'Inspections',
                      tone: const Color(0xFF0A9B67),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 24),
              const _HomeSectionTitle(title: 'Quick actions'),
              const SizedBox(height: 12),
              SizedBox(
                height: 112,
                child: ListView(
                  scrollDirection: Axis.horizontal,
                  clipBehavior: Clip.none,
                  children: [
                    _QuickAction(
                      icon: Icons.add_box_outlined,
                      label: 'New\ninspection',
                      tone: const Color(0xFF2268E8),
                      onTap: () => widget.onNavigate(2),
                    ),
                    _QuickAction(
                      icon: Icons.search_rounded,
                      label: 'Station\nsearch',
                      tone: const Color(0xFF0A9B67),
                      onTap: () => widget.onNavigate(1),
                    ),
                    _QuickAction(
                      icon: Icons.bar_chart_rounded,
                      label: 'Findings',
                      tone: const Color(0xFFF59E0B),
                      onTap: () => widget.onNavigate(3),
                    ),
                    _QuickAction(
                      icon: Icons.auto_awesome_rounded,
                      label: 'AI\nassistant',
                      tone: const Color(0xFF7C4DFF),
                      onTap: () => widget.onNavigate(4),
                    ),
                    _QuickAction(
                      icon: Icons.sync_rounded,
                      label: 'Offline\nsync',
                      tone: const Color(0xFF0EA5B7),
                      onTap: syncBusy
                          ? null
                          : () => ref
                              .read(syncControllerProvider.notifier)
                              .synchronize(),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 26),
              _HomeSectionTitle(
                title: 'Recent inspections',
                action: TextButton(
                  onPressed: () => widget.onNavigate(2),
                  child: const Text('View all'),
                ),
              ),
              const SizedBox(height: 8),
              if (data.inspections.isEmpty)
                _SoftCard(
                  child: Column(
                    children: [
                      const Icon(
                        Icons.fact_check_outlined,
                        size: 36,
                        color: Color(0xFF2268E8),
                      ),
                      const SizedBox(height: 8),
                      const Text(
                        'No inspections yet',
                        style: TextStyle(fontWeight: FontWeight.w800),
                      ),
                      const SizedBox(height: 4),
                      const Text(
                        'Start an offline inspection from Quick actions.',
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 12),
                      AppButton(
                        onPressed: () => widget.onNavigate(2),
                        icon: Icons.add_rounded,
                        label: 'Start inspection',
                      ),
                    ],
                  ),
                )
              else
                for (final row in data.inspections.take(4))
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: _RecentInspection(
                      row: row,
                      onOpen: () async {
                        await Navigator.of(context).push(
                          appRoute(
                            InspectionFormScreen(
                              inspectionId: '${row['inspection_id']}',
                            ),
                          ),
                        );
                        _refresh();
                      },
                    ),
                  ),
              const SizedBox(height: 16),
              Row(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Expanded(
                    flex: 3,
                    child: _SoftCard(
                      child: Row(
                        children: [
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                const Text(
                                  'Monthly progress',
                                  style: TextStyle(
                                    fontSize: 16,
                                    fontWeight: FontWeight.w900,
                                  ),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  '${data.completed} of ${data.inspections.length} inspections',
                                  style: Theme.of(context).textTheme.bodySmall,
                                ),
                              ],
                            ),
                          ),
                          SizedBox(
                            width: 64,
                            height: 64,
                            child: Stack(
                              alignment: Alignment.center,
                              children: [
                                CircularProgressIndicator(
                                  value: progress,
                                  strokeWidth: 7,
                                  strokeCap: StrokeCap.round,
                                  backgroundColor: Theme.of(context)
                                      .colorScheme
                                      .outlineVariant,
                                  color: const Color(0xFF2268E8),
                                ),
                                Text(
                                  '${(progress * 100).round()}%',
                                  style: const TextStyle(
                                    fontWeight: FontWeight.w900,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    flex: 2,
                    child: _SoftCard(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          _MiniCount(
                            icon: Icons.warning_amber_rounded,
                            label: 'Open findings',
                            value: data.openFindings,
                            tone: const Color(0xFFF59E0B),
                          ),
                          const Divider(height: 18),
                          _MiniCount(
                            icon: Icons.cloud_upload_outlined,
                            label: 'To sync',
                            value: data.pendingSync,
                            tone: const Color(0xFF0EA5B7),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
              if (data.stations == 0) ...[
                const SizedBox(height: 16),
                AppButton(
                  expand: true,
                  loading: syncBusy,
                  onPressed: syncBusy
                      ? null
                      : () =>
                          ref.read(syncControllerProvider.notifier).bootstrap(),
                  icon: Icons.download_for_offline_rounded,
                  label: 'Download stations for offline use',
                ),
              ],
            ],
          );
        },
      ),
    );
  }
}

class _HomeHeader extends StatelessWidget {
  const _HomeHeader({
    required this.inspector,
    required this.syncBusy,
    required this.pendingSync,
    required this.unreadNotifications,
    required this.onSync,
    required this.onFetchLatest,
    required this.onNotifications,
  });

  final String inspector;
  final bool syncBusy;
  final int pendingSync;
  final int unreadNotifications;
  final VoidCallback onSync;
  final VoidCallback onFetchLatest;
  final VoidCallback onNotifications;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            AppIconButton(
              tooltip: 'Profile and settings',
              icon: Icons.menu_rounded,
              onPressed: () => showGlassBottomSheet<void>(
                context,
                builder: (_) => HomeActionsSheet(
                  onFetchLatest: onFetchLatest,
                  onSync: onSync,
                ),
              ),
            ),
            const SizedBox(width: 14),
            const Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Rail Inspect',
                    style: TextStyle(
                      color: Color(0xFF15358F),
                      fontSize: 23,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                  Text(
                    'Commercial Inspection Dashboard',
                    style: TextStyle(fontSize: 12),
                  ),
                ],
              ),
            ),
            Stack(
              clipBehavior: Clip.none,
              children: [
                AppIconButton(
                  tooltip: 'Notifications',
                  onPressed: onNotifications,
                  icon: Icons.notifications_none_rounded,
                ),
                if (unreadNotifications > 0)
                  Positioned(
                    right: -2,
                    top: -3,
                    child: Container(
                      padding: const EdgeInsets.all(4),
                      decoration: const BoxDecoration(
                        color: Color(0xFFE84855),
                        shape: BoxShape.circle,
                      ),
                      child: Text(
                        unreadNotifications > 9 ? '9+' : '$unreadNotifications',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 9,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                    ),
                  ),
              ],
            ),
            const SizedBox(width: 6),
            AppIconButton(
              tooltip: 'Fetch latest data from PostgreSQL',
              icon: Icons.cloud_download_outlined,
              onPressed: syncBusy ? null : onFetchLatest,
            ),
            const SizedBox(width: 6),
          ],
        ),
        const SizedBox(height: 26),
        Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Good morning,',
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    inspector,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                          fontWeight: FontWeight.w900,
                        ),
                  ),
                ],
              ),
            ),
            GestureDetector(
              onTap: () => showGlassBottomSheet<void>(
                context,
                builder: (_) => const ProfileSheet(),
              ),
              child: CircleAvatar(
                radius: 28,
                backgroundColor: const Color(0xFFDCEBFF),
                child: Icon(
                  Icons.person_rounded,
                  size: 32,
                  color: Theme.of(context).colorScheme.primary,
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }
}

class _InspectionPulse extends StatelessWidget {
  const _InspectionPulse({required this.data});

  final _TodayData data;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 17),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            Color(0xFF3A9DF5),
            Color(0xFF9D4EDD),
            Color(0xFFF15BB5),
          ],
        ),
        borderRadius: BorderRadius.circular(25),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFF9D4EDD).withValues(alpha: 0.24),
            blurRadius: 24,
            offset: const Offset(0, 12),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Expanded(
                child: Text(
                  'Inspection pulse',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 16,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              Icon(
                Icons.insights_rounded,
                color: Colors.white.withValues(alpha: 0.92),
              ),
            ],
          ),
          const SizedBox(height: 5),
          Text(
            '${data.stations} stations ready for field work',
            style: TextStyle(
              color: Colors.white.withValues(alpha: 0.84),
              fontSize: 12,
            ),
          ),
          const SizedBox(height: 18),
          Row(
            children: [
              _PulseValue(
                  label: 'Open findings', value: '${data.openFindings}'),
              _PulseValue(label: 'To sync', value: '${data.pendingSync}'),
              _PulseValue(label: 'Completed', value: '${data.completed}'),
            ],
          ),
          const SizedBox(height: 13),
          ClipRRect(
            borderRadius: BorderRadius.circular(10),
            child: LinearProgressIndicator(
              value: data.inspections.isEmpty
                  ? 0
                  : data.completed / data.inspections.length,
              minHeight: 7,
              backgroundColor: Colors.white.withValues(alpha: 0.25),
              color: Colors.white.withValues(alpha: 0.9),
            ),
          ),
        ],
      ),
    );
  }
}

class _PulseValue extends StatelessWidget {
  const _PulseValue({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            value,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 22,
              fontWeight: FontWeight.w900,
            ),
          ),
          Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              color: Colors.white.withValues(alpha: 0.82),
              fontSize: 10,
            ),
          ),
        ],
      ),
    );
  }
}

class _InspectionMetric extends StatelessWidget {
  const _InspectionMetric({
    required this.icon,
    required this.label,
    required this.value,
    required this.caption,
    required this.tone,
  });

  final IconData icon;
  final String label;
  final String value;
  final String caption;
  final Color tone;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minHeight: 150),
      padding: const EdgeInsets.all(13),
      decoration: _softDecoration(context),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              color: tone.withValues(alpha: 0.12),
              shape: BoxShape.circle,
            ),
            child: Icon(icon, color: tone, size: 21),
          ),
          const SizedBox(height: 10),
          Text(
            label,
            maxLines: 2,
            style: TextStyle(
              color: tone,
              fontSize: 11,
              fontWeight: FontWeight.w800,
            ),
          ),
          const Spacer(),
          Text(
            value,
            style: const TextStyle(fontSize: 27, fontWeight: FontWeight.w900),
          ),
          Text(caption, style: const TextStyle(fontSize: 11)),
        ],
      ),
    );
  }
}

class _QuickAction extends StatelessWidget {
  const _QuickAction({
    required this.icon,
    required this.label,
    required this.tone,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final Color tone;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 82,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 3),
        child: Semantics(
          button: true,
          label: label.replaceAll('\n', ' '),
          child: InkWell(
            onTap: onTap,
            borderRadius: BorderRadius.circular(17),
            child: Container(
              height: 104,
              padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 10),
              decoration: _softDecoration(context, radius: 17),
              child: Column(
                children: [
                  Container(
                    width: 38,
                    height: 38,
                    decoration: BoxDecoration(
                      color: tone.withValues(alpha: 0.12),
                      shape: BoxShape.circle,
                    ),
                    child: Icon(icon, size: 21, color: tone),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    label,
                    textAlign: TextAlign.center,
                    maxLines: 2,
                    style: const TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.w800,
                      height: 1.15,
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

class _RecentInspection extends StatelessWidget {
  const _RecentInspection({required this.row, required this.onOpen});

  final Map<String, dynamic> row;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) {
    final completed = row['status'] == 'submitted';
    return InkWell(
      onTap: onOpen,
      borderRadius: BorderRadius.circular(17),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: _softDecoration(context, radius: 17),
        child: Row(
          children: [
            CircleAvatar(
              radius: 20,
              backgroundColor: const Color(0xFFDCEBFF),
              child: Text(
                '${row['station_code']}',
                style: const TextStyle(
                  fontSize: 10,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${row['station_code']}',
                    style: const TextStyle(fontWeight: FontWeight.w900),
                  ),
                  Text(
                    '${row['inspection_type']}',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            ),
            StatusBadge(
              completed ? 'Completed' : 'Pending',
              tone:
                  completed ? const Color(0xFF0A9B67) : const Color(0xFFF59E0B),
            ),
            const SizedBox(width: 8),
            Text(
              shortDate(row['started_at']),
              style: Theme.of(context).textTheme.labelSmall,
            ),
          ],
        ),
      ),
    );
  }
}

class _HomeSectionTitle extends StatelessWidget {
  const _HomeSectionTitle({required this.title, this.action});

  final String title;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Text(
            title,
            style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w900),
          ),
        ),
        if (action != null) action!,
      ],
    );
  }
}

class _SoftCard extends StatelessWidget {
  const _SoftCard({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: _softDecoration(context),
      child: child,
    );
  }
}

class _MiniCount extends StatelessWidget {
  const _MiniCount({
    required this.icon,
    required this.label,
    required this.value,
    required this.tone,
  });

  final IconData icon;
  final String label;
  final int value;
  final Color tone;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, size: 20, color: tone),
        const SizedBox(width: 7),
        Expanded(
          child: Text(label, style: const TextStyle(fontSize: 11)),
        ),
        Text('$value', style: const TextStyle(fontWeight: FontWeight.w900)),
      ],
    );
  }
}

BoxDecoration _softDecoration(
  BuildContext context, {
  double radius = 20,
}) {
  final colors = Theme.of(context).colorScheme;
  final dark = Theme.of(context).brightness == Brightness.dark;
  return BoxDecoration(
    color: colors.surface,
    borderRadius: BorderRadius.circular(radius),
    border: Border.all(color: colors.outlineVariant.withValues(alpha: 0.7)),
    boxShadow: [
      BoxShadow(
        color: Colors.black.withValues(alpha: dark ? 0.28 : 0.09),
        blurRadius: 24,
        spreadRadius: -8,
        offset: const Offset(0, 10),
      ),
    ],
  );
}
