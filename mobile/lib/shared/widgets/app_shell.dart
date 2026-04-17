import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'package:voicenote_ai/core/router/app_routes.dart';

/// Bottom-navigation shell for the 4 main tabs.
class AppShell extends StatelessWidget {
  const AppShell({required this.child, required this.location, super.key});

  final Widget child;
  final String location;

  static const _tabs = <_ShellTab>[
    _ShellTab(AppRoutes.notes, Icons.note_alt_outlined, Icons.note_alt, 'Заметки'),
    _ShellTab(AppRoutes.habits, Icons.repeat_outlined, Icons.repeat, 'Привычки'),
    _ShellTab(AppRoutes.agent, Icons.auto_awesome_outlined, Icons.auto_awesome, 'AI Агент'),
    _ShellTab(AppRoutes.profile, Icons.person_outline, Icons.person, 'Профиль'),
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
      body: child,
      bottomNavigationBar: NavigationBar(
        selectedIndex: _currentIndex,
        onDestinationSelected: (idx) => context.go(_tabs[idx].route),
        destinations: [
          for (final t in _tabs)
            NavigationDestination(
              icon: Icon(t.icon),
              selectedIcon: Icon(t.activeIcon),
              label: t.label,
            ),
        ],
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
