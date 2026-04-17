import 'dart:async';
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:record/record.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/network/dio_client.dart';
import 'package:voicenote_ai/features/notes/data/models/note.dart';

enum VoiceRecorderStatus { idle, recording, processing }

@immutable
class VoiceRecorderState {
  const VoiceRecorderState({
    required this.status,
    this.startedAt,
    this.error,
  });

  final VoiceRecorderStatus status;
  final DateTime? startedAt;
  final String? error;

  const VoiceRecorderState.idle()
      : status = VoiceRecorderStatus.idle,
        startedAt = null,
        error = null;
}

class VoiceRecorderController extends StateNotifier<VoiceRecorderState> {
  VoiceRecorderController(this._dio)
      : _recorder = AudioRecorder(),
        super(const VoiceRecorderState.idle());

  final AudioRecorder _recorder;
  final Dio _dio;

  String? _currentPath;

  Future<bool> _ensurePermission() async {
    if (await _recorder.hasPermission()) return true;
    final status = await Permission.microphone.request();
    return status.isGranted;
  }

  Future<void> start() async {
    if (state.status != VoiceRecorderStatus.idle) return;
    try {
      if (!await _ensurePermission()) {
        state = const VoiceRecorderState(
          status: VoiceRecorderStatus.idle,
          error: 'Нужен доступ к микрофону',
        );
        return;
      }
      final dir = await getTemporaryDirectory();
      _currentPath =
          '${dir.path}/voicenote_${DateTime.now().millisecondsSinceEpoch}.m4a';
      await _recorder.start(
        const RecordConfig(
          encoder: AudioEncoder.aacLc,
          bitRate: 64000,
          sampleRate: 22050,
        ),
        path: _currentPath!,
      );
      state = VoiceRecorderState(
        status: VoiceRecorderStatus.recording,
        startedAt: DateTime.now(),
      );
    } catch (e) {
      state = VoiceRecorderState(
        status: VoiceRecorderStatus.idle,
        error: 'Не удалось начать запись: $e',
      );
    }
  }

  Future<void> cancel() async {
    if (state.status != VoiceRecorderStatus.recording) return;
    try {
      await _recorder.stop();
    } catch (_) {}
    await _safeDelete(_currentPath);
    _currentPath = null;
    state = const VoiceRecorderState.idle();
  }

  Future<Note?> stopAndUpload() async {
    if (state.status != VoiceRecorderStatus.recording) return null;
    state = const VoiceRecorderState(status: VoiceRecorderStatus.processing);
    final path = await _recorder.stop();
    final filePath = path ?? _currentPath;
    if (filePath == null || !File(filePath).existsSync()) {
      state = const VoiceRecorderState(
        status: VoiceRecorderStatus.idle,
        error: 'Файл записи пустой',
      );
      return null;
    }
    try {
      final formData = FormData.fromMap({
        'audio': await MultipartFile.fromFile(filePath, filename: 'voice.m4a'),
      });
      final response = await _dio.post<Map<String, dynamic>>(
        '/voice/recognize',
        data: formData,
        options: Options(contentType: 'multipart/form-data'),
      );
      state = const VoiceRecorderState.idle();
      return Note.fromJson(response.data!);
    } on DioException catch (e) {
      state = VoiceRecorderState(
        status: VoiceRecorderStatus.idle,
        error: ApiException.fromDio(e).message,
      );
      return null;
    } finally {
      await _safeDelete(filePath);
      _currentPath = null;
    }
  }

  Future<void> _safeDelete(String? path) async {
    if (path == null) return;
    try {
      final f = File(path);
      if (await f.exists()) await f.delete();
    } catch (_) {}
  }

  @override
  void dispose() {
    _recorder.dispose();
    super.dispose();
  }
}

final voiceRecorderProvider =
    StateNotifierProvider.autoDispose<VoiceRecorderController, VoiceRecorderState>(
  (ref) => VoiceRecorderController(ref.watch(dioProvider)),
);
