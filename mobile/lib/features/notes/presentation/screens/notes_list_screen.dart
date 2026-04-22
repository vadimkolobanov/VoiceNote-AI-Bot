import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:voicenote_ai/core/router/app_routes.dart';
import 'package:voicenote_ai/features/notes/application/notes_controller.dart';
import 'package:voicenote_ai/features/notes/data/repositories/notes_repository.dart';
import 'package:voicenote_ai/features/notes/presentation/widgets/note_card.dart';
import 'package:voicenote_ai/features/voice/presentation/voice_bar.dart';
import 'package:voicenote_ai/shared/widgets/app_error.dart';
import 'package:voicenote_ai/shared/widgets/loading_shimmer.dart';

class NotesListScreen extends ConsumerStatefulWidget {
  const NotesListScreen({super.key});

  @override
  ConsumerState<NotesListScreen> createState() => _NotesListScreenState();
}

class _NotesListScreenState extends ConsumerState<NotesListScreen> {
  NotesSegment _segment = NotesSegment.active;
  final _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_maybeLoadMore);
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  void _maybeLoadMore() {
    if (_scrollController.position.pixels >=
        _scrollController.position.maxScrollExtent - 300) {
      ref.read(notesControllerProvider(_segment).notifier).loadMore();
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(notesControllerProvider(_segment));
    final controller = ref.read(notesControllerProvider(_segment).notifier);

    return Scaffold(
      appBar: AppBar(
        title: const Text('VoiceNote AI'),
        actions: [
          IconButton(
            icon: const Icon(Icons.search),
            onPressed: () => _openSearch(context),
          ),
        ],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(56),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
            child: SegmentedButton<NotesSegment>(
              style: SegmentedButton.styleFrom(
                visualDensity: VisualDensity.compact,
              ),
              segments: const [
                ButtonSegment(value: NotesSegment.active, label: Text('Активные')),
                ButtonSegment(value: NotesSegment.archive, label: Text('Архив')),
              ],
              selected: {_segment},
              onSelectionChanged: (s) => setState(() => _segment = s.first),
            ),
          ),
        ),
      ),
      body: Column(
        children: [
          Expanded(
            child: RefreshIndicator(
              onRefresh: controller.refresh,
              child: Builder(
                builder: (_) {
                  if (state.isLoading && state.items.isEmpty) {
                    return const ListCardSkeleton();
                  }
                  if (state.error != null && state.items.isEmpty) {
                    return AppErrorView(
                      error: state.error!,
                      onRetry: controller.refresh,
                    );
                  }
                  if (state.items.isEmpty) {
                    return LayoutBuilder(
                      builder: (ctx, c) => SingleChildScrollView(
                        physics: const AlwaysScrollableScrollPhysics(),
                        child: SizedBox(
                          height: c.maxHeight,
                          child: const EmptyStateView(
                            icon: Icons.note_alt_outlined,
                            title: 'Пока пусто',
                            subtitle:
                                'Нажмите на микрофон или введите текст, чтобы создать заметку',
                          ),
                        ),
                      ),
                    );
                  }
                  return ListView.separated(
                    controller: _scrollController,
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.all(16),
                    itemCount: state.items.length + (state.hasMore ? 1 : 0),
                    separatorBuilder: (_, __) => const SizedBox(height: 10),
                    itemBuilder: (_, i) {
                      if (i >= state.items.length) {
                        return const Padding(
                          padding: EdgeInsets.all(16),
                          child: Center(child: CircularProgressIndicator()),
                        );
                      }
                      final note = state.items[i];
                      return Dismissible(
                        key: ValueKey('note-${note.id}'),
                        background: _SwipeBg(
                          color: Theme.of(context).colorScheme.primary,
                          icon: Icons.archive_outlined,
                          alignment: Alignment.centerLeft,
                        ),
                        secondaryBackground: _SwipeBg(
                          color: Theme.of(context).colorScheme.error,
                          icon: Icons.delete_outline,
                          alignment: Alignment.centerRight,
                        ),
                        confirmDismiss: (dir) async {
                          if (dir == DismissDirection.endToStart) {
                            return await _confirmDelete(context);
                          }
                          return true;
                        },
                        onDismissed: (dir) {
                          if (dir == DismissDirection.endToStart) {
                            controller.deleteNote(note.id);
                          } else {
                            controller.archiveLocal(note.id);
                          }
                        },
                        child: NoteCard(
                          note: note,
                          onTap: () => context.push(AppRoutes.noteDetailFor(note.id)),
                          onCompleteTap: () => controller.completeNote(note.id),
                        ),
                      );
                    },
                  );
                },
              ),
            ),
          ),
          const VoiceBar(),
        ],
      ),
    );
  }

  Future<bool> _confirmDelete(BuildContext context) async {
    final result = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Удалить заметку?'),
        content: const Text('Это действие нельзя будет отменить.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Отмена')),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(ctx).colorScheme.error,
            ),
            child: const Text('Удалить'),
          ),
        ],
      ),
    );
    return result ?? false;
  }

  void _openSearch(BuildContext context) {
    showSearch<void>(
      context: context,
      delegate: _NotesSearchDelegate(ref),
    );
  }
}

class _SwipeBg extends StatelessWidget {
  const _SwipeBg({required this.color, required this.icon, required this.alignment});
  final Color color;
  final IconData icon;
  final Alignment alignment;

  @override
  Widget build(BuildContext context) {
    return Container(
      alignment: alignment,
      padding: const EdgeInsets.symmetric(horizontal: 24),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Icon(icon, color: Colors.white),
    );
  }
}

class _NotesSearchDelegate extends SearchDelegate<void> {
  _NotesSearchDelegate(this.ref);
  final WidgetRef ref;

  @override
  List<Widget> buildActions(BuildContext context) => [
        IconButton(icon: const Icon(Icons.clear), onPressed: () => query = ''),
      ];

  @override
  Widget buildLeading(BuildContext context) => IconButton(
        icon: const Icon(Icons.arrow_back),
        onPressed: () => close(context, null),
      );

  @override
  Widget buildResults(BuildContext context) {
    if (query.trim().isEmpty) return const Center(child: Text('Введите запрос'));
    final repo = ref.read(notesRepositoryProvider);
    return FutureBuilder(
      future: repo.search(query.trim()),
      builder: (_, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snap.hasError) {
          return AppErrorView(error: snap.error!);
        }
        final items = snap.data ?? const [];
        if (items.isEmpty) {
          return const EmptyStateView(
            icon: Icons.search_off,
            title: 'Ничего не найдено',
          );
        }
        return ListView.separated(
          padding: const EdgeInsets.all(16),
          itemCount: items.length,
          separatorBuilder: (_, __) => const SizedBox(height: 10),
          itemBuilder: (_, i) => NoteCard(
            note: items[i],
            onTap: () {
              close(context, null);
              context.push(AppRoutes.noteDetailFor(items[i].id));
            },
          ),
        );
      },
    );
  }

  @override
  Widget buildSuggestions(BuildContext context) => const Center(
        child: Text('AI-поиск по вашим заметкам'),
      );
}
