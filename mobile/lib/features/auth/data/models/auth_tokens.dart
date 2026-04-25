import 'user.dart';

/// Ответ на `/api/v1/auth/email/{register,login}` или `/auth/refresh`.
///
/// Поля называются `access`/`refresh` — точно так же как в backend
/// `TokenPairResponse` (PRODUCT_PLAN.md §5.2). У `/auth/refresh` нет user.
class AuthTokens {
  const AuthTokens({
    required this.access,
    required this.refresh,
    this.user,
  });

  final String access;
  final String refresh;
  final User? user;

  factory AuthTokens.fromJson(Map<String, dynamic> json) => AuthTokens(
        access: json['access'] as String,
        refresh: json['refresh'] as String,
        user: json['user'] is Map<String, dynamic>
            ? User.fromJson(json['user'] as Map<String, dynamic>)
            : null,
      );
}
