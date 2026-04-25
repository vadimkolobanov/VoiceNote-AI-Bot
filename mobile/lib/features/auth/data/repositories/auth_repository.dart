import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/network/dio_client.dart';
import 'package:voicenote_ai/features/auth/data/models/auth_tokens.dart';
import 'package:voicenote_ai/features/auth/data/models/user.dart';

/// Auth-API клиент. Поверхность контрактов — PRODUCT_PLAN.md §5.2.
class AuthRepository {
  AuthRepository(this._dio);

  final Dio _dio;

  Future<AuthTokens> register({
    required String email,
    required String password,
    String? displayName,
  }) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/auth/email/register',
        data: {
          'email': email.trim(),
          'password': password,
          if (displayName != null && displayName.trim().isNotEmpty)
            'display_name': displayName.trim(),
        },
      );
      return AuthTokens.fromJson(response.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<AuthTokens> login({
    required String email,
    required String password,
  }) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/auth/email/login',
        data: {'email': email.trim(), 'password': password},
      );
      return AuthTokens.fromJson(response.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<AuthTokens> refresh(String refreshToken) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/auth/refresh',
        data: {'refresh': refreshToken},
      );
      return AuthTokens.fromJson(response.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> logout(String refreshToken) async {
    try {
      await _dio.post<void>('/auth/logout', data: {'refresh': refreshToken});
    } on DioException {
      // logout — best-effort
    }
  }

  Future<User> fetchProfile() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>('/profile');
      return User.fromJson(response.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}

final authRepositoryProvider = Provider<AuthRepository>(
  (ref) => AuthRepository(ref.watch(dioProvider)),
);
