import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/local/app_database.dart';
import 'app_theme.dart';

final initialThemePresetProvider = Provider<AppThemePreset>(
  (_) => AppThemePreset.vision,
);

final themeControllerProvider =
    StateNotifierProvider<ThemeController, AppThemePreset>((ref) {
  return ThemeController(
    database: ref.read(databaseProvider),
    initialPreset: ref.read(initialThemePresetProvider),
  );
});

class ThemeController extends StateNotifier<AppThemePreset> {
  ThemeController({
    required AppDatabase database,
    required AppThemePreset initialPreset,
  })  : _database = database,
        super(initialPreset);

  final AppDatabase _database;

  Future<void> select(AppThemePreset preset) async {
    if (preset == state) return;
    state = preset;
    await _database.setMetadata('app_theme_preset', preset.storageKey);
  }
}
