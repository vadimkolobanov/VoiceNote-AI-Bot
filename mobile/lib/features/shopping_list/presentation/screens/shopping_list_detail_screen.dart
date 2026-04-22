import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/features/auth/application/session_controller.dart';
import 'package:voicenote_ai/features/shopping_list/data/models/shopping_list.dart';
import 'package:voicenote_ai/features/shopping_list/data/repositories/shopping_repository.dart';
import 'package:voicenote_ai/shared/widgets/app_error.dart';

class ShoppingListDetailScreen extends ConsumerStatefulWidget {
  const ShoppingListDetailScreen({required this.listId, super.key});
  final int listId;

  @override
  ConsumerState<ShoppingListDetailScreen> createState() => _ShoppingListDetailScreenState();
}

class _ShoppingListDetailScreenState extends ConsumerState<ShoppingListDetailScreen> {
  void _invalidate() {
    ref.invalidate(shoppingListDetailProvider(widget.listId));
    ref.invalidate(shoppingListsProvider(false));
    ref.invalidate(shoppingListsProvider(true));
  }

  Future<void> _toggle(ShoppingItem item) async {
    try {
      await ref.read(shoppingRepositoryProvider).toggleItem(item.id, !item.checked);
      _invalidate();
    } on ApiException catch (e) {
      _snack(e.message);
    }
  }

  Future<void> _addItem(ShoppingListDetail detail) async {
    final nameCtl = TextEditingController();
    final qtyCtl = TextEditingController();
    await showModalBottomSheet<void>(
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
            Text(
              'Добавить товар',
              style: Theme.of(ctx).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 14),
            TextField(
              controller: nameCtl,
              autofocus: true,
              decoration: const InputDecoration(
                labelText: 'Название',
                hintText: 'Например: молоко',
              ),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: qtyCtl,
              decoration: const InputDecoration(
                labelText: 'Количество (необязательно)',
                hintText: '1 л, 2 шт, 500 г',
              ),
            ),
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                icon: const Icon(Icons.add),
                label: const Text('Добавить'),
                onPressed: () async {
                  final name = nameCtl.text.trim();
                  if (name.isEmpty) return;
                  try {
                    await ref.read(shoppingRepositoryProvider).addItem(
                          detail.id,
                          name,
                          quantity: qtyCtl.text.trim().isEmpty ? null : qtyCtl.text.trim(),
                        );
                    if (ctx.mounted) Navigator.pop(ctx);
                    _invalidate();
                  } on ApiException catch (e) {
                    if (ctx.mounted) {
                      ScaffoldMessenger.of(ctx).showSnackBar(
                        SnackBar(content: Text(e.message)),
                      );
                    }
                  }
                },
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _deleteItem(int itemId) async {
    try {
      await ref.read(shoppingRepositoryProvider).deleteItem(itemId);
      _invalidate();
    } on ApiException catch (e) {
      _snack(e.message);
    }
  }

  Future<void> _showShare(ShoppingListDetail detail) async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      final invite = await ref.read(shoppingRepositoryProvider).createInvite(detail.id);
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (ctx) => _InviteDialog(invite: invite),
      );
    } on ApiException catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  Future<void> _archive(ShoppingListDetail detail) async {
    try {
      await ref.read(shoppingRepositoryProvider).archiveList(detail.id);
      _invalidate();
      if (mounted) Navigator.of(context).pop();
    } on ApiException catch (e) {
      _snack(e.message);
    }
  }

  Future<void> _restore(ShoppingListDetail detail) async {
    try {
      await ref.read(shoppingRepositoryProvider).restoreList(detail.id);
      _invalidate();
    } on ApiException catch (e) {
      _snack(e.message);
    }
  }

