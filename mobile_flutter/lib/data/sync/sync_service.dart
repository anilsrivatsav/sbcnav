import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../local/app_database.dart';
import '../remote/mobile_api.dart';
import 'reference_snapshot.dart';

final referenceRevisionProvider = StateProvider<int>((ref) => 0);

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
    required this.failed,
    required this.offlineStationDetails,
    required this.offlineStationTotal,
    required this.offlineWorks,
    this.queue = const [],
    this.history = const [],
    this.lastSyncAt,
    this.lastCateringSyncAt,
    this.lastWorksSyncAt,
    this.lastReferenceSyncAt,
    this.offlineCateringUnits = 0,
    this.dataVersion,
    this.message = 'Ready',
    this.busy = false,
  });

  final int pending;
  final int failed;
  final int offlineStationDetails;
  final int offlineStationTotal;
  final int offlineWorks;
  final List<Map<String, dynamic>> queue;
  final List<Map<String, dynamic>> history;
  final String? lastSyncAt;
  final String? lastCateringSyncAt;
  final String? lastWorksSyncAt;
  final String? lastReferenceSyncAt;
  final int offlineCateringUnits;
  final String? dataVersion;
  final String message;
  final bool busy;

  double? get offlineProgress => offlineStationTotal == 0
      ? null
      : (offlineStationDetails / offlineStationTotal).clamp(0, 1);
}

class SyncRunResult {
  const SyncRunResult({
    required this.pushed,
    required this.failed,
    required this.pulled,
  });

  final int pushed;
  final int failed;
  final int pulled;
}

class SyncService {
  SyncService({required this.database, required this.api});

  final AppDatabase database;
  final MobileApi api;
  Future<ReferenceSnapshot>? _referenceDownload;

  Future<ReferenceSnapshot> refreshReferenceData() => _referenceDownload ??=
      _downloadReferenceData().whenComplete(() => _referenceDownload = null);

  Future<ReferenceSnapshot> _downloadReferenceData() async {
    final responses = await Future.wait([
      api.bootstrap(),
      api.cateringUnits(),
      api.referenceWorks(),
    ]);
    final snapshot = ReferenceSnapshot.fromResponses(
        responses[0], responses[1], responses[2]);
    await database.cacheReferenceData(snapshot);
    return snapshot;
  }

  Future<void> _reportDeviceState() async {
    try {
      await api.updateDeviceState(
        await database.deviceId(),
        {
          'cached_stations': await database.cachedStationCount(),
          'cached_station_details': await database.offlineStationDetailCount(),
          'cached_works': (await database.portfolioWorks()).length,
          'cached_units': (await database.cateringUnits()).length,
          'cached_earnings': 0,
          'pending_operations': await database.pendingCount(),
          'failed_operations': await database.failedSyncCount(),
          'data_version': await database.metadata('data_version'),
          'cache_updated_at':
              await database.metadata('offline_station_details_at'),
          'last_sync_at': await database.metadata('last_sync_at'),
        },
      );
    } catch (_) {
      // Cache reporting must never make offline work or sync fail.
    }
  }

  Future<void> bootstrap({
    Future<void> Function(int cached, int total)? onProgress,
    String? section,
    List<String>? stationCodes,
  }) async {
    final data = await api.bootstrap();
    await database.cacheBootstrap(data);
    final selectionKey = [
      section?.trim() ?? '',
      ...(stationCodes ?? const <String>[])
          .map((code) => code.trim().toUpperCase()),
    ].join('|');
    final previousSelection =
        await database.metadata('offline_download_selection');
    var offset = previousSelection == selectionKey
        ? int.tryParse(
                await database.metadata('offline_download_offset') ?? '0') ??
            0
        : 0;
    await database.setMetadata('offline_download_selection', selectionKey);
    await database.setMetadata('offline_download_offset', '$offset');
    try {
      var hasMore = true;
      while (hasMore) {
        final page = await api.offlineStationDetails(
          offset: offset,
          section: section,
          stationCodes: stationCodes,
        );
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
        await database.setMetadata('offline_download_offset', '$offset');
      }
      await database.setMetadata('offline_download_offset', '0');
    } catch (_) {
      // Keep the last successful offset so the next download can resume.
      await database.setMetadata('offline_download_offset', '$offset');
      rethrow;
    }
    await _reportDeviceState();
  }

