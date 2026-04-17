import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/features/habits/application/habits_controller.dart';
import 'package:voicenote_ai/features/habits/data/models/habit.dart';

class HabitCard extends ConsumerWidget {
  const HabitCard({required this.habit, super.key});

  final Habit habit;

  IconData get _icon {
    switch (habit.iconName) {
      case 'water':
        return Icons.water_drop_outlined;
      case 'run':
      case 'sport':
        return Icons.directions_run;
      case 'book':
        return Icons.menu_book_outlined;
      case 'meditation':
        return Icons.self_improvement;
      case 'sleep':
        return Icons.bedtime_outlined;
      default:
        return Icons.repeat;
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final scheme = Theme.of(context).colorScheme;
    final statsAsync = ref.watch(habitWeeklyStatsProvider(habit.id));

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 42,
                  height: 42,
                  decoration: BoxDecoration(
                    color: scheme.primaryContainer,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(_icon, color: scheme.primary),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        habit.name,
                        style: Theme.of(context).textTheme.titleSmall?.copyWith(
                              fontWeight: FontWeight.w600,
                            ),
                      ),
                      const SizedBox(height: 2),
                      Row(
                        children: [
                          Icon(Icons.local_fire_department, size: 14, color: scheme.secondary),
                          const SizedBox(width: 4),
                          Text(
                            '${habit.streak} дн. подряд',
                            style: Theme.of(context).textTheme.bodySmall,
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                FilledButton.tonal(
                  onPressed: habit.completedToday
                      ? null
                      : () => ref
                          .read(habitsActionsProvider)
                          .track(habit.id, HabitTrackStatus.done),
                  child: Text(habit.completedToday ? 'Готово' : 'Done!'),
                ),
              ],
            ),
            const SizedBox(height: 14),
            statsAsync.when(
              loading: () => SizedBox(
                height: 20,
                child: LinearProgressIndicator(
                  color: scheme.primary.withValues(alpha: 0.4),
                  backgroundColor: scheme.surfaceContainerHighest,
                ),
              ),
              error: (_, __) => const SizedBox.shrink(),
              data: (stats) => _WeekGrid(stats: stats),
            ),
          ],
        ),
      ),
    );
  }
}

class _WeekGrid extends StatelessWidget {
  const _WeekGrid({required this.stats});
  final List<HabitDailyStat> stats;

  static const _labels = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final now = DateTime.now();
    final start = now.subtract(Duration(days: now.weekday - 1));

    return Row(
      children: List.generate(7, (i) {
        final date = DateTime(start.year, start.month, start.day + i);
        HabitDailyStat? entry;
        for (final s in stats) {
          if (s.date.year == date.year &&
              s.date.month == date.month &&
              s.date.day == date.day) {
            entry = s;
            break;
          }
        }
        final status = entry?.status;
        Color bg;
        switch (status) {
          case HabitTrackStatus.done:
            bg = scheme.primary;
          case HabitTrackStatus.skipped:
            bg = scheme.error.withValues(alpha: 0.4);
          case null:
            bg = scheme.surfaceContainerHighest;
        }
        return Expanded(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 3),
            child: Column(
              children: [
                AspectRatio(
                  aspectRatio: 1,
                  child: Container(
                    decoration: BoxDecoration(
                      color: bg,
                      borderRadius: BorderRadius.circular(8),
                    ),
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  _labels[i],
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: scheme.onSurfaceVariant,
                      ),
                ),
              ],
            ),
          ),
        );
      }),
    );
  }
}
