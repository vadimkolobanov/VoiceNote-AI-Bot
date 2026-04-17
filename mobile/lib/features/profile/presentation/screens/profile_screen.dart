import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:voicenote_ai/core/router/app_routes.dart';
import 'package:voicenote_ai/features/auth/application/session_controller.dart';
import 'package:voicenote_ai/features/payments/data/repositories/payments_repository.dart';

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(sessionControllerProvider);
    final user = session.user;
    final subscriptionAsync = ref.watch(subscriptionProvider);

    if (user == null) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }

    final scheme = Theme.of(context).colorScheme;
    final xpForCurrent = _xpForLevel(user.level);
    final xpForNext = _xpForLevel(user.level + 1);
    final progress = ((user.xp - xpForCurrent) / (xpForNext - xpForCurrent)).clamp(0.0, 1.0);

    return Scaffold(
      appBar: AppBar(title: const Text('Профиль')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                children: [
                  CircleAvatar(
                    radius: 32,
                    backgroundColor: scheme.primaryContainer,
                    child: Text(
                      (user.firstName.isNotEmpty ? user.firstName[0] : '?').toUpperCase(),
                      style: TextStyle(
                        fontSize: 28,
                        fontWeight: FontWeight.w700,
                        color: scheme.onPrimaryContainer,
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    user.firstName,
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                  ),
                  const SizedBox(height: 14),
                  Row(
                    children: [
                      Text('Уровень ${user.level}',
                          style: Theme.of(context).textTheme.bodyMedium),
                      const Spacer(),
                      Text('${user.xp} / $xpForNext XP',
                          style: Theme.of(context).textTheme.bodySmall),
                    ],
                  ),
                  const SizedBox(height: 6),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(8),
                    child: LinearProgressIndicator(
                      value: progress,
                      minHeight: 8,
                      backgroundColor: scheme.surfaceContainerHighest,
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          _SectionTitle(title: 'Подписка'),
          subscriptionAsync.when(
            loading: () => const Card(
              child: Padding(
                padding: EdgeInsets.all(16),
                child: Center(child: CircularProgressIndicator()),
              ),
            ),
            error: (e, _) => Card(
              child: ListTile(
                leading: const Icon(Icons.error_outline),
                title: Text('Не удалось загрузить: $e'),
              ),
            ),
            data: (sub) => Card(
              child: ListTile(
                leading: Icon(
                  sub.isActive ? Icons.workspace_premium : Icons.lock_outline,
                  color: sub.isActive ? Colors.amber.shade700 : scheme.outline,
                ),
                title: Text(sub.isActive ? 'Premium активна' : 'Бесплатный план'),
                subtitle: sub.isActive && sub.expiresAt != null
                    ? Text('До ${sub.expiresAt!.toLocal().toString().split(' ').first}')
                    : const Text('Открой AI-агента и больше'),
                trailing: FilledButton.tonal(
                  onPressed: () => context.push(AppRoutes.paywall),
                  child: Text(sub.isActive ? 'Управлять' : 'Подписаться'),
                ),
              ),
            ),
          ),
          const SizedBox(height: 16),
          _SectionTitle(title: 'Разделы'),
          Card(
            child: Column(
              children: [
                _ProfileTile(
                  icon: Icons.shopping_cart_outlined,
                  title: 'Список покупок',
                  onTap: () => context.push(AppRoutes.shopping),
                ),
                const Divider(height: 1),
                _ProfileTile(
                  icon: Icons.cake_outlined,
                  title: 'Дни рождения',
                  onTap: () => context.push(AppRoutes.birthdays),
                ),
                const Divider(height: 1),
                _ProfileTile(
                  icon: Icons.emoji_events_outlined,
                  title: 'Достижения',
                  onTap: () => context.push(AppRoutes.achievements),
                ),
                const Divider(height: 1),
                _ProfileTile(
                  icon: Icons.settings_outlined,
                  title: 'Настройки',
                  onTap: () => context.push(AppRoutes.settings),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          TextButton.icon(
            icon: const Icon(Icons.logout),
            label: const Text('Выйти'),
            style: TextButton.styleFrom(foregroundColor: scheme.error),
            onPressed: () => ref.read(sessionControllerProvider.notifier).logout(),
          ),
        ],
      ),
    );
  }

  int _xpForLevel(int level) {
    if (level <= 1) return 0;
    return ((level - 1) * (level - 1) * 100);
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle({required this.title});
  final String title;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(4, 8, 0, 8),
      child: Text(
        title.toUpperCase(),
        style: Theme.of(context).textTheme.labelSmall?.copyWith(
              fontWeight: FontWeight.w700,
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
      ),
    );
  }
}

class _ProfileTile extends StatelessWidget {
  const _ProfileTile({required this.icon, required this.title, required this.onTap});
  final IconData icon;
  final String title;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: Icon(icon),
      title: Text(title),
      trailing: const Icon(Icons.chevron_right),
      onTap: onTap,
    );
  }
}
