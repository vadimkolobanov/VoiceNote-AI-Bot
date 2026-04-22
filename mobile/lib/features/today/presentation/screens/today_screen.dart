import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import 'package:voicenote_ai/core/router/app_routes.dart';
import 'package:voicenote_ai/core/theme/mx_tokens.dart';
import 'package:voicenote_ai/core/utils/date_formatter.dart';
import 'package:voicenote_ai/features/auth/application/session_controller.dart';
import 'package:voicenote_ai/features/habits/application/habits_controller.dart';
import 'package:voicenote_ai/features/notes/application/notes_controller.dart';
import 'package:voicenote_ai/features/notes/data/models/note.dart';
import 'package:voicenote_ai/features/notes/data/repositories/notes_repository.dart';
import 'package:voicenote_ai/features/tasks/data/models/reminder.dart';
import 'package:voicenote_ai/features/tasks/data/repositories/reminders_repository.dart';

/// «Сегодня» — dashboard. Первый экран после логина.
class TodayScreen extends ConsumerWidget {
  const TodayScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(sessionControllerProvider);
    final remindersAsync = ref.watch(allRemindersProvider);
    final habitsAsync = ref.watch(habitsListProvider);
    // notesControllerProvider возвращает NotesListState (не AsyncValue),
    // поэтому читаем поля напрямую.
    final notesState = ref.watch(
      notesControllerProvider(const NotesQuery(
        segment: NotesSegment.active, type: NoteType.note,
      )),
    );

    final now = DateTime.now();
    final weekday = DateFormat('EEEE, d MMMM', 'ru').format(now);
    final greeting = _greeting(now.hour);
    final name = session.user?.firstName ?? 'друг';

    return Scaffold(
      appBar: AppBar(
        automaticallyImplyLeading: false,
        titleSpacing: 20,
        title: Row(
          children: [
            Container(
              width: 32, height: 32,
              decoration: const BoxDecoration(
                gradient: MX.brandGradient,
                borderRadius: BorderRadius.all(Radius.circular(8)),
              ),
              child: const Center(
                child: Text('М',
                    style: TextStyle(
                        color: Colors.white, fontWeight: FontWeight.w700, fontSize: 16)),
              ),
            ),
            const SizedBox(width: 10),
            const Text('Методекс', style: TextStyle(fontWeight: FontWeight.w600)),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.notifications_none),
            onPressed: () => context.push(AppRoutes.allReminders),
          ),
          IconButton(
            icon: const CircleAvatar(
              radius: 16,
              backgroundColor: MX.accentAi,
              child: Icon(Icons.person_outline, color: MX.bgBase, size: 18),
            ),
            onPressed: () => context.push(AppRoutes.profile),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () async {
            ref.invalidate(allRemindersProvider);
            ref.invalidate(habitsListProvider);
          },
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 120),
            children: [
              _Header(
                subtitle: _capitalize(weekday),
                title: '$greeting, $name',
              ),
              const SizedBox(height: 20),
              _AiGreetingCard(isVip: session.user?.isVip ?? false),
              const SizedBox(height: 20),
              _StatsRow(
                tasksToday: _countToday(remindersAsync.valueOrNull),
                habits: habitsAsync.valueOrNull?.length ?? 0,
                notes: notesState.items.length,
              ),
              const SizedBox(height: 28),
              _SectionTitle(
                label: 'На сегодня',
                trailing: TextButton(
                  onPressed: () => context.go(AppRoutes.tasks),
                  child: const Text('Все →'),
                ),
              ),
              const SizedBox(height: 8),
              remindersAsync.when(
                loading: () => const _Shimmer(),
                error: (_, __) => const _EmptyHint('Не удалось загрузить'),
                data: (all) {
                  final today = _filterToday(all);
                  if (today.isEmpty) {
                    return const _EmptyHint('Сегодня свободно — можно позволить себе что-то хорошее.');
                  }
                  return Column(
                    children: [for (final r in today.take(4)) _ReminderRow(reminder: r)],
                  );
                },
              ),
              const SizedBox(height: 28),
              _SectionTitle(
                label: 'Привычки',
                trailing: TextButton(
                  onPressed: () => context.go(AppRoutes.habits),
                  child: const Text('Все →'),
                ),
              ),
              const SizedBox(height: 8),
              habitsAsync.when(
                loading: () => const _Shimmer(),
                error: (_, __) => const _EmptyHint('Не удалось загрузить'),
                data: (habits) {
                  if (habits.isEmpty) {
                    return const _EmptyHint('Создайте первую привычку.');
                  }
                  return Column(
                    children: [
                      for (final h in habits.take(3))
                        Padding(
                          padding: const EdgeInsets.only(bottom: 8),
                          child: _HabitPill(name: h.name, streak: h.streak, done: h.completedToday),
                        ),
                    ],
                  );
                },
              ),
              const SizedBox(height: 28),
              _SectionTitle(
                label: 'Последние заметки',
                trailing: TextButton(
                  onPressed: () => context.go(AppRoutes.notes),
                  child: const Text('Все →'),
                ),
              ),
              const SizedBox(height: 8),
              if (notesState.items.isEmpty)
                const _EmptyHint('Записей пока нет. Нажмите микрофон внизу.')
              else
                Column(
                  children: [
                    for (final n in notesState.items.take(3))
                      Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: _NoteRow(note: n),
                      ),
                  ],
                ),
            ],
          ),
        ),
      ),
    );
  }

  static String _greeting(int hour) {
    if (hour < 6) return 'Доброй ночи';
    if (hour < 12) return 'Доброе утро';
    if (hour < 18) return 'Добрый день';
    return 'Добрый вечер';
  }

  static String _capitalize(String s) =>
      s.isEmpty ? s : s[0].toUpperCase() + s.substring(1);

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
// Widgets
// ═══════════════════════════════════════════════════════════════════════════

