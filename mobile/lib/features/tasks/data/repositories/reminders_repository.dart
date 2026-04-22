import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/network/dio_client.dart';
import 'package:voicenote_ai/features/tasks/data/models/reminder.dart';

class RemindersRepository {
  RemindersRepository(this._dio);
  final Dio _dio;

  Future<List<Reminder>> listAll({
    List<String> statuses = const ['active'],
    List<String> entityTypes = const ['note', 'habit', 'birthday'],
    int limit = 200,
  }) async {
    try {
      final response = await _dio.get<List<dynamic>>(
        '/reminders',
        queryParameters: {
          'status': statuses,
          'entity_type': entityTypes,
          'limit': limit,
        },
      );
      return (response.data ?? const [])
          .map((e) => Reminder.fromJson(e as Map<String, dynamic>))
          .toList(growable: false);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}

final remindersRepositoryProvider = Provider<RemindersRepository>(
  (ref) => RemindersRepository(ref.watch(dioProvider)),
);

final allRemindersProvider =
    FutureProvider.autoDispose<List<Reminder>>((ref) async {
  return ref.watch(remindersRepositoryProvider).listAll();
});
