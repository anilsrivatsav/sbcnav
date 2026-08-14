import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/config.dart';

final mobileApiProvider = Provider<MobileApi>((ref) => MobileApi());

class MobileApiException implements Exception {
  const MobileApiException(this.message);
  final String message;

  @override
  String toString() => message;
}

class MobileApi {
  MobileApi({Dio? dio})
      : _dio = dio ??
            Dio(
              BaseOptions(
                baseUrl: AppConfig.apiBaseUrl,
                connectTimeout: AppConfig.requestTimeout,
                receiveTimeout: AppConfig.requestTimeout,
                sendTimeout: AppConfig.requestTimeout,
                headers: const {'Accept': 'application/json'},
              ),
            );

  final Dio _dio;

  Future<Map<String, dynamic>> bootstrap() => _request(
        () => _dio.get('/api/mobile/v1/bootstrap'),
      );

  Future<Map<String, dynamic>> station360(String stationCode) => _request(
        () => _dio.get(
          '/api/mobile/v1/stations/${Uri.encodeComponent(stationCode)}/360',
        ),
      );

  Future<Map<String, dynamic>> offlineStationDetails({
    required int offset,
    int limit = 10,
  }) =>
      _request(
        () => _dio.get(
          '/api/mobile/v1/offline/station-details',
          queryParameters: {'offset': offset, 'limit': limit},
          options: Options(receiveTimeout: const Duration(seconds: 90)),
        ),
      );

  Future<Map<String, dynamic>> push(
    String deviceId,
    List<Map<String, dynamic>> operations,
  ) =>
      _request(
        () => _dio.post(
          '/api/mobile/v1/sync/push',
          data: {'device_id': deviceId, 'operations': operations},
        ),
      );

  Future<Map<String, dynamic>> pull(int cursor) => _request(
        () => _dio.get(
          '/api/mobile/v1/sync/pull',
          queryParameters: {'cursor': cursor},
        ),
      );

  Future<Map<String, dynamic>> askAi(String question) => _request(
        () => _dio.post(
          '/api/ai/query',
          data: {'question': question, 'context': const {}},
        ),
      );

  Future<Map<String, dynamic>> syncCateringFromGoogleSheet() => _request(
        () => _dio.post(
          '/api/catering/sync',
          options: Options(
            receiveTimeout: const Duration(seconds: 180),
            sendTimeout: const Duration(seconds: 30),
          ),
        ),
      );

  Future<Map<String, dynamic>> _request(
    Future<Response<dynamic>> Function() operation,
  ) async {
    try {
      return _data(await operation());
    } on DioException catch (error) {
      final response = error.response?.data;
      if (response is Map) {
        final detail = response['detail'];
        if (detail is String && detail.trim().isNotEmpty) {
          throw MobileApiException(detail);
        }
        final message = response['message'];
        if (message is String && message.trim().isNotEmpty) {
          throw MobileApiException(message);
        }
      }
      if (error.type == DioExceptionType.connectionTimeout ||
          error.type == DioExceptionType.receiveTimeout ||
          error.type == DioExceptionType.sendTimeout) {
        throw const MobileApiException(
          'The server took too long to respond. Your offline work is safe.',
        );
      }
      if (error.type == DioExceptionType.connectionError) {
        throw const MobileApiException(
          'The server is unavailable. Continue offline and sync later.',
        );
      }
      throw const MobileApiException(
        'The request could not be completed. Please try again.',
      );
    }
  }

  Map<String, dynamic> _data(Response<dynamic> response) {
    final body = response.data;
    if (body is! Map || body['success'] != true) {
      throw MobileApiException(
        body is Map
            ? '${body['message'] ?? 'Request failed'}'
            : 'Invalid API response',
      );
    }
    final data = body['data'];
    if (data is! Map) {
      throw const MobileApiException('API returned an invalid data object');
    }
    return Map<String, dynamic>.from(data);
  }
}