class _Header extends StatelessWidget {
  const _Header({required this.subtitle, required this.title});
  final String subtitle;
  final String title;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          subtitle.toUpperCase(),
          style: Theme.of(context).textTheme.labelSmall?.copyWith(
                letterSpacing: 1.2, fontWeight: FontWeight.w600,
                color: MX.fgMicro,
              ),
        ),
        const SizedBox(height: 6),
        Text(title, style: Theme.of(context).textTheme.displaySmall),
      ],
    );
  }
}

class _AiGreetingCard extends StatelessWidget {
  const _AiGreetingCard({required this.isVip});
  final bool isVip;
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: MX.accentAiSoft,
        borderRadius: BorderRadius.circular(MX.rLg),
        border: Border.all(color: MX.accentAiLine),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 40, height: 40,
            decoration: const BoxDecoration(
              gradient: MX.brandGradient,
              borderRadius: BorderRadius.all(Radius.circular(10)),
            ),
            child: const Center(
              child: Text('М',
                  style: TextStyle(
                      color: Colors.white, fontWeight: FontWeight.w700, fontSize: 18)),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Секретарь',
                    style: Theme.of(context).textTheme.titleSmall?.copyWith(
                          color: MX.accentAi,
                          fontWeight: FontWeight.w700,
                        )),
                const SizedBox(height: 4),
                Text(
                  isVip
                      ? 'Помню 0 фактов о вас. Спросите что-нибудь в AI-чате.'
                      : 'Разблокируйте AI-ассистента и полную память в Premium.',
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _StatsRow extends StatelessWidget {
  const _StatsRow({required this.tasksToday, required this.habits, required this.notes});
  final int tasksToday;
  final int habits;
  final int notes;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        _StatCell(value: tasksToday, label: 'на сегодня', color: MX.accentAi),
        const SizedBox(width: 10),
        _StatCell(value: habits, label: 'привычек', color: MX.accentTools),
        const SizedBox(width: 10),
        _StatCell(value: notes, label: 'заметок', color: MX.fgMuted),
      ],
    );
  }
}

