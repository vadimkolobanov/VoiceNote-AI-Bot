import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';

import 'package:voicenote_ai/core/theme/mx_tokens.dart';

/// Методекс Секретарь — Material 3 theme built on top of MX design tokens.
///
/// Design is **dark-first** (OLED-safe `#09090B`). Light theme is retained
/// as a pragmatic fallback for user preference, but is not pixel-matched to
/// the hand-off; colors are inverted mechanically.
abstract final class AppTheme {
  /// Category tag colors used by legacy note-category chips. Kept to avoid
  /// breaking existing widgets that read them — prefer MX semantic tokens
  /// for new code.
  static const Map<String, Color> categoryColors = {
    'заметка': MX.accentAi,
    'напоминание': MX.accentPurple,
    'задача': MX.accentTools,
    'покупки': MX.accentTools,
    'идея': MX.statusWarning,
    'здоровье': MX.accentSecurity,
  };

  static ThemeData dark() => _build(brightness: Brightness.dark);

  /// Light theme кусочно — нужно для пользователей, которые ставят светлую
  /// системную тему. Брендирование то же (cyan primary), но поверхности
  /// светлые.
  static ThemeData light() => _build(brightness: Brightness.light);

  static ThemeData _build({required Brightness brightness}) {
    final bool isDark = brightness == Brightness.dark;

    final ColorScheme scheme = ColorScheme(
      brightness: brightness,
      primary: MX.accentAi,
      onPrimary: isDark ? MX.bgBase : Colors.white,
      primaryContainer: MX.accentAiSoft,
      onPrimaryContainer: MX.accentAi,
      secondary: MX.accentTools,
      onSecondary: MX.bgBase,
      secondaryContainer: MX.accentToolsSoft,
      onSecondaryContainer: MX.accentTools,
      tertiary: MX.accentPurple,
      onTertiary: Colors.white,
      error: MX.accentSecurity,
      onError: Colors.white,
      surface: isDark ? MX.bgBase : const Color(0xFFFAFAFA),
      onSurface: isDark ? MX.fg : const Color(0xFF18181B),
      onSurfaceVariant: isDark ? MX.fgMuted : const Color(0xFF52525B),
      surfaceContainerLowest: isDark ? MX.bgBase : Colors.white,
      surfaceContainerLow: isDark ? MX.bgSection : const Color(0xFFF4F4F5),
      surfaceContainer: isDark ? MX.bgCard : const Color(0xFFF1F1F1),
      surfaceContainerHigh: isDark ? MX.bgElevated : const Color(0xFFE8E8E8),
      surfaceContainerHighest: isDark
          ? const Color(0xFF24242A)
          : const Color(0xFFDCDCE0),
      outline: isDark ? MX.lineBright : const Color(0xFFC4C4C9),
      outlineVariant: isDark ? MX.line : const Color(0xFFE4E4E7),
      inverseSurface: isDark ? MX.fg : MX.bgBase,
      onInverseSurface: isDark ? MX.bgBase : MX.fg,
      inversePrimary: MX.accentAi,
      shadow: Colors.black,
      scrim: Colors.black54,
    );

    // Typography — Space Grotesk for display/headlines, Inter for body.
    final baseText = ThemeData(brightness: brightness).textTheme;
    final display = GoogleFonts.spaceGroteskTextTheme(baseText);
    final body = GoogleFonts.interTextTheme(baseText);

    final textTheme = TextTheme(
      // display / headlines — Space Grotesk, tight letter spacing
      displayLarge: display.displayLarge?.copyWith(
        fontSize: 56, fontWeight: FontWeight.w600,
        letterSpacing: -1.2, height: 1.15, color: scheme.onSurface,
      ),
      displayMedium: display.displayMedium?.copyWith(
        fontSize: 40, fontWeight: FontWeight.w600,
        letterSpacing: -0.8, height: 1.2, color: scheme.onSurface,
      ),
      displaySmall: display.displaySmall?.copyWith(
        fontSize: 28, fontWeight: FontWeight.w600,
        letterSpacing: -0.4, height: 1.28, color: scheme.onSurface,
      ),
      headlineLarge: display.headlineLarge?.copyWith(
        fontSize: 24, fontWeight: FontWeight.w600,
        letterSpacing: -0.2, color: scheme.onSurface,
      ),
      headlineMedium: display.headlineMedium?.copyWith(
        fontSize: 20, fontWeight: FontWeight.w600, color: scheme.onSurface,
      ),
      headlineSmall: display.headlineSmall?.copyWith(
        fontSize: 18, fontWeight: FontWeight.w600, color: scheme.onSurface,
      ),
      titleLarge: body.titleLarge?.copyWith(
        fontSize: 18, fontWeight: FontWeight.w600, color: scheme.onSurface,
      ),
      titleMedium: body.titleMedium?.copyWith(
        fontSize: 16, fontWeight: FontWeight.w600, color: scheme.onSurface,
      ),
      titleSmall: body.titleSmall?.copyWith(
        fontSize: 14, fontWeight: FontWeight.w600, color: scheme.onSurface,
      ),
      // body — Inter
      bodyLarge: body.bodyLarge?.copyWith(
        fontSize: 16, fontWeight: FontWeight.w400, height: 1.5,
        color: scheme.onSurface,
      ),
      bodyMedium: body.bodyMedium?.copyWith(
        fontSize: 14, fontWeight: FontWeight.w400, height: 1.45,
        color: scheme.onSurface,
      ),
      bodySmall: body.bodySmall?.copyWith(
        fontSize: 12, fontWeight: FontWeight.w400, height: 1.4,
        color: scheme.onSurfaceVariant,
      ),
      labelLarge: body.labelLarge?.copyWith(
        fontSize: 14, fontWeight: FontWeight.w600, color: scheme.onSurface,
      ),
      labelMedium: body.labelMedium?.copyWith(
        fontSize: 12, fontWeight: FontWeight.w500, color: scheme.onSurface,
      ),
      labelSmall: body.labelSmall?.copyWith(
        fontSize: 11, fontWeight: FontWeight.w600,
        letterSpacing: 0.8, color: scheme.onSurfaceVariant,
      ),
    );

    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      colorScheme: scheme,
      scaffoldBackgroundColor: scheme.surface,
      textTheme: textTheme,
      splashFactory: InkSparkle.splashFactory,
      pageTransitionsTheme: const PageTransitionsTheme(
        builders: {
          TargetPlatform.android: CupertinoPageTransitionsBuilder(),
          TargetPlatform.iOS: CupertinoPageTransitionsBuilder(),
        },
      ),
      appBarTheme: AppBarTheme(
        backgroundColor: scheme.surface,
        foregroundColor: scheme.onSurface,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        systemOverlayStyle: isDark
            ? SystemUiOverlayStyle.light
            : SystemUiOverlayStyle.dark,
        titleTextStyle: textTheme.titleLarge,
      ),
      cardTheme: CardThemeData(
        elevation: 0,
        color: isDark ? MX.surfaceOverlay : Colors.white,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(MX.rLg),
          side: BorderSide(color: scheme.outlineVariant),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: isDark ? MX.surfaceOverlay : const Color(0xFFF4F4F5),
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 13),
        hintStyle: TextStyle(color: scheme.onSurfaceVariant),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(MX.rSm),
          borderSide: BorderSide(color: scheme.outlineVariant),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(MX.rSm),
          borderSide: BorderSide(color: scheme.outlineVariant),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(MX.rSm),
          borderSide: BorderSide(color: scheme.primary, width: 1.5),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(MX.rSm),
          borderSide: BorderSide(color: scheme.error),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size(0, 44),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(MX.rFull)),
          textStyle: textTheme.labelLarge,
          backgroundColor: scheme.onSurface,
          foregroundColor: scheme.surface,
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size(0, 44),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(MX.rFull)),
          side: BorderSide(color: scheme.outline),
          foregroundColor: scheme.onSurface,
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          foregroundColor: scheme.onSurface,
        ),
      ),
      iconButtonTheme: IconButtonThemeData(
        style: IconButton.styleFrom(
          foregroundColor: scheme.onSurfaceVariant,
        ),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: isDark ? MX.surfaceOverlay : const Color(0xFFF0F0F5),
        side: BorderSide(color: scheme.outlineVariant),
        labelStyle: textTheme.labelMedium,
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(MX.rFull)),
      ),
      dividerTheme: DividerThemeData(
        color: scheme.outlineVariant,
        thickness: 0.5,
        space: 0.5,
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: isDark ? MX.bgSection : Colors.white,
        indicatorColor: MX.accentAiSoft,
        labelTextStyle: WidgetStatePropertyAll(
          textTheme.labelSmall?.copyWith(fontWeight: FontWeight.w600),
        ),
        elevation: 0,
        height: 72,
      ),
      bottomSheetTheme: BottomSheetThemeData(
        backgroundColor: isDark ? MX.bgCard : Colors.white,
        surfaceTintColor: Colors.transparent,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(MX.rXl)),
        ),
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: isDark ? MX.bgCard : Colors.white,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(MX.rLg)),
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        backgroundColor: isDark ? MX.bgElevated : const Color(0xFF18181B),
        contentTextStyle: textTheme.bodyMedium?.copyWith(color: MX.fg),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(MX.rMd)),
      ),
      tooltipTheme: TooltipThemeData(
        decoration: BoxDecoration(
          color: MX.bgElevated,
          borderRadius: BorderRadius.circular(MX.rSm),
        ),
        textStyle: textTheme.labelMedium?.copyWith(color: MX.fg),
      ),
    );
  }
}
