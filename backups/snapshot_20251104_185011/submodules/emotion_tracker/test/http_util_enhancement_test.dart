import 'package:flutter_test/flutter_test.dart';
import 'package:emotion_tracker/utils/http_util.dart';
import 'package:emotion_tracker/core/error_state.dart';
import 'package:emotion_tracker/providers/api_token_service.dart';

void main() {
  group('HttpUtil Enhancement Tests', () {
    test('processHttpError should handle CloudflareTunnelException', () {
      final error = CloudflareTunnelException(
        'Tunnel is down',
        502,
        'Bad Gateway',
      );

      final errorState = HttpUtil.processHttpError(error);

      expect(errorState.type, ErrorType.cloudflareError);
      expect(errorState.message, 'Tunnel is down');
      expect(errorState.showRetry, true);
      expect(errorState.showInfo, true);
    });

    test('processHttpError should handle NetworkException', () {
      final error = NetworkException('Network connection failed');

      final errorState = HttpUtil.processHttpError(error);

      expect(errorState.type, ErrorType.networkError);
      expect(errorState.message, 'Network connection failed');
      expect(errorState.showRetry, true);
      expect(errorState.showInfo, false);
    });

    test('processHttpError should handle UnauthorizedException', () {
      final error = UnauthorizedException('Session expired');

      final errorState = HttpUtil.processHttpError(error);

      expect(errorState.type, ErrorType.unauthorized);
      expect(errorState.showRetry, false);
      expect(errorState.autoRedirect, true);
    });

    test('processHttpError should handle RateLimitException', () {
      final error = RateLimitException('Too many requests');

      final errorState = HttpUtil.processHttpError(error);

      expect(errorState.type, ErrorType.rateLimited);
      expect(errorState.message, 'Too many requests');
      expect(errorState.showRetry, true);
    });

    test('processHttpError should handle ApiException', () {
      final error = ApiException('Server error', 500);

      final errorState = HttpUtil.processHttpError(error);

      expect(errorState.type, ErrorType.serverError);
      expect(errorState.showRetry, true);
      expect(errorState.showInfo, true);
    });

    test('isHttpErrorRetryable should work correctly', () {
      final cloudflareError = CloudflareTunnelException('Tunnel down', 502, '');
      final networkError = NetworkException('Network failed');
      final unauthorizedError = UnauthorizedException('Session expired');

      expect(HttpUtil.isHttpErrorRetryable(cloudflareError), true);
      expect(HttpUtil.isHttpErrorRetryable(networkError), true);
      expect(HttpUtil.isHttpErrorRetryable(unauthorizedError), false);
    });

    test('getHttpErrorRetryDelay should return appropriate delays', () {
      final networkError = NetworkException('Network failed');
      final rateLimitError = RateLimitException('Rate limited');

      final networkDelay = HttpUtil.getHttpErrorRetryDelay(networkError, 1);
      final rateLimitDelay = HttpUtil.getHttpErrorRetryDelay(rateLimitError, 1);

      expect(networkDelay.inSeconds, 2); // Exponential backoff: 2^1 = 2
      expect(rateLimitDelay.inSeconds, 10); // Rate limit: (1+1)*5 = 10
    });

    test('processHttpError should handle generic errors', () {
      final error = Exception('Unknown error');

      final errorState = HttpUtil.processHttpError(error);

      expect(errorState.type, ErrorType.generic);
      expect(errorState.showRetry, true);
    });
  });
}
