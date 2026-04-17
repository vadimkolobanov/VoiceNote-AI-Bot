import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/utils/date_formatter.dart';
import 'package:voicenote_ai/features/habits/application/habits_controller.dart';
import 'package:voicenote_ai/features/habits/presentation/widgets/habit_card.dart';
import 'package:voicenote_ai/shared/widgets/app_error.dart';

class HabitsScreen extends ConsumerWidget {
  const HabitsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(habitsListProvider);

    return Scaffold(
      appBar: AppBar(
        title: Text('Сегодня, ${DateFormatter.dayMonth(DateTime.now())}'),
        actions: [
          IconButton(
            tooltip: 'Создать привычку',
            icon: const Icon(Icons.add),
            onPressed: () => _showCreate(context, ref),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(habitsListProvider),
        child: async.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => AppErrorView(
            error: e,
            onRetry: () => ref.invalidate(habitsListProvider),
          ),
          data: (habits) {
            if (habits.isEmpty) {
              return LayoutBuilder(
                builder: (_, c) => SingleChildScrollView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  child: SizedBox(
                    height: c.maxHeight,
                    child: EmptyStateView(
                      icon: Icons.repeat,
                      title: 'Пока нет привычек',
                      subtitle:
                          'Опишите словами то, что хотите отслеживать — AI поможет создать трекер',
                      action: FilledButton.icon(
                        icon: const Icon(Icons.add),
                        label: const Text('Создать'),
                        onPressed: () => _showCreate(context, ref),
                      ),
                    ),
                  ),
                ),
              );
            }
            return ListView.separated(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
              itemCount: habits.length,
              separatorBuilder: (_, __) => const SizedBox(height: 10),
              itemBuilder: (_, i) => HabitCard(habit: habits[i]),
            );
          },
        ),
      ),
    );
  }

  void _showCreate(BuildContext context, WidgetRef ref) {
    final controller = TextEditingController();
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => Padding(
        padding: EdgeInsets.only(
          left: 20,
          right: 20,
          top: 20,
          bottom: MediaQuery.of(ctx).viewInsets.bottom + 20,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Новая привычка',
              style: Theme.of(ctx).textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
            ),
            const SizedBox(height: 4),
            Text(
              'Опишите привычку, которую хотите отслеживать',
              style: Theme.of(ctx).textTheme.bodySmall,
            ),
            const SizedBox(height: 16),
            TextField(
              controller: controller,
              autofocus: true,
              minLines: 2,
              maxLines: 5,
              decoration: const InputDecoration(
                hintText: 'Например: пить 2 литра воды каждый день',
              ),
            ),
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: () async {
                  final text = controller.text.trim();
                  if (text.isEmpty) return;
                  try {
                    await ref.read(habitsActionsProvider).create(text);
                    if (ctx.mounted) Navigator.pop(ctx);
                  } on ApiException catch (e) {
                    if (ctx.mounted) {
                      ScaffoldMessenger.of(ctx).showSnackBar(
                        SnackBar(content: Text(e.message)),
                      );
                    }
                  }
                },
                child: const Text('Создать'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
