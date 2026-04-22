/// Единая модель напоминаний (Phase 3a).
///
/// Объединяет на клиенте note / habit / birthday в одну ленту.
enum ReminderEntityType {
  note,
  habit,
  birthday;

  static ReminderEntityType parse(String raw) {
    switch (raw) {
      case 'habit':
        return ReminderEntityType.habit;
      case 'birthday':
        return ReminderEntityType.birthday;
      default:
        return ReminderEntityType.note;
    }
  }
}

class Reminder {
  const Reminder({
    required this.id,
    required this.entityType,
    required this.entityId,
    required this.title,
    required this.dtstart,
    required this.status,
    this.rrule,
    this.nextFireAt,
    this.lastFiredAt,
    this.preReminderMinutes = 0,
  });

  final int id;
  final ReminderEntityType entityType;
  final int entityId;
  final String title;
  final String? rrule;
  final DateTime dtstart;
  final DateTime? nextFireAt;
  final DateTime? lastFiredAt;
  final int preReminderMinutes;
  final String status; // active | paused | completed

  bool get isRecurring => rrule != null && rrule!.isNotEmpty;

  factory Reminder.fromJson(Map<String, dynamic> json) => Reminder(
        id: (json['id'] as num).toInt(),
        entityType: ReminderEntityType.parse(json['entity_type'] as String),
        entityId: (json['entity_id'] as num).toInt(),
        title: (json['title'] as String?) ?? '',
        rrule: json['rrule'] as String?,
        dtstart: DateTime.parse(json['dtstart'] as String),
        nextFireAt: json['next_fire_at'] != null
            ? DateTime.parse(json['next_fire_at'] as String)
            : null,
        lastFiredAt: json['last_fired_at'] != null
            ? DateTime.parse(json['last_fired_at'] as String)
            : null,
        preReminderMinutes: (json['pre_reminder_minutes'] as num?)?.toInt() ?? 0,
        status: (json['status'] as String?) ?? 'active',
      );
}
