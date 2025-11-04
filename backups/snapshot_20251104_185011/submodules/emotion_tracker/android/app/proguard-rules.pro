# Add project specific ProGuard rules here.
# You can control the set of applied configuration files using the
# proguardFiles setting in build.gradle.
#
# For more details, see
#   http://developer.android.com/guide/developing/tools/proguard.html

# If your project uses WebView with JS, uncomment the following
# and specify the fully qualified class name to the JavaScript interface
# class:
#-keepclassmembers class fqcn.of.javascript.interface.for.webview {
#   public *;
#}

# Uncomment this to preserve the line number information for
# debugging stack traces.
#-keepattributes SourceFile,LineNumberTable

# If you keep the line number information, uncomment this to
# hide the original source file name.
#-renamesourcefileattribute SourceFile

# Keep javax.imageio classes to fix R8 compilation issues
-keep class javax.imageio.** { *; }
-keep class javax.imageio.spi.** { *; }
-dontwarn javax.imageio.**

# Keep classes that might be referenced by image processing libraries
-keep class com.github.jaiimageio.** { *; }
-dontwarn com.github.jaiimageio.**

# Keep all classes related to image processing
-keep class java.awt.** { *; }
-dontwarn java.awt.**

# Keep QR code related classes
-keep class com.google.zxing.** { *; }
-dontwarn com.google.zxing.**

# Flutter specific rules
-keep class io.flutter.app.** { *; }
-keep class io.flutter.plugin.**  { *; }
-keep class io.flutter.util.**  { *; }
-keep class io.flutter.view.**  { *; }
-keep class io.flutter.**  { *; }
-keep class io.flutter.plugins.**  { *; }

# Keep AdMob classes
-keep class com.google.android.gms.** { *; }
-dontwarn com.google.android.gms.**

# Appended to address R8 missing classes reported during release builds
# Source: build/app/outputs/mapping/release/missing_rules.txt
-dontwarn javax.imageio.spi.ImageInputStreamSpi
-dontwarn javax.imageio.spi.ImageOutputStreamSpi
-dontwarn javax.imageio.spi.ImageReaderSpi
-dontwarn javax.imageio.spi.ImageWriterSpi

# Suppress missing Play Core (deferred components / splitinstall) classes reported by R8
-dontwarn com.google.android.play.core.**
-dontwarn com.google.android.play.core.splitcompat.**
-dontwarn com.google.android.play.core.splitinstall.**
-dontwarn com.google.android.play.core.tasks.**
