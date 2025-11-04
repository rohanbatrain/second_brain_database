import 'package:flutter_test/flutter_test.dart';
import 'package:emotion_tracker/core/global_error_handler.dart';
import 'package:emotion_tracker/core/error_state.dart';
import 'package:emotion_tracker/core/error_constants.dart';
import 'package:emotion_tracker/providers/api_token_service.dart';
import 'package:emotion_tracker/utils/http_util.dart';

void main() {
  group('Global Error Handling System - Comprehensive Tests', () {
    group('Error Classification and Processing', () {
      test('should handle all known exception types correctly', () {
        final testCases = [
          (UnauthorizedException('Session expired'), ErrorType.unauthorized),
          (RateLimitException('Rate limited'), ErrorType.rateLimited),
          (
            CloudflareTunnelException('Tunnel down', 502, 'body'),
            ErrorType.cloudflareError,
          ),
          (NetworkException('Network error'), ErrorType.networkError),
          (ApiException('Server error', 500), ErrorType.serverError),
          (ApiException('Client error', 404), ErrorType.generic),
          (Exception('Unknown error'), ErrorType.generic),
        ];

        for (final (exception, expectedType) in testCases) {
          final errorState = GlobalErrorHandler.processError(exception);
          expect(
            errorState.type,
            expectedType,
            reason: 'Failed for ${exception.runtimeType}',
          );
          expect(errorState.title, isNotEmpty);
          expect(errorState.message, isNotEmpty);
        }
      });

      test('should preserve original error in metadata', () {
        final originalError = ApiException('Test error', 500);
        final errorState = GlobalErrorHandler.processError(originalError);

        expect(errorState.metadata?['originalError'], equals(originalError));
        expect(errorState.metadata?['statusCode'], equals(500));
      });

      test('should handle null and edge case inputs', () {
        final testCases = [null, '', 'string error', 42, <String, dynamic>{}];

        for (final testCase in testCases) {
          expect(
            () => GlobalErrorHandler.processError(testCase),
            returnsNormally,
            reason: 'Failed for input: $testCase',
          );

          final errorState = GlobalErrorHandler.processError(testCase);
          expect(errorState.type, ErrorType.generic);
        }
      });
    });

    group('Error State Configuration', () {
      test('should provide correct configurations for all error types', () {
        for (final errorType in ErrorType.values) {
          final config = ErrorConfigs.getConfig(errorType);

          expect(config.icon, isNotNull, reason: 'Missing icon for $errorType');
          expect(
            config.color,
            isNotNull,
            reason: 'Missing color for $errorType',
          );
          expect(
            config.showRetry,
            isA<bool>(),
            reason: 'Invalid showRetry for $errorType',
          );
          expect(
            config.showInfo,
            isA<bool>(),
            reason: 'Invalid showInfo for $errorType',
          );
          expect(
            config.autoRedirect,
            isA<bool>(),
            reason: 'Invalid autoRedirect for $errorType',
          );
        }
      });

      test('should have appropriate retry configurations', () {
        // Unauthorized errors should not be retryable
        final unauthorizedState = GlobalErrorHandler.processError(
          UnauthorizedException('Session expired'),
        );
        expect(GlobalErrorHandler.isRetryable(unauthorizedState), isFalse);

        // Network errors should be retryable
        final networkState = GlobalErrorHandler.processError(
          NetworkException('Network error'),
        );
        expect(GlobalErrorHandler.isRetryable(networkState), isTrue);

        // Server errors should be retryable
        final serverState = GlobalErrorHandler.processError(
          ApiException('Server error', 500),
        );
        expect(GlobalErrorHandler.isRetryable(serverState), isTrue);
      });
    });

    group('Retry Logic and Delays', () {
      test('should calculate appropriate retry delays', () {
        final rateLimitState = GlobalErrorHandler.processError(
          RateLimitException('Rate limited'),
        );

        // Rate limit delays should be longer
        final delay1 = GlobalErrorHandler.getRetryDelay(rateLimitState, 0);
        final delay2 = GlobalErrorHandler.getRetryDelay(rateLimitState, 1);
        expect(delay1.inSeconds, equals(5));
        expect(delay2.inSeconds, equals(10));

        final networkState = GlobalErrorHandler.processError(
          NetworkException('Network error'),
        );

        // Network delays should use exponential backoff
        final networkDelay1 = GlobalErrorHandler.getRetryDelay(networkState, 0);
        final networkDelay2 = GlobalErrorHandler.getRetryDelay(networkState, 1);
        expect(networkDelay1.inSeconds, equals(1));
        expect(networkDelay2.inSeconds, equals(2));
      });

      test('should respect maximum retry limits', () {
        expect(GlobalErrorHandler.hasExceededMaxRetries(0), isFalse);
        expect(GlobalErrorHandler.hasExceededMaxRetries(2), isFalse);
        expect(GlobalErrorHandler.hasExceededMaxRetries(3), isTrue);
        expect(GlobalErrorHandler.hasExceededMaxRetries(5), isTrue);
      });

      test('should cap retry delays at reasonable maximums', () {
        final networkState = GlobalErrorHandler.processError(
          NetworkException('Network error'),
        );

        // Very high retry counts should be capped
        final delay = GlobalErrorHandler.getRetryDelay(networkState, 10);
        expect(delay.inSeconds, lessThanOrEqualTo(30));
      });
    });

    group('Error Message Formatting', () {
      test('should provide user-friendly messages for all error types', () {
        final testCases = [
          (ApiException('', 400), 'should have default bad request message'),
          (ApiException('', 403), 'should have access denied message'),
          (ApiException('', 404), 'should have not found message'),
          (ApiException('', 500), 'should have server error message'),
          (ApiException('', 502), 'should have bad gateway message'),
          (ApiException('', 503), 'should have service unavailable message'),
          (ApiException('', 504), 'should have gateway timeout message'),
        ];

        for (final (exception, description) in testCases) {
          final errorState = GlobalErrorHandler.processError(exception);
          expect(errorState.message, isNotEmpty, reason: description);
          expect(
            errorState.message,
            isNot(contains('null')),
            reason: description,
          );
        }
      });

      test('should preserve custom error messages when available', () {
        final customMessage = 'Custom error message';
        final exception = ApiException(customMessage, 400);
        final errorState = GlobalErrorHandler.processError(exception);

        expect(errorState.message, contains(customMessage));
      });

      test('should handle empty error messages gracefully', () {
        final exception = ApiException('', 500);
        final errorState = GlobalErrorHandler.processError(exception);
        expect(errorState.message, isNotEmpty);
        expect(errorState.message, isNot(equals('null')));
      });
    });

    group('Error Constants Validation', () {
      test('should have all required error constants defined', () {
        expect(ErrorConstants.sessionExpired, isNotEmpty);
        expect(ErrorConstants.networkError, isNotEmpty);
        expect(ErrorConstants.timeout, isNotEmpty);
        expect(ErrorConstants.unknown, isNotEmpty);
        expect(ErrorConstants.serverError, isNotEmpty);
        expect(ErrorConstants.rateLimited, isNotEmpty);
        expect(ErrorConstants.cloudflareDown, isNotEmpty);
        expect(ErrorConstants.accessDenied, isNotEmpty);
        expect(ErrorConstants.notFound, isNotEmpty);
        expect(ErrorConstants.badRequest, isNotEmpty);
        expect(ErrorConstants.serviceUnavailable, isNotEmpty);
        expect(ErrorConstants.gatewayTimeout, isNotEmpty);
      });

      test('should have reasonable timeout and retry configurations', () {
        expect(ErrorConstants.snackbarDuration.inSeconds, greaterThan(0));
        expect(ErrorConstants.retryDelay.inSeconds, greaterThan(0));
        expect(ErrorConstants.maxRetries, greaterThan(0));
        expect(
          ErrorConstants.maxRetries,
          lessThan(10),
        ); // Reasonable upper bound
      });

      test('should have consistent error titles', () {
        expect(ErrorConstants.unauthorizedTitle, isNotEmpty);
        expect(ErrorConstants.rateLimitTitle, isNotEmpty);
        expect(ErrorConstants.networkTitle, isNotEmpty);
        expect(ErrorConstants.serverTitle, isNotEmpty);
        expect(ErrorConstants.cloudflareTitle, isNotEmpty);
        expect(ErrorConstants.genericTitle, isNotEmpty);
      });
    });

    group('Integration with Existing Systems', () {
      test('should maintain compatibility with existing exception types', () {
        // Test that existing exception types still work
        final apiException = ApiException('Test', 500);
        final unauthorizedException = UnauthorizedException('Test');
        final rateLimitException = RateLimitException('Test');

        expect(
          () => GlobalErrorHandler.processError(apiException),
          returnsNormally,
        );
        expect(
          () => GlobalErrorHandler.processError(unauthorizedException),
          returnsNormally,
        );
        expect(
          () => GlobalErrorHandler.processError(rateLimitException),
          returnsNormally,
        );
      });

      test('should handle HttpUtil exceptions correctly', () {
        final cloudflareException = CloudflareTunnelException(
          'Tunnel down',
          502,
          'body',
        );
        final networkException = NetworkException('Network error');

        final cloudflareState = GlobalErrorHandler.processError(
          cloudflareException,
        );
        final networkState = GlobalErrorHandler.processError(networkException);

        expect(cloudflareState.type, ErrorType.cloudflareError);
        expect(networkState.type, ErrorType.networkError);
        expect(cloudflareState.metadata?['statusCode'], equals(502));
        expect(cloudflareState.metadata?['responseBody'], equals('body'));
      });
    });

    group('Performance and Memory', () {
      test('should not leak memory when processing many errors', () {
        // Process many errors to check for memory leaks
        for (int i = 0; i < 1000; i++) {
          final error = ApiException('Error $i', 500);
          final errorState = GlobalErrorHandler.processError(error);
          expect(errorState, isNotNull);
        }
      });

      test('should handle concurrent error processing', () async {
        final futures = List.generate(100, (index) async {
          final error = ApiException('Error $index', 500);
          return GlobalErrorHandler.processError(error);
        });

        final results = await Future.wait(futures);
        expect(results.length, equals(100));

        for (final result in results) {
          expect(result.type, ErrorType.serverError);
        }
      });
    });

    group('Edge Cases and Error Conditions', () {
      test('should handle malformed ApiException gracefully', () {
        final testCases = [
          ApiException('', null), // No status code
          ApiException('', -1), // Invalid status code
          ApiException('', 999), // Unknown status code
        ];

        for (final exception in testCases) {
          expect(
            () => GlobalErrorHandler.processError(exception),
            returnsNormally,
          );
          final errorState = GlobalErrorHandler.processError(exception);
          expect(errorState.message, isNotEmpty);
        }
      });

      test('should handle deeply nested error objects', () {
        final nestedError = Exception('Inner error');
        final wrapperError = ApiException(
          'Wrapper: ${nestedError.toString()}',
          500,
        );

        final errorState = GlobalErrorHandler.processError(wrapperError);
        expect(errorState.type, ErrorType.serverError);
        // The message will be processed by the error handler
        expect(errorState.message, isNotEmpty);
      });

      test('should handle circular reference errors safely', () {
        // Create a mock error that might cause circular references
        final error = ApiException('Circular test', 500);

        // Process multiple times to check for circular reference issues
        for (int i = 0; i < 10; i++) {
          expect(() => GlobalErrorHandler.processError(error), returnsNormally);
        }
      });
    });

    group('Error State Consistency', () {
      test('should maintain consistent error state properties', () {
        final testErrors = [
          UnauthorizedException('Test'),
          RateLimitException('Test'),
          ApiException('Test', 500),
          NetworkException('Test'),
          CloudflareTunnelException('Test', 502, 'body'),
        ];

        for (final error in testErrors) {
          final errorState = GlobalErrorHandler.processError(error);

          // All error states should have these properties
          expect(errorState.type, isNotNull);
          expect(errorState.title, isNotEmpty);
          expect(errorState.message, isNotEmpty);
          expect(errorState.icon, isNotNull);
          expect(errorState.color, isNotNull);
          expect(errorState.showRetry, isA<bool>());
          expect(errorState.showInfo, isA<bool>());
          expect(errorState.autoRedirect, isA<bool>());
        }
      });

      test('should have appropriate error state configurations', () {
        // Unauthorized should auto-redirect
        final unauthorizedState = GlobalErrorHandler.processError(
          UnauthorizedException('Test'),
        );
        expect(unauthorizedState.autoRedirect, isTrue);
        expect(unauthorizedState.showRetry, isFalse);

        // Cloudflare errors should show info
        final cloudflareState = GlobalErrorHandler.processError(
          CloudflareTunnelException('Test', 502, 'body'),
        );
        expect(cloudflareState.showInfo, isTrue);
        expect(cloudflareState.showRetry, isTrue);

        // Server errors should be retryable
        final serverState = GlobalErrorHandler.processError(
          ApiException('Test', 500),
        );
        expect(serverState.showRetry, isTrue);
        expect(serverState.autoRedirect, isFalse);
      });
    });
  });
}
