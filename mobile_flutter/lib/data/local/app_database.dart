import 'dart:convert';
import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';
import 'package:path/path.dart';
import 'package:sqflite/sqflite.dart';
import 'package:uuid/uuid.dart';

final databaseProvider = Provider<AppDatabase>(
  (_) => throw StateError('AppDatabase must be initialized before use'),
);

class AppDatabase {
  Database? _db;
  final _uuid = const Uuid();

  Database get db {
    final value = _db;
    if (value == null) throw StateError('Database has not been opened');
    return value;
  }

  Future<void> open() async {
    final root = await getDatabasesPath();
    _db = await openDatabase(
      join(root, 'rail_inspect.db'),
      version: 5,
      onConfigure: (database) => database.execute('PRAGMA foreign_keys = ON'),
      onUpgrade: (database, oldVersion, _) async {
        if (oldVersion < 2) {
          await database.execute(
            'CREATE INDEX IF NOT EXISTS ix_local_responses_inspection '
            'ON responses(inspection_id, section_code)',
          );
          await database.execute(
            'CREATE INDEX IF NOT EXISTS ix_local_sync_queue_entity '
            'ON sync_queue(entity_type, entity_id)',
          );
        }
        if (oldVersion < 3) {
          await _createFieldRecordTables(database);
        }
        if (oldVersion < 4) {
          await _createNotificationTable(database);
        }
        if (oldVersion < 5) {
          await _createSyncHistoryTable(database);
          await _addColumnIfMissing(
            database,
            'notifications',
            'station_code',
            'TEXT',
          );
          await _addColumnIfMissing(
            database,
            'notifications',
            'contract_name',
            'TEXT',
          );
          await _addColumnIfMissing(
            database,
            'notifications',
            'contract_code',
            'TEXT',
          );
        }
      },
      onCreate: (database, _) async {
        await database.execute('''
          CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
          )
        ''');
        await database.execute('''
          CREATE TABLE stations (
            station_code TEXT PRIMARY KEY,
            station_name TEXT,
            division TEXT,
            section TEXT,
            categorisation TEXT,
            number_of_platforms INTEGER,
            payload_json TEXT NOT NULL,
            cached_at TEXT NOT NULL
          )
        ''');
        await database.execute('''
          CREATE TABLE templates (
            template_id TEXT PRIMARY KEY,
            template_code TEXT NOT NULL,
            name TEXT NOT NULL,
            domain TEXT NOT NULL,
            version INTEGER NOT NULL,
            definition_json TEXT NOT NULL,
            cached_at TEXT NOT NULL
          )
        ''');
        await database.execute('''
          CREATE TABLE station_details (
            station_code TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            cached_at TEXT NOT NULL
          )
        ''');
        await database.execute('''
          CREATE TABLE inspections (
            inspection_id TEXT PRIMARY KEY,
            station_code TEXT NOT NULL,
            template_id TEXT NOT NULL,
            inspector_name TEXT NOT NULL,
            inspection_type TEXT NOT NULL,
            status TEXT NOT NULL,
            score INTEGER,
            remarks TEXT,
            device_id TEXT NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            client_updated_at TEXT NOT NULL,
            server_version INTEGER NOT NULL DEFAULT 0
          )
        ''');
        await database.execute(
          'CREATE INDEX ix_local_inspections_station ON inspections(station_code)',
        );
        await database.execute('''
          CREATE TABLE responses (
            response_id TEXT PRIMARY KEY,
            inspection_id TEXT NOT NULL,
            section_code TEXT NOT NULL,
            question_code TEXT NOT NULL,
            response_value TEXT,
            remarks TEXT,
            severity TEXT,
            asset_ref TEXT,
            platform TEXT,
            evidence_count INTEGER NOT NULL DEFAULT 0,
            response_json TEXT,
            client_updated_at TEXT NOT NULL,
            server_version INTEGER NOT NULL DEFAULT 0,
            UNIQUE(inspection_id, question_code, asset_ref),
            FOREIGN KEY(inspection_id) REFERENCES inspections(inspection_id) ON DELETE CASCADE
          )
        ''');
        await database.execute('''
          CREATE TABLE findings (
            finding_id TEXT PRIMARY KEY,
            inspection_id TEXT NOT NULL,
            response_id TEXT,
            station_code TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            severity TEXT NOT NULL,
            status TEXT NOT NULL,
            responsible_party TEXT,
            target_date TEXT,
            financial_implication INTEGER,
            repeat_observation INTEGER NOT NULL DEFAULT 0,
            client_updated_at TEXT NOT NULL,
            server_version INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(inspection_id) REFERENCES inspections(inspection_id) ON DELETE CASCADE
          )
        ''');
        await database.execute(
          'CREATE INDEX ix_local_findings_status ON findings(status, severity)',
        );
        await database.execute('''
          CREATE TABLE sync_queue (
            operation_id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            action TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            created_at TEXT NOT NULL
          )
        ''');
        await database.execute(
          'CREATE INDEX ix_local_responses_inspection '
          'ON responses(inspection_id, section_code)',
        );
        await database.execute(
          'CREATE INDEX ix_local_sync_queue_entity '
          'ON sync_queue(entity_type, entity_id)',
        );
        await _createFieldRecordTables(database);
        await _createNotificationTable(database);
        await _createSyncHistoryTable(database);
      },
    );
    await _seedBundledOfflinePack();
    await _ensureDeviceId();
  }

