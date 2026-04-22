import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/features/notes/application/notes_controller.dart';
import 'package:voicenote_ai/features/notes/data/models/note.dart';
import 'package:voicenote_ai/features/notes/data/repositories/notes_repository.dart';

class CreateNoteScreen extends ConsumerStatefulWidget {
  const CreateNoteScreen({super.key});

  @override
  ConsumerState<CreateNoteScreen> createState() => _CreateNoteScreenState();
}

class _CreateNoteScreenState extends ConsumerState<CreateNoteScreen> {
  final _text = TextEditingController();
  bool _saving = false;

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final text = _text.text.trim();
    if (text.isEmpty) return;
    setState(() => _saving = true);
    try {
      final note = await ref.read(notesRepositoryProvider).create(text);
      if (!mounted) return;
      final query = NotesQuery(segment: NotesSegment.active, type: note.type);
      ref.read(notesControllerProvider(query).notifier).upsert(note);
      context.pop();
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Новая заметка'),
        actions: [
          TextButton(
            onPressed: _saving ? null : _save,
            child: _saving
                ? const SizedBox(
                    width: 16, height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text('Создать'),
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: TextField(
          controller: _text,
          autofocus: true,
          maxLines: null,
          minLines: 8,
          textCapitalization: TextCapitalization.sentences,
          decoration: const InputDecoration(
            hintText: 'Что у вас на уме?..\n\nНапример: «Купить молоко завтра в 18:00»',
          ),
        ),
      ),
    );
  }
}
