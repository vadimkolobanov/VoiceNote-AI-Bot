import 'dart:async';
import 'dart:ui' as ui;

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons/lucide_icons.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/network/dio_client.dart';
import 'package:voicenote_ai/core/theme/mx_tokens.dart';
import 'package:voicenote_ai/features/voice_capture/data/voice_recorder.dart';

/// Режим «Расскажи о себе» — длинная исповедь приложению. Извлекаются только
/// факты (без создания моментов).
///
/// Голос записывается локально через `record` (без on-device STT, без
/// системных пиков), один раз на стопе аплоадится в `/voice/recognize`.
/// Текст можно дополнять и редактировать, потом «Запомни» → `/learning/tell`.
class LearningScreen extends ConsumerStatefulWidget {
  const LearningScreen({super.key});

  @override
  ConsumerState<LearningScreen> createState() => _LearningScreenState();
}

enum _Phase { idle, recording, transcribing, saving }

class _LearningScreenState extends ConsumerState<LearningScreen>
    with TickerProviderStateMixin {
  late final AnimationController _breath = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 2400),
  )..repeat(reverse: true);
  late final AnimationController _morph = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 700),
  );

  _Phase _phase = _Phase.idle;
  bool _textMode = false;
  final _textCtl = TextEditingController();
  final _scrollCtl = ScrollController();

  double _amp = 0.0;
  StreamSubscription<double>? _ampSub;

  @override
  void initState() {
    super.initState();
    HapticFeedback.lightImpact();
  }

  @override
  void dispose() {
    _breath.dispose();
    _morph.dispose();
    _ampSub?.cancel();
    _textCtl.dispose();
    _scrollCtl.dispose();
    super.dispose();
  }

  Future<void> _toggleListening() async {
    if (_phase == _Phase.transcribing || _phase == _Phase.saving) return;
    HapticFeedback.lightImpact();
    if (_phase == _Phase.recording) {
      await _stopRecording();
      return;
    }
    final recorder = ref.read(voiceRecorderProvider);
    final ok = await recorder.start();
    if (!ok) {
      _toast('Нужен доступ к микрофону.');
      return;
    }
    if (!mounted) return;
    setState(() => _phase = _Phase.recording);
    _ampSub = recorder.amplitudeStream.listen((a) {
      if (!mounted) return;
      setState(() => _amp = a);
    });
  }

  Future<void> _stopRecording() async {
    _ampSub?.cancel();
    _ampSub = null;
    final recorder = ref.read(voiceRecorderProvider);
    final path = await recorder.stop();
    if (!mounted) return;
    setState(() {
      _phase = _Phase.transcribing;
      _amp = 0;
    });
    if (path == null) {
      setState(() => _phase = _Phase.idle);
      return;
    }
    try {
      final result = await recorder.recognize(path);
      if (!mounted) return;
      final txt = result.text.trim();
      if (txt.isNotEmpty) {
        final cur = _textCtl.text.trim();
        _textCtl.text = cur.isEmpty ? txt : '$cur $txt';
      }
      _scrollToBottom();
    } on ApiException catch (e) {
      _toast(e.message);
    } catch (_) {
      _toast('Не удалось распознать. Попробуй ещё раз.');
    } finally {
      if (mounted) setState(() => _phase = _Phase.idle);
    }
  }

  void _scrollToBottom() {
    if (!_scrollCtl.hasClients) return;
    Future<void>.microtask(() {
      if (_scrollCtl.hasClients) {
        _scrollCtl.animateTo(
          _scrollCtl.position.maxScrollExtent,
          duration: const Duration(milliseconds: 120),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _submit() async {
    if (_phase == _Phase.recording) await _stopRecording();
    final text = _textCtl.text.trim();
    if (text.length < 8) {
      _toast('Расскажи побольше — хотя бы пару фраз.');
      return;
    }
    HapticFeedback.mediumImpact();
    setState(() => _phase = _Phase.saving);
    _morph.forward(from: 0);
    try {
      final dio = ref.read(dioProvider);
      final resp = await dio.post<Map<String, dynamic>>(
        '/learning/tell',
        data: {'text': text},
        options: Options(receiveTimeout: const Duration(seconds: 90)),
      );
      final written = (resp.data?['facts_written'] as num?)?.toInt() ?? 0;
      if (!mounted) return;
      _showResult(written);
    } on ApiException catch (e) {
      _toast(e.message);
    } on DioException catch (e) {
      _toast('Сеть: ${e.message}');
    } catch (e) {
      _toast('$e');
    } finally {
      if (mounted) {
        setState(() => _phase = _Phase.idle);
        _morph.reset();
      }
    }
  }

  void _toast(String m) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));

  void _showResult(int written) {
    showDialog<void>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: MX.bgElevated,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(MX.rLg),
        ),
        title: Row(
          children: [
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: const LinearGradient(
                  colors: [Color(0xFFA78BFA), Color(0xFF7C3AED)],
                ),
                boxShadow: [
                  BoxShadow(
                    color: const Color(0xFFA78BFA).withAlpha(80),
                    blurRadius: 12,
                  ),
                ],
              ),
              child: const Icon(LucideIcons.brain, color: Colors.white, size: 18),
            ),
            const SizedBox(width: 12),
            const Text('Запомнил'),
          ],
        ),
        content: Text(
          written == 0
              ? 'Не нашёл здесь долгоиграющих фактов. Попробуй рассказать о близких, привычках или местах.'
              : 'Добавил в память $written ${_factWord(written)}. Загляни в «Что я о тебе знаю».',
        ),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.of(context).pop();
              if (mounted) {
                _textCtl.clear();
                setState(() {});
              }
            },
            child: const Text('Дальше'),
          ),
          if (written > 0)
            FilledButton(
              onPressed: () {
                Navigator.of(context).pop();
                context.go('/facts');
              },
              child: const Text('Посмотреть'),
            ),
        ],
      ),
    );
  }

  String _factWord(int n) {
    final m100 = n % 100;
    if (m100 >= 11 && m100 <= 14) return 'фактов';
    switch (n % 10) {
      case 1:
        return 'факт';
      case 2:
      case 3:
      case 4:
        return 'факта';
      default:
        return 'фактов';
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Scaffold(
      backgroundColor: const Color(0xFF050507),
      body: Stack(
        children: [
          Positioned.fill(
            child: AnimatedBuilder(
              animation: _morph,
              builder: (_, __) {
                final glow = Color.lerp(
                  const Color(0xFFA78BFA).withAlpha(40),
                  const Color(0xFF7C3AED).withAlpha(60),
                  _morph.value,
                )!;
                return DecoratedBox(
                  decoration: BoxDecoration(
                    gradient: RadialGradient(
                      center: const Alignment(0, 0.4),
                      radius: 1.1,
                      colors: [glow, Colors.transparent],
                    ),
                  ),
                );
              },
            ),
          ),

          SafeArea(
            child: Column(
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(8, 8, 8, 0),
                  child: Row(
                    children: [
                      IconButton(
                        icon: const Icon(LucideIcons.x,
                            color: MX.fgMuted, size: 22),
                        onPressed: () => context.pop(),
                      ),
                      const SizedBox(width: 4),
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 10, vertical: 4),
                        decoration: BoxDecoration(
                          color: const Color(0xFFA78BFA).withAlpha(28),
                          border: Border.all(
                              color: const Color(0xFFA78BFA).withAlpha(60)),
                          borderRadius: BorderRadius.circular(MX.rFull),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Icon(LucideIcons.brain,
                                size: 12, color: Color(0xFFA78BFA)),
                            const SizedBox(width: 6),
                            Text(
                              'РАССКАЖИ О СЕБЕ',
                              style: t.textTheme.labelSmall?.copyWith(
                                color: const Color(0xFFA78BFA),
                                fontSize: 10,
                                letterSpacing: 1,
                              ),
                            ),
                          ],
                        ),
                      ),
                      const Spacer(),
                      IconButton(
                        icon: Icon(
                          _textMode ? LucideIcons.mic : LucideIcons.type,
                          color: MX.fgMuted,
                          size: 22,
                        ),
                        onPressed: () async {
                          if (_phase == _Phase.recording) {
                            await _stopRecording();
                          }
                          setState(() => _textMode = !_textMode);
                        },
                      ),
                    ],
                  ),
                ),

                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 14, 20, 12),
                  child: Text(
                    'Расскажи про близких, привычки, любимые места.\nЯ не сохраню это в Хронику — только в память.',
                    textAlign: TextAlign.center,
                    style: t.textTheme.bodySmall?.copyWith(
                      color: MX.fgMuted,
                      height: 1.5,
                    ),
                  ),
                ),

                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(24, 8, 24, 16),
                    child: _textMode
                        ? TextField(
                            controller: _textCtl,
                            autofocus: true,
                            maxLines: null,
                            expands: true,
                            enabled: _phase != _Phase.saving,
                            textCapitalization: TextCapitalization.sentences,
                            textAlignVertical: TextAlignVertical.top,
                            style: t.textTheme.bodyLarge?.copyWith(
                              color: MX.fg,
                              fontSize: 18,
                              height: 1.5,
                            ),
                            decoration: InputDecoration(
                              hintText:
                                  'Расскажи о себе своими словами — как близкому. О людях, работе, привычках, целях…',
                              hintStyle: t.textTheme.bodyLarge?.copyWith(
                                color: MX.fgFaint,
                                fontSize: 16,
                                height: 1.5,
                              ),
                              border: InputBorder.none,
                              focusedBorder: InputBorder.none,
                              enabledBorder: InputBorder.none,
                              contentPadding: EdgeInsets.zero,
                            ),
                          )
                        : SingleChildScrollView(
                            controller: _scrollCtl,
                            child: _Transcript(
                              committed: _textCtl.text,
                              phase: _phase,
                            ),
                          ),
                  ),
                ),

                if (!_textMode) ...[
                  AnimatedBuilder(
                    animation: Listenable.merge([_breath, _morph]),
                    builder: (_, __) {
                      final breathScale = 1 + (_breath.value - 0.5) * 0.04;
                      final ampScale =
                          (_phase == _Phase.recording) ? _amp * 0.36 : 0.0;
                      final scale = breathScale + ampScale;
                      final core = Color.lerp(
                        const Color(0xFFA78BFA),
                        const Color(0xFF7C3AED),
                        _morph.value,
                      )!;
                      final halo = Color.lerp(
                        const Color(0xFF7C3AED),
                        const Color(0xFF4F46E5),
                        _morph.value,
                      )!;
                      return GestureDetector(
                        onTap: _toggleListening,
                        child: _BigOrb(
                          scale: scale,
                          core: core,
                          halo: halo,
                          phase: _phase,
                        ),
                      );
                    },
                  ),
                  const SizedBox(height: 8),
                  Text(
                    _hint(),
                    textAlign: TextAlign.center,
                    style: t.textTheme.bodySmall?.copyWith(color: MX.fgMicro),
                  ),
                  const SizedBox(height: 12),
                ],

                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 0, 20, 18),
                  child: SizedBox(
                    width: double.infinity,
                    height: 52,
                    child: FilledButton.icon(
                      style: FilledButton.styleFrom(
                        backgroundColor: const Color(0xFFA78BFA),
                        foregroundColor: Colors.black,
                      ),
                      onPressed: (_phase == _Phase.saving ||
                              _phase == _Phase.transcribing ||
                              _textCtl.text.trim().length < 8)
                          ? null
                          : _submit,
                      icon: _phase == _Phase.saving
                          ? const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(
                                  strokeWidth: 2, color: Colors.black87),
                            )
                          : const Icon(LucideIcons.brain, size: 18),
                      label: Text(
                        _phase == _Phase.saving ? 'Запоминаю…' : 'Запомни',
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _hint() {
    switch (_phase) {
      case _Phase.idle:
        return 'Тап по орбу — начать рассказ';
      case _Phase.recording:
        return 'Тап по орбу — пауза';
      case _Phase.transcribing:
        return 'Распознаю…';
      case _Phase.saving:
        return 'Разбираю на факты…';
    }
  }
}

// ---------------------------------------------------------------------------

class _Transcript extends StatelessWidget {
  const _Transcript({required this.committed, required this.phase});

  final String committed;
  final _Phase phase;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final hasCommitted = committed.trim().isNotEmpty;
    if (!hasCommitted) {
      String hint;
      switch (phase) {
        case _Phase.recording:
          hint = 'Слушаю… говори';
          break;
        case _Phase.transcribing:
          hint = 'Распознаю…';
          break;
        default:
          hint = 'Тап по орбу — начни';
      }
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 24),
        child: Text(
          hint,
          style: t.textTheme.headlineSmall?.copyWith(
            color: MX.fgFaint,
            fontWeight: FontWeight.w400,
            letterSpacing: -0.3,
            height: 1.4,
          ),
        ),
      );
    }
    return Text(
      committed,
      style: t.textTheme.bodyLarge?.copyWith(
        color: MX.fg,
        fontSize: 19,
        height: 1.5,
      ),
    );
  }
}

