import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/network/dio_client.dart';
import 'package:voicenote_ai/features/auth/data/models/auth_tokens.dart';
import 'package:voicenote_ai/features/auth/data/models/user.dart';

class AuthRepository {
  AuthRepository(this._dio);

  final Dio _dio;

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

  Future<AuthTokens> register({
    required String email,
    required String password,
    required String firstName,
  }) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/auth/email/register',
        data: {
          'email': email.trim(),
          'password': password,
          'first_name': firstName.trim(),
        },
      );
      return AuthTokens.fromJson(response.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> logout(String refreshToken) async {
    try {
      await _dio.post<void>(
        '/auth/email/logout',
        data: {'refresh_token': refreshToken},
      );
    } on DioException {
      // logout is best-effort
    }
  }

  Future<User> fetchMe() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>('/profile/me');
      return User.fromJson(response.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}

final authRepositoryProvider = Provider<AuthRepository>(
  (ref) => AuthRepository(ref.watch(dioProvider)),
);
