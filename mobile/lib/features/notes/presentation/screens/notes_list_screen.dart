import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import 'package:voicenote_ai/core/router/app_routes.dart';
import 'package:voicenote_ai/core/theme/mx_tokens.dart';
import 'package:voicenote_ai/core/widgets/mx_widgets.dart';
import 'package:voicenote_ai/features/notes/application/notes_controller.dart';
import 'package:voicenote_ai/features/notes/data/models/note.dart';
import 'package:voicenote_ai/features/notes/data/repositories/notes_repository.dart';
import 'package:voicenote_ai/shared/widgets/app_error.dart';
import 'package:voicenote_ai/shared/widgets/app_shell.dart';

class NotesListScreen extends ConsumerStatefulWidget {
  const NotesListScreen({super.key});

  @override
  ConsumerState<NotesListScreen> createState() => _NotesListScreenState();
}

class _NotesListScreenState extends ConsumerState<NotesListScreen> {
  NotesSegment _segment = NotesSegment.active;
  String _filter = 'all';
  final _scrollController = ScrollController();

  NotesQuery get _query =>
      NotesQuery(segment: _segment, type: NoteType.note);

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(() {
      if (_scrollController.position.pixels >=
          _scrollController.position.maxScrollExtent - 300) {
        ref.read(notesControllerProvider(_query).notifier).loadMore();
      }
    });
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(notesControllerProvider(_query));
    final controller = ref.read(notesControllerProvider(_query).notifier);
    final notes = _applyFilter(state.items);

    return Scaffold(
      backgroundColor: MX.bgBase,
      drawer: const MethodexDrawer(),
      appBar: MxAppBar(
        title: 'Заметки',
        subtitle: state.items.isEmpty ? null : '${state.items.length} всего',
        actions: [
          IconButton(
            icon: const Icon(Icons.search, size: 22),
            onPressed: () => _openSearch(context),
          ),
          IconButton(
            icon: const Icon(Icons.more_vert, size: 22),
            onPressed: () {},
          ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: MxFilterPills(
              selected: _filter,
              onSelected: (v) => setState(() => _filter = v),
              items: [
                MxFilterPill(value: 'all', label: 'Все', count: state.items.length),
                MxFilterPill(
                  value: 'reminder',
                  label: 'С напоминанием',
                  count: state.items.where((n) => n.dueDate != null).length,
                ),
                MxFilterPill(value: 'archive', label: 'Архив'),
              ],
            ),
          ),
          Expanded(
            child: RefreshIndicator(
              onRefresh: controller.refresh,
              child: _buildBody(state, notes, controller),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBody(NotesListState state, List<Note> notes, NotesController c) {
    if (state.isLoading && state.items.isEmpty) {
      return const _NotesSkeleton();
    }
    if (state.error != null && state.items.isEmpty) {
      return AppErrorView(error: state.error!, onRetry: c.refresh);
    }
    if (notes.isEmpty) {
      return LayoutBuilder(
        builder: (_, bc) => SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          child: SizedBox(
            height: bc.maxHeight,
            child: const MxEmptyState(
              icon: Icons.edit_note_outlined,
              title: 'Пока пусто',
              subtitle: 'Нажмите микрофон внизу, чтобы быстро записать мысль.',
            ),
          ),
        ),
      );
    }
    return ListView.separated(
      controller: _scrollController,
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.fromLTRB(20, 0, 20, 120),
      itemCount: notes.length + (state.hasMore ? 1 : 0),
      separatorBuilder: (_, __) => const SizedBox(height: 10),
      itemBuilder: (_, i) {
        if (i >= notes.length) {
          return const Padding(
            padding: EdgeInsets.all(16),
            child: Center(child: CircularProgressIndicator(color: MX.accentAi)),
          );
        }
        final note = notes[i];
        return _NoteCardMx(
          note: note,
          onTap: () => context.push(AppRoutes.noteDetailFor(note.id)),
          onComplete: () => c.completeNote(note.id),
        );
      },
    );
  }

  List<Note> _applyFilter(List<Note> all) {
    switch (_filter) {
      case 'reminder':
        return all.where((n) => n.dueDate != null).toList();
      case 'archive':
        return all.where((n) => n.isArchived).toList();
      default:
        return all;
    }
  }

  void _openSearch(BuildContext context) {
    showSearch<void>(context: context, delegate: _NotesSearchDelegate(ref));
  }
}

// ═══════════════════════════════════════════════════════════════════════════

class _NoteCardMx extends StatelessWidget {
  const _NoteCardMx({
    required this.note,
    required this.onTap,
    required this.onComplete,
  });
  final Note note;
  final VoidCallback onTap;
  final VoidCallback onComplete;

  IconData get _icon {
    if (note.isShoppingList) return Icons.shopping_cart_outlined;
    if (note.isTask) return Icons.task_alt;
    return Icons.edit_note;
  }

  String get _timeAgo {
    final diff = DateTime.now().difference(note.createdAt);
    if (diff.inMinutes < 60) return '${diff.inMinutes} мин';
    if (diff.inHours < 24) return '${diff.inHours} ч';
    if (diff.inDays == 1) return 'Вчера';
    if (diff.inDays < 7) return '${diff.inDays} дн';
    return DateFormat('d MMM', 'ru').format(note.createdAt);
  }

  @override
  Widget build(BuildContext context) {
    return MxCard(
      onTap: onTap,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(_icon, size: 13, color: MX.fgMuted),
              const SizedBox(width: 6),
              if (note.category != null)
                Text(
                  note.category!.toUpperCase(),
                  style: const TextStyle(
                    color: MX.fgMicro, fontSize: 10,
                    fontWeight: FontWeight.w700, letterSpacing: 1.2,
                  ),
                ),
              const Spacer(),
              Text(_timeAgo,
                  style: const TextStyle(color: MX.fgMicro, fontSize: 11)),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            note.summaryText?.isNotEmpty == true
                ? note.summaryText!
                : note.correctedText,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: MX.fg, fontSize: 15, fontWeight: FontWeight.w600,
              height: 1.3, letterSpacing: -0.1,
            ),
          ),
          if ((note.summaryText ?? '').isNotEmpty &&
              note.correctedText != note.summaryText) ...[
            const SizedBox(height: 6),
            Text(
              note.correctedText,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: MX.fgMuted, fontSize: 13, height: 1.45,
              ),
            ),
          ],
          if (note.dueDate != null) ...[
            const SizedBox(height: 10),
            MxBadge(
              icon: Icons.notifications_active_outlined,
              label: DateFormat('EEE HH:mm', 'ru').format(note.dueDate!.toLocal()),
              accent: MxAccent.ai,
            ),
          ],
        ],
      ),
    );
  }
}