  Future<SyncRunResult> synchronize() async {
    final startedAt = DateTime.now().toUtc().toIso8601String();
    final connectivity = await Connectivity().checkConnectivity();
    if (connectivity.every((item) => item == ConnectivityResult.none)) {
      await database.recordSyncHistory(
        startedAt: startedAt,
        status: 'offline',
        errorMessage: 'No network connection',
      );
      throw const MobileApiException(
        'No network. Your work remains safely on this device.',
      );
    }

    final operations = await database.pendingOperations();
    var pushed = 0;
    var failed = 0;
    var pulled = 0;
    try {
      if (operations.isNotEmpty) {
        final deviceId = await database.deviceId();
        final result = await api.push(deviceId, operations);
        final results = result['results'] as List? ?? const [];
        final processed = <String>[];
        for (final raw in results) {
          if (raw is! Map) continue;
          final operationId = '${raw['operation_id'] ?? ''}';
          if (operationId.isEmpty) continue;
          if (raw['status'] == 'processed') {
            processed.add(operationId);
            pushed++;
          } else {
            failed++;
            await database.markSyncError(
              operationId,
              '${raw['message'] ?? 'The server rejected this record'}',
            );
            final conflict = raw['conflict'];
            if (conflict is Map) {
              await database.markSyncConflict(
                operationId,
                Map<String, dynamic>.from(conflict),
              );
            }
          }
        }
        await database.markOperationsProcessed(processed);
      }

      var cursor =
          int.tryParse(await database.metadata('sync_cursor') ?? '0') ?? 0;
      var hasMore = true;
      while (hasMore) {
        final result = await api.pull(cursor);
        final changes = result['changes'] as List? ?? const [];
        pulled += changes.length;
        cursor = (result['cursor'] as num?)?.toInt() ?? cursor;
        await database.applyChanges(changes, cursor);
        hasMore = result['has_more'] == true;
      }
      await database.recordSyncHistory(
        startedAt: startedAt,
        status: failed == 0 ? 'success' : 'partial',
        pushed: pushed,
        failed: failed,
        pulled: pulled,
      );
      await database.setMetadata(
        'last_sync_at',
        DateTime.now().toUtc().toIso8601String(),
      );
      await _reportDeviceState();
      return SyncRunResult(pushed: pushed, failed: failed, pulled: pulled);
    } catch (error) {
      for (final operation in operations) {
        await database.markSyncError(
          '${operation['operation_id']}',
          '$error',
        );
      }
      await database.recordSyncHistory(
        startedAt: startedAt,
        status: 'failed',
        pushed: pushed,
        failed: operations.length,
        pulled: pulled,
        errorMessage: '$error',
      );
      rethrow;
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
      failed: await _database.failedSyncCount(),
      offlineStationDetails: await _database.offlineStationDetailCount(),
      offlineStationTotal: int.tryParse(
            await _database.metadata('offline_station_details_total') ?? '0',
          ) ??
          0,
      lastSyncAt: await _database.metadata('last_sync_at'),
      lastCateringSyncAt: await _database.metadata('last_catering_sync_at'),
      lastWorksSyncAt: await _database.metadata('last_works_sync_at'),
      lastReferenceSyncAt: await _database.metadata('last_reference_sync_at'),
      offlineCateringUnits: (await _database.cateringUnits()).length,
      dataVersion: await _database.metadata('data_version'),
      offlineWorks: (await _database.portfolioWorks()).length,
      queue: await _database.syncQueueItems(),
      history: await _database.syncHistory(),
      message: message,
      busy: busy,
    );
  }

  Future<void> bootstrap({String? section, List<String>? stationCodes}) async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() async {
      await _sync.bootstrap(
        section: section,
        stationCodes: stationCodes,
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

  /// Refreshes catering and PH-53 works while preserving local inspection work.
  Future<void> refreshFromServer() async {
    state = AsyncData(await _snapshot(
        message: 'Updating catering and works from Oracle...', busy: true));
    try {
      final snapshot = await _sync.refreshReferenceData();
      ref.read(referenceRevisionProvider.notifier).state++;
      state = AsyncData(await _snapshot(
          message:
              '${snapshot.units.length} catering units and ${snapshot.works.length} works updated from Oracle'));
    } catch (error) {
      state = AsyncData(
          await _snapshot(message: 'Offline · saved data kept. $error'));
    }
  }

  Future<void> synchronize() async {
    state = const AsyncLoading();
    try {
      final result = await _sync.synchronize();
      state = AsyncData(
        await _snapshot(
          message: result.failed == 0
              ? '${result.pushed} uploaded, ${result.pulled} downloaded'
              : '${result.pushed} uploaded, ${result.failed} need attention',
        ),
      );
    } catch (error) {
      state = AsyncData(
        await _snapshot(message: 'Sync failed: $error'),
      );
    }
  }

  Future<void> retryFailed() async {
    await _database.retryFailedOperations();
    await synchronize();
  }

  Future<void> refreshPending() async {
    state = AsyncData(await _snapshot());
  }
}
