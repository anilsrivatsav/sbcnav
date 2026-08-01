import 'dart:math' as math;

import 'package:intl/intl.dart';

const amenityCategoryOrder = [
  'Waiting Facilities',
  'Passenger Convenience',
  'Accessibility',
  'Information & Digital',
];

class StationCardData {
  const StationCardData({
    required this.code,
    required this.name,
    required this.section,
    required this.dailyFootfall,
    required this.category,
    required this.totalPlatforms,
    required this.abssFlag,
    required this.redevelopmentFlag,
  });

  final String code;
  final String name;
  final String section;
  final String dailyFootfall;
  final String category;
  final int totalPlatforms;
  final bool abssFlag;
  final bool redevelopmentFlag;
}

class AmenityItem {
  const AmenityItem(this.label, {this.quantity});

  final String label;
  final int? quantity;

  String get displayLabel => quantity == null ? label : '$label ($quantity)';
}

class ContractSummary {
  const ContractSummary({
    required this.key,
    required this.name,
    required this.type,
    required this.earnings,
    required this.status,
    this.validFrom,
    this.validTo,
    this.daysToExpiry,
    this.renewalState = 'Date unavailable',
    this.details = const {},
    this.payments = const [],
  });

  final String key;
  final String name;
  final String type;
  final double earnings;
  final String status;
  final DateTime? validFrom;
  final DateTime? validTo;
  final int? daysToExpiry;
  final String renewalState;
  final Map<String, dynamic> details;
  final List<Map<String, dynamic>> payments;
}

class WorkSummary {
  const WorkSummary({
    required this.key,
    required this.name,
    required this.cost,
    required this.status,
    required this.progress,
    required this.targetCompletion,
    this.details = const {},
  });

  final String key;
  final String name;
  final String cost;
  final String status;
  final int? progress;
  final String targetCompletion;
  final Map<String, dynamic> details;
}

String cleanText(Object? value, {String fallback = '—'}) {
  final text = value?.toString().trim() ?? '';
  if (text.isEmpty || {'-', '--', 'null', 'n/a'}.contains(text.toLowerCase())) {
    return fallback;
  }
  return text;
}

double? numericValue(Object? value) {
  if (value is num) return value.toDouble();
  final text = value?.toString().replaceAll(',', '').trim() ?? '';
  return double.tryParse(
      RegExp(r'-?\d+(?:\.\d+)?').firstMatch(text)?.group(0) ?? '');
}

double dailyFootfallValue(Object? annualFootfall) {
  return math.max(0, numericValue(annualFootfall) ?? 0) / 30;
}

String formatDailyFootfall(Object? annualFootfall) {
  final value = dailyFootfallValue(annualFootfall);
  if (value >= 10000000) {
    return '${_compact(value / 10000000)} Cr';
  }
  if (value >= 100000) return '${_compact(value / 100000)} Lakh';
  if (value >= 1000) return '${_compact(value / 1000)}K';
  return NumberFormat('#,##0').format(value.round());
}

String _compact(double value) {
  return value
      .toStringAsFixed(value >= 10 ? 1 : 2)
      .replaceFirst(RegExp(r'\.?0+$'), '');
}

int highestPlatformNumber(
  List<dynamic> platformRows, {
  Object? stationPlatforms,
  Object? declaredPlatforms,
}) {
  var highest = 0;
  void inspect(Object? value) {
    final text = value?.toString() ?? '';
    for (final match in RegExp(r'\d+').allMatches(text)) {
      highest = math.max(highest, int.tryParse(match.group(0)!) ?? 0);
    }
  }

  for (final raw in platformRows) {
    if (raw is Map) {
      inspect(raw['platform']);
      inspect(raw['platform_no']);
    } else {
      inspect(raw);
    }
  }
  inspect(stationPlatforms);
  if (highest == 0) inspect(declaredPlatforms);
  return highest;
}