class _NotesSkeleton extends StatelessWidget {
  const _NotesSkeleton();
  @override
  Widget build(BuildContext context) {
    return ListView.separated(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      itemCount: 5,
      physics: const NeverScrollableScrollPhysics(),
      separatorBuilder: (_, __) => const SizedBox(height: 10),
      itemBuilder: (_, __) => Container(
        height: 100,
        decoration: BoxDecoration(
          color: MX.surfaceOverlay,
          borderRadius: BorderRadius.circular(MX.rLg),
          border: Border.all(color: MX.line),
        ),
      ),
    );
  }
}

class _NotesSearchDelegate extends SearchDelegate<void> {
  _NotesSearchDelegate(this.ref);
  final WidgetRef ref;

  @override
  List<Widget> buildActions(BuildContext context) =>
      [IconButton(icon: const Icon(Icons.clear), onPressed: () => query = '')];

  @override
  Widget buildLeading(BuildContext context) => IconButton(
        icon: const Icon(Icons.arrow_back),
        onPressed: () => close(context, null),
      );

  @override
  Widget buildResults(BuildContext context) {
    if (query.trim().isEmpty) {
      return const MxEmptyState(
        icon: Icons.search,
        title: 'Введите запрос',
        subtitle: 'AI-поиск по всем заметкам',
      );
    }
    final repo = ref.read(notesRepositoryProvider);
    return FutureBuilder(
      future: repo.search(query.trim()),
      builder: (_, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator(color: MX.accentAi));
        }
        if (snap.hasError) return AppErrorView(error: snap.error!);
        final items = snap.data ?? const [];
        if (items.isEmpty) {
          return const MxEmptyState(icon: Icons.search_off, title: 'Ничего не найдено');
        }
        return ListView.separated(
          padding: const EdgeInsets.all(20),
          itemCount: items.length,
          separatorBuilder: (_, __) => const SizedBox(height: 10),
          itemBuilder: (_, i) => _NoteCardMx(
            note: items[i],
            onTap: () {
              close(context, null);
              (context).push(AppRoutes.noteDetailFor(items[i].id));
            },
            onComplete: () {},
          ),
        );
      },
    );
  }

  @override
  Widget buildSuggestions(BuildContext context) => const MxEmptyState(
        icon: Icons.search,
        title: 'AI-поиск по заметкам',
        subtitle: 'Опишите что ищете — найду по смыслу.',
      );
}
