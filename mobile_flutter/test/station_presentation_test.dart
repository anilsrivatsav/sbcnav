import 'package:flutter_test/flutter_test.dart';
import 'package:rail_inspect/features/stations/station_presentation.dart';

void main() {
  group('station presentation', () {
    test('daily footfall is always annual footfall divided by 30', () {
      expect(dailyFootfallValue(3750000), 125000);
      expect(formatDailyFootfall(3750000), '1.25 Lakh');
    });

    test('total platforms uses the highest number in platform labels', () {
      final result = highestPlatformNumber([
        {'platform': 'PF 1'},
        {'platform': 'PF 2/3 (Island)'},
        {'platform': 'PF 4'},
        {'platform': 'PF 5'},
      ]);

      expect(result, 5);
    });

    test('amenities are normalized into four deduplicated categories', () {
      final result = buildAmenityCategories(
        {'pay_and_use': 'Yes'},
        {
          'infra': {'fob_details': '2 FOB with stairs'},
          'wheelchairs': {'available_good_condition': 3},
          'trolley': {'trolley_path': 'YES'},
          'platforms': [
            {'platform': 'PF-1', 'lifts': 1, 'ramp': 'Yes'},
            {'platform': 'PF-2/3', 'lifts': 1, 'ramp': 'No'},
          ],
        },
      );

      expect(result.keys.toList(), amenityCategoryOrder);
      expect(
        result['Accessibility']!.map((item) => item.displayLabel),
        containsAll([
          'FOB (2)',
          'Lift (2)',
          'Ramp (1)',
          'Trolley Path',
          'Wheelchair (3)',
        ]),
      );
      expect(
        result['Passenger Convenience']!.single.displayLabel,
        'Toilets',
      );
    });

    test('duplicate contracts merge and retain aggregate earnings', () {
      final result = buildContracts([
        {
          'unit_no': 'SBC-01',
          'licensee_name': 'Refreshments',
          'type_of_unit': 'Stall',
          'unit_status': 'Active',
          'earnings_total': 12000,
        },
        {
          'unit_no': 'SBC-01',
          'licensee_name': 'Refreshments',
          'type_of_unit': 'Stall',
          'unit_status': 'Active',
          'earnings_total': 12000,
        },
      ], const []);

      expect(result, hasLength(1));
      expect(result.single.earnings, 12000);
      expect(result.single.status, 'Active');
    });

    test('unallotted units remain visible without tender earnings', () {
      final result = buildContracts([
        {
          'unit_no': 'CS-09',
          'type_of_unit': 'Catering stall',
          'unit_status': 'Tender under Finalisation',
          'remarks': 'Tender under Finalisation',
          'earnings_total': 75000,
          'earnings': [
            {'amount': 75000, 'payment_head': 'Tender EMD'},
          ],
        },
      ], const []);

      expect(result, hasLength(1));
      expect(result.single.name, contains('CS-09'));
      expect(result.single.status, 'Available');
      expect(result.single.earnings, 0);
      expect(result.single.payments, isEmpty);
      expect(result.single.validFrom, isNull);
      expect(result.single.validTo, isNull);
      expect(contractValidityLabel(result.single), 'Not allotted');
    });

    test('works expose only concise fields and deduplicate by project id', () {
      final result = buildWorks([
        {
          'project_id': 'P-1',
          'short_name_of_work': 'Platform extension',
          'cost': '2.29 Cr',
          'status': 'In progress',
          'physical_progress': '20%',
          'tdc': '31/03/2026',
        },
        {
          'project_id': 'P-1',
          'short_name_of_work': 'Platform extension',
          'cost': '2.29 Cr',
          'status': 'In progress',
          'physical_progress': '10%',
          'tdc': '31/03/2026',
        },
      ]);

      expect(result, hasLength(1));
      expect(result.single.progress, 20);
      expect(result.single.targetCompletion, '31/03/2026');
    });
  });
}
