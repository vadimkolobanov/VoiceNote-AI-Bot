import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import 'package:voicenote_ai/core/theme/mx_tokens.dart';
import 'package:voicenote_ai/features/agent/presentation/ask_sheet.dart';
import 'package:voicenote_ai/features/moments/application/moments_providers.dart';
import 'package:voicenote_ai/features/moments/data/models/moment.dart';

/// S7 — Хроника (PRODUCT_PLAN.md §2.4) — vertical timeline с цветными
/// dot'ами на рельсе и анимированным появлением.
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
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 16),
            sliver: SliverToBoxAdapter(child: _AskPill()),
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

          // Группы по дате — каждая со своей плашкой и dot-ами на рельсе.
          for (var gi = 0; gi < groups.length; gi++) ...[
            SliverToBoxAdapter(
              child: _DateBubble(label: groups[gi].label, isFirst: gi == 0),
            ),
            SliverList.builder(
              itemCount: groups[gi].items.length,
              itemBuilder: (_, i) {
                final m = groups[gi].items[i];
                final isLastOverall =
                    gi == groups.length - 1 && i == groups[gi].items.length - 1;
                return _TimelineRow(
                  moment: m,
                  isLast: isLastOverall,
                  index: i,
                  onTap: () => context.push('/moment/${m.id}'),
                );
              },
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
                    child: CircularProgressIndicator(
                        strokeWidth: 2, color: MX.accentAi),
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

// ─────────────────────────────────────────────────────────────────────────────
// Constants — рельса проходит через центр dot'а на левой стороне.
// ─────────────────────────────────────────────────────────────────────────────
const double _railLeft = 32; // расстояние от края экрана до центра рельсы
const double _dotSize = 14;
const double _connectorWidth = 2;

class _AskPill extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Material(
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
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Row(
            children: [
              const Icon(Icons.auto_awesome, color: MX.accentAi, size: 20),
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
    );
  }
}

class _DateBubble extends StatelessWidget {
  const _DateBubble({required this.label, required this.isFirst});
  final String label;
  final bool isFirst;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Padding(
      padding: EdgeInsets.fromLTRB(8, isFirst ? 4 : 16, 16, 12),
      child: Row(
        children: [
          // Большой gradient-dot на месте рельсы — «голова» секции.
          Container(
            width: _railLeft + _dotSize / 2,
            alignment: Alignment.centerRight,
            child: Container(
              width: 18,
              height: 18,
              decoration: const BoxDecoration(
                gradient: MX.brandGradient,
                shape: BoxShape.circle,
                boxShadow: [
                  BoxShadow(
                    color: Color(0x6612C2E9),
                    blurRadius: 12,
                    spreadRadius: 1,
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(width: 10),
          Container(
            padding:
                const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: MX.surfaceOverlayHi,
              borderRadius: BorderRadius.circular(MX.rFull),
              border: Border.all(color: MX.line),
            ),
            child: Text(
              label,
              style: t.textTheme.labelMedium?.copyWith(
                color: MX.fg,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _TimelineRow extends StatelessWidget {
  const _TimelineRow({
    required this.moment,
    required this.isLast,
    required this.index,
    required this.onTap,
  });

  final Moment moment;
  final bool isLast;
  final int index;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = _accentForKind(moment.kind);
    final delay = Duration(milliseconds: 40 * index.clamp(0, 6));
    return TweenAnimationBuilder<double>(
      key: ValueKey(moment.id),
      tween: Tween(begin: 0, end: 1),
      duration: const Duration(milliseconds: 320),
      curve: Curves.easeOutCubic,
      builder: (context, v, child) {
        return Opacity(
          opacity: v,
          child: Transform.translate(
            offset: Offset(8 * (1 - v), 0),
            child: child,
          ),
        );
      },
      child: AnimatedSlide(
        offset: Offset.zero,
        duration: delay,
        curve: Curves.easeOut,
        child: IntrinsicHeight(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Rail + dot
              SizedBox(
                width: _railLeft + _dotSize / 2 + 4,
                child: CustomPaint(
                  painter: _RailPainter(
                    color: color,
                    isLast: isLast,
                  ),
                ),
              ),
              const SizedBox(width: 6),
              // Card
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(0, 6, 16, 12),
                  child: _BubbleCard(moment: moment, accent: color, onTap: onTap),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _RailPainter extends CustomPainter {
  _RailPainter({required this.color, required this.isLast});
  final Color color;
  final bool isLast;

  @override
  void paint(Canvas canvas, Size size) {
    final cx = _railLeft;
    final cy = 18.0; // dot чуть ниже верха карточки
    final linePaint = Paint()
      ..color = MX.line
      ..strokeWidth = _connectorWidth
      ..style = PaintingStyle.stroke;
    // Сегмент над dot'ом
    canvas.drawLine(Offset(cx, 0), Offset(cx, cy - _dotSize / 2), linePaint);
    // Сегмент под dot'ом
    if (!isLast) {
      canvas.drawLine(
        Offset(cx, cy + _dotSize / 2),
        Offset(cx, size.height),
        linePaint,
      );
    }
    // Glow вокруг dot'а
    final glowPaint = Paint()
      ..color = color.withAlpha(60)
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 6);
    canvas.drawCircle(Offset(cx, cy), _dotSize / 2 + 3, glowPaint);
    // Сам dot — кольцо + центр
    final ringPaint = Paint()
      ..color = color
      ..strokeWidth = 2
      ..style = PaintingStyle.stroke;
    final corePaint = Paint()
      ..color = MX.bgBase
      ..style = PaintingStyle.fill;
    canvas.drawCircle(Offset(cx, cy), _dotSize / 2, corePaint);
    canvas.drawCircle(Offset(cx, cy), _dotSize / 2, ringPaint);
    final innerPaint = Paint()..color = color;
    canvas.drawCircle(Offset(cx, cy), _dotSize / 2 - 3, innerPaint);
  }

  @override
  bool shouldRepaint(covariant _RailPainter old) =>
      old.color != color || old.isLast != isLast;
}

class _BubbleCard extends StatelessWidget {
  const _BubbleCard({
    required this.moment,
    required this.accent,
    required this.onTap,
  });
  final Moment moment;
  final Color accent;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final timeText = DateFormat.Hm().format(moment.createdAt);
    return Material(
      color: MX.surfaceOverlay,
      borderRadius: BorderRadius.circular(MX.rMd),
      child: InkWell(
        borderRadius: BorderRadius.circular(MX.rMd),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.fromLTRB(14, 12, 14, 14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(MX.rMd),
            border: Border.all(color: MX.line),
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                accent.withAlpha(18),
                Colors.transparent,
              ],
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(_iconForKind(moment.kind), color: accent, size: 16),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      moment.title.isEmpty ? '(без названия)' : moment.title,
                      style: t.textTheme.bodyLarge?.copyWith(
                        fontWeight: FontWeight.w600,
                        decoration: moment.completedToday
                            ? TextDecoration.lineThrough
                            : null,
                        color: moment.completedToday ? MX.fgFaint : MX.fg,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  Text(
                    timeText,
                    style: t.textTheme.bodySmall?.copyWith(color: MX.fgMuted),
                  ),
                ],
              ),
              if (moment.summary != null && moment.summary!.isNotEmpty) ...[
                const SizedBox(height: 6),
                Text(
                  moment.summary!,
                  maxLines: 3,
                  overflow: TextOverflow.ellipsis,
                  style: t.textTheme.bodySmall?.copyWith(color: MX.fgMuted),
                ),
              ],
              if (moment.nextReminderAt != null || moment.isHabit) ...[
                const SizedBox(height: 8),
                Row(
                  children: [
                    Icon(
                      moment.isHabit ? Icons.repeat : Icons.schedule,
                      size: 13,
                      color: MX.fgMicro,
                    ),
                    const SizedBox(width: 4),
                    Expanded(
                      child: Text(
                        moment.nextReminderAt != null
                            ? _formatNext(moment.nextReminderAt!)
                            : _rruleHumanRu(moment.rrule),
                        style: t.textTheme.bodySmall
                            ?.copyWith(color: MX.fgMicro, fontSize: 11),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────

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

String _formatNext(DateTime when) {
  final now = DateTime.now();
  final today = DateTime(now.year, now.month, now.day);
  final wDate = DateTime(when.year, when.month, when.day);
  final hhmm = DateFormat.Hm().format(when);
  final diffDays = wDate.difference(today).inDays;
  if (diffDays == 0) return 'Сегодня в $hhmm';
  if (diffDays == 1) return 'Завтра в $hhmm';
  if (diffDays > 1 && diffDays < 7) {
    return '${DateFormat.EEEE('ru').format(when)} в $hhmm';
  }
  return '${DateFormat('d MMM', 'ru').format(when)} в $hhmm';
}

String _rruleHumanRu(String? rrule) {
  if (rrule == null || rrule.isEmpty) return 'Регулярно';
  final parts = <String, String>{};
  for (final kv in rrule.split(';')) {
    final i = kv.indexOf('=');
    if (i > 0) parts[kv.substring(0, i).toUpperCase()] = kv.substring(i + 1).toUpperCase();
  }
  switch (parts['FREQ'] ?? '') {
    case 'DAILY':
      return 'Каждый день';
    case 'WEEKLY':
      return 'Каждую неделю';
    case 'MONTHLY':
      return 'Каждый месяц';
    case 'YEARLY':
      return 'Каждый год';
    default:
      return 'Регулярно';
  }
}

IconData _iconForKind(String kind) {
  switch (kind) {
    case 'task':
      return Icons.notifications_active_outlined;
    case 'shopping':
      return Icons.shopping_basket_outlined;
    case 'habit':
      return Icons.repeat;
    case 'birthday':
      return Icons.cake_outlined;
    case 'cycle':
      return Icons.event_repeat_outlined;
    case 'thought':
      return Icons.auto_awesome_outlined;
    case 'note':
    default:
      return Icons.sticky_note_2_outlined;
  }
}

Color _accentForKind(String kind) {
  switch (kind) {
    case 'task':
      return MX.accentAi;
    case 'shopping':
      return MX.accentTools;
    case 'habit':
      return MX.accentPurple;
    case 'birthday':
      return MX.statusWarning;
    case 'cycle':
      return MX.accentAi;
    case 'thought':
      return MX.accentPurple;
    case 'note':
    default:
      return MX.fgMuted;
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
