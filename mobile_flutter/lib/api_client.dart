import 'dart:convert';

import 'package:http/http.dart' as http;

import 'config.dart';

class ApiException implements Exception {
  ApiException(this.message);

  final String message;

  @override
  String toString() => message;
}

class RailApiClient {
  RailApiClient({http.Client? httpClient}) : _httpClient = httpClient ?? http.Client();

  final http.Client _httpClient;

  Uri _uri(String path, [Map<String, String?> query = const {}]) {
    final base = Uri.parse(AppConfig.apiBaseUrl);
    return base.replace(
      path: path,
      queryParameters: {
        for (final entry in query.entries)
          if (entry.value != null && entry.value!.isNotEmpty) entry.key: entry.value,
      },
    );
  }

  Future<dynamic> _get(String path, [Map<String, String?> query = const {}]) async {
    final response = await _httpClient.get(_uri(path, query));
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw ApiException('API ${response.statusCode}: ${response.body}');
    }
    final decoded = jsonDecode(response.body) as Map<String, dynamic>;
    if (decoded['success'] != true) {
      throw ApiException((decoded['message'] ?? 'Request failed').toString());
    }
    return decoded['data'];
  }

  Future<Map<String, dynamic>> stats() async => await _get('/api/stats') as Map<String, dynamic>;

  Future<Map<String, dynamic>> reports() async => await _get('/api/reports') as Map<String, dynamic>;

  Future<Map<String, dynamic>> amenityReports() async => await _get('/api/passenger-amenities/reports') as Map<String, dynamic>;

  Future<List<Map<String, dynamic>>> stations({String search = ''}) async {
    return _items('/api/stations', {'page': '1', 'page_size': '500', 'search': search, 'sort_by': 'station_name'});
  }

  Future<List<Map<String, dynamic>>> units({String search = ''}) async {
    return _items('/api/units', {'page': '1', 'page_size': '500', 'search': search, 'sort_by': 'unit_no'});
  }

  Future<List<Map<String, dynamic>>> earnings({String search = ''}) async {
    return _items('/api/earnings', {'page': '1', 'page_size': '500', 'search': search, 'sort_by': 'date_of_receipt', 'sort_order': 'desc'});
  }

  Future<List<Map<String, dynamic>>> works({String search = ''}) async {
    return _items('/api/works', {'page': '1', 'page_size': '500', 'search': search, 'sort_by': 'project_id'});
  }

  Future<List<Map<String, dynamic>>> amenities({String kind = 'summary', String search = ''}) async {
    return _items('/api/passenger-amenities', {'kind': kind, 'page': '1', 'page_size': '500', 'search': search, 'sort_by': 'station_code'});
  }

  Future<Map<String, dynamic>> stationFullDetail(String stationCode) async {
    return await _get('/api/stations/${Uri.encodeComponent(stationCode)}/detail') as Map<String, dynamic>;
  }

  Future<List<Map<String, dynamic>>> _items(String path, Map<String, String?> query) async {
    final data = await _get(path, query) as Map<String, dynamic>;
    final rawItems = (data['items'] as List<dynamic>? ?? const []);
    return rawItems.map((item) => Map<String, dynamic>.from(item as Map)).toList();
  }
}
