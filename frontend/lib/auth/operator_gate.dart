import 'package:flutter/material.dart';

import '../scene/playback.dart';
import 'operator_session.dart';

typedef OperatorMissionBuilder =
    Widget Function(
      BuildContext context,
      JsonMap bootstrap,
      Future<void> Function(String login, String csrfToken) switchOperator,
      VoidCallback sessionExpired,
    );

/// Opens the default operator and isolates each operator's mission workspace.
class OperatorGate extends StatefulWidget {
  const OperatorGate({super.key, required this.missionBuilder, this.session});

  final OperatorMissionBuilder missionBuilder;
  final OperatorSession? session;

  @override
  State<OperatorGate> createState() => _OperatorGateState();
}

class _OperatorGateState extends State<OperatorGate> {
  late final OperatorSession session;

  @override
  void initState() {
    super.initState();
    session = widget.session ?? OperatorSession();
    session.addListener(_refresh);
    session.restore();
  }

  void _refresh() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    session.removeListener(_refresh);
    session.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final bootstrap = session.bootstrap;
    if (bootstrap != null) {
      return KeyedSubtree(
        key: ValueKey(
          "${(bootstrap['operator'] as Map)['user_id']}:${bootstrap['csrf_token']}",
        ),
        child: widget.missionBuilder(
          context,
          bootstrap,
          (login, token) => session.switchOperator(login, csrfToken: token),
          session.expire,
        ),
      );
    }
    if (session.restoring || session.busy) {
      return const Scaffold(
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              CircularProgressIndicator(),
              SizedBox(height: 20),
              Text('Opening operator workspace…'),
            ],
          ),
        ),
      );
    }
    return Scaffold(
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.cloud_off_outlined, size: 38),
              const SizedBox(height: 16),
              Text(
                session.error ?? 'Could not open the operator workspace.',
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 20),
              FilledButton.icon(
                onPressed: session.retry,
                icon: const Icon(Icons.refresh_rounded),
                label: const Text('Retry'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
