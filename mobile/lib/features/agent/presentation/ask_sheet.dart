import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

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
  bool _busy = false;
  AgentAnswer? _answer;
  String? _error;

  @override
  void dispose() {
    _ctl.dispose();
    super.dispose();
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

    return Padding(
      padding: EdgeInsets.only(bottom: mq.viewInsets.bottom),
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
                  autofocus: true,
                  maxLines: 3,
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
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    onPressed: _busy ? null : _ask,
                    icon: _busy
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.send_outlined, size: 18),
                    label: Text(_busy ? 'Думаю…' : 'Спросить'),
                  ),
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
