import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/local/app_database.dart';
import '../../shared/widgets.dart';

class NotificationsSheet extends ConsumerStatefulWidget {
  const NotificationsSheet({super.key});

  @override
  ConsumerState<NotificationsSheet> createState() => _NotificationsSheetState();
}

class _NotificationsSheetState extends ConsumerState<NotificationsSheet> {
  late Future<List<Map<String, dynamic>>> _rows;

  @override
  void initState() {
    super.initState();
    _rows = ref.read(databaseProvider).notifications();
  }

  void _reload() =>
      setState(() => _rows = ref.read(databaseProvider).notifications());

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(
            AppSpacing.page, AppSpacing.x2, AppSpacing.page, AppSpacing.x3),
        child: FutureBuilder<List<Map<String, dynamic>>>(
          future: _rows,
          builder: (context, snapshot) {
            final rows = snapshot.data ?? const <Map<String, dynamic>>[];
            return ListView(
              shrinkWrap: true,
              children: [
                Row(
                  children: [
                    const Expanded(
                      child: PageHeading(
                        title: 'Notifications',
                        subtitle: 'Renewals, payments and inspection actions',
                      ),
                    ),
                    if (rows.any((row) => row['is_read'] == 0))
                      TextButton(
                        onPressed: () async {
                          await ref
                              .read(databaseProvider)
                              .markAllNotificationsRead();
                          _reload();
                        },
                        child: const Text('Mark all read'),
                      ),
                  ],
                ),
                const SizedBox(height: AppSpacing.x2),
                if (snapshot.connectionState == ConnectionState.waiting)
                  const GlassLoadingList(itemCount: 3)
                else if (rows.isEmpty)
                  const EmptyState(
                    icon: Icons.notifications_none_rounded,
                    title: 'All clear',
                    message: 'No contract or inspection alerts are waiting.',
                  )
                else
                  for (final row in rows)
                    Padding(
                      padding: const EdgeInsets.only(bottom: AppSpacing.x1),
                      child: _NotificationRow(
                        row: row,
                        onTap: () async {
                          await ref.read(databaseProvider).markNotificationRead(
                              '${row['notification_id']}');
                          _reload();
                        },
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

class _NotificationRow extends StatelessWidget {
  const _NotificationRow({required this.row, required this.onTap});

  final Map<String, dynamic> row;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final read = row['is_read'] == 1;
    final severity = '${row['severity'] ?? 'medium'}';
    final color = switch (severity) {
      'critical' => const Color(0xFFB91C1C),
      'high' => const Color(0xFFEA580C),
      _ => const Color(0xFFD97706),
    };
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(18),
      child: GlassPanel(
        padding: const EdgeInsets.all(14),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(
                read
                    ? Icons.notifications_none_rounded
                    : Icons.notifications_active_rounded,
                color: read ? Theme.of(context).colorScheme.outline : color),
            const SizedBox(width: 11),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('${row['title']}',
                      style: const TextStyle(fontWeight: FontWeight.w900)),
                  const SizedBox(height: 4),
                  Text('${row['body']}'),
                ],
              ),
            ),
            if (!read)
              Container(
                  width: 8,
                  height: 8,
                  decoration:
                      BoxDecoration(color: color, shape: BoxShape.circle)),
          ],
        ),
      ),
    );
  }
}
