import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/core/utils/date_formatter.dart';
import 'package:voicenote_ai/core/theme/mx_tokens.dart';
import 'package:voicenote_ai/core/widgets/mx_widgets.dart';
import 'package:voicenote_ai/features/ai_agent/data/models/chat_message.dart';
import 'package:voicenote_ai/features/ai_agent/data/repositories/ai_repository.dart';
import 'package:voicenote_ai/shared/widgets/app_error.dart';

final _factsProvider =
    FutureProvider.autoDispose<List<MemoryFact>>((ref) async {
  return ref.watch(aiRepositoryProvider).facts();
});

class MemoryFactsScreen extends ConsumerWidget {
  const MemoryFactsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(_factsProvider);

    return Scaffold(
      backgroundColor: MX.bgBase,
      appBar: MxAppBar(
        title: 'Память',
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, size: 22),
          onPressed: () => Navigator.of(context).pop(),
        ),
        actions: [
          IconButton(
            tooltip: 'Сбросить всю память',
            icon: const Icon(Icons.delete_sweep_outlined, size: 22),
            onPressed: () => _confirmReset(context, ref),
          ),
        ],
      ),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => AppErrorView(error: e, onRetry: () => ref.invalidate(_factsProvider)),
        data: (facts) {
          if (facts.isEmpty) {
            return const EmptyStateView(
              icon: Icons.psychology_alt_outlined,
              title: 'Память пуста',
              subtitle: 'AI сохранит сюда важные факты о вас из заметок и диалогов',
            );
          }
          return ListView.separated(
            padding: const EdgeInsets.all(16),
            itemCount: facts.length,
            separatorBuilder: (_, __) => const SizedBox(height: 8),
            itemBuilder: (_, i) {
              final f = facts[i];
              return Card(
                child: ListTile(
                  leading: const Icon(Icons.fiber_manual_record, size: 10),
                  title: Text(f.text),
                  subtitle: Text(
                    '${_sourceLabel(f.sourceType)} • ${DateFormatter.relative(f.createdAt)}',
                  ),
                  trailing: IconButton(
                    icon: const Icon(Icons.close),
                    onPressed: () async {
                      await ref.read(aiRepositoryProvider).deleteFact(f.id);
                      ref.invalidate(_factsProvider);
                    },
                  ),
                ),
              );
            },
          );
        },
      ),
    );
  }

  String _sourceLabel(String s) => switch (s) {
        'note' => 'из заметки',
        'chat' => 'из диалога',
        _ => 'вручную',
      };

  Future<void> _confirmReset(BuildContext context, WidgetRef ref) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Сбросить память AI?'),
        content: const Text('Вся история диалогов и факты будут удалены.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Отмена')),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: Theme.of(ctx).colorScheme.error),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Сбросить'),
          ),
        ],
      ),
    );
    if (ok == true) {
      await ref.read(aiRepositoryProvider).reset();
      ref.invalidate(_factsProvider);
    }
  }
}
