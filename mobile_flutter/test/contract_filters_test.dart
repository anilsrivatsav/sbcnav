import 'package:flutter_test/flutter_test.dart';
import 'package:rail_inspect/features/contracts/contract_filters.dart';

void main() {
  final publicity = <Map<String, dynamic>>[
    {
      'status': 'running',
      'policy_code': 'RDN',
      'contract_number': 'SBC-RDN-KPN-26',
      'contract_name': 'RDN',
      'assets': [
        {'station_code': 'KPN'},
      ],
    },
    {
      'status': 'running',
      'policy_code': 'OOH',
      'contract_number': 'SBC-VGrdn-GR-1-2024',
      'contract_name': 'Vertical garden',
      'assets': [
        {'asset_name': 'Vertical Garden'},
      ],
    },
    {
      'status': 'cancelled',
      'policy_code': 'RDN',
      'contract_number': 'SBC-RDN-YPR-OLD',
      'contract_name': 'RDN',
      'assets': [
        {'station_code': 'YPR'},
      ],
    },
  ];

  test('Publicity defaults to running rows', () {
    expect(filterPublicityContracts(publicity), hasLength(2));
  });

  test('Policy matching uses exact values and contract-number tokens', () {
    final rows = filterPublicityContracts(publicity, policy: 'RDN');
    expect(rows, hasLength(1));
    expect(rows.single['contract_number'], 'SBC-RDN-KPN-26');
  });

  test('Station and asset matching compares complete asset labels', () {
    expect(filterPublicityContracts(publicity, asset: 'KPN'), hasLength(1));
    expect(filterPublicityContracts(publicity, asset: 'Vertical Garden'),
        hasLength(1));
    expect(filterPublicityContracts(publicity, asset: 'Vertical'), isEmpty);
  });

  test('Status, policy and station filters combine consistently', () {
    expect(
      filterPublicityContracts(
        publicity,
        status: 'running',
        policy: 'RDN',
        asset: 'KPN',
      ),
      hasLength(1),
    );
  });

  test('Catering type and station values match exactly', () {
    final units = <Map<String, dynamic>>[
      {
        'unit_no': 'CS-01',
        'station_code': 'SBC',
        'type_of_unit': 'CATERING',
        'unit_status': 'Operational',
        'licensee_name': 'Vendor',
      },
      {
        'unit_no': 'CS-02',
        'station_code': 'SBCA',
        'type_of_unit': 'CATERING PLUS',
        'unit_status': 'Operational',
        'licensee_name': 'Vendor',
      },
    ];
    final rows = filterCateringContracts(
      units,
      type: 'CATERING',
      station: 'SBC',
    );
    expect(rows, hasLength(1));
    expect(rows.single['unit_no'], 'CS-01');
  });
}
