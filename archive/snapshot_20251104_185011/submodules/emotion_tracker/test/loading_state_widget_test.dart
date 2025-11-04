import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:emotion_tracker/widgets/loading_state_widget.dart';

void main() {
  group('LoadingStateWidget', () {
    testWidgets('displays default loading indicator with message', (
      WidgetTester tester,
    ) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(body: LoadingStateWidget(message: 'Loading data...')),
        ),
      );

      // Verify loading indicator is present
      expect(find.byType(CircularProgressIndicator), findsOneWidget);

      // Verify message is displayed
      expect(find.text('Loading data...'), findsOneWidget);
    });

    testWidgets('displays compact loading indicator', (
      WidgetTester tester,
    ) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: LoadingStateWidget(message: 'Loading...', compact: true),
          ),
        ),
      );

      // Verify loading indicator is present
      expect(find.byType(CircularProgressIndicator), findsOneWidget);

      // Verify message is displayed
      expect(find.text('Loading...'), findsOneWidget);

      // Verify compact styling by checking the SizedBox dimensions
      final sizedBox = tester.widget<SizedBox>(find.byType(SizedBox).first);
      expect(sizedBox.width, equals(24.0));
      expect(sizedBox.height, equals(24.0));
    });

    testWidgets('hides message when showMessage is false', (
      WidgetTester tester,
    ) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: LoadingStateWidget(message: 'Loading...', showMessage: false),
          ),
        ),
      );

      // Verify loading indicator is present
      expect(find.byType(CircularProgressIndicator), findsOneWidget);

      // Verify message is not displayed
      expect(find.text('Loading...'), findsNothing);
    });

    testWidgets('uses custom color for loading indicator', (
      WidgetTester tester,
    ) async {
      const customColor = Colors.red;

      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: LoadingStateWidget(message: 'Loading...', color: customColor),
          ),
        ),
      );

      // Verify loading indicator uses custom color
      final progressIndicator = tester.widget<CircularProgressIndicator>(
        find.byType(CircularProgressIndicator),
      );
      expect(progressIndicator.color, equals(customColor));
    });

    testWidgets('uses custom size for loading indicator', (
      WidgetTester tester,
    ) async {
      const customSize = 40.0;

      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: LoadingStateWidget(message: 'Loading...', size: customSize),
          ),
        ),
      );

      // Verify loading indicator uses custom size
      final sizedBox = tester.widget<SizedBox>(find.byType(SizedBox).first);
      expect(sizedBox.width, equals(customSize));
      expect(sizedBox.height, equals(customSize));
    });

    testWidgets('displays custom indicator when provided', (
      WidgetTester tester,
    ) async {
      const customIndicator = Icon(Icons.hourglass_empty);

      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: LoadingStateWidget(
              message: 'Loading...',
              customIndicator: customIndicator,
            ),
          ),
        ),
      );

      // Verify custom indicator is displayed instead of CircularProgressIndicator
      expect(find.byType(CircularProgressIndicator), findsNothing);
      expect(find.byIcon(Icons.hourglass_empty), findsOneWidget);
    });

    group('Factory Constructors', () {
      testWidgets('refresh factory creates appropriate widget', (
        WidgetTester tester,
      ) async {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: LoadingStateWidget.refresh(message: 'Refreshing...'),
            ),
          ),
        );

        // Verify loading indicator is present
        expect(find.byType(CircularProgressIndicator), findsOneWidget);

        // Verify message is not shown (RefreshIndicator shows its own)
        expect(find.text('Refreshing...'), findsNothing);

        // Verify compact styling
        final sizedBox = tester.widget<SizedBox>(find.byType(SizedBox).first);
        expect(sizedBox.width, equals(24.0));
      });

      testWidgets('inline factory creates appropriate widget', (
        WidgetTester tester,
      ) async {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: LoadingStateWidget.inline(
                message: 'Loading inline...',
                size: 20.0,
              ),
            ),
          ),
        );

        // Verify loading indicator is present
        expect(find.byType(CircularProgressIndicator), findsOneWidget);

        // Verify message is shown
        expect(find.text('Loading inline...'), findsOneWidget);

        // Verify custom size
        final sizedBox = tester.widget<SizedBox>(find.byType(SizedBox).first);
        expect(sizedBox.width, equals(20.0));
      });

      testWidgets('fullScreen factory creates appropriate widget', (
        WidgetTester tester,
      ) async {
        await tester.pumpWidget(
          MaterialApp(home: Scaffold(body: LoadingStateWidget.fullScreen())),
        );

        // Verify loading indicator is present
        expect(find.byType(CircularProgressIndicator), findsOneWidget);

        // Verify default message is shown
        expect(find.text('Loading...'), findsOneWidget);

        // Verify full-screen styling (non-compact)
        final sizedBox = tester.widget<SizedBox>(find.byType(SizedBox).first);
        expect(sizedBox.width, equals(32.0));
      });
    });

    group('LoadingStateHelper', () {
      testWidgets('createRefreshIndicator creates RefreshIndicator', (
        WidgetTester tester,
      ) async {
        bool refreshCalled = false;

        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: LoadingStateHelper.createRefreshIndicator(
                child: const Text('Content'),
                onRefresh: () async {
                  refreshCalled = true;
                },
              ),
            ),
          ),
        );

        // Verify RefreshIndicator is present
        expect(find.byType(RefreshIndicator), findsOneWidget);
        expect(find.text('Content'), findsOneWidget);
      });

      testWidgets('createLoadingOverlay shows overlay when loading', (
        WidgetTester tester,
      ) async {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: LoadingStateHelper.createLoadingOverlay(
                child: const Text('Content'),
                isLoading: true,
                loadingMessage: 'Processing...',
              ),
            ),
          ),
        );

        // Verify content is present
        expect(find.text('Content'), findsOneWidget);

        // Verify loading overlay is present
        expect(find.byType(LoadingStateWidget), findsOneWidget);
        expect(find.text('Processing...'), findsOneWidget);

        // Verify overlay container is present
        expect(find.byType(Container), findsOneWidget);
      });

      testWidgets('createLoadingOverlay hides overlay when not loading', (
        WidgetTester tester,
      ) async {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: LoadingStateHelper.createLoadingOverlay(
                child: const Text('Content'),
                isLoading: false,
                loadingMessage: 'Processing...',
              ),
            ),
          ),
        );

        // Verify content is present
        expect(find.text('Content'), findsOneWidget);

        // Verify loading overlay is not present
        expect(find.byType(LoadingStateWidget), findsNothing);
        expect(find.text('Processing...'), findsNothing);
      });

      testWidgets('createLoadingButton shows loading state', (
        WidgetTester tester,
      ) async {
        bool buttonPressed = false;

        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: LoadingStateHelper.createLoadingButton(
                text: 'Submit',
                onPressed: () {
                  buttonPressed = true;
                },
                isLoading: true,
                loadingText: 'Submitting...',
              ),
            ),
          ),
        );

        // Verify loading state is shown
        expect(find.byType(CircularProgressIndicator), findsOneWidget);
        expect(find.text('Submitting...'), findsOneWidget);
        expect(find.text('Submit'), findsNothing);

        // Verify button is disabled during loading
        final button = tester.widget<ElevatedButton>(
          find.byType(ElevatedButton),
        );
        expect(button.onPressed, isNull);
      });

      testWidgets('createLoadingButton shows normal state', (
        WidgetTester tester,
      ) async {
        bool buttonPressed = false;

        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: LoadingStateHelper.createLoadingButton(
                text: 'Submit',
                onPressed: () {
                  buttonPressed = true;
                },
                isLoading: false,
                icon: Icons.send,
              ),
            ),
          ),
        );

        // Verify normal state is shown
        expect(find.byType(CircularProgressIndicator), findsNothing);
        expect(find.text('Submit'), findsOneWidget);
        expect(find.byIcon(Icons.send), findsOneWidget);

        // Verify button is enabled
        final button = tester.widget<ElevatedButton>(
          find.byType(ElevatedButton),
        );
        expect(button.onPressed, isNotNull);

        // Test button press
        await tester.tap(find.byType(ElevatedButton));
        expect(buttonPressed, isTrue);
      });
    });

    group('LoadingStateTransitions Extension', () {
      testWidgets('withLoadingTransition shows loading state', (
        WidgetTester tester,
      ) async {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: const Text('Content').withLoadingTransition(
                isLoading: true,
                loadingMessage: 'Loading content...',
              ),
            ),
          ),
        );

        // Verify loading state is shown
        expect(find.byType(LoadingStateWidget), findsOneWidget);
        expect(find.text('Loading content...'), findsOneWidget);
        expect(find.text('Content'), findsNothing);
      });

      testWidgets('withLoadingTransition shows content when not loading', (
        WidgetTester tester,
      ) async {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: const Text('Content').withLoadingTransition(
                isLoading: false,
                loadingMessage: 'Loading content...',
              ),
            ),
          ),
        );

        // Verify content is shown
        expect(find.text('Content'), findsOneWidget);
        expect(find.byType(LoadingStateWidget), findsNothing);
        expect(find.text('Loading content...'), findsNothing);
      });
    });

    testWidgets('smooth transitions work correctly', (
      WidgetTester tester,
    ) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: LoadingStateWidget(
              message: 'Loading...',
              transitionDuration: Duration(milliseconds: 100),
            ),
          ),
        ),
      );

      // Verify AnimatedOpacity is present for smooth transitions
      expect(find.byType(AnimatedOpacity), findsOneWidget);

      // Verify AnimatedSwitcher is present for message transitions
      expect(find.byType(AnimatedSwitcher), findsOneWidget);
    });
  });
}
