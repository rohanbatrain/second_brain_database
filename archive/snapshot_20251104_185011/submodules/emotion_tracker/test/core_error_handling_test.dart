import 'package:flutter_test/flutter_test.dart';
import 'package:emotion_tracker/core/global_error_handler.dart';
import 'package:emotion_tracker/core/error_state.dart';
import 'package:emotion_tracker/core/error_constants.dart';
import 'package:emotion_tracker/providers/api_token_service.dart';
import 'package:emotion_tracker/utils/http_util.dart';

void main() {
  group('GlobalErrorHandler', () {
    test('should process UnauthorizedException correctly', () {
      final error = UnauthorizedException('Session expired');
      final errorState = GlobalErrorHandler.processError(error);

      expect(errorState.type, ErrorType.unauthorized);
      expect(errorState.title, ErrorConstants.unauthorizedTitle);
      expect(errorState.message, ErrorConstants.sessionExpired);
      expect(errorState.autoRedirect, true);
      expect(errorState.showRetry, false);
    });

    test('should process RateLimitException correctly', () {
      final error = RateLimitException('Too many requests');
      final errorState = GlobalErrorHandler.processError(error);

      expect(errorState.type, ErrorType.rateLimited);
      expect(errorState.title, ErrorConstants.rateLimitTitle);
      expect(errorState.message, 'Too many requests');
      expect(errorState.showRetry, true);
    });

    test('should process CloudflareTunnelException correctly', () {
      final error = CloudflareTunnelException(
        'Tunnel down',
        502,
        'Bad Gateway',
      );
      final errorState = GlobalErrorHandler.processError(error);

      expect(errorState.type, ErrorType.cloudflareError);
      expect(errorState.title, ErrorConstants.cloudflareTitle);
      expect(errorState.message, 'Tunnel down');
      expect(errorState.showRetry, true);
      expect(errorState.showInfo, true);
    });

    test('should process NetworkException correctly', () {
      final error = NetworkException('Network error');
      final errorState = GlobalErrorHandler.processError(error);

      expect(errorState.type, ErrorType.networkError);
      expect(errorState.title, ErrorConstants.networkTitle);
      expect(errorState.message, 'Network error');
      expect(errorState.showRetry, true);
    });

    test('should process ApiException with 500 status correctly', () {
      final error = ApiException('Server error', 500);
      final errorState = GlobalErrorHandler.processError(error);

      expect(errorState.type, ErrorType.serverError);
      expect(errorState.title, ErrorConstants.serverTitle);
      expect(errorState.showRetry, true);
      expect(errorState.showInfo, true);
    });

    test('should process ApiException with 404 status correctly', () {
      final error = ApiException('Not found', 404);
      final errorState = GlobalErrorHandler.processError(error);

      expect(errorState.type, ErrorType.generic);
      expect(errorState.message, ErrorConstants.notFound);
    });

    test('should process generic errors correctly', () {
      final error = Exception('Unknown error');
      final errorState = GlobalErrorHandler.processError(error);

      expect(errorState.type, ErrorType.generic);
      expect(errorState.title, ErrorConstants.genericTitle);
      expect(errorState.message, ErrorConstants.unknown);
    });

    test('should determine retryability correctly', () {
      expect(
        GlobalErrorHandler.isRetryable(
          GlobalErrorHandler.processError(UnauthorizedException('test')),
        ),
        false,
      );

      expect(
        GlobalErrorHandler.isRetryable(
          GlobalErrorHandler.processError(RateLimitException('test')),
        ),
        true,
      );

      expect(
        GlobalErrorHandler.isRetryable(
          GlobalErrorHandler.processError(NetworkException('test')),
        ),
        true,
      );
    });

    test('should calculate retry delays correctly', () {
      final rateLimitError = GlobalErrorHandler.processError(
        RateLimitException('test'),
      );
      final networkError = GlobalErrorHandler.processError(
        NetworkException('test'),
      );

      // Rate limit should have longer delay
      final rateLimitDelay = GlobalErrorHandler.getRetryDelay(
        rateLimitError,
        0,
      );
      expect(rateLimitDelay.inSeconds, 5);

      // Network error should use exponential backoff
      final networkDelay = GlobalErrorHandler.getRetryDelay(networkError, 1);
      expect(networkDelay.inSeconds, 2);
    });
  });
}
