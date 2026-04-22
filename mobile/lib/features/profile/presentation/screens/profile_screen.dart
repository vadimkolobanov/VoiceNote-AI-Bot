import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:voicenote_ai/core/router/app_routes.dart';
import 'package:voicenote_ai/core/theme/mx_tokens.dart';
import 'package:voicenote_ai/core/widgets/mx_widgets.dart';
import 'package:voicenote_ai/features/auth/application/session_controller.dart';
import 'package:voicenote_ai/features/payments/data/repositories/payments_repository.dart';

/// Профиль — верстан по макету ScreenProfile: hero + stats + VIP CTA
/// + секции Профиль / Ассистент / Уведомления / Данные.
class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(sessionControllerProvider);
    final user = session.user;
    final subAsync = ref.watch(subscriptionProvider);

    if (user == null) {
      return const Scaffold(
        backgroundColor: MX.bgBase,
        body: Center(child: CircularProgressIndicator(color: MX.accentAi)),
      );
    }

    return Scaffold(
      backgroundColor: MX.bgBase,
      appBar: MxAppBar(
        title: 'Профиль',
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, size: 22),
          onPressed: () => Navigator.of(context).pop(),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings_outlined, size: 22),
            onPressed: () => context.push(AppRoutes.settings),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 40),
        children: [
          // ── Hero ────────────────────────────────
          MxCard(
            padding: const EdgeInsets.all(20),
            child: Row(
              children: [
                Container(
                  width: 60, height: 60,
                  decoration: const BoxDecoration(
                    shape: BoxShape.circle, gradient: MX.brandGradient,
                  ),
                  child: Center(
                    child: Text(
                      _initials(user.firstName),
                      style: const TextStyle(
                        color: Colors.white, fontSize: 22, fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(user.firstName,
                          style: const TextStyle(
                            color: MX.fg, fontSize: 18, fontWeight: FontWeight.w700,
                          )),
                      const SizedBox(height: 2),
                      Text('Уровень ${user.level} · ${user.xp} XP',
                          style: const TextStyle(color: MX.fgMicro, fontSize: 12)),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),

          // ── Stats grid ──────────────────────────
          Row(
            children: [
              _Stat(value: '${user.xp}', label: 'опыта'),
              const SizedBox(width: 8),
              _Stat(value: '${user.level}', label: 'уровень'),
              const SizedBox(width: 8),
              _Stat(value: user.isVip ? 'Premium' : 'Free', label: 'план',
                  accent: user.isVip),
            ],
          ),

          const SizedBox(height: 22),

          // ── VIP CTA (если не премиум) ──────────
          if (!user.isVip)
            _VipCta(onTap: () => context.push(AppRoutes.paywall))
          else
            _ManageVip(
              subscription: subAsync.valueOrNull,
              onTap: () => context.push(AppRoutes.paywall),
            ),

          const SizedBox(height: 22),

          // ── Разделы ─────────────────────────────
          const MxSectionTitle(label: 'Профиль', topPad: 0),
          MxCard(
            padding: EdgeInsets.zero,
            child: Column(
              children: [
                _ProfileTile(
                  icon: Icons.person_outline, title: 'Личные данные',
                  value: user.firstName,
                  onTap: () => context.push(AppRoutes.settings),
                ),
                const Divider(height: 1, color: MX.lineFaint),
                _ProfileTile(
                  icon: Icons.schedule, title: 'Часовой пояс', value: user.timezone,
                  onTap: () => context.push(AppRoutes.settings),
                ),
                if (user.cityName != null) ...[
                  const Divider(height: 1, color: MX.lineFaint),
                  _ProfileTile(
                    icon: Icons.location_city_outlined, title: 'Город',
                    value: user.cityName!,
                    onTap: () => context.push(AppRoutes.settings),
                  ),
                ],
              ],
            ),
          ),

          const MxSectionTitle(label: 'Ассистент'),
          MxCard(
            padding: EdgeInsets.zero,
            child: Column(
              children: [
                _ProfileTile(
                  icon: Icons.auto_awesome, title: 'Подписка',
                  value: user.isVip ? 'Premium' : 'Free · доступен VIP',
                  valueColor: user.isVip ? MX.accentAi : MX.fgMuted,
                  onTap: () => context.push(AppRoutes.paywall),
                ),
                const Divider(height: 1, color: MX.lineFaint),
                _ProfileTile(
                  icon: Icons.psychology_alt_outlined, title: 'Память о вас',
                  value: user.isVip ? 'Активна' : 'Только VIP',
                  onTap: () => context.push(AppRoutes.memoryFacts),
                ),
                const Divider(height: 1, color: MX.lineFaint),
                _ProfileTile(
                  icon: Icons.wb_sunny_outlined, title: 'Утренняя сводка',
                  value: user.isVip ? '09:00' : 'Только VIP',
                  onTap: () => context.push(AppRoutes.settings),
                ),
              ],
            ),
          ),

          const MxSectionTitle(label: 'Разделы'),
          MxCard(
            padding: EdgeInsets.zero,
            child: Column(
              children: [
                _ProfileTile(
                  icon: Icons.shopping_cart_outlined, title: 'Покупки',
                  onTap: () => context.push(AppRoutes.shopping),
                ),
                const Divider(height: 1, color: MX.lineFaint),
                _ProfileTile(
                  icon: Icons.cake_outlined, title: 'Дни рождения',
                  onTap: () => context.push(AppRoutes.birthdays),
                ),
                const Divider(height: 1, color: MX.lineFaint),
                _ProfileTile(
                  icon: Icons.emoji_events_outlined, title: 'Достижения',
                  onTap: () => context.push(AppRoutes.achievements),
                ),
              ],
            ),
          ),

          const SizedBox(height: 24),
          TextButton.icon(
            icon: const Icon(Icons.logout, color: MX.accentSecurity, size: 18),
            label: const Text('Выйти', style: TextStyle(color: MX.accentSecurity)),
            onPressed: () => ref.read(sessionControllerProvider.notifier).logout(),
          ),
        ],
      ),
    );
  }

  static String _initials(String name) {
    final parts = name.trim().split(' ');
    if (parts.isEmpty) return '?';
    if (parts.length == 1) return parts.first.characters.firstOrNull?.toUpperCase() ?? '?';
    return (parts[0].characters.firstOrNull ?? '').toUpperCase() +
        (parts[1].characters.firstOrNull ?? '').toUpperCase();
  }
}

class _Stat extends StatelessWidget {
  const _Stat({required this.value, required this.label, this.accent = false});
  final String value;
  final String label;
  final bool accent;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
        decoration: BoxDecoration(
          color: MX.surfaceOverlay,
          borderRadius: BorderRadius.circular(MX.rLg),
          border: Border.all(color: MX.line),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              value,
              maxLines: 1, overflow: TextOverflow.ellipsis,
              style: TextStyle(
                color: accent ? MX.accentAi : MX.fg,
                fontSize: 18, fontWeight: FontWeight.w700, height: 1.0,
              ),
            ),
            const SizedBox(height: 4),
            Text(label,
                style: const TextStyle(color: MX.fgMicro, fontSize: 11)),
          ],
        ),
      ),
    );
  }
}

