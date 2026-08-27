class AppConfig {
  static const apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    // The release APK must talk to the same PostgreSQL-backed API as the web UI.
    // Local development can still override this with --dart-define API_BASE_URL=...
    defaultValue: 'https://sbcnav.onrender.com',
  );

  static const requestTimeout = Duration(seconds: 25);
  static const pageSize = 500;
}
