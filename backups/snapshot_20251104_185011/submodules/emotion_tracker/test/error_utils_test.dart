import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:emotion_tracker/core/error_utils.dart';
import 'package:emotion_tracker/core/error_state.dart';
import 'package:emotion_tracker/core/error_constants.dart';
import 'package:emotion_tracker/providers/api_token_service.dart';

void main() {
  group('ErrorUtils', () {
    group('formatErrorMessage', () {
      test('should format ErrorState message correctly', () {
        final errorState = ErrorState(
          type: ErrorType.networkError,
          title: 'Network Error',
          message: 'Connection failed',
          icon: Icons.wifi_off,
          color: Colors.red,
        );

        final result = ErrorUtils.formatErrorMessage(errorState);
        expect(result, equals('Connection failed'));
      });

      test('should handle TimeoutException', () {
        final error = TimeoutException(
          'Request timeout',
          const Duration(seconds: 30),
        );
        final result = ErrorUtils.formatErrorMessage(error);
        expect(result, equals(ErrorConstants.timeout));
      });

      test('should handle FormatException', () {
        final error = FormatException('Invalid JSON');
        final result = ErrorUtils.formatErrorMessage(error);
        expect(result, equals('Invalid data format received from server.'));
      });

      test('should clean technical messages', () {
        final error = Exception('HttpException: Connection refused');
        final result = ErrorUtils.formatErrorMessage(error);
        expect(result, equals(ErrorConstants.connectionRefused));
      });

      test('should use fallback for null error', () {
        final result = ErrorUtils.formatErrorMessage(
          null,
          fallback: 'Custom fallback',
        );
        expect(result, equals('Custom fallback'));
      });

      test(
        'should use default fallback for null error without custom fallback',
        () {
          final result = ErrorUtils.formatErrorMessage(null);
          expect(result, equals(ErrorConstants.unknown));
        },
      );
    });

    group('getErrorSeverity', () {
      test('should return correct severity for ErrorState types', () {
        final unauthorizedError = ErrorState(
          type: ErrorType.unauthorized,
          title: 'Unauthorized',
          message: 'Session expired',
          icon: Icons.logout,
          color: Colors.orange,
        );
        expect(
          ErrorUtils.getErrorSeverity(unauthorizedError),
          equals(ErrorSeverity.warning),
        );

        final serverError = ErrorState(
          type: ErrorType.serverError,
          title: 'Server Error',
          message: 'Internal server error',
          icon: Icons.error,
          color: Colors.red,
        );
        expect(
          ErrorUtils.getErrorSeverity(serverError),
          equals(ErrorSeverity.error),
        );

        final cloudflareError = ErrorState(
          type: ErrorType.cloudflareError,
          title: 'Cloudflare Error',
          message: 'Tunnel down',
          icon: Icons.cloud_off,
          color: Colors.red,
        );
        expect(
          ErrorUtils.getErrorSeverity(cloudflareError),
          equals(ErrorSeverity.critical),
        );
      });

      test('should return correct severity for exception types', () {
        expect(
          ErrorUtils.getErrorSeverity(TimeoutException('timeout')),
          equals(ErrorSeverity.warning),
        );
        expect(
          ErrorUtils.getErrorSeverity(FormatException('format')),
          equals(ErrorSeverity.error),
        );
        expect(
          ErrorUtils.getErrorSeverity(Exception('generic')),
          equals(ErrorSeverity.error),
        );
      });
    });

    group('createRetryDelay', () {
      test('should create appropriate delay for rate limited errors', () async {
        final stopwatch = Stopwatch()..start();
        await ErrorUtils.createRetryDelay(1, ErrorType.rateLimited);
        stopwatch.stop();

        // Should be approximately 10 seconds (retryCount + 1) * 5
        expect(stopwatch.elapsedMilliseconds, greaterThan(9000));
        expect(stopwatch.elapsedMilliseconds, lessThan(11000));
      });

      test('should create exponential backoff for network errors', () async {
        final stopwatch = Stopwatch()..start();
        await ErrorUtils.createRetryDelay(1, ErrorType.networkError);
        stopwatch.stop();

        // Should be approximately 2 seconds (1 << 1)
        expect(stopwatch.elapsedMilliseconds, greaterThan(1800));
        expect(stopwatch.elapsedMilliseconds, lessThan(2200));
      });

      test('should use default delay for other error types', () async {
        final stopwatch = Stopwatch()..start();
        await ErrorUtils.createRetryDelay(1, ErrorType.generic);
        stopwatch.stop();

        // Should be approximately 2 seconds (ErrorConstants.retryDelay)
        expect(stopwatch.elapsedMilliseconds, greaterThan(1800));
        expect(stopwatch.elapsedMilliseconds, lessThan(2200));
      });
    });

    group('withRetry', () {
      test('should succeed on first attempt', () async {
        int callCount = 0;
        final result = await ErrorUtils.withRetry(() async {
          callCount++;
          return 'success';
        });

        expect(result, equals('success'));
        expect(callCount, equals(1));
      });

      test('should retry on failure and eventually succeed', () async {
        int callCount = 0;
        final result = await ErrorUtils.withRetry(() async {
          callCount++;
          if (callCount < 3) {
            throw Exception('Temporary failure');
          }
          return 'success';
        }, maxRetries: 3);

        expect(result, equals('success'));
        expect(callCount, equals(3));
      });

      test('should fail after max retries', () async {
        int callCount = 0;

        try {
          await ErrorUtils.withRetry(() async {
            callCount++;
            throw Exception('Persistent failure');
          }, maxRetries: 2);
          fail('Expected exception to be thrown');
        } catch (e) {
          expect(e, isA<Exception>());
        }

        expect(callCount, equals(3)); // Initial attempt + 2 retries
      });

      test('should respect custom shouldRetry function', () async {
        int callCount = 0;

        expect(() async {
          await ErrorUtils.withRetry(
            () async {
              callCount++;
              throw UnauthorizedException('Unauthorized');
            },
            maxRetries: 3,
            shouldRetry: (error) => false, // Don't retry unauthorized errors
          );
        }, throwsA(isA<UnauthorizedException>()));

        expect(callCount, equals(1)); // Should not retry
      });

      test('should call onRetry callback', () async {
        int retryCallbackCount = 0;
        dynamic lastRetryError;
        int lastRetryCount = -1;

        try {
          await ErrorUtils.withRetry(
            () async => throw Exception('Test error'),
            maxRetries: 2,
            onRetry: (error, retryCount) {
              retryCallbackCount++;
              lastRetryError = error;
              lastRetryCount = retryCount;
            },
          );
        } catch (e) {
          // Expected to fail
        }

        expect(retryCallbackCount, equals(2));
        expect(lastRetryError.toString(), contains('Test error'));
        expect(lastRetryCount, equals(1)); // Last retry count
      });

      test('should call onError callback on final failure', () async {
        dynamic finalError;
        StackTrace? finalStackTrace;

        try {
          await ErrorUtils.withRetry(
            () async => throw Exception('Final error'),
            maxRetries: 1,
            onError: (error, stackTrace) {
              finalError = error;
              finalStackTrace = stackTrace;
            },
          );
        } catch (e) {
          // Expected to fail
        }

        expect(finalError.toString(), contains('Final error'));
        expect(finalStackTrace, isNotNull);
      });
    });

    group('canRecover', () {
      test('should return false for unauthorized errors', () {
        final errorState = ErrorState(
          type: ErrorType.unauthorized,
          title: 'Unauthorized',
          message: 'Session expired',
          icon: Icons.logout,
          color: Colors.orange,
        );

        expect(ErrorUtils.canRecover(errorState, 0), isFalse);
      });

      test('should return false when max retries exceeded', () {
        final errorState = ErrorState(
          type: ErrorType.networkError,
          title: 'Network Error',
          message: 'Connection failed',
          icon: Icons.wifi_off,
          color: Colors.red,
        );

        expect(
          ErrorUtils.canRecover(errorState, ErrorConstants.maxRetries),
          isFalse,
        );
      });

      test('should return true for retryable errors within limits', () {
        final errorState = ErrorState(
          type: ErrorType.networkError,
          title: 'Network Error',
          message: 'Connection failed',
          icon: Icons.wifi_off,
          color: Colors.red,
        );

        expect(ErrorUtils.canRecover(errorState, 1), isTrue);
      });
    });

    group('createRecoveryStrategy', () {
      test('should return null for non-recoverable errors', () {
        final errorState = ErrorState(
          type: ErrorType.unauthorized,
          title: 'Unauthorized',
          message: 'Session expired',
          icon: Icons.logout,
          color: Colors.orange,
        );

        final strategy = ErrorUtils.createRecoveryStrategy(
          errorState,
          () async {},
          0,
        );

        expect(strategy, isNull);
      });

      test('should return recovery function for recoverable errors', () {
        final errorState = ErrorState(
          type: ErrorType.networkError,
          title: 'Network Error',
          message: 'Connection failed',
          icon: Icons.wifi_off,
          color: Colors.red,
        );

        final strategy = ErrorUtils.createRecoveryStrategy(
          errorState,
          () async {},
          0,
        );

        expect(strategy, isNotNull);
        expect(strategy, isA<Function>());
      });

      test(
        'should execute original operation when recovery strategy is called',
        () async {
          bool operationCalled = false;
          final errorState = ErrorState(
            type: ErrorType.networkError,
            title: 'Network Error',
            message: 'Connection failed',
            icon: Icons.wifi_off,
            color: Colors.red,
          );

          final strategy = ErrorUtils.createRecoveryStrategy(
            errorState,
            () async {
              operationCalled = true;
            },
            0,
          );

          expect(strategy, isNotNull);
          await strategy!();
          expect(operationCalled, isTrue);
        },
      );
    });

    group('getUserActionSuggestion', () {
      test(
        'should return appropriate suggestions for different error types',
        () {
          final networkError = ErrorState(
            type: ErrorType.networkError,
            title: 'Network Error',
            message: 'Connection failed',
            icon: Icons.wifi_off,
            color: Colors.red,
          );
          expect(
            ErrorUtils.getUserActionSuggestion(networkError),
            equals('Please check your internet connection and try again.'),
          );

          final rateLimitError = ErrorState(
            type: ErrorType.rateLimited,
            title: 'Rate Limited',
            message: 'Too many requests',
            icon: Icons.hourglass_empty,
            color: Colors.orange,
          );
          expect(
            ErrorUtils.getUserActionSuggestion(rateLimitError),
            equals('Please wait a moment before trying again.'),
          );

          final unauthorizedError = ErrorState(
            type: ErrorType.unauthorized,
            title: 'Unauthorized',
            message: 'Session expired',
            icon: Icons.logout,
            color: Colors.orange,
          );
          expect(
            ErrorUtils.getUserActionSuggestion(unauthorizedError),
            equals('Please log in again to continue.'),
          );
        },
      );
    });

    group('isCriticalError', () {
      test('should identify critical errors correctly', () {
        final cloudflareError = ErrorState(
          type: ErrorType.cloudflareError,
          title: 'Cloudflare Error',
          message: 'Tunnel down',
          icon: Icons.cloud_off,
          color: Colors.red,
        );

        expect(ErrorUtils.isCriticalError(cloudflareError), isTrue);

        final networkError = ErrorState(
          type: ErrorType.networkError,
          title: 'Network Error',
          message: 'Connection failed',
          icon: Icons.wifi_off,
          color: Colors.red,
        );

        expect(ErrorUtils.isCriticalError(networkError), isFalse);
      });
    });

    group('createDebouncedErrorHandler', () {
      test('should create a working debounced handler', () {
        final debouncedHandler = ErrorUtils.createDebouncedErrorHandler(
          (error) {},
        );

        expect(debouncedHandler, isA<Function>());

        // Call the handler - it should not throw
        expect(() => debouncedHandler(Exception('Test')), returnsNormally);
      });

      test('should format error messages correctly for comparison', () {
        // Test that different exceptions with same message are treated as duplicates
        final error1 = Exception('Same message');
        final error2 = Exception('Same message');
        final error3 = Exception('Different message');

        final message1 = ErrorUtils.formatErrorMessage(error1);
        final message2 = ErrorUtils.formatErrorMessage(error2);
        final message3 = ErrorUtils.formatErrorMessage(error3);

        expect(message1, equals(message2)); // Same message should be equal
        expect(
          message1,
          isNot(equals(message3)),
        ); // Different message should not be equal
      });

      test('should handle immediate duplicate errors', () {
        int handlerCallCount = 0;
        final debouncedHandler = ErrorUtils.createDebouncedErrorHandler(
          (error) => handlerCallCount++,
          debounceTime: const Duration(milliseconds: 100),
        );

        // Call with same error message multiple times immediately
        debouncedHandler(Exception('Test error'));
        debouncedHandler(
          Exception('Test error'),
        ); // Should be skipped as duplicate
        debouncedHandler(
          Exception('Test error'),
        ); // Should be skipped as duplicate

        // The handler should not be called yet (timer hasn't fired)
        expect(handlerCallCount, equals(0));
      });

      test('should create a working debounced handler', () {
        // Simple test to verify the handler is created and can be called
        bool handlerCreated = false;
        final debouncedHandler = ErrorUtils.createDebouncedErrorHandler(
          (error) => handlerCreated = true,
        );

        expect(debouncedHandler, isA<Function>());

        // Call the handler - it should not throw
        expect(() => debouncedHandler(Exception('Test')), returnsNormally);
      });
    });

    group('safeErrorHandler', () {
      test('should handle errors without throwing', () {
        String? capturedMessage;

        expect(() {
          ErrorUtils.safeErrorHandler(
            Exception('Test error'),
            onSafeError: (message) => capturedMessage = message,
          );
        }, returnsNormally);

        expect(capturedMessage, isNotNull);
        expect(capturedMessage, contains('Test error'));
      });

      test('should use fallback message when error handling fails', () {
        String? capturedMessage;

        ErrorUtils.safeErrorHandler(
          null,
          fallbackMessage: 'Safe fallback',
          onSafeError: (message) => capturedMessage = message,
        );

        expect(capturedMessage, equals('Safe fallback'));
      });
    });
  });
}
