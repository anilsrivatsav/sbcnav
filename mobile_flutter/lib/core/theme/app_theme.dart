import 'package:flutter/material.dart';

abstract final class AppPalette {
  static const teal = Color(0xFF00AFA5);
  static const indigo = Color(0xFF5B5FEF);
  static const royalBlue = Color(0xFF2878FF);
  static const emerald = Color(0xFF00A878);
  static const cyan = Color(0xFF00A7C4);
  static const amber = Color(0xFFF2A900);
  static const red = Color(0xFFE84855);
  static const ink = Color(0xFF102338);
  static const midnight = Color(0xFF07131F);
}

enum AppThemePreset { vision, deepTeal, midnight, alpine, signal }

extension AppThemePresetInfo on AppThemePreset {
  String get storageKey => name;

  String get label => switch (this) {
        AppThemePreset.vision => 'Vision Glass',
        AppThemePreset.deepTeal => 'Deep Teal',
        AppThemePreset.midnight => 'Midnight',
        AppThemePreset.alpine => 'Alpine',
        AppThemePreset.signal => 'Signal',
      };

  String get description => switch (this) {
        AppThemePreset.vision => 'Adaptive blue-grey glass',
        AppThemePreset.deepTeal => 'Reference-inspired dark teal',
        AppThemePreset.midnight => 'Indigo night operations',
        AppThemePreset.alpine => 'Bright and low-glare',
        AppThemePreset.signal => 'High-contrast control room',
      };

  ThemeMode get themeMode => switch (this) {
        AppThemePreset.vision => ThemeMode.system,
        AppThemePreset.alpine => ThemeMode.light,
        _ => ThemeMode.dark,
      };

  List<Color> get previewColors => switch (this) {
        AppThemePreset.vision => const [
            Color(0xFFDCE8F2),
            Color(0xFF5B5FEF),
            Color(0xFF00AFA5),
          ],
        AppThemePreset.deepTeal => const [
            Color(0xFF061A1E),
            Color(0xFF123D42),
            Color(0xFF29A7F4),
          ],
        AppThemePreset.midnight => const [
            Color(0xFF090C20),
            Color(0xFF29245B),
            Color(0xFF5C8DFF),
          ],
        AppThemePreset.alpine => const [
            Color(0xFFF6FAFC),
            Color(0xFFDDEEF0),
            Color(0xFF315DA8),
          ],
        AppThemePreset.signal => const [
            Color(0xFF0E1318),
            Color(0xFF28221A),
            Color(0xFFF2A900),
          ],
      };

  static AppThemePreset fromStorage(String? value) {
    return AppThemePreset.values.firstWhere(
      (preset) => preset.storageKey == value,
      orElse: () => AppThemePreset.vision,
    );
  }
}

class AppVisualTheme extends ThemeExtension<AppVisualTheme> {
  const AppVisualTheme({
    required this.background,
    required this.glassTint,
    required this.glassHighlight,
    required this.ambientAccent,
  });

  final List<Color> background;
  final Color glassTint;
  final Color glassHighlight;
  final Color ambientAccent;

  @override
  AppVisualTheme copyWith({
    List<Color>? background,
    Color? glassTint,
    Color? glassHighlight,
    Color? ambientAccent,
  }) {
    return AppVisualTheme(
      background: background ?? this.background,
      glassTint: glassTint ?? this.glassTint,
      glassHighlight: glassHighlight ?? this.glassHighlight,
      ambientAccent: ambientAccent ?? this.ambientAccent,
    );
  }

  @override
  AppVisualTheme lerp(covariant AppVisualTheme? other, double t) {
    if (other == null) return this;
    return AppVisualTheme(
      background: List.generate(
        background.length,
        (index) => Color.lerp(
          background[index],
          other.background[index],
          t,
        )!,
      ),
      glassTint: Color.lerp(glassTint, other.glassTint, t)!,
      glassHighlight: Color.lerp(glassHighlight, other.glassHighlight, t)!,
      ambientAccent: Color.lerp(ambientAccent, other.ambientAccent, t)!,
    );
  }
}

