import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/theme/mx_tokens.dart';
import 'package:voicenote_ai/features/auth/application/session_controller.dart';
import 'package:voicenote_ai/features/auth/data/models/user.dart';
import 'package:voicenote_ai/features/onboarding/data/onboarding_flag.dart';
import 'package:voicenote_ai/features/profile/data/profile_repository.dart';

/// S9 — Профиль (PRODUCT_PLAN.md §2.2 + §5.2 PATCH /profile).
class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(sessionControllerProvider);
    final user = session.user;
    final t = Theme.of(context);

    return CustomScrollView(
      slivers: [
        SliverAppBar(
          floating: true,
          backgroundColor: MX.bgBase,
          surfaceTintColor: Colors.transparent,
          title: Text('Профиль', style: t.textTheme.titleLarge),
        ),
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 120),
          sliver: SliverList(
            delegate: SliverChildListDelegate.fixed([
              if (user != null) _Header(user: user) else const SizedBox.shrink(),
              const SizedBox(height: 16),
              const _StatsSection(),
              const SizedBox(height: 16),
              _MenuTile(
                icon: Icons.badge_outlined,
                title: 'Имя',
                subtitle: user?.displayName ?? 'Не указано',
                onTap: user == null ? null : () => _editName(context, ref, user),
              ),
              _MenuTile(
                icon: Icons.notifications_outlined,
                title: 'Утренний дайджест',
                subtitle: user?.digestHour != null
                    ? 'Каждое утро в ${user!.digestHour!.toString().padLeft(2, '0')}:00'
                    : 'Не настроен',
                onTap: user == null ? null : () => _editDigestHour(context, ref, user),
              ),
              _MenuTile(
                icon: Icons.alarm_outlined,
                title: 'Напомнить заранее',
                subtitle: (user?.preReminderMinutes ?? 0) == 0
                    ? 'В момент события'
                    : 'За ${user!.preReminderMinutes} мин до',
                onTap: user == null
                    ? null
                    : () => _editPreReminder(context, ref, user),
              ),
              _MenuTile(
                icon: Icons.public,
                title: 'Часовой пояс',
                subtitle:
                    user == null ? '—' : tzHumanLabel(user.timezone),
                onTap: user == null ? null : () => _editTimezone(context, ref, user),
              ),
              _MenuTile(
                icon: Icons.psychology_outlined,
                title: 'Что я о тебе знаю',
                subtitle: 'Накопленные факты',
                onTap: () => context.push('/facts'),
              ),
              _MenuTile(
                icon: Icons.auto_stories_outlined,
                title: 'Расскажи о себе',
                subtitle: 'Обучи память — рассказом, не задачей',
                onTap: () => context.push('/learning'),
              ),
              _MenuTile(
                icon: Icons.workspace_premium_outlined,
                title: 'Подписка Pro',
                subtitle: user?.isPro == true ? 'Активна' : 'Не активна — оформить',
                onTap: () => context.push('/paywall'),
              ),
              _MenuTile(
                icon: Icons.school_outlined,
                title: 'Показать обзор снова',
                subtitle: 'Три слайда о голосе, памяти и вопросах',
                onTap: () async {
                  await ref.read(onboardingSeenProvider.notifier).reset();
                  if (context.mounted) context.go('/onboarding');
                },
              ),
              _MenuTile(
                icon: Icons.feedback_outlined,
                title: 'Помоги стать лучше',
                subtitle: 'Что не так? Что классно? Что добавить?',
                onTap: () => context.push('/feedback'),
              ),
              const SizedBox(height: 24),
              OutlinedButton(
                onPressed: () => ref.read(sessionControllerProvider.notifier).logout(),
                child: const Padding(
                  padding: EdgeInsets.symmetric(vertical: 12),
                  child: Text('Выйти', style: TextStyle(color: MX.accentSecurity)),
                ),
              ),
              const SizedBox(height: 8),
              TextButton(
                onPressed: () => _confirmDeleteAccount(context, ref),
                child: const Text(
                  'Удалить мою память',
                  style: TextStyle(color: MX.accentSecurity),
                ),
              ),
            ]),
          ),
        ),
      ],
    );
  }

  Future<void> _editName(BuildContext context, WidgetRef ref, User user) async {
    final result = await showDialog<String>(
      context: context,
      builder: (_) => _SingleFieldDialog(
        title: 'Имя',
        initial: user.displayName ?? '',
        hint: 'Как тебя называть',
      ),
    );
    if (result == null) return;
    await _patch(context, ref, () =>
        ref.read(profileRepositoryProvider).patch(displayName: result));
  }

  Future<void> _editTimezone(BuildContext context, WidgetRef ref, User user) async {
    // РФ + СНГ — фиксированный UTC, без DST.
    // Зарубежье — только название (там DST, точный смещение зависит от сезона).
    const tzs = <_Tz>[
      // ── РФ + ближнее зарубежье (по offset на запад → восток) ──
      _Tz('Europe/Kaliningrad', 'Калининград', '+2'),
      _Tz('Europe/Minsk',       'Минск',       '+3'),
      _Tz('Europe/Moscow',      'Москва',      '+3'),
      _Tz('Europe/Kyiv',        'Киев',        '+3'),
      _Tz('Europe/Volgograd',   'Волгоград',   '+3'),
      _Tz('Europe/Samara',      'Самара',      '+4'),
      _Tz('Europe/Saratov',     'Саратов',     '+4'),
      _Tz('Europe/Astrakhan',   'Астрахань',   '+4'),
      _Tz('Asia/Yekaterinburg', 'Екатеринбург', '+5'),
      _Tz('Asia/Tashkent',      'Ташкент',     '+5'),
      _Tz('Asia/Almaty',        'Алматы',      '+5'),
      _Tz('Asia/Omsk',          'Омск',        '+6'),
      _Tz('Asia/Bishkek',       'Бишкек',      '+6'),
      _Tz('Asia/Krasnoyarsk',   'Красноярск',  '+7'),
      _Tz('Asia/Novosibirsk',   'Новосибирск', '+7'),
      _Tz('Asia/Barnaul',       'Барнаул',     '+7'),
      _Tz('Asia/Tomsk',         'Томск',       '+7'),
      _Tz('Asia/Irkutsk',       'Иркутск',     '+8'),
      _Tz('Asia/Yakutsk',       'Якутск',      '+9'),
      _Tz('Asia/Vladivostok',   'Владивосток', '+10'),
      _Tz('Asia/Magadan',       'Магадан',     '+11'),
      _Tz('Asia/Sakhalin',      'Южно-Сахалинск', '+11'),
      _Tz('Asia/Kamchatka',     'Петропавловск-Камчатский', '+12'),
      // ── Кавказ (DST нет) ──
      _Tz('Asia/Tbilisi',       'Тбилиси',     '+4'),
      _Tz('Asia/Yerevan',       'Ереван',      '+4'),
      _Tz('Asia/Baku',          'Баку',        '+4'),
      // ── Европа (DST есть, смещение плавает — не показываем) ──
      _Tz('Europe/Chisinau',    'Кишинёв',     null),
      _Tz('Europe/Berlin',      'Берлин',      null),
      _Tz('Europe/Paris',       'Париж',       null),
      _Tz('Europe/London',      'Лондон',      null),
      _Tz('Europe/Lisbon',      'Лиссабон',    null),
      // ── Азия / Ближний Восток (без DST) ──
      _Tz('Asia/Jerusalem',     'Иерусалим',   null), // DST есть
      _Tz('Asia/Dubai',         'Дубай',       '+4'),
      _Tz('Asia/Bangkok',       'Бангкок',     '+7'),
      _Tz('Asia/Shanghai',      'Шанхай',      '+8'),
      _Tz('Asia/Tokyo',         'Токио',       '+9'),
      // ── Америка (DST есть) ──
      _Tz('America/New_York',   'Нью-Йорк',    null),
      _Tz('America/Chicago',    'Чикаго',      null),
      _Tz('America/Denver',     'Денвер',      null),
      _Tz('America/Los_Angeles','Лос-Анджелес', null),
      _Tz('America/Sao_Paulo',  'Сан-Паулу',   null),
      _Tz('America/Argentina/Buenos_Aires', 'Буэнос-Айрес', null),
      // ── Универсальный fallback ──
      _Tz('UTC',                'UTC',         '+0'),
    ];

    final result = await showModalBottomSheet<_Tz>(
      context: context,
      backgroundColor: MX.bgCard,
      isScrollControlled: true,
      builder: (_) => _PickerSheet<_Tz>(
        title: 'Часовой пояс',
        options: tzs,
        current: tzs.firstWhere(
          (t) => t.id == user.timezone,
          orElse: () => tzs.firstWhere((t) => t.id == 'Europe/Moscow'),
        ),
        formatLabel: (t) =>
            t.utcOffset == null ? t.label : '${t.label} · UTC${t.utcOffset}',
      ),
    );
    if (result == null) return;
    await _patch(context, ref, () =>
        ref.read(profileRepositoryProvider).patch(timezone: result.id));
  }

  Future<void> _editDigestHour(BuildContext context, WidgetRef ref, User user) async {
    final hours = List<int>.generate(24, (i) => i);
    final result = await showModalBottomSheet<int>(
      context: context,
      backgroundColor: MX.bgCard,
      builder: (_) => _PickerSheet<int>(
        title: 'Утренний дайджест',
        options: hours,
        current: user.digestHour ?? 8,
        formatLabel: (h) => '${h.toString().padLeft(2, '0')}:00',
      ),
    );
    if (result == null) return;
    await _patch(context, ref, () =>
        ref.read(profileRepositoryProvider).patch(digestHour: result));
  }

  Future<void> _editPreReminder(BuildContext context, WidgetRef ref, User user) async {
    const options = <int>[0, 5, 10, 15, 30, 60];
    final result = await showModalBottomSheet<int>(
      context: context,
      backgroundColor: MX.bgCard,
      builder: (_) => _PickerSheet<int>(
        title: 'Напомнить заранее',
        options: options,
        current: user.preReminderMinutes,
        formatLabel: (m) => m == 0 ? 'В момент события' : 'За $m мин до',
      ),
    );
    if (result == null) return;
    await _patch(context, ref, () =>
        ref.read(profileRepositoryProvider).patch(preReminderMinutes: result));
  }

  Future<void> _confirmDeleteAccount(BuildContext context, WidgetRef ref) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: MX.bgElevated,
        title: const Text('Удалить мою память?'),
        content: const Text(
          'Сразу уйдёт всё: моменты, привычки, факты, токены устройств. '
          'Откатить нельзя.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Отмена'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text(
              'Удалить всё',
              style: TextStyle(color: MX.accentSecurity),
            ),
          ),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await ref.read(profileRepositoryProvider).deleteAccount();
      // Чистим локальную сессию и кидаем на login.
      await ref.read(sessionControllerProvider.notifier).logout();
    } on ApiException catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(e.message)));
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('$e')));
      }
    }
  }

  Future<void> _patch(BuildContext context, WidgetRef ref,
      Future<User> Function() op) async {
    try {
      await op();
      // Перечитываем профиль — controller обновит state.user.
      await ref.read(sessionControllerProvider.notifier).refreshUser();
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Запомнил.')),
        );
      }
    } on ApiException catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(e.message)));
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
      }
    }
  }
}

