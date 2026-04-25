import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/network/dio_client.dart';
import 'package:voicenote_ai/features/auth/data/models/user.dart';

/// PATCH /api/v1/profile (PRODUCT_PLAN.md §5.2). Только мутации; чтение —
/// через `sessionControllerProvider` (User уже в памяти).
class ProfileRepository {
  ProfileRepository(this._dio);

  final Dio _dio;

  Future<User> patch({
    String? displayName,
    String? timezone,
    String? locale,
    int? digestHour,
  }) async {
    try {
      final response = await _dio.patch<Map<String, dynamic>>(
        '/profile',
        data: {
          if (displayName != null) 'display_name': displayName,
          if (timezone != null) 'timezone': timezone,
          if (locale != null) 'locale': locale,
          if (digestHour != null) 'digest_hour': digestHour,
        },
      );
      return User.fromJson(response.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}

final profileRepositoryProvider = Provider<ProfileRepository>(
  (ref) => ProfileRepository(ref.watch(dioProvider)),
);
