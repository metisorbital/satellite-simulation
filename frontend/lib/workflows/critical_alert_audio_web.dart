import 'dart:js_interop';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:web/web.dart' as web;

/// Small Web Audio adapter for model-prediction critical alerts.
///
/// [arm] must be called from a browser user gesture. Browsers may reject audio
/// otherwise; this class handles rejection quietly so warning presentation is
/// never dependent on sound availability.
class CriticalAlertAudio {
  web.AudioContext? _context;
  Future<web.AudioBuffer>? _asset;
  web.AudioBufferSourceNode? _activeSource;
  final ValueNotifier<bool> _armed = ValueNotifier<bool>(false);
  bool _disposed = false;
  int _playGeneration = 0;

  /// Whether browser audio was enabled by an explicit operator action.
  bool get isArmed => _armed.value && !_disposed;

  /// Observable browser-audio availability for UI affordances.
  ValueListenable<bool> get armed => _armed;

  /// Enables audio after a click or another explicit operator gesture.
  Future<bool> arm() async {
    if (_disposed) return false;
    final context = _context ??= web.AudioContext();
    try {
      if (context.state != 'running') {
        await context.resume().toDart;
      }
      if (_disposed) return false;
      _armed.value = context.state == 'running';
      if (_armed.value) await _loadAsset(context);
    } catch (_) {
      if (!_disposed) _armed.value = false;
    }
    return !_disposed && _armed.value;
  }

  /// Plays the packaged critical-alert MP3 at exactly 50 percent gain.
  Future<bool> play() async {
    if (!isArmed) return false;
    final context = _context;
    if (context == null) return false;
    final generation = ++_playGeneration;
    try {
      final asset = await _loadAsset(context);
      if (_disposed || !isArmed || generation != _playGeneration) return false;
      final source = web.AudioBufferSourceNode(
        context,
        web.AudioBufferSourceOptions(buffer: asset),
      );
      final gain = web.GainNode(context, web.GainOptions(gain: 0.5));
      _stopActiveSource();
      source.connect(gain);
      gain.connect(context.destination);
      source.start();
      _activeSource = source;
      return true;
    } catch (_) {
      if (!_disposed) _armed.value = false;
      return false;
    }
  }

  /// Stops the currently playing critical-alert asset without altering records.
  Future<void> stop() async {
    _playGeneration++;
    _stopActiveSource();
  }

  void _stopActiveSource() {
    final source = _activeSource;
    _activeSource = null;
    if (source == null) return;
    try {
      source.stop();
      source.disconnect();
    } catch (_) {
      // The one-shot source may already have reached the end of the asset.
    }
  }

  Future<web.AudioBuffer> _loadAsset(web.AudioContext context) async {
    final cached = _asset;
    if (cached != null) return cached;
    final loading = _decodeAsset(context);
    _asset = loading;
    try {
      return await loading;
    } catch (_) {
      if (identical(_asset, loading)) _asset = null;
      rethrow;
    }
  }

  Future<web.AudioBuffer> _decodeAsset(web.AudioContext context) async {
    final data = await rootBundle.load(
      'assets/sound_effects/soundreality-code-red-185448.mp3',
    );
    return context.decodeAudioData(data.buffer.toJS).toDart;
  }

  /// Releases the shared browser audio context when the mission page closes.
  Future<void> dispose() async {
    if (_disposed) return;
    _disposed = true;
    _armed.value = false;
    await stop();
    final context = _context;
    _context = null;
    if (context != null) {
      try {
        await context.close().toDart;
      } catch (_) {
        // Closing an already-closed browser context is harmless for the UI.
      }
    }
    _armed.dispose();
  }
}
