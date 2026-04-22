import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/core/utils/date_formatter.dart';
import 'package:voicenote_ai/features/tasks/data/models/reminder.dart';
import 'package:voicenote_ai/features/tasks/data/repositories/reminders_repository.dart';
import 'package:voicenote_ai/shared/widgets/app_error.dart';

/// Unified reminders feed (Phase 3a).
/// Показывает ВСЕ предстоящие напоминания — заметки с due_date,
/// привычки, дни рождения — в едином списке, сгруппированы по типу.
class AllRemindersScreen extends ConsumerWidget {
  const AllRemindersScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(allRemindersProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Все напоминания')),
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(allRemindersProvider),
        child: async.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => AppErrorView(error: e, onRetry: () => ref.invalidate(allRemindersProvider)),
          data: (reminders) {
            if (reminders.isEmpty) {
              return const EmptyStateView(
                icon: Icons.notifications_none,
                title: 'Нет активных напоминаний',
                subtitle: 'Создайте задачу с датой, добавьте привычку или день рождения',
              );
            }
            final groups = <ReminderEntityType, List<Reminder>>{};
            for (final r in reminders) {
              groups.putIfAbsent(r.entityType, () => []).add(r);
            }
            final sections = <Widget>[];
            for (final type in ReminderEntityType.values) {
              final list = groups[type];
              if (list == null || list.isEmpty) continue;
              sections.add(_SectionHeader(label: _sectionLabel(type), icon: _sectionIcon(type)));
              for (final r in list) {
                sections.add(_ReminderTile(reminder: r));
              }
            }
            return ListView(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
              children: sections,
            );
          },
        ),
      ),
    );
  }

  String _sectionLabel(ReminderEntityType type) {
    switch (type) {
      case ReminderEntityType.note:
        return 'ЗАДАЧИ';
      case ReminderEntityType.habit:
        return 'ПРИВЫЧКИ';
      case ReminderEntityType.birthday:
        return 'ДНИ РОЖДЕНИЯ';
    }
  }

  IconData _sectionIcon(ReminderEntityType type) {
    switch (type) {
      case ReminderEntityType.note:
        return Icons.task_alt;
      case ReminderEntityType.habit:
        return Icons.repeat;
      case ReminderEntityType.birthday:
        return Icons.cake_outlined;
    }
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.label, required this.icon});
  final String label;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.fromLTRB(4, 16, 4, 8),
      child: Row(
        children: [
          Icon(icon, size: 18, color: scheme.primary),
          const SizedBox(width: 8),
          Text(
            label,
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  fontWeight: FontWeight.w800,
                  color: scheme.primary,
                  letterSpacing: 1.2,
                ),
          ),
        ],
      ),
    );
  }
}

class _ReminderTile extends StatelessWidget {
  const _ReminderTile({required this.reminder});
  final Reminder reminder;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final fireText = reminder.nextFireAt != null
        ? DateFormatter.smartDate(reminder.nextFireAt!)
        : reminder.isRecurring
            ? _humanRrule(reminder.rrule!)
            : 'Без срока';
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        title: Text(
          reminder.title,
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(fontWeight: FontWeight.w600),
        ),
        subtitle: Row(
          children: [
            Icon(Icons.schedule, size: 14, color: scheme.onSurfaceVariant),
            const SizedBox(width: 4),
            Flexible(
              child: Text(
                fireText,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
            if (reminder.isRecurring) ...[
              const SizedBox(width: 8),
              Icon(Icons.repeat, size: 13, color: scheme.onSurfaceVariant),
            ],
          ],
        ),
      ),
    );
  }

  String _humanRrule(String rule) {
    final lower = rule.toLowerCase();
    if (lower.contains('daily')) return 'каждый день';
    if (lower.contains('weekly')) return 'каждую неделю';
    if (lower.contains('yearly')) return 'каждый год';
    if (lower.contains('monthly')) return 'каждый месяц';
    return 'повтор';
  }
}
