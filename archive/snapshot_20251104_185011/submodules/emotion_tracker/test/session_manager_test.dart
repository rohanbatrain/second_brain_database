import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:emotion_tracker/core/session_manager.dart';
import 'package:emotion_tracker/providers/api_token_service.dart'
    show UnauthorizedException;

void main() {
  group('SessionManager', () {
    test('should detect UnauthorizedException as session expired', () {
      final error = UnauthorizedException('Session expired');
      expect(SessionManager.isSessionExpired(error), true);

      final otherError = Exception('Other error');
      expect(SessionManager.isSessionExpired(otherError), false);
    });

    testWidgets('should check session validity correctly', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: Consumer(
            builder: (context, ref, child) {
              return MaterialApp(
                home: Scaffold(
                  body: Builder(
                    builder: (context) {
                      // Initially should be invalid (not logged in)
                      final isValid = SessionManager.isSessionValid(ref);
                      return Text('Session valid: $isValid');
                    },
                  ),
                ),
              );
            },
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Should show that session is not valid initially
      expect(find.text('Session valid: false'), findsOneWidget);
    });

    testWidgets('should clear auth data using existing auth provider', (
      tester,
    ) async {
      await tester.pumpWidget(
        ProviderScope(
          child: Consumer(
            builder: (context, ref, child) {
              return MaterialApp(
                home: Scaffold(
                  body: ElevatedButton(
                    onPressed: () async {
                      await SessionManager.clearAuthData(ref);
                    },
                    child: const Text('Clear Auth Data'),
                  ),
                ),
              );
            },
          ),
        ),
      );

      // Should not throw any errors when clearing auth data
      await tester.tap(find.text('Clear Auth Data'));
      await tester.pumpAndSettle();

      // Test passes if no exceptions are thrown
      expect(find.text('Clear Auth Data'), findsOneWidget);
    });
  });
}
