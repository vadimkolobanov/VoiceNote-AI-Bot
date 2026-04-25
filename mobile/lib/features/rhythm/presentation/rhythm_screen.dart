import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:voicenote_ai/core/theme/mx_tokens.dart';
import 'package:voicenote_ai/features/moments/application/moments_providers.dart';
import 'package:voicenote_ai/features/moments/data/models/moment.dart';

/// S8 — Ритм (PRODUCT_PLAN.md §2.5). Habits + cycles.
class RhythmScreen extends ConsumerWidget {
  const RhythmScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final rhythm = ref.watch(rhythmProvider);
    final t = Theme.of(context);

    return RefreshIndicator(
      color: MX.accentAi,
      onRefresh: () async => ref.invalidate(rhythmProvider),
      child: CustomScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        slivers: [
          SliverAppBar(
            floating: true,
            backgroundColor: MX.bgBase,
            surfaceTintColor: Colors.transparent,
            title: Text('Ритм', style: t.textTheme.titleLarge),
          ),
          ...rhythm.when(
            loading: () => const [
              SliverPadding(
                padding: EdgeInsets.symmetric(horizontal: 20),
                sliver: SliverToBoxAdapter(child: _SkeletonGrid()),
              ),
            ],
            error: (e, _) => [
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(20, 24, 20, 0),
                sliver: SliverToBoxAdapter(child: _ErrorCard(error: e)),
              ),
            ],
            data: (data) {
              if (data.habits.isEmpty && data.cycles.isEmpty) {
                return const [
                  SliverPadding(
                    padding: EdgeInsets.fromLTRB(20, 24, 20, 0),
                    sliver: SliverToBoxAdapter(child: _EmptyCard()),
                  ),
                ];
              }
              return [
                if (data.habits.isNotEmpty)
                  SliverPadding(
                    padding: const EdgeInsets.fromLTRB(20, 8, 20, 0),
                    sliver: SliverToBoxAdapter(
                      child: _SectionHeader(
                        title: 'Привычки',
                        subtitle: '${data.habits.length} активных',
                      ),
                    ),
                  ),
                if (data.habits.isNotEmpty)
                  SliverPadding(
                    padding: const EdgeInsets.fromLTRB(20, 12, 20, 8),
                    sliver: SliverList.builder(
                      itemCount: data.habits.length,
                      itemBuilder: (_, i) => Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: _HabitCard(moment: data.habits[i]),
                      ),
                    ),
                  ),
                if (data.cycles.isNotEmpty)
                  SliverPadding(
                    padding: const EdgeInsets.fromLTRB(20, 24, 20, 0),
                    sliver: SliverToBoxAdapter(
                      child: _SectionHeader(
                        title: 'Циклы',
                        subtitle: '${data.cycles.length} повторов',
                      ),
                    ),
                  ),
                if (data.cycles.isNotEmpty)
                  SliverPadding(
                    padding: const EdgeInsets.fromLTRB(20, 12, 20, 8),
                    sliver: SliverList.builder(
                      itemCount: data.cycles.length,
                      itemBuilder: (_, i) => Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: _CycleCard(moment: data.cycles[i]),
                      ),
                    ),
                  ),
              ];
            },
          ),
          const SliverPadding(padding: EdgeInsets.only(bottom: 120)),
        ],
      ),
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
    return Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        Text(title, style: t.textTheme.titleMedium),
        const SizedBox(width: 8),
        Padding(
          padding: const EdgeInsets.only(bottom: 2),
          child: Text(subtitle,
              style: t.textTheme.bodySmall?.copyWith(color: MX.fgFaint)),
        ),
      ],
    );
  }
}

class _HabitCard extends StatelessWidget {
  const _HabitCard({required this.moment});
  final Moment moment;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    // 7-day heatmap-плейсхолдер. Реальные `habit_entries` появятся в M5.5/M6.2.
    return Material(
      color: MX.surfaceOverlay,
      borderRadius: BorderRadius.circular(MX.rMd),
      child: InkWell(
        borderRadius: BorderRadius.circular(MX.rMd),
        onTap: () => context.push('/moment/${moment.id}'),
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(MX.rMd),
            border: Border.all(color: MX.line),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    width: 36, height: 36,
                    decoration: BoxDecoration(
                      color: MX.accentPurpleSoft,
                      borderRadius: BorderRadius.circular(MX.rSm),
                    ),
                    child: const Icon(Icons.repeat, color: MX.accentPurple, size: 18),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(moment.title.isEmpty ? '(без названия)' : moment.title,
                            style: t.textTheme.bodyLarge?.copyWith(fontWeight: FontWeight.w600)),
                        const SizedBox(height: 2),
                        Text(_humanRrule(moment.rrule),
                            style: t.textTheme.bodySmall?.copyWith(color: MX.fgMuted)),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              const _Heatmap7d(),
            ],
          ),
        ),
      ),
    );
  }
}