class _StatsSection extends ConsumerWidget {
  const _StatsSection();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = Theme.of(context);
    final stats = ref.watch(profileStatsProvider);
    return stats.when(
      loading: () => Container(
        height: 120,
        decoration: BoxDecoration(
          color: MX.surfaceOverlay,
          borderRadius: BorderRadius.circular(MX.rLg),
          border: Border.all(color: MX.line),
        ),
        child: const Center(
          child: SizedBox(
            width: 22,
            height: 22,
            child: CircularProgressIndicator(strokeWidth: 2, color: MX.accentAi),
          ),
        ),
      ),
      error: (e, _) => const SizedBox.shrink(),
      data: (s) => Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: MX.surfaceOverlay,
          borderRadius: BorderRadius.circular(MX.rLg),
          border: Border.all(color: MX.line),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Статистика', style: t.textTheme.titleMedium),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: _StatTile(
                    icon: Icons.check_circle_outline,
                    color: const Color(0xFF34C759),
                    label: 'Сегодня',
                    value: '${s.doneToday}',
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: _StatTile(
                    icon: Icons.warning_amber_rounded,
                    color: s.overdueCount > 0
                        ? const Color(0xFFFF453A)
                        : MX.fgMuted,
                    label: 'Просрочено',
                    value: '${s.overdueCount}',
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: _StatTile(
                    icon: Icons.list_alt_outlined,
                    color: MX.accentAi,
                    label: 'Активных',
                    value: '${s.activeCount}',
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Icon(Icons.calendar_today_outlined,
                    size: 14, color: MX.fgMuted),
                const SizedBox(width: 6),
                Text(
                  'Эта неделя: ${s.weekCompleted}/${s.weekPlanned}',
                  style: t.textTheme.bodySmall?.copyWith(color: MX.fgMuted),
                ),
                const Spacer(),
                Text(
                  'Всего: ${s.totalMoments}',
                  style: t.textTheme.bodySmall?.copyWith(color: MX.fgMuted),
                ),
              ],
            ),
            if (s.habitStreaks.isNotEmpty) ...[
              const SizedBox(height: 12),
              const Divider(height: 1, color: MX.line),
              const SizedBox(height: 12),
              Text('Серии', style: t.textTheme.labelMedium?.copyWith(color: MX.fgMuted)),
              const SizedBox(height: 6),
              for (final h in s.habitStreaks) ...[
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: Row(
                    children: [
                      const Icon(Icons.local_fire_department,
                          size: 16, color: Color(0xFFFF9F0A)),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(h.title,
                            style: t.textTheme.bodyMedium,
                            overflow: TextOverflow.ellipsis),
                      ),
                      Text(
                        '${h.streakDays} ${_dayWord(h.streakDays)}',
                        style: t.textTheme.bodySmall?.copyWith(
                          color: MX.fg,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ],
          ],
        ),
      ),
    );
  }
}

