/// User — отражает `UserPublic` из backend `/api/v1/auth/*` ответов.
///
/// Поля 1:1 совпадают с docs/PRODUCT_PLAN.md §4.3 + §5.2. is_pro вычисляется
/// бэком из `pro_until` и приходит уже как boolean.
class User {
  const User({
    required this.id,
    required this.timezone,
    required this.locale,
    required this.isPro,
    required this.createdAtIso,
    this.email,
    this.displayName,
    this.digestHour,
  });

  final int id;
  final String? email;
  final String? displayName;
  final String timezone;
  final String locale;
  final int? digestHour;
  final bool isPro;
  final String createdAtIso;

  factory User.fromJson(Map<String, dynamic> json) => User(
        id: (json['id'] as num).toInt(),
        email: json['email'] as String?,
        displayName: json['display_name'] as String?,
        timezone: (json['timezone'] as String?) ?? 'Europe/Moscow',
        locale: (json['locale'] as String?) ?? 'ru',
        digestHour: (json['digest_hour'] as num?)?.toInt(),
        isPro: (json['is_pro'] as bool?) ?? false,
        createdAtIso: (json['created_at'] as String?) ?? '',
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'email': email,
        'display_name': displayName,
        'timezone': timezone,
        'locale': locale,
        'digest_hour': digestHour,
        'is_pro': isPro,
        'created_at': createdAtIso,
      };

  User copyWith({
    String? displayName,
    String? timezone,
    String? locale,
    int? digestHour,
    bool? isPro,
  }) =>
      User(
        id: id,
        email: email,
        displayName: displayName ?? this.displayName,
        timezone: timezone ?? this.timezone,
        locale: locale ?? this.locale,
        digestHour: digestHour ?? this.digestHour,
        isPro: isPro ?? this.isPro,
        createdAtIso: createdAtIso,
      );
}
