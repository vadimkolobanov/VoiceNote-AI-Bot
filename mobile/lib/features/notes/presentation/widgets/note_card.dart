import 'package:flutter/material.dart';

import 'package:voicenote_ai/core/theme/app_theme.dart';
import 'package:voicenote_ai/core/theme/mx_tokens.dart';
import 'package:voicenote_ai/core/utils/date_formatter.dart';
import 'package:voicenote_ai/features/notes/data/models/note.dart';

class NoteCard extends StatelessWidget {
  const NoteCard({
    required this.note,
    this.onTap,
    this.onCompleteTap,
    super.key,
  });

  final Note note;
  final VoidCallback? onTap;
  final VoidCallback? onCompleteTap;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    final category = (note.category ?? '').toLowerCase();
    final chipColor = AppTheme.categoryColors[category] ?? scheme.primary;

    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 14, 12, 14),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 4,
                height: 52,
                decoration: BoxDecoration(
                  color: chipColor,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      note.displayTitle,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: textTheme.titleSmall?.copyWith(
                        decoration: note.isCompleted ? TextDecoration.lineThrough : null,
                        color: note.isCompleted
                            ? scheme.onSurfaceVariant
                            : scheme.onSurface,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Row(
                      children: [
                        if (note.category != null) ...[
                          _Chip(label: note.category!, color: chipColor),
                          const SizedBox(width: 8),
                        ],
                        if (note.dueDate != null)
                          Flexible(
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(Icons.schedule, size: 14, color: scheme.onSurfaceVariant),
                                const SizedBox(width: 4),
                                Flexible(
                                  child: Text(
                                    DateFormatter.smartDate(note.dueDate!),
                                    overflow: TextOverflow.ellipsis,
                                    style: textTheme.bodySmall?.copyWith(
                                      color: scheme.onSurfaceVariant,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          )
                        else
                          Text(
                            DateFormatter.relative(note.createdAt),
                            style: textTheme.bodySmall?.copyWith(
                              color: scheme.onSurfaceVariant,
                            ),
                          ),
                      ],
                    ),
                  ],
                ),
              ),
              IconButton(
                tooltip: note.isCompleted ? 'Выполнено' : 'Отметить выполненным',
                icon: Icon(
                  note.isCompleted ? Icons.check_circle : Icons.radio_button_unchecked,
                  color: note.isCompleted ? MX.accentTools : scheme.outline,
                ),
                onPressed: note.isCompleted ? null : onCompleteTap,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Chip extends StatelessWidget {
  const _Chip({required this.label, required this.color});
  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        label,
        style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: color,
              fontWeight: FontWeight.w600,
            ),
      ),
    );
  }
}
