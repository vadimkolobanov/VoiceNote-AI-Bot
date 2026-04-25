import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import 'package:voicenote_ai/core/theme/mx_tokens.dart';
import 'package:voicenote_ai/features/moments/application/moments_providers.dart';
import 'package:voicenote_ai/features/moments/data/models/moment.dart';
import 'package:voicenote_ai/features/moments/data/repositories/moments_repository.dart';

/// S10 — Детали момента (PRODUCT_PLAN.md §2.6).
class MomentDetailsScreen extends ConsumerStatefulWidget {
  const MomentDetailsScreen({super.key, required this.momentId});
  final int momentId;

  @override
  ConsumerState<MomentDetailsScreen> createState() => _MomentDetailsScreenState();
}

class _MomentDetailsScreenState extends ConsumerState<MomentDetailsScreen> {
  Moment? _moment;
  bool _busy = false;
  Object? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final m = await ref.read(momentsRepositoryProvider).get(widget.momentId);
      setState(() => _moment = m);
    } catch (e) {
      setState(() => _error = e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _withRepo(Future<Moment> Function(MomentsRepository) op) async {
    final repo = ref.read(momentsRepositoryProvider);
    setState(() => _busy = true);
    try {
      final updated = await op(repo);
      setState(() => _moment = updated);
      ref.invalidate(todayProvider);
      ref.read(timelineControllerProvider.notifier).refresh();
    } catch (e) {
      _toast('$e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _toast(String msg) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Scaffold(
      backgroundColor: MX.bgBase,
      appBar: AppBar(
        backgroundColor: MX.bgBase,
        surfaceTintColor: Colors.transparent,
        title: const Text('Момент'),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () => context.pop(),
        ),
      ),
      body: _busy && _moment == null
          ? const Center(child: CircularProgressIndicator(color: MX.accentAi))
          : _error != null
              ? Center(child: Text('$_error', style: t.textTheme.bodyMedium))
              : _moment == null
                  ? const SizedBox.shrink()
                  : ListView(
                      padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
                      children: [
                        _Header(moment: _moment!),
                        const SizedBox(height: 16),
                        _SectionTitle('Текст'),
                        const SizedBox(height: 8),
                        Container(
                          padding: const EdgeInsets.all(14),
                          decoration: BoxDecoration(
                            color: MX.surfaceOverlay,
                            borderRadius: BorderRadius.circular(MX.rMd),
                            border: Border.all(color: MX.line),
                          ),
                          child: Text(
                            _moment!.rawText,
                            style: t.textTheme.bodyLarge,
                          ),
                        ),
                        if (_moment!.summary != null && _moment!.summary!.isNotEmpty) ...[
                          const SizedBox(height: 20),
                          _SectionTitle('Кратко'),
                          const SizedBox(height: 8),
                          Container(
                            padding: const EdgeInsets.all(14),
                            decoration: BoxDecoration(
                              color: MX.surfaceOverlay,
                              borderRadius: BorderRadius.circular(MX.rMd),
                              border: Border.all(color: MX.line),
                            ),
                            child: Text(
                              _moment!.summary!,
                              style: t.textTheme.bodyMedium?.copyWith(color: MX.fgMuted),
                            ),
                          ),
                        ],
                        const SizedBox(height: 20),
                        _SectionTitle('Грани'),
                        const SizedBox(height: 8),
                        _FacetChips(facets: _moment!.facets),
                        const SizedBox(height: 24),
                        _ActionsBar(
                          moment: _moment!,
                          busy: _busy,
                          onComplete: () => _withRepo((r) => r.complete(_moment!.id)),
                          onSnooze: _onSnoozeTap,
                          onDelete: _onDeleteTap,
                        ),
                      ],
                    ),
    );
  }

  Future<void> _onSnoozeTap() async {
    final until = await showModalBottomSheet<DateTime>(
      context: context,
      backgroundColor: MX.bgCard,
      builder: (_) => _SnoozeSheet(),
    );
    if (until == null) return;
    await _withRepo((r) => r.snooze(_moment!.id, until));
    if (mounted) _toast('Перенёс на ${DateFormat.MMMd('ru').add_Hm().format(until)}');
  }

  Future<void> _onDeleteTap() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Удалить?'),
        content: const Text('Момент скроется из списков. Это можно откатить в течение 30 дней.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Нет')),
          TextButton(onPressed: () => Navigator.pop(context, true), child: const Text('Удалить')),
        ],
      ),
    );
    if (confirmed != true) return;
    setState(() => _busy = true);
    try {
      await ref.read(momentsRepositoryProvider).delete(_moment!.id);
      ref.invalidate(todayProvider);
      ref.read(timelineControllerProvider.notifier).refresh();
      if (mounted) context.pop();
    } catch (e) {
      _toast('$e');
      if (mounted) setState(() => _busy = false);
    }
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.moment});
  final Moment moment;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          moment.title.isEmpty ? '(без названия)' : moment.title,
          style: t.textTheme.headlineSmall?.copyWith(
            decoration: moment.isDone ? TextDecoration.lineThrough : null,
            color: moment.isDone ? MX.fgFaint : MX.fg,
          ),
        ),
        const SizedBox(height: 6),
        Wrap(
          spacing: 8,
          children: [
            _MetaPill(text: _kindLabel(moment.kind)),
            if (moment.occursAt != null)
              _MetaPill(text: DateFormat.yMMMd('ru').add_Hm().format(moment.occursAt!)),
            _MetaPill(text: 'статус: ${_statusLabel(moment.status)}'),
          ],
        ),
      ],
    );
  }
}

