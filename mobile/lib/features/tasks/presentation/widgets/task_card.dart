import 'package:flutter/material.dart';

import 'package:voicenote_ai/core/utils/date_formatter.dart';
import 'package:voicenote_ai/features/notes/data/models/note.dart';

/// Card for a single task.
///
/// Long-press or overflow-menu reveals quick-actions:
///  — Перенести на завтра
///  — Перенести на неделю
///  — Снять дату (превращает в обычную заметку)
class TaskCard extends StatelessWidget {
  const TaskCard({
    required this.task,
    this.onTap,
    this.onCompleteTap,
    this.onPostponeDay,
    this.onPostponeWeek,
    this.onClearDueDate,
    super.key,
  });

  final Note task;
  final VoidCallback? onTap;
  final VoidCallback? onCompleteTap;
  final VoidCallback? onPostponeDay;
  final VoidCallback? onPostponeWeek;
  final VoidCallback? onClearDueDate;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    final now = DateTime.now();
    final due = task.dueDate;
    final isOverdue = due != null && due.isBefore(now) && !task.isCompleted;
    final isToday = due != null &&
        due.year == now.year && due.month == now.month && due.day == now.day;

    Color dueColor;
    if (task.isCompleted) {
      dueColor = scheme.onSurfaceVariant;
    } else if (isOverdue) {
      dueColor = scheme.error;
    } else if (isToday) {
      dueColor = scheme.primary;
    } else {
      dueColor = scheme.onSurfaceVariant;
    }

    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        onLongPress: _hasQuickActions ? () => _showQuickActions(context) : null,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(4, 6, 4, 6),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              IconButton(
                tooltip: task.isCompleted ? 'Выполнено' : 'Отметить',
                icon: Icon(
                  task.isCompleted ? Icons.check_circle : Icons.radio_button_unchecked,
                  color: task.isCompleted ? scheme.primary : scheme.outline,
                  size: 28,
                ),
                onPressed: task.isCompleted ? null : onCompleteTap,
              ),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        task.summaryText?.isNotEmpty == true
                            ? task.summaryText!
                            : task.correctedText,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: textTheme.titleSmall?.copyWith(
                          decoration: task.isCompleted ? TextDecoration.lineThrough : null,
                          color: task.isCompleted
                              ? scheme.onSurfaceVariant
                              : scheme.onSurface,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          Icon(
                            isOverdue ? Icons.warning_amber_rounded : Icons.schedule,
                            size: 14,
                            color: dueColor,
                          ),
                          const SizedBox(width: 4),
                          Flexible(
                            child: Text(
                              due == null ? 'Без срока' : DateFormatter.smartDate(due),
                              overflow: TextOverflow.ellipsis,
                              style: textTheme.bodySmall?.copyWith(
                                color: dueColor,
                                fontWeight: isOverdue ? FontWeight.w600 : null,
                              ),
                            ),
                          ),
                          if (task.recurrenceRule != null) ...[
                            const SizedBox(width: 10),
                            Icon(Icons.repeat, size: 13, color: scheme.onSurfaceVariant),
                            const SizedBox(width: 2),
                            Text(
                              _humanRrule(task.recurrenceRule!),
                              style: textTheme.bodySmall?.copyWith(
                                color: scheme.onSurfaceVariant,
                              ),
                            ),
                          ],
                        ],
                      ),
                    ],
                  ),
                ),
              ),
              if (_hasQuickActions)
                PopupMenuButton<String>(
                  tooltip: 'Действия',
                  icon: const Icon(Icons.more_vert, size: 20),
                  onSelected: _onMenuSelected,
                  itemBuilder: _menuItems,
                ),
            ],
          ),
        ),
      ),
    );
  }

  bool get _hasQuickActions =>
      !task.isCompleted && (onPostponeDay != null || onPostponeWeek != null || onClearDueDate != null);

  List<PopupMenuEntry<String>> _menuItems(BuildContext context) {
    return [
      if (onPostponeDay != null)
        const PopupMenuItem(value: 'day', child: Text('Перенести на завтра')),
      if (onPostponeWeek != null)
        const PopupMenuItem(value: 'week', child: Text('Перенести на неделю')),
      if (onClearDueDate != null)
        const PopupMenuItem(value: 'clear', child: Text('Убрать дату')),
    ];
  }

  void _onMenuSelected(String value) {
    switch (value) {
      case 'day':
        onPostponeDay?.call();
      case 'week':
        onPostponeWeek?.call();
      case 'clear':
        onClearDueDate?.call();
    }
  }

  Future<void> _showQuickActions(BuildContext context) async {
    final picked = await showModalBottomSheet<String>(
      context: context,
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (onPostponeDay != null)
              ListTile(
                leading: const Icon(Icons.snooze),
                title: const Text('Перенести на завтра'),
                onTap: () => Navigator.pop(ctx, 'day'),
              ),
            if (onPostponeWeek != null)
              ListTile(
                leading: const Icon(Icons.skip_next_outlined),
                title: const Text('Перенести на неделю'),
                onTap: () => Navigator.pop(ctx, 'week'),
              ),
            if (onClearDueDate != null)
              ListTile(
                leading: const Icon(Icons.event_busy),
                title: const Text('Убрать дату'),
                onTap: () => Navigator.pop(ctx, 'clear'),
              ),
          ],
        ),
      ),
    );
    if (picked != null) _onMenuSelected(picked);
  }

  String _humanRrule(String rule) {
    final lower = rule.toLowerCase();
    if (lower.contains('daily')) return 'каждый день';
    if (lower.contains('weekly')) return 'каждую неделю';
    if (lower.contains('monthly')) return 'каждый месяц';
    if (lower.contains('yearly')) return 'каждый год';
    return 'повтор';
  }
}
