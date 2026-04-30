import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons/lucide_icons.dart';

import 'package:voicenote_ai/core/router/app_routes.dart';
import 'package:voicenote_ai/core/theme/mx_tokens.dart';
import 'package:voicenote_ai/features/onboarding/data/onboarding_flag.dart';

/// Онбоардинг — три коротких слайда.
///
/// Идея: не учим UI («тыкни сюда → потом сюда»), а объясняем три способа
/// разговаривать с приложением через живые примеры. Скип доступен сразу,
/// «Назад» появляется со второго слайда. Финальная кнопка кладёт seen-флаг
/// и уносит на /today.
class OnboardingScreen extends ConsumerStatefulWidget {
  const OnboardingScreen({super.key});

  @override
  ConsumerState<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends ConsumerState<OnboardingScreen> {
  final _pageCtl = PageController();
  int _page = 0;

  @override
  void dispose() {
    _pageCtl.dispose();
    super.dispose();
  }

  Future<void> _finish() async {
    HapticFeedback.lightImpact();
    await ref.read(onboardingSeenProvider.notifier).markSeen();
    if (!mounted) return;
    context.go(AppRoutes.today);
  }

  void _next() {
    if (_page >= 2) {
      _finish();
      return;
    }
    HapticFeedback.selectionClick();
    _pageCtl.nextPage(
      duration: const Duration(milliseconds: 280),
      curve: Curves.easeOutCubic,
    );
  }

  void _back() {
    if (_page == 0) return;
    _pageCtl.previousPage(
      duration: const Duration(milliseconds: 220),
      curve: Curves.easeOut,
    );
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Scaffold(
      backgroundColor: const Color(0xFF050507),
      body: SafeArea(
        child: Column(
          children: [
            // Top bar: back + skip
            Padding(
              padding: const EdgeInsets.fromLTRB(8, 8, 8, 0),
              child: Row(
                children: [
                  AnimatedOpacity(
                    duration: const Duration(milliseconds: 180),
                    opacity: _page == 0 ? 0 : 1,
                    child: IconButton(
                      icon: const Icon(LucideIcons.chevronLeft,
                          color: MX.fgMuted, size: 22),
                      onPressed: _page == 0 ? null : _back,
                    ),
                  ),
                  const Spacer(),
                  TextButton(
                    onPressed: _finish,
                    child: Text(
                      'Пропустить',
                      style: t.textTheme.bodyMedium?.copyWith(
                        color: MX.fgMuted,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                ],
              ),
            ),

            Expanded(
              child: PageView(
                controller: _pageCtl,
                onPageChanged: (i) => setState(() => _page = i),
                children: const [
                  _SlideCapture(),
                  _SlideLearn(),
                  _SlideAsk(),
                ],
              ),
            ),

            // Dots
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: List.generate(3, (i) {
                  final active = i == _page;
                  return AnimatedContainer(
                    duration: const Duration(milliseconds: 200),
                    margin: const EdgeInsets.symmetric(horizontal: 4),
                    width: active ? 22 : 6,
                    height: 6,
                    decoration: BoxDecoration(
                      color: active ? MX.accentAi : MX.fgGhost,
                      borderRadius: BorderRadius.circular(MX.rFull),
                    ),
                  );
                }),
              ),
            ),

            Padding(
              padding: const EdgeInsets.fromLTRB(20, 0, 20, 18),
              child: SizedBox(
                width: double.infinity,
                height: 52,
                child: FilledButton(
                  style: FilledButton.styleFrom(
                    backgroundColor: MX.accentAi,
                    foregroundColor: Colors.black,
                  ),
                  onPressed: _next,
                  child: Text(
                    _page == 2 ? 'Поехали' : 'Дальше',
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

// ---------------------------------------------------------------------------
// Slide 1: voice capture
// ---------------------------------------------------------------------------

class _SlideCapture extends StatelessWidget {
  const _SlideCapture();

  @override
  Widget build(BuildContext context) {
    return _SlideLayout(
      orb: const _Orb(
        icon: LucideIcons.mic,
        core: MX.accentAi,
        halo: Color(0xFF7C3AED),
      ),
      title: 'Говори как думаешь',
      subtitle:
          'Жми микрофон внизу и расскажи как другу. Я разберу даты, людей и повторения.',
      examples: [
        '«Напомни в среду в 19 забрать машину из сервиса»',
        '«Через час позвонить маме»',
        '«Каждый понедельник тренировка в 8 утра»',
      ],
      footer:
          'Не пиши формально. Чем естественнее, тем лучше я пойму.',
    );
  }
}

// ---------------------------------------------------------------------------
// Slide 2: learning (memory)
// ---------------------------------------------------------------------------

class _SlideLearn extends StatelessWidget {
  const _SlideLearn();

  @override
  Widget build(BuildContext context) {
    return _SlideLayout(
      orb: const _Orb(
        icon: LucideIcons.brain,
        core: Color(0xFFA78BFA),
        halo: Color(0xFF7C3AED),
      ),
      title: 'Я буду помнить тебя',
      subtitle:
          'Расскажи мне о своей жизни — людях, работе, привычках, мечтах. Это не задачи и не напоминания. Это контекст, который делает меня твоим, а не очередным приложением.',
      examples: [
        '«Меня зовут Вадим, жена Диана работает в Сбере, сыну Мише 4 года»',
        '«Я разработчик, по утрам бегаю, кофе без сахара»',
        '«Веду проект Methodex, цель — выйти на 1000 пользователей к лету»',
      ],
      footer:
          'Чем больше ты делишься — тем лучше я понимаю. Через пару месяцев я буду знать тебя так, что станет сложно без меня.',
    );
  }
}

// ---------------------------------------------------------------------------
// Slide 3: ask
// ---------------------------------------------------------------------------

class _SlideAsk extends StatelessWidget {
  const _SlideAsk();

  @override
  Widget build(BuildContext context) {
    return _SlideLayout(
      orb: const _Orb(
        icon: LucideIcons.sparkles,
        core: MX.accentAi,
        halo: Color(0xFF4F46E5),
      ),
      title: 'Спрашивай о себе',
      subtitle:
          'Вверху на «Сегодня» есть кнопка «Спроси меня». Задавай вопросы голосом или текстом — я ищу по твоим моментам и фактам.',
      examples: [
        '«Когда у мамы день рождения?»',
        '«Что я обещал жене на выходные?»',
        '«О чём я договорился с боссом на той неделе?»',
      ],
      footer:
          'Чем больше я о тебе знаю, тем точнее отвечаю. Подсказки накапливаются молча.',
    );
  }
}

// ---------------------------------------------------------------------------
// Shared layout
// ---------------------------------------------------------------------------

class _SlideLayout extends StatelessWidget {
  const _SlideLayout({
    required this.orb,
    required this.title,
    required this.subtitle,
    required this.examples,
    required this.footer,
  });

  final Widget orb;
  final String title;
  final String subtitle;
  final List<String> examples;
  final String footer;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(24, 8, 24, 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 8),
          Center(child: orb),
          const SizedBox(height: 24),
          Text(
            title,
            textAlign: TextAlign.center,
            style: t.textTheme.headlineMedium?.copyWith(
              color: MX.fg,
              fontWeight: FontWeight.w700,
              letterSpacing: -0.4,
            ),
          ),
          const SizedBox(height: 12),
          Text(
            subtitle,
            textAlign: TextAlign.center,
            style: t.textTheme.bodyLarge?.copyWith(
              color: MX.fgMuted,
              height: 1.5,
            ),
          ),
          const SizedBox(height: 20),
          for (final e in examples) ...[
            _ExampleChip(text: e),
            const SizedBox(height: 8),
          ],
          const SizedBox(height: 12),
          Text(
            footer,
            textAlign: TextAlign.center,
            style: t.textTheme.bodySmall?.copyWith(
              color: MX.fgFaint,
              height: 1.5,
            ),
          ),
        ],
      ),
    );
  }
}

class _ExampleChip extends StatelessWidget {
  const _ExampleChip({required this.text});
  final String text;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: MX.surfaceOverlay,
        borderRadius: BorderRadius.circular(MX.rMd),
        border: Border.all(color: MX.line),
      ),
      child: Row(
        children: [
          const Icon(LucideIcons.quote, size: 14, color: MX.accentAi),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              text,
              style: t.textTheme.bodyMedium?.copyWith(
                color: MX.fg,
                height: 1.4,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _Orb extends StatefulWidget {
  const _Orb({
    required this.icon,
    required this.core,
    required this.halo,
  });

  final IconData icon;
  final Color core;
  final Color halo;

  @override
  State<_Orb> createState() => _OrbState();
}

class _OrbState extends State<_Orb> with SingleTickerProviderStateMixin {
  late final AnimationController _breath = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 2400),
  )..repeat(reverse: true);

  @override
  void dispose() {
    _breath.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    const baseSize = 96.0;
    return SizedBox(
      width: 180,
      height: 180,
      child: AnimatedBuilder(
        animation: _breath,
        builder: (_, __) {
          final scale = 1 + (_breath.value - 0.5) * 0.06;
          return Stack(
            alignment: Alignment.center,
            children: [
              Transform.scale(
                scale: scale * 1.5,
                child: ImageFiltered(
                  imageFilter: ui.ImageFilter.blur(sigmaX: 28, sigmaY: 28),
                  child: Container(
                    width: baseSize,
                    height: baseSize,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: widget.halo.withAlpha(110),
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
                        widget.core.withAlpha(235),
                        widget.core.withAlpha(170),
                        widget.halo.withAlpha(70),
                      ],
                    ),
                    boxShadow: [
                      BoxShadow(
                        color: widget.core.withAlpha(120),
                        blurRadius: 32,
                        spreadRadius: 3,
                      ),
                    ],
                  ),
                  child: Icon(widget.icon, color: Colors.white, size: 30),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}
