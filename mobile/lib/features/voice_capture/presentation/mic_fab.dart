import 'dart:async';
import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons/lucide_icons.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;

import 'package:voicenote_ai/app.dart';
import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/theme/mx_tokens.dart';
import 'package:voicenote_ai/features/moments/application/moments_providers.dart';
import 'package:voicenote_ai/features/moments/data/models/moment.dart';
import 'package:voicenote_ai/features/moments/data/repositories/moments_repository.dart';

/// Inline-микрофон в shell. Без отдельной страницы:
/// - тап (voice idle) → начинает слушать прямо тут, орб дышит, облачко с
///   транскриптом всплывает над FAB
/// - тап (listening) → сохранить
/// - 2.5 сек тишины → сохранить
/// - свайп вверх (drag) → отмена
/// - свайп влево/вправо → переключение режим voice ↔ text (буква "T")
/// - тап (text idle) → облачко с textfield для ручного ввода
class MicFab extends ConsumerStatefulWidget {
  const MicFab({super.key});

  @override
  ConsumerState<MicFab> createState() => _MicFabState();
}

enum _Mode { voiceIdle, voiceListening, voiceSaving, textIdle, textComposing }

class _MicFabState extends ConsumerState<MicFab>
    with TickerProviderStateMixin {
  // Speech
  final _stt = stt.SpeechToText();
  bool _sttInited = false;

  // State
  _Mode _mode = _Mode.voiceIdle;
  String _liveText = '';
  bool _isVoiceMode = true; // флаг переключения voice/text по свайпу
  final _textCtl = TextEditingController();
  final _fabKey = GlobalKey();

  // Animations
  late final AnimationController _breath = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 2400),
  )..repeat(reverse: true);
  late final AnimationController _morph = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 700),
  );
  late final AnimationController _modeMorph = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 240),
    value: 0,
  );

  // Amplitude
  double _amp = 0.0;
  double _ampTarget = 0.0;
  Timer? _ampTicker;

  // Auto-stop
  Timer? _silenceTimer;
  static const _silenceMs = 2500;

  // Bubble overlay
  OverlayEntry? _bubbleEntry;

  // Drag tracking (для определения свайпа влево/вправо/вверх)
  Offset _dragStart = Offset.zero;
  bool _dragHandled = false;

  @override
  void initState() {
    super.initState();
    _startAmpTicker();
  }

  @override
  void dispose() {
    _breath.dispose();
    _morph.dispose();
    _modeMorph.dispose();
    _ampTicker?.cancel();
    _silenceTimer?.cancel();
    _textCtl.dispose();
    _stt.cancel();
    _hideBubble();
    super.dispose();
  }

  // -- amplitude smoother -----------------------------------------------

  void _startAmpTicker() {
    _ampTicker = Timer.periodic(const Duration(milliseconds: 16), (_) {
      final next = _amp + (_ampTarget - _amp) * 0.18;
      final eq = (next - _amp).abs() < 0.001 && _ampTarget == 0;
      if (!eq) {
        if (mounted) setState(() => _amp = next);
      }
      _ampTarget = math.max(0.0, _ampTarget - 0.015);
    });
  }

  // -- mode toggle (swipe) ----------------------------------------------

  void _toggleMode() {
    HapticFeedback.selectionClick();
    if (_mode == _Mode.voiceListening || _mode == _Mode.textComposing) {
      _cancel();
    }
    setState(() {
      _isVoiceMode = !_isVoiceMode;
      _mode = _isVoiceMode ? _Mode.voiceIdle : _Mode.textIdle;
    });
    if (_isVoiceMode) {
      _modeMorph.reverse();
    } else {
      _modeMorph.forward();
    }
  }

  // -- gestures ---------------------------------------------------------

  void _onTap() {
    HapticFeedback.lightImpact();
    switch (_mode) {
      case _Mode.voiceIdle:
        _startListening();
        break;
      case _Mode.voiceListening:
        _commit();
        break;
      case _Mode.textIdle:
        _openCompose();
        break;
      case _Mode.textComposing:
        _commit();
        break;
      case _Mode.voiceSaving:
        break;
    }
  }

  // -- voice listening --------------------------------------------------

  Future<void> _ensureStt() async {
    if (_sttInited) return;
    final mic = await Permission.microphone.status;
    if (!mic.isGranted) {
      final r = await Permission.microphone.request();
      if (!r.isGranted) {
        rootMessengerKey.currentState?.showSnackBar(
          const SnackBar(content: Text('Нужен доступ к микрофону')),
        );
        return;
      }
    }
    final ok = await _stt.initialize(
      onStatus: (s) {
        if (!mounted) return;
        // Android SpeechRecognizer выключается через ~5-10с — сами рестартим
        // пока юзер активно слушает (а не нажал save/cancel).
        if ((s == 'done' || s == 'notListening') &&
            _mode == _Mode.voiceListening) {
          _restartListening();
        }
      },
      onError: (e) {
        if (!mounted) return;
        if (_mode == _Mode.voiceListening) {
          _restartListening();
        }
      },
    );
    _sttInited = ok;
  }

  Future<void> _restartListening() async {
    await Future<void>.delayed(const Duration(milliseconds: 250));
    if (!mounted || _mode != _Mode.voiceListening) return;
    try {
      await _stt.listen(
        onResult: (r) {
          if (!mounted) return;
          setState(() => _liveText = r.recognizedWords);
          _bumpSpeech();
          _bubbleEntry?.markNeedsBuild();
        },
        onSoundLevelChange: (level) {
          if (!mounted) return;
          final norm = (level + 2) / 12;
          _ampTarget = norm.clamp(0.0, 1.0);
          if (level > 0.3) _bumpSpeech();
        },
        listenOptions: stt.SpeechListenOptions(
          partialResults: true,
          cancelOnError: false,
          listenMode: stt.ListenMode.dictation,
        ),
        pauseFor: const Duration(seconds: 60),
        listenFor: const Duration(minutes: 2),
        localeId: 'ru_RU',
      );
    } catch (_) {/* ignore */}
  }

  Future<void> _startListening() async {
    await _ensureStt();
    if (!_sttInited || !mounted) return;
    setState(() {
      _mode = _Mode.voiceListening;
      _liveText = '';
    });
    _showBubble();
    await _stt.listen(
      onResult: (r) {
        if (!mounted) return;
        setState(() => _liveText = r.recognizedWords);
        _bumpSpeech();
        _bubbleEntry?.markNeedsBuild();
      },
      onSoundLevelChange: (level) {
        if (!mounted) return;
        final norm = (level + 2) / 12;
        _ampTarget = norm.clamp(0.0, 1.0);
        if (level > 0.3) _bumpSpeech();
      },
      listenOptions: stt.SpeechListenOptions(
        partialResults: true,
        cancelOnError: true,
        listenMode: stt.ListenMode.dictation,
      ),
      pauseFor: const Duration(seconds: 60),
      listenFor: const Duration(minutes: 2),
      localeId: 'ru_RU',
    );
  }

  void _bumpSpeech() {
    _silenceTimer?.cancel();
    _silenceTimer = Timer(const Duration(milliseconds: _silenceMs), _onSilence);
  }

  void _onSilence() {
    if (_mode != _Mode.voiceListening) return;
    if (_liveText.trim().length < 2) return;
    _commit();
  }

  // -- text compose -----------------------------------------------------

  void _openCompose() {
    setState(() {
      _mode = _Mode.textComposing;
      _textCtl.text = '';
    });
    _showBubble();
  }

  // -- commit / cancel --------------------------------------------------

  Future<void> _commit() async {
    if (_mode == _Mode.voiceSaving) return;
    HapticFeedback.mediumImpact();
    _silenceTimer?.cancel();

    final isVoice = _mode == _Mode.voiceListening;
    final text = isVoice ? _liveText.trim() : _textCtl.text.trim();

    if (isVoice) {
      try {
        await _stt.stop();
      } catch (_) {}
    }

    if (text.isEmpty) {
      _cancel();
      return;
    }

    setState(() => _mode = _Mode.voiceSaving);
    _bubbleEntry?.markNeedsBuild();
    _morph.forward(from: 0);

    Moment? saved;
    try {
      final create = ref.read(createMomentProvider);
      saved = await create(
        rawText: text,
        source: isVoice ? 'voice' : 'text',
      );
    } on ApiException catch (e) {
      _showInlineToast(e.message, error: true);
      _resetIdle();
      return;
    } catch (e) {
      _showInlineToast('$e', error: true);
      _resetIdle();
      return;
    }

    await Future<void>.delayed(const Duration(milliseconds: 450));
    if (!mounted) return;
    HapticFeedback.lightImpact();
    _hideBubble();
    _showUndoToast(saved);
    _resetIdle();
  }

  void _cancel() {
    _silenceTimer?.cancel();
    try {
      _stt.cancel();
    } catch (_) {}
    _hideBubble();
    _resetIdle();
  }

  void _resetIdle() {
    if (!mounted) return;
    _morph.reset();
    setState(() {
      _liveText = '';
      _textCtl.clear();
      _mode = _isVoiceMode ? _Mode.voiceIdle : _Mode.textIdle;
    });
  }

  // -- bubble overlay ---------------------------------------------------

  void _showBubble() {
    _hideBubble();
    final entry = OverlayEntry(builder: (_) => _BubbleHost(
      fabKey: _fabKey,
      builder: _buildBubbleContent,
    ));
    _bubbleEntry = entry;
    Overlay.of(context, rootOverlay: true).insert(entry);
  }

  void _hideBubble() {
    _bubbleEntry?.remove();
    _bubbleEntry = null;
  }

  Widget _buildBubbleContent(BuildContext ctx) {
    if (_mode == _Mode.voiceSaving) {
      return _BubbleCard(
        text: _liveText.isEmpty ? _textCtl.text : _liveText,
        showCheck: true,
      );
    }
    if (_mode == _Mode.textComposing) {
      return _BubbleCard(
        onClose: _cancel,
        child: TextField(
          controller: _textCtl,
          autofocus: true,
          maxLines: null,
          minLines: 1,
          style: const TextStyle(color: MX.fg, fontSize: 16, height: 1.4),
          decoration: const InputDecoration(
            hintText: 'Расскажи…',
            hintStyle: TextStyle(color: MX.fgFaint),
            border: InputBorder.none,
            isDense: true,
            contentPadding: EdgeInsets.zero,
          ),
          onSubmitted: (_) => _commit(),
          textInputAction: TextInputAction.done,
          onChanged: (_) => _bubbleEntry?.markNeedsBuild(),
        ),
        footerHint: _textCtl.text.trim().isEmpty
            ? 'Свайп ↕ — на голос'
            : 'Тап T — сохранить',
      );
    }
    // listening
    return _BubbleCard(
      onClose: _cancel,
      text: _liveText.isEmpty ? null : _liveText,
      placeholder: 'Слушаю…',
      footerHint: _liveText.isEmpty
          ? 'Свайп ↕ — текстом'
          : 'Тишина 2.5с → сохраню. Тап мик — сейчас.',
    );
  }

  void _showInlineToast(String msg, {bool error = false}) {
    rootMessengerKey.currentState
      ?..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          duration: const Duration(milliseconds: 1800),
          backgroundColor: error ? const Color(0xFF3a1010) : MX.bgElevated,
          content: Text(
            msg,
            style: const TextStyle(color: MX.fg, fontSize: 13),
          ),
          margin: const EdgeInsets.fromLTRB(20, 0, 20, 90),
          behavior: SnackBarBehavior.floating,
        ),
      );
  }

  void _showUndoToast(Moment moment) {
    final repo = ref.read(momentsRepositoryProvider);
    rootMessengerKey.currentState
      ?..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          duration: const Duration(milliseconds: 2200),
          backgroundColor: MX.bgElevated,
          margin: const EdgeInsets.fromLTRB(20, 0, 20, 90),
          behavior: SnackBarBehavior.floating,
          content: Row(
            children: [
              const Icon(LucideIcons.checkCircle2,
                  size: 16, color: Color(0xFF34D399)),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  moment.title.isEmpty ? 'Запомнил' : moment.title,
                  style: const TextStyle(color: MX.fg, fontSize: 13),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              const SizedBox(width: 8),
              GestureDetector(
                onTap: () async {
                  rootMessengerKey.currentState?.hideCurrentSnackBar();
                  try {
                    await repo.delete(moment.id);
                  } catch (_) {}
                },
                child: const Text(
                  'Отмена',
                  style: TextStyle(
                    color: MX.accentAi,
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),
        ),
      );
  }

  // -- build ------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      key: _fabKey,
      behavior: HitTestBehavior.opaque,
      onTap: _onTap,
      onPanStart: (d) {
        _dragStart = d.globalPosition;
        _dragHandled = false;
      },
      onPanUpdate: (d) {
        if (_dragHandled) return;
        final dx = d.globalPosition.dx - _dragStart.dx;
        final dy = d.globalPosition.dy - _dragStart.dy;
        // Вертикальный свайп (вверх или вниз) = переключение режима.
        // Если что-то записывалось/набиралось — _toggleMode сам отменит.
        if (dy.abs() > 40 && dy.abs() > dx.abs() * 1.5) {
          _dragHandled = true;
          _toggleMode();
        }
      },
      child: SizedBox(
        height: 92,
        width: 92,
        child: Center(
          child: AnimatedBuilder(
            animation: Listenable.merge([_breath, _morph, _modeMorph]),
            builder: (_, __) {
              final breathScale = 1 + (_breath.value - 0.5) * 0.04;
              final ampScale = (_mode == _Mode.voiceListening)
                  ? _amp * 0.32
                  : 0.0;
              final scale = breathScale + ampScale;
              // Voice палитра: cyan → purple на сохранении.
              final voiceCore =
                  Color.lerp(MX.accentAi, MX.accentPurple, _morph.value)!;
              final voiceHalo = Color.lerp(
                const Color(0xFF00B8D4),
                const Color(0xFF7C3AED),
                _morph.value,
              )!;
              // Text палитра: тёплый зелёный → янтарь на сохранении.
              final textCore = Color.lerp(
                const Color(0xFF34D399),
                const Color(0xFFFBBF24),
                _morph.value,
              )!;
              final textHalo = Color.lerp(
                const Color(0xFF10B981),
                const Color(0xFFF59E0B),
                _morph.value,
              )!;
              final core = Color.lerp(voiceCore, textCore, _modeMorph.value)!;
              final halo = Color.lerp(voiceHalo, textHalo, _modeMorph.value)!;
              return _OrbBody(
                scale: scale,
                core: core,
                halo: halo,
                listening: _mode == _Mode.voiceListening,
                saving: _mode == _Mode.voiceSaving,
                modeMorph: _modeMorph.value,
              );
            },
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------

class _OrbBody extends StatelessWidget {
  const _OrbBody({
    required this.scale,
    required this.core,
    required this.halo,
    required this.listening,
    required this.saving,
    required this.modeMorph,
  });

  final double scale;
  final Color core;
  final Color halo;
  final bool listening;
  final bool saving;
  final double modeMorph; // 0 = voice, 1 = text

  @override
  Widget build(BuildContext context) {
    final glowAlpha = saving
        ? 220
        : (listening ? 200 : 170);

    return Stack(
      alignment: Alignment.center,
      children: [
        // glow halo (visible only listening/saving)
        if (listening || saving)
          Transform.scale(
            scale: scale * 1.6,
            child: ImageFiltered(
              imageFilter: ui.ImageFilter.blur(sigmaX: 18, sigmaY: 18),
              child: Container(
                width: 72,
                height: 72,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: halo.withAlpha(110),
                ),
              ),
            ),
          ),
        Transform.scale(
          scale: scale,
          child: Container(
            width: 72,
            height: 72,
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
                  blurRadius: 22,
                  spreadRadius: 2,
                ),
              ],
            ),
            child: Center(
              child: Opacity(
                opacity: 1 - modeMorph,
                child: const Icon(LucideIcons.mic,
                    color: Colors.white, size: 28),
              ),
            ),
          ),
        ),
        // 'T' символ для text-mode
        if (modeMorph > 0.05)
          Opacity(
            opacity: modeMorph,
            child: const Text(
              'T',
              style: TextStyle(
                color: Colors.white,
                fontSize: 26,
                fontWeight: FontWeight.w600,
                fontFamily: 'serif',
                letterSpacing: -1,
              ),
            ),
          ),
      ],
    );
  }
}

// ---------------------------------------------------------------------------
// Bubble — позиционируется относительно FAB.
// ---------------------------------------------------------------------------

class _BubbleHost extends StatefulWidget {
  const _BubbleHost({required this.fabKey, required this.builder});
  final GlobalKey fabKey;
  final WidgetBuilder builder;

  @override
  State<_BubbleHost> createState() => _BubbleHostState();
}

class _BubbleHostState extends State<_BubbleHost>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctl = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 220),
  )..forward();

  @override
  void dispose() {
    _ctl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final mq = MediaQuery.of(context);
    final renderBox =
        widget.fabKey.currentContext?.findRenderObject() as RenderBox?;
    final fabRect = renderBox?.localToGlobal(Offset.zero);
    final screenW = mq.size.width;
    final fabCenterX = (fabRect?.dx ?? screenW / 2) +
        (renderBox?.size.width ?? 64) / 2;
    final fabTop = fabRect?.dy ??
        mq.size.height - 84 - mq.padding.bottom;

    return AnimatedBuilder(
      animation: _ctl,
      builder: (_, child) => Opacity(
        opacity: _ctl.value,
        child: Transform.translate(
          offset: Offset(0, (1 - _ctl.value) * 12),
          child: child,
        ),
      ),
      child: Stack(
        children: [
          Positioned(
            left: 24,
            right: 24,
            bottom: mq.size.height - fabTop + 18,
            child: Center(
              child: Builder(builder: (ctx) => widget.builder(ctx)),
            ),
          ),
          Positioned(
            left: fabCenterX - 6,
            bottom: mq.size.height - fabTop + 8,
            child: const _BubbleTail(),
          ),
        ],
      ),
    );
  }
}

