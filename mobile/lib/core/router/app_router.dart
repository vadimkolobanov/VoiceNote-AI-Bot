import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:voicenote_ai/core/router/app_routes.dart';
import 'package:voicenote_ai/features/ai_agent/presentation/screens/ai_chat_screen.dart';
import 'package:voicenote_ai/features/ai_agent/presentation/screens/memory_facts_screen.dart';
import 'package:voicenote_ai/features/auth/application/session_controller.dart';
import 'package:voicenote_ai/features/auth/presentation/screens/login_screen.dart';
import 'package:voicenote_ai/features/auth/presentation/screens/register_screen.dart';
import 'package:voicenote_ai/features/auth/presentation/screens/splash_screen.dart';
import 'package:voicenote_ai/features/birthdays/presentation/screens/birthdays_screen.dart';
import 'package:voicenote_ai/features/habits/presentation/screens/habits_screen.dart';
import 'package:voicenote_ai/features/notes/presentation/screens/create_note_screen.dart';
import 'package:voicenote_ai/features/notes/presentation/screens/note_detail_screen.dart';
import 'package:voicenote_ai/features/notes/presentation/screens/notes_list_screen.dart';
import 'package:voicenote_ai/features/payments/presentation/screens/payment_webview_screen.dart';
import 'package:voicenote_ai/features/payments/presentation/screens/paywall_screen.dart';
import 'package:voicenote_ai/features/profile/presentation/screens/achievements_screen.dart';
import 'package:voicenote_ai/features/profile/presentation/screens/profile_screen.dart';
import 'package:voicenote_ai/features/profile/presentation/screens/settings_screen.dart';
import 'package:voicenote_ai/features/shopping_list/presentation/screens/shopping_list_screen.dart';
import 'package:voicenote_ai/shared/widgets/app_shell.dart';

final _rootKey = GlobalKey<NavigatorState>();
final _shellKey = GlobalKey<NavigatorState>();

final routerProvider = Provider<GoRouter>((ref) {
  final session = ref.watch(sessionControllerProvider);

  return GoRouter(
    navigatorKey: _rootKey,
    initialLocation: AppRoutes.splash,
    debugLogDiagnostics: false,
    refreshListenable: ref.watch(sessionControllerProvider.notifier).refresh,
    redirect: (context, state) {
      final status = session.status;
      final location = state.matchedLocation;

      final isSplash = location == AppRoutes.splash;
      final isAuthRoute =
          location == AppRoutes.login || location == AppRoutes.register;

      if (status == SessionStatus.unknown) {
        return isSplash ? null : AppRoutes.splash;
      }
      if (status == SessionStatus.unauthenticated) {
        return isAuthRoute ? null : AppRoutes.login;
      }
      // authenticated
      if (isSplash || isAuthRoute) return AppRoutes.notes;
      return null;
    },
    routes: [
      GoRoute(
        path: AppRoutes.splash,
        builder: (_, __) => const SplashScreen(),
      ),
      GoRoute(
        path: AppRoutes.login,
        builder: (_, __) => const LoginScreen(),
      ),
      GoRoute(
        path: AppRoutes.register,
        builder: (_, __) => const RegisterScreen(),
      ),

      ShellRoute(
        navigatorKey: _shellKey,
        builder: (context, state, child) => AppShell(location: state.matchedLocation, child: child),
        routes: [
          GoRoute(
            path: AppRoutes.notes,
            pageBuilder: (_, __) => const NoTransitionPage(child: NotesListScreen()),
          ),
          GoRoute(
            path: AppRoutes.habits,
            pageBuilder: (_, __) => const NoTransitionPage(child: HabitsScreen()),
          ),
          GoRoute(
            path: AppRoutes.agent,
            pageBuilder: (_, __) => const NoTransitionPage(child: AiChatScreen()),
          ),
          GoRoute(
            path: AppRoutes.profile,
            pageBuilder: (_, __) => const NoTransitionPage(child: ProfileScreen()),
          ),
        ],
      ),

      // Pushed screens (outside shell)
      GoRoute(
        parentNavigatorKey: _rootKey,
        path: AppRoutes.createNote,
        builder: (_, __) => const CreateNoteScreen(),
      ),
      GoRoute(
        parentNavigatorKey: _rootKey,
        path: AppRoutes.noteDetail,
        builder: (context, state) {
          final id = int.parse(state.pathParameters['id']!);
          return NoteDetailScreen(noteId: id);
        },
      ),
      GoRoute(
        parentNavigatorKey: _rootKey,
        path: AppRoutes.shopping,
        builder: (_, __) => const ShoppingListScreen(),
      ),
      GoRoute(
        parentNavigatorKey: _rootKey,
        path: AppRoutes.birthdays,
        builder: (_, __) => const BirthdaysScreen(),
      ),
      GoRoute(
        parentNavigatorKey: _rootKey,
        path: AppRoutes.paywall,
        builder: (_, __) => const PaywallScreen(),
      ),
      GoRoute(
        parentNavigatorKey: _rootKey,
        path: AppRoutes.payment,
        builder: (context, state) {
          final url = state.uri.queryParameters['url'] ?? '';
          return PaymentWebViewScreen(confirmationUrl: url);
        },
      ),
      GoRoute(
        parentNavigatorKey: _rootKey,
        path: AppRoutes.settings,
        builder: (_, __) => const SettingsScreen(),
      ),
      GoRoute(
        parentNavigatorKey: _rootKey,
        path: AppRoutes.memoryFacts,
        builder: (_, __) => const MemoryFactsScreen(),
      ),
      GoRoute(
        parentNavigatorKey: _rootKey,
        path: AppRoutes.achievements,
        builder: (_, __) => const AchievementsScreen(),
      ),
    ],
    errorBuilder: (_, state) => Scaffold(
      body: Center(child: Text('Маршрут не найден: ${state.uri}')),
    ),
  );
});
