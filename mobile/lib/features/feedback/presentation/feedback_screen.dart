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
        title: Text(_sent ? '' : 'Помоги стать лучше'),
        leading: IconButton(
          icon: const Icon(LucideIcons.x),
          onPressed: () => context.pop(),
        ),
        backgroundColor: MX.bgBase,
        elevation: 0,
        scrolledUnderElevation: 0,
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
      child: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              // Большое сердце с glow
              Container(
                width: 96,
                height: 96,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: const RadialGradient(
                    center: Alignment(-0.2, -0.3),
                    radius: 0.95,
                    colors: [
                      Color(0xFFFF6B9D),
                      Color(0xFFFF2D55),
                    ],
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: const Color(0xFFFF2D55).withAlpha(120),
                      blurRadius: 40,
                      spreadRadius: 4,
                    ),
                  ],
                ),
                child: const Icon(LucideIcons.heart,
                    color: Colors.white, size: 44),
              ),
              const SizedBox(height: 28),
              Text(
                'Спасибо.',
                textAlign: TextAlign.center,
                style: t.textTheme.headlineMedium?.copyWith(
                  color: MX.fg,
                  fontWeight: FontWeight.w600,
                  letterSpacing: -0.4,
                ),
              ),
              const SizedBox(height: 10),
              Text(
                'Я прочитаю это сегодня вечером.\nНа важные вещи — отвечу.',
                textAlign: TextAlign.center,
                style: t.textTheme.bodyMedium?.copyWith(
                  color: MX.fgMuted,
                  height: 1.5,
                ),
              ),
              const SizedBox(height: 32),
              SizedBox(
                width: 220,
                height: 48,
                child: FilledButton(
                  onPressed: () => context.pop(),
                  child: const Text(
                    'Закрыть',
                    style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
                  ),
                ),
              ),
            ],
          ),
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
