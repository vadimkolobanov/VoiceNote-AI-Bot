import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Флаг «пользователь уже видел онбоардинг».
///
/// Версия в ключе нужна, чтобы при существенных изменениях обзора можно было
/// показать его снова всем пользователям (просто инкрементируем суффикс).
class OnboardingFlag {
  static const _key = 'seen_onboarding_v1';

  Future<bool> hasSeen() async {
    final p = await SharedPreferences.getInstance();
    return p.getBool(_key) ?? false;
  }

  Future<void> markSeen() async {
    final p = await SharedPreferences.getInstance();
    await p.setBool(_key, true);
  }

  Future<void> reset() async {
    final p = await SharedPreferences.getInstance();
    await p.remove(_key);
  }
}

final onboardingFlagProvider = Provider<OnboardingFlag>((_) => OnboardingFlag());

/// `null` пока неизвестно (booting), `true/false` после первой проверки.
/// Роутер использует это, чтобы решить, показать ли /onboarding после логина.
class OnboardingSeenNotifier extends StateNotifier<bool?> {
  OnboardingSeenNotifier(this._flag) : super(null) {
    _bootstrap();
  }

  final OnboardingFlag _flag;

  Future<void> _bootstrap() async {
    state = await _flag.hasSeen();
  }

  Future<void> markSeen() async {
    await _flag.markSeen();
    state = true;
  }

  Future<void> reset() async {
    await _flag.reset();
    state = false;
  }
}

final onboardingSeenProvider =
    StateNotifierProvider<OnboardingSeenNotifier, bool?>(
  (ref) => OnboardingSeenNotifier(ref.read(onboardingFlagProvider)),
);
