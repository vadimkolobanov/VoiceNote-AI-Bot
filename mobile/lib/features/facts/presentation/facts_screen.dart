import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/theme/mx_tokens.dart';
import 'package:voicenote_ai/features/facts/data/models/fact.dart';
import 'package:voicenote_ai/features/facts/data/repositories/facts_repository.dart';

/// S15 — «Что я о тебе знаю» (PRODUCT_PLAN.md §2.2 + §6.4).
///
/// Группировка по `kind`, плоский список с тапом для редактирования.
/// Авто-извлечение фактов делается бэком только для Pro-юзеров (§6.4),
/// но просмотр и ручное редактирование открыты всем.
class FactsScreen extends ConsumerWidget {
  const FactsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final factsAsync = ref.watch(factsListProvider);
    final t = Theme.of(context);

    return Scaffold(
      backgroundColor: MX.bgBase,
      appBar: AppBar(
        backgroundColor: MX.bgBase,
        surfaceTintColor: Colors.transparent,
        title: const Text('Что я о тебе знаю'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.pop(),
        ),
      ),
      body: RefreshIndicator(
        color: MX.accentAi,
        onRefresh: () async => ref.invalidate(factsListProvider),
        child: factsAsync.when(
          loading: () => const Center(child: CircularProgressIndicator(color: MX.accentAi)),
          error: (e, _) => ListView(
            padding: const EdgeInsets.all(20),
            children: [_ErrorCard(error: e)],
          ),
          data: (items) {
            if (items.isEmpty) {
              return ListView(
                padding: const EdgeInsets.all(20),
                children: [_EmptyCard(t: t)],
              );
            }
            final groups = _groupByKind(items);
            return ListView(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
              children: [
                for (final entry in groups.entries) ...[
                  Padding(
                    padding: const EdgeInsets.fromLTRB(4, 16, 4, 8),
                    child: Text(
                      _kindLabel(entry.key),
                      style: t.textTheme.titleSmall?.copyWith(color: MX.fgMuted),
                    ),
                  ),
                  for (final f in entry.value)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: _FactCard(fact: f),
                    ),
                ],
              ],
            );
          },
        ),
      ),
    );
  }
}

