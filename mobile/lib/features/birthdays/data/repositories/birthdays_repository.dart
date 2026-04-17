import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/network/dio_client.dart';
import 'package:voicenote_ai/features/birthdays/data/models/birthday.dart';

class BirthdaysRepository {
  BirthdaysRepository(this._dio);
  final Dio _dio;

  Future<List<Birthday>> list({int page = 1, int perPage = 100}) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/birthdays',
        queryParameters: {'page': page, 'per_page': perPage},
      );
      final items = (response.data!['items'] as List?) ?? const [];
      return items
          .map((e) => Birthday.fromJson(e as Map<String, dynamic>))
          .toList(growable: false);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Birthday> create(String name, String dateDdMmYyyy) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/birthdays',
        data: {'person_name': name, 'birth_date': dateDdMmYyyy},
      );
      return Birthday.fromJson(response.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> delete(int id) async {
    try {
      await _dio.delete<void>('/birthdays/$id');
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}

final birthdaysRepositoryProvider = Provider<BirthdaysRepository>(
  (ref) => BirthdaysRepository(ref.watch(dioProvider)),
);

final birthdaysListProvider = FutureProvider.autoDispose<List<Birthday>>(
  (ref) async => ref.watch(birthdaysRepositoryProvider).list(),
);
