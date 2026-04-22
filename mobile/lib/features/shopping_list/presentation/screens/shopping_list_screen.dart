import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/theme/mx_tokens.dart';
import 'package:voicenote_ai/core/utils/date_formatter.dart';
import 'package:voicenote_ai/core/widgets/mx_widgets.dart';
import 'package:voicenote_ai/features/shopping_list/data/models/shopping_list.dart';
import 'package:voicenote_ai/features/shopping_list/data/repositories/shopping_repository.dart';
import 'package:voicenote_ai/features/shopping_list/presentation/screens/shopping_list_detail_screen.dart';
import 'package:voicenote_ai/shared/widgets/app_error.dart';

/// Главный экран «Покупки» — теперь показывает список ВСЕХ списков,
/// с прогрессом отмечек и участниками, возможностью создать новый/войти по коду.
class ShoppingListsScreen extends ConsumerStatefulWidget {
  const ShoppingListsScreen({super.key});

  @override
  ConsumerState<ShoppingListsScreen> createState() => _ShoppingListsScreenState();
}

class _ShoppingListsScreenState extends ConsumerState<ShoppingListsScreen>
    with SingleTickerProviderStateMixin {
  bool _showArchived = false;

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(shoppingListsProvider(_showArchived));

    return Scaffold(
      backgroundColor: MX.bgBase,
      appBar: MxAppBar(
        title: 'Покупки',
        subtitle: async.valueOrNull == null ? null :
          '${async.valueOrNull!.length} ${_showArchived ? "архивных" : "активных"}',
        actions: [
          IconButton(
            tooltip: _showArchived ? 'Активные' : 'Архив',
            icon: Icon(_showArchived ? Icons.inbox_outlined : Icons.archive_outlined, size: 22),
            onPressed: () => setState(() => _showArchived = !_showArchived),
          ),
          IconButton(
            tooltip: 'Присоединиться по коду',
            icon: const Icon(Icons.vpn_key_outlined, size: 22),
            onPressed: () => _showJoinDialog(context),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(shoppingListsProvider(_showArchived)),
        child: async.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => AppErrorView(
            error: e,
            onRetry: () => ref.invalidate(shoppingListsProvider(_showArchived)),
          ),
          data: (lists) {
            if (lists.isEmpty) {
              return LayoutBuilder(
                builder: (_, c) => SingleChildScrollView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  child: SizedBox(
                    height: c.maxHeight,
                    child: EmptyStateView(
                      icon: Icons.shopping_cart_outlined,
                      title: _showArchived ? 'Нет архивных списков' : 'Нет активных списков',
                      subtitle: _showArchived
                          ? null
                          : 'Создайте новый список или присоединитесь по коду',
                      action: !_showArchived
                          ? FilledButton.icon(
                              onPressed: () => _showCreateDialog(context),
                              icon: const Icon(Icons.add),
                              label: const Text('Создать список'),
                            )
                          : null,
                    ),
                  ),
                ),
              );
            }
            return ListView.separated(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 100),
              itemCount: lists.length,
              separatorBuilder: (_, __) => const SizedBox(height: 10),
              itemBuilder: (_, i) => _ListCard(
                summary: lists[i],
                onTap: () => _openList(lists[i].id),
              ),
            );
          },
        ),
      ),
      floatingActionButton: _showArchived
          ? null
          : FloatingActionButton.extended(
              onPressed: () => _showCreateDialog(context),
              icon: const Icon(Icons.add),
              label: const Text('Новый список'),
            ),
    );
  }

  void _openList(int id) {
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => ShoppingListDetailScreen(listId: id)),
    );
  }

  Future<void> _showCreateDialog(BuildContext context) async {
    final controller = TextEditingController();
    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Новый список покупок'),
        content: TextField(
          controller: controller,
          autofocus: true,
          decoration: const InputDecoration(
            hintText: 'Название (необязательно)',
            prefixIcon: Icon(Icons.drive_file_rename_outline),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Отмена'),
          ),
          FilledButton(
            onPressed: () async {
              try {
                final title = controller.text.trim().isEmpty
                    ? 'Список покупок'
                    : controller.text.trim();
                final detail = await ref.read(shoppingRepositoryProvider).createList(title);
                if (!ctx.mounted) return;
                Navigator.pop(ctx);
                ref.invalidate(shoppingListsProvider(_showArchived));
                _openList(detail.id);
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
        ],
      ),
    );
  }

  Future<void> _showJoinDialog(BuildContext context) async {
    final controller = TextEditingController();
    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Присоединиться к списку'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('Введите 6-значный код, который вам прислал владелец списка.'),
            const SizedBox(height: 12),
            TextField(
              controller: controller,
              autofocus: true,
              textCapitalization: TextCapitalization.characters,
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 28,
                fontWeight: FontWeight.w700,
                letterSpacing: 6,
              ),
              decoration: const InputDecoration(hintText: 'XXXXXX'),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Отмена'),
          ),
          FilledButton(
            onPressed: () async {
              final code = controller.text.trim();
              if (code.length < 4) return;
              try {
                final listId = await ref.read(shoppingRepositoryProvider).joinByCode(code);
                if (!ctx.mounted) return;
                Navigator.pop(ctx);
                ref.invalidate(shoppingListsProvider(_showArchived));
                _openList(listId);
              } on ApiException catch (e) {
                if (ctx.mounted) {
                  ScaffoldMessenger.of(ctx).showSnackBar(
                    SnackBar(content: Text(e.message)),
                  );
                }
              }
            },
            child: const Text('Войти'),
          ),
        ],
      ),
    );
  }
}

class _ListCard extends StatelessWidget {
  const _ListCard({required this.summary, required this.onTap});
  final ShoppingListSummary summary;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return MxCard(
      onTap: onTap,
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              MxAccentTile(
                icon: summary.isArchived ? Icons.archive_outlined : Icons.shopping_cart_outlined,
                accent: summary.isArchived ? MxAccent.neutral : MxAccent.tools,
                size: 40,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      summary.title,
                      style: const TextStyle(
                        color: MX.fg, fontWeight: FontWeight.w700, fontSize: 15,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 2),
                    Text(
                      summary.isArchived
                          ? 'Архив · ${DateFormatter.shortDayMonth(summary.archivedAt!)}'
                          : 'Создан ${DateFormatter.relative(summary.createdAt)}',
                      style: const TextStyle(color: MX.fgMicro, fontSize: 12),
                    ),
                  ],
                ),
              ),
              Text(
                '${summary.checkedCount}/${summary.itemsCount}',
                style: TextStyle(
                  fontSize: 14, fontWeight: FontWeight.w700,
                  color: summary.isCompleted ? MX.accentTools : MX.fgMuted,
                ),
              ),
            ],
          ),
          if (summary.itemsCount > 0) ...[
            const SizedBox(height: 12),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: summary.progress,
                minHeight: 4,
                backgroundColor: MX.surfaceOverlay,
                color: summary.isCompleted ? MX.accentTools : MX.accentAi,
              ),
            ),
          ],
        ],
      ),
    );
  }
}
