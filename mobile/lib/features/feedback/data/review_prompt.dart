import 'package:flutter/foundation.dart';
import 'package:in_app_review/in_app_review.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Просим оценку в RuStore/Google Play через in_app_review API.
///
/// Логика: после N-го (по умолчанию 3) успешного создания момента
/// **и** при условии что мы не просили в последние 30 дней — показываем
/// нативный системный prompt стора (без перехода в стор, в текущем приложении).
class ReviewPrompt {
  ReviewPrompt._();

  static const _kCounterKey = 'mx_review_moment_count';
  static const _kLastShownKey = 'mx_review_last_shown_ts';
  static const _triggerAt = 3;
  static const _cooldown = Duration(days: 30);

  /// Зови после каждого успешного создания момента.
  static Future<void> bumpAndMaybeAsk() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final n = (prefs.getInt(_kCounterKey) ?? 0) + 1;
      await prefs.setInt(_kCounterKey, n);

      if (n < _triggerAt) return;

      final lastTs = prefs.getInt(_kLastShownKey) ?? 0;
      final last = DateTime.fromMillisecondsSinceEpoch(lastTs);
      if (DateTime.now().difference(last) < _cooldown) return;

      final review = InAppReview.instance;
      final available = await review.isAvailable();
      if (!available) return;

      await review.requestReview();
      await prefs.setInt(_kLastShownKey, DateTime.now().millisecondsSinceEpoch);
      // не сбрасываем counter, но и больше не покажем 30 дней
    } catch (e) {
      if (kDebugMode) debugPrint('[review] $e');
    }
  }
}
