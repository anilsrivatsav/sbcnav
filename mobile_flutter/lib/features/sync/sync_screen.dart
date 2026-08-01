import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/sync/sync_service.dart';
import '../../shared/widgets.dart';

class SyncScreen extends ConsumerWidget {
  const SyncScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
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
                    const SizedBox(height: AppSpacing.x3),
                    AppButton(
                      expand: true,
                      onPressed: () => ref
                          .read(syncControllerProvider.notifier)
                          .synchronize(),
                      icon: Icons.sync_rounded,
                      label: 'Sync now',
                    ),
                  ],
                ),
              ),
              const SizedBox(height: AppSpacing.x2),
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
            ],
          ),
        ),
      ],
    );
  }
}
