import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:voicenote_ai/core/router/app_routes.dart';
import 'package:voicenote_ai/core/theme/mx_tokens.dart';
import 'package:voicenote_ai/core/widgets/mx_widgets.dart';
import 'package:voicenote_ai/features/notes/application/notes_controller.dart';
import 'package:voicenote_ai/features/notes/data/models/note.dart';
import 'package:voicenote_ai/features/notes/data/repositories/notes_repository.dart';
import 'package:voicenote_ai/features/tasks/presentation/widgets/task_card.dart';
import 'package:voicenote_ai/shared/widgets/app_error.dart';
import 'package:voicenote_ai/shared/widgets/app_shell.dart';
import 'package:voicenote_ai/shared/widgets/loading_shimmer.dart';

/// Отдельный экран задач: та же сущность `notes`, но type=task.
/// Сортировка по due_date, визуальный акцент на просроченных/сегодняшних.
class TasksScreen extends ConsumerStatefulWidget {
  const TasksScreen({super.key});

  @override
  ConsumerState<TasksScreen> createState() => _TasksScreenState();
}

class _TasksScreenState extends ConsumerState<TasksScreen> {
  NotesSegment _segment = NotesSegment.active;
  final _scrollController = ScrollController();

  NotesQuery get _query => NotesQuery(segment: _segment, type: NoteType.task);

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

    return Scaffold(
      backgroundColor: MX.bgBase,
      drawer: const MethodexDrawer(),
      appBar: MxAppBar(
        title: 'Задачи',
        subtitle: state.items.isEmpty ? null : '${state.items.length} всего',
        actions: [
          IconButton(
            tooltip: 'Все напоминания',
            icon: const Icon(Icons.notifications_none, size: 22),
            onPressed: () => context.push(AppRoutes.allReminders),
          ),
          IconButton(icon: const Icon(Icons.add, size: 22), onPressed: () {}),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: MxFilterPills(
              selected: _segment == NotesSegment.active ? 'active' : 'archive',
              onSelected: (v) => setState(() =>
                  _segment = v == 'active' ? NotesSegment.active : NotesSegment.archive),
              items: const [
                MxFilterPill(value: 'active', label: 'Предстоящие'),
                MxFilterPill(value: 'archive', label: 'Выполнено'),
              ],
            ),
          ),
          Expanded(
            child: RefreshIndicator(
              onRefresh: controller.refresh,
              child: Builder(
                builder: (_) {
                  if (state.isLoading && state.items.isEmpty) {
                    return const ListCardSkeleton();
                  }
                  if (state.error != null && state.items.isEmpty) {
                    return AppErrorView(error: state.error!, onRetry: controller.refresh);
                  }
                  if (state.items.isEmpty) {
                    return LayoutBuilder(
                      builder: (_, c) => SingleChildScrollView(
                        physics: const AlwaysScrollableScrollPhysics(),
                        child: SizedBox(
                          height: c.maxHeight,
                          child: EmptyStateView(
                            icon: Icons.task_alt,
                            title: _segment == NotesSegment.active
                                ? 'Нет предстоящих задач'
                                : 'Нет выполненных задач',
                            subtitle: _segment == NotesSegment.active
                                ? 'Скажите: «Напомни завтра в 10 позвонить врачу»'
                                : null,
                          ),
                        ),
                      ),
                    );
                  }

                  // Группировка: сегодня / завтра / позже / просрочено
                  final sections = _groupByDate(state.items);
                  return ListView.builder(
                    controller: _scrollController,
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
                    itemCount: _countRows(sections) + (state.hasMore ? 1 : 0),
                    itemBuilder: (_, i) {
                      if (i >= _countRows(sections)) {
                        return const Padding(
                          padding: EdgeInsets.all(16),
                          child: Center(child: CircularProgressIndicator()),
                        );
                      }
                      return _buildRow(context, sections, i, controller);
                    },
                  );
                },
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ---- Grouping helpers ----

  Map<String, List<Note>> _groupByDate(List<Note> items) {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final tomorrow = today.add(const Duration(days: 1));

    final overdue = <Note>[];
    final todayList = <Note>[];
    final tomorrowList = <Note>[];
    final later = <Note>[];
    final noDate = <Note>[];

    for (final t in items) {
      final d = t.dueDate;
      if (d == null) {
        noDate.add(t);
        continue;
      }
      final tDay = DateTime(d.year, d.month, d.day);
      if (t.isCompleted) {
        later.add(t); // для архива
      } else if (tDay.isBefore(today)) {
        overdue.add(t);
      } else if (tDay == today) {
        todayList.add(t);
      } else if (tDay == tomorrow) {
        tomorrowList.add(t);
      } else {
        later.add(t);
      }
    }

    return {
      if (overdue.isNotEmpty) 'Просрочено': overdue,
      if (todayList.isNotEmpty) 'Сегодня': todayList,
      if (tomorrowList.isNotEmpty) 'Завтра': tomorrowList,
      if (later.isNotEmpty) 'Позже': later,
      if (noDate.isNotEmpty) 'Без срока': noDate,
    };
  }

  int _countRows(Map<String, List<Note>> sections) {
    int count = 0;
    for (final l in sections.values) {
      count += 1 + l.length;
    }
    return count;
  }

  Widget _buildRow(
    BuildContext context,
    Map<String, List<Note>> sections,
    int index,
    NotesController controller,
  ) {
    int cursor = 0;
    for (final entry in sections.entries) {
      if (index == cursor) {
        return Padding(
          padding: const EdgeInsets.fromLTRB(4, 12, 4, 6),
          child: Text(
            entry.key.toUpperCase(),
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  fontWeight: FontWeight.w800,
                  color: entry.key == 'Просрочено'
                      ? Theme.of(context).colorScheme.error
                      : Theme.of(context).colorScheme.primary,
                  letterSpacing: 1.2,
                ),
          ),
        );
      }
      cursor++;
      for (final task in entry.value) {
        if (index == cursor) {
          return Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: TaskCard(
              task: task,
              onTap: () => context.push(AppRoutes.noteDetailFor(task.id)),
              onCompleteTap: () => controller.completeNote(task.id),
              onPostponeDay: () => _postpone(task, const Duration(days: 1), controller),
              onPostponeWeek: () => _postpone(task, const Duration(days: 7), controller),
              onClearDueDate: () => _clearDueDate(task, controller),
            ),
          );
        }
        cursor++;
      }
    }
    return const SizedBox.shrink();
  }

  Future<void> _postpone(
    Note task,
    Duration delta,
    NotesController controller,
  ) async {
    final base = task.dueDate ?? DateTime.now();
    // при переносе из прошлого стартуем от сегодняшнего 9:00 локального времени
    final now = DateTime.now();
    final anchor = base.isBefore(now) ? DateTime(now.year, now.month, now.day, 9) : base;
    final newDue = anchor.add(delta);
    try {
      final updated = await ref.read(notesRepositoryProvider).patch(
            task.id,
            dueDate: newDue,
          );
      controller.upsert(updated);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Не удалось перенести: $e')),
        );
      }
    }
  }

  Future<void> _clearDueDate(Note task, NotesController controller) async {
    try {
      await ref.read(notesRepositoryProvider).patch(
            task.id,
            clearDueDate: true,
            clearRecurrence: true,
            type: 'note',
          );
      // пропадёт из этого списка — refresh подтянет актуальное состояние
      controller.archiveLocal(task.id);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Не удалось снять дату: $e')),
        );
      }
    }
  }
}
