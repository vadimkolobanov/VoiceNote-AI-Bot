import 'package:flutter/material.dart';

/// Methodex Design System — Dart tokens.
///
/// Mirrors `mobile/assets/brand/methodex-tokens.css` 1:1. Treat this file as
/// generated — do not edit values unless the CSS tokens change first.
abstract final class MX {
  // ── Surfaces ───────────────────────────────────────────────────────────
  static const Color bgBase = Color(0xFF09090B);
  static const Color bgSection = Color(0xFF0C0C0F);
  static const Color bgCard = Color(0xFF141418);
  static const Color bgElevated = Color(0xFF1A1A1F);

  // For cards drawn on top of `bgBase` we use a translucent white overlay so
  // the card feels like a glassy surface rather than a painted block. This
  // matches `rgba(255,255,255,0.03)` used across the mocks.
  static const Color surfaceOverlay = Color(0x08FFFFFF); // 3%
  static const Color surfaceOverlayHi = Color(0x0AFFFFFF); // 4%

  // ── Foreground ─────────────────────────────────────────────────────────
  static const Color fg = Color(0xFFFFFFFF);
  static const Color fgMuted = Color(0x80FFFFFF); // 50%
  static const Color fgMicro = Color(0x66FFFFFF); // 40%
  static const Color fgFaint = Color(0x4DFFFFFF); // 30%
  static const Color fgGhost = Color(0x26FFFFFF); // 15%

  // ── Lines ──────────────────────────────────────────────────────────────
  static const Color lineFaint = Color(0x0AFFFFFF); // 4%
  static const Color line = Color(0x0FFFFFFF); // 6%
  static const Color lineStrong = Color(0x1FFFFFFF); // 12%
  static const Color lineBright = Color(0x40FFFFFF); // 25%

  // ── Accent: AI (cyan) ──────────────────────────────────────────────────
  static const Color accentAi = Color(0xFF00E5FF);
  static const Color accentAiSoft = Color(0x1F00E5FF); // 12%
  static const Color accentAiLine = Color(0x4000E5FF); // 25%

  // ── Accent: Security (red) ─────────────────────────────────────────────
  static const Color accentSecurity = Color(0xFFFF6B6B);
  static const Color accentSecuritySoft = Color(0x1FFF6B6B);
  static const Color accentSecurityLine = Color(0x40FF6B6B);

  // ── Accent: Tools (emerald) ────────────────────────────────────────────
  static const Color accentTools = Color(0xFF34D399);
  static const Color accentToolsSoft = Color(0x1F34D399);
  static const Color accentToolsLine = Color(0x4034D399);

  // ── Accent: Purple ─────────────────────────────────────────────────────
  static const Color accentPurple = Color(0xFF7C3AED);
  static const Color accentPurpleSoft = Color(0x247C3AED); // ~14%

  // ── Status ─────────────────────────────────────────────────────────────
  static const Color statusSuccess = accentTools;
  static const Color statusWarning = Color(0xFFFBBF24);
  static const Color statusDanger = accentSecurity;
  static const Color statusInfo = accentAi;

  // ── Brand gradient (used for logo, avatars, hero cards) ────────────────
  static const LinearGradient brandGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [accentAi, accentPurple],
  );

  // ── Radii (dp) ─────────────────────────────────────────────────────────
  static const double rXs = 6;
  static const double rSm = 8;
  static const double rMd = 12;
  static const double rLg = 16;
  static const double rXl = 24;
  static const double rFull = 9999;

  // ── Spacing (dp) ───────────────────────────────────────────────────────
  static const double s1 = 4;
  static const double s2 = 8;
  static const double s3 = 12;
  static const double s4 = 16;
  static const double s5 = 20;
  static const double s6 = 24;
  static const double s8 = 32;
  static const double s10 = 40;
  static const double s12 = 48;
  static const double s16 = 64;
  static const double s20 = 80;

  // ── Motion ─────────────────────────────────────────────────────────────
  static const Duration durFast = Duration(milliseconds: 150);
  static const Duration durMed = Duration(milliseconds: 250);
  static const Duration durSlow = Duration(milliseconds: 700);

  static const Curve easeOutExpo = Cubic(0.16, 1, 0.3, 1);
  static const Curve easeStandard = Cubic(0.4, 0, 0.2, 1);

  // ── Elevation shadows ──────────────────────────────────────────────────
  static const List<BoxShadow> fabGlow = [
    BoxShadow(
      color: Color(0x4000E5FF),
      blurRadius: 24,
      offset: Offset(0, 8),
      spreadRadius: 0,
    ),
  ];

  static const List<BoxShadow> cardShadow = [
    BoxShadow(
      color: Color(0x33000000),
      blurRadius: 24,
      offset: Offset(0, 8),
    ),
  ];
}
