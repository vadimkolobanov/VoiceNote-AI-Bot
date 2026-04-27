import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/theme/mx_tokens.dart';
import 'package:voicenote_ai/features/moments/application/moments_providers.dart';

/// S11 — Захват момента (PRODUCT_PLAN.md §2.7).
///
/// M5.5: hold-to-talk. Удерживаешь микрофон — слушает; отпустил — стоп.
/// Свайп вверх во время удержания — отмена записи. Текстовое поле наверху,
/// микрофон снизу по центру (как в Telegram/WhatsApp).
class VoiceCaptureScreen extends ConsumerStatefulWidget {
  const VoiceCaptureScreen({super.key});

  @override
  ConsumerState<VoiceCaptureScreen> createState() => _VoiceCaptureScreenState();
}

class _VoiceCaptureScreenState extends ConsumerState<VoiceCaptureScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _pulse = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 800),
  )..repeat(reverse: true);

  final _textCtl = TextEditingController();
  final _stt = stt.SpeechToText();

  bool _busy = false;
  bool _sttReady = false;
  bool _listening = false;
  bool _usedVoice = false;
  bool _cancelOnRelease = false;
  String _liveText = '';
  Offset? _pressOrigin;

  // Порог свайпа вверх для отмены (px)
  static const double _cancelThresholdY = 80;

  @override
  void initState() {
    super.initState();
    _initStt();
  }

  Future<void> _initStt() async {
    try {
      final ok = await _stt.initialize(
        // Не сбрасываем _listening из onStatus: на Android прилетают
        // спонтанные notListening/done события во время речи. UI-флаг
        // _listening управляется только жестами пользователя.
        onStatus: (_) {},
        onError: (e) {
          if (!mounted) return;
          // error_no_match / speech_timeout — спам, игнорируем.
          if (e.errorMsg == 'error_no_match' ||
              e.errorMsg == 'error_speech_timeout') {
            return;
          }
          _toast('STT: ${e.errorMsg}');
        },
      );
      if (mounted) setState(() => _sttReady = ok);
    } catch (_) {
      if (mounted) setState(() => _sttReady = false);
    }
  }

  @override
  void dispose() {
    _pulse.dispose();
    _textCtl.dispose();
    _stt.cancel();
    super.dispose();
  }

  Future<void> _startListening() async {
    if (_busy || _listening) return;
    HapticFeedback.mediumImpact();

    if (!_sttReady) {
      final mic = await Permission.microphone.request();
      if (!mic.isGranted) {
        _toast('Нет разрешения на микрофон');
        return;
      }
      await _initStt();
      if (!_sttReady) {
        _toast('Распознавание речи недоступно');
        return;
      }
    }

    setState(() {
      _liveText = '';
      _listening = true;
      _cancelOnRelease = false;
    });

    await _stt.listen(
      onResult: (r) {
        if (!mounted) return;
        setState(() {
          _liveText = r.recognizedWords;
        });
      },
      listenOptions: stt.SpeechListenOptions(
        partialResults: true,
        cancelOnError: true,
        listenMode: stt.ListenMode.dictation,
      ),
      // Большие значения — мы сами останавливаем по релизу.
      pauseFor: const Duration(seconds: 30),
      listenFor: const Duration(minutes: 2),
      localeId: 'ru_RU',
    );
  }

  Future<void> _stopListening({required bool keepText}) async {
    HapticFeedback.lightImpact();
    final captured = _liveText.trim();
    final hadText = _textCtl.text.trim().isNotEmpty;
    try {
      if (keepText) {
        await _stt.stop();
      } else {
        await _stt.cancel();
      }
    } catch (_) {/* stop у уже остановленного — не страшно */}
    if (!mounted) return;
    setState(() {
      _listening = false;
      if (keepText && captured.isNotEmpty) {
        final cur = _textCtl.text.trim();
        _textCtl.text = cur.isEmpty ? captured : '$cur $captured';
        _textCtl.selection =
            TextSelection.collapsed(offset: _textCtl.text.length);
        _usedVoice = true;
      }
      _liveText = '';
    });
    // Авто-сохранение: если был чистый голосовой ввод (не дописывали к
    // ранее набранному тексту) и что-то распозналось — сразу сейвим.
    if (keepText && captured.isNotEmpty && !hadText) {
      await _save();
    }
  }

  Future<void> _save() async {
    if (_listening) {
      await _stopListening(keepText: true);
    }
    final text = _textCtl.text.trim();
    if (text.isEmpty) {
      _toast('Напиши или скажи что-нибудь.');
      return;
    }
    setState(() => _busy = true);
    try {
      final create = ref.read(createMomentProvider);
      await create(rawText: text, source: _usedVoice ? 'voice' : 'text');
      if (mounted) {
        HapticFeedback.lightImpact();
        context.pop();
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Запомнил.')),
        );
      }
    } on ApiException catch (e) {
      _toast(e.message);
    } catch (e) {
      _toast('$e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _toast(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Scaffold(
      backgroundColor: MX.bgBase,
      body: SafeArea(
        child: Column(
          children: [
            // close
            Align(
              alignment: Alignment.topRight,
              child: Padding(
                padding: const EdgeInsets.all(8),
                child: IconButton(
                  icon: const Icon(Icons.close, color: MX.fgMuted, size: 28),
                  onPressed: _busy ? null : () => context.pop(),
                ),
              ),
            ),

            Padding(
              padding: const EdgeInsets.fromLTRB(20, 4, 20, 8),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Text('Расскажи мне', style: t.textTheme.titleMedium),
              ),
            ),

            // text field — основная зона
            Expanded(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: TextField(
                  controller: _textCtl,
                  autofocus: false,
                  maxLines: null,
                  expands: true,
                  enabled: !_busy && !_listening,
                  textCapitalization: TextCapitalization.sentences,
                  textAlignVertical: TextAlignVertical.top,
                  style: t.textTheme.bodyLarge,
                  decoration: InputDecoration(
                    hintText:
                        'Например: завтра в 10 встреча с Аней по поводу макетов.\n\nИли зажми микрофон и расскажи голосом.',
                    hintStyle:
                        t.textTheme.bodyMedium?.copyWith(color: MX.fgFaint),
                    filled: true,
                    fillColor: MX.surfaceOverlay,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(MX.rMd),
                      borderSide: const BorderSide(color: MX.line),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(MX.rMd),
                      borderSide: const BorderSide(color: MX.accentAi),
                    ),
                    contentPadding: const EdgeInsets.all(16),
                  ),
                ),
              ),
            ),

            // live transcription preview во время записи
            if (_listening)
              Padding(
                padding: const EdgeInsets.fromLTRB(24, 12, 24, 0),
                child: Text(
                  _liveText.isEmpty ? 'Слушаю…' : _liveText,
                  textAlign: TextAlign.center,
                  style: t.textTheme.bodyMedium?.copyWith(
                    color: _cancelOnRelease ? MX.fgMuted : MX.accentAi,
                    fontStyle: _cancelOnRelease ? FontStyle.italic : FontStyle.normal,
                  ),
                ),
              ),

            const SizedBox(height: 12),

            // mic button — hold to talk
            GestureDetector(
              onLongPressStart: (d) {
                _pressOrigin = d.globalPosition;
                _startListening();
              },
              onLongPressMoveUpdate: (d) {
                if (_pressOrigin == null) return;
                final dy = _pressOrigin!.dy - d.globalPosition.dy;
                final shouldCancel = dy > _cancelThresholdY;
                if (shouldCancel != _cancelOnRelease) {
                  setState(() => _cancelOnRelease = shouldCancel);
                  HapticFeedback.selectionClick();
                }
              },
              onLongPressEnd: (_) {
                final cancel = _cancelOnRelease;
                _pressOrigin = null;
                _stopListening(keepText: !cancel);
              },
              onLongPressCancel: () {
                _pressOrigin = null;
                _stopListening(keepText: false);
              },
              onTap: () {
                if (_listening) return;
                _toast('Зажми и держи микрофон, чтобы говорить.');
              },
              child: AnimatedBuilder(
                animation: _pulse,
                builder: (context, child) {
                  final scale = _listening ? 1 + (_pulse.value * 0.18) : 1.0;
                  return Transform.scale(scale: scale, child: child);
                },
                child: Container(
                  width: 96,
                  height: 96,
                  decoration: BoxDecoration(
                    gradient: _listening
                        ? LinearGradient(
                            colors: _cancelOnRelease
                                ? const [Color(0xFF8E8E93), Color(0xFF636366)]
                                : const [Color(0xFFFF5C5C), Color(0xFFFF2D55)],
                          )
                        : MX.brandGradient,
                    shape: BoxShape.circle,
                    boxShadow: MX.fabGlow,
                  ),
                  child: Icon(
                    _cancelOnRelease ? Icons.delete_outline : Icons.mic,
                    size: 44,
                    color: Colors.white,
                  ),
                ),
              ),
            ),

            const SizedBox(height: 8),
            Text(
              _listening
                  ? (_cancelOnRelease
                      ? 'Отпусти — отмена'
                      : 'Свайп вверх — отмена')
                  : 'Зажми, чтобы говорить',
              style: t.textTheme.bodySmall?.copyWith(color: MX.fgMuted),
            ),

            const SizedBox(height: 12),

            // save
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 0, 20, 16),
              child: SizedBox(
                width: double.infinity,
                height: 52,
                child: FilledButton(
                  onPressed: (_busy || _listening) ? null : _save,
                  child: Text(
                    _busy ? 'Сохраняю…' : 'Сохранить',
                    style: const TextStyle(
                        fontSize: 16, fontWeight: FontWeight.w600),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
