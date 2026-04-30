import 'dart:async';
import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons/lucide_icons.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/network/dio_client.dart';
import 'package:voicenote_ai/core/theme/mx_tokens.dart';

/// Режим «Расскажи о себе» — длинная исповедь приложению. Извлекаются только
/// факты (без создания моментов). Эстетика — большая «аудио-капсула»:
/// фиолетовый/cyan орб дышит и реагирует на голос, транскрипт растёт сверху.
///
/// Отличия от мгновенного захвата (MicFab):
/// - тап-toggle, **без** автостопа по тишине (можно делать паузы)
/// - явная кнопка «Запомни» (длинная сессия требует уверенного коммита)
/// - крупная зона транскрипта, прокрутка
class LearningScreen extends ConsumerStatefulWidget {
  const LearningScreen({super.key});

  @override
  ConsumerState<LearningScreen> createState() => _LearningScreenState();
}

class _LearningScreenState extends ConsumerState<LearningScreen>
    with TickerProviderStateMixin {
  // STT
  final _stt = stt.SpeechToText();
  bool _sttReady = false;

  // Animation
  late final AnimationController _breath = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 2400),
  )..repeat(reverse: true);
  late final AnimationController _morph = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 700),
  );

  // State
  bool _listening = false;
  bool _saving = false;
  bool _textMode = false;
  String _liveText = '';
  final _textCtl = TextEditingController();
  final _scrollCtl = ScrollController();

  // Amplitude
  double _amp = 0.0;
  double _ampTarget = 0.0;
  Timer? _ampTicker;

  @override
  void initState() {
    super.initState();
    HapticFeedback.lightImpact();
    _startAmpTicker();
    _initStt();
  }

  @override
  void dispose() {
    _breath.dispose();
    _morph.dispose();
    _ampTicker?.cancel();
    _textCtl.dispose();
    _scrollCtl.dispose();
    _stt.cancel();
    super.dispose();
  }

  void _startAmpTicker() {
    _ampTicker = Timer.periodic(const Duration(milliseconds: 16), (_) {
      final next = _amp + (_ampTarget - _amp) * 0.18;
      if ((next - _amp).abs() > 0.001 || _ampTarget != 0) {
        if (mounted) setState(() => _amp = next);
      }
      _ampTarget = math.max(0.0, _ampTarget - 0.012);
    });
  }

  Future<void> _initStt() async {
    try {
      final ok = await _stt.initialize(
        onStatus: (s) {
          if (!mounted) return;
          // Android SpeechRecognizer внутренне выключается через ~5-10 сек
          // даже если мы хотим долго слушать. Перезапускаем пока юзер сам
          // не остановил.
          if ((s == 'done' || s == 'notListening') && _listening && !_saving) {
            _restartListening();
          }
        },
        onError: (e) {
          if (!mounted) return;
          // error_no_match / speech_timeout — нормально, перезапустим.
          if (_listening && !_saving) {
            _restartListening();
          }
        },
      );
      if (mounted) setState(() => _sttReady = ok);
    } catch (_) {/* ignore */}
  }

  Future<void> _restartListening() async {
    // защита от штормового цикла: ждём 250мс перед перезапуском
    await Future<void>.delayed(const Duration(milliseconds: 250));
    if (!mounted || !_listening || _saving) return;
    // переносим то что уже распознано в commit-text, чтобы не потерять
    final cap = _liveText.trim();
    if (cap.isNotEmpty) {
      final cur = _textCtl.text.trim();
      _textCtl.text = cur.isEmpty ? cap : '$cur $cap';
      _liveText = '';
    }
    try {
      await _stt.listen(
        onResult: (r) {
          if (!mounted) return;
          setState(() => _liveText = r.recognizedWords);
          _scrollToBottom();
        },
        onSoundLevelChange: (level) {
          if (!mounted) return;
          final norm = (level + 2) / 12;
          _ampTarget = norm.clamp(0.0, 1.0);
        },
        listenOptions: stt.SpeechListenOptions(
          partialResults: true,
          cancelOnError: false,
          listenMode: stt.ListenMode.dictation,
        ),
        pauseFor: const Duration(seconds: 30),
        listenFor: const Duration(minutes: 5),
        localeId: 'ru_RU',
      );
    } catch (_) {/* ignore */}
  }

  Future<void> _toggleListening() async {
    if (_saving) return;
    HapticFeedback.lightImpact();
    if (_listening) {
      await _stop();
      return;
    }
    if (!_sttReady) {
      final mic = await Permission.microphone.request();
      if (!mic.isGranted) return;
      await _initStt();
      if (!_sttReady) return;
    }
    setState(() {
      _listening = true;
      _liveText = '';
    });
    await _stt.listen(
      onResult: (r) {
        if (!mounted) return;
        setState(() => _liveText = r.recognizedWords);
        _scrollToBottom();
      },
      onSoundLevelChange: (level) {
        if (!mounted) return;
        final norm = (level + 2) / 12;
        _ampTarget = norm.clamp(0.0, 1.0);
      },
      listenOptions: stt.SpeechListenOptions(
        partialResults: true,
        cancelOnError: true,
        listenMode: stt.ListenMode.dictation,
      ),
      // Большие значения чтобы юзер мог делать паузы и думать.
      pauseFor: const Duration(seconds: 30),
      listenFor: const Duration(minutes: 5),
      localeId: 'ru_RU',
    );
  }

  Future<void> _stop() async {
    final captured = _liveText.trim();
    try {
      await _stt.stop();
    } catch (_) {}
    if (!mounted) return;
    setState(() {
      _listening = false;
      if (captured.isNotEmpty) {
        final cur = _textCtl.text.trim();
        _textCtl.text = cur.isEmpty ? captured : '$cur $captured';
      }
      _liveText = '';
    });
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
    if (_listening) await _stop();
    final text = _textCtl.text.trim();
    if (text.length < 8) {
      _toast('Расскажи побольше — хотя бы пару фраз.');
      return;
    }
    HapticFeedback.mediumImpact();
    setState(() => _saving = true);
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
        setState(() => _saving = false);
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

  // -- build ------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Scaffold(
      backgroundColor: const Color(0xFF050507),
      body: Stack(
        children: [
          // Background radial glow
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
                // Top bar: close + title
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
                      // toggle voice/text
                      IconButton(
                        icon: Icon(
                          _textMode ? LucideIcons.mic : LucideIcons.type,
                          color: MX.fgMuted,
                          size: 22,
                        ),
                        onPressed: () async {
                          if (_listening) await _stop();
                          setState(() => _textMode = !_textMode);
                        },
                      ),
                    ],
                  ),
                ),

                // Hint
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

                // Transcript / textfield (большая зона)
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(24, 8, 24, 16),
                    child: _textMode
                        ? TextField(
                            controller: _textCtl,
                            autofocus: true,
                            maxLines: null,
                            expands: true,
                            enabled: !_saving,
                            textCapitalization: TextCapitalization.sentences,
                            textAlignVertical: TextAlignVertical.top,
                            style: t.textTheme.bodyLarge?.copyWith(
                              color: MX.fg,
                              fontSize: 18,
                              height: 1.5,
                            ),
                            decoration: InputDecoration(
                              hintText:
                                  'Меня зовут Вадим. Жена Диана работает в Сбере. У нас сын Миша — 4 года. Я не ем мясо, бегаю по утрам в 7. По выходным мы ездим к маме в Истру…',
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
                              live: _liveText,
                              listening: _listening,
                            ),
                          ),
                  ),
                ),

                // Orb виден только в голосовом режиме.
                if (!_textMode) ...[
                  AnimatedBuilder(
                    animation: Listenable.merge([_breath, _morph]),
                    builder: (_, __) {
                      final breathScale = 1 + (_breath.value - 0.5) * 0.04;
                      final ampScale = _listening ? _amp * 0.32 : 0.0;
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
                          listening: _listening,
                          saving: _saving,
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

                // Submit
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
                      onPressed: (_saving ||
                              (_textCtl.text.trim().length < 8 &&
                                  _liveText.trim().length < 8))
                          ? null
                          : _submit,
                      icon: _saving
                          ? const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(
                                  strokeWidth: 2, color: Colors.black87),
                            )
                          : const Icon(LucideIcons.brain, size: 18),
                      label: Text(
                        _saving ? 'Запоминаю…' : 'Запомни',
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
    if (_saving) return 'Разбираю на факты…';
    if (_listening) return 'Тап по орбу — пауза';
    if (_textMode) return 'Печатай. Тап «Запомни» когда готов.';
    return 'Тап по орбу — начать рассказ';
  }
}

// ---------------------------------------------------------------------------

class _Transcript extends StatelessWidget {
  const _Transcript({
    required this.committed,
    required this.live,
    required this.listening,
  });

  final String committed;
  final String live;
  final bool listening;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final hasCommitted = committed.trim().isNotEmpty;
    final hasLive = live.trim().isNotEmpty;
    if (!hasCommitted && !hasLive) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 24),
        child: Text(
          listening ? 'Слушаю…' : 'Тап по орбу — начни',
          style: t.textTheme.headlineSmall?.copyWith(
            color: MX.fgFaint,
            fontWeight: FontWeight.w400,
            letterSpacing: -0.3,
            height: 1.4,
          ),
        ),
      );
    }
    return RichText(
      text: TextSpan(
        style: t.textTheme.bodyLarge?.copyWith(
          color: MX.fg,
          fontSize: 19,
          height: 1.5,
        ),
        children: [
          if (hasCommitted) TextSpan(text: committed),
          if (hasCommitted && hasLive) const TextSpan(text: ' '),
          if (hasLive)
            TextSpan(
              text: live,
              style: TextStyle(color: MX.fg.withAlpha(180)),
            ),
        ],
      ),
    );
  }
}

class _BigOrb extends StatelessWidget {
  const _BigOrb({
    required this.scale,
    required this.core,
    required this.halo,
    required this.listening,
    required this.saving,
  });

  final double scale;
  final Color core;
  final Color halo;
  final bool listening;
  final bool saving;

  @override
  Widget build(BuildContext context) {
    const baseSize = 110.0;
    final glowAlpha = saving ? 240 : (listening ? 200 : 160);
    return SizedBox(
      width: 240,
      height: 240,
      child: Stack(
        alignment: Alignment.center,
        children: [
          if (listening || saving)
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
                    core.withAlpha(saving ? 240 : 230),
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
            ),
          ),
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
          // микрофон-индикатор внутри
          if (listening || (!saving && true))
            Positioned(
              bottom: 36,
              child: Icon(
                listening ? LucideIcons.mic : LucideIcons.brain,
                color: Colors.white.withAlpha(200),
                size: 22,
              ),
            ),
        ],
      ),
    );
  }
}
