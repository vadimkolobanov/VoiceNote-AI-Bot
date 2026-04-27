import 'dart:io';

import 'package:dio/dio.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/core/network/dio_client.dart';

import 'local_notifications.dart';
import 'pending_action.dart';

final pushServiceProvider = Provider<PushService>((ref) {
  return PushService(ref);
});

class PushService {
  PushService(this._ref);

  final Ref _ref;
  String? _lastRegisteredToken;

  static Future<void> initFirebase() async {
    if (Firebase.apps.isEmpty) {
      try {
        await Firebase.initializeApp();
      } catch (e) {
        debugPrint('[push] Firebase.initializeApp failed: $e');
      }
    }
    // Локальные уведомления + регистрация background-handler.
    try {
      await initLocalNotifications();
      FirebaseMessaging.onBackgroundMessage(firebaseBgMessageHandler);
      FirebaseMessaging.onMessage.listen((msg) {
        showReminderFromMessage(msg);
      });
    } catch (e) {
      debugPrint('[push] init local notifications failed: $e');
    }
  }

  /// Запросить разрешение, получить FCM-токен и зарегистрировать его на бэке.
  /// Вызывать после успешного логина.
  Future<void> registerForUser() async {
    if (Firebase.apps.isEmpty) {
      debugPrint('[push] Firebase not initialized — skip register');
      return;
    }
    try {
      final messaging = FirebaseMessaging.instance;
      final settings = await messaging.requestPermission(
        alert: true,
        badge: true,
        sound: true,
      );
      if (settings.authorizationStatus == AuthorizationStatus.denied) {
        debugPrint('[push] notification permission denied');
        return;
      }

      final token = await messaging.getToken();
      if (token == null || token.isEmpty) {
        debugPrint('[push] empty FCM token');
        return;
      }
      await _sendToBackend(token);

      messaging.onTokenRefresh.listen((newToken) {
        _sendToBackend(newToken);
      });
    } catch (e, st) {
      debugPrint('[push] registerForUser failed: $e\n$st');
    }
  }

  Future<void> _sendToBackend(String token) async {
    if (token == _lastRegisteredToken) return;
    final dio = _ref.read(dioProvider);
    final platform = Platform.isIOS ? 'ios' : 'android';
    try {
      await dio.post<dynamic>(
        '/push/register',
        data: <String, String>{'token': token, 'platform': platform},
      );
      _lastRegisteredToken = token;
      debugPrint('[push] registered token (${token.substring(0, 12)}…)');
    } on DioException catch (e) {
      debugPrint('[push] register failed: ${e.response?.statusCode} ${e.message}');
    }
  }

  /// Подобрать накопленные нажатия inline-кнопок из push'ей и выполнить
  /// соответствующие API-вызовы. Вызывать на старте и при возврате из фона.
  Future<List<int>> processPendingActions() async {
    final actions = await PendingAction.drain();
    if (actions.isEmpty) return const [];
    final dio = _ref.read(dioProvider);
    final touched = <int>[];
    for (final a in actions) {
      try {
        if (a.actionId == actionDone) {
          await dio.post<dynamic>('/moments/${a.momentId}/complete');
          touched.add(a.momentId);
        } else if (a.actionId == actionSnooze15) {
          final until = DateTime.now()
              .toUtc()
              .add(const Duration(minutes: 15))
              .toIso8601String();
          await dio.post<dynamic>(
            '/moments/${a.momentId}/snooze',
            data: <String, String>{'until': until},
          );
          touched.add(a.momentId);
        }
      } on DioException catch (e) {
        debugPrint('[push] pending action failed: ${e.message}');
      }
    }
    return touched;
  }

  Future<void> unregister() async {
    final token = _lastRegisteredToken;
    if (token == null) return;
    final dio = _ref.read(dioProvider);
    try {
      await dio.post<dynamic>('/push/unregister', data: {'token': token});
    } on DioException catch (_) {}
    _lastRegisteredToken = null;
  }
}
