import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/features/birthdays/data/models/birthday.dart';
import 'package:voicenote_ai/features/birthdays/data/repositories/birthdays_repository.dart';
import 'package:voicenote_ai/shared/widgets/app_error.dart';

class BirthdaysScreen extends ConsumerWidget {
  const BirthdaysScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(birthdaysListProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Дни рождения')),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => AppErrorView(
          error: e,
          onRetry: () => ref.invalidate(birthdaysListProvider),
        ),
        data: (items) {
          if (items.isEmpty) {
            return const EmptyStateView(
              icon: Icons.cake_outlined,
              title: 'Пока пусто',
              subtitle: 'Добавьте первый день рождения',
            );
          }
          final sorted = [...items]..sort((a, b) => a.daysUntil.compareTo(b.daysUntil));
          return ListView.separated(
            padding: const EdgeInsets.all(16),
            itemCount: sorted.length,
            separatorBuilder: (_, __) => const SizedBox(height: 8),
            itemBuilder: (_, i) {
              final b = sorted[i];
              return Card(
                child: ListTile(
                  leading: CircleAvatar(
                    backgroundColor: Theme.of(context).colorScheme.primaryContainer,
                    child: Text(
                      b.name.isNotEmpty ? b.name[0].toUpperCase() : '?',
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.onPrimaryContainer,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                  title: Text(b.name),
                  subtitle: Text(
                    '${DateFormat('d MMMM', 'ru').format(DateTime(2000, b.month, b.day))}'
                    '${b.year != null ? ' · ${b.year}' : ''}',
                  ),
                  trailing: _DaysChip(days: b.daysUntil),
                  onLongPress: () async {
                    final ok = await _confirmDelete(context);
                    if (ok) {
                      try {
                        await ref.read(birthdaysRepositoryProvider).delete(b.id);
                        ref.invalidate(birthdaysListProvider);
                      } on ApiException catch (e) {
                        if (context.mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text(e.message)),
                          );
                        }
                      }
                    }
                  },
                ),
              );
            },
          );
        },
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _showAdd(context, ref),
        icon: const Icon(Icons.add),
        label: const Text('Добавить'),
      ),
    );
  }

  Future<bool> _confirmDelete(BuildContext context) async {
    final result = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Удалить запись?'),
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
    return result ?? false;
  }

  Future<void> _showAdd(BuildContext context, WidgetRef ref) async {
    final name = TextEditingController();
    DateTime? date;
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setState) => Padding(
          padding: EdgeInsets.only(
            left: 20, right: 20, top: 20,
            bottom: MediaQuery.of(ctx).viewInsets.bottom + 20,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Новый день рождения',
                  style: Theme.of(ctx).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
              const SizedBox(height: 16),
              TextField(
                controller: name,
                autofocus: true,
                decoration: const InputDecoration(
                  labelText: 'Имя',
                  prefixIcon: Icon(Icons.person_outline),
                ),
              ),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                icon: const Icon(Icons.calendar_today_outlined),
                label: Text(
                  date == null ? 'Выбрать дату' : DateFormat('d MMMM yyyy', 'ru').format(date!),
                ),
                onPressed: () async {
                  final now = DateTime.now();
                  final picked = await showDatePicker(
                    context: ctx,
                    initialDate: date ?? DateTime(now.year - 20, now.month, now.day),
                    firstDate: DateTime(1920),
                    lastDate: now,
                  );
                  if (picked != null) setState(() => date = picked);
                },
              ),
              const SizedBox(height: 16),
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: () async {
                    if (name.text.trim().isEmpty || date == null) return;
                    final fmt = '${date!.day.toString().padLeft(2, '0')}.'
                        '${date!.month.toString().padLeft(2, '0')}.${date!.year}';
                    try {
                      await ref
                          .read(birthdaysRepositoryProvider)
                          .create(name.text.trim(), fmt);
                      ref.invalidate(birthdaysListProvider);
                      if (ctx.mounted) Navigator.pop(ctx);
                    } on ApiException catch (e) {
                      if (ctx.mounted) {
                        ScaffoldMessenger.of(ctx).showSnackBar(
                          SnackBar(content: Text(e.message)),
                        );
                      }
                    }
                  },
                  child: const Text('Сохранить'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _DaysChip extends StatelessWidget {
  const _DaysChip({required this.days});
  final int days;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final label = days == 0
        ? 'Сегодня!'
        : days < 7
            ? 'Через $days дн.'
            : 'Через $days дн.';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: days < 7 ? scheme.primary.withValues(alpha: 0.15) : scheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        label,
        style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: days < 7 ? scheme.primary : scheme.onSurfaceVariant,
              fontWeight: FontWeight.w600,
            ),
      ),
    );
  }
}
