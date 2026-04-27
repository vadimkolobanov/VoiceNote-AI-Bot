import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:lucide_icons/lucide_icons.dart';

import 'package:voicenote_ai/core/theme/mx_tokens.dart';
import 'package:voicenote_ai/features/moments/data/models/moment.dart';

/// Карточка момента. PRODUCT_PLAN.md §2.3 (Сегодня) + §2.4 (Хроника).
///
/// Свайп-действия (done/snooze) реализуются на уровне списка через
/// Dismissible / Slidable; тут — только визуал и tap-to-open.
class MomentCard extends StatelessWidget {
  const MomentCard({
    super.key,
    required this.moment,
    required this.onTap,
    this.onComplete,
  });

  final Moment moment;
  final VoidCallback onTap;
  final VoidCallback? onComplete;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    final color = _accentForKind(moment.kind);

    const overdueColor = Color(0xFFFF453A);
    return Material(
      color: MX.surfaceOverlay,
      borderRadius: BorderRadius.circular(MX.rMd),
      child: InkWell(
        borderRadius: BorderRadius.circular(MX.rMd),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.fromLTRB(14, 14, 8, 14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(MX.rMd),
            border: Border.all(
              color: moment.isOverdue
                  ? overdueColor.withAlpha(120)
                  : MX.line,
            ),
            color: moment.isOverdue
                ? overdueColor.withAlpha(15)
                : null,
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Цветной значок-таб
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  color: color.withAlpha(40),
                  borderRadius: BorderRadius.circular(MX.rSm),
                ),
                child: Icon(_iconForKind(moment.kind), color: color, size: 18),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      moment.title.isEmpty ? '(без названия)' : moment.title,
                      style: t.textTheme.bodyLarge?.copyWith(
                        decoration: moment.completedToday
                            ? TextDecoration.lineThrough
                            : null,
                        color: moment.completedToday ? MX.fgFaint : MX.fg,
                        fontWeight: FontWeight.w600,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    if (moment.isOverdue) ...[
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          const Icon(LucideIcons.alertTriangle,
                              size: 14, color: overdueColor),
                          const SizedBox(width: 4),
                          Expanded(
                            child: Text(
                              moment.occursAt != null
                                  ? 'Просрочено · ${_formatOverdue(moment.occursAt!)}'
                                  : 'Просрочено',
                              style: t.textTheme.bodySmall?.copyWith(
                                color: overdueColor,
                                fontWeight: FontWeight.w600,
                              ),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                    ] else if (moment.nextReminderAt != null || moment.isHabit) ...[
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          Icon(
                            moment.isHabit ? LucideIcons.repeat : LucideIcons.clock,
                            size: 14,
                            color: MX.fgMuted,
                          ),
                          const SizedBox(width: 4),
                          Expanded(
                            child: Text(
                              moment.nextReminderAt != null
                                  ? _formatWhen(moment.nextReminderAt!)
                                  : _rruleHumanRu(moment.rrule),
                              style: t.textTheme.bodySmall
                                  ?.copyWith(color: MX.fgMuted),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                    ] else if (moment.summary != null && moment.summary!.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Text(
                        moment.summary!,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: t.textTheme.bodySmall?.copyWith(color: MX.fgMuted),
                      ),
                    ],
                  ],
                ),
              ),
              if (onComplete != null)
                IconButton(
                  iconSize: 24,
                  visualDensity: VisualDensity.compact,
                  icon: Icon(
                    moment.completedToday
                        ? LucideIcons.checkCircle2
                        : LucideIcons.circle,
                    color: moment.completedToday
                        ? const Color(0xFF34C759)
                        : MX.fgMuted,
                  ),
                  onPressed: onComplete,
                  tooltip: moment.completedToday
                      ? (moment.isHabit ? 'Снять отметку на сегодня' : 'Вернуть в активные')
                      : 'Выполнено',
                )
              else
                const SizedBox(width: 8),
            ],
          ),
        ),
      ),
    );
  }
}

IconData _iconForKind(String kind) {
  switch (kind) {
    case 'task':
      return LucideIcons.bell;
    case 'shopping':
      return LucideIcons.shoppingCart;
    case 'habit':
      return LucideIcons.repeat;
    case 'birthday':
      return LucideIcons.gift;
    case 'cycle':
      return LucideIcons.calendar;
    case 'thought':
      return LucideIcons.sparkles;
    case 'note':
    default:
      return LucideIcons.fileText;
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

String _rruleHumanRu(String? rrule) {
  if (rrule == null || rrule.isEmpty) return 'Регулярно';
  final parts = <String, String>{};
  for (final kv in rrule.split(';')) {
    final i = kv.indexOf('=');
    if (i > 0) parts[kv.substring(0, i).toUpperCase()] = kv.substring(i + 1).toUpperCase();
  }
  final freq = parts['FREQ'] ?? '';
  switch (freq) {
    case 'DAILY':
      return 'Каждый день';
    case 'WEEKLY':
      final days = parts['BYDAY'];
      if (days == null || days.isEmpty) return 'Каждую неделю';
      const map = {
        'MO': 'пн', 'TU': 'вт', 'WE': 'ср', 'TH': 'чт',
        'FR': 'пт', 'SA': 'сб', 'SU': 'вс',
      };
      final names = days.split(',').map((d) => map[d.trim()] ?? d).join(', ');
      return 'По $names';
    case 'MONTHLY':
      return 'Каждый месяц';
    case 'YEARLY':
      return 'Каждый год';
    default:
      return 'Регулярно';
  }
}

String _formatOverdue(DateTime when) {
  final now = DateTime.now();
  final diff = now.difference(when);
  if (diff.inMinutes < 60) return '${diff.inMinutes} мин назад';
  if (diff.inHours < 24) return '${diff.inHours} ч назад';
  if (diff.inDays < 7) return '${diff.inDays} дн назад';
  return DateFormat('d MMM', 'ru').format(when);
}

String _formatWhen(DateTime when) {
  final now = DateTime.now();
  final today = DateTime(now.year, now.month, now.day);
  final wDate = DateTime(when.year, when.month, when.day);
  final hhmm = DateFormat.Hm().format(when);

  final diffDays = wDate.difference(today).inDays;
  if (diffDays == 0) return 'Сегодня в $hhmm';
  if (diffDays == 1) return 'Завтра в $hhmm';
  if (diffDays == -1) return 'Вчера в $hhmm';
  if (diffDays > 1 && diffDays < 7) {
    return '${DateFormat.EEEE('ru').format(when)} в $hhmm';
  }
  return '${DateFormat('d MMM', 'ru').format(when)} в $hhmm';
}
