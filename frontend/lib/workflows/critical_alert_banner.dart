import 'dart:async';

import 'package:flutter/material.dart';
import 'package:pointer_interceptor/pointer_interceptor.dart';

import '../api/notifications_generated.dart';
import 'critical_alert_audio.dart';

/// A local, dismissible overlay for unread critical model predictions.
///
/// The widget only presents server-owned notifications. Dismissing it changes
/// no receipt or case state; its [onReview] callback lets the parent open the
/// linked investigation in the existing workspace.
class CriticalAlertBanner extends StatefulWidget {
  /// Creates the mission-control critical alert banner.
  const CriticalAlertBanner({
    super.key,
    required this.notifications,
    required this.audio,
    required this.onReview,
    required this.onApprove,
  });

  /// Notifications from the shared workspace controller.
  final List<OperatorNotification> notifications;

  /// Browser audio adapter armed by a separate user gesture.
  final CriticalAlertAudio audio;

  /// Opens the durable investigation associated with an alert's case id.
  final ValueChanged<String> onReview;

  /// Approves the unchanged saved proposal through the durable case workflow.
  final Future<void> Function(String caseId) onApprove;

  @override
  State<CriticalAlertBanner> createState() => _CriticalAlertBannerState();
}

class _CriticalAlertBannerState extends State<CriticalAlertBanner> {
  final Set<String> _dismissedVersions = <String>{};
  final Set<String> _playedVersions = <String>{};
  final Set<String> _soundPendingVersions = <String>{};
  String? _approvingVersion;
  String? _errorVersion;
  String? _approvalError;

  @override
  void initState() {
    super.initState();
    widget.audio.armed.addListener(_onAudioAvailabilityChanged);
    WidgetsBinding.instance.addPostFrameCallback((_) => _playCandidate());
  }

  @override
  void dispose() {
    widget.audio.armed.removeListener(_onAudioAvailabilityChanged);
    unawaited(widget.audio.stop());
    super.dispose();
  }

  void _onAudioAvailabilityChanged() {
    if (!mounted) return;
    setState(() {});
    _playCandidate();
  }

  @override
  void didUpdateWidget(covariant CriticalAlertBanner oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (_currentAlert == null) unawaited(widget.audio.stop());
    _playCandidate();
  }

  bool _isCriticalModelPrediction(OperatorNotification item) =>
      item.category == 'warning' &&
      item.unread &&
      item.source == 'model_prediction' &&
      item.severity == 'critical';

  String _versionKey(OperatorNotification item) =>
      '${item.key}:${item.version}';

  OperatorNotification? get _currentAlert {
    for (final item in widget.notifications) {
      if (_isCriticalModelPrediction(item) &&
          !_dismissedVersions.contains(_versionKey(item))) {
        return item;
      }
    }
    return null;
  }

  void _playCandidate() {
    if (!mounted) return;
    final candidate = _currentAlert;
    if (candidate == null || !widget.audio.isArmed) return;
    final version = _versionKey(candidate);
    if (_playedVersions.contains(version) ||
        _soundPendingVersions.contains(version)) {
      return;
    }
    _soundPendingVersions.add(version);
    unawaited(_play(version));
  }

  Future<void> _play(String version) async {
    try {
      if (await widget.audio.play() && mounted) _playedVersions.add(version);
    } finally {
      _soundPendingVersions.remove(version);
    }
  }

  void _dismiss(OperatorNotification item) {
    unawaited(widget.audio.stop());
    setState(() => _dismissedVersions.add(_versionKey(item)));
  }