  Future<void> _seedBundledOfflinePack() async {
    final raw = await rootBundle.loadString(
      'assets/offline_station_pack.json',
    );
    final pack = jsonDecode(raw) as Map<String, dynamic>;
    final bundledVersion = '${pack['generated_at'] ?? ''}';
    final installedVersion = await metadata('bundled_offline_pack_at');
    final stationCount = Sqflite.firstIntValue(
          await db.rawQuery('SELECT COUNT(*) FROM stations'),
        ) ??
        0;
    final detailCount = await offlineStationDetailCount();
    if (stationCount > 0 &&
        detailCount > 0 &&
        bundledVersion.isNotEmpty &&
        bundledVersion == installedVersion) {
      return;
    }
    await cacheBootstrap(pack);
    final details = pack['station_details'] as List? ?? const [];
    await cacheStationDetails(
      details,
      total: (pack['stations'] as List? ?? const []).length,
    );
    await setMetadata(
      'bundled_offline_pack_at',
      pack['generated_at'] ?? DateTime.now().toUtc().toIso8601String(),
    );
  }

  static Future<void> _createFieldRecordTables(DatabaseExecutor db) async {
    await db.execute('''
      CREATE TABLE IF NOT EXISTS evidence (
        evidence_id TEXT PRIMARY KEY,
        inspection_id TEXT NOT NULL,
        response_id TEXT,
        question_code TEXT,
        local_path TEXT,
        mime_type TEXT NOT NULL,
        caption TEXT,
        context TEXT,
        created_at TEXT NOT NULL,
        client_updated_at TEXT NOT NULL,
        server_version INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY(inspection_id) REFERENCES inspections(inspection_id) ON DELETE CASCADE
      )
    ''');
    await db.execute(
      'CREATE INDEX IF NOT EXISTS ix_local_evidence_inspection '
      'ON evidence(inspection_id, question_code)',
    );
    await db.execute('''
      CREATE TABLE IF NOT EXISTS inspection_notes (
        note_id TEXT PRIMARY KEY,
        inspection_id TEXT NOT NULL,
        section_code TEXT,
        question_code TEXT,
        title TEXT NOT NULL,
        body TEXT NOT NULL,
        context TEXT,
        created_at TEXT NOT NULL,
        client_updated_at TEXT NOT NULL,
        server_version INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY(inspection_id) REFERENCES inspections(inspection_id) ON DELETE CASCADE
      )
    ''');
    await db.execute(
      'CREATE INDEX IF NOT EXISTS ix_local_notes_inspection '
      'ON inspection_notes(inspection_id, created_at)',
    );
  }

  Future<String> _ensureDeviceId() async {
    final current = await metadata('device_id');
    if (current != null) return current;
    final value = _uuid.v4();
    await setMetadata('device_id', value);
    return value;
  }

  Future<String> deviceId() => _ensureDeviceId();

  Future<String?> metadata(String key) async {
    final rows = await db.query('metadata', where: 'key = ?', whereArgs: [key]);
    return rows.isEmpty ? null : rows.first['value'] as String;
  }

