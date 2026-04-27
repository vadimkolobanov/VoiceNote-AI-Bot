import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons/lucide_icons.dart';

import 'package:voicenote_ai/core/router/app_routes.dart';
import 'package:voicenote_ai/core/theme/mx_tokens.dart';

/// AppShell — корневой каркас 4-табного UI (PRODUCT_PLAN.md §2.1):
/// Сегодня · Хроника · Ритм · Профиль + плавающая кнопка микрофона по центру.
class AppShell extends StatelessWidget {
  const AppShell({
    super.key,
    required this.location,
    required this.child,
  });

  final String location;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: MX.bgBase,
      extendBody: true,
      body: child,
      floatingActionButton: _MicFab(
        onTap: () {
          HapticFeedback.mediumImpact();
          context.push(AppRoutes.voiceCapture);
        },
      ),
      floatingActionButtonLocation: FloatingActionButtonLocation.centerDocked,
      bottomNavigationBar: _BottomBar(currentLocation: location),
    );
  }
}

class _MicFab extends StatelessWidget {
  const _MicFab({required this.onTap});
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: SizedBox(
        height: 64,
        width: 64,
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            onTap: onTap,
            borderRadius: BorderRadius.circular(MX.rFull),
            child: Container(
              decoration: BoxDecoration(
                gradient: MX.brandGradient,
                shape: BoxShape.circle,
                boxShadow: MX.fabGlow,
              ),
              child: const Icon(LucideIcons.mic, color: Colors.white, size: 28),
            ),
          ),
        ),
      ),
    );
  }
}

class _BottomBar extends StatelessWidget {
  const _BottomBar({required this.currentLocation});
  final String currentLocation;

  static const _tabs = <_TabSpec>[
    _TabSpec(path: AppRoutes.today, icon: LucideIcons.calendar, activeIcon: LucideIcons.calendar, label: 'Сегодня'),
    _TabSpec(path: AppRoutes.timeline, icon: LucideIcons.layers, activeIcon: LucideIcons.layers, label: 'Хроника'),
    _TabSpec(path: AppRoutes.rhythm, icon: LucideIcons.repeat, activeIcon: LucideIcons.repeat, label: 'Ритм'),
    _TabSpec(path: AppRoutes.profile, icon: LucideIcons.user, activeIcon: LucideIcons.user, label: 'Профиль'),
  ];

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        // Полупрозрачная подложка, чтобы FAB-glow читался поверх таб-бара.
        color: Color(0xEB09090B),
        border: Border(top: BorderSide(color: MX.line)),
      ),
      child: SafeArea(
        top: false,
        child: SizedBox(
          height: 64,
          child: Row(
            children: [
              _tabBtn(context, _tabs[0]),
              _tabBtn(context, _tabs[1]),
              const SizedBox(width: 64), // место под FAB
              _tabBtn(context, _tabs[2]),
              _tabBtn(context, _tabs[3]),
            ],
          ),
        ),
      ),
    );
  }

  Widget _tabBtn(BuildContext context, _TabSpec spec) {
    final active = currentLocation.startsWith(spec.path);
    return Expanded(
      child: InkWell(
        onTap: () {
          if (!active) context.go(spec.path);
        },
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(active ? spec.activeIcon : spec.icon,
                color: active ? MX.fg : MX.fgFaint, size: 24),
            const SizedBox(height: 2),
            Text(
              spec.label,
              style: TextStyle(
                color: active ? MX.fg : MX.fgFaint,
                fontSize: 11,
                fontWeight: active ? FontWeight.w600 : FontWeight.w500,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _TabSpec {
  const _TabSpec({
    required this.path,
    required this.icon,
    required this.activeIcon,
    required this.label,
  });
  final String path;
  final IconData icon;
  final IconData activeIcon;
  final String label;
}
