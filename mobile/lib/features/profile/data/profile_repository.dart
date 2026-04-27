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

  Future<ProfileStats> fetchStats() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>('/profile/stats');
      return ProfileStats.fromJson(response.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  /// DELETE /profile — необратимое удаление аккаунта и всей памяти.
  Future<void> deleteAccount() async {
    try {
      await _dio.delete<dynamic>('/profile');
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}

class HabitStreak {
  HabitStreak({required this.momentId, required this.title, required this.streakDays});
  final int momentId;
  final String title;
  final int streakDays;
  factory HabitStreak.fromJson(Map<String, dynamic> j) => HabitStreak(
        momentId: (j['moment_id'] as num).toInt(),
        title: (j['title'] as String?) ?? '',
        streakDays: (j['streak_days'] as num).toInt(),
      );
}

class ProfileStats {
  ProfileStats({
    required this.totalMoments,
    required this.activeCount,
    required this.doneToday,
    required this.overdueCount,
    required this.weekCompleted,
    required this.weekPlanned,
    required this.habitStreaks,
  });
  final int totalMoments;
  final int activeCount;
  final int doneToday;
  final int overdueCount;
  final int weekCompleted;
  final int weekPlanned;
  final List<HabitStreak> habitStreaks;

  factory ProfileStats.fromJson(Map<String, dynamic> j) => ProfileStats(
        totalMoments: (j['total_moments'] as num).toInt(),
        activeCount: (j['active_count'] as num).toInt(),
        doneToday: (j['done_today'] as num).toInt(),
        overdueCount: (j['overdue_count'] as num).toInt(),
        weekCompleted: (j['week_completed'] as num).toInt(),
        weekPlanned: (j['week_planned'] as num).toInt(),
        habitStreaks: ((j['habit_streaks'] as List?) ?? const [])
            .map((e) => HabitStreak.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}

final profileRepositoryProvider = Provider<ProfileRepository>(
  (ref) => ProfileRepository(ref.watch(dioProvider)),
);

final profileStatsProvider = FutureProvider.autoDispose<ProfileStats>(
  (ref) => ref.watch(profileRepositoryProvider).fetchStats(),
);