StationCardData stationCardData(
  Map<String, dynamic> station,
  Map<String, dynamic>? detail,
) {
  final amenities = _map(detail?['amenities']);
  final platforms = _list(amenities['platforms']);
  return StationCardData(
    code: cleanText(station['station_code'], fallback: ''),
    name: cleanText(station['station_name'], fallback: 'Unnamed station'),
    section: cleanText(station['section']),
    dailyFootfall: formatDailyFootfall(station['passenger_footfall']),
    category: cleanText(station['categorisation'], fallback: 'Unclassified'),
    totalPlatforms: highestPlatformNumber(
      platforms,
      stationPlatforms: station['platforms'],
      declaredPlatforms: station['number_of_platforms'],
    ),
    abssFlag: station['abss_flag'] == true ||
        abssStationCodes.contains(
            cleanText(station['station_code'], fallback: '').toUpperCase()),
    redevelopmentFlag: station['redevelopment_flag'] == true ||
        redevelopmentStationCodes.contains(
            cleanText(station['station_code'], fallback: '').toUpperCase()),
  );
}

const abssStationCodes = {
  'KGI',
  'RMGM',
  'CPT',
  'MYA',
  'MWM',
  'TK',
  'GBB',
  'KJM',
  'WFD',
  'MLO',
  'BWT',
  'KPN',
  'HSRA',
  'DPJ',
  'DBU',
  'HUP',
  'SSPN',
  'SBGA',
  'CSDR',
};

const redevelopmentStationCodes = {'YPR', 'BNC'};

Map<String, List<AmenityItem>> buildAmenityCategories(
  Map<String, dynamic> station,
  Map<String, dynamic> amenities,
) {
  final values = <String, Map<String, int?>>{
    for (final category in amenityCategoryOrder) category: {},
  };

  void add(String category, String label, [Object? rawQuantity]) {
    final quantity = _positiveInteger(rawQuantity);
    final existing = values[category]![label];
    values[category]![label] =
        existing == null ? quantity : math.max(existing, quantity ?? existing);
  }

  final infra = _map(amenities['infra']);
  final fob = cleanText(infra['fob_details'], fallback: '');
  if (_isPresent(fob)) add('Accessibility', 'FOB', fob);

  final wheelchair = _map(amenities['wheelchairs']);
  final wheelchairCount = wheelchair['available_good_condition'];
  if ((numericValue(wheelchairCount) ?? 0) > 0) {
    add('Accessibility', 'Wheelchair', wheelchairCount);
  }

  final trolley = _map(amenities['trolley']);
  if (_isAffirmative(trolley['trolley_path'])) {
    add('Accessibility', 'Trolley Path');
  }

  var lifts = 0;
  var escalators = 0;
  var ramps = 0;
  for (final raw in _list(amenities['platforms'])) {
    final platform = _map(raw);
    lifts += _positiveInteger(platform['lifts']) ?? 0;
    escalators += _positiveInteger(platform['escalators']) ?? 0;
    if (_isAffirmative(platform['ramp']) ||
        (_positiveInteger(platform['ramp']) ?? 0) > 0) {
      ramps += _positiveInteger(platform['ramp']) ?? 1;
    }
  }
  if (lifts > 0) add('Accessibility', 'Lift', lifts);
  if (escalators > 0) add('Accessibility', 'Escalator', escalators);
  if (ramps > 0) add('Accessibility', 'Ramp', ramps);

  if (_isPresent(cleanText(station['pay_and_use'], fallback: ''))) {
    add('Passenger Convenience', 'Toilets');
  }

  final parking = cleanText(station['parking'], fallback: '');
  if (_isPresent(parking)) add('Passenger Convenience', 'Parking');

  final shelter = cleanText(infra['shelter_details'], fallback: '');
  if (_isPresent(shelter)) add('Waiting Facilities', 'Platform Shelter');

  return {
    for (final category in amenityCategoryOrder)
      category: values[category]!
          .entries
          .map((entry) => AmenityItem(entry.key, quantity: entry.value))
          .toList()
        ..sort((a, b) => a.label.compareTo(b.label)),
  };
}

