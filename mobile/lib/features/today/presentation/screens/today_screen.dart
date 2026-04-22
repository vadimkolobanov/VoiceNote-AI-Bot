import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import 'package:voicenote_ai/core/router/app_routes.dart';
import 'package:voicenote_ai/core/theme/mx_tokens.dart';
import 'package:voicenote_ai/core/utils/date_formatter.dart';
import 'package:voicenote_ai/core/widgets/mx_widgets.dart';
import 'package:voicenote_ai/features/auth/application/session_controller.dart';
import 'package:voicenote_ai/features/habits/application/habits_controller.dart';
import 'package:voicenote_ai/features/habits/data/models/habit.dart';
import 'package:voicenote_ai/features/notes/application/notes_controller.dart';
import 'package:voicenote_ai/features/notes/data/models/note.dart';
import 'package:voicenote_ai/features/notes/data/repositories/notes_repository.dart';
import 'package:voicenote_ai/features/tasks/data/models/reminder.dart';
import 'package:voicenote_ai/features/tasks/data/repositories/reminders_repository.dart';
import 'package:voicenote_ai/shared/widgets/app_shell.dart';

/// «Сегодня» — dashboard. Первый экран после входа. Соответствует макету
/// ScreenToday: AI greeting, 3 статы, напоминания (rows со stripe), привычки
/// (check-list внутри карточки) и последние заметки.
class TodayScreen extends ConsumerWidget {
  const TodayScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(sessionControllerProvider);
    final remindersAsync = ref.watch(allRemindersProvider);
    final habitsAsync = ref.watch(habitsListProvider);
    final notesState = ref.watch(
      notesControllerProvider(const NotesQuery(
        segment: NotesSegment.active, type: NoteType.note,
      )),
    );

    final now = DateTime.now();
    final weekday = DateFormat('EEE, d MMMM', 'ru').format(now);
    final name = session.user?.firstName ?? 'друг';
    final isVip = session.user?.isVip ?? false;

