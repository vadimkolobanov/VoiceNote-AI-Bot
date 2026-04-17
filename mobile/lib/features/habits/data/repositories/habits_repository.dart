import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/network/dio_client.dart';
import 'package:voicenote_ai/features/habits/data/models/habit.dart';

class HabitsRepository {
  HabitsRepository(this._dio);
  final Dio _dio;

  Future<List<Habit>> list() async {
    try {
      final response = await _dio.get<dynamic>('/habits');
      final raw = response.data;
      final list = raw is List
          ? raw
          : (raw is Map ? (raw['items'] as List?) ?? const [] : const <dynamic>[]);
      return list
          .map((e) => Habit.fromJson(e as Map<String, dynamic>))
          .toList(growable: false);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<List<Habit>> createFromText(String text) async {
    try {
      final response = await _dio.post<dynamic>(
        '/habits',
        data: {'text': text},
      );
      final data = response.data;
      final list = data is List ? data : (data is Map ? data['items'] as List? ?? const [] : const <dynamic>[]);
      return list
          .map((e) => Habit.fromJson(e as Map<String, dynamic>))
          .toList(growable: false);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> track(int habitId, HabitTrackStatus status, {DateTime? date}) async {
    try {
      await _dio.post<void>(
        '/habits/$habitId/track',
        data: {
          'status': status.name,
          if (date != null) 'date': date.toIso8601String().split('T').first,
        },
      );
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<List<HabitDailyStat>> weeklyStats(int habitId) async {
    try {
      final response = await _dio.get<dynamic>(
        '/habits/$habitId/stats',
        queryParameters: {'days': 7},
      );
      final raw = response.data;
      final list = raw is List ? raw : (raw is Map ? raw['items'] as List? ?? const [] : const <dynamic>[]);
      return list
          .map((e) => HabitDailyStat.fromJson(e as Map<String, dynamic>))
          .toList(growable: false);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> delete(int id) async {
    try {
      await _dio.delete<void>('/habits/$id');
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}

final habitsRepositoryProvider = Provider<HabitsRepository>(
  (ref) => HabitsRepository(ref.watch(dioProvider)),
);
