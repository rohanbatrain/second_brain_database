import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:emotion_tracker/widgets/error_state_widget.dart';
import 'package:emotion_tracker/providers/api_token_service.dart';
import 'package:emotion_tracker/utils/http_util.dart';

void main() {
  group('ErrorStateWidget Tests', () {
    Widget createTestWidget(Widget child) {
      return ProviderScope(child: MaterialApp(home: Scaffold(body: child)));
    }

    testWidgets('should display UnauthorizedException correctly', (
      tester,
    ) async {
      final error = UnauthorizedException('Session expired');
      bool retryPressed = false;

      await tester.pumpWidget(
        createTestWidget(
          ErrorStateWidget(error: error, onRetry: () => retryPressed = true),
        ),
      );

      // Check for session expired title and logout icon
      expect(find.text('Session Expired'), findsOneWidget);
      expect(find.byIcon(Icons.logout), findsOneWidget);
      expect(
        find.text('Your session has expired. Please log in again.'),
        findsOneWidget,
      );

      // Unauthorized errors should not show retry button by default
      expect(find.text('Retry'), findsNothing);
    });

    testWidgets('should display RateLimitException correctly', (tester) async {
      final error = RateLimitException('Too many requests');
      bool retryPressed = false;

      await tester.pumpWidget(
        createTestWidget(
          ErrorStateWidget(error: error, onRetry: () => retryPressed = true),
        ),
      );

      // Check for rate limit title and hourglass icon
      expect(find.text('Rate Limited'), findsOneWidget);
      expect(find.byIcon(Icons.hourglass_empty), findsOneWidget);
      expect(find.text('Too many requests'), findsOneWidget);

      // Should show retry button
      expect(find.text('Retry'), findsOneWidget);

      // Test retry callback
      await tester.tap(find.text('Retry'));
      expect(retryPressed, isTrue);
    });

    testWidgets('should display CloudflareTunnelException correctly', (
      tester,
    ) async {
      final error = CloudflareTunnelException(
        'Tunnel down',
        502,
        'Bad Gateway',
      );
      bool retryPressed = false;
      bool infoPressed = false;

      await tester.pumpWidget(
        createTestWidget(
          ErrorStateWidget(
            error: error,
            onRetry: () => retryPressed = true,
            onInfo: () => infoPressed = true,
          ),
        ),
      );

      // Check for server unavailable title and cloud off icon
      expect(find.text('Server Unavailable'), findsOneWidget);
      expect(find.byIcon(Icons.cloud_off), findsOneWidget);
      expect(find.text('Tunnel down'), findsOneWidget);

      // Should show both retry and info buttons
      expect(find.text('Retry'), findsOneWidget);
      expect(find.text('More Info'), findsOneWidget);

      // Test retry callback
      await tester.tap(find.text('Retry'));
      expect(retryPressed, isTrue);

      // Test info callback
      await tester.tap(find.text('More Info'));
      expect(infoPressed, isTrue);
    });

    testWidgets('should display NetworkException correctly', (tester) async {
      final error = NetworkException('No internet connection');
      bool retryPressed = false;

      await tester.pumpWidget(
        createTestWidget(
          ErrorStateWidget(error: error, onRetry: () => retryPressed = true),
        ),
      );

      // Check for connection problem title and wifi off icon
      expect(find.text('Connection Problem'), findsOneWidget);
      expect(find.byIcon(Icons.wifi_off), findsOneWidget);
      expect(find.text('No internet connection'), findsOneWidget);

      // Should show retry button
      expect(find.text('Retry'), findsOneWidget);

      // Test retry callback
      await tester.tap(find.text('Retry'));
      expect(retryPressed, isTrue);
    });

    testWidgets('should display ApiException with server error correctly', (
      tester,
    ) async {
      final error = ApiException('Internal server error', 500);
      bool retryPressed = false;

      await tester.pumpWidget(
        createTestWidget(
          ErrorStateWidget(error: error, onRetry: () => retryPressed = true),
        ),
      );

      // Check for server error title and error icon
      expect(find.text('Server Error'), findsOneWidget);
      expect(find.byIcon(Icons.error_outline), findsOneWidget);
      expect(
        find.text('Internal server error occurred. Please try again later.'),
        findsOneWidget,
      );

      // Should show retry and info buttons for server errors
      expect(find.text('Retry'), findsOneWidget);
      expect(find.text('More Info'), findsOneWidget);

      // Test retry callback
      await tester.tap(find.text('Retry'));
      expect(retryPressed, isTrue);
    });

    testWidgets('should display ApiException with client error correctly', (
      tester,
    ) async {
      final error = ApiException('Access denied', 403);
      bool retryPressed = false;

      await tester.pumpWidget(
        createTestWidget(
          ErrorStateWidget(error: error, onRetry: () => retryPressed = true),
        ),
      );

      // Check for generic error title and error icon
      expect(find.text('Error'), findsOneWidget);
      expect(find.byIcon(Icons.error_outline), findsOneWidget);
      expect(
        find.text('You do not have permission to perform this action.'),
        findsOneWidget,
      );

      // Should show retry button
      expect(find.text('Retry'), findsOneWidget);

      // Test retry callback
      await tester.tap(find.text('Retry'));
      expect(retryPressed, isTrue);
    });

    testWidgets('should display generic error correctly', (tester) async {
      final error = Exception('Unknown error');
      bool retryPressed = false;

      await tester.pumpWidget(
        createTestWidget(
          ErrorStateWidget(error: error, onRetry: () => retryPressed = true),
        ),
      );

      // Check for generic error title and error icon
      expect(find.text('Error'), findsOneWidget);
      expect(find.byIcon(Icons.error_outline), findsOneWidget);
      expect(find.text('An unknown error occurred.'), findsOneWidget);

      // Should show retry button
      expect(find.text('Retry'), findsOneWidget);

      // Test retry callback
      await tester.tap(find.text('Retry'));
      expect(retryPressed, isTrue);
    });

    testWidgets('should support custom messages and titles', (tester) async {
      final error = NetworkException('Network error');

      await tester.pumpWidget(
        createTestWidget(
          ErrorStateWidget(
            error: error,
            customTitle: 'Custom Title',
            customMessage: 'Custom error message',
          ),
        ),
      );

      // Check for custom title and message
      expect(find.text('Custom Title'), findsOneWidget);
      expect(find.text('Custom error message'), findsOneWidget);

      // Should still use the correct icon for the error type
      expect(find.byIcon(Icons.wifi_off), findsOneWidget);
    });

    testWidgets('should support compact mode', (tester) async {
      final error = NetworkException('Network error');

      await tester.pumpWidget(
        createTestWidget(
          ErrorStateWidget(error: error, compact: true, onRetry: () {}),
        ),
      );

      // Widget should render (specific size testing would require more complex setup)
      expect(find.text('Connection Problem'), findsOneWidget);
      expect(find.byIcon(Icons.wifi_off), findsOneWidget);
      expect(find.text('Retry'), findsOneWidget);
    });

    testWidgets('should handle missing callbacks gracefully', (tester) async {
      final error = CloudflareTunnelException(
        'Tunnel down',
        502,
        'Bad Gateway',
      );

      await tester.pumpWidget(createTestWidget(ErrorStateWidget(error: error)));

      // Should show info button even without onInfo callback (uses default)
      expect(find.text('More Info'), findsOneWidget);

      // Should not show retry button without onRetry callback
      expect(find.text('Retry'), findsNothing);
    });
  });
}
