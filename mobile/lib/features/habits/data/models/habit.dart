enum HabitTrackStatus { done, skipped }

class Habit {
  const Habit({
    required this.id,
    required this.name,
    required this.streak,
    required this.isActive,
    this.frequencyRule,
    this.reminderTime,
    this.iconName,
    this.completedToday = false,
  });

  final int id;
  final String name;
  final int streak;
  final bool isActive;
  final String? frequencyRule;
  final String? reminderTime;
  final String? iconName;
  final bool completedToday;

  factory Habit.fromJson(Map<String, dynamic> json) => Habit(
        id: (json['id'] as num).toInt(),
        name: (json['name'] as String?) ?? '',
        streak: (json['current_streak'] as num?)?.toInt() ??
            (json['streak'] as num?)?.toInt() ??
            0,
        isActive: (json['is_active'] as bool?) ?? true,
        frequencyRule: json['frequency_rule'] as String?,
        reminderTime: json['reminder_time'] as String?,
        iconName: json['icon'] as String?,
        completedToday: (json['completed_today'] as bool?) ?? false,
      );

  Habit copyWith({
    int? streak,
    bool? completedToday,
  }) =>
      Habit(
        id: id,
        name: name,
        streak: streak ?? this.streak,
        isActive: isActive,
        frequencyRule: frequencyRule,
        reminderTime: reminderTime,
        iconName: iconName,
        completedToday: completedToday ?? this.completedToday,
      );
}

class HabitDailyStat {
  const HabitDailyStat({required this.date, required this.status});

  final DateTime date;
  final HabitTrackStatus? status;

  factory HabitDailyStat.fromJson(Map<String, dynamic> json) {
    final raw = json['status'] as String?;
    return HabitDailyStat(
      date: DateTime.parse(json['date'] as String),
      status: switch (raw) {
        'done' => HabitTrackStatus.done,
        'skipped' => HabitTrackStatus.skipped,
        _ => null,
      },
    );
  }
}
