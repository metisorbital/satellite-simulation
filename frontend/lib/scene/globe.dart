import 'dart:convert';
import 'dart:js_interop';
import 'package:flutter/material.dart';
import 'package:web/web.dart' as web;
import 'playback.dart';

@JS('metisGlobe.create')
external void _create(web.HTMLElement element, JSFunction select);
@JS('metisGlobe.update')
external void _update(String id, String data);
@JS('metisGlobe.clock')
external void _clock(String id, String epoch, double seconds);
@JS('metisGlobe.command')
external void globeCommand(String id, String action);
@JS('metisGlobe.diagnostics')
external String _diagnostics(String id);
@JS('metisGlobe.destroy')
external void _destroy(String id);

JsonMap globeDiagnostics() =>
    jsonDecode(_diagnostics('metis-earth')) as JsonMap;

/// A rendering-only Cesium platform view, driven by Flutter's committed clock.
class Globe extends StatefulWidget {
  const Globe({
    super.key,
    required this.playback,
    required this.seconds,
    required this.selected,
    required this.trajectory,
    required this.onSelect,
  });
  final CommittedPlayback playback;
  final double? seconds;
  final String selected;
  final JsonMap? trajectory;
  final ValueChanged<String> onSelect;
  @override
  State<Globe> createState() => _GlobeState();
}

class _GlobeState extends State<Globe> {
  bool ready = false;
  String? renderError;
  JsonMap? _lastStatus, _lastTrajectory;
  String? _lastSelected;
  int _lastRevision = -1;
  void update() {
    if (!ready) return;
    if (widget.playback.status != null) {
      _clock(
        'metis-earth',
        widget.playback.status!['epoch_utc'] as String,
        widget.seconds ?? 0,
      );
    }
    renderError =
        (jsonDecode(_diagnostics('metis-earth')) as JsonMap)['error']
            as String?;
    if (_lastRevision == widget.playback.revision &&
        identical(_lastStatus, widget.playback.status) &&
        identical(_lastTrajectory, widget.trajectory) &&
        _lastSelected == widget.selected) {
      return;
    }
    _lastRevision = widget.playback.revision;
    _lastStatus = widget.playback.status;
    _lastTrajectory = widget.trajectory;
    _lastSelected = widget.selected;
    _update(
      'metis-earth',
      jsonEncode({
        'status': widget.playback.status,
        'frames': widget.playback.frames,
        'seconds': widget.seconds,
        'selected': widget.selected,
        'trajectory': widget.trajectory,
      }),
    );
    renderError =
        (jsonDecode(_diagnostics('metis-earth')) as JsonMap)['error']
            as String?;
  }

  @override
  void didUpdateWidget(Globe oldWidget) {
    super.didUpdateWidget(oldWidget);
    update();
  }

  @override
  void dispose() {
    if (ready) _destroy('metis-earth');
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Stack(
    children: [
      HtmlElementView.fromTagName(
        tagName: 'div',
        onElementCreated: (element) {
          final container = element as web.HTMLDivElement;
          container.id = 'metis-earth';
          container.style.width = '100%';
          container.style.height = '100%';
          // A platform view must be attached before Cesium measures its canvas.
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (!mounted) return;
            _create(
              container,
              ((JSString id) => widget.onSelect(id.toDart)).toJS,
            );
            ready = true;
            update();
          });
        },
      ),
      if (renderError != null)
        Positioned(
          bottom: 12,
          left: 12,
          right: 12,
          child: ColoredBox(
            color: const Color(0xff392b24),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Text(renderError!),
            ),
          ),
        ),
    ],
  );
}
