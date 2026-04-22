import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/core/errors/api_exception.dart';
import 'package:voicenote_ai/core/theme/mx_tokens.dart';
import 'package:voicenote_ai/features/auth/application/session_controller.dart';
import 'package:voicenote_ai/features/auth/data/models/dev_user.dart';
import 'package:voicenote_ai/features/auth/data/repositories/auth_repository.dart';

/// Методекс-онбординг + вход.
///
/// Показывает все запланированные способы входа (Email, Telegram-код,
/// Госуслуги, MAX) — большинство пока заглушки «Скоро». Снизу — одна
/// dev-кнопка «Войти как Deco» для быстрого входа под тестовым
/// пользователем. Полный список dev-юзеров всё ещё доступен по долгому
/// нажатию на ту же кнопку.
class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  bool _loading = false;

  Future<void> _devLoginAsDeco() async {
    final users = await _fetchDevUsers();
    if (users == null) return;
    final deco = users.firstWhere(
      (u) => (u.username ?? '').toLowerCase().contains('metodex') ||
             (u.firstName ?? '').toLowerCase() == 'deco',
      orElse: () => users.first,
    );
    await _devLoginAs(deco.telegramId);
  }

  Future<List<DevUser>?> _fetchDevUsers() async {
    setState(() => _loading = true);
    try {
      return await ref.read(authRepositoryProvider).listDevUsers();
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
      }
      return null;
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _devLoginAs(int telegramId) async {
    setState(() => _loading = true);
    try {
      await ref.read(sessionControllerProvider.notifier).devLogin(telegramId);
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _showDevPicker() async {
    final users = await _fetchDevUsers();
    if (users == null || !mounted) return;
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (ctx) => _DevUsersSheet(
        users: users,
        onPick: (id) {
          Navigator.pop(ctx);
          _devLoginAs(id);
        },
      ),
    );
  }

  void _soon(String what) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('$what появится в ближайших обновлениях')),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(24, 40, 24, 24),
          children: [
            // ── Logo
            Container(
              width: 88, height: 88,
              decoration: BoxDecoration(
                gradient: MX.brandGradient,
                borderRadius: BorderRadius.circular(MX.rXl),
                boxShadow: MX.fabGlow,
              ),
              child: const Center(
                child: Text('М',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 44,
                      fontWeight: FontWeight.w700,
                    )),
              ),
            ),
            const SizedBox(height: 32),
            Text(
              'Методекс Секретарь',
              style: Theme.of(context).textTheme.displaySmall,
            ),
            const SizedBox(height: 8),
            Text(
              'Заметки, которые думают за вас.',
              style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                    color: MX.fgMuted,
                  ),
            ),
            const SizedBox(height: 40),

            // ── Feature bullets
            const _FeatureRow(icon: Icons.mic, text: 'Голосовые заметки с AI-расшифровкой'),
            const SizedBox(height: 12),
            const _FeatureRow(icon: Icons.notifications_active_outlined, text: 'Умные напоминания и повторы'),
            const SizedBox(height: 12),
            const _FeatureRow(icon: Icons.repeat, text: 'Трекер привычек и ежедневная сводка'),

            const SizedBox(height: 40),

            // ── Auth methods
            _AuthButton(
              label: 'Войти через email',
              icon: Icons.email_outlined,
              onTap: _loading ? null : () => _soon('Email-вход'),
              primary: true,
            ),
            const SizedBox(height: 10),
            _AuthButton(
              label: 'Войти через Telegram',
              icon: Icons.telegram,
              onTap: _loading ? null : () => _soon('Вход через Telegram'),
            ),
            const SizedBox(height: 10),
            _AuthButton(
              label: 'Войти через Госуслуги',
              icon: Icons.security_outlined,
              onTap: _loading ? null : () => _soon('Вход через Госуслуги'),
            ),
            const SizedBox(height: 10),
            _AuthButton(
              label: 'Войти через MAX',
              icon: Icons.chat_bubble_outline,
              onTap: _loading ? null : () => _soon('Вход через MAX'),
            ),

            const SizedBox(height: 32),

            // ── Dev login (for testing)
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: MX.surfaceOverlay,
                borderRadius: BorderRadius.circular(MX.rMd),
                border: Border.all(color: MX.accentAiLine, style: BorderStyle.solid),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.bug_report_outlined, color: MX.accentAi, size: 18),
                      const SizedBox(width: 8),
                      Text('DEV-режим',
                          style: Theme.of(context).textTheme.labelSmall?.copyWith(
                                color: MX.accentAi,
                                fontWeight: FontWeight.w700,
                                letterSpacing: 1.2,
                              )),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Тестовая кнопка входа в аккаунт Deco. Долгое нажатие — выбор другого пользователя.',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(color: MX.fgMuted),
                  ),
                  const SizedBox(height: 12),
                  GestureDetector(
                    onLongPress: _loading ? null : _showDevPicker,
                    child: _AuthButton(
                      label: _loading ? 'Загрузка…' : 'Войти как Deco',
                      icon: Icons.person,
                      onTap: _loading ? null : _devLoginAsDeco,
                      accent: true,
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

class _FeatureRow extends StatelessWidget {
  const _FeatureRow({required this.icon, required this.text});
  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 36, height: 36,
          decoration: BoxDecoration(
            color: MX.accentAiSoft,
            borderRadius: BorderRadius.circular(MX.rSm),
          ),
          child: const Icon(Icons.check, color: MX.accentAi, size: 18),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Text(text, style: Theme.of(context).textTheme.bodyMedium),
        ),
      ],
    );
  }
}

