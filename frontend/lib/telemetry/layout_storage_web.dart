import 'package:web/web.dart' as web;

/// Reads a saved layout from browser local storage.
String? readTelemetryLayout(String key) {
  try {
    return web.window.localStorage.getItem(key);
  } catch (_) {
    return null;
  }
}

/// Writes a saved layout to browser local storage.
void writeTelemetryLayout(String key, String value) {
  try {
    web.window.localStorage.setItem(key, value);
  } catch (_) {
    // Storage can be disabled or unavailable in restricted browser contexts.
  }
}
