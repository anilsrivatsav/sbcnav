import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/sync/sync_service.dart';
import '../../shared/widgets.dart';

class SyncScreen extends ConsumerStatefulWidget {
  const SyncScreen({super.key});

  @override
  ConsumerState<SyncScreen> createState() => _SyncScreenState();
}

class _SyncScreenState extends ConsumerState<SyncScreen> {
  static const _sections = <String>[
    'All',
    'BNC WFD Section',
    'BWT Section',
    'HUP Section',
    'MYS Section',
    'NMGA-HAS',
    'SA Section',
    'SBC',
    'TK Section',
    'YNK-KQZ',
  ];

  String _section = 'All';
  final _stationCodesController = TextEditingController();

  @override
  void dispose() {
    _stationCodesController.dispose();
    super.dispose();
  }

  void _downloadSelection() {
    final codes = _stationCodesController.text
        .split(RegExp(r'[,\s]+'))
        .map((code) => code.trim().toUpperCase())
        .where((code) => code.isNotEmpty)
        .toSet()
        .toList();
    ref.read(syncControllerProvider.notifier).bootstrap(
          section: _section == 'All' ? null : _section,
          stationCodes: codes.isEmpty ? null : codes,
        );
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(syncControllerProvider);
    return ListView(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.page,
        AppSpacing.x3,
        AppSpacing.page,
        AppSpacing.x4,
      ),
      children: [
        const PageHeading(
          title: 'Sync',
          subtitle: 'Control what is downloaded and uploaded.',
        ),
        const SizedBox(height: AppSpacing.x3),
        state.when(
          loading: () => GlassPanel(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Synchronizing records',
                  style: Theme.of(
                    context,
                  ).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                ),
                const SizedBox(height: AppSpacing.x2),
                const GlassProgressBar(value: 0.7),
                const SizedBox(height: AppSpacing.x1),
                const Text('Your offline work remains available.'),
              ],
            ),
          ),
          error: (error, _) => ErrorPane(
            error: error,
            retry: () =>
                ref.read(syncControllerProvider.notifier).synchronize(),
          ),
          data: (value) => Column(
            children: [
              GlassPanel(
                child: Column(
                  children: [
                    Icon(
                      value.pending == 0
                          ? Icons.cloud_done_rounded
                          : Icons.cloud_upload_rounded,
                      size: 48,
                      color: Theme.of(context).colorScheme.primary,
                    ),
                    const SizedBox(height: AppSpacing.x2),
                    Text(
                      value.pending == 0
                          ? 'Device is up to date'
                          : '${value.pending} changes waiting',
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                            fontWeight: FontWeight.w800,
                          ),
                    ),
                    const SizedBox(height: 5),
                    Text(
                      value.lastSyncAt == null
                          ? 'No successful sync yet'
                          : 'Last sync ${shortDate(value.lastSyncAt)}',
                    ),
                    const SizedBox(height: 5),
                    Text(
                      value.message,
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                    if (value.dataVersion != null) ...[
                      const SizedBox(height: 5),
                      Text(
                        'Data version ${shortDate(value.dataVersion)}',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ],
                    if (value.failed > 0) ...[
                      const SizedBox(height: AppSpacing.x1),
                      StatusBadge(
                        '${value.failed} failed',
                        tone: const Color(0xFFB91C1C),
                      ),
                    ],
                    const SizedBox(height: AppSpacing.x3),
                    Text(
                      'Selective offline download',
                      style: Theme.of(context).textTheme.titleSmall?.copyWith(
                            fontWeight: FontWeight.w800,
                          ),
                    ),
                    const SizedBox(height: 6),
                    const Text(
                      'Choose a section or enter station codes. Existing cached data is preserved.',
                    ),
                    const SizedBox(height: AppSpacing.x2),
                    DropdownButtonFormField<String>(
                      value: _section,
                      decoration: const InputDecoration(
                        labelText: 'Section',
                        prefixIcon: Icon(Icons.account_tree_outlined),
                      ),
                      items: _sections
                          .map(
                            (section) => DropdownMenuItem<String>(
                              value: section,
                              child: Text(section),
                            ),
                          )
                          .toList(),
                      onChanged: (value) => setState(() => _section = value ?? 'All'),
                    ),
                    const SizedBox(height: AppSpacing.x1),
                    TextField(
                      controller: _stationCodesController,
                      textCapitalization: TextCapitalization.characters,
                      decoration: const InputDecoration(
                        labelText: 'Station codes (optional)',
                        hintText: 'SBC, KJM, YPR',
                        prefixIcon: Icon(Icons.location_on_outlined),
                      ),
                    ),
                    const SizedBox(height: AppSpacing.x2),
                    AppButton(
                      expand: true,
                      kind: AppButtonKind.secondary,
                      loading: value.busy,
                      onPressed: value.busy ? null : _downloadSelection,
                      icon: Icons.download_for_offline_rounded,
                      label: 'Download selected data',
                    ),
                    const SizedBox(height: AppSpacing.x2),
                    AppButton(
                      expand: true,
                      onPressed: () => ref
                          .read(syncControllerProvider.notifier)
                          .synchronize(),
                      icon: Icons.sync_rounded,
                      label: 'Sync now',
                    ),
                    const SizedBox(height: AppSpacing.x1),
                    AppButton(
                      expand: true,
                      kind: AppButtonKind.secondary,
                      onPressed: () => ref
                          .read(syncControllerProvider.notifier)
                          .refreshFromServer(),
                      icon: Icons.cloud_download_rounded,
                      label: 'Fetch latest PostgreSQL data',
                    ),
                    if (value.failed > 0) ...[
                      const SizedBox(height: AppSpacing.x1),
                      AppButton(
                        expand: true,
                        kind: AppButtonKind.secondary,
                        onPressed: () => ref
                            .read(syncControllerProvider.notifier)
                            .retryFailed(),
                        icon: Icons.replay_rounded,
                        label: 'Retry failed records',
                      ),
                    ],
                  ],
                ),
              ),
              const SizedBox(height: AppSpacing.x2),
              if (value.queue.isNotEmpty) ...[
                _SyncQueuePanel(rows: value.queue),
                const SizedBox(height: AppSpacing.x2),
              ],
              GlassPanel(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Station data',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w800,
                          ),
                    ),
                    const SizedBox(height: 6),
                    const Text(
                      'Download the station master, linked units, earnings, '
                      'works, contracts, platforms and passenger amenities. '
                      'Your drafts and findings are preserved.',
                    ),
                    const SizedBox(height: AppSpacing.x2),
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            '${value.offlineStationDetails} of '
                            '${value.offlineStationTotal == 0 ? 'all' : value.offlineStationTotal} '
                            'stations cached',
                            style: const TextStyle(
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                        ),
                        const Icon(Icons.offline_pin_outlined),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.x1),
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            '${value.offlineWorks} sanctioned works cached',
                            style: const TextStyle(fontWeight: FontWeight.w800),
                          ),
                        ),
                        const Icon(Icons.engineering_outlined),
                      ],
                    ),
                    if (value.offlineProgress != null) ...[
                      const SizedBox(height: AppSpacing.x1),
                      GlassProgressBar(value: value.offlineProgress!),
                    ],
                    const SizedBox(height: AppSpacing.x3),
                    AppButton(
                      expand: true,
                      kind: AppButtonKind.secondary,
                      loading: value.busy,
                      onPressed: value.busy
                          ? null
                          : () => ref
                              .read(syncControllerProvider.notifier)
                              .bootstrap(),
                      icon: Icons.download_rounded,
                      label: 'Download all for offline use',
                    ),
                  ],
                ),
              ),
              if (value.history.isNotEmpty) ...[
                const SizedBox(height: AppSpacing.x2),
                _SyncHistoryPanel(rows: value.history),
              ],
            ],
          ),
        ),
      ],
    );
  }
}

