import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/core/router/app_router.dart';
import 'package:voicenote_ai/core/theme/app_theme.dart';
import 'package:voicenote_ai/features/moments/application/moments_providers.dart';
import 'package:voicenote_ai/features/push/push_service.dart';

/// Глобальный messenger — чтобы SnackBar-ы показывались одним и тем же
/// ScaffoldMessenger-ом независимо от текущего экрана/роута. Это решает
/// случаи, когда context исчезает до показа (async операции + pop).
final rootMessengerKey = GlobalKey<ScaffoldMessengerState>();

class VoiceNoteApp extends ConsumerStatefulWidget {
  const VoiceNoteApp({super.key});

  @override
  ConsumerState<VoiceNoteApp> createState() => _VoiceNoteAppState();
}

class _VoiceNoteAppState extends ConsumerState<VoiceNoteApp>
    with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _drainPushActions();
    });
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _drainPushActions();
    }
  }

  Future<void> _drainPushActions() async {
    try {
      final touched = await ref.read(pushServiceProvider).processPendingActions();
      if (touched.isNotEmpty) {
        ref.invalidate(todayProvider);
      }
    } catch (_) {/* offline — оставим до следующего раза */}
  }

  @override
  Widget build(BuildContext context) {
    final router = ref.watch(routerProvider);
    return MaterialApp.router(
      title: 'Методекс Секретарь',
      debugShowCheckedModeBanner: false,
      routerConfig: router,
      scaffoldMessengerKey: rootMessengerKey,
      theme: AppTheme.light(),
      darkTheme: AppTheme.dark(),
      // Дизайн спроектирован dark-first; light — pragmatic fallback.
      themeMode: ThemeMode.dark,
      locale: const Locale('ru'),
      supportedLocales: const [Locale('ru'), Locale('en')],
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
    );
  }
}
