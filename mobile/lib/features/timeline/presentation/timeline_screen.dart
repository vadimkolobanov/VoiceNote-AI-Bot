import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import 'package:voicenote_ai/core/theme/mx_tokens.dart';
import 'package:voicenote_ai/features/agent/presentation/ask_sheet.dart';
import 'package:voicenote_ai/features/moments/application/moments_providers.dart';
import 'package:voicenote_ai/features/moments/data/models/moment.dart';
import 'package:voicenote_ai/features/moments/presentation/widgets/moment_card.dart';

/// S7 — Хроника (PRODUCT_PLAN.md §2.4). Группировка по датам, бесконечная
/// прокрутка через `loadMore`. Поиск к ИИ — в M6 (Pro-фича).
class TimelineScreen extends ConsumerStatefulWidget {
  const TimelineScreen({super.key});

  @override
  ConsumerState<TimelineScreen> createState() => _TimelineScreenState();
}

class _TimelineScreenState extends ConsumerState<TimelineScreen> {
  final _scrollCtl = ScrollController();

  @override
  void initState() {
    super.initState();
    _scrollCtl.addListener(_maybeLoadMore);
  }

  @override
  void dispose() {
    _scrollCtl.removeListener(_maybeLoadMore);
    _scrollCtl.dispose();
    super.dispose();
  }

  void _maybeLoadMore() {
    if (!_scrollCtl.hasClients) return;
    final pos = _scrollCtl.position;
    if (pos.pixels > pos.maxScrollExtent - 320) {
      ref.read(timelineControllerProvider.notifier).loadMore();
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(timelineControllerProvider);
    final t = Theme.of(context);

    final groups = _groupByDate(state.items);

    return RefreshIndicator(
      onRefresh: () => ref.read(timelineControllerProvider.notifier).refresh(),
      color: MX.accentAi,
      child: CustomScrollView(
        controller: _scrollCtl,
        physics: const AlwaysScrollableScrollPhysics(),
        slivers: [
          SliverAppBar(
            floating: true,
            backgroundColor: MX.bgBase,
            surfaceTintColor: Colors.transparent,
            title: Text('Хроника', style: t.textTheme.titleLarge),
          ),
          // Кнопка-плашка «Спроси меня». Тап → AskSheet (S14, Pro-only).
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 16),
            sliver: SliverToBoxAdapter(
              child: Material(
                color: MX.surfaceOverlay,
                borderRadius: BorderRadius.circular(MX.rFull),
                child: InkWell(
                  borderRadius: BorderRadius.circular(MX.rFull),
                  onTap: () => AskSheet.show(context),
                  child: Container(
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(MX.rFull),
                      border: Border.all(color: MX.line),
                    ),
                    padding:
                        const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    child: Row(
                      children: [
                        const Icon(Icons.auto_awesome,
                            color: MX.accentAi, size: 20),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Text(
                            'Спроси меня о чём угодно…',
                            style: t.textTheme.bodyMedium
                                ?.copyWith(color: MX.fgMuted),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),

          if (state.isLoading && state.items.isEmpty)
            const SliverPadding(
              padding: EdgeInsets.symmetric(horizontal: 20),
              sliver: SliverToBoxAdapter(child: _SkeletonList(count: 5)),
            ),
          if (state.error != null && state.items.isEmpty)
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(20, 24, 20, 0),
              sliver: SliverToBoxAdapter(child: _ErrorCard(error: state.error!)),
            ),
          if (state.items.isEmpty && !state.isLoading && state.error == null)
            const SliverPadding(
              padding: EdgeInsets.fromLTRB(20, 32, 20, 0),
              sliver: SliverToBoxAdapter(child: _EmptyCard()),
            ),

          // Группы по дате
          for (final g in groups) ...[
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(20, 4, 20, 8),
              sliver: SliverToBoxAdapter(
                child: Text(
                  g.label,
                  style: t.textTheme.titleSmall?.copyWith(color: MX.fgMuted),
                ),
              ),
            ),
            SliverPadding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              sliver: SliverList.builder(
                itemCount: g.items.length,
                itemBuilder: (_, i) => Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: MomentCard(
                    moment: g.items[i],
                    onTap: () => context.push('/moment/${g.items[i].id}'),
                  ),
                ),
              ),
            ),
          ],

          if (state.isLoading && state.items.isNotEmpty)
            const SliverPadding(
              padding: EdgeInsets.all(20),
              sliver: SliverToBoxAdapter(
                child: Center(
                  child: SizedBox(
                    width: 22,
                    height: 22,
                    child: CircularProgressIndicator(strokeWidth: 2, color: MX.accentAi),
                  ),
                ),
              ),
            ),

          const SliverPadding(padding: EdgeInsets.only(bottom: 120)),
        ],
      ),
    );
  }
}

class _DateGroup {
  _DateGroup(this.label, this.items);
  final String label;
  final List<Moment> items;
}

List<_DateGroup> _groupByDate(List<Moment> items) {
  final map = <DateTime, List<Moment>>{};
  for (final m in items) {
    final d = DateTime(m.createdAt.year, m.createdAt.month, m.createdAt.day);
    map.putIfAbsent(d, () => []).add(m);
  }
  final keys = map.keys.toList()..sort((a, b) => b.compareTo(a));
  return [
    for (final d in keys) _DateGroup(_labelForDate(d), map[d]!),
  ];
}

String _labelForDate(DateTime d) {
  final now = DateTime.now();
  final today = DateTime(now.year, now.month, now.day);
  final diff = today.difference(d).inDays;
  if (diff == 0) return 'Сегодня';
  if (diff == 1) return 'Вчера';
  if (diff < 7) return DateFormat.EEEE('ru').format(d);
  return DateFormat('d MMMM yyyy', 'ru').format(d);
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
            height: 72,
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
          Text('Хроника пуста.',
              style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 8),
          Text(
            'Каждый твой момент тут останется. Начни с микрофона.',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: MX.fgMuted),
          ),
        ],
      ),
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
