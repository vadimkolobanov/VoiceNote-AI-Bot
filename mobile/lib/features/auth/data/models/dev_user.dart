class DevUser {
  const DevUser({
    required this.telegramId,
    required this.notesCount,
    this.firstName,
    this.username,
  });

  final int telegramId;
  final String? firstName;
  final String? username;
  final int notesCount;

  String get displayName {
    final name = (firstName ?? '').trim();
    if (name.isNotEmpty) return name;
    final uname = (username ?? '').trim();
    if (uname.isNotEmpty) return '@$uname';
    return 'id $telegramId';
  }

  factory DevUser.fromJson(Map<String, dynamic> json) => DevUser(
        telegramId: (json['telegram_id'] as num).toInt(),
        firstName: json['first_name'] as String?,
        username: json['username'] as String?,
        notesCount: (json['notes_count'] as num?)?.toInt() ?? 0,
      );
}