String _dayWord(int n) {
  final m100 = n % 100;
  if (m100 >= 11 && m100 <= 14) return 'дней';
  switch (n % 10) {
    case 1:
      return 'день';
    case 2:
    case 3:
    case 4:
      return 'дня';
    default:
      return 'дней';
  }
}

class _StatTile extends StatelessWidget {
  const _StatTile({
    required this.icon,
    required this.color,
    required this.label,
    required this.value,
  });

  final IconData icon;
  final Color color;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 12),
      decoration: BoxDecoration(
        color: color.withAlpha(15),
        borderRadius: BorderRadius.circular(MX.rMd),
        border: Border.all(color: color.withAlpha(40)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color, size: 18),
          const SizedBox(height: 6),
          Text(value, style: t.textTheme.titleLarge?.copyWith(
            color: MX.fg, fontWeight: FontWeight.w700,
          )),
          Text(label, style: t.textTheme.bodySmall?.copyWith(color: MX.fgMuted)),
        ],
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.user});
  final User user;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: MX.surfaceOverlay,
        borderRadius: BorderRadius.circular(MX.rLg),
        border: Border.all(color: MX.line),
      ),
      child: Row(
        children: [
          Container(
            width: 56, height: 56,
            decoration: BoxDecoration(
              gradient: MX.brandGradient,
              borderRadius: BorderRadius.circular(MX.rFull),
            ),
            child: Center(
              child: Text(
                _firstChar(user),
                style: const TextStyle(
                    fontSize: 22, fontWeight: FontWeight.w700, color: Colors.white),
              ),
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(user.displayName ?? 'Без имени', style: t.textTheme.titleMedium),
                if (user.email != null) ...[
                  const SizedBox(height: 2),
                  Text(user.email!,
                      style: t.textTheme.bodySmall?.copyWith(color: MX.fgMuted)),
                ],
              ],
            ),
          ),
          if (user.isPro)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(
                color: MX.accentAiSoft,
                borderRadius: BorderRadius.circular(MX.rFull),
                border: Border.all(color: MX.accentAiLine),
              ),
              child: const Text('PRO',
                  style: TextStyle(
                      color: MX.accentAi, fontSize: 11, fontWeight: FontWeight.w700)),
            ),
        ],
      ),
    );
  }

  String _firstChar(User u) {
    final src = (u.displayName?.trim().isNotEmpty == true)
        ? u.displayName!
        : (u.email ?? '?');
    return src.characters.first.toUpperCase();
  }
}

