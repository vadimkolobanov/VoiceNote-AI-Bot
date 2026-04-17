import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/features/notes/application/notes_controller.dart';
import 'package:voicenote_ai/features/notes/data/models/note.dart';
import 'package:voicenote_ai/features/notes/data/repositories/notes_repository.dart';
import 'package:voicenote_ai/features/voice/application/voice_recorder_controller.dart';

class VoiceBar extends ConsumerStatefulWidget {
  const VoiceBar({super.key, this.onCreated});

  final ValueChanged<Note>? onCreated;

  @override
  ConsumerState<VoiceBar> createState() => _VoiceBarState();
}

class _VoiceBarState extends ConsumerState<VoiceBar>
    with SingleTickerProviderStateMixin {
  final _controller = TextEditingController();
  late final AnimationController _pulse =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 900))
        ..repeat(reverse: true);
  bool _sending = false;

  @override
  void dispose() {
    _controller.dispose();
    _pulse.dispose();
    super.dispose();
  }

  Future<void> _sendText() async {
    final text = _controller.text.trim();
    if (text.isEmpty || _sending) return;
    setState(() => _sending = true);
    try {
      final note = await ref.read(notesRepositoryProvider).create(text);
      _controller.clear();
      widget.onCreated?.call(note);
      ref.read(notesControllerProvider(NotesSegment.active).notifier).upsert(note);
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Не удалось создать заметку')),
        );
      }
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  Future<void> _onMicLongPress() async {
    await ref.read(voiceRecorderProvider.notifier).start();
  }

  Future<void> _onMicRelease() async {
    final voice = ref.read(voiceRecorderProvider.notifier);
    final note = await voice.stopAndUpload();
    if (note != null) {
      widget.onCreated?.call(note);
      ref.read(notesControllerProvider(NotesSegment.active).notifier).upsert(note);
    } else {
      final err = ref.read(voiceRecorderProvider).error;
      if (mounted && err != null) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(err)));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(voiceRecorderProvider);
    final scheme = Theme.of(context).colorScheme;
    final isRecording = state.status == VoiceRecorderStatus.recording;
    final isProcessing = state.status == VoiceRecorderStatus.processing;

    return Material(
      color: scheme.surface,
      elevation: 8,
      shadowColor: Colors.black.withValues(alpha: 0.08),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
          child: Row(
            children: [
              GestureDetector(
                onLongPressStart: (_) => _onMicLongPress(),
                onLongPressEnd: (_) => _onMicRelease(),
                child: AnimatedBuilder(
                  animation: _pulse,
                  builder: (_, __) {
                    final scale = isRecording ? 1.0 + _pulse.value * 0.2 : 1.0;
                    return Transform.scale(
                      scale: scale,
                      child: Container(
                        width: 52,
                        height: 52,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: isRecording ? scheme.error : scheme.primary,
                          boxShadow: [
                            if (isRecording)
                              BoxShadow(
                                color: scheme.error.withValues(alpha: 0.35),
                                blurRadius: 16,
                                spreadRadius: 2,
                              ),
                          ],
                        ),
                        child: isProcessing
                            ? const Center(
                                child: SizedBox(
                                  width: 20,
                                  height: 20,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                    color: Colors.white,
                                  ),
                                ),
                              )
                            : const Icon(Icons.mic, color: Colors.white, size: 26),
                      ),
                    );
                  },
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: TextField(
                  controller: _controller,
                  minLines: 1,
                  maxLines: 4,
                  enabled: !isRecording,
                  textCapitalization: TextCapitalization.sentences,
                  decoration: InputDecoration(
                    hintText: isRecording ? 'Идёт запись…' : 'Напишите заметку',
                    contentPadding:
                        const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                  ),
                  onSubmitted: (_) => _sendText(),
                ),
              ),
              const SizedBox(width: 6),
              IconButton.filled(
                onPressed: _sending ? null : _sendText,
                icon: _sending
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      )
                    : const Icon(Icons.send_rounded),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