List<ContractSummary> buildContracts(
  List<dynamic> catering,
  List<dynamic> commercial,
) {
  final grouped = <String, ContractSummary>{};

  void merge(ContractSummary item) {
    final existing = grouped[item.key];
    if (existing == null) {
      grouped[item.key] = item;
      return;
    }
    grouped[item.key] = ContractSummary(
      key: item.key,
      name:
          existing.name.length >= item.name.length ? existing.name : item.name,
      type: existing.type == 'Commercial' ? item.type : existing.type,
      earnings: math.max(existing.earnings, item.earnings),
      status: _preferredStatus(existing.status, item.status),
      validFrom: existing.validFrom ?? item.validFrom,
      validTo: existing.validTo ?? item.validTo,
      daysToExpiry: existing.daysToExpiry ?? item.daysToExpiry,
      renewalState: existing.renewalState != 'Date unavailable'
          ? existing.renewalState
          : item.renewalState,
      details: existing.details.length >= item.details.length
          ? existing.details
          : item.details,
      payments: [
        ...existing.payments,
        ...item.payments.where((payment) => !existing.payments
            .any((old) => old.toString() == payment.toString())),
      ],
    );
  }

  for (final raw in catering) {
    final row = _map(raw);
    final unitNo = cleanText(row['unit_no'], fallback: '');
    final name = cleanText(
      row['licensee_name'],
      fallback: cleanText(row['type_of_unit'], fallback: 'Catering contract'),
    );
    final earnings = numericValue(row['earnings_total']) ??
        _list(row['earnings']).fold<double>(
          0,
          (sum, earning) => sum + (numericValue(_map(earning)['amount']) ?? 0),
        );
    merge(
      ContractSummary(
        key: _normalizeKey(unitNo.isNotEmpty
            ? 'unit:$unitNo'
            : '$name:${row['type_of_unit']}'),
        name: unitNo.isEmpty ? name : '$unitNo · $name',
        type: cleanText(row['type_of_unit'], fallback: 'Catering'),
        earnings: earnings,
        status: cleanText(row['unit_status'], fallback: 'Status unavailable'),
        validFrom: _contractDate(row, ['contract_from', 'contract_period_from']),
        validTo: _contractDate(row, ['contract_to', 'contract_upto']),
        renewalState: _renewalState(
          _contractDate(row, ['contract_to', 'contract_upto']),
        ),
        daysToExpiry: _daysToExpiry(
          _contractDate(row, ['contract_to', 'contract_upto']),
        ),
        details: row,
        payments: _paymentRows(row),
      ),
    );
  }

  for (final raw in commercial) {
    final row = _map(raw);
    final name =
        cleanText(row['contract_name'], fallback: 'Commercial contract');
    final keyValue = cleanText(row['contract_key'], fallback: '');
    merge(
      ContractSummary(
        key: _normalizeKey(keyValue.isNotEmpty
            ? 'contract:$keyValue'
            : '$name:${row['policy']}'),
        name: name,
        type: cleanText(
          row['sub_category'],
          fallback: cleanText(row['policy'], fallback: 'Commercial'),
        ),
        earnings: numericValue(row['total_license_fee_2026_2027']) ??
            numericValue(row['year_ending_amount']) ??
            numericValue(row['annual_license_fee']) ??
            0,
        status: _contractStatus(row),
        validFrom: _contractDate(row, ['contract_period_from', 'contract_from']),
        validTo: _contractDate(row, ['contract_upto', 'contract_to']),
        renewalState: _renewalState(
          _contractDate(row, ['contract_upto', 'contract_to']),
        ),
        daysToExpiry: _daysToExpiry(
          _contractDate(row, ['contract_upto', 'contract_to']),
        ),
        details: row,
        payments: _paymentRows(row),
      ),
    );
  }

  final result = grouped.values.toList();
  result.sort((a, b) => a.name.compareTo(b.name));
  return result;
}

List<Map<String, dynamic>> _paymentRows(Map<String, dynamic> row) {
  final values = row['payments'] ?? row['payment_history'] ?? row['earnings'];
  if (values is! List) return const [];
  return [
    for (final value in values)
      if (value is Map) Map<String, dynamic>.from(value),
  ];
}

List<WorkSummary> buildWorks(List<dynamic> works) {
  final grouped = <String, WorkSummary>{};
  for (final raw in works) {
    final row = _map(raw);
    final name = cleanText(
      row['short_name_of_work'],
      fallback: cleanText(row['work_name'], fallback: 'Unnamed work'),
    );
    final projectId = cleanText(row['project_id'], fallback: '');
    final key = _normalizeKey(projectId.isEmpty ? name : projectId);
    final progress = _progress(row['physical_progress']);
    final item = WorkSummary(
      key: key,
      name: name,
      cost: cleanText(row['cost']),
      status: cleanText(row['status'], fallback: 'Status unavailable'),
      progress: progress,
      targetCompletion: cleanText(
        row['tdc'] ?? row['target_completion'],
      ),
      details: row,
    );
    final existing = grouped[key];
    if (existing == null || (item.progress ?? -1) > (existing.progress ?? -1)) {
      grouped[key] = item;
    }
  }
  final result = grouped.values.toList();
  result.sort((a, b) => a.name.compareTo(b.name));
  return result;
}

