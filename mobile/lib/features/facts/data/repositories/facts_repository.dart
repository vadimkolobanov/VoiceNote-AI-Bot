import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/network/dio_client.dart';
import 'package:voicenote_ai/features/facts/data/models/fact.dart';

/// /api/v1/facts/* — PRODUCT_PLAN.md §5.2, экран S15.
class FactsRepository {
  FactsRepository(this._dio);
  final Dio _dio;

  Future<List<Fact>> list({String? kind}) async {
    try {
      final response = await _dio.get<List<dynamic>>(
        '/facts',
        queryParameters: {if (kind != null) 'kind': kind},
      );
      return (response.data ?? const [])
          .map((e) => Fact.fromJson(e as Map<String, dynamic>))
          .toList(growable: false);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Fact> create({
    required String kind,
    required String key,
    required Map<String, dynamic> value,
    double confidence = 1.0,
  }) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/facts',
        data: {
          'kind': kind,
          'key': key,
          'value': value,
          'confidence': confidence,
        },
      );
      return Fact.fromJson(response.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Fact> patch(int id, Map<String, dynamic> changes) async {
    try {
      final response = await _dio.patch<Map<String, dynamic>>(
        '/facts/$id',
        data: changes,
      );
      return Fact.fromJson(response.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> delete(int id) async {
    try {
      await _dio.delete<void>('/facts/$id');
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}

final factsRepositoryProvider = Provider<FactsRepository>(
  (ref) => FactsRepository(ref.watch(dioProvider)),
);

final factsListProvider = FutureProvider.autoDispose<List<Fact>>((ref) async {
  final repo = ref.watch(factsRepositoryProvider);
  return repo.list();
});