class AppTheme {
  static ThemeData get softNeumorphic =>
      forPreset(AppThemePreset.vision, Brightness.light);

  static ThemeData get light =>
      forPreset(AppThemePreset.vision, Brightness.light);
  static ThemeData get dark =>
      forPreset(AppThemePreset.vision, Brightness.dark);

  static ThemeData forPreset(
    AppThemePreset preset,
    Brightness brightness,
  ) {
    final effectiveBrightness = preset == AppThemePreset.alpine
        ? Brightness.light
        : preset == AppThemePreset.vision
            ? brightness
            : Brightness.dark;
    return _theme(effectiveBrightness, preset);
  }

  static ThemeData _theme(
    Brightness brightness,
    AppThemePreset preset,
  ) {
    final dark = brightness == Brightness.dark;
    final colors = _colorScheme(preset, brightness);
    final visual = _visualTheme(preset, brightness);

    final baseText = Typography.material2021(
      platform: TargetPlatform.android,
    ).black.apply(
          bodyColor: colors.onSurface,
          displayColor: colors.onSurface,
        );

    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      colorScheme: colors,
      scaffoldBackgroundColor: Colors.transparent,
      canvasColor: colors.surface,
      splashFactory: NoSplash.splashFactory,
      highlightColor: Colors.transparent,
      hoverColor: Colors.transparent,
      extensions: [visual],
      textTheme: baseText.copyWith(
        headlineLarge: baseText.headlineLarge?.copyWith(
          fontSize: 32,
          fontWeight: FontWeight.w900,
          height: 1.1,
          letterSpacing: 0,
        ),
        headlineMedium: baseText.headlineMedium?.copyWith(
          fontSize: 27,
          fontWeight: FontWeight.w900,
          height: 1.12,
          letterSpacing: 0,
        ),
        headlineSmall: baseText.headlineSmall?.copyWith(
          fontSize: 23,
          fontWeight: FontWeight.w900,
          height: 1.15,
          letterSpacing: 0,
        ),
        titleLarge: baseText.titleLarge?.copyWith(
          fontSize: 19,
          fontWeight: FontWeight.w800,
          height: 1.2,
          letterSpacing: 0,
        ),
        titleMedium: baseText.titleMedium?.copyWith(
          fontSize: 15,
          fontWeight: FontWeight.w800,
          height: 1.28,
          letterSpacing: 0,
        ),
        bodyLarge: baseText.bodyLarge?.copyWith(
          fontSize: 15,
          height: 1.42,
          letterSpacing: 0,
        ),
        bodyMedium: baseText.bodyMedium?.copyWith(
          fontSize: 13.5,
          height: 1.4,
          letterSpacing: 0,
        ),
        bodySmall: baseText.bodySmall?.copyWith(
          fontSize: 11.5,
          height: 1.35,
          letterSpacing: 0,
        ),
        labelLarge: baseText.labelLarge?.copyWith(
          fontSize: 13,
          fontWeight: FontWeight.w800,
          letterSpacing: 0,
        ),
      ),
      appBarTheme: AppBarTheme(
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        backgroundColor: Colors.transparent,
        surfaceTintColor: Colors.transparent,
        foregroundColor: colors.onSurface,
        titleTextStyle: TextStyle(
          color: colors.onSurface,
          fontSize: 19,
          fontWeight: FontWeight.w900,
          letterSpacing: 0,
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: colors.surface.withValues(alpha: dark ? 0.34 : 0.52),
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 16, vertical: 15),
        labelStyle: TextStyle(color: colors.onSurfaceVariant),
        hintStyle:
            TextStyle(color: colors.onSurfaceVariant.withValues(alpha: 0.7)),
        prefixIconColor: colors.primary,
        suffixIconColor: colors.onSurfaceVariant,
        border: _inputBorder(colors.outlineVariant.withValues(alpha: 0.48)),
        enabledBorder:
            _inputBorder(colors.outlineVariant.withValues(alpha: 0.48)),
        focusedBorder: _inputBorder(colors.primary.withValues(alpha: 0.8), 1.5),
        errorBorder: _inputBorder(colors.error.withValues(alpha: 0.8), 1.4),
      ),
      cardTheme: const CardThemeData(
        color: Colors.transparent,
        elevation: 0,
        margin: EdgeInsets.zero,
      ),
      dialogTheme: const DialogThemeData(
        elevation: 0,
        backgroundColor: Colors.transparent,
        surfaceTintColor: Colors.transparent,
      ),
      bottomSheetTheme: const BottomSheetThemeData(
        elevation: 0,
        modalElevation: 0,
        backgroundColor: Colors.transparent,
        modalBackgroundColor: Colors.transparent,
        surfaceTintColor: Colors.transparent,
        showDragHandle: false,
      ),
      popupMenuTheme: PopupMenuThemeData(
        elevation: 0,
        color: colors.surface.withValues(alpha: 0.94),
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: BorderSide(
            color: Colors.white.withValues(alpha: dark ? 0.08 : 0.56),
          ),
        ),
      ),
      dropdownMenuTheme: DropdownMenuThemeData(
        menuStyle: MenuStyle(
          elevation: const WidgetStatePropertyAll(0),
          backgroundColor: WidgetStatePropertyAll(
            colors.surface.withValues(alpha: 0.96),
          ),
          shape: WidgetStatePropertyAll(
            RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
          ),
        ),
      ),
      dividerTheme: DividerThemeData(
        color: colors.outlineVariant.withValues(alpha: 0.38),
        thickness: 1,
      ),
      progressIndicatorTheme: ProgressIndicatorThemeData(
        color: colors.primary,
        linearTrackColor:
            colors.surfaceContainerHighest.withValues(alpha: 0.55),
      ),
      tooltipTheme: TooltipThemeData(
        decoration: BoxDecoration(
          color: colors.inverseSurface.withValues(alpha: 0.94),
          borderRadius: BorderRadius.circular(12),
          boxShadow: const [
            BoxShadow(
              color: Color(0x26000000),
              blurRadius: 18,
              offset: Offset(0, 8),
            ),
          ],
        ),
        textStyle: TextStyle(color: colors.onInverseSurface),
      ),
      pageTransitionsTheme: const PageTransitionsTheme(
        builders: {
          TargetPlatform.android: FadeForwardsPageTransitionsBuilder(),
          TargetPlatform.iOS: FadeForwardsPageTransitionsBuilder(),
        },
      ),
    );
  }

  static OutlineInputBorder _inputBorder(Color color, [double width = 1]) {
    return OutlineInputBorder(
      borderRadius: BorderRadius.circular(18),
      borderSide: BorderSide(color: color, width: width),
    );
  }

  static ColorScheme _colorScheme(
    AppThemePreset preset,
    Brightness brightness,
  ) {
    final dark = brightness == Brightness.dark;
    final seed = switch (preset) {
      AppThemePreset.vision => const Color(0xFF8B5CF6),
      AppThemePreset.deepTeal => const Color(0xFF42B8A8),
      AppThemePreset.midnight => const Color(0xFF777BFF),
      AppThemePreset.alpine => const Color(0xFF1D7180),
      AppThemePreset.signal => AppPalette.amber,
    };
    final surface = switch (preset) {
      AppThemePreset.vision =>
        dark ? const Color(0xFF122232) : const Color(0xFFFFFEFF),
      AppThemePreset.deepTeal => const Color(0xFF0B292D),
      AppThemePreset.midnight => const Color(0xFF15182D),
      AppThemePreset.alpine => const Color(0xFFF8FBFC),
      AppThemePreset.signal => const Color(0xFF1B2025),
    };
    var scheme = ColorScheme.fromSeed(
      seedColor: seed,
      brightness: brightness,
      surface: surface,
      dynamicSchemeVariant: DynamicSchemeVariant.fidelity,
    );
    if (preset == AppThemePreset.vision && !dark) {
      scheme = scheme.copyWith(
        primary: const Color(0xFF1A2942),
        onPrimary: Colors.white,
        secondary: const Color(0xFF18B7A5),
        tertiary: const Color(0xFF9859E8),
        surface: const Color(0xFFFFFEFF),
        surfaceContainerHighest: const Color(0xFFF3F0FA),
      );
    }
    if (preset == AppThemePreset.deepTeal) {
      scheme = scheme.copyWith(
        primary: const Color(0xFF73D4C4),
        secondary: const Color(0xFF6CC56E),
        tertiary: const Color(0xFF36A9F4),
        surfaceContainerHighest: const Color(0xFF173D42),
      );
    } else if (preset == AppThemePreset.midnight) {
      scheme = scheme.copyWith(
        primary: const Color(0xFFA8AAFF),
        secondary: const Color(0xFF55D8CF),
        tertiary: const Color(0xFF65A6FF),
        surfaceContainerHighest: const Color(0xFF292D50),
      );
    } else if (preset == AppThemePreset.signal) {
      scheme = scheme.copyWith(
        primary: const Color(0xFFFFC247),
        secondary: const Color(0xFF4FD8D0),
        tertiary: const Color(0xFFFF6574),
        surfaceContainerHighest: const Color(0xFF33302B),
      );
    }
    return scheme;
  }

  static AppVisualTheme _visualTheme(
    AppThemePreset preset,
    Brightness brightness,
  ) {
    final dark = brightness == Brightness.dark;
    return switch (preset) {
      AppThemePreset.vision => AppVisualTheme(
          background: dark
              ? const [
                  Color(0xFF07131F),
                  Color(0xFF10283A),
                  Color(0xFF171D36),
                  Color(0xFF092A2E),
                ]
              : const [
                  Color(0xFFEDE6FF),
                  Color(0xFFF8F2FF),
                  Color(0xFFFFF0F1),
                  Color(0xFFFFEBDD),
                ],
          glassTint: dark ? const Color(0xFF162B3C) : Colors.white,
          glassHighlight: dark ? const Color(0xFF6A91B2) : Colors.white,
          ambientAccent: AppPalette.indigo,
        ),
      AppThemePreset.deepTeal => const AppVisualTheme(
          background: [
            Color(0xFF051316),
            Color(0xFF08272C),
            Color(0xFF0B363A),
            Color(0xFF071E22),
          ],
          glassTint: Color(0xFF123C41),
          glassHighlight: Color(0xFF67B6A8),
          ambientAccent: Color(0xFF36A9F4),
        ),
      AppThemePreset.midnight => const AppVisualTheme(
          background: [
            Color(0xFF07091A),
            Color(0xFF111633),
            Color(0xFF201846),
            Color(0xFF0A2531),
          ],
          glassTint: Color(0xFF24294E),
          glassHighlight: Color(0xFF8F95FF),
          ambientAccent: Color(0xFF5C8DFF),
        ),
      AppThemePreset.alpine => const AppVisualTheme(
          background: [
            Color(0xFFE3EFF2),
            Color(0xFFF8FBFC),
            Color(0xFFE7EEF8),
            Color(0xFFF0F1FC),
          ],
          glassTint: Colors.white,
          glassHighlight: Colors.white,
          ambientAccent: Color(0xFF315DA8),
        ),
      AppThemePreset.signal => const AppVisualTheme(
          background: [
            Color(0xFF0B1015),
            Color(0xFF171E25),
            Color(0xFF282117),
            Color(0xFF101A21),
          ],
          glassTint: Color(0xFF292A29),
          glassHighlight: Color(0xFFFFD27A),
          ambientAccent: Color(0xFFF2A900),
        ),
    };
  }
}