class _Heatmap7d extends StatelessWidget {
  const _Heatmap7d();

  @override
  Widget build(BuildContext context) {
    // Заглушка: 7 квадратов, последние 2 «горящие» — даём ощущение серии.
    // Реальная история выполнения подключится, когда появятся habit_entries.
    final cells = List.generate(7, (i) {
      final filled = i >= 5;
      return Expanded(
        child: AspectRatio(
          aspectRatio: 1,
          child: Container(
            margin: const EdgeInsets.symmetric(horizontal: 2),
            decoration: BoxDecoration(
              color: filled ? MX.accentPurpleSoft : MX.surfaceOverlayHi,
              borderRadius: BorderRadius.circular(MX.rXs),
              border: Border.all(
                color: filled ? MX.accentPurple : MX.line,
                width: 0.5,
              ),
            ),
          ),
        ),
      );
    });
    return Row(children: cells);
  }
}

class _CycleCard extends StatelessWidget {
  const _CycleCard({required this.moment});
  final Moment moment;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Material(
      color: MX.surfaceOverlay,
      borderRadius: BorderRadius.circular(MX.rMd),
      child: InkWell(
        borderRadius: BorderRadius.circular(MX.rMd),
        onTap: () => context.push('/moment/${moment.id}'),
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(MX.rMd),
            border: Border.all(color: MX.line),
          ),
          child: Row(
            children: [
              Container(
                width: 36, height: 36,
                decoration: BoxDecoration(
                  color: MX.accentAiSoft,
                  borderRadius: BorderRadius.circular(MX.rSm),
                ),
                child: Icon(_cycleIcon(moment.kind), color: MX.accentAi, size: 18),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(moment.title,
                        style: t.textTheme.bodyLarge?.copyWith(fontWeight: FontWeight.w600)),
                    const SizedBox(height: 2),
                    Text(_humanRrule(moment.rrule),
                        style: t.textTheme.bodySmall?.copyWith(color: MX.fgMuted)),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right, color: MX.fgFaint),
            ],
          ),
        ),
      ),
    );
  }

  IconData _cycleIcon(String kind) {
    switch (kind) {
      case 'birthday':
        return Icons.cake_outlined;
      case 'cycle':
        return Icons.event_repeat_outlined;
      default:
        return Icons.history;
    }
  }
}

String _humanRrule(String? rrule) {
  if (rrule == null || rrule.isEmpty) return 'Без повтора';
  final upper = rrule.toUpperCase();
  if (upper.contains('FREQ=DAILY')) return 'Каждый день';
  if (upper.contains('FREQ=WEEKLY')) return _weekly(upper);
  if (upper.contains('FREQ=MONTHLY')) return 'Каждый месяц';
  if (upper.contains('FREQ=YEARLY')) return 'Каждый год';
  return rrule;
}

String _weekly(String upper) {
  final m = RegExp(r'BYDAY=([A-Z,]+)').firstMatch(upper);
  if (m == null) return 'Каждую неделю';
  final days = m.group(1)!.split(',').map(_dayLabel).join(', ');
  return 'Еженедельно: $days';
}

String _dayLabel(String d) {
  switch (d) {
    case 'MO':
      return 'пн';
    case 'TU':
      return 'вт';
    case 'WE':
      return 'ср';
    case 'TH':
      return 'чт';
    case 'FR':
      return 'пт';
    case 'SA':
      return 'сб';
    case 'SU':
      return 'вс';
    default:
      return d.toLowerCase();
  }
}

class _EmptyCard extends StatelessWidget {
  const _EmptyCard();
  @override
  Widget build(BuildContext context) {
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
          Text('Пока ничего регулярного.',
              style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 8),
          Text(
            'Расскажи: «каждый понедельник в зал в 19» или «у мамы ДР 15 марта».',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: MX.fgMuted),
          ),
        ],
      ),
    );
  }
}

class _SkeletonGrid extends StatelessWidget {
  const _SkeletonGrid();
  @override
  Widget build(BuildContext context) {
    return Column(
      children: List.generate(3, (_) {
        return Padding(
          padding: const EdgeInsets.only(bottom: 10),
          child: Container(
            height: 100,
            decoration: BoxDecoration(
              color: MX.surfaceOverlay,
              borderRadius: BorderRadius.circular(MX.rMd),
              border: Border.all(color: MX.line),
            ),
          ),
        );
      }),
    );
  }
}

class _ErrorCard extends StatelessWidget {
  const _ErrorCard({required this.error});
  final Object error;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: MX.accentSecuritySoft,
        borderRadius: BorderRadius.circular(MX.rMd),
        border: Border.all(color: MX.accentSecurityLine),
      ),
      child: Row(
        children: [
          const Icon(Icons.error_outline, color: MX.accentSecurity),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              error.toString(),
              style: Theme.of(context).textTheme.bodySmall?.copyWith(color: MX.fg),
            ),
          ),
        ],
      ),
    );
  }
}
