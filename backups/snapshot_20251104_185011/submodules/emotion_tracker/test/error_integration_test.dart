import 'package:flutter_test/flutter_test.dart';
import 'package:emotion_tracker/core/global_error_handler.dart';
import 'package:emotion_tracker/core/error_state.dart';
import 'package:emotion_tracker/core/error_constants.dart';
import 'package:emotion_tracker/providers/api_token_service.dart';
import 'package:emotion_tracker/utils/http_util.dart';

void main() {
  group('Error Integration Tests', () {
    test(
      'should handle all existing exception types from api_token_service',
      () {
        // Test UnauthorizedException
        final unauthorizedError = UnauthorizedException('Session expired');
        final unauthorizedState = GlobalErrorHandler.processError(
          unauthorizedError,
        );
        expect(unauthorizedState.type, ErrorType.unauthorized);
        expect(unauthorizedState.autoRedirect, true);

        // Test RateLimitException
        final rateLimitError = RateLimitException('Too many requests');
        final rateLimitState = GlobalErrorHandler.processError(rateLimitError);
        expect(rateLimitState.type, ErrorType.rateLimited);
        expect(rateLimitState.showRetry, true);

        // Test ApiException with different status codes
        final apiError404 = ApiException('Not found', 404);
        final apiState404 = GlobalErrorHandler.processError(apiError404);
        expect(apiState404.type, ErrorType.generic);
        expect(apiState404.message, ErrorConstants.notFound);

        final apiError500 = ApiException('Server error', 500);
        final apiState500 = GlobalErrorHandler.processError(apiError500);
        expect(apiState500.type, ErrorType.serverError);
        expect(apiState500.showInfo, true);
      },
    );

    test('should handle all existing exception types from http_util', () {
      // Test CloudflareTunnelException
      final cloudflareError = CloudflareTunnelException(
        'Tunnel down',
        502,
        'Bad Gateway',
      );
      final cloudflareState = GlobalErrorHandler.processError(cloudflareError);
      expect(cloudflareState.type, ErrorType.cloudflareError);
      expect(cloudflareState.showRetry, true);
      expect(cloudflareState.showInfo, true);

      // Test NetworkException
      final networkError = NetworkException('Connection failed');
      final networkState = GlobalErrorHandler.processError(networkError);
      expect(networkState.type, ErrorType.networkError);
      expect(networkState.showRetry, true);
    });

    test(
      'should maintain backward compatibility with existing error constants',
      () {
        // Verify that our new constants match the existing ones from ApiTokenConstants
        expect(
          ErrorConstants.sessionExpired,
          'Your session has expired. Please log in again.',
        );
        expect(
          ErrorConstants.networkError,
          'Network error: Please check your connection.',
        );
        expect(
          ErrorConstants.timeout,
          'The request timed out. Please try again.',
        );
        expect(ErrorConstants.unknown, 'An unknown error occurred.');
        expect(
          ErrorConstants.tokenNotFound,
          'Token not found or already revoked.',
        );
        expect(
          ErrorConstants.invalidDescription,
          'Token description is required and must be valid.',
        );
      },
    );

    test('should provide appropriate error configurations for each type', () {
      final configs = ErrorConfigs.configs;

      // Verify all error types have configurations
      expect(configs.containsKey(ErrorType.unauthorized), true);
      expect(configs.containsKey(ErrorType.rateLimited), true);
      expect(configs.containsKey(ErrorType.networkError), true);
      expect(configs.containsKey(ErrorType.serverError), true);
      expect(configs.containsKey(ErrorType.cloudflareError), true);
      expect(configs.containsKey(ErrorType.generic), true);

      // Verify specific configurations
      expect(configs[ErrorType.unauthorized]!.autoRedirect, true);
      expect(configs[ErrorType.unauthorized]!.showRetry, false);
      expect(configs[ErrorType.serverError]!.showInfo, true);
      expect(configs[ErrorType.cloudflareError]!.showInfo, true);
    });

    test('should handle error metadata correctly', () {
      final apiError = ApiException('Server error', 500);
      final errorState = GlobalErrorHandler.processError(apiError);

      expect(errorState.metadata, isNotNull);
      expect(errorState.metadata!['originalError'], apiError);
      expect(errorState.metadata!['statusCode'], 500);
    });

    test('should calculate retry delays appropriately', () {
      final rateLimitError = GlobalErrorHandler.processError(
        RateLimitException('test'),
      );
      final networkError = GlobalErrorHandler.processError(
        NetworkException('test'),
      );

      // Rate limit errors should have longer delays
      final rateLimitDelay = GlobalErrorHandler.getRetryDelay(
        rateLimitError,
        0,
      );
      expect(rateLimitDelay.inSeconds, 5);

      // Network errors should use exponential backoff
      final networkDelay1 = GlobalErrorHandler.getRetryDelay(networkError, 0);
      final networkDelay2 = GlobalErrorHandler.getRetryDelay(networkError, 1);
      expect(networkDelay1.inSeconds, 1);
      expect(networkDelay2.inSeconds, 2);
    });

    test('should respect max retry limits', () {
      expect(GlobalErrorHandler.hasExceededMaxRetries(0), false);
      expect(GlobalErrorHandler.hasExceededMaxRetries(2), false);
      expect(GlobalErrorHandler.hasExceededMaxRetries(3), true);
      expect(GlobalErrorHandler.hasExceededMaxRetries(5), true);
    });
  });
}
