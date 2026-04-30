import 'dart:async';
import 'dart:io';

import 'package:dio/dio.dart' as dio;
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:record/record.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/network/dio_client.dart';

/// Тонкий сервис над `record` пакетом + аплоад в наш бэк.
///
/// API:
/// - [start] — открыть микрофон, запустить запись в OGG/Opus в temp-файл
/// - [stop] — остановить, вернуть путь к файлу
/// - [cancel] — остановить и удалить файл
/// - [amplitudeStream] — реал-тайм 0..1 (нормализовано из dBFS),
///   используется чтобы орб дышал. Тихий микрофон не пикает.
/// - [recognize] — отправить файл в `/api/v1/voice/recognize` и вернуть текст
class VoiceRecorder {
  VoiceRecorder(this._ref);

  final Ref _ref;
  final AudioRecorder _record = AudioRecorder();
  StreamSubscription<Amplitude>? _ampSub;
  String? _currentPath;

  final _ampCtl = StreamController<double>.broadcast();
  Stream<double> get amplitudeStream => _ampCtl.stream;

  bool get isRecording => _currentPath != null;

  Future<bool> start() async {
    if (_currentPath != null) return true;
    final granted = await Permission.microphone.request();
    if (!granted.isGranted) return false;

    final dir = await getTemporaryDirectory();
    final ts = DateTime.now().millisecondsSinceEpoch;
    final path = '${dir.path}/mx_$ts.m4a';

    try {
      await _record.start(
        const RecordConfig(
          encoder: AudioEncoder.aacLc,
          bitRate: 64000,
          sampleRate: 16000,
          numChannels: 1,
        ),
        path: path,
      );
    } catch (e) {
      debugPrint('VoiceRecorder.start failed: $e');
      return false;
    }
    _currentPath = path;

    // amplitude stream: dBFS обычно -45..0; нормализуем в 0..1
    _ampSub = _record
        .onAmplitudeChanged(const Duration(milliseconds: 80))
        .listen((a) {
      final dbfs = a.current; // отрицательное число, ближе к 0 = громче
      final normalized = ((dbfs + 45) / 45).clamp(0.0, 1.0);
      _ampCtl.add(normalized.toDouble());
    });
    return true;
  }

  /// Останавливает запись и возвращает путь к файлу.
  Future<String?> stop() async {
    final path = _currentPath;
    _currentPath = null;
    await _ampSub?.cancel();
    _ampSub = null;
    try {
      await _record.stop();
    } catch (_) {}
    return path;
  }

  /// Останавливает и удаляет файл.
  Future<void> cancel() async {
    final p = await stop();
    if (p != null) {
      try {
        final f = File(p);
        if (await f.exists()) await f.delete();
      } catch (_) {}
    }
  }

  /// Аплоад в `/api/v1/voice/recognize` → текст. Файл удаляется после.
  Future<RecognizeResult> recognize(String path) async {
    final f = File(path);
    if (!await f.exists()) {
      throw ApiException(message: 'Аудио не сохранилось.', isNetwork: true);
    }
    final size = await f.length();
    final dioClient = _ref.read(dioProvider);
    try {
      final form = dio.FormData.fromMap({
        'audio': await dio.MultipartFile.fromFile(
          path,
          filename: 'audio.m4a',
          contentType: dio.DioMediaType('audio', 'mp4'),
        ),
      });
      final r = await dioClient.post<Map<String, dynamic>>(
        '/voice/recognize',
        data: form,
        options: dio.Options(
          sendTimeout: const Duration(seconds: 30),
          receiveTimeout: const Duration(seconds: 30),
        ),
      );
      final text = (r.data?['text'] as String?) ?? '';
      return RecognizeResult(text: text, bytes: size);
    } on dio.DioException catch (e) {
      throw ApiException.fromDio(e);
    } finally {
      try {
        if (await f.exists()) await f.delete();
      } catch (_) {}
    }
  }

  Future<void> dispose() async {
    await _ampSub?.cancel();
    await _ampCtl.close();
    try {
      await _record.dispose();
    } catch (_) {}
  }
}

class RecognizeResult {
  RecognizeResult({required this.text, required this.bytes});
  final String text;
  final int bytes;
}

final voiceRecorderProvider = Provider<VoiceRecorder>((ref) {
  final r = VoiceRecorder(ref);
  ref.onDispose(() {
    r.dispose();
  });
  return r;
});
