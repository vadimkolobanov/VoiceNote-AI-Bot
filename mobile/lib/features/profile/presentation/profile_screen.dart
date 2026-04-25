import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:voicenote_ai/core/theme/mx_tokens.dart';
import 'package:voicenote_ai/features/auth/application/session_controller.dart';

/// S9 — Профиль (PRODUCT_PLAN.md §2.2). Минимальная версия M4.
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
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: MX.surfaceOverlay,
                  borderRadius: BorderRadius.circular(MX.rLg),
                  border: Border.all(color: MX.line),
                ),
                child: Row(
                  children: [
                    Container(
                      width: 56,
                      height: 56,
                      decoration: BoxDecoration(
                        gradient: MX.brandGradient,
                        borderRadius: BorderRadius.circular(MX.rFull),
                      ),
                      child: Center(
                        child: Text(
                          (user?.displayName ?? user?.email ?? '?')
                              .characters
                              .first
                              .toUpperCase(),
                          style: const TextStyle(
                            fontSize: 22,
                            fontWeight: FontWeight.w700,
                            color: Colors.white,
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            user?.displayName ?? 'Без имени',
                            style: t.textTheme.titleMedium,
                          ),
                          if (user?.email != null) ...[
                            const SizedBox(height: 2),
                            Text(user!.email!, style: t.textTheme.bodySmall?.copyWith(color: MX.fgMuted)),
                          ],
                        ],
                      ),
                    ),
                    if (user?.isPro == true)
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                        decoration: BoxDecoration(
                          color: MX.accentAiSoft,
                          borderRadius: BorderRadius.circular(MX.rFull),
                          border: Border.all(color: MX.accentAiLine),
                        ),
                        child: const Text('PRO',
                            style: TextStyle(
                                color: MX.accentAi,
                                fontSize: 11,
                                fontWeight: FontWeight.w700)),
                      ),
                  ],
                ),
              ),
              const SizedBox(height: 24),
              _MenuTile(
                icon: Icons.notifications_outlined,
                title: 'Утренний дайджест',
                subtitle: user?.digestHour != null
                    ? 'Каждое утро в ${user!.digestHour}:00'
                    : 'Не настроен',
                onTap: () {},
              ),
              _MenuTile(
                icon: Icons.public,
                title: 'Часовой пояс',
                subtitle: user?.timezone ?? '—',
                onTap: () {},
              ),
              _MenuTile(
                icon: Icons.workspace_premium_outlined,
                title: 'Подписка Pro',
                subtitle: user?.isPro == true ? 'Активна' : 'Не активна',
                onTap: () {},
              ),
              _MenuTile(
                icon: Icons.psychology_outlined,
                title: 'Что я о тебе знаю',
                subtitle: 'Накопленные факты',
                onTap: () {},
              ),
              const SizedBox(height: 24),
              OutlinedButton(
                onPressed: () => ref.read(sessionControllerProvider.notifier).logout(),
                child: const Padding(
                  padding: EdgeInsets.symmetric(vertical: 12),
                  child: Text('Выйти', style: TextStyle(color: MX.accentSecurity)),
                ),
              ),
            ]),
          ),
        ),
      ],
    );
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
  final VoidCallback onTap;

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
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(color: MX.fgMuted)),
                    ],
                  ),
                ),
                const Icon(Icons.chevron_right, color: MX.fgFaint),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
