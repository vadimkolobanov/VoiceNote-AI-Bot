import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/theme/mx_tokens.dart';
import 'package:voicenote_ai/features/notes/application/notes_controller.dart';
import 'package:voicenote_ai/features/notes/data/models/note.dart';
import 'package:voicenote_ai/features/notes/data/repositories/notes_repository.dart';
import 'package:voicenote_ai/features/voice/application/voice_recorder_controller.dart';

/// Full-screen экран голосовой записи — соответствует ScreenVoice из макета.
///
/// Центральный круглый микрофон, живая waveform (48 столбиков), таймер,
/// кнопки Отмена / Стоп / Готово. Если пользователь не нажимает запись —
/// предлагаем ввести текст вручную.
class VoiceCaptureScreen extends ConsumerStatefulWidget {
  const VoiceCaptureScreen({super.key});

  @override
  ConsumerState<VoiceCaptureScreen> createState() => _VoiceCaptureScreenState();
}

class _VoiceCaptureScreenState extends ConsumerState<VoiceCaptureScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _wave;
  final _text = TextEditingController();
  bool _textMode = false;
  bool _sending = false;
  DateTime? _startedAt;

  @override
  void initState() {
    super.initState();
    _wave = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat();
  }

  @override
  void dispose() {
    _wave.dispose();
    _text.dispose();
    super.dispose();
  }

  Future<void> _startRecording() async {
    await ref.read(voiceRecorderProvider.notifier).start();
    _startedAt = DateTime.now();
    setState(() {});
  }

  Future<void> _cancelRecording() async {
    await ref.read(voiceRecorderProvider.notifier).cancel();
    _startedAt = null;
    if (mounted) Navigator.of(context).pop();
  }

  Future<void> _stopAndUpload() async {
    final note = await ref.read(voiceRecorderProvider.notifier).stopAndUpload();
    if (note != null) {
      _upsert(note);
      if (mounted) Navigator.of(context).pop();
    } else {
      final err = ref.read(voiceRecorderProvider).error;
      if (mounted && err != null) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(err)));
      }
    }
  }

  Future<void> _sendText() async {
    if (_text.text.trim().isEmpty || _sending) return;
    setState(() => _sending = true);
    try {
      final note = await ref.read(notesRepositoryProvider).create(_text.text.trim());
      _upsert(note);
      if (mounted) Navigator.of(context).pop();
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
      }
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  void _upsert(Note note) {
    if (note.type == NoteType.shopping) return;
    ref.read(notesControllerProvider(
      NotesQuery(segment: NotesSegment.active, type: note.type),
    ).notifier).upsert(note);
  }

  String get _elapsed {
    if (_startedAt == null) return '00:00';
    final d = DateTime.now().difference(_startedAt!);
    final mm = d.inMinutes.toString().padLeft(2, '0');
    final ss = (d.inSeconds % 60).toString().padLeft(2, '0');
    return '$mm:$ss';
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(voiceRecorderProvider);
    final isRecording = state.status == VoiceRecorderStatus.recording;

    // Пересчёт таймера раз в секунду
    if (isRecording) {
      Future.delayed(const Duration(seconds: 1), () {
        if (mounted) setState(() {});
      });
    }

    return Scaffold(
      backgroundColor: MX.bgBase,
      body: SafeArea(
        child: Stack(
          children: [
            // ── Header ──────────────────────────────────
            Positioned(
              top: 0, left: 0, right: 0,
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Row(
                  children: [
                    IconButton(
                      icon: const Icon(Icons.close, color: MX.fg, size: 24),
                      onPressed: _cancelRecording,
                    ),
                    Expanded(
                      child: Center(
                        child: Text(
                          isRecording
                              ? 'ЗАПИСЬ · $_elapsed'
                              : _textMode
                                  ? 'ВВОД ТЕКСТОМ'
                                  : 'ГОТОВ К ЗАПИСИ',
                          style: TextStyle(
                            color: isRecording ? MX.accentAi : MX.fgMicro,
                            fontSize: 11, fontWeight: FontWeight.w700, letterSpacing: 1.5,
                          ),
                        ),
                      ),
                    ),
                    IconButton(
                      icon: Icon(_textMode ? Icons.mic : Icons.keyboard,
                          color: MX.fgMuted, size: 22),
                      onPressed: () => setState(() => _textMode = !_textMode),
                    ),
                  ],
                ),
              ),
            ),

            // ── Main content ────────────────────────────
            Center(
              child: _textMode
                  ? _TextInputMode(
                      controller: _text,
                      sending: _sending,
                      onSend: _sendText,
                    )
                  : _VoiceMode(
                      isRecording: isRecording,
                      elapsed: _elapsed,
                      waveController: _wave,
                      onStart: _startRecording,
                      onStop: _stopAndUpload,
                      onCancel: _cancelRecording,
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────

class _VoiceMode extends StatelessWidget {
  const _VoiceMode({
    required this.isRecording,
    required this.elapsed,
    required this.waveController,
    required this.onStart,
    required this.onStop,
    required this.onCancel,
  });
  final bool isRecording;
  final String elapsed;
  final AnimationController waveController;
  final VoidCallback onStart;
  final VoidCallback onStop;
  final VoidCallback onCancel;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 32),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Glow halo
          Stack(
            alignment: Alignment.center,
            children: [
              if (isRecording)
                Container(
                  width: 300, height: 300,
                  decoration: const BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: RadialGradient(
                      colors: [Color(0x3300E5FF), Color(0x0000E5FF)],
                    ),
                  ),
                ),
              // Large timer
              Text(
                elapsed,
                style: const TextStyle(
                  color: MX.fg, fontSize: 56, fontWeight: FontWeight.w700,
                  letterSpacing: -1, fontFeatures: [],
                ),
              ),
            ],
          ),
          const SizedBox(height: 36),

          // Waveform
          if (isRecording)
            AnimatedBuilder(
              animation: waveController,
              builder: (_, __) => _Waveform(phase: waveController.value),
            )
          else
            const SizedBox(height: 68),

          const SizedBox(height: 48),

          // Controls
          if (isRecording)
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                _IconCircle(
                  icon: Icons.close,
                  color: MX.fgMuted,
                  size: 56,
                  onTap: onCancel,
                ),
                const SizedBox(width: 24),
                GestureDetector(
                  onTap: onStop,
                  child: Container(
                    width: 84, height: 84,
                    decoration: const BoxDecoration(
                      shape: BoxShape.circle,
                      color: MX.accentAi,
                      boxShadow: MX.fabGlow,
                    ),
                    child: const Center(
                      child: SizedBox(
                        width: 28, height: 28,
                        child: DecoratedBox(
                          decoration: BoxDecoration(
                            color: MX.bgBase,
                            borderRadius: BorderRadius.all(Radius.circular(4)),
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 24),
                _IconCircle(
                  icon: Icons.check,
                  color: MX.accentTools,
                  border: MX.accentToolsLine,
                  size: 56,
                  onTap: onStop,
                ),
              ],
            )
          else
            GestureDetector(
              onTap: onStart,
              child: Container(
                width: 96, height: 96,
                decoration: const BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: MX.brandGradient,
                  boxShadow: MX.fabGlow,
                ),
                child: const Icon(Icons.mic, color: Colors.white, size: 40),
              ),
            ),

          const SizedBox(height: 18),
          Text(
            isRecording ? 'Отмена · Стоп · Готово' : 'Нажмите, чтобы начать запись',
            style: const TextStyle(color: MX.fgMuted, fontSize: 12),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────

class _TextInputMode extends StatelessWidget {
  const _TextInputMode({
    required this.controller,
    required this.sending,
    required this.onSend,
  });
  final TextEditingController controller;
  final bool sending;
  final VoidCallback onSend;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          TextField(
            controller: controller,
            autofocus: true,
            maxLines: 6,
            minLines: 3,
            style: const TextStyle(color: MX.fg, fontSize: 16, height: 1.5),
            decoration: InputDecoration(
              filled: true,
              fillColor: MX.surfaceOverlay,
              hintText: 'Например: «купить молоко и хлеб»',
              hintStyle: const TextStyle(color: MX.fgFaint),
              contentPadding: const EdgeInsets.all(16),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(MX.rLg),
                borderSide: const BorderSide(color: MX.line),
              ),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(MX.rLg),
                borderSide: const BorderSide(color: MX.line),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(MX.rLg),
                borderSide: const BorderSide(color: MX.accentAi, width: 1.5),
              ),
            ),
          ),
          const SizedBox(height: 20),
          SizedBox(
            width: double.infinity,
            height: 52,
            child: Material(
              color: MX.accentAi,
              borderRadius: BorderRadius.circular(MX.rFull),
              child: InkWell(
                borderRadius: BorderRadius.circular(MX.rFull),
                onTap: sending ? null : onSend,
                child: Center(
                  child: sending
                      ? const SizedBox(
                          width: 20, height: 20,
                          child: CircularProgressIndicator(
                            color: MX.bgBase, strokeWidth: 2,
                          ),
                        )
                      : const Text(
                          'Сохранить',
                          style: TextStyle(
                            color: MX.bgBase, fontSize: 15, fontWeight: FontWeight.w700,
                          ),
                        ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _IconCircle extends StatelessWidget {
  const _IconCircle({
    required this.icon,
    required this.color,
    this.border,
    required this.size,
    required this.onTap,
  });
  final IconData icon;
  final Color color;
  final Color? border;
  final double size;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: size, height: size,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: MX.surfaceOverlay,
          border: Border.all(color: border ?? MX.line),
        ),
        child: Icon(icon, color: color, size: size * 0.4),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────
// Live waveform: 48 bars, sine-wave height modulated by animation phase.
// ─────────────────────────────────────────────────────────────────────────

class _Waveform extends StatelessWidget {
  const _Waveform({required this.phase});
  final double phase;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 68,
      child: CustomPaint(
        painter: _WaveformPainter(phase: phase),
        size: const Size.fromHeight(68),
      ),
    );
  }
}

class _WaveformPainter extends CustomPainter {
  _WaveformPainter({required this.phase});
  final double phase;
  static const int bars = 48;
  static final Random _rng = Random(7);

  @override
  void paint(Canvas canvas, Size size) {
    const gap = 3.0;
    final barWidth = (size.width - gap * (bars - 1)) / bars;
    final paint = Paint()
      ..style = PaintingStyle.fill
      ..strokeCap = StrokeCap.round;

    for (var i = 0; i < bars; i++) {
      // Базовая синусоида + небольшой стабильный джиттер на бар.
      final freq = (i / bars) * 2 * pi;
      final sineAmp = (sin(freq * 3 + phase * 2 * pi) + 1) / 2;
      final jitter = 0.4 + 0.6 * (_rng.nextDouble());
      final heightFactor = (0.2 + sineAmp * 0.8) * jitter;
      final h = (size.height * heightFactor).clamp(3.0, size.height);

      // Активный диапазон — центральные столбики ярче.
      final isActive = i > 6 && i < bars - 6;
      paint.color = isActive ? MX.accentAi : MX.fgGhost;

      final x = i * (barWidth + gap);
      final y = (size.height - h) / 2;
      final rect = RRect.fromRectAndRadius(
        Rect.fromLTWH(x, y, barWidth, h),
        const Radius.circular(2),
      );
      canvas.drawRRect(rect, paint);
    }
  }

  @override
  bool shouldRepaint(covariant _WaveformPainter oldDelegate) => oldDelegate.phase != phase;
}
