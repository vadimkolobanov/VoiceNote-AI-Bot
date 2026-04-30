import 'dart:async';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons/lucide_icons.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/theme/mx_tokens.dart';
import 'package:voicenote_ai/features/agent/data/agent_repository.dart';
import 'package:voicenote_ai/features/auth/application/session_controller.dart';
import 'package:voicenote_ai/features/voice_capture/data/voice_recorder.dart';

/// S14 — окно «Спроси меня о чём угодно» (PRODUCT_PLAN.md §2.4 + §6.3).
///
/// Pro-only: для free-юзера показываем paywall-CTA. 402 ответ от бэка
/// тоже трактуется как «нужен Pro» (§5.2).
///
/// Голос: запись через `record` + аплоад в `/voice/recognize` (Yandex STT).
/// Никаких системных пиков от платформенного SpeechRecognizer.
class AskSheet extends ConsumerStatefulWidget {
  const AskSheet({super.key});

  @override
  ConsumerState<AskSheet> createState() => _AskSheetState();

  /// Удобная точка вызова. `useRootNavigator: true`, чтобы модалка
  /// перекрывала нижний центральный mic-FAB AppShell.
  static Future<void> show(BuildContext context) =>
      showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        useRootNavigator: true,
        useSafeArea: true,
        backgroundColor: MX.bgCard,
        builder: (_) => const AskSheet(),
      );
}

enum _Phase { idle, recording, transcribing, asking }

