import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/utils/date_formatter.dart';
import 'package:voicenote_ai/features/notes/data/models/note.dart';
import 'package:voicenote_ai/features/notes/data/repositories/notes_repository.dart';
import 'package:voicenote_ai/shared/widgets/app_error.dart';

final _noteProvider = FutureProvider.family.autoDispose<Note, int>(
  (ref, id) => ref.watch(notesRepositoryProvider).getById(id),
);

/// Экран детали заметки/задачи с редактируемыми полями.
///
/// Поддерживает:
///  — inline-редактирование текста (с явной кнопкой «Сохранить»)
///  — смену категории через dropdown (пресеты + свободный ввод)
///  — смену типа (note↔task↔idea) через chips
///  — назначение/изменение/снятие due_date через DatePicker+TimePicker
///  — выбор recurrence (нет / ежедневно / еженедельно / ежемесячно / ежегодно)
///  — действия: выполнить, архивировать (разархивировать), удалить
class NoteDetailScreen extends ConsumerStatefulWidget {
  const NoteDetailScreen({required this.noteId, super.key});
  final int noteId;

  @override
  ConsumerState<NoteDetailScreen> createState() => _NoteDetailScreenState();
}

class _NoteDetailScreenState extends ConsumerState<NoteDetailScreen> {
  final _text = TextEditingController();
  bool _dirty = false;
  bool _saving = false;
  Note? _loaded;

  static const _categoryPresets = <String>[
    'Общее',
    'Задачи',
    'Идея',
    'Работа',
    'Личное',
    'Семья',
    'Здоровье',
    'Покупки',
  ];

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  void _syncController(Note n) {
    if (_loaded?.id != n.id || _loaded?.correctedText != n.correctedText) {
      _text.text = n.correctedText;
      _loaded = n;
      _dirty = false;
    }
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    try {
      await ref.read(notesRepositoryProvider).patch(
            widget.noteId,
            text: _text.text,
          );
      ref.invalidate(_noteProvider(widget.noteId));
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Сохранено')),
      );
      setState(() => _dirty = false);
    } on ApiException catch (e) {
      _snack(e.message);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _patchField({
    String? category,
    String? type,
    DateTime? dueDate,
    bool clearDueDate = false,
    String? recurrenceRule,
    bool clearRecurrence = false,
  }) async {
    try {
      await ref.read(notesRepositoryProvider).patch(
            widget.noteId,
            category: category,
            type: type,
            dueDate: dueDate,
            clearDueDate: clearDueDate,
            recurrenceRule: recurrenceRule,
            clearRecurrence: clearRecurrence,
          );
      ref.invalidate(_noteProvider(widget.noteId));
    } on ApiException catch (e) {
      _snack(e.message);
    }
  }

  Future<void> _complete() async {
    try {
      await ref.read(notesRepositoryProvider).complete(widget.noteId);
      if (!mounted) return;
      ref.invalidate(_noteProvider(widget.noteId));
    } on ApiException catch (e) {
      _snack(e.message);
    }
  }

  Future<void> _delete() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Удалить?'),
        content: const Text('Это действие нельзя будет отменить.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Отмена')),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: Theme.of(ctx).colorScheme.error),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Удалить'),
          ),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await ref.read(notesRepositoryProvider).delete(widget.noteId);
      if (mounted) context.pop();
    } on ApiException catch (e) {
      _snack(e.message);
    }
  }

  Future<void> _pickDueDate(Note note) async {
    final now = DateTime.now();
    final initialDate = note.dueDate ?? now.add(const Duration(hours: 1));
    final pickedDate = await showDatePicker(
      context: context,
      initialDate: initialDate,
      firstDate: now.subtract(const Duration(days: 1)),
      lastDate: DateTime(now.year + 5),
    );
    if (pickedDate == null || !mounted) return;
    final pickedTime = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.fromDateTime(initialDate),
    );
    if (pickedTime == null) return;
    final combined = DateTime(
      pickedDate.year, pickedDate.month, pickedDate.day,
      pickedTime.hour, pickedTime.minute,
    );
    await _patchField(dueDate: combined, type: 'task');
  }

  Future<void> _clearDueDate() async {
    await _patchField(clearDueDate: true, clearRecurrence: true, type: 'note');
  }

  void _snack(String msg) {
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(_noteProvider(widget.noteId));

    return Scaffold(
      appBar: AppBar(
        title: Text(async.valueOrNull?.isTask == true ? 'Задача' : 'Заметка'),
        actions: [
          if (_dirty && !_saving)
            TextButton(onPressed: _save, child: const Text('Сохранить')),
          if (_saving)
            const Padding(
              padding: EdgeInsets.all(14),
              child: SizedBox(
                width: 20, height: 20,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            ),
        ],
      ),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => AppErrorView(
          error: e,
          onRetry: () => ref.invalidate(_noteProvider(widget.noteId)),
        ),
        data: (note) {
          _syncController(note);
          return ListView(
            padding: const EdgeInsets.all(20),
            children: [
              _TypeSelector(
                current: note.type,
                onChanged: (t) => _patchField(type: t.apiValue),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _text,
                maxLines: null,
                minLines: 6,
                onChanged: (v) {
                  final isDirty = v != note.correctedText;
                  if (isDirty != _dirty) setState(() => _dirty = isDirty);
                },
                decoration: const InputDecoration(
                  labelText: 'Текст',
                  alignLabelWithHint: true,
                ),
              ),
              const SizedBox(height: 24),
              _MetaSection(
                title: 'Дата и время',
                children: [
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: const Icon(Icons.schedule),
                    title: Text(note.dueDate == null
                        ? 'Без срока'
                        : DateFormatter.smartDate(note.dueDate!)),
                    trailing: note.dueDate == null
                        ? FilledButton.tonal(
                            onPressed: () => _pickDueDate(note),
                            child: const Text('Назначить'),
                          )
                        : Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              IconButton(
                                icon: const Icon(Icons.edit_outlined),
                                tooltip: 'Изменить',
                                onPressed: () => _pickDueDate(note),
                              ),
                              IconButton(
                                icon: const Icon(Icons.close),
                                tooltip: 'Убрать дату',
                                onPressed: _clearDueDate,
                              ),
                            ],
                          ),
                  ),
                  if (note.dueDate != null) ...[
                    const Divider(),
                    _RecurrenceSelector(
                      current: note.recurrenceRule,
                      onChanged: (rule) async {
                        if (rule == null) {
                          await _patchField(clearRecurrence: true);
                        } else {
                          await _patchField(recurrenceRule: rule);
                        }
                      },
                    ),
                  ],
                ],
              ),
              const SizedBox(height: 16),
              _MetaSection(
                title: 'Категория',
                children: [
                  _CategoryChips(
                    current: note.category,
                    presets: _categoryPresets,
                    onChanged: (c) => _patchField(category: c),
                  ),
                ],
              ),
              const SizedBox(height: 28),
              Wrap(
                spacing: 12,
                runSpacing: 12,
                children: [
                  FilledButton.icon(
                    onPressed: note.isCompleted ? null : _complete,
                    icon: const Icon(Icons.check),
                    label: Text(note.isCompleted ? 'Выполнено' : 'Выполнить'),
                  ),
                  OutlinedButton.icon(
                    onPressed: _delete,
                    icon: const Icon(Icons.delete_outline),
                    label: const Text('Удалить'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: Theme.of(context).colorScheme.error,
                      side: BorderSide(color: Theme.of(context).colorScheme.error),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 20),
              Text(
                'Создано ${DateFormatter.relative(note.createdAt)}',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
              ),
            ],
          );
        },
      ),
    );
  }
}

