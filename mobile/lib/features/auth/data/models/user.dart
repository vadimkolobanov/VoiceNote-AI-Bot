class User {
  const User({
    required this.id,
    required this.firstName,
    required this.isVip,
    required this.level,
    required this.xp,
    required this.timezone,
    this.cityName,
  });

  final int id;
  final String firstName;
  final bool isVip;
  final int level;
  final int xp;
  final String timezone;
  final String? cityName;

  factory User.fromJson(Map<String, dynamic> json) => User(
        id: (json['telegram_id'] as num).toInt(),
        firstName: (json['first_name'] as String?) ?? 'Пользователь',
        isVip: (json['is_vip'] as bool?) ?? false,
        level: (json['level'] as num?)?.toInt() ?? 1,
        xp: (json['xp'] as num?)?.toInt() ?? 0,
        timezone: (json['timezone'] as String?) ?? 'UTC',
        cityName: json['city_name'] as String?,
      );

  User copyWith({
    String? firstName,
    bool? isVip,
    int? level,
    int? xp,
    String? timezone,
    String? cityName,
  }) =>
      User(
        id: id,
        firstName: firstName ?? this.firstName,
        isVip: isVip ?? this.isVip,
        level: level ?? this.level,
        xp: xp ?? this.xp,
        timezone: timezone ?? this.timezone,
        cityName: cityName ?? this.cityName,
      );
}