  Future<void> setMetadata(String key, Object value) async {
    await db.insert(
        'metadata',
        {
          'key': key,
          'value': '$value',
        },
        conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<List<Map<String, dynamic>>> portfolioWorks() async {
    final raw = await metadata('portfolio_works_json');
    if (raw == null || raw.isEmpty) return const [];
    final decoded = jsonDecode(raw);
    if (decoded is! List) return const [];
    return decoded
        .whereType<Map>()
        .map((row) => Map<String, dynamic>.from(row))
        .toList();
  }

  Future<Map<String, dynamic>> portfolioTotals() async {
    final raw = await metadata('portfolio_totals_json');
    if (raw == null || raw.isEmpty) return const {};
    final decoded = jsonDecode(raw);
    return decoded is Map ? Map<String, dynamic>.from(decoded) : const {};
  }

  Future<void> cacheBootstrap(Map<String, dynamic> data) async {
    final now = DateTime.now().toUtc().toIso8601String();
    await db.transaction((txn) async {
      for (final raw in (data['stations'] as List? ?? const [])) {
        final station = Map<String, dynamic>.from(raw as Map);
        await txn.insert(
            'stations',
            {
              'station_code': station['station_code'],
              'station_name': station['station_name'],
              'division': station['division'],
              'section': station['section'],
              'categorisation': station['categorisation'],
              'number_of_platforms': station['number_of_platforms'],
              'payload_json': jsonEncode(station),
              'cached_at': now,
            },
            conflictAlgorithm: ConflictAlgorithm.replace);
      }
      for (final raw in (data['templates'] as List? ?? const [])) {
        final template = Map<String, dynamic>.from(raw as Map);
        await txn.insert(
            'templates',
            {
              'template_id': template['template_id'],
              'template_code': template['template_code'],
              'name': template['name'],
              'domain': template['domain'],
              'version': template['version'],
              'definition_json': jsonEncode(template['definition']),
              'cached_at': now,
            },
            conflictAlgorithm: ConflictAlgorithm.replace);
      }
      await txn.insert(
          'metadata',
          {
            'key': 'sync_cursor',
            'value': '${data['cursor'] ?? 0}',
          },
          conflictAlgorithm: ConflictAlgorithm.replace);
      if (data['all_works'] is List) {
        await txn.insert(
            'metadata',
            {
              'key': 'portfolio_works_json',
              'value': jsonEncode(data['all_works']),
            },
            conflictAlgorithm: ConflictAlgorithm.replace);
      }
      if (data['portfolio_totals'] is Map) {
        await txn.insert(
            'metadata',
            {
              'key': 'portfolio_totals_json',
              'value': jsonEncode(data['portfolio_totals']),
            },
            conflictAlgorithm: ConflictAlgorithm.replace);
      }
      await txn.insert(
          'metadata',
          {
            'key': 'last_sync_at',
            'value': now,
          },
          conflictAlgorithm: ConflictAlgorithm.replace);
    });
  }

  Future<List<Map<String, dynamic>>> stations({String search = ''}) async {
    final query = search.trim().toLowerCase();
    final rows = await db.query(
      'stations',
      where: query.isEmpty
          ? null
          : '''LOWER(station_code) LIKE ? OR LOWER(station_name) LIKE ?
               OR LOWER(division) LIKE ? OR LOWER(section) LIKE ?''',
      whereArgs: query.isEmpty ? null : List.filled(4, '%$query%'),
      orderBy: 'station_name, station_code',
    );
    return rows
        .map(
          (row) =>
              jsonDecode(row['payload_json'] as String) as Map<String, dynamic>,
        )
        .toList();
  }

  Future<List<Map<String, dynamic>>> stationOverviewRows({
    String search = '',
  }) async {
    final query = search.trim().toLowerCase();
    final rows = await db.rawQuery(
      '''
      SELECT s.payload_json AS station_json,
             d.payload_json AS detail_json
      FROM stations s
      LEFT JOIN station_details d ON d.station_code = s.station_code
      ${query.isEmpty ? '' : '''
      WHERE LOWER(s.station_code) LIKE ?
         OR LOWER(s.station_name) LIKE ?
         OR LOWER(s.division) LIKE ?
         OR LOWER(s.section) LIKE ?
      '''}
      ORDER BY s.station_name, s.station_code
      ''',
      query.isEmpty ? null : List.filled(4, '%$query%'),
    );
    return rows.map((row) {
      final station =
          jsonDecode(row['station_json'] as String) as Map<String, dynamic>;
      final detailJson = row['detail_json'] as String?;
      return {
        ...station,
        if (detailJson != null)
          '_station_detail': jsonDecode(detailJson) as Map<String, dynamic>,
      };
    }).toList();
  }

  Future<Map<String, dynamic>?> station(String stationCode) async {
    final rows = await db.query(
      'stations',
      where: 'station_code = ?',
      whereArgs: [stationCode],
      limit: 1,
    );
    if (rows.isEmpty) return null;
    return jsonDecode(rows.first['payload_json'] as String)
        as Map<String, dynamic>;
  }

  Future<void> cacheStationDetail(
    String stationCode,
    Map<String, dynamic> detail,
  ) async {
    await db.insert(
        'station_details',
        {
          'station_code': stationCode,
          'payload_json': jsonEncode(detail),
          'cached_at': DateTime.now().toUtc().toIso8601String(),
        },
        conflictAlgorithm: ConflictAlgorithm.replace);
    await _createContractNotifications(db, stationCode, detail);
  }

  Future<void> cacheStationDetails(
    List<dynamic> items, {
    required int total,
  }) async {
    final now = DateTime.now().toUtc().toIso8601String();
    await db.transaction((txn) async {
      for (final raw in items) {
        final item = Map<String, dynamic>.from(raw as Map);
        final code = '${item['station_code']}'.trim().toUpperCase();
        final detail = item['detail'];
        if (code.isEmpty || detail is! Map) continue;
        await txn.insert(
          'station_details',
          {
            'station_code': code,
            'payload_json': jsonEncode(detail),
            'cached_at': now,
          },
          conflictAlgorithm: ConflictAlgorithm.replace,
        );
        await _createContractNotifications(txn, code, detail);
      }
      final count = Sqflite.firstIntValue(
            await txn.rawQuery('SELECT COUNT(*) FROM station_details'),
          ) ??
          0;
      await txn.insert(
        'metadata',
        {'key': 'offline_station_details_count', 'value': '$count'},
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
      await txn.insert(
        'metadata',
        {'key': 'offline_station_details_total', 'value': '$total'},
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
      await txn.insert(
        'metadata',
        {'key': 'offline_station_details_at', 'value': now},
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
    });
  }

  Future<int> offlineStationDetailCount() async {
    return Sqflite.firstIntValue(
          await db.rawQuery('SELECT COUNT(*) FROM station_details'),
        ) ??
        0;
  }

  Future<List<Map<String, dynamic>>> notifications({bool unreadOnly = false}) {
    return db.query(
      'notifications',
      where: unreadOnly ? 'is_read = 0' : null,
      orderBy: 'created_at DESC',
    );
  }

  Future<List<Map<String, dynamic>>> contractNotificationsForStation(
    String stationCode,
  ) {
    return db.query(
      'notifications',
      where: 'type = ? AND station_code = ?',
      whereArgs: ['contract_expiry', stationCode],
      orderBy: 'due_at',
    );
  }

  Future<int> unreadNotificationCount() async {
    return Sqflite.firstIntValue(
          await db
              .rawQuery('SELECT COUNT(*) FROM notifications WHERE is_read = 0'),
        ) ??
        0;
  }

  Future<void> markNotificationRead(String notificationId) async {
    await db.update('notifications', {'is_read': 1},
        where: 'notification_id = ?', whereArgs: [notificationId]);
  }

  Future<void> markAllNotificationsRead() async {
    await db.update('notifications', {'is_read': 1});
  }

  static Future<void> _createNotificationTable(DatabaseExecutor db) async {
    await db.execute('''
      CREATE TABLE IF NOT EXISTS notifications (
        notification_id TEXT PRIMARY KEY,
        type TEXT NOT NULL,
        title TEXT NOT NULL,
        body TEXT NOT NULL,
        related_type TEXT,
        related_id TEXT,
        station_code TEXT,
        contract_name TEXT,
        contract_code TEXT,
        severity TEXT NOT NULL,
        is_read INTEGER NOT NULL DEFAULT 0,
        due_at TEXT,
        created_at TEXT NOT NULL
      )
    ''');
    await db.execute(
      'CREATE INDEX IF NOT EXISTS ix_local_notifications_read '
      'ON notifications(is_read, created_at)',
    );
  }

  static Future<void> _createSyncHistoryTable(DatabaseExecutor db) async {
    await db.execute('''
      CREATE TABLE IF NOT EXISTS sync_history (
        sync_id INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at TEXT NOT NULL,
        completed_at TEXT NOT NULL,
        status TEXT NOT NULL,
        pushed INTEGER NOT NULL DEFAULT 0,
        failed INTEGER NOT NULL DEFAULT 0,
        pulled INTEGER NOT NULL DEFAULT 0,
        error_message TEXT
      )
    ''');
    await db.execute(
      'CREATE INDEX IF NOT EXISTS ix_local_sync_history_completed '
      'ON sync_history(completed_at DESC)',
    );
  }

  static Future<void> _addColumnIfMissing(
    DatabaseExecutor db,
    String table,
    String column,
    String definition,
  ) async {
    final columns = await db.rawQuery('PRAGMA table_info($table)');
    if (columns.any((row) => row['name'] == column)) return;
    await db.execute('ALTER TABLE $table ADD COLUMN $column $definition');
  }

  static Future<void> _createContractNotifications(
    DatabaseExecutor db,
    String stationCode,
    Object? rawDetail,
  ) async {
    if (rawDetail is! Map) return;
    final detail = Map<String, dynamic>.from(rawDetail);
    final contracts = <dynamic>[
      ...(detail['contracts'] is List ? detail['contracts'] as List : const []),
      ...(detail['commercial_contracts'] is List
          ? detail['commercial_contracts'] as List
          : const []),
    ];
    final now = DateTime.now();
    final activeIds = <String>{};
    for (final raw in contracts) {
      if (raw is! Map) continue;
      final row = Map<String, dynamic>.from(raw);
      final end = _notificationDate(
        row['valid_to'] ??
            row['contract_to'] ??
            row['contract_upto'] ??
            row['contract_period_to'],
      );
      if (end == null) continue;
      final days =
          end.difference(DateTime(now.year, now.month, now.day)).inDays;
      if (days > 50) continue;
      final bucket = days < 0
          ? 'expired'
          : days <= 1
              ? '1d'
              : days <= 5
                  ? '5d'
                  : days <= 10
                      ? '10d'
                      : days <= 30
                          ? '30d'
                          : '50d';
      final key =
          '${row['unit_no'] ?? row['contract_key'] ?? row['contract_name'] ?? 'contract'}';
      final id = 'contract-expiry-$stationCode-$key-$bucket';
      activeIds.add(id);
      final name =
          '${row['contract_name'] ?? row['licensee_name'] ?? row['unit_no'] ?? 'Contract'}';
      final body = days < 0
          ? '$name expired ${-days} days ago at $stationCode.'
          : '$name expires in $days days at $stationCode.';
      await db.insert(
        'notifications',
        {
          'notification_id': id,
          'type': 'contract_expiry',
          'title': days < 0 ? 'Contract expired' : 'Contract renewal due',
          'body': body,
          'related_type': 'contract',
          'related_id': key,
          'station_code': stationCode,
          'contract_name': name,
          'contract_code': key,
          'severity': days < 0 || days <= 10
              ? 'critical'
              : days <= 30
                  ? 'high'
                  : 'medium',
          'is_read': 0,
          'due_at': end.toIso8601String(),
          'created_at': DateTime.now().toUtc().toIso8601String(),
        },
        conflictAlgorithm: ConflictAlgorithm.ignore,
      );
      await db.update(
        'notifications',
        {
          'title': days < 0 ? 'Contract expired' : 'Contract renewal due',
          'body': body,
          'station_code': stationCode,
          'contract_name': name,
          'contract_code': key,
          'severity': days < 0 || days <= 10
              ? 'critical'
              : days <= 30
                  ? 'high'
                  : 'medium',
          'due_at': end.toIso8601String(),
        },
        where: 'notification_id = ?',
        whereArgs: [id],
      );
    }
    final existing = await db.query(
      'notifications',
      columns: ['notification_id'],
      where: 'notification_id LIKE ?',
      whereArgs: ['contract-expiry-$stationCode-%'],
    );
    for (final row in existing) {
      final id = '${row['notification_id']}';
      if (!activeIds.contains(id)) {
        await db.delete('notifications',
            where: 'notification_id = ?', whereArgs: [id]);
      }
    }
  }

  static DateTime? _notificationDate(Object? value) {
    final text = value?.toString().trim() ?? '';
    if (text.isEmpty || text == '-' || text.toLowerCase() == 'n/a') return null;
    final iso = DateTime.tryParse(text);
    if (iso != null) return DateTime(iso.year, iso.month, iso.day);
    final match =
        RegExp(r'^(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})').firstMatch(text);
    if (match != null) {
      final yearValue = int.parse(match.group(3)!);
      final year = yearValue < 100 ? 2000 + yearValue : yearValue;
      return DateTime(
          year, int.parse(match.group(2)!), int.parse(match.group(1)!));
    }
    for (final format in ['dd MMM yyyy', 'dd-MMM-yyyy']) {
      try {
        final parsed = DateFormat(format).parseStrict(text);
        return DateTime(parsed.year, parsed.month, parsed.day);
      } catch (_) {}
    }
    return null;
  }

  Future<Map<String, dynamic>?> stationDetail(String stationCode) async {
    final rows = await db.query(
      'station_details',
      where: 'station_code = ?',
      whereArgs: [stationCode],
      limit: 1,
    );
    if (rows.isEmpty) return null;
    return jsonDecode(rows.first['payload_json'] as String)
        as Map<String, dynamic>;
  }

  Future<List<Map<String, dynamic>>> templates() async {
    final rows = await db.query('templates', orderBy: 'name, version DESC');
    return rows
        .map(
          (row) => {
            ...row,
            'definition': jsonDecode(row['definition_json'] as String),
          },
        )
        .toList();
  }

  Future<Map<String, dynamic>?> template(String templateId) async {
    final rows = await db.query(
      'templates',
      where: 'template_id = ?',
      whereArgs: [templateId],
      limit: 1,
    );
    if (rows.isEmpty) return null;
    return {
      ...rows.first,
      'definition': jsonDecode(rows.first['definition_json'] as String),
    };
  }

  Future<String> createInspection({
    required String stationCode,
    required String templateId,
    required String inspectorName,
    String inspectionType = 'scheduled',
  }) async {
    final now = DateTime.now().toUtc().toIso8601String();
    final id = _uuid.v4();
    final device = await deviceId();
    final row = {
      'inspection_id': id,
      'station_code': stationCode,
      'template_id': templateId,
      'inspector_name': inspectorName.trim(),
      'inspection_type': inspectionType,
      'status': 'in_progress',
      'device_id': device,
      'started_at': now,
      'client_updated_at': now,
      'server_version': 0,
    };
    await db.transaction((txn) async {
      await txn.insert('inspections', row);
      await _queue(txn, 'inspection', id, row);
    });
    return id;
  }

  Future<List<Map<String, dynamic>>> inspections() {
    return db.rawQuery('''
      SELECT i.*,
        (SELECT COUNT(*) FROM responses r
          WHERE r.inspection_id = i.inspection_id) AS response_count,
        (SELECT COUNT(*) FROM findings f
          WHERE f.inspection_id = i.inspection_id AND f.status != 'closed')
          AS open_finding_count,
        (SELECT COUNT(*) FROM evidence e
          WHERE e.inspection_id = i.inspection_id) AS evidence_count,
        (SELECT COUNT(*) FROM inspection_notes n
          WHERE n.inspection_id = i.inspection_id) AS note_count
      FROM inspections i
      ORDER BY i.client_updated_at DESC
    ''');
  }

  Future<Map<String, dynamic>?> inspection(String id) async {
    final rows = await db.query(
      'inspections',
      where: 'inspection_id = ?',
      whereArgs: [id],
      limit: 1,
    );
    return rows.isEmpty ? null : rows.first;
  }

  Future<List<Map<String, dynamic>>> responses(String inspectionId) {
    return db.query(
      'responses',
      where: 'inspection_id = ?',
      whereArgs: [inspectionId],
      orderBy: 'section_code, question_code',
    );
  }

  Future<String> saveResponse({
    required String inspectionId,
    required String sectionCode,
    required String questionCode,
    required String value,
    String? remarks,
    String? severity,
    String? platform,
  }) async {
    final existing = await db.query(
      'responses',
      columns: ['response_id'],
      where: 'inspection_id = ? AND question_code = ? AND asset_ref IS NULL',
      whereArgs: [inspectionId, questionCode],
      limit: 1,
    );
    final id =
        existing.isEmpty ? _uuid.v4() : existing.first['response_id'] as String;
    final now = DateTime.now().toUtc().toIso8601String();
    final row = {
      'response_id': id,
      'inspection_id': inspectionId,
      'section_code': sectionCode,
      'question_code': questionCode,
      'response_value': value,
      'remarks': remarks,
      'severity': severity,
      'platform': platform,
      'evidence_count': 0,
      'client_updated_at': now,
      'server_version': 0,
    };
    await db.transaction((txn) async {
      await txn.insert(
        'responses',
        row,
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
      await txn.update(
        'inspections',
        {'client_updated_at': now},
        where: 'inspection_id = ?',
        whereArgs: [inspectionId],
      );
      await _queue(txn, 'response', id, row);
    });
    return id;
  }

  Future<void> completeInspection(
    String inspectionId,
    int score, {
    String? remarks,
  }) async {
    final now = DateTime.now().toUtc().toIso8601String();
    await db.transaction((txn) async {
      final current = await txn.query(
        'inspections',
        where: 'inspection_id = ?',
        whereArgs: [inspectionId],
        limit: 1,
      );
      if (current.isEmpty || current.first['status'] == 'submitted') return;
      await txn.update(
        'inspections',
        {
          'status': 'submitted',
          'score': score,
          'remarks': remarks?.trim().isEmpty == true ? null : remarks?.trim(),
          'completed_at': now,
          'client_updated_at': now,
        },
        where: 'inspection_id = ?',
        whereArgs: [inspectionId],
      );
      final rows = await txn.query(
        'inspections',
        where: 'inspection_id = ?',
        whereArgs: [inspectionId],
        limit: 1,
      );
      await _queue(txn, 'inspection', inspectionId, rows.first);
    });
  }

  Future<void> createFinding({
    required String inspectionId,
    required String responseId,
    required String stationCode,
    required String title,
    required String description,
    required String severity,
    String? responsibleParty,
    String? targetDate,
    int? financialImplication,
    bool repeatObservation = false,
  }) async {
    final existing = await db.query(
      'findings',
      columns: ['finding_id'],
      where: 'response_id = ?',
      whereArgs: [responseId],
      limit: 1,
    );
    final id =
        existing.isEmpty ? _uuid.v4() : existing.first['finding_id'] as String;
    final now = DateTime.now().toUtc().toIso8601String();
    final row = {
      'finding_id': id,
      'inspection_id': inspectionId,
      'response_id': responseId,
      'station_code': stationCode,
      'title': title,
      'description': description,
      'severity': severity,
      'status': 'open',
      'responsible_party': responsibleParty?.trim().isEmpty == true
          ? null
          : responsibleParty?.trim(),
      'target_date': targetDate,
      'financial_implication': financialImplication,
      'repeat_observation': repeatObservation ? 1 : 0,
      'client_updated_at': now,
      'server_version': 0,
    };
    await db.transaction((txn) async {
      await txn.insert(
        'findings',
        row,
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
      await _queue(txn, 'finding', id, {
        ...row,
        'repeat_observation': repeatObservation,
      });
    });
  }

  Future<void> resolveFindingForResponse(String responseId) async {
    final rows = await db.query(
      'findings',
      where: 'response_id = ? AND status != ?',
      whereArgs: [responseId, 'closed'],
    );
    if (rows.isEmpty) return;
    final now = DateTime.now().toUtc().toIso8601String();
    await db.transaction((txn) async {
      for (final finding in rows) {
        final id = '${finding['finding_id']}';
        await txn.update(
          'findings',
          {'status': 'closed', 'client_updated_at': now},
          where: 'finding_id = ?',
          whereArgs: [id],
        );
        final updated = await txn.query(
          'findings',
          where: 'finding_id = ?',
          whereArgs: [id],
          limit: 1,
        );
        await _queue(txn, 'finding', id, {
          ...updated.first,
          'repeat_observation': updated.first['repeat_observation'] == 1,
        });
      }
    });
  }

  Future<List<Map<String, dynamic>>> findingsForInspection(
    String inspectionId,
  ) {
    return db.query(
      'findings',
      where: 'inspection_id = ?',
      whereArgs: [inspectionId],
      orderBy:
          "CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 ELSE 2 END, client_updated_at DESC",
    );
  }

  Future<String> addEvidence({
    required String inspectionId,
    required String localPath,
    required String mimeType,
    String? responseId,
    String? questionCode,
    String? caption,
    String? context,
  }) async {
    final id = _uuid.v4();
    final now = DateTime.now().toUtc().toIso8601String();
    final row = {
      'evidence_id': id,
      'inspection_id': inspectionId,
      'response_id': responseId,
      'question_code': questionCode,
      'local_path': localPath,
      'mime_type': mimeType,
      'caption': caption?.trim().isEmpty == true ? null : caption?.trim(),
      'context': context?.trim().isEmpty == true ? null : context?.trim(),
      'created_at': now,
      'client_updated_at': now,
      'server_version': 0,
    };
    final bytes = await File(localPath).readAsBytes();
    await db.transaction((txn) async {
      await txn.insert('evidence', row);
      if (responseId != null) {
        await txn.rawUpdate(
          'UPDATE responses SET evidence_count = evidence_count + 1, '
          'client_updated_at = ? WHERE response_id = ?',
          [now, responseId],
        );
        final response = await txn.query(
          'responses',
          where: 'response_id = ?',
          whereArgs: [responseId],
          limit: 1,
        );
        if (response.isNotEmpty) {
          await _queue(txn, 'response', responseId, response.first);
        }
      }
      await _queue(txn, 'evidence', id, {
        ...row,
        'content_base64': base64Encode(bytes),
      });
    });
    return id;
  }

  Future<List<Map<String, dynamic>>> evidenceForInspection(
    String inspectionId,
  ) {
    return db.query(
      'evidence',
      where: 'inspection_id = ?',
      whereArgs: [inspectionId],
      orderBy: 'created_at DESC',
    );
  }

  Future<String> addInspectionNote({
    required String inspectionId,
    required String title,
    required String body,
    String? sectionCode,
    String? questionCode,
    String? context,
  }) async {
    final id = _uuid.v4();
    final now = DateTime.now().toUtc().toIso8601String();
    final row = {
      'note_id': id,
      'inspection_id': inspectionId,
      'section_code': sectionCode,
      'question_code': questionCode,
      'title': title.trim(),
      'body': body.trim(),
      'context': context?.trim().isEmpty == true ? null : context?.trim(),
      'created_at': now,
      'client_updated_at': now,
      'server_version': 0,
    };
    await db.transaction((txn) async {
      await txn.insert('inspection_notes', row);
      await _queue(txn, 'note', id, row);
    });
    return id;
  }

  Future<List<Map<String, dynamic>>> notesForInspection(String inspectionId) {
    return db.query(
      'inspection_notes',
      where: 'inspection_id = ?',
      whereArgs: [inspectionId],
      orderBy: 'created_at DESC',
    );
  }

  Future<List<Map<String, dynamic>>> findings() {
    return db.query(
      'findings',
      orderBy:
          "CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 ELSE 2 END, client_updated_at DESC",
    );
  }

  Future<List<Map<String, dynamic>>> findingsForStation(
    String stationCode, {
    bool openOnly = false,
  }) {
    return db.query(
      'findings',
      where: openOnly
          ? 'station_code = ? AND status NOT IN (?, ?)'
          : 'station_code = ?',
      whereArgs: openOnly ? [stationCode, 'verified', 'closed'] : [stationCode],
      orderBy:
          "CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, target_date, client_updated_at DESC",
    );
  }

  Future<List<Map<String, dynamic>>> inspectionsForStation(
    String stationCode,
  ) {
    return db.rawQuery(
      '''
      SELECT i.*,
        (SELECT COUNT(*) FROM findings f
          WHERE f.inspection_id = i.inspection_id
          AND f.status NOT IN ('verified', 'closed')) AS open_finding_count
      FROM inspections i
      WHERE i.station_code = ?
      ORDER BY i.client_updated_at DESC
      ''',
      [stationCode],
    );
  }

  Future<void> updateFindingLifecycle({
    required String findingId,
    required String status,
    String? responsibleParty,
    String? targetDate,
  }) async {
    const allowed = {
      'open',
      'assigned',
      'action_taken',
      'verification_due',
      'returned',
      'verified',
      'closed',
    };
    if (!allowed.contains(status)) {
      throw ArgumentError.value(status, 'status', 'Unsupported finding status');
    }
    final now = DateTime.now().toUtc().toIso8601String();
    await db.transaction((txn) async {
      await txn.update(
        'findings',
        {
          'status': status,
          'responsible_party': responsibleParty?.trim().isEmpty == true
              ? null
              : responsibleParty?.trim(),
          'target_date':
              targetDate?.trim().isEmpty == true ? null : targetDate?.trim(),
          'client_updated_at': now,
        },
        where: 'finding_id = ?',
        whereArgs: [findingId],
      );
      final rows = await txn.query(
        'findings',
        where: 'finding_id = ?',
        whereArgs: [findingId],
        limit: 1,
      );
      if (rows.isEmpty) throw StateError('Finding no longer exists');
      await _queue(txn, 'finding', findingId, {
        ...rows.first,
        'repeat_observation': rows.first['repeat_observation'] == 1,
      });
    });
  }

  Future<int> pendingCount() async {
    final result = Sqflite.firstIntValue(
      await db.rawQuery('SELECT COUNT(*) FROM sync_queue'),
    );
    return result ?? 0;
  }

  Future<List<Map<String, dynamic>>> pendingOperations({
    int limit = 200,
  }) async {
    final rows = await db.query(
      'sync_queue',
      orderBy: 'created_at',
      limit: limit,
    );
    return rows
        .map(
          (row) => {
            'operation_id': row['operation_id'],
            'entity_type': row['entity_type'],
            'entity_id': row['entity_id'],
            'action': row['action'],
            'payload': jsonDecode(row['payload_json'] as String),
          },
        )
        .toList();
  }

  Future<List<Map<String, dynamic>>> syncQueueItems({int limit = 100}) {
    return db.query(
      'sync_queue',
      columns: [
        'operation_id',
        'entity_type',
        'entity_id',
        'attempts',
        'last_error',
        'created_at',
      ],
      orderBy: 'CASE WHEN last_error IS NULL THEN 1 ELSE 0 END, created_at',
      limit: limit,
    );
  }

  Future<int> failedSyncCount() async {
    return Sqflite.firstIntValue(
          await db.rawQuery(
            'SELECT COUNT(*) FROM sync_queue WHERE last_error IS NOT NULL',
          ),
        ) ??
        0;
  }

  Future<void> retryFailedOperations() async {
    await db.update(
      'sync_queue',
      {'attempts': 0, 'last_error': null},
      where: 'last_error IS NOT NULL',
    );
  }

  Future<void> recordSyncHistory({
    required String startedAt,
    required String status,
    int pushed = 0,
    int failed = 0,
    int pulled = 0,
    String? errorMessage,
  }) async {
    await db.insert('sync_history', {
      'started_at': startedAt,
      'completed_at': DateTime.now().toUtc().toIso8601String(),
      'status': status,
      'pushed': pushed,
      'failed': failed,
      'pulled': pulled,
      'error_message': errorMessage,
    });
  }

  Future<List<Map<String, dynamic>>> syncHistory({int limit = 10}) {
    return db.query(
      'sync_history',
      orderBy: 'completed_at DESC',
      limit: limit,
    );
  }

  Future<void> markOperationsProcessed(Iterable<String> operationIds) async {
    await db.transaction((txn) async {
      for (final id in operationIds) {
        await txn.delete(
          'sync_queue',
          where: 'operation_id = ?',
          whereArgs: [id],
        );
      }
    });
  }

  Future<void> markSyncError(String operationId, String error) async {
    await db.rawUpdate(
      'UPDATE sync_queue SET attempts = attempts + 1, last_error = ? WHERE operation_id = ?',
      [error, operationId],
    );
  }

  Future<void> applyChanges(List<dynamic> changes, int cursor) async {
    await db.transaction((txn) async {
      for (final raw in changes) {
        final change = Map<String, dynamic>.from(raw as Map);
        final entity = '${change['entity_type']}';
        final action = '${change['action']}';
        final payload = Map<String, dynamic>.from(change['payload'] as Map);
        final table = switch (entity) {
          'inspection' => 'inspections',
          'response' => 'responses',
          'finding' => 'findings',
          'evidence' => 'evidence',
          'note' => 'inspection_notes',
          _ => null,
        };
        if (table == null) continue;
        final pending = await txn.query(
          'sync_queue',
          columns: ['operation_id'],
          where: 'entity_type = ? AND entity_id = ?',
          whereArgs: [entity, change['entity_id']],
          limit: 1,
        );
        if (pending.isNotEmpty) continue;
        final idKey = entity == 'note' ? 'note_id' : '${entity}_id';
        if (action == 'delete') {
          await txn.delete(
            table,
            where: '$idKey = ?',
            whereArgs: [change['entity_id']],
          );
        } else {
          final columns = await txn.rawQuery('PRAGMA table_info($table)');
          final allowed = columns.map((row) => row['name'] as String).toSet();
          final clean = {
            for (final entry in payload.entries)
              if (allowed.contains(entry.key) &&
                  entry.value is! Map &&
                  entry.value is! List)
                entry.key:
                    entry.value is bool ? (entry.value ? 1 : 0) : entry.value,
          };
          if (entity == 'evidence') {
            final existing = await txn.query(
              table,
              columns: ['evidence_id'],
              where: 'evidence_id = ?',
              whereArgs: [change['entity_id']],
              limit: 1,
            );
            if (existing.isNotEmpty) {
              await txn.update(
                table,
                clean,
                where: 'evidence_id = ?',
                whereArgs: [change['entity_id']],
              );
            } else {
              await txn.insert(table, clean);
            }
          } else {
            await txn.insert(
              table,
              clean,
              conflictAlgorithm: ConflictAlgorithm.replace,
            );
          }
        }
      }
      await txn.insert(
          'metadata',
          {
            'key': 'sync_cursor',
            'value': '$cursor',
          },
          conflictAlgorithm: ConflictAlgorithm.replace);
      await txn.insert(
          'metadata',
          {
            'key': 'last_sync_at',
            'value': DateTime.now().toUtc().toIso8601String(),
          },
          conflictAlgorithm: ConflictAlgorithm.replace);
    });
  }

  Future<void> _queue(
    DatabaseExecutor executor,
    String entityType,
    String entityId,
    Map<String, dynamic> payload,
  ) async {
    final existing = await executor.query(
      'sync_queue',
      columns: ['operation_id'],
      where: 'entity_type = ? AND entity_id = ? AND action = ?',
      whereArgs: [entityType, entityId, 'upsert'],
      orderBy: 'created_at',
      limit: 1,
    );
    if (existing.isNotEmpty) {
      await executor.update(
        'sync_queue',
        {
          'payload_json': jsonEncode(payload),
          'attempts': 0,
          'last_error': null,
        },
        where: 'operation_id = ?',
        whereArgs: [existing.first['operation_id']],
      );
      return;
    }
    await executor.insert('sync_queue', {
      'operation_id': _uuid.v4(),
      'entity_type': entityType,
      'entity_id': entityId,
      'action': 'upsert',
      'payload_json': jsonEncode(payload),
      'attempts': 0,
      'created_at': DateTime.now().toUtc().toIso8601String(),
    });
  }
}
