/// Библиотека UI-примитивов Методекс Design System.
///
/// Используй эти виджеты во всех экранах вместо собственных одноразовых
/// карточек — у них единое поведение, цвета, радиусы, паддинги.
library;

import 'package:flutter/material.dart';

import 'package:voicenote_ai/core/theme/mx_tokens.dart';

// ═══════════════════════════════════════════════════════════════════════════
// MxAppBar — единый верхний бар с меню слева, title+subtitle и actions.
// ═══════════════════════════════════════════════════════════════════════════

class MxAppBar extends StatelessWidget implements PreferredSizeWidget {
  const MxAppBar({
    required this.title,
    this.subtitle,
    this.onMenuPressed,
    this.actions = const [],
    this.leading,
    this.showLogo = false,
    super.key,
  });

  final String title;
  final String? subtitle;
  final VoidCallback? onMenuPressed;
  final List<Widget> actions;
  final Widget? leading;
  final bool showLogo;

  @override
  Size get preferredSize =>
      Size.fromHeight(subtitle == null ? 56 : 72);

  @override
  Widget build(BuildContext context) {
    return AppBar(
      backgroundColor: MX.bgBase,
      elevation: 0,
      scrolledUnderElevation: 0,
      titleSpacing: 4,
      toolbarHeight: subtitle == null ? 56 : 72,
      leading: leading ??
          Builder(
            builder: (ctx) {
              final scaffold = Scaffold.maybeOf(ctx);
              final hasDrawer = scaffold?.hasDrawer ?? false;
              // Если у окружающего Scaffold нет drawer — показываем back-кнопку,
              // чтобы пользователь мог вернуться назад, а не застревал на
              // мёртвом hamburger-е.
              if (!hasDrawer && onMenuPressed == null) {
                return IconButton(
                  icon: const Icon(Icons.arrow_back, size: 22),
                  onPressed: () => Navigator.of(ctx).maybePop(),
                );
              }
              return IconButton(
                icon: const Icon(Icons.menu, size: 22),
                onPressed: onMenuPressed ?? () => scaffold?.openDrawer(),
              );
            },
          ),
      title: showLogo
          ? _LogoTitle(title: title, subtitle: subtitle)
          : _PlainTitle(title: title, subtitle: subtitle),
      actions: [...actions, const SizedBox(width: 4)],
    );
  }
}

class _PlainTitle extends StatelessWidget {
  const _PlainTitle({required this.title, this.subtitle});
  final String title;
  final String? subtitle;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: const TextStyle(
            fontSize: 17, fontWeight: FontWeight.w600, color: MX.fg,
            letterSpacing: -0.2,
          ),
        ),
        if (subtitle != null) ...[
          const SizedBox(height: 2),
          Text(
            subtitle!,
            style: const TextStyle(fontSize: 11, color: MX.fgMicro, fontWeight: FontWeight.w500),
          ),
        ],
      ],
    );
  }
}

class _LogoTitle extends StatelessWidget {
  const _LogoTitle({required this.title, this.subtitle});
  final String title;
  final String? subtitle;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 28, height: 28,
          decoration: BoxDecoration(
            gradient: MX.brandGradient,
            borderRadius: BorderRadius.circular(6),
          ),
          child: const Center(
            child: Text('М',
                style: TextStyle(
                    color: Colors.white, fontWeight: FontWeight.w700, fontSize: 14)),
          ),
        ),
        const SizedBox(width: 10),
        Expanded(child: _PlainTitle(title: title, subtitle: subtitle)),
      ],
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// MxCard — surface overlay + thin line border + radius 14
// ═══════════════════════════════════════════════════════════════════════════

