import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart' show WidgetsFlutterBinding;
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:firebase_messaging/firebase_messaging.dart';

import 'pending_action.dart';

const String reminderChannelId = 'reminder_v1';
const String reminderChannelName = 'Напоминания';
const String actionDone = 'mx_done';
const String actionSnooze15 = 'mx_snooze15';

final FlutterLocalNotificationsPlugin _ln = FlutterLocalNotificationsPlugin();

FlutterLocalNotificationsPlugin get localNotifications => _ln;

Future<void> initLocalNotifications({
  void Function(NotificationResponse)? onTap,
}) async {
  const androidInit = AndroidInitializationSettings('@mipmap/ic_launcher');
  const initSettings = InitializationSettings(android: androidInit);

  await _ln.initialize(
    initSettings,
    onDidReceiveNotificationResponse: (resp) {
      _handleResponse(resp);
      if (onTap != null) onTap(resp);
    },
    onDidReceiveBackgroundNotificationResponse: notificationBgHandler,
  );

  // Android 13+ требует отдельный runtime-permission на пуши.
  await _ln
      .resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin>()
      ?.requestNotificationsPermission();

  await _ln
      .resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin>()
      ?.createNotificationChannel(
    const AndroidNotificationChannel(
      reminderChannelId,
      reminderChannelName,
      description: 'Напоминания о моментах и привычках',
      importance: Importance.high,
    ),
  );
}

Future<void> showReminderFromMessage(RemoteMessage m) async {
  final data = m.data;
  final momentId = int.tryParse((data['moment_id'] ?? '').toString()) ?? 0;
  final title = (data['title'] ?? 'Напоминание').toString();
  final body = (data['body'] ?? '').toString();
  await _ln.show(
    momentId == 0 ? DateTime.now().millisecondsSinceEpoch ~/ 1000 : momentId,
    title,
    body,
    NotificationDetails(
      android: AndroidNotificationDetails(
        reminderChannelId,
        reminderChannelName,
        importance: Importance.high,
        priority: Priority.high,
        category: AndroidNotificationCategory.reminder,
        actions: <AndroidNotificationAction>[
          const AndroidNotificationAction(
            actionDone,
            'Выполнено',
            showsUserInterface: false,
            cancelNotification: true,
          ),
          const AndroidNotificationAction(
            actionSnooze15,
            '+15 мин',
            showsUserInterface: false,
            cancelNotification: true,
          ),
        ],
      ),
    ),
    payload: jsonEncode({'moment_id': momentId, 'kind': data['kind'] ?? 'reminder'}),
  );
}

@pragma('vm:entry-point')
void notificationBgHandler(NotificationResponse resp) {
  // background isolate — в отдельной памяти, dio/secure storage недоступны
  // напрямую. Сохраняем намерение и обработаем при следующем запуске UI.
  PendingAction.saveFromResponseSync(resp);
}

void _handleResponse(NotificationResponse resp) {
  // Foreground / приложение в памяти. Кладём в очередь — обработчик
  // в UI-слое поднимет и выполнит API-вызов.
  PendingAction.saveFromResponseSync(resp);
}

@pragma('vm:entry-point')
Future<void> firebaseBgMessageHandler(RemoteMessage message) async {
  // background isolate — local_notifications надо init заново (отдельная
  // память). Firebase автоматически инициализирован FCM-плагином.
  WidgetsFlutterBinding.ensureInitialized();
  await initLocalNotifications();
  await showReminderFromMessage(message);
  if (kDebugMode) debugPrint('[push-bg] reminder shown for ${message.data}');
}