    return Scaffold(
      backgroundColor: MX.bgBase,
      drawer: const MethodexDrawer(),
      appBar: MxAppBar(
        title: 'Сегодня',
        subtitle: _capitalize(weekday),
        actions: [
          IconButton(
            icon: const Icon(Icons.search, size: 22),
            onPressed: () {},
          ),
          IconButton(
            icon: const Icon(Icons.notifications_none, size: 22),
            onPressed: () => context.push(AppRoutes.allReminders),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(allRemindersProvider);
          ref.invalidate(habitsListProvider);
        },
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 120),
          children: [
            _AiGreetingCard(name: name, isVip: isVip),
            _StatsRow(
              tasksCount: _countToday(remindersAsync.valueOrNull),
              habitsDone: _countHabitsDone(habitsAsync.valueOrNull),
              habitsTotal: habitsAsync.valueOrNull?.length ?? 0,
              notesCount: notesState.items.length,
            ),
            MxSectionTitle(
              label: 'Напоминания',
              meta: remindersAsync.valueOrNull == null
                  ? null
                  : '${_countToday(remindersAsync.valueOrNull)} на сегодня',
              trailing: TextButton(
                onPressed: () => context.go(AppRoutes.tasks),
                child: const Text('Все',
                    style: TextStyle(color: MX.fgMuted, fontSize: 12)),
              ),
            ),
            remindersAsync.when(
              loading: () => const _SkeletonBlock(lines: 3),
              error: (_, __) => const MxEmptyState(
                icon: Icons.error_outline,
                title: 'Не удалось загрузить',
              ),
              data: (all) {
                final today = _filterToday(all);
                if (today.isEmpty) {
                  return const MxEmptyState(
                    icon: Icons.check_circle_outline,
                    title: 'Сегодня свободно',
                    subtitle: 'Можно позволить себе что-то хорошее.',
                  );
                }
                return Column(
                  children: [
                    for (final r in today.take(4))
                      Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: MxReminderRow(
                          time: DateFormat('HH:mm').format(r.nextFireAt!.toLocal()),
                          title: r.title,
                          accent: _accentFor(r),
                          repeat: r.isRecurring,
                        ),
                      ),
                  ],
                );
              },
            ),
            MxSectionTitle(
              label: 'Привычки',
              meta: habitsAsync.valueOrNull == null
                  ? null
                  : '${_countHabitsDone(habitsAsync.valueOrNull)} из ${habitsAsync.valueOrNull?.length ?? 0}',
              trailing: TextButton(
                onPressed: () => context.go(AppRoutes.habits),
                child: const Text('Все',
                    style: TextStyle(color: MX.fgMuted, fontSize: 12)),
              ),
            ),
            habitsAsync.when(
              loading: () => const _SkeletonBlock(lines: 2),
              error: (_, __) => const SizedBox.shrink(),
              data: (habits) {
                if (habits.isEmpty) {
                  return const MxEmptyState(
                    icon: Icons.repeat,
                    title: 'Пока нет привычек',
                    subtitle: 'Создайте первую — начнём трекать.',
                  );
                }
                return MxCard(
                  padding: const EdgeInsets.all(14),
                  child: Column(
                    children: [
                      for (var i = 0; i < habits.length && i < 5; i++) ...[
                        _HabitChecklistRow(habit: habits[i]),
                        if (i < habits.length - 1 && i < 4)
                          const Divider(color: MX.lineFaint, height: 20, thickness: 0.5),
                      ],
                    ],
                  ),
                );
              },
            ),
            MxSectionTitle(
              label: 'Недавно',
              meta: 'Последние заметки',
              trailing: TextButton(
                onPressed: () => context.go(AppRoutes.notes),
                child: const Text('Все',
                    style: TextStyle(color: MX.fgMuted, fontSize: 12)),
              ),
            ),
            if (notesState.items.isEmpty)
              const MxEmptyState(
                icon: Icons.edit_note_outlined,
                title: 'Записей пока нет',
                subtitle: 'Нажмите микрофон внизу, чтобы быстро записать мысль.',
              )
            else
              Column(
                children: [
                  for (final n in notesState.items.take(3))
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: _TodayNoteRow(
                        note: n,
                        onTap: () => context.push(AppRoutes.noteDetailFor(n.id)),
                      ),
                    ),
                ],
              ),
          ],
        ),
      ),
    );
  }

  static String _capitalize(String s) =>
      s.isEmpty ? s : s[0].toUpperCase() + s.substring(1);

  static MxAccent _accentFor(Reminder r) => switch (r.entityType) {
        ReminderEntityType.note => MxAccent.ai,
        ReminderEntityType.habit => MxAccent.tools,
        ReminderEntityType.birthday => MxAccent.security,
      };

  static int _countHabitsDone(List<Habit>? habits) =>
      habits == null ? 0 : habits.where((h) => h.completedToday).length;

  static int _countToday(List<Reminder>? all) {
    if (all == null) return 0;
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final tomorrow = today.add(const Duration(days: 1));
    return all.where((r) {
      final f = r.nextFireAt;
      return f != null && !f.isBefore(today) && f.isBefore(tomorrow);
    }).length;
  }

  static List<Reminder> _filterToday(List<Reminder>? all) {
    if (all == null) return const [];
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final tomorrow = today.add(const Duration(days: 1));
    final list = all.where((r) {
      final f = r.nextFireAt;
      return f != null && f.isBefore(tomorrow) && !f.isBefore(today);
    }).toList();
    list.sort((a, b) => (a.nextFireAt ?? today).compareTo(b.nextFireAt ?? today));
    return list;
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// AI greeting card
// ═══════════════════════════════════════════════════════════════════════════

class _AiGreetingCard extends StatelessWidget {
  const _AiGreetingCard({required this.name, required this.isVip});
  final String name;
  final bool isVip;

  @override
  Widget build(BuildContext context) {
    final hour = DateTime.now().hour;
    final greeting = hour < 6
        ? 'Доброй ночи'
        : hour < 12
            ? 'Доброе утро'
            : hour < 18
                ? 'Добрый день'
                : 'Добрый вечер';

    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Color(0x0F00E5FF), Color(0x05FFFFFF)],
        ),
        borderRadius: BorderRadius.circular(MX.rLg),
        border: Border.all(color: MX.accentAiLine),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.auto_awesome, size: 14, color: MX.accentAi),
              const SizedBox(width: 6),
              Text(
                isVip ? 'АССИСТЕНТ · VIP' : 'АССИСТЕНТ',
                style: const TextStyle(
                  color: MX.accentAi, fontSize: 11,
                  fontWeight: FontWeight.w800, letterSpacing: 1.2,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            '$greeting, $name. ${isVip ? "Показать краткую сводку дня?" : "Включите VIP, чтобы я помнил всё о вас."}',
            style: const TextStyle(
              color: MX.fg, fontSize: 16, fontWeight: FontWeight.w500,
              height: 1.4, letterSpacing: -0.1,
            ),
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              MxPrimaryButton(
                label: isVip ? 'Да, покажи' : 'Узнать о VIP',
                height: 36,
                onTap: () {},
              ),
              const SizedBox(width: 8),
              MxGhostButton(
                label: 'Открыть чат',
                height: 36,
                onTap: () {},
              ),
            ],
          ),
        ],
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// Stats row
// ═══════════════════════════════════════════════════════════════════════════