class MxCard extends StatelessWidget {
  const MxCard({
    required this.child,
    this.padding = const EdgeInsets.all(16),
    this.radius = MX.rLg,
    this.border,
    this.background,
    this.onTap,
    super.key,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final double radius;
  final Color? border;
  final Color? background;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final content = AnimatedContainer(
      duration: MX.durMed, curve: MX.easeStandard,
      padding: padding,
      decoration: BoxDecoration(
        color: background ?? MX.surfaceOverlay,
        borderRadius: BorderRadius.circular(radius),
        border: Border.all(color: border ?? MX.line),
      ),
      child: child,
    );
    if (onTap == null) return content;
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(radius),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(radius),
        splashColor: MX.surfaceOverlayHi,
        child: content,
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// MxSectionTitle — uppercase micro label + optional meta / trailing
// ═══════════════════════════════════════════════════════════════════════════

class MxSectionTitle extends StatelessWidget {
  const MxSectionTitle({
    required this.label,
    this.meta,
    this.color,
    this.trailing,
    this.topPad = 18,
    this.bottomPad = 10,
    super.key,
  });

  final String label;
  final String? meta;
  final Color? color;
  final Widget? trailing;
  final double topPad;
  final double bottomPad;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.fromLTRB(0, topPad, 0, bottomPad),
      child: Row(
        children: [
          Text(
            label.toUpperCase(),
            style: TextStyle(
              fontSize: 11, fontWeight: FontWeight.w700, letterSpacing: 1.2,
              color: color ?? MX.fgMicro,
            ),
          ),
          if (meta != null) ...[
            const SizedBox(width: 8),
            Text(
              meta!,
              style: const TextStyle(fontSize: 11, color: MX.fgMicro),
            ),
          ],
          const Spacer(),
          if (trailing != null) trailing!,
        ],
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// MxBadge — маленький chip (neutral/ai/tools/security/warning)
// ═══════════════════════════════════════════════════════════════════════════

enum MxAccent { neutral, ai, tools, security, warning }

class MxBadge extends StatelessWidget {
  const MxBadge({
    required this.label,
    this.icon,
    this.accent = MxAccent.neutral,
    this.uppercase = false,
    super.key,
  });

  final String label;
  final IconData? icon;
  final MxAccent accent;
  final bool uppercase;

  @override
  Widget build(BuildContext context) {
    final (fg, bg, border) = switch (accent) {
      MxAccent.ai => (MX.accentAi, MX.accentAiSoft, MX.accentAiLine),
      MxAccent.tools => (MX.accentTools, MX.accentToolsSoft, MX.accentToolsLine),
      MxAccent.security => (MX.accentSecurity, MX.accentSecuritySoft, MX.accentSecurityLine),
      MxAccent.warning => (MX.statusWarning, const Color(0x1FFBBF24), const Color(0x40FBBF24)),
      MxAccent.neutral => (MX.fgMuted, MX.surfaceOverlay, MX.line),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: bg,
        border: Border.all(color: border),
        borderRadius: BorderRadius.circular(MX.rFull),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 11, color: fg),
            const SizedBox(width: 4),
          ],
          Text(
            uppercase ? label.toUpperCase() : label,
            style: TextStyle(
              color: fg,
              fontSize: 11,
              fontWeight: FontWeight.w600,
              letterSpacing: uppercase ? 0.8 : 0,
            ),
          ),
        ],
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// MxFilterPills — горизонтальный ряд chip-ов с одним активным
// ═══════════════════════════════════════════════════════════════════════════

class MxFilterPill {
  const MxFilterPill({required this.value, required this.label, this.count});
  final String value;
  final String label;
  final int? count;
}

class MxFilterPills extends StatelessWidget {
  const MxFilterPills({
    required this.items,
    required this.selected,
    required this.onSelected,
    super.key,
  });

  final List<MxFilterPill> items;
  final String selected;
  final ValueChanged<String> onSelected;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 34,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 20),
        itemCount: items.length,
        separatorBuilder: (_, __) => const SizedBox(width: 6),
        itemBuilder: (_, i) {
          final p = items[i];
          final active = p.value == selected;
          return GestureDetector(
            onTap: () => onSelected(p.value),
            child: AnimatedContainer(
              duration: MX.durFast, curve: MX.easeStandard,
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: active ? MX.fg : MX.surfaceOverlay,
                borderRadius: BorderRadius.circular(MX.rFull),
                border: Border.all(color: active ? MX.fg : MX.lineStrong),
              ),
              child: Row(
                children: [
                  Text(
                    p.label,
                    style: TextStyle(
                      fontSize: 13, fontWeight: FontWeight.w600,
                      color: active ? MX.bgBase : MX.fgMuted,
                    ),
                  ),
                  if (p.count != null) ...[
                    const SizedBox(width: 5),
                    Text(
                      '${p.count}',
                      style: TextStyle(
                        fontSize: 12, fontWeight: FontWeight.w500,
                        color: active ? MX.bgBase.withValues(alpha: 0.6) : MX.fgFaint,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// MxPrimaryButton — белая pill (на тёмном фоне)
// ═══════════════════════════════════════════════════════════════════════════

class MxPrimaryButton extends StatelessWidget {
  const MxPrimaryButton({
    required this.label,
    this.icon,
    this.onTap,
    this.expanded = false,
    this.accent = false,
    this.height = 44,
    super.key,
  });

  final String label;
  final IconData? icon;
  final VoidCallback? onTap;
  final bool expanded;
  final bool accent;
  final double height;

  @override
  Widget build(BuildContext context) {
    final child = Material(
      color: accent ? MX.accentAi : MX.fg,
      borderRadius: BorderRadius.circular(MX.rFull),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(MX.rFull),
        child: Container(
          height: height,
          padding: const EdgeInsets.symmetric(horizontal: 20),
          alignment: Alignment.center,
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (icon != null) ...[
                Icon(icon, size: 18, color: MX.bgBase),
                const SizedBox(width: 8),
              ],
              Text(
                label,
                style: const TextStyle(
                  color: MX.bgBase, fontSize: 14, fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
      ),
    );
    return expanded ? SizedBox(width: double.infinity, child: child) : child;
  }
}

class MxGhostButton extends StatelessWidget {
  const MxGhostButton({
    required this.label,
    this.icon,
    this.onTap,
    this.height = 44,
    super.key,
  });
  final String label;
  final IconData? icon;
  final VoidCallback? onTap;
  final double height;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(MX.rFull),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(MX.rFull),
        child: Container(
          height: height,
          padding: const EdgeInsets.symmetric(horizontal: 18),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(MX.rFull),
            border: Border.all(color: MX.lineStrong),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (icon != null) ...[
                Icon(icon, size: 18, color: MX.fg),
                const SizedBox(width: 8),
              ],
              Text(label,
                  style: const TextStyle(
                      color: MX.fg, fontSize: 14, fontWeight: FontWeight.w600)),
            ],
          ),
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// MxReminderRow — напоминание с цветной полосой слева + time + title + check
// ═══════════════════════════════════════════════════════════════════════════

class MxReminderRow extends StatelessWidget {
  const MxReminderRow({
    required this.time,
    required this.title,
    this.tag,
    this.accent = MxAccent.ai,
    this.onComplete,
    this.onTap,
    this.overdueBadge = false,
    this.repeat = false,
    super.key,
  });

  final String time;
  final String title;
  final String? tag;
  final MxAccent accent;
  final VoidCallback? onComplete;
  final VoidCallback? onTap;
  final bool overdueBadge;
  final bool repeat;

  Color get _stripeColor => switch (accent) {
        MxAccent.ai => MX.accentAi,
        MxAccent.tools => MX.accentTools,
        MxAccent.security => MX.accentSecurity,
        MxAccent.warning => MX.statusWarning,
        MxAccent.neutral => MX.fgFaint,
      };

  @override
  Widget build(BuildContext context) {
    return MxCard(
      onTap: onTap,
      padding: EdgeInsets.zero,
      child: IntrinsicHeight(
        child: Row(
          children: [
            Container(
              width: 4,
              decoration: BoxDecoration(
                color: _stripeColor,
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(MX.rLg),
                  bottomLeft: Radius.circular(MX.rLg),
                ),
              ),
            ),
            const SizedBox(width: 12),
            SizedBox(
              width: 54,
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 14),
                child: Text(
                  time,
                  style: TextStyle(
                    fontSize: 13, fontWeight: FontWeight.w700,
                    color: _stripeColor, fontFeatures: const [],
                  ),
                ),
              ),
            ),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        if (repeat) ...[
                          const Icon(Icons.repeat, size: 11, color: MX.fgFaint),
                          const SizedBox(width: 4),
                        ],
                        Flexible(
                          child: Text(
                            title,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              fontSize: 14, color: MX.fg, height: 1.35,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ),
                      ],
                    ),
                    if (tag != null || overdueBadge) ...[
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          if (tag != null)
                            Text(tag!,
                                style: const TextStyle(fontSize: 11, color: MX.fgMicro)),
                          if (overdueBadge) ...[
                            const SizedBox(width: 6),
                            const MxBadge(label: 'просрочено', accent: MxAccent.warning),
                          ],
                        ],
                      ),
                    ],
                  ],
                ),
              ),
            ),
            IconButton(
              icon: const Icon(Icons.check, size: 18, color: MX.fgMuted),
              onPressed: onComplete,
            ),
          ],
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// MxEmptyState — single empty-state helper
// ═══════════════════════════════════════════════════════════════════════════

class MxEmptyState extends StatelessWidget {
  const MxEmptyState({
    required this.icon,
    required this.title,
    this.subtitle,
    this.action,
    super.key,
  });

  final IconData icon;
  final String title;
  final String? subtitle;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 52, height: 52,
            decoration: BoxDecoration(
              color: MX.surfaceOverlay,
              borderRadius: BorderRadius.circular(MX.rLg),
              border: Border.all(color: MX.line),
            ),
            child: Icon(icon, color: MX.fgMuted, size: 22),
          ),
          const SizedBox(height: 16),
          Text(title,
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 16, fontWeight: FontWeight.w600, color: MX.fg,
              )),
          if (subtitle != null) ...[
            const SizedBox(height: 6),
            Text(subtitle!,
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 13, color: MX.fgMuted, height: 1.4)),
          ],
          if (action != null) ...[
            const SizedBox(height: 20),
            action!,
          ],
        ],
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// MxStripeIcon — маленький цветной квадрат-иконка (для list/grid tiles)
// ═══════════════════════════════════════════════════════════════════════════

class MxAccentTile extends StatelessWidget {
  const MxAccentTile({
    required this.icon,
    this.accent = MxAccent.neutral,
    this.size = 34,
    super.key,
  });
  final IconData icon;
  final MxAccent accent;
  final double size;

  @override
  Widget build(BuildContext context) {
    final (fg, bg, border) = switch (accent) {
      MxAccent.ai => (MX.accentAi, MX.accentAiSoft, MX.accentAiLine),
      MxAccent.tools => (MX.accentTools, MX.accentToolsSoft, MX.accentToolsLine),
      MxAccent.security => (MX.accentSecurity, MX.accentSecuritySoft, MX.accentSecurityLine),
      MxAccent.warning => (MX.statusWarning, const Color(0x1FFBBF24), const Color(0x40FBBF24)),
      MxAccent.neutral => (MX.fgMuted, MX.surfaceOverlay, MX.line),
    };
    return Container(
      width: size, height: size,
      decoration: BoxDecoration(
        color: bg,
        border: Border.all(color: border),
        borderRadius: BorderRadius.circular(MX.rMd),
      ),
      child: Icon(icon, color: fg, size: size * 0.5),
    );
  }
}
