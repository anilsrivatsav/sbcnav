import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:rail_inspect/core/theme/app_theme.dart';
import 'package:rail_inspect/shared/widgets.dart';

void main() {
  testWidgets('Rail Inspect design system renders', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.light,
        home: const Scaffold(body: Text('Rail Inspect')),
      ),
    );

    expect(find.text('Rail Inspect'), findsOneWidget);
    expect(Theme.of(tester.element(find.text('Rail Inspect'))).useMaterial3,
        isTrue);
  });

  testWidgets('premium button exposes an accessible tap target', (
    tester,
  ) async {
    var tapped = false;
    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.light,
        home: Scaffold(
          body: Center(
            child: AppButton(
              label: 'Start inspection',
              icon: Icons.fact_check_outlined,
              onPressed: () => tapped = true,
            ),
          ),
        ),
      ),
    );

    final button = find.text('Start inspection');
    expect(button, findsOneWidget);
    expect(tester.getSize(find.byType(AppButton)).height,
        greaterThanOrEqualTo(48));
    await tester.tap(button);
    expect(tapped, isTrue);
  });
}