class _BigOrb extends StatelessWidget {
  const _BigOrb({
    required this.scale,
    required this.core,
    required this.halo,
    required this.phase,
  });

  final double scale;
  final Color core;
  final Color halo;
  final _Phase phase;

  @override
  Widget build(BuildContext context) {
    const baseSize = 110.0;
    final active = phase == _Phase.recording ||
        phase == _Phase.saving ||
        phase == _Phase.transcribing;
    final glowAlpha =
        phase == _Phase.saving ? 240 : (active ? 200 : 160);
    return SizedBox(
      width: 240,
      height: 240,
      child: Stack(
        alignment: Alignment.center,
        children: [
          if (active)
            Transform.scale(
              scale: scale * 1.5,
              child: ImageFiltered(
                imageFilter: ui.ImageFilter.blur(sigmaX: 30, sigmaY: 30),
                child: Container(
                  width: baseSize,
                  height: baseSize,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: halo.withAlpha(120),
                  ),
                ),
              ),
            ),
          Transform.scale(
            scale: scale,
            child: Container(
              width: baseSize,
              height: baseSize,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: RadialGradient(
                  center: const Alignment(-0.2, -0.3),
                  radius: 0.95,
                  colors: [
                    core.withAlpha(active ? 240 : 230),
                    core.withAlpha(180),
                    halo.withAlpha(80),
                  ],
                ),
                boxShadow: [
                  BoxShadow(
                    color: core.withAlpha(glowAlpha ~/ 2),
                    blurRadius: 40,
                    spreadRadius: 4,
                  ),
                ],
              ),
              child: Center(
                child: phase == _Phase.transcribing
                    ? const SizedBox(
                        width: 36,
                        height: 36,
                        child: CircularProgressIndicator(
                          strokeWidth: 3,
                          color: Colors.white,
                        ),
                      )
                    : null,
              ),
            ),
          ),
          if (phase != _Phase.transcribing)
            Transform.scale(
              scale: scale * 0.45,
              child: Container(
                width: baseSize * 0.5,
                height: baseSize * 0.5,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: RadialGradient(
                    colors: [
                      Colors.white.withAlpha(220),
                      core.withAlpha(150),
                      core.withAlpha(0),
                    ],
                  ),
                ),
              ),
            ),
          if (phase == _Phase.idle || phase == _Phase.recording)
            Positioned(
              bottom: 36,
              child: Icon(
                phase == _Phase.recording
                    ? LucideIcons.mic
                    : LucideIcons.brain,
                color: Colors.white.withAlpha(200),
                size: 22,
              ),
            ),
        ],
      ),
    );
  }
}
