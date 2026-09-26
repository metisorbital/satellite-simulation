import 'package:flutter/material.dart';
import 'package:pointer_interceptor/pointer_interceptor.dart';

import '../api/mission.dart';
import 'shift_log_page.dart';
export 'shift_log_page.dart';

/// Backward-compatible modal presentation of the durable shift log.
///
/// New navigation should use [ShiftLogPage]. This wrapper keeps existing
/// callers and browser modal behavior working while sharing the same store.
class ShiftLogDialog extends StatelessWidget {
  /// Creates a modal shift log for [runId].
  const ShiftLogDialog({
    super.key,
    required this.mission,
    required this.runId,
    required this.operatorName,
  });

  /// Authenticated mission state and durable shift-log API.
  final Mission mission;

  /// The run whose records are shown.
  final String runId;

  /// Display name for the active operator.
  final String operatorName;

  @override
  Widget build(BuildContext context) => PointerInterceptor(
    child: Dialog(
      insetPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 18),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 820, maxHeight: 900),
        child: ShiftLogPage(
          mission: mission,
          runId: runId,
          operatorName: operatorName,
          embedded: true,
          onClose: () => Navigator.of(context).pop(),
        ),
      ),
    ),
  );
}