class _AuthButton extends StatelessWidget {
  const _AuthButton({
    required this.label,
    required this.icon,
    required this.onTap,
    this.primary = false,
    this.accent = false,
  });

  final String label;
  final IconData icon;
  final VoidCallback? onTap;
  final bool primary;
  final bool accent;

  @override
  Widget build(BuildContext context) {
    final isDisabled = onTap == null;
    final Color bg, fg, border;
    if (accent) {
      bg = MX.accentAi; fg = MX.bgBase; border = MX.accentAi;
    } else if (primary) {
      bg = MX.fg; fg = MX.bgBase; border = MX.fg;
    } else {
      bg = Colors.transparent; fg = MX.fg; border = MX.lineStrong;
    }

    return Opacity(
      opacity: isDisabled ? 0.55 : 1,
      child: Material(
        color: bg,
        borderRadius: BorderRadius.circular(MX.rFull),
        child: InkWell(
          borderRadius: BorderRadius.circular(MX.rFull),
          onTap: onTap,
          child: Container(
            height: 52,
            padding: const EdgeInsets.symmetric(horizontal: 20),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(MX.rFull),
              border: Border.all(color: border),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(icon, size: 20, color: fg),
                const SizedBox(width: 10),
                Text(
                  label,
                  style: TextStyle(
                    color: fg,
                    fontSize: 15,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _DevUsersSheet extends StatelessWidget {
  const _DevUsersSheet({required this.users, required this.onPick});
  final List<DevUser> users;
  final ValueChanged<int> onPick;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Container(
        constraints: BoxConstraints(maxHeight: MediaQuery.of(context).size.height * 0.8),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(height: 8),
            Container(width: 40, height: 4, decoration: BoxDecoration(
              color: MX.fgGhost, borderRadius: BorderRadius.circular(MX.rFull),
            )),
            const SizedBox(height: 16),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Text('Выбрать пользователя',
                  style: Theme.of(context).textTheme.titleMedium),
            ),
            const SizedBox(height: 12),
            Flexible(
              child: ListView.builder(
                shrinkWrap: true,
                padding: const EdgeInsets.symmetric(horizontal: 12),
                itemCount: users.length,
                itemBuilder: (_, i) {
                  final u = users[i];
                  return ListTile(
                    leading: CircleAvatar(
                      backgroundColor: MX.accentAiSoft,
                      child: Text(u.displayName.characters.firstOrNull?.toUpperCase() ?? '?',
                          style: const TextStyle(color: MX.accentAi, fontWeight: FontWeight.w700)),
                    ),
                    title: Text(u.displayName, style: const TextStyle(fontWeight: FontWeight.w600)),
                    subtitle: Text('id ${u.telegramId} · ${u.notesCount} заметок'),
                    onTap: () => onPick(u.telegramId),
                  );
                },
              ),
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }
}
