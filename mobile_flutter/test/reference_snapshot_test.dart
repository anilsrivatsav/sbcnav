import 'package:flutter_test/flutter_test.dart';
import 'package:rail_inspect/data/sync/reference_snapshot.dart';

void main() {
  final bootstrap = {
    'data_version': '2026-10-30',
    'all_works': [
      {'project_id': 'PH53-1'}
    ],
    'portfolio_totals': {'works': 1},
  };
  final units = {
    'items': [
      {'unit_no': 'CS-01', 'station_code': 'SBC', 'license_fee': '1305999'}
    ],
    'pagination': {'total': 1},
  };
  final works = {
    'items': [
      {
        'project_id': 'PH53-1',
        'station_codes': ['SBC', 'YPR']
      }
    ],
    'pagination': {'total': 1},
  };

  test('rejects partial downloads instead of replacing offline records', () {
    expect(
        () => ReferenceSnapshot.fromResponses(
            bootstrap,
            {
              ...units,
              'pagination': {'total': 369}
            },
            works),
        throwsStateError);
  });

  test('rejects a register that changed during the download', () {
    expect(
        () => ReferenceSnapshot.fromResponses({
              ...bootstrap,
              'all_works': [
                {'project_id': 'different'}
              ]
            }, units, works),
        throwsStateError);
  });

  test('rejects duplicate identifiers', () {
    expect(
        () => ReferenceSnapshot.fromResponses(
            bootstrap,
            {
              'items': [
                {'unit_no': 'CS-01'},
                {'unit_no': 'CS-01'}
              ],
              'pagination': {'total': 2},
            },
            works),
        throwsStateError);
  });

  test('refreshes only catering and works in cached station details', () {
    final snapshot = ReferenceSnapshot.fromResponses(bootstrap, units, works);
    final publicity = [
      {'contract_number': 'SBC-OOH-1', 'annual_license_fee': 500000}
    ];
    final before = {
      'contracts': publicity,
      'commercial_contracts': [
        {'id': 12}
      ],
      'amenities': {
        'platforms': [
          {'platform': '1'}
        ]
      },
      'units': [
        {'unit_no': 'old'}
      ],
      'works': [
        {'project_id': 'removed'}
      ],
    };
    final after = snapshot.updateStation('SBC', before);
    expect(after['contracts'], same(publicity));
    expect(after['commercial_contracts'], same(before['commercial_contracts']));
    expect(after['amenities'], same(before['amenities']));
    expect((after['units'] as List).single['license_fee'], '1305999');
    expect((after['works'] as List).single['project_id'], 'PH53-1');
    expect(snapshot.updateStation('YPR', before)['units'], isEmpty);
    expect(snapshot.updateStation('YPR', before)['works'], hasLength(1));
  });
}