  Future<void> _approve(OperatorNotification item) async {
    if (_approvingVersion != null || item.case_id == null) return;
    final version = _versionKey(item);
    setState(() {
      _approvingVersion = version;
      _approvalError = null;
      _errorVersion = null;
    });
    try {
      await widget.onApprove(item.case_id!);
      if (mounted) _dismiss(item);
    } catch (_) {
      if (mounted) {
        setState(() {
          _errorVersion = version;
          _approvalError =
              'Approval was not confirmed. Review the investigation or retry.';
        });
      }
    } finally {
      if (mounted) setState(() => _approvingVersion = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    final alert = _currentAlert;
    if (alert == null) return const SizedBox.shrink();
    final approving = _approvingVersion != null;
    return PointerInterceptor(
      child: Semantics(
        liveRegion: true,
        label: 'Critical model prediction alert',
        child: Material(
          color: Colors.transparent,
          child: Container(
            width: 390,
            constraints: const BoxConstraints(maxWidth: 390),
            padding: const EdgeInsets.fromLTRB(16, 13, 10, 14),
            decoration: BoxDecoration(
              color: const Color(0xff321018),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: const Color(0xffff5268), width: 1.2),
              boxShadow: const [
                BoxShadow(
                  color: Color(0x99000000),
                  blurRadius: 18,
                  offset: Offset(0, 8),
                ),
              ],
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Padding(
                  padding: EdgeInsets.only(top: 2),
                  child: Icon(
                    Icons.error_rounded,
                    color: Color(0xffff7585),
                    size: 22,
                  ),
                ),
                const SizedBox(width: 11),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'MODEL ALERT · CRITICAL',
                        style: TextStyle(
                          color: Color(0xffffa9b2),
                          fontSize: 10,
                          fontWeight: FontWeight.w800,
                          letterSpacing: 1.05,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        alert.title,
                        style: const TextStyle(
                          color: Color(0xfffff0f2),
                          fontSize: 15,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 5),
                      Text(
                        alert.summary,
                        maxLines: 3,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: Color(0xffffc8cf),
                          fontSize: 12,
                          height: 1.35,
                        ),
                      ),
                      const SizedBox(height: 12),
                      const Text(
                        'Approve to reschedule the routine batch and protect '
                        'capture at T+90 and downlink at T+100.',
                        style: TextStyle(
                          color: Color(0xffffc8cf),
                          fontSize: 11,
                          height: 1.35,
                        ),
                      ),
                      if (_errorVersion == _versionKey(alert)) ...[
                        const SizedBox(height: 8),
                        Text(
                          _approvalError!,
                          style: const TextStyle(
                            color: Color(0xfffff0f2),
                            fontSize: 12,
                          ),
                        ),
                      ],
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 6,
                        runSpacing: 4,
                        crossAxisAlignment: WrapCrossAlignment.center,
                        children: [
                          TextButton(
                            onPressed: alert.case_id == null || approving
                                ? null
                                : () {
                                    widget.onReview(alert.case_id!);
                                    _dismiss(alert);
                                  },
                            style: TextButton.styleFrom(
                              foregroundColor: const Color(0xffffe2e6),
                              padding: const EdgeInsets.symmetric(
                                horizontal: 10,
                                vertical: 7,
                              ),
                            ),
                            child: const Text('Review'),
                          ),
                          FilledButton(
                            onPressed: alert.case_id == null || approving
                                ? null
                                : () => unawaited(_approve(alert)),
                            style: FilledButton.styleFrom(
                              backgroundColor: const Color(0xffc83049),
                              foregroundColor: Colors.white,
                            ),
                            child: Text(approving ? 'Approving…' : 'Approve'),
                          ),
                          if (!widget.audio.isArmed)
                            Padding(
                              padding: EdgeInsets.only(left: 4),
                              child: IconButton(
                                tooltip: 'Enable alert sound',
                                onPressed: () => unawaited(widget.audio.arm()),
                                icon: const Icon(
                                  Icons.volume_off_outlined,
                                  color: Color(0xffe8a4ad),
                                  size: 16,
                                ),
                              ),
                            ),
                        ],
                      ),
                    ],
                  ),
                ),
                IconButton(
                  tooltip: 'Dismiss alert display',
                  onPressed: approving ? null : () => _dismiss(alert),
                  icon: const Icon(
                    Icons.close_rounded,
                    color: Color(0xffffb3bc),
                    size: 18,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
