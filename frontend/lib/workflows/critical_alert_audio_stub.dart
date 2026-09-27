import 'package:flutter/foundation.dart';

/// Browser sound adapter for the critical-alert banner.
///
/// Native builds do not provide browser Web Audio, so the adapter remains
/// intentionally unavailable while preserving the overlay's behavior.
class CriticalAlertAudio {
  /// Returns an adapter that cannot emit browser audio on this platform.
  CriticalAlertAudio();

  final ValueNotifier<bool> _armed = ValueNotifier<bool>(false);

  /// Observable browser-audio availability for UI affordances.
  ValueListenable<bool> get armed => _armed;

  /// Whether a user gesture has enabled alert audio.
  bool get isArmed => _armed.value;

  /// Attempts to enable browser audio after an explicit user gesture.
  Future<bool> arm() async => false;

  /// Attempts to play a critical alert tone.
  Future<bool> play() async => false;

  /// Stops the currently playing critical alert, if any.
  Future<void> stop() async {}

  /// Releases audio resources.
  Future<void> dispose() async => _armed.dispose();
}
