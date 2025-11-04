import 'package:flutter_test/flutter_test.dart';
import 'package:emotion_tracker/providers/api_token_service.dart';

void main() {
  group('API Token Service Error Handling', () {
    group('Error Message Formatting', () {
      test('should format ApiException with status code', () {
        final exception = ApiException('Test error', 404);
        expect(exception.toString(), 'ApiException: Test error (Status code: 404)');
      });

      test('should format ApiException without status code', () {
        final exception = ApiException('Test error');
        expect(exception.toString(), 'ApiException: Test error');
      });

      test('should format UnauthorizedException', () {
        final exception = UnauthorizedException('Session expired');
        expect(exception.toString(), 'Session expired');
      });

      test('should format RateLimitException', () {
        final exception = RateLimitException('Too many requests');
        expect(exception.toString(), 'Too many requests');
      });
    });

    group('Constants Validation', () {
      test('should have all required error message constants', () {
        expect(ApiTokenConstants.errorSessionExpired, isNotEmpty);
        expect(ApiTokenConstants.errorNetwork, isNotEmpty);
        expect(ApiTokenConstants.errorTimeout, isNotEmpty);
        expect(ApiTokenConstants.errorUnknown, isNotEmpty);
        expect(ApiTokenConstants.errorTokenNotFound, isNotEmpty);
        expect(ApiTokenConstants.errorInvalidDescription, isNotEmpty);
      });
    });
  });
}