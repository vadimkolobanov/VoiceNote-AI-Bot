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
      await ref.read(notesRepositoryProvider).update(widget.noteId, _text.text);
      if (!mounted) return;
      ref.invalidate(_noteProvider(widget.noteId));
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Сохранено')),
      );
      setState(() => _dirty = false);
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _complete() async {
    try {
      await ref.read(notesRepositoryProvider).complete(widget.noteId);
      if (!mounted) return;
      ref.invalidate(_noteProvider(widget.noteId));
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
      }
    }
  }

  Future<void> _delete() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Удалить заметку?'),
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
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(_noteProvider(widget.noteId));

    return Scaffold(
      appBar: AppBar(
        title: const Text('Заметка'),
        actions: [
          if (_dirty && !_saving)
            TextButton(onPressed: _save, child: const Text('Сохранить')),
          if (_saving)
            const Padding(
              padding: EdgeInsets.all(14),
              child: SizedBox(
                width: 20,
                height: 20,
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
              Row(
                children: [
                  if (note.category != null)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: Theme.of(context).colorScheme.primaryContainer,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        note.category!,
                        style: Theme.of(context).textTheme.labelSmall?.copyWith(
                              fontWeight: FontWeight.w600,
                            ),
                      ),
                    ),
                  const Spacer(),
                  Text(
                    DateFormatter.relative(note.createdAt),
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
              if (note.dueDate != null) ...[
                const SizedBox(height: 12),
                Row(
                  children: [
                    const Icon(Icons.schedule, size: 18),
                    const SizedBox(width: 6),
                    Text(DateFormatter.smartDate(note.dueDate!)),
                    if (note.recurrenceRule != null) ...[
                      const SizedBox(width: 10),
                      const Icon(Icons.repeat, size: 18),
                      const SizedBox(width: 4),
                      Text(note.recurrenceRule!),
                    ],
                  ],
                ),
              ],
              const SizedBox(height: 20),
              TextField(
                controller: _text,
                maxLines: null,
                minLines: 6,
                onChanged: (v) {
                  final isDirty = v != note.correctedText;
                  if (isDirty != _dirty) {
                    setState(() => _dirty = isDirty);
                  }
                },
                decoration: const InputDecoration(
                  hintText: 'Текст заметки',
                ),
              ),
              const SizedBox(height: 24),
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
            ],
          );
        },
      ),
    );
  }
}
