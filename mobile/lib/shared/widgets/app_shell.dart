import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'package:voicenote_ai/core/router/app_routes.dart';
import 'package:voicenote_ai/core/theme/mx_tokens.dart';

/// Methodex-style bottom navigation: 4 tabs (Сегодня / Заметки / Задачи / Привычки)
/// с центральной FAB-кнопкой для голосового ввода. Профиль — в правом углу AppBar
/// (раскрывается через Drawer — см. будущие итерации).
///
/// Нарисован поверх системных safe-area вручную, чтобы совпадал с дизайн-моками.
class AppShell extends StatelessWidget {
  const AppShell({required this.child, required this.location, super.key});

  final Widget child;
  final String location;

  static const _tabs = <_ShellTab>[
    _ShellTab(AppRoutes.today, Icons.dashboard_outlined, Icons.dashboard, 'Сегодня'),
    _ShellTab(AppRoutes.notes, Icons.edit_note_outlined, Icons.edit_note, 'Заметки'),
    _ShellTab(AppRoutes.tasks, Icons.checklist_outlined, Icons.checklist, 'Задачи'),
    _ShellTab(AppRoutes.habits, Icons.repeat_outlined, Icons.repeat, 'Привычки'),
    _ShellTab(AppRoutes.agent, Icons.auto_awesome_outlined, Icons.auto_awesome, 'AI'),
  ];

  int get _currentIndex {
    for (var i = 0; i < _tabs.length; i++) {
      if (location.startsWith(_tabs[i].route)) return i;
    }
    return 0;
  }

  @override
  Widget build(BuildContext context) {
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

class _ShellTab {
  const _ShellTab(this.route, this.icon, this.activeIcon, this.label);
  final String route;
  final IconData icon;
  final IconData activeIcon;
  final String label;
}

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
    // Компоновка: 2 таба | FAB | 2 таба (оставшиеся 5 — центральный FAB
    // занимает "слот", которого нет среди tabs — запускает экран голосового ввода).
    final left = tabs.take(2).toList();
    final right = tabs.skip(2).toList();

    return Container(
      decoration: BoxDecoration(
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
              // Сами иконки
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
                  const SizedBox(width: 72), // слот под FAB
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
              // Сам FAB
              Positioned(
                top: -18,
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
                fontSize: 11, fontWeight: FontWeight.w600, color: color, letterSpacing: 0.2,
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
        width: 64, height: 64,
        decoration: const BoxDecoration(
          shape: BoxShape.circle,
          gradient: MX.brandGradient,
          boxShadow: MX.fabGlow,
        ),
        child: const Icon(Icons.mic, color: Colors.white, size: 28),
      ),
    );
  }
}
