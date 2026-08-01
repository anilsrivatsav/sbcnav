import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:rail_inspect/core/theme/app_theme.dart';
import 'package:rail_inspect/core/theme/theme_controller.dart';
import 'package:rail_inspect/data/local/app_database.dart';

void main() {
  test('every preset provides a complete visual theme', () {
    for (final preset in AppThemePreset.values) {
      final theme = AppTheme.forPreset(preset, Brightness.dark);
      expect(theme.extension<AppVisualTheme>(), isNotNull);
      expect(
        theme.extension<AppVisualTheme>()!.background,
        hasLength(4),
      );
    }
  });

  test('preset brightness follows its intended environment', () {
    expect(
      AppTheme.forPreset(
        AppThemePreset.deepTeal,
        Brightness.light,
      ).brightness,
      Brightness.dark,
    );
    expect(
      AppTheme.forPreset(
        AppThemePreset.alpine,
        Brightness.dark,
      ).brightness,
      Brightness.light,
    );
  });

  test('theme controller persists a selection', () async {
    final database = _ThemeTestDatabase();
    final controller = ThemeController(
      database: database,
      initialPreset: AppThemePreset.vision,
    );

    await controller.select(AppThemePreset.deepTeal);

    expect(controller.state, AppThemePreset.deepTeal);
    expect(database.savedValue, 'deepTeal');
  });
}

class _ThemeTestDatabase extends AppDatabase {
  String? savedValue;

  @override
  Future<void> setMetadata(String key, Object value) async {
    expect(key, 'app_theme_preset');
    savedValue = '$value';
  }
}
