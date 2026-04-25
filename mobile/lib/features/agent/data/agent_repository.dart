import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/network/dio_client.dart';

/// /api/v1/agent/* (PRODUCT_PLAN.md §5.2 + §6.3). Pro-only.
class AgentRepository {
  AgentRepository(this._dio);
  final Dio _dio;

  Future<AgentAnswer> ask(String question) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/agent/ask',
        data: {'question': question},
      );
      return AgentAnswer.fromJson(response.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}

@immutable
class AgentAnswer {
  const AgentAnswer({required this.answer, required this.cited});
  final String answer;
  final List<CitedMoment> cited;

  factory AgentAnswer.fromJson(Map<String, dynamic> json) => AgentAnswer(
        answer: (json['answer'] as String?) ?? '',
        cited: ((json['cited_moments'] as List<dynamic>?) ?? const [])
            .map((e) => CitedMoment.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}

@immutable
class CitedMoment {
  const CitedMoment({required this.id, required this.title, required this.snippet});
  final int id;
  final String title;
  final String snippet;

  factory CitedMoment.fromJson(Map<String, dynamic> json) => CitedMoment(
        id: (json['id'] as num).toInt(),
        title: (json['title'] as String?) ?? '',
        snippet: (json['snippet'] as String?) ?? '',
      );
}

final agentRepositoryProvider = Provider<AgentRepository>(
  (ref) => AgentRepository(ref.watch(dioProvider)),
);
