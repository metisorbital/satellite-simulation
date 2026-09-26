import 'package:flutter/material.dart';

const _background = Color(0xff070d15);
const _sidebar = Color(0xff0a111a);
const _line = Color(0xff202a36);
const _mint = Color(0xff95cfbc);
const _gold = Color(0xffc7b985);
const _text = Color(0xffd4dfe8);
const _muted = Color(0xff94a4b7);
const _quiet = Color(0xff8091a5);

/// Destinations share one mission session and committed simulation clock.
enum MissionView {
  overview('Overview', Icons.grid_view_rounded),
  telemetry('Telemetry', Icons.show_chart_rounded),
  warnings('Early warnings', Icons.warning_amber_rounded),
  investigations('Investigations', Icons.search_rounded),
  planning('Mission planning', Icons.event_note_outlined),
  history('Case history', Icons.history_rounded),
  shiftLog('Shift log', Icons.menu_book_outlined);

  const MissionView(this.title, this.icon);
  final String title;
  final IconData icon;

  bool get isCase =>
      this == warnings || this == investigations || this == history;
}

/// The navigation and operator rail for the Metis mission control shell.
///
/// The parent owns the rail width. Use [compact] when that width is reduced
/// to an icon rail; all compact controls retain labels through tooltips and
/// semantics. Navigation callbacks are deliberately supplied by the parent
/// so this shell does not own mission state or routing.
class MissionSidebar extends StatelessWidget {
  /// Creates the mission navigation rail.
  const MissionSidebar({
    super.key,
    required this.view,
    required this.onNavigate,
    required this.onSettings,
    required this.onInfo,
    required this.onLogout,
    required this.operatorRecordsEnabled,
    required this.operatorName,
    required this.operatorLogin,
    required this.busy,
    required this.connected,
    required this.runLabel,
    this.compact = false,
  });

  final MissionView view;
  final ValueChanged<MissionView> onNavigate;

  /// Invoked when the Settings control is selected.
  final VoidCallback onSettings;

  /// Invoked when the mission model and credits control is selected.
  final VoidCallback onInfo;

  /// Invoked by the operator popup's demo logout action.
  final VoidCallback onLogout;

  /// Private records require a named operator session.
  final bool operatorRecordsEnabled;

  /// The operator's display name.
  final String operatorName;

  /// The operator's login or account identifier.
  final String operatorLogin;

  /// Whether the mission is currently performing a session operation.
  final bool busy;

  /// Whether the telemetry stream is connected.
  final bool connected;

  /// Human-readable label for the current simulated run.
  final String runLabel;

