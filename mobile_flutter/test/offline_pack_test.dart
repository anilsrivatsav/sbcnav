import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('bundled offline pack contains complete station details', () async {
    final raw = await rootBundle.loadString(
      'assets/offline_station_pack.json',
    );
    final pack = jsonDecode(raw) as Map<String, dynamic>;
    final stations = pack['stations'] as List;
    final details = pack['station_details'] as List;

    expect(stations, isNotEmpty);
    expect(details.length, stations.length);
    final totals = pack['portfolio_totals'] as Map;
    expect(totals['stations'], 132);
    expect(totals['works'], 152);
    expect((pack['all_works'] as List).length, 152);
    expect(
      details.every((item) {
        final detail = (item as Map)['detail'] as Map;
        return detail.containsKey('station') &&
            detail.containsKey('units') &&
            detail.containsKey('earnings') &&
            detail.containsKey('works') &&
            detail.containsKey('commercial_contracts') &&
            detail.containsKey('amenities');
      }),
      isTrue,
    );
  });
}