class _MetaPill extends StatelessWidget {
  const _MetaPill({required this.text});
  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: MX.surfaceOverlay,
        borderRadius: BorderRadius.circular(MX.rFull),
        border: Border.all(color: MX.line),
      ),
      child: Text(text,
          style: Theme.of(context).textTheme.bodySmall?.copyWith(color: MX.fgMuted)),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.text);
  final String text;
  @override
  Widget build(BuildContext context) => Text(
        text,
        style: Theme.of(context).textTheme.titleSmall?.copyWith(color: MX.fgMuted),
      );
}

class _FacetChips extends StatelessWidget {
  const _FacetChips({required this.facets});
  final Map<String, dynamic> facets;

  @override
  Widget build(BuildContext context) {
    final chips = <Widget>[];
    final people = (facets['people'] as List?)?.cast<String>() ?? [];
    final places = (facets['places'] as List?)?.cast<String>() ?? [];
    final topics = (facets['topics'] as List?)?.cast<String>() ?? [];
    for (final p in people) {
      chips.add(_chip('человек: $p', Icons.person_outline, MX.accentAi));
    }
    for (final p in places) {
      chips.add(_chip('место: $p', Icons.place_outlined, MX.accentTools));
    }
    for (final tp in topics) {
      chips.add(_chip(tp, Icons.tag, MX.accentPurple));
    }
    final priority = facets['priority'] as String?;
    if (priority != null && priority != 'normal') {
      chips.add(_chip('приоритет: $priority', Icons.flag_outlined, MX.statusWarning));
    }
    if (chips.isEmpty) {
      return Text(
        'Граней пока нет.',
        style: Theme.of(context).textTheme.bodySmall?.copyWith(color: MX.fgFaint),
      );
    }
    return Wrap(spacing: 8, runSpacing: 8, children: chips);
  }

  Widget _chip(String text, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color.withAlpha(30),
        borderRadius: BorderRadius.circular(MX.rFull),
        border: Border.all(color: color.withAlpha(60)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 6),
          Text(text, style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }
}

class _ActionsBar extends StatelessWidget {
  const _ActionsBar({
    required this.moment,
    required this.busy,
    required this.onComplete,
    required this.onSnooze,
    required this.onDelete,
  });

  final Moment moment;
  final bool busy;
  final VoidCallback onComplete;
  final VoidCallback onSnooze;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        if (moment.isActive) ...[
          Expanded(
            child: FilledButton.icon(
              onPressed: busy ? null : onComplete,
              icon: const Icon(Icons.check_circle_outline),
              label: const Text('Готово'),
            ),
          ),
          const SizedBox(width: 8),
          OutlinedButton.icon(
            onPressed: busy ? null : onSnooze,
            icon: const Icon(Icons.snooze),
            label: const Text('Отложить'),
          ),
          const SizedBox(width: 8),
        ],
        IconButton(
          tooltip: 'Удалить',
          onPressed: busy ? null : onDelete,
          icon: const Icon(Icons.delete_outline, color: MX.accentSecurity),
        ),
      ],
    );
  }
}

class _SnoozeSheet extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final now = DateTime.now();
    final options = <(String, DateTime)>[
      ('+1 час', now.add(const Duration(hours: 1))),
      ('+3 часа', now.add(const Duration(hours: 3))),
      ('Завтра утром (9:00)', DateTime(now.year, now.month, now.day + 1, 9)),
      ('Через неделю', now.add(const Duration(days: 7))),
    ];
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(8, 16, 8, 16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: MX.fgGhost,
                borderRadius: BorderRadius.circular(MX.rFull),
              ),
            ),
            const SizedBox(height: 16),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Text('Когда напомнить ещё раз?',
                    style: Theme.of(context).textTheme.titleMedium),
              ),
            ),
            const SizedBox(height: 12),
            for (final o in options)
              ListTile(
                title: Text(o.$1),
                subtitle: Text(DateFormat.MMMd('ru').add_Hm().format(o.$2)),
                onTap: () => Navigator.pop(context, o.$2),
              ),
          ],
        ),
      ),
    );
  }
}

String _kindLabel(String kind) {
  switch (kind) {
    case 'task':
      return 'Дело';
    case 'shopping':
      return 'Покупки';
    case 'habit':
      return 'Привычка';
    case 'birthday':
      return 'ДР';
    case 'cycle':
      return 'Цикл';
    case 'thought':
      return 'Мысль';
    case 'note':
    default:
      return 'Заметка';
  }
}

String _statusLabel(String status) {
  switch (status) {
    case 'done':
      return 'выполнен';
    case 'archived':
      return 'архив';
    case 'trashed':
      return 'удалён';
    default:
      return 'активен';
  }
}
