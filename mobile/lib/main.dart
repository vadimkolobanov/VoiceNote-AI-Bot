import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/date_symbol_data_local.dart';

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

  runApp(const ProviderScope(child: VoiceNoteApp()));
}
