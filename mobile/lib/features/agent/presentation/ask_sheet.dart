import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/theme/mx_tokens.dart';
import 'package:voicenote_ai/features/agent/data/agent_repository.dart';
import 'package:voicenote_ai/features/auth/application/session_controller.dart';

/// S14 — окно «Спроси меня о чём угодно» (PRODUCT_PLAN.md §2.4 + §6.3).
///
/// Pro-only: для free-юзера показываем paywall-CTA. 402 ответ от бэка
/// тоже трактуется как «нужен Pro» (§5.2).
class AskSheet extends ConsumerStatefulWidget {
  const AskSheet({super.key});

  @override
  ConsumerState<AskSheet> createState() => _AskSheetState();

  /// Удобная точка вызова. Возвращает Future, чтобы вызывающий экран знал
  /// о закрытии.
  static Future<void> show(BuildContext context) =>
      showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        backgroundColor: MX.bgCard,
        useSafeArea: true,
        builder: (_) => const AskSheet(),
      );
}

class _AskSheetState extends ConsumerState<AskSheet> {
  final _ctl = TextEditingController();
  final _stt = stt.SpeechToText();
  bool _busy = false;
  bool _sttReady = false;
  bool _listening = false;
  String _liveText = '';
  AgentAnswer? _answer;
  String? _error;

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
          if (mounted && _listening) setState(() => _listening = false);
        },
      );
      if (mounted) setState(() => _sttReady = ok);
    } catch (_) {}
  }

  @override
  void dispose() {
    _ctl.dispose();
    _stt.cancel();
    super.dispose();
  }

  Future<void> _startListening() async {
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
      listenFor: const Duration(seconds: 60),
      localeId: 'ru_RU',
    );
  }

  /// Released: положить текст в поле и сразу отправить запрос.
  Future<void> _stopAndAsk() async {
    if (!_listening) return;
    HapticFeedback.lightImpact();
    final captured = _liveText.trim();
    try {
      await _stt.stop();
    } catch (_) {}
    if (!mounted) return;
    setState(() {
      _listening = false;
      if (captured.isNotEmpty) {
        final cur = _ctl.text.trim();
        _ctl.text = cur.isEmpty ? captured : '$cur $captured';
      }
      _liveText = '';
    });
    if (_ctl.text.trim().isNotEmpty) {
      await _ask();
    }
  }

  Future<void> _cancelListening() async {
    if (!_listening) return;
    try {
      await _stt.cancel();
    } catch (_) {}
    if (!mounted) return;
    setState(() {
      _listening = false;
      _liveText = '';
    });
  }

  Future<void> _ask() async {
    final q = _ctl.text.trim();
    if (q.isEmpty) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final ans = await ref.read(agentRepositoryProvider).ask(q);
      setState(() => _answer = ans);
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } catch (e) {
      setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final isPro = ref.watch(sessionControllerProvider).user?.isPro ?? false;
    final t = Theme.of(context);
    final mq = MediaQuery.of(context);

    // Снизу либо клавиатура (viewInsets.bottom), либо запас под центральный
    // мик-FAB из AppShell (~80px). Берём максимум, чтобы кнопка «Спросить»
    // не уходила под FAB на Хронике/Сегодня.
    return Padding(
      padding: EdgeInsets.only(bottom: max(mq.viewInsets.bottom, 80)),
      child: ConstrainedBox(
        constraints: BoxConstraints(maxHeight: mq.size.height * 0.85),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(height: 12),
            Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: MX.fgGhost,
                borderRadius: BorderRadius.circular(MX.rFull),
              ),
            ),
            const SizedBox(height: 16),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Row(
                children: [
                  const Icon(Icons.auto_awesome, color: MX.accentAi),
                  const SizedBox(width: 10),
                  Text('Спроси меня', style: t.textTheme.titleLarge),
                ],
              ),
            ),
            const SizedBox(height: 12),
            if (!isPro)
              _ProGate()
            else ...[
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: TextField(
                  controller: _ctl,
                  autofocus: false,
                  maxLines: 3,
                  enabled: !_busy && !_listening,
                  textInputAction: TextInputAction.send,
                  onSubmitted: (_) => _ask(),
                  style: t.textTheme.bodyLarge,
                  decoration: InputDecoration(
                    hintText: 'Что я обещал маме на её ДР?',
                    hintStyle: t.textTheme.bodyMedium?.copyWith(color: MX.fgFaint),
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
                  ),
                ),
              ),
              const SizedBox(height: 12),
              if (_listening)
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20),
                  child: Text(
                    _liveText.isEmpty ? 'Слушаю…' : _liveText,
                    textAlign: TextAlign.center,
                    style: t.textTheme.bodyMedium
                        ?.copyWith(color: MX.accentAi),
                  ),
                ),
              if (_busy)
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20),
                  child: Text(
                    'Думаю…',
                    textAlign: TextAlign.center,
                    style: t.textTheme.bodyMedium?.copyWith(color: MX.fgMuted),
                  ),
                ),
              const SizedBox(height: 8),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Row(
                  children: [
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: (_busy || _listening) ? null : _ask,
                        icon: const Icon(Icons.send_outlined, size: 16),
                        label: const Text('Спросить'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    GestureDetector(
                      onLongPressStart: (_) => _startListening(),
                      onLongPressEnd: (_) => _stopAndAsk(),
                      onLongPressCancel: _cancelListening,
                      onTap: () {
                        if (!_listening) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text('Зажми и держи микрофон.'),
                              duration: Duration(seconds: 2),
                            ),
                          );
                        }
                      },
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 150),
                        width: 56,
                        height: 40,
                        decoration: BoxDecoration(
                          gradient: _listening
                              ? const LinearGradient(
                                  colors: [
                                    Color(0xFFFF5C5C),
                                    Color(0xFFFF2D55)
                                  ],
                                )
                              : MX.brandGradient,
                          borderRadius: BorderRadius.circular(MX.rMd),
                        ),
                        child: Icon(
                          _listening ? Icons.stop : Icons.mic,
                          color: Colors.white,
                          size: 22,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 12),
              if (_error != null)
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20),
                  child: Text(_error!,
                      style: t.textTheme.bodySmall?.copyWith(color: MX.accentSecurity)),
                ),
              if (_answer != null)
                Flexible(
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
                    child: _AnswerCard(answer: _answer!),
                  ),
                ),
              const SizedBox(height: 8),
            ],
          ],
        ),
      ),
    );
  }
}