  /// Whether to render the icon-only rail variant.
  final bool compact;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(
        color: _sidebar,
        border: Border(right: BorderSide(color: _line)),
      ),
      child: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) => SingleChildScrollView(
            primary: false,
            child: ConstrainedBox(
              constraints: BoxConstraints(minHeight: constraints.maxHeight),
              child: IntrinsicHeight(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    _Brand(compact: compact),
                    if (!compact)
                      const Padding(
                        padding: EdgeInsets.fromLTRB(16, 2, 16, 10),
                        child: Text(
                          'MISSION OPERATIONS',
                          style: TextStyle(
                            color: _muted,
                            fontSize: 9,
                            fontWeight: FontWeight.w700,
                            letterSpacing: 1.4,
                          ),
                        ),
                      )
                    else
                      const SizedBox(height: 10),
                    for (final destination in MissionView.values)
                      _NavigationItem(
                        icon: destination.icon,
                        label: destination.title,
                        selected: view == destination,
                        compact: compact,
                        onPressed:
                            (destination.isCase ||
                                    destination == MissionView.shiftLog) &&
                                !operatorRecordsEnabled
                            ? null
                            : () => onNavigate(destination),
                      ),
                    const Spacer(),
                    _RunStatus(
                      busy: busy,
                      connected: connected,
                      runLabel: runLabel,
                      compact: compact,
                    ),
                    const SizedBox(height: 8),
                    _BottomAction(
                      icon: Icons.settings_outlined,
                      label: 'Settings',
                      compact: compact,
                      onPressed: onSettings,
                    ),
                    _BottomAction(
                      icon: Icons.info_outline_rounded,
                      label: 'Help & info',
                      compact: compact,
                      onPressed: onInfo,
                    ),
                    const SizedBox(height: 8),
                    _OperatorMenu(
                      compact: compact,
                      operatorName: operatorName,
                      operatorLogin: operatorLogin,
                      onLogout: onLogout,
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// A compact mission header with the current view and connection metadata.
///
/// The header has a fixed 48 logical pixel height so desktop content can align
/// with the shell without depending on the parent page's layout.
class MissionHeader extends StatelessWidget {
  /// Creates the mission header.
  const MissionHeader({
    super.key,
    required this.viewTitle,
    required this.runState,
    required this.connectionLabel,
    required this.utc,
    required this.connected,
    this.observed = false,
    this.compact = false,
  });

  /// Current destination's readable title.
  final String viewTitle;

  /// Current run state, such as `Running` or `Paused`.
  final String runState;

  /// Human-readable stream status supplied by the mission controller.
  final String connectionLabel;

  /// Current UTC value to display.
  final String utc;

  /// Whether the stream status should use the connected treatment.
  final bool connected;

  /// Whether the active producer replays observed spacecraft measurements.
  final bool observed;

  /// Whether to hide the text breadcrumb for an icon-only shell.
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final streamColor = connected ? _mint : _gold;
    return Container(
      height: 48,
      padding: EdgeInsets.symmetric(horizontal: compact ? 10 : 20),
      decoration: const BoxDecoration(
        color: _background,
        border: Border(bottom: BorderSide(color: _line)),
      ),
      child: Row(
        children: [
          if (compact)
            Tooltip(
              message: 'Mission control',
              child: const Icon(Icons.public_outlined, size: 17, color: _muted),
            )
          else
            Flexible(
              flex: 3,
              child: Semantics(
                label: 'Mission control, $viewTitle',
                excludeSemantics: true,
                child: Text.rich(
                  TextSpan(
                    text: 'Mission control',
                    style: const TextStyle(color: _quiet, fontSize: 11),
                    children: [
                      const TextSpan(
                        text: '  /  ',
                        style: TextStyle(color: Color(0xff354555)),
                      ),
                      TextSpan(
                        text: viewTitle,
                        style: const TextStyle(color: _text),
                      ),
                    ],
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ),
          const Spacer(),
          if (compact)
            Padding(
              padding: const EdgeInsets.only(right: 8),
              child: Tooltip(
                message:
                    'Run state: $runState\nTelemetry connection: $connectionLabel',
                child: Icon(
                  connected ? Icons.wifi_rounded : Icons.wifi_off_rounded,
                  size: 15,
                  color: streamColor,
                ),
              ),
            ),
          if (!compact) ...[
            _HeaderLabel(
              text: observed ? 'OBSERVED REPLAY' : 'SYNTHETIC DATA',
              color: observed ? _mint : _gold,
            ),
            const SizedBox(width: 18),
            _HeaderStatus(
              icon: Icons.circle,
              label: runState,
              color: _mint,
              tooltip: 'Run state: $runState',
            ),
            const SizedBox(width: 18),
            _HeaderStatus(
              icon: connected ? Icons.wifi_rounded : Icons.wifi_off_rounded,
              label: connectionLabel,
              color: streamColor,
              tooltip: 'Telemetry connection: $connectionLabel',
            ),
            const SizedBox(width: 18),
          ],
          Flexible(
            flex: compact ? 1 : 2,
            child: Semantics(
              label: 'Current UTC $utc',
              excludeSemantics: true,
              child: Text(
                utc,
                textAlign: TextAlign.right,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  color: _quiet,
                  fontSize: 10,
                  fontFeatures: [FontFeature.tabularFigures()],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _Brand extends StatelessWidget {
  const _Brand({required this.compact});

  final bool compact;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 72,
      child: Align(
        alignment: compact ? Alignment.center : Alignment.centerLeft,
        child: compact
            ? Tooltip(
                message: 'Metis mission control',
                child: Image.asset(
                  'assets/images/metis-mark.png',
                  width: 30,
                  height: 30,
                  fit: BoxFit.contain,
                ),
              )
            : Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Image.asset(
                    'assets/images/metis-mark.png',
                    width: 29,
                    height: 36,
                    fit: BoxFit.contain,
                  ),
                  const SizedBox(width: 11),
                  const Text(
                    'metis',
                    style: TextStyle(
                      color: _text,
                      fontSize: 27,
                      fontWeight: FontWeight.w700,
                      letterSpacing: -1.2,
                    ),
                  ),
                  const Text(
                    '.',
                    style: TextStyle(
                      color: _mint,
                      fontSize: 27,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
      ),
    );
  }
}

class _NavigationItem extends StatelessWidget {
  const _NavigationItem({
    required this.icon,
    required this.label,
    required this.selected,
    required this.compact,
    required this.onPressed,
  });

  final IconData icon;
  final String label;
  final bool selected;
  final bool compact;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    final content = SizedBox(
      height: 43,
      child: Padding(
        padding: EdgeInsets.symmetric(horizontal: compact ? 0 : 14),
        child: Row(
          mainAxisAlignment: compact
              ? MainAxisAlignment.center
              : MainAxisAlignment.start,
          children: [
            Icon(icon, size: 19, color: selected ? _mint : _muted),
            if (!compact) ...[
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  label,
                  style: TextStyle(
                    color: selected ? _mint : _muted,
                    fontSize: 13,
                    fontWeight: selected ? FontWeight.w600 : FontWeight.w400,
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
    final item = Semantics(
      button: true,
      enabled: onPressed != null,
      selected: selected,
      onTap: !compact ? onPressed : null,
      label: compact ? null : label,
      excludeSemantics: !compact,
      child: Material(
        color: selected ? const Color(0xff152922) : Colors.transparent,
        borderRadius: BorderRadius.circular(5),
        child: InkWell(
          onTap: onPressed,
          borderRadius: BorderRadius.circular(5),
          hoverColor: const Color(0xff14202a),
          child: content,
        ),
      ),
    );
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      child: compact ? Tooltip(message: label, child: item) : item,
    );
  }
}

class _BottomAction extends StatelessWidget {
  const _BottomAction({
    required this.icon,
    required this.label,
    required this.compact,
    required this.onPressed,
  });

  final IconData icon;
  final String label;
  final bool compact;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    final action = Semantics(
      button: true,
      onTap: !compact ? onPressed : null,
      label: compact ? null : label,
      excludeSemantics: !compact,
      child: Material(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(5),
        child: InkWell(
          onTap: onPressed,
          borderRadius: BorderRadius.circular(5),
          hoverColor: const Color(0xff14202a),
          child: SizedBox(
            height: 40,
            child: Row(
              mainAxisAlignment: compact
                  ? MainAxisAlignment.center
                  : MainAxisAlignment.start,
              children: [
                Padding(
                  padding: EdgeInsets.symmetric(horizontal: compact ? 0 : 14),
                  child: Icon(icon, size: 19, color: _muted),
                ),
                if (!compact)
                  Expanded(
                    child: Text(
                      label,
                      style: const TextStyle(color: _muted, fontSize: 12),
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 1),
      child: compact ? Tooltip(message: label, child: action) : action,
    );
  }
}

class _RunStatus extends StatelessWidget {
  const _RunStatus({
    required this.busy,
    required this.connected,
    required this.runLabel,
    required this.compact,
  });

  final bool busy;
  final bool connected;
  final String runLabel;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final connectionText = busy
        ? 'Working'
        : connected
        ? 'Stream connected'
        : 'Stream disconnected';
    final statusColor = connected ? _mint : _gold;
    final statusLabel = '$runLabel · $connectionText';
    final child = compact
        ? Icon(
            connected ? Icons.wifi_rounded : Icons.wifi_off_rounded,
            size: 18,
            color: statusColor,
          )
        : Container(
            margin: const EdgeInsets.fromLTRB(14, 18, 14, 14),
            padding: const EdgeInsets.only(top: 17),
            decoration: const BoxDecoration(
              border: Border(top: BorderSide(color: _line)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'CURRENT RUN',
                  style: TextStyle(
                    color: _muted,
                    fontSize: 9,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 1.4,
                  ),
                ),
                const SizedBox(height: 10),
                Row(
                  children: [
                    Icon(Icons.circle, size: 7, color: statusColor),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        runLabel,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(color: _text, fontSize: 12),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  connectionText,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(color: statusColor, fontSize: 10),
                ),
              ],
            ),
          );
    return compact
        ? Tooltip(message: statusLabel, child: child)
        : Semantics(label: statusLabel, excludeSemantics: true, child: child);
  }
}

class _OperatorMenu extends StatelessWidget {
  const _OperatorMenu({
    required this.compact,
    required this.operatorName,
    required this.operatorLogin,
    required this.onLogout,
  });

  final bool compact;
  final String operatorName;
  final String operatorLogin;
  final VoidCallback onLogout;

  @override
  Widget build(BuildContext context) {
    final initials = _initials(operatorName);
    final label = operatorName.trim().isEmpty
        ? 'Operator menu'
        : 'Operator $operatorName, $operatorLogin';
    final menu = PopupMenuButton<_OperatorAction>(
      tooltip: label,
      onSelected: (action) {
        if (action == _OperatorAction.logout) onLogout();
      },
      itemBuilder: (context) => [
        PopupMenuItem<_OperatorAction>(
          enabled: false,
          height: 34,
          child: Text(
            'Demo logout ends this run.',
            style: TextStyle(color: _muted, fontSize: 11),
          ),
        ),
        const PopupMenuItem<_OperatorAction>(
          value: _OperatorAction.logout,
          child: Row(
            children: [
              Icon(Icons.logout_rounded, size: 17),
              SizedBox(width: 10),
              Text('Log out'),
            ],
          ),
        ),
      ],
      child: ExcludeSemantics(
        child: SizedBox(
          height: 51,
          child: Padding(
            padding: EdgeInsets.symmetric(horizontal: compact ? 0 : 10),
            child: Row(
              mainAxisAlignment: compact
                  ? MainAxisAlignment.center
                  : MainAxisAlignment.start,
              children: [
                CircleAvatar(
                  radius: 17,
                  backgroundColor: const Color(0xff22352f),
                  child: Text(
                    initials,
                    style: const TextStyle(color: _mint, fontSize: 10),
                  ),
                ),
                if (!compact) ...[
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          operatorName,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(color: _text, fontSize: 12),
                        ),
                        const SizedBox(height: 3),
                        Text(
                          operatorLogin,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(color: _muted, fontSize: 10),
                        ),
                      ],
                    ),
                  ),
                  const Icon(
                    Icons.expand_more_rounded,
                    size: 16,
                    color: _muted,
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
    return Container(
      margin: const EdgeInsets.fromLTRB(8, 8, 8, 8),
      padding: const EdgeInsets.only(top: 8),
      decoration: const BoxDecoration(
        border: Border(top: BorderSide(color: _line)),
      ),
      child: menu,
    );
  }

  String _initials(String name) {
    final parts = name
        .trim()
        .split(RegExp(r'\s+'))
        .where((part) => part.isNotEmpty)
        .toList();
    if (parts.isEmpty) return 'OP';
    if (parts.length == 1) {
      final end = parts.first.length < 2 ? parts.first.length : 2;
      return parts.first.substring(0, end).toUpperCase();
    }
    return '${parts.first.substring(0, 1)}${parts.last.substring(0, 1)}'
        .toUpperCase();
  }
}

class _HeaderLabel extends StatelessWidget {
  const _HeaderLabel({required this.text, required this.color});

  final String text;
  final Color color;

  @override
  Widget build(BuildContext context) => Text(
    text,
    style: TextStyle(
      color: color,
      fontSize: 8,
      fontWeight: FontWeight.w700,
      letterSpacing: 1.1,
    ),
  );
}

class _HeaderStatus extends StatelessWidget {
  const _HeaderStatus({
    required this.icon,
    required this.label,
    required this.color,
    required this.tooltip,
  });

  final IconData icon;
  final String label;
  final Color color;
  final String tooltip;

  @override
  Widget build(BuildContext context) => Semantics(
    label: tooltip,
    excludeSemantics: true,
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: icon == Icons.circle ? 7 : 14, color: color),
        const SizedBox(width: 6),
        ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 145),
          child: Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(color: color, fontSize: 10),
          ),
        ),
      ],
    ),
  );
}

enum _OperatorAction { logout }