class _StatsRow extends StatelessWidget {
  const _StatsRow({
    required this.tasksCount,
    required this.habitsDone,
    required this.habitsTotal,
    required this.notesCount,
  });
  final int tasksCount;
  final int habitsDone;
  final int habitsTotal;
  final int notesCount;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 16),
      child: Row(
        children: [
          _StatCell(value: '$tasksCount', label: 'задачи', color: MX.fg),
          const SizedBox(width: 8),
          _StatCell(
            value: habitsTotal > 0 ? '$habitsDone/$habitsTotal' : '0',
            label: 'привычки',
            color: MX.accentTools,
          ),
          const SizedBox(width: 8),
          _StatCell(value: '$notesCount', label: 'заметок', color: MX.fg),
        ],
      ),
    );
  }
}

class _StatCell extends StatelessWidget {
  const _StatCell({required this.value, required this.label, required this.color});
  final String value;
  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
        decoration: BoxDecoration(
          color: MX.surfaceOverlay,
          borderRadius: BorderRadius.circular(MX.rLg),
          border: Border.all(color: MX.line),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              value,
              style: TextStyle(
                color: color, fontSize: 22, fontWeight: FontWeight.w700, height: 1.0,
              ),
            ),
            const SizedBox(height: 4),
            Text(label,
                style: const TextStyle(
                    color: MX.fgMicro, fontSize: 11, fontWeight: FontWeight.w500)),
          ],
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// Habit checklist row
// ═══════════════════════════════════════════════════════════════════════════

class _HabitChecklistRow extends StatelessWidget {
  const _HabitChecklistRow({required this.habit});
  final Habit habit;

  @override
  Widget build(BuildContext context) {
    final done = habit.completedToday;
    return Row(
      children: [
        AnimatedContainer(
          duration: MX.durFast,
          width: 22, height: 22,
          decoration: BoxDecoration(
            color: done ? MX.accentTools : Colors.transparent,
            borderRadius: BorderRadius.circular(6),
            border: Border.all(
              color: done ? MX.accentTools : MX.lineBright, width: 1.5,
            ),
          ),
          child: done ? const Icon(Icons.check, size: 14, color: MX.bgBase) : null,
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Text(
            habit.name,
            style: TextStyle(
              fontSize: 14, fontWeight: FontWeight.w500,
              color: done ? MX.fgMuted : MX.fg,
              decoration: done ? TextDecoration.lineThrough : null,
            ),
          ),
        ),
        if (habit.streak > 0) ...[
          const Icon(Icons.local_fire_department, size: 14, color: MX.statusWarning),
          const SizedBox(width: 2),
          Text('${habit.streak}',
              style: const TextStyle(
                color: MX.statusWarning, fontSize: 12, fontWeight: FontWeight.w700,
              )),
        ],
      ],
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// Recent note row
// ═══════════════════════════════════════════════════════════════════════════

class _TodayNoteRow extends StatelessWidget {
  const _TodayNoteRow({required this.note, this.onTap});
  final Note note;
  final VoidCallback? onTap;

  IconData get _icon => note.isShoppingList
      ? Icons.shopping_cart_outlined
      : Icons.edit_note_outlined;

  MxAccent get _accent => note.isShoppingList ? MxAccent.tools : MxAccent.neutral;

  @override
  Widget build(BuildContext context) {
    return MxCard(
      onTap: onTap,
      padding: const EdgeInsets.all(14),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          MxAccentTile(icon: _icon, accent: _accent),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  note.summaryText?.isNotEmpty == true
                      ? note.summaryText!
                      : note.correctedText,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: MX.fg, fontSize: 14, fontWeight: FontWeight.w600,
                  ),
                ),
                if ((note.summaryText ?? '').isNotEmpty &&
                    note.correctedText != note.summaryText) ...[
                  const SizedBox(height: 3),
                  Text(
                    note.correctedText,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(color: MX.fgMuted, fontSize: 12, height: 1.4),
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(width: 10),
          Text(
            DateFormatter.relative(note.createdAt),
            style: const TextStyle(color: MX.fgMicro, fontSize: 11),
          ),
        ],
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// Skeleton
// ═══════════════════════════════════════════════════════════════════════════

class _SkeletonBlock extends StatelessWidget {
  const _SkeletonBlock({this.lines = 3});
  final int lines;
  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        for (var i = 0; i < lines; i++)
          Container(
            margin: const EdgeInsets.only(bottom: 8),
            height: 52,
            decoration: BoxDecoration(
              color: MX.surfaceOverlay,
              borderRadius: BorderRadius.circular(MX.rLg),
              border: Border.all(color: MX.line),
            ),
          ),
      ],
    );
  }
}
