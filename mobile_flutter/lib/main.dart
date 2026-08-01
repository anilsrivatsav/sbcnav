import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';
import 'core/theme/app_theme.dart';
import 'core/theme/theme_controller.dart';
import 'data/local/app_database.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final database = AppDatabase();
  await database.open();
  final initialTheme = AppThemePresetInfo.fromStorage(
    await database.metadata('app_theme_preset'),
  );
  runApp(
    ProviderScope(
      overrides: [
        databaseProvider.overrideWithValue(database),
        initialThemePresetProvider.overrideWithValue(initialTheme),
      ],
      child: const RailInspectApp(),
    ),
  );
}
