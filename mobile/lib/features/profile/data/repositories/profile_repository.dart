import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/network/dio_client.dart';

class Achievement {
  const Achievement({
    required this.code,
    required this.name,
    required this.description,
    required this.icon,
    required this.xpReward,
    required this.earned,
  });

  final String code;
  final String name;
  final String description;
  final String icon;
  final int xpReward;
  final bool earned;

  factory Achievement.fromJson(Map<String, dynamic> json) => Achievement(
        code: json['code'] as String,
        name: (json['name'] as String?) ?? '',
        description: (json['description'] as String?) ?? '',
        icon: (json['icon'] as String?) ?? '🏆',
        xpReward: (json['xp_reward'] as num?)?.toInt() ?? 0,
        earned: (json['earned'] as bool?) ?? false,
      );
}

class ProfileRepository {
  ProfileRepository(this._dio);
  final Dio _dio;

  Future<Map<String, dynamic>> updateProfile({
    String? timezone,
    String? cityName,
    bool? dailyDigestEnabled,
    String? dailyDigestTime,
    String? defaultReminderTime,
    int? preReminderMinutes,
  }) async {
    try {
      final body = <String, dynamic>{};
      if (timezone != null) body['timezone'] = timezone;
      if (cityName != null) body['city_name'] = cityName;
      if (dailyDigestEnabled != null) body['daily_digest_enabled'] = dailyDigestEnabled;
      if (dailyDigestTime != null) body['daily_digest_time'] = dailyDigestTime;
      if (defaultReminderTime != null) body['default_reminder_time'] = defaultReminderTime;
      if (preReminderMinutes != null) body['pre_reminder_minutes'] = preReminderMinutes;

      final response = await _dio.put<Map<String, dynamic>>(
        '/profile/me',
        data: body,
      );
      return response.data!;
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<List<Achievement>> achievements() async {
    try {
      final response = await _dio.get<dynamic>('/profile/me/achievements');
      final raw = response.data;
      final list = raw is List
          ? raw
          : (raw is Map ? (raw['items'] as List?) ?? const [] : const <dynamic>[]);
      return list
          .map((e) => Achievement.fromJson(e as Map<String, dynamic>))
          .toList(growable: false);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> registerDevice(String fcmToken, String platform) async {
    try {
      await _dio.post<void>(
        '/profile/devices',
        data: {'fcm_token': fcmToken, 'platform': platform},
      );
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> unregisterDevice(String fcmToken) async {
    try {
      await _dio.delete<void>(
        '/profile/devices',
        data: {'fcm_token': fcmToken},
      );
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}

final profileRepositoryProvider = Provider<ProfileRepository>(
  (ref) => ProfileRepository(ref.watch(dioProvider)),
);

final achievementsProvider =
    FutureProvider.autoDispose<List<Achievement>>((ref) async {
  return ref.watch(profileRepositoryProvider).achievements();
});
