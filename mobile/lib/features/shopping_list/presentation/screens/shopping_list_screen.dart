import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/features/shopping_list/data/repositories/shopping_repository.dart';
import 'package:voicenote_ai/shared/widgets/app_error.dart';

class ShoppingListScreen extends ConsumerWidget {
  const ShoppingListScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(shoppingListProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Покупки'),
        actions: [
          async.maybeWhen(
            data: (list) => list != null && list.items.isNotEmpty
                ? IconButton(
                    tooltip: 'Архивировать список',
                    icon: const Icon(Icons.archive_outlined),
                    onPressed: () async {
                      await ref.read(shoppingRepositoryProvider).archive();
                      ref.invalidate(shoppingListProvider);
                    },
                  )
                : const SizedBox.shrink(),
            orElse: () => const SizedBox.shrink(),
          ),
        ],
      ),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) =>
            AppErrorView(error: e, onRetry: () => ref.invalidate(shoppingListProvider)),
        data: (list) {
          if (list == null || list.items.isEmpty) {
            return const EmptyStateView(
              icon: Icons.shopping_cart_outlined,
              title: 'Список пуст',
              subtitle: 'Добавьте первый товар внизу экрана',
            );
          }
          return ListView.builder(
            padding: const EdgeInsets.fromLTRB(8, 8, 8, 100),
            itemCount: list.items.length,
            itemBuilder: (_, i) {
              final item = list.items[i];
              return CheckboxListTile(
                value: item.checked,
                onChanged: (v) async {
                  if (v == null) return;
                  try {
                    await ref.read(shoppingRepositoryProvider).toggle(i, v);
                    ref.invalidate(shoppingListProvider);
                  } on ApiException catch (e) {
                    if (context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(content: Text(e.message)),
                      );
                    }
                  }
                },
                title: Text(
                  item.name,
                  style: TextStyle(
                    decoration: item.checked ? TextDecoration.lineThrough : null,
                    color: item.checked ? Theme.of(context).colorScheme.onSurfaceVariant : null,
                  ),
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

  void _showAdd(BuildContext context, WidgetRef ref) {
    final controller = TextEditingController();
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => Padding(
        padding: EdgeInsets.only(
          left: 20, right: 20, top: 20,
          bottom: MediaQuery.of(ctx).viewInsets.bottom + 20,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Добавить товар',
                style: Theme.of(ctx).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
            const SizedBox(height: 12),
            TextField(
              controller: controller,
              autofocus: true,
              decoration: const InputDecoration(hintText: 'Например: хлеб'),
              onSubmitted: (_) => _submit(ctx, ref, controller.text),
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: () => _submit(ctx, ref, controller.text),
                child: const Text('Добавить'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _submit(BuildContext ctx, WidgetRef ref, String name) async {
    final trimmed = name.trim();
    if (trimmed.isEmpty) return;
    try {
      await ref.read(shoppingRepositoryProvider).add(trimmed);
      ref.invalidate(shoppingListProvider);
      if (ctx.mounted) Navigator.pop(ctx);
    } on ApiException catch (e) {
      if (ctx.mounted) {
        ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(content: Text(e.message)));
      }
    }
  }
}
