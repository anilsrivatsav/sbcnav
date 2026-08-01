import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/theme/app_theme.dart';
import 'features/shell/mobile_shell.dart';

class RailInspectApp extends ConsumerWidget {
  const RailInspectApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Rail Inspect',
      themeMode: ThemeMode.light,
      theme: AppTheme.softNeumorphic,
      darkTheme: AppTheme.softNeumorphic,
      themeAnimationDuration: const Duration(milliseconds: 420),
      themeAnimationCurve: Curves.easeOutCubic,
      home: const MobileShell(),
    );
  }
}
