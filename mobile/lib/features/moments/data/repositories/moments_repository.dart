import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/network/dio_client.dart';
import 'package:voicenote_ai/features/moments/data/models/moment.dart';

/// /api/v1/moments/* клиент. Поверхность — PRODUCT_PLAN.md §5.2.
class MomentsRepository {
  MomentsRepository(this._dio);

  final Dio _dio;

  /// Список моментов в одном из 3 представлений.
  Future<MomentsList> list({
    required String view, // 'today' | 'timeline' | 'rhythm'
    int? cursor,
    int limit = 50,
  }) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/moments',
        queryParameters: {
          'view': view,
          if (cursor != null) 'cursor': cursor,
          'limit': limit,
        },
      );
      final data = response.data!;
      final items = (data['items'] as List<dynamic>? ?? [])
          .map((e) => Moment.fromJson(e as Map<String, dynamic>))
          .toList(growable: false);
      return MomentsList(items: items, nextCursor: (data['next_cursor'] as num?)?.toInt());
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Moment> create({
    required String rawText,
    String source = 'text',
    String? clientId,
    DateTime? occursAt,
    String? rrule,
  }) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/moments',
        data: {
          'raw_text': rawText,
          'source': source,
          if (clientId != null) 'client_id': clientId,
          if (occursAt != null) 'occurs_at': occursAt.toUtc().toIso8601String(),
          if (rrule != null && rrule.isNotEmpty) 'rrule': rrule,
        },
      );
      return Moment.fromJson(response.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Moment> get(int id) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>('/moments/$id');
      return Moment.fromJson(response.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Moment> patch(int id, Map<String, dynamic> changes) async {
    try {
      final response = await _dio.patch<Map<String, dynamic>>(
        '/moments/$id',
        data: changes,
      );
      return Moment.fromJson(response.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Moment> complete(int id) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>('/moments/$id/complete');
      return Moment.fromJson(response.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Moment> snooze(int id, DateTime until) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/moments/$id/snooze',
        data: {'until': until.toUtc().toIso8601String()},
      );
      return Moment.fromJson(response.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> delete(int id) async {
    try {
      await _dio.delete<void>('/moments/$id');
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}

class MomentsList {
  const MomentsList({required this.items, this.nextCursor});
  final List<Moment> items;
  final int? nextCursor;
}

final momentsRepositoryProvider = Provider<MomentsRepository>(
  (ref) => MomentsRepository(ref.watch(dioProvider)),
);
