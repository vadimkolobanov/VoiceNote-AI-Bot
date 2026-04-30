import 'package:device_info_plus/device_info_plus.dart';
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart' show TargetPlatform, defaultTargetPlatform;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:package_info_plus/package_info_plus.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/network/dio_client.dart';

class FeedbackRepository {
  FeedbackRepository(this._dio);

  final Dio _dio;

  Future<void> submit({
    required String sentiment,
    required String body,
    String? screenAt,
  }) async {
    final ctx = await _collectContext();
    try {
      await _dio.post<dynamic>(
        '/feedback',
        data: {
          'sentiment': sentiment,
          'body': body,
          'app_version': ctx.version,
          'device_info': ctx.device,
          if (screenAt != null) 'screen_at': screenAt,
        },
      );
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<_FeedbackContext> _collectContext() async {
    String version = '';
    try {
      final pkg = await PackageInfo.fromPlatform();
      version = '${pkg.version}+${pkg.buildNumber}';
    } catch (_) {}
    String device = '';
    try {
      final di = DeviceInfoPlugin();
      if (defaultTargetPlatform == TargetPlatform.android) {
        final a = await di.androidInfo;
        device = '${a.manufacturer} ${a.model} · Android ${a.version.release}';
      } else if (defaultTargetPlatform == TargetPlatform.iOS) {
        final i = await di.iosInfo;
        device = '${i.name} ${i.utsname.machine} · iOS ${i.systemVersion}';
      } else {
        device = defaultTargetPlatform.name;
      }
    } catch (_) {}
    return _FeedbackContext(version: version, device: device);
  }
}

class _FeedbackContext {
  _FeedbackContext({required this.version, required this.device});
  final String version;
  final String device;
}

final feedbackRepositoryProvider = Provider<FeedbackRepository>(
  (ref) => FeedbackRepository(ref.watch(dioProvider)),
);
