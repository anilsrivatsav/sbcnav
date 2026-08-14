import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import '../lib/features/works/works_screen.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('works register preserves the source section totals', () async {
    final pack = jsonDecode(await rootBundle.loadString(
        'assets/offline_station_pack.json')) as Map<String, dynamic>;
    final rows = (pack['all_works'] as List).cast<Map>();
    final counts = <String, int>{};
    for (final raw in rows) {
      final section = workSection(Map<String, dynamic>.from(raw));
      counts[section] = (counts[section] ?? 0) + 1;
    }
    expect(counts, equals({
      'North': 37,
      'West': 37,
      'GSU/SBC': 24,
      'East': 20,
      'South': 14,
      'Division': 8,
      'CAO/CN': 5,
      'Sr.DCM': 3,
      'Sr.DSTE': 3,
      'Sr.DEE': 1,
    }));
    expect(counts.values.fold<int>(0, (sum, value) => sum + value), 152);
  });

  test('every work is assigned exactly one visible work type', () async {
    final pack = jsonDecode(await rootBundle.loadString(
        'assets/offline_station_pack.json')) as Map<String, dynamic>;
    final rows = (pack['all_works'] as List)
        .map((raw) => Map<String, dynamic>.from(raw as Map))
        .toList();
    final types = rows.map(workCategory).toList();
    expect(types.length, 152);
    expect(types.every((type) => type.trim().isNotEmpty), isTrue);
    expect(types.toSet().length, greaterThan(1));
  });
}
