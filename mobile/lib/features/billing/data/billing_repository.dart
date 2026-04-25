import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/network/dio_client.dart';

/// /api/v1/billing/* — клиент (PRODUCT_PLAN.md §5.2 + §8).
class BillingRepository {
  BillingRepository(this._dio);
  final Dio _dio;

  Future<List<BillingPlan>> plans() async {
    try {
      final response = await _dio.get<List<dynamic>>('/billing/plans');
      return (response.data ?? const [])
          .map((e) => BillingPlan.fromJson(e as Map<String, dynamic>))
          .toList(growable: false);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  /// Создаёт подписку и возвращает confirmation_url.
  /// Если `is_mock=true`, URL — это deeplink на наш собственный mock-flow.
  Future<SubscribeResult> subscribe(String planCode) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/billing/subscribe',
        data: {'plan': planCode},
      );
      return SubscribeResult.fromJson(response.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<BillingStatus> status() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>('/billing/status');
      return BillingStatus.fromJson(response.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> cancel() async {
    try {
      await _dio.post<void>('/billing/cancel');
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  /// Mock-only. Используется внутри embedded WebView, когда backend в
  /// `YK_MODE=mock` — UI показывает кнопку «Я заплатил» и зовёт это.
  Future<void> mockConfirm(String externalId) async {
    try {
      await _dio.post<void>(
        '/billing/mock/confirm',
        queryParameters: {'external_id': externalId},
      );
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}

@immutable
class BillingPlan {
  const BillingPlan({
    required this.code,
    required this.title,
    required this.priceRub,
    required this.periodDays,
  });
  final String code;
  final String title;
  final String priceRub;
  final int periodDays;

  factory BillingPlan.fromJson(Map<String, dynamic> json) => BillingPlan(
        code: json['code'] as String,
        title: json['title'] as String,
        priceRub: json['price_rub'] as String,
        periodDays: (json['period_days'] as num).toInt(),
      );
}

@immutable
class SubscribeResult {
  const SubscribeResult({
    required this.subscriptionId,
    required this.externalId,
    required this.isMock,
    this.confirmationUrl,
  });
  final int subscriptionId;
  final String externalId;
  final bool isMock;
  final String? confirmationUrl;

  factory SubscribeResult.fromJson(Map<String, dynamic> json) => SubscribeResult(
        subscriptionId: (json['subscription_id'] as num).toInt(),
        externalId: json['external_id'] as String,
        isMock: (json['is_mock'] as bool?) ?? false,
        confirmationUrl: json['confirmation_url'] as String?,
      );
}

@immutable
class BillingStatus {
  const BillingStatus({
    required this.isPro,
    required this.autoRenew,
    this.proUntil,
    this.plan,
    this.status,
    this.endsAt,
  });
  final bool isPro;
  final bool autoRenew;
  final String? proUntil;
  final String? plan;
  final String? status;
  final String? endsAt;

  factory BillingStatus.fromJson(Map<String, dynamic> json) => BillingStatus(
        isPro: (json['is_pro'] as bool?) ?? false,
        autoRenew: (json['auto_renew'] as bool?) ?? false,
        proUntil: json['pro_until'] as String?,
        plan: json['plan'] as String?,
        status: json['status'] as String?,
        endsAt: json['ends_at'] as String?,
      );
}

final billingRepositoryProvider = Provider<BillingRepository>(
  (ref) => BillingRepository(ref.watch(dioProvider)),
);

final billingPlansProvider = FutureProvider.autoDispose<List<BillingPlan>>(
  (ref) => ref.watch(billingRepositoryProvider).plans(),
);

final billingStatusProvider = FutureProvider.autoDispose<BillingStatus>(
  (ref) => ref.watch(billingRepositoryProvider).status(),
);