class _MenuTile extends StatelessWidget {
  const _MenuTile({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Material(
        color: MX.surfaceOverlay,
        borderRadius: BorderRadius.circular(MX.rMd),
        child: InkWell(
          borderRadius: BorderRadius.circular(MX.rMd),
          onTap: onTap,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(MX.rMd),
              border: Border.all(color: MX.line),
            ),
            child: Row(
              children: [
                Icon(icon, color: MX.fgMuted, size: 22),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(title, style: Theme.of(context).textTheme.bodyMedium),
                      const SizedBox(height: 2),
                      Text(subtitle,
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              color: MX.fgMuted)),
                    ],
                  ),
                ),
                if (onTap != null) const Icon(Icons.chevron_right, color: MX.fgFaint),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _SingleFieldDialog extends StatefulWidget {
  const _SingleFieldDialog({
    required this.title,
    required this.initial,
    required this.hint,
  });
  final String title;
  final String initial;
  final String hint;

  @override
  State<_SingleFieldDialog> createState() => _SingleFieldDialogState();
}

class _SingleFieldDialogState extends State<_SingleFieldDialog> {
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
      title: Text(widget.title),
      content: TextField(
        controller: _ctl,
        autofocus: true,
        decoration: InputDecoration(hintText: widget.hint),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Отмена'),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(context, _ctl.text.trim()),
          child: const Text('Сохранить'),
        ),
      ],
    );
  }
}

