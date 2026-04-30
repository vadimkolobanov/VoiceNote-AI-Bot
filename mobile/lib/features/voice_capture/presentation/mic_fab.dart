import 'dart:async';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons/lucide_icons.dart';

import 'package:voicenote_ai/app.dart';
import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/theme/mx_tokens.dart';
import 'package:voicenote_ai/features/moments/application/moments_providers.dart';
import 'package:voicenote_ai/features/moments/data/models/moment.dart';
import 'package:voicenote_ai/features/moments/data/repositories/moments_repository.dart';
import 'package:voicenote_ai/features/voice_capture/data/voice_recorder.dart';

/// Inline-микрофон. Записывает голос локально (без on-device STT, без пиков
/// системы), на стопе аплоадит на бэк → Yandex SpeechKit → текст → создание
/// момента → undo-toast.
class MicFab extends ConsumerStatefulWidget {
  const MicFab({super.key});

  @override
  ConsumerState<MicFab> createState() => _MicFabState();
}

enum _Mode { voiceIdle, voiceRecording, voiceTranscribing, voiceSaving, textIdle, textComposing }

class _MicFabState extends ConsumerState<MicFab>
    with TickerProviderStateMixin {
  // State
  _Mode _mode = _Mode.voiceIdle;
  String _liveText = '';
  bool _isVoiceMode = true;
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
  StreamSubscription<double>? _ampSub;

  // Auto-stop on silence
  Timer? _silenceTimer;
  static const _silenceMs = 1800;
  static const _silenceAmpThreshold = 0.12;

  // Bubble overlay
  OverlayEntry? _bubbleEntry;

  // Drag tracking
  Offset _dragStart = Offset.zero;
  bool _dragHandled = false;

  @override
  void dispose() {
    _breath.dispose();
    _morph.dispose();
    _modeMorph.dispose();
    _ampSub?.cancel();
    _silenceTimer?.cancel();
    _textCtl.dispose();
    _hideBubble();
    super.dispose();
  }

  // -- mode toggle ------------------------------------------------------

  Future<void> _toggleMode() async {
    HapticFeedback.selectionClick();
    if (_mode == _Mode.voiceRecording || _mode == _Mode.textComposing) {
      await _cancel();
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

  Future<void> _onTap() async {
    HapticFeedback.lightImpact();
    switch (_mode) {
      case _Mode.voiceIdle:
        await _startRecording();
        break;
      case _Mode.voiceRecording:
        await _stopAndCommit();
        break;
      case _Mode.textIdle:
        _openCompose();
        break;
      case _Mode.textComposing:
        await _commit();
        break;
      case _Mode.voiceTranscribing:
      case _Mode.voiceSaving:
        // в процессе — ничего не делаем
        break;
    }
  }

  // -- voice recording --------------------------------------------------

  Future<void> _startRecording() async {
    final recorder = ref.read(voiceRecorderProvider);
    final ok = await recorder.start();
    if (!ok) {
      _showInlineToast('Нужен доступ к микрофону', error: true);
      return;
    }
    if (!mounted) return;

    setState(() {
      _mode = _Mode.voiceRecording;
      _liveText = '';
    });
    _showBubble();

    _ampSub?.cancel();
    _ampSub = recorder.amplitudeStream.listen((a) {
      if (!mounted) return;
      setState(() => _amp = a);
      if (a >= _silenceAmpThreshold) {
        _silenceTimer?.cancel();
        _silenceTimer = Timer(
          const Duration(milliseconds: _silenceMs),
          _onSilence,
        );
      }
    });
  }

  void _onSilence() {
    if (_mode != _Mode.voiceRecording) return;
    // Авто-стоп на тишине, только если запись длилась хоть пару секунд
    _stopAndCommit();
  }

  Future<void> _stopAndCommit() async {
    if (_mode != _Mode.voiceRecording) return;
    HapticFeedback.mediumImpact();
    _silenceTimer?.cancel();
    _ampSub?.cancel();
    _ampSub = null;

    final recorder = ref.read(voiceRecorderProvider);
    final path = await recorder.stop();
    if (!mounted) return;

    if (path == null) {
      _resetIdle();
      return;
    }

    setState(() {
      _mode = _Mode.voiceTranscribing;
      _amp = 0;
    });
    _bubbleEntry?.markNeedsBuild();

    String text = '';
    try {
      final result = await recorder.recognize(path);
      text = result.text.trim();
    } on ApiException catch (e) {
      _showInlineToast(e.message, error: true);
      _hideBubble();
      _resetIdle();
      return;
    } catch (e) {
      _showInlineToast('Не удалось распознать', error: true);
      _hideBubble();
      _resetIdle();
      return;
    }

    if (text.isEmpty) {
      _showInlineToast('Не услышал. Попробуй ближе к микрофону.');
      _hideBubble();
      _resetIdle();
      return;
    }

    if (!mounted) return;
    setState(() {
      _liveText = text;
    });
    _bubbleEntry?.markNeedsBuild();
    await _commitText(text, isVoice: true);
  }

  // -- text compose -----------------------------------------------------

  void _openCompose() {
    setState(() {
      _mode = _Mode.textComposing;
      _textCtl.text = '';
    });
    _showBubble();
  }

  Future<void> _commit() async {
    final text = _textCtl.text.trim();
    if (text.isEmpty) {
      await _cancel();
      return;
    }
    await _commitText(text, isVoice: false);
  }

  Future<void> _commitText(String text, {required bool isVoice}) async {
    setState(() => _mode = _Mode.voiceSaving);
    _bubbleEntry?.markNeedsBuild();
    _morph.forward(from: 0);

    Moment? saved;
    try {
      final create = ref.read(createMomentProvider);
      saved = await create(rawText: text, source: isVoice ? 'voice' : 'text');
    } on ApiException catch (e) {
      _showInlineToast(e.message, error: true);
      _hideBubble();
      _resetIdle();
      return;
    } catch (e) {
      _showInlineToast('$e', error: true);
      _hideBubble();
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

  Future<void> _cancel() async {
    _silenceTimer?.cancel();
    _ampSub?.cancel();
    _ampSub = null;
    try {
      await ref.read(voiceRecorderProvider).cancel();
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
      _amp = 0;
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
    if (_mode == _Mode.voiceTranscribing) {
      return _BubbleCard(
        onClose: _cancel,
        child: Row(
          children: const [
            SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: MX.accentAi,
              ),
            ),
            SizedBox(width: 12),
            Text(
              'Распознаю…',
              style: TextStyle(color: MX.fg, fontSize: 16),
            ),
          ],
        ),
      );
    }
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
    // voiceRecording
    return _BubbleCard(
      onClose: _cancel,
      placeholder: 'Слушаю…',
      footerHint: 'Молчишь 1.8с → сохраню. Тап мик — сейчас.',
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
              final ampScale = (_mode == _Mode.voiceRecording)
                  ? _amp * 0.36
                  : 0.0;
              final scale = breathScale + ampScale;
              final voiceCore =
                  Color.lerp(MX.accentAi, MX.accentPurple, _morph.value)!;
              final voiceHalo = Color.lerp(
                const Color(0xFF00B8D4),
                const Color(0xFF7C3AED),
                _morph.value,
              )!;
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
                active: _mode == _Mode.voiceRecording,
                processing: _mode == _Mode.voiceTranscribing,
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
    required this.active,
    required this.processing,
    required this.saving,
    required this.modeMorph,
  });

  final double scale;
  final Color core;
  final Color halo;
  final bool active;
  final bool processing;
  final bool saving;
  final double modeMorph;

  @override
  Widget build(BuildContext context) {
    final glowAlpha = saving ? 220 : (active ? 200 : 170);

    return Stack(
      alignment: Alignment.center,
      children: [
        if (active || saving || processing)
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
              child: processing
                  ? const SizedBox(
                      width: 26,
                      height: 26,
                      child: CircularProgressIndicator(
                        strokeWidth: 2.5,
                        color: Colors.white,
                      ),
                    )
                  : Opacity(
                      opacity: 1 - modeMorph,
                      child: const Icon(LucideIcons.mic,
                          color: Colors.white, size: 28),
                    ),
            ),
          ),
        ),
        if (modeMorph > 0.05 && !processing)
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