class _VipCta extends StatelessWidget {
  const _VipCta({required this.onTap});
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: MX.accentAiSoft,
        borderRadius: BorderRadius.circular(MX.rLg),
        border: Border.all(color: MX.accentAiLine),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.auto_awesome, color: MX.accentAi, size: 14),
              const SizedBox(width: 6),
              Text('АССИСТЕНТ · VIP',
                  style: const TextStyle(
                    color: MX.accentAi, fontSize: 11,
                    fontWeight: FontWeight.w800, letterSpacing: 1.2,
                  )),
            ],
          ),
          const SizedBox(height: 10),
          const Text(
            '390 ₽/мес и он начнёт думать за вас.',
            style: TextStyle(
              color: MX.fg, fontSize: 16, fontWeight: FontWeight.w600, height: 1.3,
            ),
          ),
          const SizedBox(height: 14),
          MxPrimaryButton(
            label: 'Открыть VIP →',
            height: 40,
            onTap: onTap,
          ),
        ],
      ),
    );
  }
}

class _ManageVip extends StatelessWidget {
  const _ManageVip({this.subscription, required this.onTap});
  final dynamic subscription;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return MxCard(
      padding: const EdgeInsets.all(18),
      onTap: onTap,
      border: MX.accentAiLine,
      child: Row(
        children: [
          const Icon(Icons.workspace_premium, color: MX.accentAi, size: 22),
          const SizedBox(width: 12),
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Premium активен',
                    style: TextStyle(
                      color: MX.fg, fontSize: 14, fontWeight: FontWeight.w700,
                    )),
                SizedBox(height: 2),
                Text('Управление подпиской',
                    style: TextStyle(color: MX.fgMuted, fontSize: 12)),
              ],
            ),
          ),
          const Icon(Icons.chevron_right, size: 18, color: MX.fgFaint),
        ],
      ),
    );
  }
}

class _ProfileTile extends StatelessWidget {
  const _ProfileTile({
    required this.icon,
    required this.title,
    this.value,
    this.valueColor,
    this.onTap,
  });
  final IconData icon;
  final String title;
  final String? value;
  final Color? valueColor;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
          child: Row(
            children: [
              Container(
                width: 32, height: 32,
                decoration: BoxDecoration(
                  color: MX.surfaceOverlay,
                  borderRadius: BorderRadius.circular(MX.rSm),
                  border: Border.all(color: MX.line),
                ),
                child: Icon(icon, size: 15, color: MX.fgMuted),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(title,
                    style: const TextStyle(
                        color: MX.fg, fontSize: 14, fontWeight: FontWeight.w500)),
              ),
              if (value != null) ...[
                Text(
                  value!,
                  style: TextStyle(color: valueColor ?? MX.fgMuted, fontSize: 12),
                ),
                const SizedBox(width: 6),
              ],
              const Icon(Icons.chevron_right, color: MX.fgFaint, size: 16),
            ],
          ),
        ),
      ),
    );
  }
}
