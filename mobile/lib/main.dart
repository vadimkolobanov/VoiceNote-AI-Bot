import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'package:sentry_flutter/sentry_flutter.dart';

import 'package:voicenote_ai/app.dart';
import 'package:voicenote_ai/core/config/env.dart';
import 'package:voicenote_ai/features/push/push_service.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await SystemChrome.setPreferredOrientations(const [
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);

  await Env.init();
  await initializeDateFormatting('ru');
  await PushService.initFirebase();

  // Sentry: DSN кладём в assets/.env как SENTRY_DSN. Если не задан —
  // приложение запускается без crash-reporting, без блокировки.
  final dsn = Env.sentryDsn;
  if (dsn.isNotEmpty) {
    await SentryFlutter.init(
      (o) {
        o.dsn = dsn;
        o.tracesSampleRate = 0.1;
        o.environment = Env.environment;
        o.release = 'metodex@1.0.0';
      },
      appRunner: () =>
          runApp(const ProviderScope(child: VoiceNoteApp())),
    );
  } else {
    runApp(const ProviderScope(child: VoiceNoteApp()));
  }
}
