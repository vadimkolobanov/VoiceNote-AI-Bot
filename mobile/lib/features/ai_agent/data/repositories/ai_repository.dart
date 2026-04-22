import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/network/dio_client.dart';
import 'package:voicenote_ai/features/ai_agent/data/models/chat_message.dart';

class AiRepository {
  AiRepository(this._dio);
  final Dio _dio;

  Future<String> send(String message) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/memory/chat',
        data: {'message': message},
      );
      return (response.data!['reply'] as String?) ?? '';
    } on DioException catch (e) {
      if (e.response?.statusCode == 404) {
        return 'AI-агент появится в ближайших обновлениях. Следите за новостями!';
      }
      throw ApiException.fromDio(e);
    }
  }

  Future<List<ChatMessage>> history({int limit = 50}) async {
    try {
      final response = await _dio.get<dynamic>(
        '/memory/conversations',
        queryParameters: {'limit': limit},
      );
      final raw = response.data;
      final list = raw is List
          ? raw
          : (raw is Map ? (raw['items'] as List?) ?? const [] : const <dynamic>[]);
      return list
          .map((e) => ChatMessage.fromJson(e as Map<String, dynamic>))
          .toList(growable: false);
    } on DioException catch (e) {
      if (e.response?.statusCode == 404) return const <ChatMessage>[];
      throw ApiException.fromDio(e);
    }
  }

  Future<List<MemoryFact>> facts() async {
    try {
      final response = await _dio.get<dynamic>('/memory/facts');
      final raw = response.data;
      final list = raw is List
          ? raw
          : (raw is Map ? (raw['items'] as List?) ?? const [] : const <dynamic>[]);
      return list
          .map((e) => MemoryFact.fromJson(e as Map<String, dynamic>))
          .toList(growable: false);
    } on DioException catch (e) {
      if (e.response?.statusCode == 404) return const <MemoryFact>[];
      throw ApiException.fromDio(e);
    }
  }

  Future<void> deleteFact(int id) async {
    try {
      await _dio.delete<void>('/memory/facts/$id');
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> reset() async {
    try {
      await _dio.delete<void>('/memory/reset');
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}

final aiRepositoryProvider = Provider<AiRepository>(
  (ref) => AiRepository(ref.watch(dioProvider)),
);
