import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:voicenote_ai/core/router/app_routes.dart';
import 'package:voicenote_ai/features/auth/application/session_controller.dart';
import 'package:voicenote_ai/features/auth/presentation/screens/login_screen.dart';
import 'package:voicenote_ai/features/auth/presentation/screens/splash_screen.dart';
import 'package:voicenote_ai/features/facts/presentation/facts_screen.dart';
import 'package:voicenote_ai/features/learning/presentation/learning_screen.dart';
import 'package:voicenote_ai/features/moment_details/presentation/moment_details_screen.dart';
import 'package:voicenote_ai/features/paywall/presentation/paywall_screen.dart';
import 'package:voicenote_ai/features/profile/presentation/profile_screen.dart';
import 'package:voicenote_ai/features/rhythm/presentation/rhythm_screen.dart';
import 'package:voicenote_ai/features/timeline/presentation/timeline_screen.dart';
import 'package:voicenote_ai/features/today/presentation/today_screen.dart';
import 'package:voicenote_ai/features/voice_capture/presentation/voice_capture_screen.dart';
import 'package:voicenote_ai/shared/widgets/app_shell.dart';

final _rootKey = GlobalKey<NavigatorState>();
final _shellKey = GlobalKey<NavigatorState>();

/// 4-tab Shell + voice modal + auth/splash. PRODUCT_PLAN.md §7.4.
final routerProvider = Provider<GoRouter>((ref) {
  final session = ref.watch(sessionControllerProvider);

  return GoRouter(
    navigatorKey: _rootKey,
    initialLocation: AppRoutes.splash,
    debugLogDiagnostics: false,
    refreshListenable: ref.watch(sessionControllerProvider.notifier).refresh,
    redirect: (context, state) {
      final status = session.status;
      final loc = state.matchedLocation;
      final isSplash = loc == AppRoutes.splash;
      final isAuth = loc == AppRoutes.login;

      if (status == SessionStatus.unknown) {
        return isSplash ? null : AppRoutes.splash;
      }
      if (status == SessionStatus.unauthenticated) {
        return isAuth ? null : AppRoutes.login;
      }
      // authenticated
      if (isSplash || isAuth) return AppRoutes.today;
      return null;
    },
    routes: [
      GoRoute(path: AppRoutes.splash, builder: (_, __) => const SplashScreen()),
      GoRoute(path: AppRoutes.login, builder: (_, __) => const LoginScreen()),

      ShellRoute(
        navigatorKey: _shellKey,
        builder: (context, state, child) =>
            AppShell(location: state.matchedLocation, child: child),
        routes: [
          GoRoute(
            path: AppRoutes.today,
            pageBuilder: (_, __) => const NoTransitionPage(child: TodayScreen()),
          ),
          GoRoute(
            path: AppRoutes.timeline,
            pageBuilder: (_, __) => const NoTransitionPage(child: TimelineScreen()),
          ),
          GoRoute(
            path: AppRoutes.rhythm,
            pageBuilder: (_, __) => const NoTransitionPage(child: RhythmScreen()),
          ),
          GoRoute(
            path: AppRoutes.profile,
            pageBuilder: (_, __) => const NoTransitionPage(child: ProfileScreen()),
          ),
        ],
      ),

      GoRoute(
        parentNavigatorKey: _rootKey,
        path: AppRoutes.voiceCapture,
        pageBuilder: (_, __) => CustomTransitionPage(
          opaque: true,
          fullscreenDialog: true,
          child: const VoiceCaptureScreen(),
          transitionsBuilder: (_, animation, __, child) =>
              FadeTransition(opacity: animation, child: child),
        ),
      ),
      GoRoute(
        parentNavigatorKey: _rootKey,
        path: AppRoutes.momentDetails,
        builder: (_, state) {
          final id = int.parse(state.pathParameters['id']!);
          return MomentDetailsScreen(momentId: id);
        },
      ),
      GoRoute(
        parentNavigatorKey: _rootKey,
        path: AppRoutes.facts,
        builder: (_, __) => const FactsScreen(),
      ),
      GoRoute(
        parentNavigatorKey: _rootKey,
        path: AppRoutes.learning,
        builder: (_, __) => const LearningScreen(),
      ),
      GoRoute(
        parentNavigatorKey: _rootKey,
        path: AppRoutes.paywall,
        builder: (_, __) => const PaywallScreen(),
      ),
    ],
    errorBuilder: (_, state) => Scaffold(
      body: Center(child: Text('Маршрут не найден: ${state.uri}')),
    ),
  );
});