class _AskSheetState extends ConsumerState<AskSheet>
    with TickerProviderStateMixin {
  final _ctl = TextEditingController();

  late final AnimationController _breath = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 2400),
  )..repeat(reverse: true);

  _Phase _phase = _Phase.idle;
  double _amp = 0.0;
  StreamSubscription<double>? _ampSub;

  AgentAnswer? _answer;
  String? _error;

  @override
  void dispose() {
    _ctl.dispose();
    _breath.dispose();
    _ampSub?.cancel();
    // Если пользователь закрыл шит во время записи — отменим запись.
    if (_phase == _Phase.recording) {
      // ignore: discarded_futures
      ref.read(voiceRecorderProvider).cancel();
    }
    super.dispose();
  }

  bool get _busy =>
      _phase == _Phase.recording ||
      _phase == _Phase.transcribing ||
      _phase == _Phase.asking;

  Future<void> _toggleListening() async {
    if (_phase == _Phase.transcribing || _phase == _Phase.asking) return;
    HapticFeedback.lightImpact();
    if (_phase == _Phase.recording) {
      await _stopAndAsk();
      return;
    }
    final recorder = ref.read(voiceRecorderProvider);
    final ok = await recorder.start();
    if (!ok) {
      _toast('Нужен доступ к микрофону.');
      return;
    }
    if (!mounted) return;
    setState(() {
      _phase = _Phase.recording;
      _error = null;
      _answer = null;
    });
    _ampSub = recorder.amplitudeStream.listen((a) {
      if (!mounted) return;
      setState(() => _amp = a);
    });
  }

  /// Стоп записи → распознавание → подставить текст и сразу спросить.
  Future<void> _stopAndAsk() async {
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
    String captured = '';
    try {
      final r = await recorder.recognize(path);
      captured = r.text.trim();
    } on ApiException catch (e) {
      _toast(e.message);
    } catch (_) {
      _toast('Не удалось распознать. Попробуй ещё раз.');
    }
    if (!mounted) return;
    if (captured.isNotEmpty) {
      final cur = _ctl.text.trim();
      _ctl.text = cur.isEmpty ? captured : '$cur $captured';
    }
    setState(() => _phase = _Phase.idle);
    if (_ctl.text.trim().isNotEmpty) {
      await _ask();
    }
  }

  Future<void> _ask() async {
    final q = _ctl.text.trim();
    if (q.isEmpty) return;
    setState(() {
      _phase = _Phase.asking;
      _error = null;
    });
    try {
      final ans = await ref.read(agentRepositoryProvider).ask(q);
      if (!mounted) return;
      setState(() => _answer = ans);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _phase = _Phase.idle);
    }
  }

  void _toast(String m) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));

  @override
  Widget build(BuildContext context) {
    final isPro = ref.watch(sessionControllerProvider).user?.isPro ?? false;
    final t = Theme.of(context);
    final mq = MediaQuery.of(context);

    // Низ экрана: либо клавиатура, либо системная навигация (жесты/кнопки).
    // useSafeArea на модалке не всегда учитывает gesture-bar Xiaomi/MIUI,
    // поэтому добавляем viewPadding.bottom вручную.
    final bottomPad = mq.viewInsets.bottom > 0
        ? mq.viewInsets.bottom
        : mq.viewPadding.bottom + 12;
    return Padding(
      padding: EdgeInsets.only(bottom: bottomPad),
      child: ConstrainedBox(
        constraints: BoxConstraints(maxHeight: mq.size.height * 0.88),
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
                  enabled: !_busy,
                  textInputAction: TextInputAction.send,
                  onSubmitted: (_) => _ask(),
                  style: t.textTheme.bodyLarge,
                  decoration: InputDecoration(
                    hintText: 'Что я обещал маме на её ДР?',
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
                  ),
                ),
              ),
              const SizedBox(height: 14),
              Center(
                child: Column(
                  children: [
                    AnimatedBuilder(
                      animation: _breath,
                      builder: (_, __) {
                        final breathScale =
                            1 + (_breath.value - 0.5) * 0.04;
                        final ampScale = (_phase == _Phase.recording)
                            ? _amp * 0.36
                            : 0.0;
                        return GestureDetector(
                          onTap: _phase == _Phase.asking ? null : _toggleListening,
                          child: _Orb(
                            scale: breathScale + ampScale,
                            phase: _phase,
                          ),
                        );
                      },
                    ),
                    const SizedBox(height: 8),
                    Text(
                      _hint(),
                      textAlign: TextAlign.center,
                      style: t.textTheme.bodySmall
                          ?.copyWith(color: MX.fgMicro),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 12),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: SizedBox(
                  width: double.infinity,
                  height: 44,
                  child: FilledButton.icon(
                    onPressed: _busy || _ctl.text.trim().isEmpty ? null : _ask,
                    icon: _phase == _Phase.asking
                        ? const SizedBox(
                            width: 14,
                            height: 14,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Icon(Icons.send_outlined, size: 16),
                    label: Text(_phase == _Phase.asking
                        ? 'Думаю…'
                        : 'Спросить'),
                  ),
                ),
              ),
              const SizedBox(height: 12),
              if (_error != null)
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20),
                  child: Text(
                    _error!,
                    style: t.textTheme.bodySmall
                        ?.copyWith(color: MX.accentSecurity),
                  ),
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

  String _hint() {
    switch (_phase) {
      case _Phase.idle:
        return _ctl.text.trim().isEmpty
            ? 'Тап по орбу — задай вопрос голосом'
            : 'Тап по орбу — добавить ещё голосом';
      case _Phase.recording:
        return 'Слушаю… тап — стоп и спросить';
      case _Phase.transcribing:
        return 'Распознаю…';
      case _Phase.asking:
        return 'Думаю…';
    }
  }
}

// ---------------------------------------------------------------------------

class _Orb extends StatelessWidget {
  const _Orb({required this.scale, required this.phase});

  final double scale;
  final _Phase phase;

  @override
  Widget build(BuildContext context) {
    const baseSize = 76.0;
    final active = phase != _Phase.idle;
    const core = MX.accentAi;
    final halo = active ? const Color(0xFF7C3AED) : const Color(0xFF4F46E5);
    return SizedBox(
      width: 140,
      height: 140,
      child: Stack(
        alignment: Alignment.center,
        children: [
          if (active)
            Transform.scale(
              scale: scale * 1.5,
              child: ImageFiltered(
                imageFilter: ui.ImageFilter.blur(sigmaX: 22, sigmaY: 22),
                child: Container(
                  width: baseSize,
                  height: baseSize,
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
              width: baseSize,
              height: baseSize,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: RadialGradient(
                  center: const Alignment(-0.2, -0.3),
                  radius: 0.95,
                  colors: [
                    core.withAlpha(active ? 240 : 220),
                    core.withAlpha(170),
                    halo.withAlpha(70),
                  ],
                ),
                boxShadow: [
                  BoxShadow(
                    color: core.withAlpha(active ? 130 : 90),
                    blurRadius: 28,
                    spreadRadius: 2,
                  ),
                ],
              ),
              child: Center(
                child: phase == _Phase.transcribing ||
                        phase == _Phase.asking
                    ? const SizedBox(
                        width: 22,
                        height: 22,
                        child: CircularProgressIndicator(
                          strokeWidth: 2.4,
                          color: Colors.white,
                        ),
                      )
                    : Icon(
                        phase == _Phase.recording
                            ? LucideIcons.mic
                            : LucideIcons.sparkles,
                        color: Colors.white,
                        size: 22,
                      ),
              ),
            ),
          ),
        ],
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