class _FactCard extends ConsumerWidget {
  const _FactCard({required this.fact});
  final Fact fact;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final color = _accentForKind(fact.kind);
    return Material(
      color: MX.surfaceOverlay,
      borderRadius: BorderRadius.circular(MX.rMd),
      child: InkWell(
        borderRadius: BorderRadius.circular(MX.rMd),
        onTap: () => _editFact(context, ref, fact),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(MX.rMd),
            border: Border.all(color: MX.line),
          ),
          child: Row(
            children: [
              Container(
                width: 32, height: 32,
                decoration: BoxDecoration(
                  color: color.withAlpha(40),
                  borderRadius: BorderRadius.circular(MX.rSm),
                ),
                child: Icon(_iconForKind(fact.kind), color: color, size: 16),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(fact.humanLabel,
                        style: Theme.of(context)
                            .textTheme
                            .bodyLarge
                            ?.copyWith(fontWeight: FontWeight.w600)),
                    if (fact.humanSubtitle.isNotEmpty) ...[
                      const SizedBox(height: 2),
                      Text(
                        fact.humanSubtitle,
                        style: Theme.of(context)
                            .textTheme
                            .bodySmall
                            ?.copyWith(color: MX.fgMuted),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ],
                ),
              ),
              IconButton(
                icon: const Icon(Icons.delete_outline, color: MX.fgFaint, size: 20),
                onPressed: () => _confirmDelete(context, ref, fact),
                tooltip: 'Удалить',
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _editFact(BuildContext context, WidgetRef ref, Fact f) async {
    // M6.3: простое редактирование `key` в одном поле; полная редактура
    // value-JSON попадёт в M6.5.
    final result = await showDialog<String>(
      context: context,
      builder: (_) => _EditDialog(initial: f.key),
    );
    if (result == null || result == f.key) return;
    try {
      await ref.read(factsRepositoryProvider).patch(f.id, {'key': result});
      ref.invalidate(factsListProvider);
    } on ApiException catch (e) {
      _toast(context, e.message);
    } catch (e) {
      _toast(context, '$e');
    }
  }

  Future<void> _confirmDelete(BuildContext context, WidgetRef ref, Fact f) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Забыть это?'),
        content: Text('Я перестану помнить «${f.humanLabel}». Откатить нельзя.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Нет')),
          TextButton(onPressed: () => Navigator.pop(context, true), child: const Text('Удалить')),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await ref.read(factsRepositoryProvider).delete(f.id);
      ref.invalidate(factsListProvider);
    } on ApiException catch (e) {
      _toast(context, e.message);
    } catch (e) {
      _toast(context, '$e');
    }
  }

  void _toast(BuildContext context, String msg) {
    if (!context.mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }
}

class _EditDialog extends StatefulWidget {
  const _EditDialog({required this.initial});
  final String initial;

  @override
  State<_EditDialog> createState() => _EditDialogState();
}

class _EditDialogState extends State<_EditDialog> {
  late final TextEditingController _ctl =
      TextEditingController(text: widget.initial);

  @override
  void dispose() {
    _ctl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Изменить ключ'),
      content: TextField(controller: _ctl, autofocus: true),
      actions: [
        TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Отмена')),
        FilledButton(
            onPressed: () => Navigator.pop(context, _ctl.text.trim()),
            child: const Text('Сохранить')),
      ],
    );
  }
}

class _EmptyCard extends StatelessWidget {
  const _EmptyCard({required this.t});
  final ThemeData t;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: MX.surfaceOverlay,
        borderRadius: BorderRadius.circular(MX.rLg),
        border: Border.all(color: MX.line),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Пока я о тебе ничего не знаю.', style: t.textTheme.titleLarge),
          const SizedBox(height: 8),
          Text(
            'Я начну запоминать факты автоматически — после Pro-подписки '
            '(имена, места, привычки). Сейчас можно добавить вручную.',
            style: t.textTheme.bodyMedium?.copyWith(color: MX.fgMuted),
          ),
        ],
      ),
    );
  }
}

class _ErrorCard extends StatelessWidget {
  const _ErrorCard({required this.error});
  final Object error;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: MX.accentSecuritySoft,
        borderRadius: BorderRadius.circular(MX.rMd),
        border: Border.all(color: MX.accentSecurityLine),
      ),
      child: Row(
        children: [
          const Icon(Icons.error_outline, color: MX.accentSecurity),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              error.toString(),
              style: Theme.of(context).textTheme.bodySmall?.copyWith(color: MX.fg),
            ),
          ),
        ],
      ),
    );
  }
}

Map<String, List<Fact>> _groupByKind(List<Fact> items) {
  const order = ['person', 'place', 'preference', 'schedule', 'other'];
  final map = <String, List<Fact>>{for (final k in order) k: []};
  for (final f in items) {
    map.putIfAbsent(f.kind, () => []).add(f);
  }
  // удаляем пустые группы
  map.removeWhere((_, v) => v.isEmpty);
  return map;
}

String _kindLabel(String k) {
  switch (k) {
    case 'person':
      return 'Люди';
    case 'place':
      return 'Места';
    case 'preference':
      return 'Предпочтения';
    case 'schedule':
      return 'Расписание';
    case 'other':
    default:
      return 'Другое';
  }
}

IconData _iconForKind(String k) {
  switch (k) {
    case 'person':
      return Icons.person_outline;
    case 'place':
      return Icons.place_outlined;
    case 'preference':
      return Icons.favorite_outline;
    case 'schedule':
      return Icons.schedule;
    case 'other':
    default:
      return Icons.label_outline;
  }
}

Color _accentForKind(String k) {
  switch (k) {
    case 'person':
      return MX.accentAi;
    case 'place':
      return MX.accentTools;
    case 'preference':
      return MX.accentPurple;
    case 'schedule':
      return MX.statusWarning;
    default:
      return MX.fgMuted;
  }
}