  Future<void> _delete(ShoppingListDetail detail) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Удалить список?'),
        content: const Text('Это действие нельзя отменить.'),
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
    if (ok != true) return;
    try {
      await ref.read(shoppingRepositoryProvider).deleteList(detail.id);
      _invalidate();
      if (mounted) Navigator.of(context).pop();
    } on ApiException catch (e) {
      _snack(e.message);
    }
  }

  Future<void> _leave(ShoppingListDetail detail) async {
    try {
      await ref.read(shoppingRepositoryProvider).leave(detail.id);
      _invalidate();
      if (mounted) Navigator.of(context).pop();
    } on ApiException catch (e) {
      _snack(e.message);
    }
  }

  void _snack(String msg) {
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(shoppingListDetailProvider(widget.listId));
    final currentUserId = ref.watch(sessionControllerProvider).user?.id;

    return Scaffold(
      body: async.when(
        loading: () => const Scaffold(body: Center(child: CircularProgressIndicator())),
        error: (e, _) => Scaffold(
          appBar: AppBar(),
          body: AppErrorView(
            error: e,
            onRetry: () => ref.invalidate(shoppingListDetailProvider(widget.listId)),
          ),
        ),
        data: (detail) {
          final isOwner = currentUserId != null && detail.ownerId == currentUserId;
          final sortedItems = [...detail.items]
            ..sort((a, b) {
              if (a.checked != b.checked) return a.checked ? 1 : -1;
              return a.position.compareTo(b.position);
            });

          return CustomScrollView(
            slivers: [
              SliverAppBar(
                pinned: true,
                title: Text(
                  detail.title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                actions: [
                  IconButton(
                    tooltip: 'Поделиться',
                    icon: const Icon(Icons.share_outlined),
                    onPressed: () => _showShare(detail),
                  ),
                  PopupMenuButton<String>(
                    onSelected: (value) {
                      switch (value) {
                        case 'archive':
                          _archive(detail);
                        case 'restore':
                          _restore(detail);
                        case 'delete':
                          _delete(detail);
                        case 'leave':
                          _leave(detail);
                      }
                    },
                    itemBuilder: (_) => [
                      if (isOwner && !detail.isArchived)
                        const PopupMenuItem(value: 'archive', child: Text('В архив')),
                      if (isOwner && detail.isArchived)
                        const PopupMenuItem(value: 'restore', child: Text('Из архива')),
                      if (isOwner)
                        const PopupMenuItem(value: 'delete', child: Text('Удалить список')),
                      if (!isOwner)
                        const PopupMenuItem(value: 'leave', child: Text('Выйти из списка')),
                    ],
                  ),
                ],
              ),
              if (detail.members.length > 1)
                SliverToBoxAdapter(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                    child: _MembersRow(members: detail.members),
                  ),
                ),
              if (sortedItems.isEmpty)
                const SliverFillRemaining(
                  hasScrollBody: false,
                  child: EmptyStateView(
                    icon: Icons.shopping_cart_outlined,
                    title: 'Список пуст',
                    subtitle: 'Нажмите «+», чтобы добавить товар',
                  ),
                )
              else
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(8, 4, 8, 100),
                  sliver: SliverList.builder(
                    itemCount: sortedItems.length,
                    itemBuilder: (_, i) {
                      final item = sortedItems[i];
                      return Dismissible(
                        key: ValueKey('shop-item-${item.id}'),
                        direction: DismissDirection.endToStart,
                        background: Container(
                          margin: const EdgeInsets.symmetric(vertical: 2),
                          padding: const EdgeInsets.symmetric(horizontal: 24),
                          alignment: Alignment.centerRight,
                          decoration: BoxDecoration(
                            color: Theme.of(context).colorScheme.error,
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: const Icon(Icons.delete, color: Colors.white),
                        ),
                        onDismissed: (_) => _deleteItem(item.id),
                        child: _ItemTile(
                          item: item,
                          onTap: () => _toggle(item),
                        ),
                      );
                    },
                  ),
                ),
            ],
          );
        },
      ),
      floatingActionButton: async.whenOrNull(
        data: (d) => d.isArchived
            ? null
            : FloatingActionButton.extended(
                onPressed: () => _addItem(d),
                icon: const Icon(Icons.add),
                label: const Text('Добавить'),
              ),
      ),
    );
  }
}

class _ItemTile extends StatelessWidget {
  const _ItemTile({required this.item, required this.onTap});
  final ShoppingItem item;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(10),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        child: Row(
          children: [
            AnimatedContainer(
              duration: const Duration(milliseconds: 180),
              width: 24, height: 24,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: item.checked ? scheme.primary : Colors.transparent,
                border: Border.all(
                  width: 2,
                  color: item.checked ? scheme.primary : scheme.outline,
                ),
              ),
              child: item.checked
                  ? const Icon(Icons.check, size: 16, color: Colors.white)
                  : null,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    item.name,
                    style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                          decoration: item.checked ? TextDecoration.lineThrough : null,
                          color: item.checked
                              ? scheme.onSurfaceVariant
                              : scheme.onSurface,
                        ),
                  ),
                  if (item.quantity != null && item.quantity!.isNotEmpty)
                    Text(
                      item.quantity!,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: scheme.onSurfaceVariant,
                          ),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MembersRow extends StatelessWidget {
  const _MembersRow({required this.members});
  final List<ShoppingMember> members;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return SizedBox(
      height: 38,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: members.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (_, i) {
          final m = members[i];
          return Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            decoration: BoxDecoration(
              color: m.isOwner ? scheme.primaryContainer : scheme.surfaceContainerHighest,
              borderRadius: BorderRadius.circular(20),
            ),
            child: Row(
              children: [
                CircleAvatar(
                  radius: 12,
                  backgroundColor: scheme.primary,
                  child: Text(
                    (m.displayName.isNotEmpty ? m.displayName[0] : '?').toUpperCase(),
                    style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w700),
                  ),
                ),
                const SizedBox(width: 6),
                Text(
                  m.displayName,
                  style: Theme.of(context).textTheme.labelMedium,
                ),
                if (m.isOwner) ...[
                  const SizedBox(width: 4),
                  Icon(Icons.star, size: 12, color: scheme.primary),
                ],
              ],
            ),
          );
        },
      ),
    );
  }
}

class _InviteDialog extends StatelessWidget {
  const _InviteDialog({required this.invite});
  final ShoppingInvite invite;

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Код приглашения'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Text('Отправьте этот код тому, с кем хотите поделиться списком:'),
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.primaryContainer,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Text(
              invite.code,
              style: const TextStyle(
                fontSize: 32,
                fontWeight: FontWeight.w800,
                letterSpacing: 8,
              ),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Действителен до ${invite.expiresAt.toLocal().toString().split('.').first}',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
      actions: [
        TextButton.icon(
          icon: const Icon(Icons.copy),
          label: const Text('Скопировать'),
          onPressed: () async {
            await Clipboard.setData(ClipboardData(text: invite.code));
            if (context.mounted) {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Код скопирован')),
              );
            }
          },
        ),
        FilledButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Готово'),
        ),
      ],
    );
  }
}
