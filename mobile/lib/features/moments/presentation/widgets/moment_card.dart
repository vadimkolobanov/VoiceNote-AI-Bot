import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

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
            border: Border.all(color: MX.line),
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
                        decoration: moment.isDone ? TextDecoration.lineThrough : null,
                        color: moment.isDone ? MX.fgFaint : MX.fg,
                        fontWeight: FontWeight.w600,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    if (moment.occursAt != null) ...[
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          const Icon(Icons.schedule, size: 14, color: MX.fgMuted),
                          const SizedBox(width: 4),
                          Text(
                            _formatWhen(moment.occursAt!),
                            style: t.textTheme.bodySmall?.copyWith(color: MX.fgMuted),
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
              if (onComplete != null && moment.isActive)
                IconButton(
                  iconSize: 22,
                  visualDensity: VisualDensity.compact,
                  icon: const Icon(Icons.check_circle_outline, color: MX.fgMuted),
                  onPressed: onComplete,
                  tooltip: 'Готово',
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
