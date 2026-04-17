import 'package:dio/dio.dart';

/// Domain-level API error surfaced to UI.
class ApiException implements Exception {
  const ApiException({
    required this.message,
    this.statusCode,
    this.code,
    this.isNetwork = false,
  });

  final String message;
  final int? statusCode;
  final String? code;
  final bool isNetwork;

  bool get isUnauthorized => statusCode == 401;
  bool get isForbidden => statusCode == 403;
  bool get isNotFound => statusCode == 404;
  bool get isConflict => statusCode == 409;
  bool get isPaymentRequired => statusCode == 402;

  factory ApiException.fromDio(DioException error) {
    if (error.type == DioExceptionType.connectionError ||
        error.type == DioExceptionType.connectionTimeout ||
        error.type == DioExceptionType.sendTimeout ||
        error.type == DioExceptionType.receiveTimeout) {
      return const ApiException(
        message: 'Нет соединения. Проверьте интернет и попробуйте снова.',
        isNetwork: true,
      );
    }

    final response = error.response;
    final data = response?.data;
    String message = 'Что-то пошло не так. Попробуйте ещё раз.';

    if (data is Map<String, dynamic>) {
      final detail = data['detail'];
      if (detail is String) {
        message = detail;
      } else if (detail is List && detail.isNotEmpty) {
        final first = detail.first;
        if (first is Map && first['msg'] is String) {
          message = first['msg'] as String;
        }
      } else if (data['message'] is String) {
        message = data['message'] as String;
      }
    } else if (data is String && data.isNotEmpty) {
      message = data;
    }

    return ApiException(
      message: message,
      statusCode: response?.statusCode,
      code: response?.statusMessage,
    );
  }

  @override
  String toString() => 'ApiException($statusCode): $message';
}
