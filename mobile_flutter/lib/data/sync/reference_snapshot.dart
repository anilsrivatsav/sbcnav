/// A complete, validated download. Partial pages never replace offline data.
class ReferenceSnapshot {
  ReferenceSnapshot._(this.units, this.works, this.version);

  final List<Map<String, dynamic>> units;
  final List<Map<String, dynamic>> works;
  final String version;

  factory ReferenceSnapshot.fromResponses(
    Map<String, dynamic> bootstrap,
    Map<String, dynamic> unitPage,
    Map<String, dynamic> workPage,
  ) {
    List<Map<String, dynamic>> completePage(
      Map<String, dynamic> page,
      String key,
    ) {
      final rows = (page['items'] as List? ?? const [])
          .map((row) => Map<String, dynamic>.from(row as Map))
          .toList();
      final total = (page['pagination'] as Map?)?['total'];
      if (rows.isEmpty || total != rows.length) {
        throw StateError(
            'Incomplete $key download. Previous offline data kept.');
      }
      final ids = rows.map((row) => '${row[key] ?? ''}').toSet();
      if (ids.contains('') || ids.length != rows.length) {
        throw StateError('Invalid or duplicate $key in Oracle download.');
      }
      return rows;
    }

    final units = completePage(unitPage, 'unit_no');
    final works = completePage(workPage, 'project_id');
    final register = bootstrap['all_works'] as List? ?? const [];
    final expected = (bootstrap['portfolio_totals'] as Map?)?['works'];
    final expectedIds =
        register.map((row) => '${(row as Map)['project_id']}').toSet();
    if (expected != works.length ||
        expectedIds.length != works.length ||
        works.any((row) => !expectedIds.contains('${row['project_id']}'))) {
      throw StateError(
          'The works register changed during download. Retry refresh.');
    }
    return ReferenceSnapshot._(units, works,
        '${bootstrap['data_version'] ?? DateTime.now().toUtc().toIso8601String()}');
  }

  /// Publicity, amenities and inspection content in each station stay intact.
  Map<String, dynamic> updateStation(
          String code, Map<String, dynamic> detail) =>
      {
        ...detail,
        'units': units
            .where((row) =>
                '${row['station_code']}'.toUpperCase() == code.toUpperCase())
            .toList(),
        'works': works
            .where((row) => (row['station_codes'] as List? ?? const []).any(
                (station) => '$station'.toUpperCase() == code.toUpperCase()))
            .toList(),
      };
}
