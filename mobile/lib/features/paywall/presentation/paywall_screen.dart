import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'package:voicenote_ai/core/theme/mx_tokens.dart';

/// S12 — Paywall (PRODUCT_PLAN.md §8). Stub до M7: показывает планы и CTA,
/// но фактический YooKassa-flow подключим в M7 (`POST /billing/subscribe`
/// → confirmation_url → WebView).
class PaywallScreen extends StatelessWidget {
  const PaywallScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Scaffold(
      backgroundColor: MX.bgBase,
      appBar: AppBar(
        backgroundColor: MX.bgBase,
        surfaceTintColor: Colors.transparent,
        title: const Text('Pro'),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () => context.pop(),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
        children: [
          Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [MX.accentAi, MX.accentPurple],
              ),
              borderRadius: BorderRadius.circular(MX.rLg),
              boxShadow: MX.fabGlow,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Pro',
                    style: t.textTheme.displaySmall?.copyWith(color: Colors.white)),
                const SizedBox(height: 8),
                Text(
                  'Я начинаю помнить тебя — а не просто записывать.',
                  style: t.textTheme.bodyLarge?.copyWith(color: Colors.white),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),
          const _Bullet(text: 'Память глубже 30 дней'),
          const _Bullet(text: 'Вопросы к ИИ по твоим записям'),
          const _Bullet(text: '«Что я о тебе знаю» — портрет из фактов'),
          const _Bullet(text: 'Проактивные подсказки'),
          const _Bullet(text: 'Расширенные лимиты голоса'),
          const SizedBox(height: 28),

          _PlanCard(
            badge: 'Месячный',
            price: '400 ₽',
            period: 'в месяц',
            highlight: false,
            onTap: () => _todo(context),
          ),
          const SizedBox(height: 12),
          _PlanCard(
            badge: 'Годовой',
            price: '3 490 ₽',
            period: 'в год · ~291 ₽/мес',
            highlight: true,
            saveLabel: 'выгоднее на 27%',
            onTap: () => _todo(context),
          ),
          const SizedBox(height: 16),
          Center(
            child: Text(
              'Можно отменить в любой момент.',
              style: t.textTheme.bodySmall?.copyWith(color: MX.fgFaint),
            ),
          ),
        ],
      ),
    );
  }

  void _todo(BuildContext context) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Оплата подключим в M7 — пока готовим юрлицо и YooKassa.'),
      ),
    );
  }
}

class _Bullet extends StatelessWidget {
  const _Bullet({required this.text});
  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 24,
            height: 24,
            decoration: BoxDecoration(
              color: MX.accentAiSoft,
              borderRadius: BorderRadius.circular(MX.rXs),
            ),
            child: const Icon(Icons.check, color: MX.accentAi, size: 16),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(text, style: Theme.of(context).textTheme.bodyMedium),
          ),
        ],
      ),
    );
  }
}

class _PlanCard extends StatelessWidget {
  const _PlanCard({
    required this.badge,
    required this.price,
    required this.period,
    required this.highlight,
    required this.onTap,
    this.saveLabel,
  });

  final String badge;
  final String price;
  final String period;
  final bool highlight;
  final VoidCallback onTap;
  final String? saveLabel;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final borderColor = highlight ? MX.accentAi : MX.lineStrong;
    return Material(
      color: highlight ? MX.accentAiSoft : MX.surfaceOverlay,
      borderRadius: BorderRadius.circular(MX.rLg),
      child: InkWell(
        borderRadius: BorderRadius.circular(MX.rLg),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(MX.rLg),
            border: Border.all(color: borderColor, width: highlight ? 1.5 : 1),
          ),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(badge, style: t.textTheme.titleMedium),
                        if (saveLabel != null) ...[
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 8, vertical: 2),
                            decoration: BoxDecoration(
                              color: MX.accentAi,
                              borderRadius: BorderRadius.circular(MX.rFull),
                            ),
                            child: Text(
                              saveLabel!,
                              style: const TextStyle(
                                  color: MX.bgBase,
                                  fontSize: 11,
                                  fontWeight: FontWeight.w700),
                            ),
                          ),
                        ],
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(period,
                        style:
                            t.textTheme.bodySmall?.copyWith(color: MX.fgMuted)),
                  ],
                ),
              ),
              Text(price,
                  style: t.textTheme.titleLarge
                      ?.copyWith(fontWeight: FontWeight.w700)),
            ],
          ),
        ),
      ),
    );
  }
}
