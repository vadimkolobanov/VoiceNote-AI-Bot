import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:voicenote_ai/core/router/app_routes.dart';
import 'package:voicenote_ai/core/theme/mx_tokens.dart';
import 'package:voicenote_ai/features/auth/application/session_controller.dart';

/// Methodex-style bottom navigation: **4 таба** (Сегодня / Заметки / Задачи /
/// Привычки) с центральной FAB-кнопкой для голосового ввода.
///
/// AI-Агент, Покупки, Дни рождения, Настройки и Профиль — через Drawer.
class AppShell extends ConsumerWidget {
  const AppShell({required this.child, required this.location, super.key});

  final Widget child;
  final String location;

  static const _tabs = <_ShellTab>[
    _ShellTab(AppRoutes.today, Icons.dashboard_outlined, Icons.dashboard, 'Сегодня'),
    _ShellTab(AppRoutes.notes, Icons.edit_note_outlined, Icons.edit_note, 'Заметки'),
    _ShellTab(AppRoutes.tasks, Icons.checklist_outlined, Icons.checklist, 'Задачи'),
    _ShellTab(AppRoutes.habits, Icons.repeat_outlined, Icons.repeat, 'Привычки'),
  ];

  int get _currentIndex {
    for (var i = 0; i < _tabs.length; i++) {
      if (location.startsWith(_tabs[i].route)) return i;
    }
    return 0;
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      extendBody: true,
      body: child,
      bottomNavigationBar: _MethodexNavBar(
        currentIndex: _currentIndex,
        tabs: _tabs,
        onTabSelected: (i) => context.go(_tabs[i].route),
        onFabTap: () => context.push(AppRoutes.voiceCapture),
      ),
    );
  }
}

/// Публичный Drawer. Каждый tab-экран должен прикрутить его к своему
/// собственному `Scaffold.drawer`. Если держать drawer только на внешнем
/// AppShell-Scaffold, то `Scaffold.of(context).openDrawer()` из внутреннего
/// AppBar попадёт во внутренний Scaffold — у которого drawer нет — и
/// ничего не откроется. Поэтому Drawer живёт на каждом tab-экране.
class MethodexDrawer extends ConsumerWidget {
  const MethodexDrawer({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(sessionControllerProvider);
    return _MethodexDrawer(
      userName: session.user?.firstName,
      isVip: session.user?.isVip ?? false,
      onTap: (route) {
        Navigator.of(context).pop();
        context.push(route);
      },
      onLogout: () async {
        Navigator.of(context).pop();
        await ref.read(sessionControllerProvider.notifier).logout();
      },
    );
  }
}

class _ShellTab {
  const _ShellTab(this.route, this.icon, this.activeIcon, this.label);
  final String route;
  final IconData icon;
  final IconData activeIcon;
  final String label;
}

// ═══════════════════════════════════════════════════════════════════════════
// Bottom nav: 2 tabs | FAB | 2 tabs (симметрично)
// ═══════════════════════════════════════════════════════════════════════════

class _MethodexNavBar extends StatelessWidget {
  const _MethodexNavBar({
    required this.currentIndex,
    required this.tabs,
    required this.onTabSelected,
    required this.onFabTap,
  });

  final int currentIndex;
  final List<_ShellTab> tabs;
  final ValueChanged<int> onTabSelected;
  final VoidCallback onFabTap;

