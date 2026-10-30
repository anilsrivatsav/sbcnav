import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../data/sync/sync_service.dart';

class ReferenceSyncBanner extends ConsumerWidget {
  const ReferenceSyncBanner({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(syncControllerProvider);
    final value = state.asData?.value;
    final busy = state.isLoading || value?.busy == true;
    final offline = value?.message.startsWith('Offline') == true;
    return Material(
      color: Theme.of(context).colorScheme.surface,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        child: Row(children: [
          Icon(offline ? Icons.cloud_off_outlined : Icons.cloud_done_outlined,
              size: 19,
              color: offline ? Colors.orange.shade700 : Colors.teal.shade700),
          const SizedBox(width: 10),
          Expanded(
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                Text(
                    busy
                        ? 'Updating from Oracle…'
                        : offline
                            ? 'Saved data · offline'
                            : 'Oracle data · available offline',
                    style: const TextStyle(
                        fontWeight: FontWeight.w700, fontSize: 12)),
                Text(
                    '${value?.offlineCateringUnits ?? 0} catering units · ${value?.offlineWorks ?? 0} works',
                    style: const TextStyle(fontSize: 12)),
              ])),
          if (busy)
            const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(strokeWidth: 2))
          else
            TextButton.icon(
              onPressed: () =>
                  ref.read(syncControllerProvider.notifier).refreshFromServer(),
              icon: const Icon(Icons.sync, size: 17),
              label: const Text('Refresh data'),
            ),
        ]),
      ),
    );
  }
}
