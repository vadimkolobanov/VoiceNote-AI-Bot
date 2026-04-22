import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/network/dio_client.dart';
import 'package:voicenote_ai/features/shopping_list/data/models/shopping_list.dart';

class ShoppingRepository {
  ShoppingRepository(this._dio);
  final Dio _dio;

  Future<List<ShoppingListSummary>> listLists({bool includeArchived = false}) async {
    try {
      final response = await _dio.get<List<dynamic>>(
        '/shopping-lists',
        queryParameters: {'include_archived': includeArchived},
      );
      return (response.data ?? const [])
          .map((e) => ShoppingListSummary.fromJson(e as Map<String, dynamic>))
          .toList(growable: false);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<ShoppingListDetail> getList(int id) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>('/shopping-lists/$id');
      return ShoppingListDetail.fromJson(response.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<ShoppingListDetail> createList(String title) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/shopping-lists',
        data: {'title': title},
      );
      return ShoppingListDetail.fromJson(response.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<ShoppingListDetail> renameList(int id, String title) async {
    try {
      final response = await _dio.patch<Map<String, dynamic>>(
        '/shopping-lists/$id',
        data: {'title': title},
      );
      return ShoppingListDetail.fromJson(response.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> deleteList(int id) async {
    try {
      await _dio.delete<void>('/shopping-lists/$id');
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<ShoppingListDetail> archiveList(int id) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>('/shopping-lists/$id/archive');
      return ShoppingListDetail.fromJson(response.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<ShoppingListDetail> restoreList(int id) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>('/shopping-lists/$id/restore');
      return ShoppingListDetail.fromJson(response.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<ShoppingItem> addItem(int listId, String name, {String? quantity}) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/shopping-lists/$listId/items',
        data: {
          'name': name,
          if (quantity != null && quantity.isNotEmpty) 'quantity': quantity,
        },
      );
      return ShoppingItem.fromJson(response.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<ShoppingItem> toggleItem(int itemId, bool checked) async {
    try {
      final response = await _dio.patch<Map<String, dynamic>>(
        '/shopping-lists/items/$itemId',
        data: {'checked': checked},
      );
      return ShoppingItem.fromJson(response.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> deleteItem(int itemId) async {
    try {
      await _dio.delete<void>('/shopping-lists/items/$itemId');
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<ShoppingInvite> createInvite(int listId) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/shopping-lists/$listId/invites',
      );
      return ShoppingInvite.fromJson(response.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<int> joinByCode(String code) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/shopping-lists/join',
        data: {'code': code.trim().toUpperCase()},
      );
      return (response.data!['list_id'] as num).toInt();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> leave(int listId) async {
    try {
      await _dio.post<void>('/shopping-lists/$listId/leave');
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> removeMember(int listId, int userId) async {
    try {
      await _dio.delete<void>('/shopping-lists/$listId/members/$userId');
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}

final shoppingRepositoryProvider = Provider<ShoppingRepository>(
  (ref) => ShoppingRepository(ref.watch(dioProvider)),
);

// Summary для главного экрана
final shoppingListsProvider =
    FutureProvider.autoDispose.family<List<ShoppingListSummary>, bool>((ref, includeArchived) {
  return ref.watch(shoppingRepositoryProvider).listLists(includeArchived: includeArchived);
});

// Детали одного списка
final shoppingListDetailProvider =
    FutureProvider.autoDispose.family<ShoppingListDetail, int>((ref, id) {
  return ref.watch(shoppingRepositoryProvider).getList(id);
});
