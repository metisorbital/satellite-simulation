/// Storage adapter used when browser local storage is unavailable.
///
/// This keeps the telemetry layout usable in VM based tools and tests without
/// introducing a platform dependency into the layout model.
String? readTelemetryLayout(String key) => null;

/// Does nothing when browser local storage is unavailable.
void writeTelemetryLayout(String key, String value) {}
