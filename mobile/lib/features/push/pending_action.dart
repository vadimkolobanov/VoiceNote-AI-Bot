import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'local_notifications.dart';

/// Очередь намерений «выполнить действие из push», которые не могли
/// быть исполнены в момент тапа (например, тап в фоне). Хранится в
/// SharedPreferences (доступно из любого isolate); UI-слой читает её
/// при старте и при возвращении из фона.
class PendingAction {
  PendingAction({required this.actionId, required this.momentId, required this.ts});

  final String actionId;
  final int momentId;
  final int ts;

  Map<String, dynamic> toJson() =>
      {'a': actionId, 'm': momentId, 't': ts};

  static PendingAction? fromJson(Map<String, dynamic> j) {
    final a = j['a'] as String?;
    final m = j['m'];
    final t = j['t'];
    if (a == null || m == null) return null;
    return PendingAction(
      actionId: a,
      momentId: (m as num).toInt(),
      ts: (t as num?)?.toInt() ?? 0,
    );
  }

  static const _key = 'mx_pending_actions';

  static void saveFromResponseSync(NotificationResponse resp) {
    if (resp.actionId == null && resp.payload == null) return;
    if (resp.payload == null) return;
    Map<String, dynamic>? data;
    try {
      data = jsonDecode(resp.payload!) as Map<String, dynamic>;
    } catch (_) {
      return;
    }
    final id = (data['moment_id'] as num?)?.toInt() ?? 0;
    if (id == 0) return;
    final aid = resp.actionId;
    if (aid != actionDone && aid != actionSnooze15) {
      // тап по самому уведомлению (без кнопки) — пока игнорируем
      return;
    }
    // SharedPreferences API асинхронный; делаем fire-and-forget,
    // потом UI прочитает.
    () async {
      final prefs = await SharedPreferences.getInstance();
      final existing = prefs.getStringList(_key) ?? <String>[];
      final entry = jsonEncode({
        'a': aid,
        'm': id,
        't': DateTime.now().millisecondsSinceEpoch,
      });
      existing.add(entry);
      await prefs.setStringList(_key, existing);
      if (kDebugMode) debugPrint('[push] pending action saved: $aid -> $id');
    }();
  }

  static Future<List<PendingAction>> drain() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getStringList(_key) ?? const <String>[];
    if (raw.isEmpty) return const [];
    await prefs.remove(_key);
    final out = <PendingAction>[];
    for (final s in raw) {
      try {
        final j = jsonDecode(s) as Map<String, dynamic>;
        final p = PendingAction.fromJson(j);
        if (p != null) out.add(p);
      } catch (_) {}
    }
    return out;
  }
}

final pendingActionsProvider = Provider<PendingAction>((ref) {
  throw UnimplementedError('use PendingAction.drain() directly');
});
