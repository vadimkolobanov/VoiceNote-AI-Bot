import 'package:flutter/material.dart';

import 'package:voicenote_ai/core/theme/mx_tokens.dart';

/// S7 — Хроника (PRODUCT_PLAN.md §2.4). Заглушка до M5.
class TimelineScreen extends StatelessWidget {
  const TimelineScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return CustomScrollView(
      slivers: [
        SliverAppBar(
          floating: true,
          backgroundColor: MX.bgBase,
          surfaceTintColor: Colors.transparent,
          title: Text('Хроника', style: t.textTheme.titleLarge),
        ),
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(20, 0, 20, 16),
          sliver: SliverToBoxAdapter(
            child: Container(
              decoration: BoxDecoration(
                color: MX.surfaceOverlay,
                borderRadius: BorderRadius.circular(MX.rFull),
                border: Border.all(color: MX.line),
              ),
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              child: Row(
                children: [
                  const Icon(Icons.search, color: MX.fgMuted, size: 20),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      'Спроси меня о чём угодно…',
                      style: t.textTheme.bodyMedium?.copyWith(color: MX.fgMuted),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 120),
          sliver: SliverToBoxAdapter(
            child: Center(
              child: Text(
                'Здесь будут все моменты, от новых к старым',
                style: t.textTheme.bodyMedium?.copyWith(color: MX.fgFaint),
              ),
            ),
          ),
        ),
      ],
    );
  }
}
