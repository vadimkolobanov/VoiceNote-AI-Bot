import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/network/dio_client.dart';
import 'package:voicenote_ai/features/notes/data/models/note.dart';

enum NotesSegment { active, archive, shopping }

class NotesRepository {
  NotesRepository(this._dio);
  final Dio _dio;

  Future<PaginatedNotes> list({
    required NotesSegment segment,
    int page = 1,
    int perPage = 20,
  }) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/notes',
        queryParameters: {
          'page': page,
          'per_page': perPage,
          'archived': segment == NotesSegment.archive,
          if (segment == NotesSegment.shopping) 'category': 'покупки',
        },
      );
      return PaginatedNotes.fromJson(response.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Note> getById(int id) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>('/notes/$id');
      return Note.fromJson(response.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Note> create(String text) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/notes',
        data: {'text': text},
      );
      return Note.fromJson(response.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Note> update(int id, String text) async {
    try {
      final response = await _dio.put<Map<String, dynamic>>(
        '/notes/$id',
        data: {'text': text},
      );
      return Note.fromJson(response.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Note> complete(int id) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>('/notes/$id/complete');
      return Note.fromJson(response.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Note> unarchive(int id) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>('/notes/$id/unarchive');
      return Note.fromJson(response.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> delete(int id) async {
    try {
      await _dio.delete<void>('/notes/$id');
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<List<Note>> search(String query) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/notes/search',
        data: {'query': query},
      );
      final items = (response.data!['items'] as List?) ??
          (response.data!['results'] as List?) ??
          const [];
      return items
          .map((e) => Note.fromJson(e as Map<String, dynamic>))
          .toList(growable: false);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}

final notesRepositoryProvider = Provider<NotesRepository>(
  (ref) => NotesRepository(ref.watch(dioProvider)),
);
