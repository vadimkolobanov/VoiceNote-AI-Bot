import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/network/dio_client.dart';
import 'package:voicenote_ai/features/shopping_list/data/models/shopping_list.dart';

class ShoppingRepository {
  ShoppingRepository(this._dio);
  final Dio _dio;

  Future<ShoppingList?> getActive() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>('/shopping-list');
      if (response.data == null || response.data!.isEmpty) return null;
      return ShoppingList.fromJson(response.data!);
    } on DioException catch (e) {
      if (e.response?.statusCode == 404) return null;
      throw ApiException.fromDio(e);
    }
  }

  Future<ShoppingList> toggle(int index, bool checked) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/shopping-list/items',
        data: {'item_index': index, 'checked': checked},
      );
      return ShoppingList.fromJson(response.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<ShoppingList> add(String itemName) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/shopping-list/items/add',
        data: {'item_name': itemName},
      );
      return ShoppingList.fromJson(response.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> archive() async {
    try {
      await _dio.post<void>('/shopping-list/archive');
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}

final shoppingRepositoryProvider = Provider<ShoppingRepository>(
  (ref) => ShoppingRepository(ref.watch(dioProvider)),
);

final shoppingListProvider = FutureProvider.autoDispose<ShoppingList?>(
  (ref) async => ref.watch(shoppingRepositoryProvider).getActive(),
);