String formatCurrency(double value) {
  if (value <= 0) return '—';
  return NumberFormat.currency(
    locale: 'en_IN',
    symbol: '₹',
    decimalDigits: 0,
  ).format(value);
}

Map<String, dynamic> _map(Object? value) =>
    value is Map ? Map<String, dynamic>.from(value) : <String, dynamic>{};

List<dynamic> _list(Object? value) => value is List ? value : const [];

int? _positiveInteger(Object? value) {
  final number = numericValue(value);
  if (number == null || number <= 0) return null;
  return number.round();
}

bool _isAffirmative(Object? value) {
  final text = cleanText(value, fallback: '').toLowerCase();
  return {'yes', 'y', 'true', 'available', 'provided'}.contains(text) ||
      (numericValue(text) ?? 0) > 0;
}

bool _isPresent(String value) {
  final text = value.trim().toLowerCase();
  return text.isNotEmpty &&
      !{'no', 'none', 'nil', 'not available', 'na'}.contains(text);
}

String _normalizeKey(String value) =>
    value.toLowerCase().replaceAll(RegExp(r'[^a-z0-9]+'), '');

String _preferredStatus(String first, String second) {
  const priorities = [
    'active',
    'current',
    'valid',
    'pending',
    'expired',
    'closed'
  ];
  final a = first.toLowerCase();
  final b = second.toLowerCase();
  for (final status in priorities) {
    if (a.contains(status)) return first;
    if (b.contains(status)) return second;
  }
  return first;
}

String _contractStatus(Map<String, dynamic> row) {
  final explicit = cleanText(
    row['status'] ?? row['contract_status'],
    fallback: '',
  );
  if (explicit.isNotEmpty) return explicit;
  final end = _contractDate(row, ['contract_upto', 'contract_to']);
  if (end == null) return 'Status unavailable';
  return end.isBefore(DateTime.now()) ? 'Expired' : 'Active';
}

DateTime? _contractDate(Map<String, dynamic> row, List<String> keys) {
  for (final key in keys) {
    final value = row[key];
    if (value is DateTime) return DateTime(value.year, value.month, value.day);
    final text = cleanText(value, fallback: '');
    if (text.isEmpty) continue;
    final iso = DateTime.tryParse(text);
    if (iso != null) return DateTime(iso.year, iso.month, iso.day);
    final match = RegExp(r'^(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})').firstMatch(text);
    if (match != null) {
      final year = int.parse(match.group(3)!) < 100
          ? 2000 + int.parse(match.group(3)!)
          : int.parse(match.group(3)!);
      return DateTime(year, int.parse(match.group(2)!), int.parse(match.group(1)!));
    }
    final monthYear = RegExp(r'^(\d{1,2})[/-](\d{4})$').firstMatch(text);
    if (monthYear != null) {
      return DateTime(int.parse(monthYear.group(2)!), int.parse(monthYear.group(1)!), 1);
    }
  }
  return null;
}

int? _daysToExpiry(DateTime? end) {
  if (end == null) return null;
  final today = DateTime.now();
  final current = DateTime(today.year, today.month, today.day);
  return end.difference(current).inDays;
}

String _renewalState(DateTime? end) {
  final days = _daysToExpiry(end);
  if (days == null) return 'Date unavailable';
  if (days < 0) return 'Expired';
  if (days <= 7) return 'Due within 7 days';
  if (days <= 30) return 'Renewal due within 30 days';
  if (days <= 90) return 'Renewal upcoming';
  return 'Active';
}

String contractValidityLabel(ContractSummary contract) {
  if (contract.validTo == null) return 'Validity date unavailable';
  final date = DateFormat('dd MMM yyyy').format(contract.validTo!);
  final days = contract.daysToExpiry ?? 0;
  if (days < 0) return 'Expired on $date';
  if (days == 0) return 'Expires today';
  return 'Valid till $date · $days days remaining';
}

String formatContractDate(DateTime date) => DateFormat('dd MMM yyyy').format(date);

int? _progress(Object? value) {
  final number = numericValue(value);
  if (number == null) return null;
  return number.clamp(0, 100).round();
}
