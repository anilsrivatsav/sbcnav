String normalizeContractText(Object? value) => '${value ?? ''}'
    .toLowerCase()
    .replaceAll(RegExp(r'[\u2013\u2014]'), '-')
    .replaceAll(RegExp(r'\s+'), ' ')
    .trim();

String contractAssetLabel(Map<dynamic, dynamic> asset) {
  final value = asset['station_code'] ??
      asset['train_number'] ??
      asset['asset_name'] ??
      asset['raw_asset_value'] ??
      '';
  return '$value'.trim().replaceFirst(RegExp(r'\.0$'), '');
}

List<String> contractAssetLabels(Map<dynamic, dynamic> row) {
  final assets = row['assets'];
  if (assets is! List) return const [];
  return assets
      .whereType<Map>()
      .map(contractAssetLabel)
      .where((value) => value.isNotEmpty)
      .toList(growable: false);
}

List<Map<dynamic, dynamic>> filterPublicityContracts(
  List<Map<dynamic, dynamic>> rows, {
  String status = 'running',
  String policy = 'all',
  String asset = 'all',
  String query = '',
}) {
  final selectedStatus = normalizeContractText(status);
  final selectedPolicy = normalizeContractText(policy);
  final selectedAsset = normalizeContractText(asset);
  final selectedQuery = normalizeContractText(query);

  return rows.where((row) {
    final rowStatus =
        normalizeContractText(row['status'] ?? row['contract_status']);
    final policyValues = [
      row['policy_code'],
      row['policy'],
      row['category'],
      row['contract_name'],
    ].map(normalizeContractText).toSet();
    final contractPolicyTokens = normalizeContractText(row['contract_number'])
        .split(RegExp(r'[^a-z0-9]+'))
        .where((value) => value.isNotEmpty)
        .toSet();
    final assets = contractAssetLabels(row);
    final normalizedAssets = assets.map(normalizeContractText).toSet();
    final contractor =
        row['contractor'] is Map ? row['contractor'] as Map : const {};
    final searchText = normalizeContractText([
      row['contract_number'],
      row['contract_name'],
      row['category'],
      row['policy_code'],
      contractor['legal_name'],
      ...assets,
    ].join(' '));

    return (selectedStatus == 'all' || rowStatus == selectedStatus) &&
        (selectedPolicy == 'all' ||
            policyValues.contains(selectedPolicy) ||
            contractPolicyTokens.contains(selectedPolicy)) &&
        (selectedAsset == 'all' || normalizedAssets.contains(selectedAsset)) &&
        (selectedQuery.isEmpty || searchText.contains(selectedQuery));
  }).toList(growable: false);
}

bool isAvailableCateringUnit(Map<dynamic, dynamic> row) {
  if (normalizeContractText(row['unit_status']) == 'available') return true;
  return normalizeContractText(row['licensee_name']).isEmpty &&
      normalizeContractText(row['contract_from']).isEmpty &&
      normalizeContractText(row['contract_to']).isEmpty;
}

bool isActiveCateringUnit(Map<dynamic, dynamic> row) {
  if (isAvailableCateringUnit(row)) return false;
  final status = normalizeContractText(row['unit_status']);
  return !RegExp(
    r'no offers|scheduled|tender|under process|cancelled|not awarded|no train service',
  ).hasMatch(status);
}

List<Map<dynamic, dynamic>> filterCateringContracts(
  List<Map<dynamic, dynamic>> rows, {
  String view = 'active',
  String type = 'all',
  String station = 'all',
  String query = '',
}) {
  final selectedType = normalizeContractText(type);
  final selectedStation =
      normalizeContractText(station).replaceFirst(RegExp(r'\.0$'), '');
  final selectedQuery = normalizeContractText(query);

  return rows.where((row) {
    final active = isActiveCateringUnit(row);
    final viewMatches = view == 'active' ? active : !active;
    final rowType = normalizeContractText(row['type_of_unit']);
    final rowStation = normalizeContractText(row['station_code'])
        .replaceFirst(RegExp(r'\.0$'), '');
    final searchText = normalizeContractText([
      row['unit_no'],
      row['station_code'],
      row['station_name'],
      row['licensee_name'],
      row['unit_status'],
      row['remarks'],
      row['type_of_unit'],
      row['pf_no'],
    ].join(' '));
    return viewMatches &&
        (selectedType == 'all' || rowType == selectedType) &&
        (selectedStation == 'all' || rowStation == selectedStation) &&
        (selectedQuery.isEmpty || searchText.contains(selectedQuery));
  }).toList(growable: false);
}