// ============================================================
// Sub-widgets
// ============================================================

class _TypeSelector extends StatelessWidget {
  const _TypeSelector({required this.current, required this.onChanged});
  final NoteType current;
  final ValueChanged<NoteType> onChanged;

  @override
  Widget build(BuildContext context) {
    return SegmentedButton<NoteType>(
      style: SegmentedButton.styleFrom(visualDensity: VisualDensity.compact),
      segments: const [
        ButtonSegment(
          value: NoteType.note,
          label: Text('Заметка'),
          icon: Icon(Icons.note_alt_outlined),
        ),
        ButtonSegment(
          value: NoteType.task,
          label: Text('Задача'),
          icon: Icon(Icons.task_alt),
        ),
        ButtonSegment(
          value: NoteType.idea,
          label: Text('Идея'),
          icon: Icon(Icons.lightbulb_outline),
        ),
      ],
      selected: {current == NoteType.shopping ? NoteType.note : current},
      onSelectionChanged: (s) => onChanged(s.first),
    );
  }
}

class _RecurrenceSelector extends StatelessWidget {
  const _RecurrenceSelector({required this.current, required this.onChanged});
  final String? current;
  final ValueChanged<String?> onChanged;

  static const _options = <(String, String?)>[
    ('Не повторять', null),
    ('Каждый день', 'FREQ=DAILY'),
    ('Каждую неделю', 'FREQ=WEEKLY'),
    ('Каждый месяц', 'FREQ=MONTHLY'),
    ('Каждый год', 'FREQ=YEARLY'),
  ];

  String _labelForCurrent() {
    if (current == null || current!.isEmpty) return 'Не повторять';
    final found = _options.firstWhere(
      (o) => o.$2 == current,
      orElse: () => ('Произвольный RRULE', current),
    );
    return found.$1;
  }

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: const Icon(Icons.repeat),
      title: const Text('Повторение'),
      subtitle: Text(_labelForCurrent()),
      trailing: const Icon(Icons.chevron_right),
      onTap: () async {
        final picked = await showModalBottomSheet<String?>(
          context: context,
          builder: (ctx) => SafeArea(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                for (final opt in _options)
                  RadioListTile<String?>(
                    title: Text(opt.$1),
                    value: opt.$2,
                    groupValue: current,
                    onChanged: (v) => Navigator.pop(ctx, v),
                  ),
              ],
            ),
          ),
        );
        if (picked != current) onChanged(picked);
      },
    );
  }
}

class _CategoryChips extends StatelessWidget {
  const _CategoryChips({
    required this.current,
    required this.presets,
    required this.onChanged,
  });
  final String? current;
  final List<String> presets;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 8,
      runSpacing: 6,
      children: [
        for (final preset in presets)
          ChoiceChip(
            label: Text(preset),
            selected: (current ?? '').toLowerCase() == preset.toLowerCase(),
            onSelected: (_) => onChanged(preset),
          ),
      ],
    );
  }
}

class _MetaSection extends StatelessWidget {
  const _MetaSection({required this.title, required this.children});
  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(14, 10, 14, 10),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: Theme.of(context).colorScheme.outlineVariant.withValues(alpha: 0.4),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title.toUpperCase(),
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  fontWeight: FontWeight.w700,
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                  letterSpacing: 1.2,
                ),
          ),
          const SizedBox(height: 4),
          ...children,
        ],
      ),
    );
  }
}