class _AnswerCard extends StatelessWidget {
  const _AnswerCard({required this.answer});
  final AgentAnswer answer;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: MX.accentAiSoft,
        borderRadius: BorderRadius.circular(MX.rMd),
        border: Border.all(color: MX.accentAiLine),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(answer.answer, style: t.textTheme.bodyLarge),
          if (answer.cited.isNotEmpty) ...[
            const SizedBox(height: 16),
            Text('Опираюсь на:',
                style: t.textTheme.bodySmall?.copyWith(color: MX.fgMuted)),
            const SizedBox(height: 8),
            for (final c in answer.cited) ...[
              _CitationTile(cite: c),
              const SizedBox(height: 6),
            ],
          ],
        ],
      ),
    );
  }
}

class _CitationTile extends StatelessWidget {
  const _CitationTile({required this.cite});
  final CitedMoment cite;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Material(
      color: MX.surfaceOverlay,
      borderRadius: BorderRadius.circular(MX.rSm),
      child: InkWell(
        borderRadius: BorderRadius.circular(MX.rSm),
        onTap: () {
          Navigator.pop(context);
          context.push('/moment/${cite.id}');
        },
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(MX.rSm),
            border: Border.all(color: MX.line),
          ),
          child: Row(
            children: [
              Text('#${cite.id}',
                  style: t.textTheme.labelSmall?.copyWith(color: MX.accentAi)),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  cite.title.isEmpty ? cite.snippet : cite.title,
                  style: t.textTheme.bodyMedium,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              const Icon(Icons.chevron_right, size: 16, color: MX.fgFaint),
            ],
          ),
        ),
      ),
    );
  }
}

class _ProGate extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Помню всё, что ты мне рассказал. Отвечаю по делу.',
            style: t.textTheme.bodyLarge,
          ),
          const SizedBox(height: 8),
          Text(
            'Это Pro-функция. Открой подписку — и спрашивай о любом своём моменте.',
            style: t.textTheme.bodyMedium?.copyWith(color: MX.fgMuted),
          ),
          const SizedBox(height: 20),
          SizedBox(
            width: double.infinity,
            child: FilledButton(
              onPressed: () {
                Navigator.pop(context);
                context.push('/paywall');
              },
              child: const Padding(
                padding: EdgeInsets.symmetric(vertical: 12),
                child: Text('Открыть Pro',
                    style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
