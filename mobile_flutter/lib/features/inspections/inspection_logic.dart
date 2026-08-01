class InspectionProgress {
  const InspectionProgress({
    required this.total,
    required this.answered,
    required this.requiredTotal,
    required this.requiredAnswered,
    required this.passed,
    required this.failed,
    required this.notApplicable,
    required this.score,
    required this.missingRequiredCodes,
  });

  final int total;
  final int answered;
  final int requiredTotal;
  final int requiredAnswered;
  final int passed;
  final int failed;
  final int notApplicable;
  final int score;
  final List<String> missingRequiredCodes;

  bool get canSubmit => missingRequiredCodes.isEmpty;
  double get completion => total == 0 ? 0 : answered / total;
}

class InspectionLogic {
  const InspectionLogic._();

  static InspectionProgress evaluate(
    List<dynamic> sections,
    Map<String, Map<String, dynamic>> responses,
  ) {
    final questions = <Map<String, dynamic>>[];
    for (final rawSection in sections) {
      final section = Map<String, dynamic>.from(rawSection as Map);
      for (final rawQuestion
          in (section['questions'] as List? ?? const <dynamic>[])) {
        questions.add(Map<String, dynamic>.from(rawQuestion as Map));
      }
    }

    final questionCodes = questions.map((question) => '${question['code']}');
    final answeredCodes = questionCodes
        .where(
          (code) =>
              responses[code]?['response_value'] != null &&
              '${responses[code]!['response_value']}'.isNotEmpty,
        )
        .toSet();
    final requiredCodes = questions
        .where((question) => question['required'] == true)
        .map((question) => '${question['code']}')
        .toSet();
    final missing = requiredCodes.difference(answeredCodes).toList()..sort();

    final relevantResponses = responses.entries
        .where((entry) => questionCodes.contains(entry.key))
        .map((entry) => entry.value)
        .toList();
    final passed = relevantResponses
        .where((response) => response['response_value'] == 'pass')
        .length;
    final failed = relevantResponses
        .where((response) => response['response_value'] == 'fail')
        .length;
    final notApplicable = relevantResponses
        .where((response) => response['response_value'] == 'na')
        .length;
    final scored = passed + failed;

    return InspectionProgress(
      total: questions.length,
      answered: answeredCodes.length,
      requiredTotal: requiredCodes.length,
      requiredAnswered: requiredCodes.length - missing.length,
      passed: passed,
      failed: failed,
      notApplicable: notApplicable,
      score: scored == 0 ? 0 : ((passed / scored) * 100).round(),
      missingRequiredCodes: missing,
    );
  }

  static int sectionForQuestion(List<dynamic> sections, String questionCode) {
    for (var index = 0; index < sections.length; index += 1) {
      final section = Map<String, dynamic>.from(sections[index] as Map);
      final questions = section['questions'] as List? ?? const <dynamic>[];
      if (questions.any(
        (question) => '${(question as Map)['code']}' == questionCode,
      )) {
        return index;
      }
    }
    return 0;
  }
}
