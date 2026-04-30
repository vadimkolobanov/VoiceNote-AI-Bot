import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons/lucide_icons.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/theme/mx_tokens.dart';
import 'package:voicenote_ai/features/feedback/data/feedback_repository.dart';

class FeedbackScreen extends ConsumerStatefulWidget {
  const FeedbackScreen({super.key});

  @override
  ConsumerState<FeedbackScreen> createState() => _FeedbackScreenState();
}

class _FeedbackScreenState extends ConsumerState<FeedbackScreen> {
  String? _sentiment;
  final _ctl = TextEditingController();
  bool _busy = false;
  bool _sent = false;

  @override
  void dispose() {
    _ctl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final body = _ctl.text.trim();
    if (_sentiment == null) {
      _toast('Выбери эмоцию.');
      return;
    }
    if (body.length < 3) {
      _toast('Напиши хотя бы пару слов.');
      return;
    }
    setState(() => _busy = true);
    try {
      await ref.read(feedbackRepositoryProvider).submit(
            sentiment: _sentiment!,
            body: body,
          );
      HapticFeedback.lightImpact();
      if (!mounted) return;
      setState(() => _sent = true);
    } on ApiException catch (e) {
      _toast(e.message);
    } catch (e) {
      _toast('$e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _toast(String m) => ScaffoldMessenger.of(context)
      .showSnackBar(SnackBar(content: Text(m)));

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Помоги стать лучше'),
        leading: IconButton(
          icon: const Icon(LucideIcons.x),
          onPressed: () => context.pop(),
        ),
      ),
      body: _sent ? _buildThanks(t) : _buildForm(t),
    );
  }

  Widget _buildForm(ThemeData t) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 4, 20, 20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Что не так? Что классно? Чего не хватает?',
              style: t.textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            Text(
              'Я читаю каждое сообщение лично. Отвечаю если оставил email.',
              style: t.textTheme.bodyMedium?.copyWith(color: MX.fgMuted),
            ),
            const SizedBox(height: 24),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                _Emoji(
                  emoji: '😊',
                  label: 'Нравится',
                  selected: _sentiment == 'positive',
                  onTap: () => setState(() => _sentiment = 'positive'),
                  color: const Color(0xFF34D399),
                ),
                _Emoji(
                  emoji: '😐',
                  label: 'Нормально',
                  selected: _sentiment == 'neutral',
                  onTap: () => setState(() => _sentiment = 'neutral'),
                  color: const Color(0xFFFBBF24),
                ),
                _Emoji(
                  emoji: '😞',
                  label: 'Бесит',
                  selected: _sentiment == 'negative',
                  onTap: () => setState(() => _sentiment = 'negative'),
                  color: const Color(0xFFFF6B6B),
                ),
              ],
            ),
            const SizedBox(height: 24),
            Expanded(
              child: TextField(
                controller: _ctl,
                maxLines: null,
                expands: true,
                enabled: !_busy,
                textCapitalization: TextCapitalization.sentences,
                textAlignVertical: TextAlignVertical.top,
                style: t.textTheme.bodyLarge,
                decoration: InputDecoration(
                  hintText:
                      'Например: «зарядку отметил, а на завтра не появилась» или «хочу импорт чата с женой»',
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
                  contentPadding: const EdgeInsets.all(16),
                ),
              ),
            ),
            const SizedBox(height: 16),
            SizedBox(
              height: 52,
              child: FilledButton(
                onPressed: _busy ? null : _submit,
                child: Text(
                  _busy ? 'Отправляю…' : 'Отправить',
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ),
            const SizedBox(height: 8),
            Center(
              child: Text(
                'Или напиши на mayardolva6@gmail.com',
                style: t.textTheme.bodySmall?.copyWith(color: MX.fgMicro),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildThanks(ThemeData t) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 84,
              height: 84,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: MX.brandGradient,
                boxShadow: MX.fabGlow,
              ),
              child: const Icon(LucideIcons.heart,
                  color: Colors.white, size: 36),
            ),
            const SizedBox(height: 24),
            Text(
              'Спасибо.',
              style: t.textTheme.headlineMedium,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            Text(
              'Я прочитаю это сегодня вечером.\nНа важные вещи — отвечу.',
              textAlign: TextAlign.center,
              style: t.textTheme.bodyMedium?.copyWith(color: MX.fgMuted),
            ),
            const SizedBox(height: 32),
            FilledButton(
              onPressed: () => context.pop(),
              child: const Padding(
                padding: EdgeInsets.symmetric(horizontal: 24, vertical: 4),
                child: Text('Закрыть'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Emoji extends StatelessWidget {
  const _Emoji({
    required this.emoji,
    required this.label,
    required this.selected,
    required this.onTap,
    required this.color,
  });
  final String emoji;
  final String label;
  final bool selected;
  final VoidCallback onTap;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(MX.rLg),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        width: 92,
        padding: const EdgeInsets.symmetric(vertical: 14),
        decoration: BoxDecoration(
          color: selected ? color.withAlpha(28) : MX.surfaceOverlay,
          borderRadius: BorderRadius.circular(MX.rLg),
          border: Border.all(
            color: selected ? color.withAlpha(120) : MX.line,
            width: selected ? 1.5 : 1,
          ),
        ),
        child: Column(
          children: [
            Text(emoji, style: const TextStyle(fontSize: 32)),
            const SizedBox(height: 6),
            Text(
              label,
              style: t.textTheme.labelSmall?.copyWith(
                color: selected ? color : MX.fgMuted,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
