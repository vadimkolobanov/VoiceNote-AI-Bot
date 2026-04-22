import 'dart:async';

import 'package:dio/dio.dart';

import 'package:voicenote_ai/core/config/env.dart';
import 'package:voicenote_ai/core/storage/secure_storage.dart';

/// Attaches JWT to outgoing requests and transparently refreshes it on 401.
///
/// Uses a single refresh future to deduplicate concurrent refreshes, and
/// propagates a `_sessionExpired` signal via callback when refresh fails so
/// the auth controller can clear session state and redirect to login.
class AuthInterceptor extends Interceptor {
  AuthInterceptor({
    required SecureTokenStorage storage,
    required Dio refreshDio,
    required FutureOr<void> Function() onSessionExpired,
  })  : _storage = storage,
        _refreshDio = refreshDio,
        _onSessionExpired = onSessionExpired;

  final SecureTokenStorage _storage;
  final Dio _refreshDio; // bare Dio without this interceptor, for refresh call
  final FutureOr<void> Function() _onSessionExpired;

  Future<String?>? _refreshInFlight;

  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    // Public endpoints — don't attach token.
    if (_isAuthEndpoint(options.path)) {
      return handler.next(options);
    }
    final token = await _storage.readAccess();
    if (token != null && token.isNotEmpty) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  }

  @override
  Future<void> onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    final response = err.response;
    final request = err.requestOptions;
    final isUnauthorized = response?.statusCode == 401;
    final alreadyRetried = request.extra['_retried'] == true;

    if (!isUnauthorized || alreadyRetried || _isAuthEndpoint(request.path)) {
      return handler.next(err);
    }

    final newAccess = await _tryRefresh();
    if (newAccess == null) {
      await _onSessionExpired();
      return handler.next(err);
    }

    // Retry the original request with a fresh token.
    request
      ..extra['_retried'] = true
      ..headers['Authorization'] = 'Bearer $newAccess';

    try {
      final retryDio = Dio(BaseOptions(
        baseUrl: request.baseUrl,
        headers: {...request.headers},
      ));
      final response = await retryDio.fetch<dynamic>(request);
      handler.resolve(response);
    } on DioException catch (e) {
      handler.next(e);
    }
  }

  Future<String?> _tryRefresh() {
    return _refreshInFlight ??= _performRefresh()
      ..whenComplete(() => _refreshInFlight = null);
  }

  Future<String?> _performRefresh() async {
    final refresh = await _storage.readRefresh();
    if (refresh == null || refresh.isEmpty) return null;

    try {
      final response = await _refreshDio.post<Map<String, dynamic>>(
        '${Env.apiUrl}/auth/refresh',
        data: {'refresh_token': refresh},
        options: Options(
          headers: {'Content-Type': 'application/json'},
          // 401 here means refresh itself expired.
          validateStatus: (c) => c != null && c < 500,
        ),
      );
      final body = response.data;
      if (response.statusCode == 200 && body is Map<String, dynamic>) {
        final access = body['access_token'] as String?;
        final newRefresh = body['refresh_token'] as String? ?? refresh;
        if (access != null) {
          await _storage.save(access: access, refresh: newRefresh);
          return access;
        }
      }
    } on DioException {
      // fall through
    }
    await _storage.clear();
    return null;
  }

  static bool _isAuthEndpoint(String path) {
    return path.contains('/auth/email/login') ||
        path.contains('/auth/email/dev-login') ||
        path.contains('/auth/email/dev-users') ||
        path.contains('/auth/refresh');
  }
}
