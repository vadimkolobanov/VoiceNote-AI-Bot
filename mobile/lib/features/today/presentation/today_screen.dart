import 'package:flutter/material.dart';

import 'package:voicenote_ai/core/theme/mx_tokens.dart';

/// S6 — Сегодня (PRODUCT_PLAN.md §2.3). Заглушка до M5; реальный фид моментов
/// подключается в M5 через `momentsTodayProvider`.
class TodayScreen extends StatelessWidget {
  const TodayScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return CustomScrollView(
      slivers: [
        SliverAppBar(
          floating: true,
          backgroundColor: MX.bgBase,
          surfaceTintColor: Colors.transparent,
          title: Text('Сегодня', style: t.textTheme.titleLarge),
        ),
        const SliverPadding(
          padding: EdgeInsets.fromLTRB(20, 8, 20, 120),
          sliver: SliverToBoxAdapter(child: _EmptyHero()),
        ),
      ],
    );
  }
}

class _EmptyHero extends StatelessWidget {
  const _EmptyHero();

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: MX.surfaceOverlay,
        borderRadius: BorderRadius.circular(MX.rLg),
        border: Border.all(color: MX.line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Доброе.', style: t.textTheme.headlineSmall),
          const SizedBox(height: 8),
          Text(
            'Сегодня никаких дел. Запиши что-нибудь новое — я запомню.',
            style: t.textTheme.bodyLarge?.copyWith(color: MX.fgMuted),
          ),
          const SizedBox(height: 24),
          Row(
            children: [
              const Icon(Icons.south, color: MX.accentAi),
              const SizedBox(width: 8),
              Text(
                'Тапни микрофон',
                style: t.textTheme.bodyMedium?.copyWith(color: MX.accentAi),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
