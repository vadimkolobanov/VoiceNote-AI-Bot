import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/network/dio_client.dart';
import 'package:voicenote_ai/features/payments/data/models/subscription.dart';

class PaymentsRepository {
  PaymentsRepository(this._dio);
  final Dio _dio;

  Future<String> createPayment(SubscriptionPlan plan) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/payments/create',
        data: {'plan': plan.apiValue},
      );
      return response.data!['confirmation_url'] as String;
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<Subscription> subscription() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>('/payments/subscription');
      return Subscription.fromJson(response.data!);
    } on DioException catch (e) {
      // Бэкенд ещё может не иметь этого endpoint-а — трактуем как "нет подписки".
      if (e.response?.statusCode == 404) {
        return const Subscription(
          status: 'inactive',
          plan: null,
          autoRenew: false,
        );
      }
      throw ApiException.fromDio(e);
    }
  }

  Future<Subscription> cancel() async {
    try {
      final response = await _dio.post<Map<String, dynamic>>('/payments/cancel');
      return Subscription.fromJson(response.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}

final paymentsRepositoryProvider = Provider<PaymentsRepository>(
  (ref) => PaymentsRepository(ref.watch(dioProvider)),
);

final subscriptionProvider = FutureProvider.autoDispose<Subscription>(
  (ref) async => ref.watch(paymentsRepositoryProvider).subscription(),
);