class _SyncQueuePanel extends StatelessWidget {
  const _SyncQueuePanel({required this.rows});

  final List<Map<String, dynamic>> rows;

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Upload queue',
            style: Theme.of(context)
                .textTheme
                .titleMedium
                ?.copyWith(fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 10),
          for (final row in rows.take(5)) ...[
            InkWell(
              borderRadius: BorderRadius.circular(12),
              onTap: row['conflict_json'] == null
                  ? null
                  : () => _showConflict(context, row),
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(
                  children: [
                    Icon(
                      row['last_error'] == null
                          ? Icons.schedule_rounded
                          : Icons.error_outline_rounded,
                      size: 18,
                      color: row['last_error'] == null
                          ? Theme.of(context).colorScheme.primary
                          : const Color(0xFFB91C1C),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            '${row['entity_type']} · ${_shortId(row['entity_id'])}',
                            style: const TextStyle(fontWeight: FontWeight.w800),
                          ),
                          if (row['last_error'] != null)
                            Text(
                              '${row['last_error']}',
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: Theme.of(context)
                                  .textTheme
                                  .bodySmall
                                  ?.copyWith(color: const Color(0xFFB91C1C)),
                            ),
                          if (row['conflict_json'] != null)
                            Text(
                              'Server version available for review',
                              style: Theme.of(context)
                                  .textTheme
                                  .bodySmall
                                  ?.copyWith(
                                    color: const Color(0xFF9A3412),
                                    fontWeight: FontWeight.w700,
                                  ),
                            ),
                        ],
                      ),
                    ),
                    if ((row['attempts'] as num?)?.toInt() != 0)
                      StatusBadge('${row['attempts']} tries'),
                  ],
                ),
              ),
            ),
            const Divider(height: 18),
          ],
          if (rows.length > 5)
            Text(
              '+ ${rows.length - 5} more queued records',
              style: Theme.of(context).textTheme.bodySmall,
            ),
        ],
      ),
    );
  }

  void _showConflict(BuildContext context, Map<String, dynamic> row) {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Server conflict'),
        content: SingleChildScrollView(
          child: SelectableText(
            'The server has a newer version of this ${row['entity_type']} record.\n\n'
            '${row['conflict_json']}',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }
}

class _SyncHistoryPanel extends StatelessWidget {
  const _SyncHistoryPanel({required this.rows});

  final List<Map<String, dynamic>> rows;

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Recent sync',
            style: Theme.of(context)
                .textTheme
                .titleMedium
                ?.copyWith(fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 10),
          for (final row in rows.take(3))
            Padding(
              padding: const EdgeInsets.only(bottom: 9),
              child: Row(
                children: [
                  StatusBadge(
                    '${row['status']}',
                    tone: row['status'] == 'success'
                        ? const Color(0xFF0A8F62)
                        : row['status'] == 'partial'
                            ? const Color(0xFFD97706)
                            : const Color(0xFFB91C1C),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      '${row['pushed']} up · ${row['pulled']} down · ${shortDate(row['completed_at'])}',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

String _shortId(Object? value) {
  final text = '${value ?? ''}';
  return text.length <= 8 ? text : text.substring(0, 8);
}
