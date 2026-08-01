import 'package:flutter_test/flutter_test.dart';
import 'package:rail_inspect/features/inspections/inspection_logic.dart';

void main() {
  const sections = [
    {
      'code': 'required',
      'questions': [
        {'code': 'q1', 'required': true},
        {'code': 'q2', 'required': true},
      ],
    },
    {
      'code': 'optional',
      'questions': [
        {'code': 'q3', 'required': false},
      ],
    },
  ];

  test('optional answers cannot replace a missing required answer', () {
    final progress = InspectionLogic.evaluate(sections, {
      'q1': {'response_value': 'pass'},
      'q3': {'response_value': 'pass'},
    });

    expect(progress.canSubmit, isFalse);
    expect(progress.requiredAnswered, 1);
    expect(progress.missingRequiredCodes, ['q2']);
  });

  test('score excludes not-applicable responses', () {
    final progress = InspectionLogic.evaluate(sections, {
      'q1': {'response_value': 'pass'},
      'q2': {'response_value': 'fail'},
      'q3': {'response_value': 'na'},
    });

    expect(progress.canSubmit, isTrue);
    expect(progress.score, 50);
    expect(progress.notApplicable, 1);
  });

  test('finds the section containing a missing question', () {
    expect(InspectionLogic.sectionForQuestion(sections, 'q3'), 1);
  });
}
