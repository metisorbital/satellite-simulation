/// Browser storage adapter selected by the active Dart platform.
library;

import 'layout_storage_stub.dart'
    if (dart.library.js_interop) 'layout_storage_web.dart'
    as platform;

/// Reads the stored telemetry layout JSON, if available.
String? readTelemetryLayout(String key) => platform.readTelemetryLayout(key);

/// Persists the telemetry layout JSON when browser storage is available.
void writeTelemetryLayout(String key, String value) =>
    platform.writeTelemetryLayout(key, value);