class _BubbleCard extends StatelessWidget {
  const _BubbleCard({
    this.text,
    this.placeholder,
    this.child,
    this.footerHint,
    this.showCheck = false,
    this.onClose,
  });
  final String? text;
  final String? placeholder;
  final Widget? child;
  final String? footerHint;
  final bool showCheck;
  final VoidCallback? onClose;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 360),
      child: Container(
        padding: const EdgeInsets.fromLTRB(16, 14, 16, 12),
        decoration: BoxDecoration(
          color: const Color(0xFF1a1a1f),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: const Color(0x1AFFFFFF)),
          boxShadow: const [
            BoxShadow(
              color: Color(0x60000000),
              blurRadius: 30,
              offset: Offset(0, 12),
            ),
          ],
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Заголовок-строка: статус + close (если onClose)
            if (showCheck || onClose != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                  children: [
                    if (showCheck) ...[
                      const Icon(LucideIcons.checkCircle2,
                          size: 16, color: Color(0xFF34D399)),
                      const SizedBox(width: 6),
                      Text(
                        'Запомнил',
                        style: t.textTheme.labelSmall?.copyWith(
                          color: const Color(0xFF34D399),
                          letterSpacing: 0.5,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                    const Spacer(),
                    if (onClose != null)
                      InkWell(
                        onTap: onClose,
                        borderRadius: BorderRadius.circular(20),
                        child: Padding(
                          padding: const EdgeInsets.all(2),
                          child: Icon(LucideIcons.x,
                              size: 18, color: MX.fgMuted),
                        ),
                      ),
                  ],
                ),
              ),
            if (child != null)
              child!
            else
              Text(
                (text?.isNotEmpty ?? false) ? text! : (placeholder ?? '…'),
                style: TextStyle(
                  color: (text?.isNotEmpty ?? false) ? MX.fg : MX.fgFaint,
                  fontSize: 16,
                  height: 1.4,
                ),
              ),
            if (footerHint != null && footerHint!.isNotEmpty) ...[
              const SizedBox(height: 10),
              Text(
                footerHint!,
                style: t.textTheme.labelSmall?.copyWith(
                  color: MX.fgMicro,
                  letterSpacing: 0.3,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _BubbleTail extends StatelessWidget {
  const _BubbleTail();

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      size: const Size(12, 8),
      painter: _TailPainter(),
    );
  }
}

class _TailPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..color = const Color(0xFF1a1a1f);
    final path = Path()
      ..moveTo(0, 0)
      ..lineTo(size.width / 2, size.height)
      ..lineTo(size.width, 0)
      ..close();
    canvas.drawPath(path, paint);
    final border = Paint()
      ..color = const Color(0x1AFFFFFF)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1;
    canvas.drawPath(path, border);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
