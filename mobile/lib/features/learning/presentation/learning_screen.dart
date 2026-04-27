import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/network/dio_client.dart';
import 'package:voicenote_ai/core/theme/mx_tokens.dart';

/// Режим «Расскажи о себе» — текст не становится моментом, а превращается
/// в долгоиграющие факты + эмбеддинги. Память приложения растёт.
class LearningScreen extends ConsumerStatefulWidget {
  const LearningScreen({super.key});

  @override
  ConsumerState<LearningScreen> createState() => _LearningScreenState();
}

class _LearningScreenState extends ConsumerState<LearningScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _pulse = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 800),
  )..repeat(reverse: true);

  final _ctl = TextEditingController();
  final _stt = stt.SpeechToText();
  bool _busy = false;
  bool _sttReady = false;
  bool _listening = false;
  String _liveText = '';

  @override
  void initState() {
    super.initState();
    _initStt();
  }

  Future<void> _initStt() async {
    try {
      final ok = await _stt.initialize(
        onStatus: (_) {},
        onError: (_) {
          if (!mounted) return;
          setState(() => _listening = false);
        },
      );
      if (mounted) setState(() => _sttReady = ok);
    } catch (_) {}
  }

  @override
  void dispose() {
    _pulse.dispose();
    _ctl.dispose();
    _stt.cancel();
    super.dispose();
  }

  Future<void> _start() async {
    if (_busy || _listening) return;
    HapticFeedback.mediumImpact();
    if (!_sttReady) {
      final mic = await Permission.microphone.request();
      if (!mic.isGranted) return;
      await _initStt();
      if (!_sttReady) return;
    }
    setState(() {
      _liveText = '';
      _listening = true;
    });
    await _stt.listen(
      onResult: (r) {
        if (!mounted) return;
        setState(() => _liveText = r.recognizedWords);
      },
      listenOptions: stt.SpeechListenOptions(
        partialResults: true,
        cancelOnError: true,
        listenMode: stt.ListenMode.dictation,
      ),
      pauseFor: const Duration(seconds: 30),
      listenFor: const Duration(minutes: 5),
      localeId: 'ru_RU',
    );
  }

  Future<void> _stop({required bool keep}) async {
    HapticFeedback.lightImpact();
    final captured = _liveText.trim();
    final hadText = _ctl.text.trim().isNotEmpty;
    try {
      if (keep) {
        await _stt.stop();
      } else {
        await _stt.cancel();
      }
    } catch (_) {}
    if (!mounted) return;
    setState(() {
      _listening = false;
      if (keep && captured.isNotEmpty) {
        final cur = _ctl.text.trim();
        _ctl.text = cur.isEmpty ? captured : '$cur $captured';
        _ctl.selection = TextSelection.collapsed(offset: _ctl.text.length);
      }
      _liveText = '';
    });
    // Авто-отправка: чистый голосовой ввод сразу уходит в /learning/tell.
    if (keep && captured.isNotEmpty && !hadText) {
      await _submit();
    }
  }

  Future<void> _submit() async {
    if (_listening) await _stop(keep: true);
    final text = _ctl.text.trim();
    if (text.length < 8) {
      _toast('Расскажи побольше — хотя бы пару фраз.');
      return;
    }
    setState(() => _busy = true);
    try {
      final dio = ref.read(dioProvider);
      final resp = await dio.post<Map<String, dynamic>>(
        '/learning/tell',
        data: {'text': text},
        options: Options(receiveTimeout: const Duration(seconds: 90)),
      );
      final written = (resp.data?['facts_written'] as num?)?.toInt() ?? 0;
      if (!mounted) return;
      _ctl.clear();
      _showResult(written);
    } on ApiException catch (e) {
      _toast(e.message);
    } on DioException catch (e) {
      _toast('Сеть: ${e.message}');
    } catch (e) {
      _toast('$e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _toast(String m) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));

  void _showResult(int written) {
    showDialog<void>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: MX.bgElevated,
        title: const Text('Запомнил'),
        content: Text(
          written == 0
              ? 'Не нашёл здесь долгоиграющих фактов. Попробуй рассказать о близких, привычках или местах.'
              : 'Добавил в память $written ${_factWord(written)}. Загляни в «Что я о тебе знаю».',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Дальше'),
          ),
          if (written > 0)
            FilledButton(
              onPressed: () {
                Navigator.of(context).pop();
                context.push('/facts');
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
      backgroundColor: MX.bgBase,
      appBar: AppBar(
        backgroundColor: MX.bgBase,
        surfaceTintColor: Colors.transparent,
        title: const Text('Расскажи о себе'),
      ),
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 8),
              child: Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [
                      MX.accentPurple.withAlpha(28),
                      MX.accentAi.withAlpha(20),
                    ],
                  ),
                  borderRadius: BorderRadius.circular(MX.rLg),
                  border: Border.all(color: MX.line),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.psychology_outlined,
                        color: MX.accentPurple, size: 22),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        'Я не сохраню это в Хронику. Я выберу здесь только то, что тебя описывает: близкие, привычки, предпочтения, места.',
                        style: t.textTheme.bodySmall
                            ?.copyWith(color: MX.fg, height: 1.4),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: TextField(
                  controller: _ctl,
                  maxLines: null,
                  expands: true,
                  enabled: !_busy && !_listening,
                  textCapitalization: TextCapitalization.sentences,
                  textAlignVertical: TextAlignVertical.top,
                  style: t.textTheme.bodyLarge,
                  decoration: InputDecoration(
                    hintText:
                        'Например: Мою жену зовут Диана, ей 32, работает в Сбере на Кутузовском. У нас сын Миша, 4 года. Я не ем мясо, бегаю по утрам, по выходным езжу к маме в Истру…',
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
                      borderSide: const BorderSide(color: MX.accentPurple),
                    ),
                    contentPadding: const EdgeInsets.all(16),
                  ),
                ),
              ),
            ),
            if (_listening)
              Padding(
                padding: const EdgeInsets.fromLTRB(24, 12, 24, 0),
                child: Text(
                  _liveText.isEmpty ? 'Слушаю…' : _liveText,
                  textAlign: TextAlign.center,
                  style: t.textTheme.bodyMedium
                      ?.copyWith(color: MX.accentPurple),
                ),
              ),
            const SizedBox(height: 12),
            GestureDetector(
              onLongPressStart: (_) => _start(),
              onLongPressEnd: (_) => _stop(keep: true),
              onLongPressCancel: () => _stop(keep: false),
              onTap: () {
                if (!_listening) {
                  _toast('Зажми и держи микрофон, чтобы говорить.');
                }
              },
              child: AnimatedBuilder(
                animation: _pulse,
                builder: (_, child) {
                  final scale = _listening ? 1 + (_pulse.value * 0.18) : 1.0;
                  return Transform.scale(scale: scale, child: child);
                },
                child: Container(
                  width: 84,
                  height: 84,
                  decoration: BoxDecoration(
                    gradient: _listening
                        ? const LinearGradient(
                            colors: [Color(0xFFFF5C5C), Color(0xFFFF2D55)],
                          )
                        : LinearGradient(
                            colors: [
                              MX.accentPurple,
                              MX.accentAi,
                            ],
                          ),
                    shape: BoxShape.circle,
                    boxShadow: MX.fabGlow,
                  ),
                  child: Icon(
                    _listening ? Icons.stop : Icons.mic,
                    size: 38,
                    color: Colors.white,
                  ),
                ),
              ),
            ),
            const SizedBox(height: 4),
            Text(
              _listening ? 'Слушаю…' : 'Зажми, чтобы говорить',
              style: t.textTheme.bodySmall?.copyWith(color: MX.fgMuted),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 16),
              child: SizedBox(
                width: double.infinity,
                height: 52,
                child: FilledButton(
                  onPressed: (_busy || _listening) ? null : _submit,
                  child: Text(
                    _busy ? 'Запоминаю…' : 'Запомни',
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
    );
  }
}
