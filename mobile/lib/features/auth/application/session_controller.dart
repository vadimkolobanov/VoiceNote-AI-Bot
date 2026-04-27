import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/core/storage/secure_storage.dart';
import 'package:voicenote_ai/features/auth/data/models/auth_tokens.dart';
import 'package:voicenote_ai/features/auth/data/models/user.dart';
import 'package:voicenote_ai/features/auth/data/repositories/auth_repository.dart';
import 'package:voicenote_ai/features/push/push_service.dart';

enum SessionStatus { unknown, unauthenticated, authenticated }

@immutable
class SessionState {
  const SessionState({required this.status, this.user});

  final SessionStatus status;
  final User? user;

  SessionState copyWith({
    SessionStatus? status,
    User? user,
    bool clearUser = false,
  }) {
    return SessionState(
      status: status ?? this.status,
      user: clearUser ? null : (user ?? this.user),
    );
  }
}

/// Управляет сессией: bootstrap из secure storage, login/register/logout,
/// обновление профиля. JWT-пара хранится в secure storage; user — в памяти.
class SessionController extends StateNotifier<SessionState> {
  SessionController(this._ref) : super(const SessionState(status: SessionStatus.unknown)) {
    _bootstrap();
  }

  final Ref _ref;

  /// Subscription target для `GoRouter.refreshListenable`.
  final ValueNotifier<int> refresh = ValueNotifier<int>(0);

  SecureTokenStorage get _storage => _ref.read(secureStorageProvider);
  AuthRepository get _repo => _ref.read(authRepositoryProvider);

  @override
  set state(SessionState value) {
    final prev = super.state;
    super.state = value;
    refresh.value++;
    if (prev.status != SessionStatus.authenticated &&
        value.status == SessionStatus.authenticated) {
      // ignore: discarded_futures
      _ref.read(pushServiceProvider).registerForUser();
    } else if (prev.status == SessionStatus.authenticated &&
        value.status == SessionStatus.unauthenticated) {
      // ignore: discarded_futures
      _ref.read(pushServiceProvider).unregister();
    }
  }

  @override
  void dispose() {
    refresh.dispose();
    super.dispose();
  }

  Future<void> _bootstrap() async {
    final access = await _storage.readAccess();
    if (access == null || access.isEmpty) {
      state = const SessionState(status: SessionStatus.unauthenticated);
      return;
    }
    try {
      final user = await _repo.fetchProfile();
      state = SessionState(status: SessionStatus.authenticated, user: user);
    } catch (_) {
      // Access протух / БД отвергла — пробуем рефреш.
      final refreshTok = await _storage.readRefresh();
      if (refreshTok == null) {
        await _storage.clear();
        state = const SessionState(status: SessionStatus.unauthenticated);
        return;
      }
      try {
        final tokens = await _repo.refresh(refreshTok);
        await _persistTokens(tokens);
        final user = await _repo.fetchProfile();
        state = SessionState(status: SessionStatus.authenticated, user: user);
      } catch (_) {
        await _storage.clear();
        state = const SessionState(status: SessionStatus.unauthenticated);
      }
    }
  }

  Future<void> register({
    required String email,
    required String password,
    String? displayName,
  }) async {
    final tokens = await _repo.register(
      email: email,
      password: password,
      displayName: displayName,
    );
    await _persistTokens(tokens);
    final user = tokens.user ?? await _repo.fetchProfile();
    state = SessionState(status: SessionStatus.authenticated, user: user);
  }

  Future<void> login({required String email, required String password}) async {
    final tokens = await _repo.login(email: email, password: password);
    await _persistTokens(tokens);
    final user = tokens.user ?? await _repo.fetchProfile();
    state = SessionState(status: SessionStatus.authenticated, user: user);
  }

  Future<void> logout() async {
    final refreshTok = await _storage.readRefresh();
    if (refreshTok != null) {
      await _repo.logout(refreshTok);
    }
    await _storage.clear();
    _ref.invalidate(authRepositoryProvider);
    state = const SessionState(status: SessionStatus.unauthenticated);
  }

  /// Зовётся auth-interceptor'ом, когда даже refresh не помог.
  Future<void> signalExpired() async {
    await _storage.clear();
    _ref.invalidate(authRepositoryProvider);
    state = const SessionState(status: SessionStatus.unauthenticated);
  }

  Future<void> refreshUser() async {
    try {
      final user = await _repo.fetchProfile();
      state = state.copyWith(user: user);
    } catch (_) {
      // ignore — оставляем предыдущего user
    }
  }

  Future<void> _persistTokens(AuthTokens t) =>
      _storage.save(access: t.access, refresh: t.refresh);
}

final sessionControllerProvider =
    StateNotifierProvider<SessionController, SessionState>(
  SessionController.new,
);
