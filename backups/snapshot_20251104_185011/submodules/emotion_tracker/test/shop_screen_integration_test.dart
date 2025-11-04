import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:emotion_tracker/screens/shop/variant1/variant1.dart';

void main() {
  group('Shop Screen Integration Tests', () {
    testWidgets('should render shop screen with all tabs', (
      WidgetTester tester,
    ) async {
      // Build the shop screen wrapped in ProviderScope
      await tester.pumpWidget(
        ProviderScope(child: MaterialApp(home: const ShopScreenV1())),
      );

      // Wait for the widget to settle
      await tester.pumpAndSettle();

      // Verify that the shop screen renders
      expect(find.byType(ShopScreenV1), findsOneWidget);

      // Verify that tabs are present
      expect(find.byType(TabBar), findsOneWidget);
      expect(find.byType(TabBarView), findsOneWidget);

      // Verify tab labels exist
      expect(find.text('Avatars'), findsOneWidget);
      expect(find.text('Banners'), findsOneWidget);
      expect(find.text('Themes'), findsOneWidget);
      expect(find.text('Bundles'), findsOneWidget);
      expect(find.text('Currency'), findsOneWidget);
    });

    testWidgets('should switch between tabs correctly', (
      WidgetTester tester,
    ) async {
      await tester.pumpWidget(
        ProviderScope(child: MaterialApp(home: const ShopScreenV1())),
      );

      await tester.pumpAndSettle();

      // Test switching to Banners tab
      await tester.tap(find.text('Banners'));
      await tester.pumpAndSettle();

      // Test switching to Themes tab
      await tester.tap(find.text('Themes'));
      await tester.pumpAndSettle();

      // Test switching to Bundles tab
      await tester.tap(find.text('Bundles'));
      await tester.pumpAndSettle();

      // Test switching to Currency tab
      await tester.tap(find.text('Currency'));
      await tester.pumpAndSettle();

      // Switch back to Avatars tab
      await tester.tap(find.text('Avatars'));
      await tester.pumpAndSettle();
    });

    testWidgets('should display cart icon in app bar', (
      WidgetTester tester,
    ) async {
      await tester.pumpWidget(
        ProviderScope(child: MaterialApp(home: const ShopScreenV1())),
      );

      await tester.pumpAndSettle();

      // Verify cart icon is present
      expect(find.byIcon(Icons.shopping_cart_outlined), findsOneWidget);
    });
  });
}