  @override
  Widget build(BuildContext context) {
    // 4 таба → 2 слева, 2 справа, FAB ровно по центру.
    final left = tabs.take(2).toList();
    final right = tabs.skip(2).toList();

    return Container(
      decoration: const BoxDecoration(
        color: MX.bgSection,
        border: Border(top: BorderSide(color: MX.line)),
      ),
      child: SafeArea(
        top: false,
        child: SizedBox(
          height: 72,
          child: Stack(
            clipBehavior: Clip.none,
            alignment: Alignment.center,
            children: [
              Row(
                children: [
                  for (final tab in left)
                    Expanded(
                      child: _NavButton(
                        tab: tab,
                        isActive: tabs.indexOf(tab) == currentIndex,
                        onTap: () => onTabSelected(tabs.indexOf(tab)),
                      ),
                    ),
                  // Зазор под FAB — ширина равна диаметру FAB + небольшой запас,
                  // чтобы лейблы не заезжали под тень кнопки.
                  const SizedBox(width: 80),
                  for (final tab in right)
                    Expanded(
                      child: _NavButton(
                        tab: tab,
                        isActive: tabs.indexOf(tab) == currentIndex,
                        onTap: () => onTabSelected(tabs.indexOf(tab)),
                      ),
                    ),
                ],
              ),
              Positioned(
                top: -22,
                child: _VoiceFab(onTap: onFabTap),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _NavButton extends StatelessWidget {
  const _NavButton({
    required this.tab,
    required this.isActive,
    required this.onTap,
  });
  final _ShellTab tab;
  final bool isActive;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = isActive ? MX.fg : MX.fgFaint;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(MX.rMd),
      child: SizedBox(
        height: 72,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(isActive ? tab.activeIcon : tab.icon, size: 22, color: color),
            const SizedBox(height: 4),
            Text(
              tab.label,
              style: TextStyle(
                fontSize: 11, fontWeight: FontWeight.w600,
                color: color, letterSpacing: 0.2,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _VoiceFab extends StatelessWidget {
  const _VoiceFab({required this.onTap});
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 60, height: 60,
        decoration: const BoxDecoration(
          shape: BoxShape.circle,
          gradient: MX.brandGradient,
          boxShadow: MX.fabGlow,
          border: Border.fromBorderSide(
            BorderSide(color: MX.bgSection, width: 4),
          ),
        ),
        child: const Icon(Icons.mic, color: Colors.white, size: 26),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// Drawer: Покупки / Дни рождения / AI / Настройки / Выход
// ═══════════════════════════════════════════════════════════════════════════

/// Методекс Drawer — точно по макету.
///
/// Секции:
/// • Header: аватар + имя + счётчик заметок + chevron (открывает профиль).
/// • «Основное»: Сегодня, Заметки, Напоминания, Привычки — со счётчиками.
/// • «Списки»: Покупки, Дни рождения — со счётчиками.
/// • «Скоро»: Финансы, Таймер фокуса, Здоровье — disabled с badge «скоро».
/// • VIP banner: «Подключите ассистента».
/// • Footer: Настройки, Поддержка.
class _MethodexDrawer extends StatelessWidget {
  const _MethodexDrawer({
    required this.onTap,
    required this.onLogout,
    this.userName,
    this.isVip = false,
  });

  final ValueChanged<String> onTap;
  final VoidCallback onLogout;
  final String? userName;
  final bool isVip;

  @override
  Widget build(BuildContext context) {
    return Drawer(
      backgroundColor: MX.bgBase,
      width: 300,
      shape: const RoundedRectangleBorder(),
      child: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _DrawerProfile(
              userName: userName,
              isVip: isVip,
              onTap: () => onTap(AppRoutes.profile),
            ),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.symmetric(vertical: 12),
                children: [
                  _Section(
                    label: 'Основное',
                    items: [
                      _Item(
                        icon: Icons.dashboard_outlined,
                        label: 'Сегодня',
                        onTap: () => onTap(AppRoutes.today),
                      ),
                      _Item(
                        icon: Icons.edit_note_outlined,
                        label: 'Заметки',
                        onTap: () => onTap(AppRoutes.notes),
                      ),
                      _Item(
                        icon: Icons.notifications_none,
                        label: 'Напоминания',
                        onTap: () => onTap(AppRoutes.allReminders),
                      ),
                      _Item(
                        icon: Icons.repeat,
                        label: 'Привычки',
                        onTap: () => onTap(AppRoutes.habits),
                      ),
                    ],
                  ),
                  _Section(
                    label: 'Списки',
                    items: [
                      _Item(
                        icon: Icons.shopping_cart_outlined,
                        label: 'Покупки',
                        onTap: () => onTap(AppRoutes.shopping),
                      ),
                      _Item(
                        icon: Icons.cake_outlined,
                        label: 'Дни рождения',
                        onTap: () => onTap(AppRoutes.birthdays),
                      ),
                    ],
                  ),
                  _Section(
                    label: 'Скоро',
                    items: [
                      _Item(
                        icon: Icons.account_balance_wallet_outlined,
                        label: 'Финансы',
                        disabled: true,
                      ),
                      _Item(
                        icon: Icons.timer_outlined,
                        label: 'Таймер фокуса',
                        disabled: true,
                      ),
                      _Item(
                        icon: Icons.favorite_outline,
                        label: 'Здоровье',
                        disabled: true,
                      ),
                    ],
                  ),
                  _VipBanner(
                    isVip: isVip,
                    onTap: () => onTap(AppRoutes.paywall),
                  ),
                ],
              ),
            ),
            _DrawerFooter(
              onSettings: () => onTap(AppRoutes.settings),
              onLogout: onLogout,
            ),
          ],
        ),
      ),
    );
  }
}

class _DrawerProfile extends StatelessWidget {
  const _DrawerProfile({this.userName, this.isVip = false, required this.onTap});
  final String? userName;
  final bool isVip;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.fromLTRB(20, 14, 16, 18),
          decoration: const BoxDecoration(
            border: Border(bottom: BorderSide(color: MX.line)),
          ),
          child: Row(
            children: [
              Container(
                width: 44, height: 44,
                decoration: const BoxDecoration(
                  gradient: MX.brandGradient,
                  borderRadius: BorderRadius.all(Radius.circular(12)),
                ),
                child: Center(
                  child: Text(
                    (userName?.characters.firstOrNull ?? 'М').toUpperCase(),
                    style: const TextStyle(
                      color: Colors.white, fontWeight: FontWeight.w700, fontSize: 18,
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      userName ?? 'Гость',
                      style: const TextStyle(
                        color: MX.fg, fontWeight: FontWeight.w600, fontSize: 15,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      isVip ? 'Premium' : 'Free',
                      style: TextStyle(
                        color: isVip ? MX.accentAi : MX.fgMicro,
                        fontSize: 12, fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right, size: 16, color: MX.fgFaint),
            ],
          ),
        ),
      ),
    );
  }
}

class _Section extends StatelessWidget {
  const _Section({required this.label, required this.items});
  final String label;
  final List<_Item> items;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(0, 14, 0, 2),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 8),
            child: Text(
              label.toUpperCase(),
              style: const TextStyle(
                color: MX.fgMicro, fontSize: 11,
                fontWeight: FontWeight.w700, letterSpacing: 1.2,
              ),
            ),
          ),
          ...items,
        ],
      ),
    );
  }
}

class _Item extends StatelessWidget {
  const _Item({
    required this.icon,
    required this.label,
    this.onTap,
    this.disabled = false,
  });
  final IconData icon;
  final String label;
  final VoidCallback? onTap;
  final bool disabled;

  @override
  Widget build(BuildContext context) {
    return Opacity(
      opacity: disabled ? 0.45 : 1,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: disabled ? null : onTap,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
            child: Row(
              children: [
                Icon(icon, size: 20, color: MX.fgMuted),
                const SizedBox(width: 14),
                Expanded(
                  child: Text(label,
                      style: const TextStyle(
                          color: MX.fg, fontSize: 14, fontWeight: FontWeight.w500)),
                ),
                if (disabled)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: MX.surfaceOverlay,
                      borderRadius: BorderRadius.circular(MX.rFull),
                      border: Border.all(color: MX.line),
                    ),
                    child: const Text('скоро',
                        style: TextStyle(
                            color: MX.fgMicro, fontSize: 10, fontWeight: FontWeight.w600,
                            letterSpacing: 0.6)),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _VipBanner extends StatelessWidget {
  const _VipBanner({required this.isVip, required this.onTap});
  final bool isVip;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 18, 16, 10),
      child: Material(
        color: MX.accentAiSoft,
        borderRadius: BorderRadius.circular(MX.rLg),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(MX.rLg),
          child: Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
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
                    Text('VIP',
                        style: TextStyle(
                          color: MX.accentAi,
                          fontSize: 11,
                          fontWeight: FontWeight.w800,
                          letterSpacing: 1.2,
                        )),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  isVip ? 'Спасибо за поддержку!' : 'Подключите ассистента',
                  style: const TextStyle(
                    color: MX.fg, fontSize: 15, fontWeight: FontWeight.w700,
                    height: 1.25,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  isVip
                      ? 'Память и решения за вас — включены.'
                      : 'Помнит всё о вас и решает за вас.',
                  style: const TextStyle(color: MX.fgMuted, fontSize: 12, height: 1.4),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _DrawerFooter extends StatelessWidget {
  const _DrawerFooter({required this.onSettings, required this.onLogout});
  final VoidCallback onSettings;
  final VoidCallback onLogout;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        border: Border(top: BorderSide(color: MX.line)),
      ),
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Column(
        children: [
          _FooterItem(icon: Icons.settings_outlined, label: 'Настройки', onTap: onSettings),
          _FooterItem(
            icon: Icons.logout, label: 'Выйти', onTap: onLogout,
            color: MX.accentSecurity,
          ),
        ],
      ),
    );
  }
}

class _FooterItem extends StatelessWidget {
  const _FooterItem({
    required this.icon,
    required this.label,
    required this.onTap,
    this.color,
  });
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
          child: Row(
            children: [
              Icon(icon, size: 20, color: color ?? MX.fgMuted),
              const SizedBox(width: 14),
              Text(label,
                  style: TextStyle(
                      color: color ?? MX.fg, fontSize: 14, fontWeight: FontWeight.w500)),
            ],
          ),
        ),
      ),
    );
  }
}
