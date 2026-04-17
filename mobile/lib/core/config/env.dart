import 'package:flutter_dotenv/flutter_dotenv.dart';

/// Environment-specific configuration loaded from `assets/.env`.
abstract final class Env {
  static Future<void> init() => dotenv.load(fileName: 'assets/.env');

  static String get apiBaseUrl =>
      dotenv.maybeGet('API_BASE_URL') ?? 'http://10.0.2.2:8000';

  static String get apiVersion => dotenv.maybeGet('API_VERSION') ?? 'v1';

  static String get apiUrl => '$apiBaseUrl/api/$apiVersion';

  static String get yookassaReturnUrl =>
      dotenv.maybeGet('YOOKASSA_RETURN_URL') ?? 'voicenote://payment/success';

  static bool get isProduction => dotenv.maybeGet('ENV') == 'production';
}