class _StatCell extends StatelessWidget {
  const _StatCell({required this.value, required this.label, required this.color});
  final int value;
  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
        decoration: BoxDecoration(
          color: MX.surfaceOverlay,
          borderRadius: BorderRadius.circular(MX.rLg),
          border: Border.all(color: MX.line),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('$value',
                style: Theme.of(context).textTheme.displaySmall?.copyWith(
                      color: color, height: 1.0,
                    )),
            const SizedBox(height: 4),
            Text(label,
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color: MX.fgMicro, letterSpacing: 0.6,
                    )),
          ],
        ),
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle({required this.label, this.trailing});
  final String label;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Text(
            label.toUpperCase(),
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: MX.fgMicro, letterSpacing: 1.2,
                  fontWeight: FontWeight.w700,
                ),
          ),
        ),
        if (trailing != null) trailing!,
      ],
    );
  }
}

class _ReminderRow extends StatelessWidget {
  const _ReminderRow({required this.reminder});
  final Reminder reminder;

  @override
  Widget build(BuildContext context) {
    final time = reminder.nextFireAt != null
        ? DateFormat('HH:mm').format(reminder.nextFireAt!.toLocal())
        : '—';
    final Color dotColor = switch (reminder.entityType) {
      ReminderEntityType.note => MX.accentAi,
      ReminderEntityType.habit => MX.accentTools,
      ReminderEntityType.birthday => MX.accentPurple,
    };

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: MX.surfaceOverlay,
        borderRadius: BorderRadius.circular(MX.rMd),
        border: Border.all(color: MX.line),
      ),
      child: Row(
        children: [
          Container(
            width: 8, height: 8,
            decoration: BoxDecoration(color: dotColor, shape: BoxShape.circle),
          ),
          const SizedBox(width: 12),
          SizedBox(
            width: 52,
            child: Text(time,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: MX.fgMuted, fontFeatures: const [],
                    )),
          ),
          Expanded(
            child: Text(reminder.title,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      fontWeight: FontWeight.w500,
                    )),
          ),
        ],
      ),
    );
  }
}

class _HabitPill extends StatelessWidget {
  const _HabitPill({required this.name, required this.streak, required this.done});
  final String name;
  final int streak;
  final bool done;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: done ? MX.accentToolsSoft : MX.surfaceOverlay,
        borderRadius: BorderRadius.circular(MX.rMd),
        border: Border.all(color: done ? MX.accentToolsLine : MX.line),
      ),
      child: Row(
        children: [
          Icon(
            done ? Icons.check_circle : Icons.radio_button_unchecked,
            color: done ? MX.accentTools : MX.fgGhost,
            size: 22,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(name,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      fontWeight: FontWeight.w500,
                      decoration: done ? TextDecoration.lineThrough : null,
                    )),
          ),
          if (streak > 0) ...[
            const Icon(Icons.local_fire_department, color: MX.statusWarning, size: 16),
            const SizedBox(width: 2),
            Text('$streak',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: MX.statusWarning, fontWeight: FontWeight.w700,
                    )),
          ],
        ],
      ),
    );
  }
}

class _NoteRow extends StatelessWidget {
  const _NoteRow({required this.note});
  final Note note;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: MX.surfaceOverlay,
        borderRadius: BorderRadius.circular(MX.rMd),
        border: Border.all(color: MX.line),
      ),
      child: Row(
        children: [
          const Icon(Icons.edit_note, color: MX.fgMuted, size: 18),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              note.summaryText?.isNotEmpty == true ? note.summaryText! : note.correctedText,
              maxLines: 1, overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.w500,
                  ),
            ),
          ),
          Text(DateFormatter.relative(note.createdAt),
              style: Theme.of(context).textTheme.bodySmall?.copyWith(color: MX.fgMicro)),
        ],
      ),
    );
  }
}

class _Shimmer extends StatelessWidget {
  const _Shimmer();
  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        for (var i = 0; i < 3; i++)
          Container(
            margin: const EdgeInsets.only(bottom: 8),
            height: 44,
            decoration: BoxDecoration(
              color: MX.surfaceOverlay,
              borderRadius: BorderRadius.circular(MX.rMd),
            ),
          ),
      ],
    );
  }
}

class _EmptyHint extends StatelessWidget {
  const _EmptyHint(this.text);
  final String text;
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: MX.surfaceOverlay,
        borderRadius: BorderRadius.circular(MX.rMd),
        border: Border.all(color: MX.line),
      ),
      child: Text(text,
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: MX.fgMuted)),
    );
  }
}
