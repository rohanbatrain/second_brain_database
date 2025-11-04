import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:emotion_tracker/screens/settings/account/api-tokens/api_tokens_screen.dart';
import 'package:emotion_tracker/providers/api_token_service.dart';
import 'package:emotion_tracker/widgets/error_state_widget.dart';
import 'package:emotion_tracker/widgets/loading_state_widget.dart';

void main() {
  group('API Tokens Screen Integration', () {
    testWidgets('should use ErrorStateWidget for error state', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            apiTokensProvider.overrideWith((ref) async {
              throw ApiException('Test error', 500);
            }),
          ],
          child: MaterialApp(home: const ApiTokensScreen()),
        ),
      );

      await tester.pump();

      // Verify ErrorStateWidget is displayed
      expect(find.byType(ErrorStateWidget), findsOneWidget);
      expect(find.text('Retry'), findsOneWidget);
    });

    testWidgets('should display empty state when no tokens', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            apiTokensProvider.overrideWith((ref) async {
              return <ApiToken>[];
            }),
          ],
          child: MaterialApp(home: const ApiTokensScreen()),
        ),
      );

      await tester.pump();

      // Verify empty state is displayed
      expect(find.text('No API tokens found'), findsOneWidget);
      expect(find.byIcon(Icons.key_off), findsOneWidget);
    });

    testWidgets('should display tokens when data is available', (tester) async {
      // Create test tokens
      final testTokens = [
        ApiToken(
          tokenId: 'test-1',
          description: 'Test Token 1',
          createdAt: DateTime.now(),
          revoked: false,
        ),
        ApiToken(
          tokenId: 'test-2',
          description: 'Test Token 2',
          createdAt: DateTime.now(),
          revoked: true,
        ),
      ];

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            apiTokensProvider.overrideWith((ref) async {
              return testTokens;
            }),
          ],
          child: MaterialApp(home: const ApiTokensScreen()),
        ),
      );

      await tester.pump();

      // Verify tokens are displayed
      expect(find.text('Test Token 1'), findsOneWidget);
      expect(find.text('Test Token 2'), findsOneWidget);
      expect(find.text('REVOKED'), findsOneWidget);
    });

    testWidgets('should use new error handling components', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            apiTokensProvider.overrideWith((ref) async {
              throw UnauthorizedException('Session expired');
            }),
          ],
          child: MaterialApp(home: const ApiTokensScreen()),
        ),
      );

      await tester.pump();

      // Verify ErrorStateWidget is used for error handling
      expect(find.byType(ErrorStateWidget), findsOneWidget);

      // The ErrorStateWidget should handle unauthorized errors appropriately
      expect(find.text('Session Expired'), findsOneWidget);
    });
  });
}
