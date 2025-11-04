# Project Overview

This is a Flutter project named `emotion_tracker`. Based on the file structure and dependencies, it appears to be a mobile application for tracking emotions.

The project uses the following technologies:

*   **Framework:** Flutter
*   **State Management:** `flutter_riverpod`
*   **Networking:** `http` and `dio`
*   **JSON Serialization:** `json_serializable`
*   **Advertising:** `google_mobile_ads`

The application has screens for:

*   Splash
*   Authentication (login, verify email, forgot password)
*   Home
*   Settings
*   Shop
*   Currency

# Building and Running

To build and run this project, you will need to have the Flutter SDK installed.

1.  **Install dependencies:**
    ```bash
    flutter pub get
    ```

2.  **Run the app:**
    ```bash
    flutter run
    ```

# Development Conventions

*   **State Management:** The project uses `flutter_riverpod` for state management. Providers are defined in the `lib/providers` directory.
*   **Routing:** The project uses a custom routing solution with page transitions. Routes are defined in `lib/main.dart`.
*   **Code Generation:** The project uses `json_serializable` for JSON serialization. To generate the serialization code, run the following command:
    ```bash
    flutter pub run build_runner build
    ```
*   **Linting:** The project uses `flutter_lints` for linting. The linting rules are defined in the `analysis_options.yaml` file.
