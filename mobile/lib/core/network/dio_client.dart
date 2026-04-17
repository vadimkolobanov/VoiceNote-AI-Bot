import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/core/config/env.dart';
import 'package:voicenote_ai/core/network/auth_interceptor.dart';
import 'package:voicenote_ai/core/storage/secure_storage.dart';
import 'package:voicenote_ai/features/auth/application/session_controller.dart';

/// Dio instance configured with base URL, timeouts, and JWT auth interceptor.
final dioProvider = Provider<Dio>((ref) {
  final storage = ref.watch(secureStorageProvider);

  final dio = Dio(
    BaseOptions(
      baseUrl: Env.apiUrl,
      connectTimeout: const Duration(seconds: 15),
      sendTimeout: const Duration(seconds: 30),
      receiveTimeout: const Duration(seconds: 30),
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
    ),
  );

  // Separate Dio without the auth interceptor — used to perform refresh.
  final refreshDio = Dio(BaseOptions(
    connectTimeout: const Duration(seconds: 15),
    receiveTimeout: const Duration(seconds: 15),
  ));

  dio.interceptors.add(
    AuthInterceptor(
      storage: storage,
      refreshDio: refreshDio,
      onSessionExpired: () async {
        // Clear session + trigger UI redirect via auth controller.
        await ref.read(sessionControllerProvider.notifier).signalExpired();
      },
    ),
  );

  // Compact logger for debugging.
  if (!Env.isProduction) {
    dio.interceptors.add(
      LogInterceptor(
        request: false,
        requestHeader: false,
        responseHeader: false,
        requestBody: true,
        responseBody: true,
        error: true,
      ),
    );
  }

  return dio;
});
