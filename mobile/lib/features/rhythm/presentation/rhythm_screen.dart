import 'package:flutter/material.dart';

import 'package:voicenote_ai/core/theme/mx_tokens.dart';

/// S8 — Ритм (PRODUCT_PLAN.md §2.5). Заглушка до M6.
class RhythmScreen extends StatelessWidget {
  const RhythmScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return CustomScrollView(
      slivers: [
        SliverAppBar(
          floating: true,
          backgroundColor: MX.bgBase,
          surfaceTintColor: Colors.transparent,
          title: Text('Ритм', style: t.textTheme.titleLarge),
        ),
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 120),
          sliver: SliverList(
            delegate: SliverChildListDelegate.fixed([
              _SectionHeader(title: 'Привычки', subtitle: 'Серии и heatmap'),
              const SizedBox(height: 12),
              const _PlaceholderCard(text: 'Пока ничего регулярного. Скажи: «каждое утро бегать 10 минут».'),
              const SizedBox(height: 24),
              _SectionHeader(title: 'Циклы', subtitle: 'ДР, зарплаты, повторяющиеся встречи'),
              const SizedBox(height: 12),
              const _PlaceholderCard(text: 'Циклы появятся, когда ты расскажешь о повторах.'),
            ]),
          ),
        ),
      ],
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.title, required this.subtitle});
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: t.textTheme.titleMedium),
        const SizedBox(height: 2),
        Text(subtitle, style: t.textTheme.bodySmall?.copyWith(color: MX.fgMuted)),
      ],
    );
  }
}

class _PlaceholderCard extends StatelessWidget {
  const _PlaceholderCard({required this.text});
  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: MX.surfaceOverlay,
        borderRadius: BorderRadius.circular(MX.rMd),
        border: Border.all(color: MX.line),
      ),
      child: Text(
        text,
        style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: MX.fgMuted),
      ),
    );
  }
}
