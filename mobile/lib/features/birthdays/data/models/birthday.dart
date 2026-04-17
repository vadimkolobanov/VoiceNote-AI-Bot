class Birthday {
  const Birthday({
    required this.id,
    required this.name,
    required this.day,
    required this.month,
    this.year,
  });

  final int id;
  final String name;
  final int day;
  final int month;
  final int? year;

  factory Birthday.fromJson(Map<String, dynamic> json) => Birthday(
        id: (json['id'] as num).toInt(),
        name: (json['person_name'] as String?) ?? '',
        day: (json['birth_day'] as num).toInt(),
        month: (json['birth_month'] as num).toInt(),
        year: (json['birth_year'] as num?)?.toInt(),
      );

  DateTime get nextDate {
    final now = DateTime.now();
    final candidate = DateTime(now.year, month, day);
    if (candidate.isBefore(DateTime(now.year, now.month, now.day))) {
      return DateTime(now.year + 1, month, day);
    }
    return candidate;
  }

  int get daysUntil {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    return nextDate.difference(today).inDays;
  }
}
