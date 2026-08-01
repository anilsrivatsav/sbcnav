import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../local/app_database.dart';
import '../remote/mobile_api.dart';

final syncServiceProvider = Provider<SyncService>(
  (ref) => SyncService(
    database: ref.watch(databaseProvider),
    api: ref.watch(mobileApiProvider),
  ),
);

final syncControllerProvider =
    AsyncNotifierProvider<SyncController, SyncSnapshot>(SyncController.new);

class SyncSnapshot {
  const SyncSnapshot({
    required this.pending,
    required this.offlineStationDetails,
    required this.offlineStationTotal,
    this.lastSyncAt,
    this.message = 'Ready',
    this.busy = false,
  });

  final int pending;
  final int offlineStationDetails;
  final int offlineStationTotal;
  final String? lastSyncAt;
  final String message;
  final bool busy;

  double? get offlineProgress => offlineStationTotal == 0
      ? null
      : (offlineStationDetails / offlineStationTotal).clamp(0, 1);
}

class SyncService {
  const SyncService({required this.database, required this.api});

  final AppDatabase database;
  final MobileApi api;

  Future<void> bootstrap({
    Future<void> Function(int cached, int total)? onProgress,
  }) async {
    final data = await api.bootstrap();
    await database.cacheBootstrap(data);
    var offset = 0;
    var hasMore = true;
    while (hasMore) {
      final page = await api.offlineStationDetails(offset: offset);
      final items = page['items'] as List? ?? const [];
      final total = (page['total'] as num?)?.toInt() ?? 0;
      await database.cacheStationDetails(items, total: total);
      final cached = await database.offlineStationDetailCount();
      if (onProgress != null) await onProgress(cached, total);
      final nextOffset = (page['next_offset'] as num?)?.toInt() ?? offset;
      hasMore = page['has_more'] == true;
      if (hasMore && nextOffset <= offset) {
        throw const MobileApiException(
          'Offline download stopped because the server returned an invalid page.',
        );
      }
      offset = nextOffset;
    }
  }

  Future<void> synchronize() async {
    final connectivity = await Connectivity().checkConnectivity();
    if (connectivity.every((item) => item == ConnectivityResult.none)) {
      throw const MobileApiException(
        'No network. Your work remains safely on this device.',
      );
    }

    final operations = await database.pendingOperations();
    if (operations.isNotEmpty) {
      final deviceId = await database.deviceId();
      final result = await api.push(deviceId, operations);
      final processed = (result['results'] as List? ?? const [])
          .where((item) => item is Map && item['status'] == 'processed')
          .map((item) => '${item['operation_id']}')
          .toList();
      await database.markOperationsProcessed(processed);
    }

    var cursor =
        int.tryParse(await database.metadata('sync_cursor') ?? '0') ?? 0;
    var hasMore = true;
    while (hasMore) {
      final result = await api.pull(cursor);
      final changes = result['changes'] as List? ?? const [];
      cursor = (result['cursor'] as num?)?.toInt() ?? cursor;
      await database.applyChanges(changes, cursor);
      hasMore = result['has_more'] == true;
    }
  }
}

class SyncController extends AsyncNotifier<SyncSnapshot> {
  AppDatabase get _database => ref.read(databaseProvider);
  SyncService get _sync => ref.read(syncServiceProvider);

  @override
  Future<SyncSnapshot> build() => _snapshot();

  Future<SyncSnapshot> _snapshot({
    String message = 'Ready',
    bool busy = false,
  }) async {
    return SyncSnapshot(
      pending: await _database.pendingCount(),
      offlineStationDetails: await _database.offlineStationDetailCount(),
      offlineStationTotal: int.tryParse(
            await _database.metadata('offline_station_details_total') ?? '0',
          ) ??
          0,
      lastSyncAt: await _database.metadata('last_sync_at'),
      message: message,
      busy: busy,
    );
  }

  Future<void> bootstrap() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() async {
      await _sync.bootstrap(
        onProgress: (cached, total) async {
          state = AsyncData(
            await _snapshot(
              message: 'Downloading station details $cached of $total',
              busy: true,
            ),
          );
        },
      );
      return _snapshot(message: 'All station details are available offline');
    });
  }

  /// Downloads the current PostgreSQL-backed station snapshot and replaces
  /// the cached station details while preserving local inspection work.
  Future<void> refreshFromServer() => bootstrap();

  Future<void> synchronize() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() async {
      await _sync.synchronize();
      return _snapshot(message: 'All changes synchronized');
    });
  }

  Future<void> refreshPending() async {
    state = AsyncData(await _snapshot());
  }
}