class _PickerSheet<T> extends StatelessWidget {
  const _PickerSheet({
    required this.title,
    required this.options,
    required this.current,
    this.formatLabel,
  });

  final String title;
  final List<T> options;
  final T current;
  final String Function(T)? formatLabel;

  @override
  Widget build(BuildContext context) {
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
                child: Text(title, style: Theme.of(context).textTheme.titleMedium),
              ),
            ),
            const SizedBox(height: 12),
            Flexible(
              child: ListView.builder(
                shrinkWrap: true,
                itemCount: options.length,
                itemBuilder: (_, i) {
                  final v = options[i];
                  final selected = v == current;
                  return ListTile(
                    title: Text(
                      formatLabel == null ? '$v' : formatLabel!(v),
                      style: TextStyle(
                          color: selected ? MX.accentAi : MX.fg,
                          fontWeight: selected ? FontWeight.w700 : FontWeight.w400),
                    ),
                    trailing: selected
                        ? const Icon(Icons.check, color: MX.accentAi)
                        : null,
                    onTap: () => Navigator.pop(context, v),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Tz {
  const _Tz(this.id, this.label, this.utcOffset);
  final String id;
  final String label;
  final String? utcOffset; // например "+3", "-5"; null если DST (плавает)
}

/// Преобразует IANA tz id (e.g. "Europe/Moscow") в человеко-читаемый
/// «Москва · UTC+3». Если такого id нет в нашем справочнике — отдаём
/// id как есть.
String tzHumanLabel(String tzId) {
  // фикс-смещения (РФ + СНГ + некоторые без DST)
  const fixed = <String, (String, String)>{
    'Europe/Kaliningrad':         ('Калининград', '+2'),
    'Europe/Minsk':               ('Минск', '+3'),
    'Europe/Moscow':              ('Москва', '+3'),
    'Europe/Kyiv':                ('Киев', '+3'),
    'Europe/Volgograd':           ('Волгоград', '+3'),
    'Europe/Samara':              ('Самара', '+4'),
    'Europe/Saratov':             ('Саратов', '+4'),
    'Europe/Astrakhan':           ('Астрахань', '+4'),
    'Asia/Yekaterinburg':         ('Екатеринбург', '+5'),
    'Asia/Tashkent':              ('Ташкент', '+5'),
    'Asia/Almaty':                ('Алматы', '+5'),
    'Asia/Omsk':                  ('Омск', '+6'),
    'Asia/Bishkek':               ('Бишкек', '+6'),
    'Asia/Krasnoyarsk':           ('Красноярск', '+7'),
    'Asia/Novosibirsk':           ('Новосибирск', '+7'),
    'Asia/Barnaul':               ('Барнаул', '+7'),
    'Asia/Tomsk':                 ('Томск', '+7'),
    'Asia/Irkutsk':               ('Иркутск', '+8'),
    'Asia/Yakutsk':               ('Якутск', '+9'),
    'Asia/Vladivostok':           ('Владивосток', '+10'),
    'Asia/Magadan':               ('Магадан', '+11'),
    'Asia/Sakhalin':              ('Южно-Сахалинск', '+11'),
    'Asia/Kamchatka':             ('Петропавловск-Камчатский', '+12'),
    'Asia/Tbilisi':               ('Тбилиси', '+4'),
    'Asia/Yerevan':               ('Ереван', '+4'),
    'Asia/Baku':                  ('Баку', '+4'),
    'Asia/Dubai':                 ('Дубай', '+4'),
    'Asia/Bangkok':               ('Бангкок', '+7'),
    'Asia/Shanghai':              ('Шанхай', '+8'),
    'Asia/Tokyo':                 ('Токио', '+9'),
    'UTC':                        ('UTC', '+0'),
  };
  final f = fixed[tzId];
  if (f != null) return '${f.$1} · UTC${f.$2}';
  // DST-зоны — без offset (плавает по сезону)
  const dst = <String, String>{
    'Europe/Chisinau':                       'Кишинёв',
    'Europe/Berlin':                         'Берлин',
    'Europe/Paris':                          'Париж',
    'Europe/London':                         'Лондон',
    'Europe/Lisbon':                         'Лиссабон',
    'Asia/Jerusalem':                        'Иерусалим',
    'America/New_York':                      'Нью-Йорк',
    'America/Chicago':                       'Чикаго',
    'America/Denver':                        'Денвер',
    'America/Los_Angeles':                   'Лос-Анджелес',
    'America/Sao_Paulo':                     'Сан-Паулу',
    'America/Argentina/Buenos_Aires':        'Буэнос-Айрес',
  };
  return dst[tzId] ?? tzId;
}
