import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/core/storage/secure_storage.dart';
import 'package:voicenote_ai/features/auth/data/models/user.dart';
import 'package:voicenote_ai/features/auth/data/repositories/auth_repository.dart';

enum SessionStatus { unknown, unauthenticated, authenticated }

@immutable
class SessionState {
  const SessionState({required this.status, this.user});

  final SessionStatus status;
  final User? user;

  SessionState copyWith({SessionStatus? status, User? user, bool clearUser = false}) {
    return SessionState(
      status: status ?? this.status,
      user: clearUser ? null : (user ?? this.user),
    );
  }
}

/// Owns the auth session: token bootstrapping, login, logout, user fetch.
class SessionController extends StateNotifier<SessionState> {
  SessionController(this._ref) : super(const SessionState(status: SessionStatus.unknown)) {
    _bootstrap();
  }

  final Ref _ref;

  /// Exposed so `GoRouter.refreshListenable` can subscribe to session changes.
  final ValueNotifier<int> refresh = ValueNotifier<int>(0);

  SecureTokenStorage get _storage => _ref.read(secureStorageProvider);
  AuthRepository get _repo => _ref.read(authRepositoryProvider);

  @override
  set state(SessionState value) {
    super.state = value;
    refresh.value++;
  }

  @override
  void dispose() {
    refresh.dispose();
    super.dispose();
  }

  Future<void> _bootstrap() async {
    final token = await _storage.readAccess();
    if (token == null || token.isEmpty) {
      state = const SessionState(status: SessionStatus.unauthenticated);
      return;
    }
    try {
      final user = await _repo.fetchMe();
      state = SessionState(status: SessionStatus.authenticated, user: user);
    } catch (_) {
      await _storage.clear();
      state = const SessionState(status: SessionStatus.unauthenticated);
    }
  }

  Future<void> login(String email, String password) async {
    final tokens = await _repo.login(email: email, password: password);
    await _storage.save(access: tokens.accessToken, refresh: tokens.refreshToken);
    final user = await _repo.fetchMe();
    state = SessionState(status: SessionStatus.authenticated, user: user);
  }

  Future<void> register({
    required String email,
    required String password,
    required String firstName,
  }) async {
    final tokens = await _repo.register(
      email: email,
      password: password,
      firstName: firstName,
    );
    await _storage.save(access: tokens.accessToken, refresh: tokens.refreshToken);
    final user = await _repo.fetchMe();
    state = SessionState(status: SessionStatus.authenticated, user: user);
  }

  Future<void> devLogin(int telegramId) async {
    final tokens = await _repo.devLogin(telegramId);
    await _storage.save(access: tokens.accessToken, refresh: tokens.refreshToken);
    final user = await _repo.fetchMe();
    state = SessionState(status: SessionStatus.authenticated, user: user);
  }

  Future<void> logout() async {
    final refreshToken = await _storage.readRefresh();
    if (refreshToken != null) {
      await _repo.logout(refreshToken);
    }
    await _storage.clear();
    _ref.invalidate(authRepositoryProvider); // forces providers depending on it to rebuild
    state = const SessionState(status: SessionStatus.unauthenticated);
  }

  /// Called by Dio's refresh interceptor when refresh fails.
  Future<void> signalExpired() async {
    await _storage.clear();
    _ref.invalidate(authRepositoryProvider);
    state = const SessionState(status: SessionStatus.unauthenticated);
  }

  Future<void> refreshUser() async {
    try {
      final user = await _repo.fetchMe();
      state = state.copyWith(user: user);
    } catch (_) {
      // ignore — keep prior user
    }
  }
}

final sessionControllerProvider =
    StateNotifierProvider<SessionController, SessionState>(
  SessionController.new,
);
