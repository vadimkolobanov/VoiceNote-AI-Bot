import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons/lucide_icons.dart';

import 'package:voicenote_ai/core/theme/mx_tokens.dart';
import 'package:voicenote_ai/features/auth/application/session_controller.dart';
import 'package:voicenote_ai/features/moments/application/moments_providers.dart';
import 'package:voicenote_ai/features/moments/data/models/moment.dart';
import 'package:voicenote_ai/features/moments/data/repositories/moments_repository.dart';
import 'package:voicenote_ai/features/moments/presentation/widgets/moment_card.dart';
import 'package:voicenote_ai/features/profile/data/profile_repository.dart';

/// S6 — Сегодня (PRODUCT_PLAN.md §2.3).
class TodayScreen extends ConsumerWidget {
  const TodayScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final feed = ref.watch(todayProvider);
    final t = Theme.of(context);
    final user = ref.watch(sessionControllerProvider).user;

    return RefreshIndicator(
      onRefresh: () async => ref.invalidate(todayProvider),
      color: MX.accentAi,
      child: CustomScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        slivers: [
          SliverAppBar(
            floating: true,
            backgroundColor: MX.bgBase,
            surfaceTintColor: Colors.transparent,
            title: Text('Сегодня', style: t.textTheme.titleLarge),
          ),
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
            sliver: SliverToBoxAdapter(child: _Greeting(name: user?.displayName)),
          ),
          ...feed.when(
            loading: () => const [
              SliverPadding(
                padding: EdgeInsets.symmetric(horizontal: 20),
                sliver: SliverToBoxAdapter(child: _SkeletonList(count: 3)),
              ),
            ],
            error: (e, _) => [
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(20, 24, 20, 0),
                sliver: SliverToBoxAdapter(child: _ErrorCard(error: e)),
              ),
            ],
            data: (items) {
              if (items.isEmpty) {
                return const [
                  SliverPadding(
                    padding: EdgeInsets.fromLTRB(20, 24, 20, 0),
                    sliver: SliverToBoxAdapter(child: _EmptyCard()),
                  ),
                ];
              }
              final upcoming = items.where((m) => m.occursAt != null).toList();
              final undated = items.where((m) => m.occursAt == null).toList();
              return [
                if (upcoming.isNotEmpty)
                  SliverPadding(
                    padding: const EdgeInsets.fromLTRB(20, 8, 20, 0),
                    sliver: SliverList.builder(
                      itemCount: upcoming.length,
                      itemBuilder: (_, i) => Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: _MomentRow(moment: upcoming[i]),
                      ),
                    ),
                  ),
                if (undated.isNotEmpty)
                  SliverPadding(
                    padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
                    sliver: SliverToBoxAdapter(
                      child: Text(
                        'Без времени',
                        style: t.textTheme.titleSmall?.copyWith(color: MX.fgMuted),
                      ),
                    ),
                  ),
                if (undated.isNotEmpty)
                  SliverPadding(
                    padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
                    sliver: SliverList.builder(
                      itemCount: undated.length,
                      itemBuilder: (_, i) => Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: _MomentRow(moment: undated[i]),
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

class _MomentRow extends ConsumerWidget {
  const _MomentRow({required this.moment});
  final Moment moment;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MomentCard(
      moment: moment,
      onTap: () => context.push('/moment/${moment.id}'),
      onComplete: () async {
        try {
          final repo = ref.read(momentsRepositoryProvider);
          if (moment.completedToday) {
            await repo.uncomplete(moment.id);
          } else {
            await repo.complete(moment.id);
          }
          ref.invalidate(todayProvider);
        } catch (e) {
          if (context.mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text('Не удалось обновить: $e')),
            );
          }
        }
      },
    );
  }
}

class _Greeting extends ConsumerWidget {
  const _Greeting({this.name});
  final String? name;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = Theme.of(context);
    final h = DateTime.now().hour;
    final salute = h < 5
        ? 'Ночь'
        : h < 12
            ? 'Доброе утро'
            : h < 18
                ? 'Добрый день'
                : 'Добрый вечер';
    final firstName = (name?.trim().isNotEmpty ?? false)
        ? name!.trim().split(' ').first
        : null;
    final stats = ref.watch(profileStatsProvider);

    return Container(
      padding: const EdgeInsets.fromLTRB(18, 16, 18, 18),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(MX.rLg),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            MX.accentAi.withAlpha(26),
            MX.accentPurple.withAlpha(20),
            Colors.transparent,
          ],
        ),
        border: Border.all(color: MX.accentAi.withAlpha(40)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: MX.accentAi.withAlpha(28),
                  borderRadius: BorderRadius.circular(MX.rFull),
                  border: Border.all(color: MX.accentAi.withAlpha(60)),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(LucideIcons.sparkles,
                        size: 12, color: MX.accentAi),
                    const SizedBox(width: 4),
                    Text(
                      'AI',
                      style: t.textTheme.labelSmall?.copyWith(
                        color: MX.accentAi,
                        fontSize: 10,
                        letterSpacing: 1,
                      ),
                    ),
                  ],
                ),
              ),
              const Spacer(),
              Text(
                _todayLabel(),
                style: t.textTheme.bodySmall?.copyWith(color: MX.fgMuted),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Text(
            firstName == null ? '$salute.' : '$salute, $firstName.',
            style: t.textTheme.headlineMedium?.copyWith(
              color: MX.fg,
              letterSpacing: -0.4,
            ),
          ),
          const SizedBox(height: 6),
          stats.when(
            loading: () => Text('Я готов помнить за тебя.',
                style: t.textTheme.bodyMedium?.copyWith(color: MX.fgMuted)),
            error: (_, __) => Text('Я готов помнить за тебя.',
                style: t.textTheme.bodyMedium?.copyWith(color: MX.fgMuted)),
            data: (s) => Text(
              _statsLine(s),
              style: t.textTheme.bodyMedium?.copyWith(color: MX.fgMuted),
            ),
          ),
        ],
      ),
    );
  }

  static String _todayLabel() {
    const months = [
      'янв', 'фев', 'мар', 'апр', 'май', 'июн',
      'июл', 'авг', 'сен', 'окт', 'ноя', 'дек',
    ];
    final n = DateTime.now();
    return '${n.day} ${months[n.month - 1]}';
  }

  static String _statsLine(ProfileStats s) {
    if (s.activeCount == 0 && s.doneToday == 0) {
      return 'Тихо. Расскажи мне, что не хочешь забыть.';
    }
    final parts = <String>[];
    if (s.activeCount > 0) parts.add('${s.activeCount} в работе');
    if (s.doneToday > 0) parts.add('${s.doneToday} выполнено');
    if (s.overdueCount > 0) parts.add('${s.overdueCount} просрочено');
    return parts.join(' · ');
  }
}

class _EmptyCard extends StatelessWidget {
  const _EmptyCard();
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
          Text('Сегодня тихо.', style: t.textTheme.titleLarge),
          const SizedBox(height: 8),
          Text(
            'Нажми микрофон и расскажи, что не хочешь забыть.',
            style: t.textTheme.bodyMedium?.copyWith(color: MX.fgMuted),
          ),
        ],
      ),
    );
  }
}

class _SkeletonList extends StatelessWidget {
  const _SkeletonList({required this.count});
  final int count;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: List.generate(count, (i) {
        return Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: Container(
            height: 76,
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
