import 'package:flutter/foundation.dart';

/// Moment — отражает `MomentOut` из backend `/api/v1/moments` (PRODUCT_PLAN.md
/// §4.1, §5.3). Никаких freezed/codegen — handwritten fromJson/toJson по §7.1.
///
/// Время хранится в двух формах:
/// - `occursAtIso` — UTC ISO8601 (для расчётов: «завтра», сортировка)
/// - `occursAtLocalIso` — naive ISO в TZ профиля юзера (для показа в UI;
///    не зависит от TZ устройства).
@immutable
class Moment {
  const Moment({
    required this.id,
    required this.rawText,
    required this.title,
    required this.facets,
    required this.status,
    required this.source,
    required this.createdVia,
    required this.createdAtIso,
    required this.updatedAtIso,
    this.clientId,
    this.summary,
    this.occursAtIso,
    this.occursAtLocalIso,
    this.rrule,
    this.rruleUntilIso,
    this.rruleUntilLocalIso,
    this.audioUrl,
    this.isHabit = false,
    this.completedToday = false,
    this.isOverdue = false,
    this.nextReminderAtIso,
    this.nextReminderAtLocalIso,
  });

  final int id;
  final String? clientId;
  final String rawText;
  final String title;
  final String? summary;
  final Map<String, dynamic> facets;
  final String? occursAtIso;
  final String? occursAtLocalIso;
  final String? rrule;
  final String? rruleUntilIso;
  final String? rruleUntilLocalIso;
  final String status;
  final String source;
  final String? audioUrl;
  final String createdAtIso;
  final String updatedAtIso;
  final String createdVia;
  final bool isHabit;
  final bool completedToday;
  final bool isOverdue;
  final String? nextReminderAtIso;
  final String? nextReminderAtLocalIso;

  // ── derived ────────────────────────────────────────────────────────────
  String get kind => (facets['kind'] as String?) ?? 'note';

  /// Время момента в TZ профиля пользователя — для отображения.
  /// Парсим `occursAtLocalIso` как naive (Dart считает локальным
  /// device-time, но мы НЕ применяем .toLocal() — дата уже в нужной TZ).
  /// Fallback на UTC.toLocal() для старых записей без `_local` полей.
  DateTime? get occursAt {
    if (occursAtLocalIso != null && occursAtLocalIso!.isNotEmpty) {
      return DateTime.tryParse(occursAtLocalIso!);
    }
    if (occursAtIso != null) {
      return DateTime.tryParse(occursAtIso!)?.toLocal();
    }
    return null;
  }

  /// Время создания: из UTC ISO в TZ устройства. Для «когда добавил» —
  /// устройство ок, потому что это реальное «вот сейчас».
  DateTime get createdAt =>
      DateTime.tryParse(createdAtIso)?.toLocal() ?? DateTime.now();

  bool get hasReminder => occursAt != null || nextReminderAt != null;
  bool get isDone => status == 'done';
  bool get isActive => status == 'active';

  /// Следующее срабатывание в TZ профиля. Для привычек — следующий день,
  /// для одноразового — moment.occurs_at если в будущем.
  DateTime? get nextReminderAt {
    if (nextReminderAtLocalIso != null && nextReminderAtLocalIso!.isNotEmpty) {
      return DateTime.tryParse(nextReminderAtLocalIso!);
    }
    if (nextReminderAtIso != null) {
      return DateTime.tryParse(nextReminderAtIso!)?.toLocal();
    }
    return null;
  }

  factory Moment.fromJson(Map<String, dynamic> json) => Moment(
        id: (json['id'] as num).toInt(),
        clientId: json['client_id'] as String?,
        rawText: (json['raw_text'] as String?) ?? '',
        title: (json['title'] as String?) ?? '',
        summary: json['summary'] as String?,
        facets:
            (json['facets'] as Map<String, dynamic>?) ?? const <String, dynamic>{},
        occursAtIso: json['occurs_at'] as String?,
        occursAtLocalIso: json['occurs_at_local'] as String?,
        rrule: json['rrule'] as String?,
        rruleUntilIso: json['rrule_until'] as String?,
        rruleUntilLocalIso: json['rrule_until_local'] as String?,
        status: (json['status'] as String?) ?? 'active',
        source: (json['source'] as String?) ?? 'text',
        audioUrl: json['audio_url'] as String?,
        createdAtIso: (json['created_at'] as String?) ?? '',
        updatedAtIso: (json['updated_at'] as String?) ?? '',
        createdVia: (json['created_via'] as String?) ?? 'mobile',
        isHabit: (json['is_habit'] as bool?) ?? false,
        completedToday: (json['completed_today'] as bool?) ?? false,
        isOverdue: (json['is_overdue'] as bool?) ?? false,
        nextReminderAtIso: json['next_reminder_at'] as String?,
        nextReminderAtLocalIso: json['next_reminder_at_local'] as String?,
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'client_id': clientId,
        'raw_text': rawText,
        'title': title,
        'summary': summary,
        'facets': facets,
        'occurs_at': occursAtIso,
        'occurs_at_local': occursAtLocalIso,
        'rrule': rrule,
        'rrule_until': rruleUntilIso,
        'rrule_until_local': rruleUntilLocalIso,
        'status': status,
        'source': source,
        'audio_url': audioUrl,
        'created_at': createdAtIso,
        'updated_at': updatedAtIso,
        'created_via': createdVia,
      };

  Moment copyWith({
    String? title,
    String? summary,
    String? occursAtIso,
    String? occursAtLocalIso,
    String? rrule,
    String? rruleUntilIso,
    String? rruleUntilLocalIso,
    String? status,
    Map<String, dynamic>? facets,
  }) =>
      Moment(
        id: id,
        clientId: clientId,
        rawText: rawText,
        title: title ?? this.title,
        summary: summary ?? this.summary,
        facets: facets ?? this.facets,
        occursAtIso: occursAtIso ?? this.occursAtIso,
        occursAtLocalIso: occursAtLocalIso ?? this.occursAtLocalIso,
        rrule: rrule ?? this.rrule,
        rruleUntilIso: rruleUntilIso ?? this.rruleUntilIso,
        rruleUntilLocalIso: rruleUntilLocalIso ?? this.rruleUntilLocalIso,
        status: status ?? this.status,
        source: source,
        audioUrl: audioUrl,
        createdAtIso: createdAtIso,
        updatedAtIso: updatedAtIso,
        createdVia: createdVia,
      );
}
