import 'dart:async';

import 'package:flutter/material.dart';

import '../api/mission.dart';
import '../api/shift_log_generated.dart';
import 'shift_log_store.dart';

const _pageBackground = Color(0xff070d15);
const _panel = Color(0xff101923);
const _panelRaised = Color(0xff0d151f);
const _line = Color(0xff202a36);
const _mint = Color(0xff95cfbc);
const _gold = Color(0xffc7b985);
const _goldDim = Color(0xff2a281c);
const _text = Color(0xffd4dfe8);
const _muted = Color(0xff94a4b7);

/// Full-page operator handover workspace for a mission run.
class ShiftLogPage extends StatefulWidget {
  /// Creates a full-page shift log for [runId].
  const ShiftLogPage({
    super.key,
    required this.mission,
    required this.runId,
    required this.operatorName,
    required this.onClose,
    this.embedded = false,
  });

  /// Authenticated mission state and durable shift-log API.
  final Mission mission;

  /// The run whose records are shown.
  final String runId;

  /// Display name for the active operator.
  final String operatorName;

  /// Called after the page has passed its leave guard.
  final VoidCallback onClose;

  /// Uses the page composition inside the legacy dialog shell.
  final bool embedded;

  @override
  ShiftLogPageState createState() => ShiftLogPageState();
}

/// State and navigation guard for [ShiftLogPage].
class ShiftLogPageState extends State<ShiftLogPage> {
  late final ShiftLogStore store;
  late final TextEditingController _entryController;
  late final TextEditingController _summaryController;
  bool _closing = false;
  bool _leavePromptOpen = false;
  bool _leaveApproved = false;

  @override
  void initState() {
    super.initState();
    _entryController = TextEditingController();
    _summaryController = TextEditingController();
    store = ShiftLogStore(
      mission: widget.mission,
      runId: widget.runId,
      operatorName: widget.operatorName,
    )..addListener(_storeChanged);
    unawaited(store.load());
  }

  /// Return whether it is safe to leave, prompting for unsaved text first.
  Future<bool> canLeave() async {
    if (!mounted || !store.validSession) return true;
    if (_leaveApproved) {
      _leaveApproved = false;
      return true;
    }
    if (store.busy || !store.hasUnsavedChanges) return !store.busy;
    if (_leavePromptOpen) return false;
    _leavePromptOpen = true;
    try {
      final shouldLeave = await showDialog<bool>(
        context: context,
        barrierDismissible: false,
        builder: (dialogContext) => AlertDialog(
          title: const Text('Leave shift log?'),
          content: Text(
            store.uncertainWrite
                ? 'A change may have been saved, but its outcome is not confirmed. Reload before continuing, or leave and review it later.'
                : 'This shift log has text that has not been saved. Leave without keeping those edits?',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(false),
              child: const Text('Keep editing'),
            ),
            FilledButton(
              onPressed: () => Navigator.of(dialogContext).pop(true),
              child: const Text('Leave'),
            ),
          ],
        ),
      );
      if (shouldLeave == true) _leaveApproved = true;
      return shouldLeave == true;
    } finally {
      _leavePromptOpen = false;
    }
  }

  @override
  void dispose() {
    store
      ..removeListener(_storeChanged)
      ..dispose();
    _entryController.dispose();
    _summaryController.dispose();
    super.dispose();
  }

  void _storeChanged() {
    if (!mounted) return;
    if (_entryController.text != store.entryText) {
      _entryController.value = TextEditingValue(
        text: store.entryText,
        selection: TextSelection.collapsed(offset: store.entryText.length),
      );
    }
    if (_summaryController.text != store.summaryText) {
      _summaryController.value = TextEditingValue(
        text: store.summaryText,
        selection: TextSelection.collapsed(offset: store.summaryText.length),
      );
    }
    setState(() {});
    if (!store.validSession && !_closing) {
      _closing = true;
      scheduleMicrotask(() {
        if (mounted) widget.onClose();
      });
    }
  }

  Future<void> _requestClose() async {
    if (_closing) return;
    final allowed = await canLeave();
    if (!mounted || !allowed) return;
    _closing = true;
    widget.onClose();
  }

  @override
  Widget build(BuildContext context) {
    if (!store.validSession) return const SizedBox.shrink();
    final content = _pageContent(context);
    final page = widget.embedded
        ? Material(color: _pageBackground, child: content)
        : Scaffold(
            backgroundColor: _pageBackground,
            body: SafeArea(child: content),
          );
    return PopScope<void>(
      canPop: false,
      onPopInvokedWithResult: (didPop, result) {
        if (!didPop) unawaited(_requestClose());
      },
      child: page,
    );
  }

  Widget _pageContent(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      final horizontal = constraints.maxWidth >= 900;
      final maxWidth = widget.embedded ? 780.0 : 1320.0;
      final narrow = constraints.maxWidth < 560;
      final horizontalPadding = widget.embedded
          ? 24.0
          : narrow
          ? 16.0
          : 32.0;
      return SingleChildScrollView(
        padding: EdgeInsets.fromLTRB(
          horizontalPadding,
          widget.embedded ? 20 : 36,
          horizontalPadding,
          widget.embedded ? 24 : 42,
        ),
        child: Center(
          child: ConstrainedBox(
            constraints: BoxConstraints(maxWidth: maxWidth),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _header(context),
                const SizedBox(height: 28),
                _contextBar(),
                const SizedBox(height: 24),
                if (store.busy && !store.loaded)
                  const LinearProgressIndicator(minHeight: 2),
                if (store.busy && store.loaded)
                  const Padding(
                    padding: EdgeInsets.only(bottom: 12),
                    child: LinearProgressIndicator(minHeight: 2),
                  ),
                if (store.error != null) _errorBanner(context),
                Flex(
                  direction: horizontal ? Axis.horizontal : Axis.vertical,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (horizontal) ...[
                      Expanded(child: _timeline(context)),
                      const SizedBox(width: 24),
                      Expanded(child: _composer(context)),
                    ] else ...[
                      _timeline(context),
                      const SizedBox(height: 24),
                      _composer(context),
                    ],
                  ],
                ),
              ],
            ),
          ),
        ),
      );
    },
  );

  Widget _header(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      final narrow = constraints.maxWidth < 560;
      final back = !widget.embedded
          ? IconButton(
              tooltip: 'Back to mission overview',
              onPressed: store.busy ? null : _requestClose,
              icon: const Icon(Icons.arrow_back_rounded),
            )
          : null;
      final close = widget.embedded
          ? Padding(
              padding: const EdgeInsets.only(left: 6),
              child: IconButton(
                tooltip: 'Close shift log',
                onPressed: store.busy ? null : _requestClose,
                icon: const Icon(Icons.close_rounded),
              ),
            )
          : null;
      final controls = Row(
        mainAxisSize: MainAxisSize.min,
        children: [_statusBadge(), close ?? const SizedBox.shrink()],
      );
      final copy = Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'SHIFT LOG',
            style: TextStyle(
              color: _muted,
              fontSize: 11,
              fontWeight: FontWeight.w700,
              letterSpacing: 1.6,
            ),
          ),
          const SizedBox(height: 9),
          const Text(
            'Leave a clear handover.',
            style: TextStyle(
              color: _text,
              fontSize: 28,
              fontWeight: FontWeight.w500,
              height: 1.15,
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            'The events, decisions and open questions your next operator needs.',
            style: TextStyle(color: _muted, fontSize: 13, height: 1.6),
          ),
        ],
      );
      if (narrow) {
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                back ?? const SizedBox.shrink(),
                const Spacer(),
                controls,
              ],
            ),
            const SizedBox(height: 12),
            copy,
          ],
        );
      }
      return Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (back != null)
            Padding(padding: const EdgeInsets.only(right: 14), child: back),
          Expanded(child: copy),
          const SizedBox(width: 16),
          controls,
        ],
      );
    },
  );

  Widget _statusBadge() {
    final draft = store.draft;
    final label = store.busy
        ? 'Saving'
        : store.uncertainWrite
        ? 'Review write'
        : draft == null
        ? 'No active draft'
        : 'Draft shift record';
    final color = store.uncertainWrite
        ? _gold
        : draft == null
        ? _muted
        : _mint;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 8),
      decoration: BoxDecoration(
        color: color.withValues(alpha: .10),
        border: Border.all(color: color.withValues(alpha: .45)),
        borderRadius: BorderRadius.circular(5),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: color,
          fontSize: 11,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }

  Widget _contextBar() {
    final submitted = store.logs
        .where((log) => log.status == 'submitted')
        .length;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
      decoration: BoxDecoration(
        color: _panelRaised,
        border: Border.all(color: _line),
        borderRadius: BorderRadius.circular(7),
      ),
      child: Wrap(
        spacing: 28,
        runSpacing: 12,
        children: [
          _contextItem('OPERATOR', store.operatorName),
          _contextItem(
            'RUN',
            _shortIdentifier(store.runId),
            tooltip: store.runId,
          ),
          _contextItem(
            'RECORDS',
            '${store.logs.length} saved · $submitted submitted',
          ),
        ],
      ),
    );
  }

  Widget _contextItem(String label, String value, {String? tooltip}) {
    final item = RichText(
      text: TextSpan(
        children: [
          TextSpan(
            text: '$label  ',
            style: const TextStyle(
              color: _muted,
              fontSize: 10,
              letterSpacing: .8,
            ),
          ),
          TextSpan(
            text: value,
            style: const TextStyle(
              color: _text,
              fontSize: 12,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
    return tooltip == null ? item : Tooltip(message: tooltip, child: item);
  }

  String _shortIdentifier(String value) =>
      value.length <= 12 ? value : '${value.substring(0, 8)}…';

  Widget _timeline(BuildContext context) => _panelCard(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _sectionHeading(
          store.logs.any((log) => log.status == 'submitted')
              ? 'SHIFT HISTORY'
              : 'COLLECTED EVENTS',
          store.logs.any((log) => log.status == 'submitted')
              ? 'Shared handover history'
              : 'The shift so far',
        ),
        const SizedBox(height: 4),
        if (!store.loaded && store.busy)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 40),
            child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
          )
        else if (store.loaded && store.logs.isEmpty)
          _emptyTimeline()
        else
          for (final log in store.logs) _recordTimeline(log),
      ],
    ),
  );

  Widget _emptyTimeline() => Padding(
    padding: const EdgeInsets.symmetric(vertical: 34),
    child: Column(
      children: [
        const Icon(Icons.menu_book_outlined, color: _muted, size: 28),
        const SizedBox(height: 12),
        const Text(
          'No entries yet.',
          style: TextStyle(
            color: _text,
            fontSize: 14,
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(height: 6),
        const Text(
          'A note or successful simulator control starts the first draft.',
          textAlign: TextAlign.center,
          style: TextStyle(color: _muted, fontSize: 12, height: 1.5),
        ),
      ],
    ),
  );

  Widget _recordTimeline(ShiftLog log) {
    final submitted = log.status == 'submitted';
    final personalDraft = store.isPersonalDraft(log);
    final readOnly = !personalDraft;
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 19),
      decoration: const BoxDecoration(
        border: Border(top: BorderSide(color: _line)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 25,
            child: Icon(
              readOnly ? Icons.lock_outline_rounded : Icons.edit_note_rounded,
              color: readOnly ? _muted : _mint,
              size: 18,
            ),
          ),
          const SizedBox(width: 13),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        personalDraft
                            ? 'Current draft'
                            : submitted
                            ? 'Submitted shift'
                            : 'Shared draft record',
                        style: const TextStyle(
                          color: _text,
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                    _smallBadge(
                      readOnly ? 'READ ONLY' : 'EDITABLE',
                      readOnly ? _muted : _mint,
                    ),
                  ],
                ),
                const SizedBox(height: 5),
                Text(
                  'Author ${store.author(log.user_id)} · Opened ${store.timestamp(log.created_at)}',
                  style: const TextStyle(color: _muted, fontSize: 11),
                ),
                if (submitted)
                  Tooltip(
                    message: log.run_id,
                    child: Text(
                      'Originating run ${_shortIdentifier(log.run_id)}',
                      style: const TextStyle(color: _muted, fontSize: 11),
                    ),
                  ),
                if (log.submitted_at != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 3),
                    child: Text(
                      'Submitted ${store.timestamp(log.submitted_at!)}',
                      style: const TextStyle(color: _muted, fontSize: 11),
                    ),
                  ),
                if (log.summary.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 12),
                    child: Text(
                      log.summary,
                      style: const TextStyle(
                        color: _text,
                        fontSize: 13,
                        height: 1.6,
                      ),
                    ),
                  ),
                for (final entry in log.entries) _entryTimeline(entry),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _entryTimeline(ShiftLogEntry entry) => Container(
    margin: const EdgeInsets.only(top: 14),
    padding: const EdgeInsets.only(left: 13),
    decoration: const BoxDecoration(
      border: Border(left: BorderSide(color: _line, width: 2)),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          shiftLogKinds[entry.kind] ?? entry.kind.replaceAll('_', ' '),
          style: const TextStyle(
            color: _mint,
            fontSize: 11,
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(height: 4),
        SelectableText(
          entry.text,
          style: const TextStyle(color: _text, fontSize: 13, height: 1.55),
        ),
        const SizedBox(height: 4),
        Text(
          '${store.author(entry.user_id)} · ${store.timestamp(entry.created_at)}',
          style: const TextStyle(color: _muted, fontSize: 11),
        ),
      ],
    ),
  );

  Widget _composer(BuildContext context) => _panelCard(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _sectionHeading('OPERATOR HANDOVER', 'What needs attention next?'),
        const SizedBox(height: 4),
        const Text(
          'Keep observations separate from assumptions. Changes are saved to this run when you add an entry or save the summary.',
          style: TextStyle(color: _muted, fontSize: 12, height: 1.6),
        ),
        const SizedBox(height: 21),
        DropdownButtonFormField<String>(
          initialValue: store.kind,
          decoration: _inputDecoration('ENTRY TYPE'),
          items: [
            for (final item in shiftLogKinds.entries)
              DropdownMenuItem(value: item.key, child: Text(item.value)),
          ],
          onChanged: store.canWrite ? (value) => store.setKind(value!) : null,
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _entryController,
          enabled: store.canWrite,
          minLines: 4,
          maxLines: 7,
          maxLength: 4000,
          onChanged: store.setEntryText,
          decoration: _inputDecoration(
            'WHAT HAPPENED, WHAT WAS DECIDED, OR WHAT REMAINS UNRESOLVED',
          ).copyWith(alignLabelWithHint: true),
        ),
        Align(
          alignment: Alignment.centerRight,
          child: FilledButton.icon(
            onPressed: store.canWrite && store.entryText.trim().isNotEmpty
                ? store.addEntry
                : null,
            icon: const Icon(Icons.add_rounded, size: 17),
            label: Text(
              store.draft == null ? 'Add entry and start draft' : 'Add entry',
            ),
          ),
        ),
        const SizedBox(height: 25),
        const Divider(color: _line),
        const SizedBox(height: 20),
        const Text(
          'SHIFT SUMMARY',
          style: TextStyle(
            color: _muted,
            fontSize: 10,
            fontWeight: FontWeight.w700,
            letterSpacing: 1.2,
          ),
        ),
        const SizedBox(height: 8),
        if (store.draft == null)
          const Text(
            'Add an entry to start a draft. Submitted shifts remain available above as read-only history.',
            style: TextStyle(color: _muted, fontSize: 12, height: 1.6),
          )
        else ...[
          TextField(
            controller: _summaryController,
            enabled: store.canWrite,
            minLines: 5,
            maxLines: 9,
            maxLength: 12000,
            onChanged: store.setSummaryText,
            decoration: _inputDecoration(
              'HANDOVER NOTES',
            ).copyWith(alignLabelWithHint: true),
          ),
          if (store.orphanedSummary != null) _orphanedSummary(),
          _warningNote(),
          const SizedBox(height: 13),
          Wrap(
            alignment: WrapAlignment.end,
            spacing: 9,
            runSpacing: 9,
            children: [
              OutlinedButton(
                onPressed: store.canWrite && store.summaryChanged
                    ? store.saveSummary
                    : null,
                child: const Text('Save summary'),
              ),
              FilledButton.icon(
                onPressed:
                    store.canWrite &&
                        !store.summaryChanged &&
                        store.entryText.trim().isEmpty
                    ? store.submit
                    : null,
                icon: const Icon(Icons.lock_outline_rounded, size: 16),
                label: const Text('Submit shift'),
              ),
            ],
          ),
          const SizedBox(height: 9),
          const Text(
            'Submitting shares this summary and every entry with all operators and locks the record. The next entry starts a new private draft; no spacecraft command is sent.',
            style: TextStyle(color: _muted, fontSize: 11, height: 1.5),
          ),
        ],
      ],
    ),
  );

  Widget _orphanedSummary() => Container(
    margin: const EdgeInsets.only(bottom: 12),
    padding: const EdgeInsets.all(13),
    decoration: BoxDecoration(
      color: _goldDim,
      border: Border.all(color: _gold.withValues(alpha: .35)),
      borderRadius: BorderRadius.circular(5),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Previous draft edits were preserved here',
          style: TextStyle(
            color: _gold,
            fontSize: 12,
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(height: 6),
        Text(
          store.orphanedSummary!,
          style: const TextStyle(color: _text, fontSize: 12, height: 1.5),
        ),
        TextButton(
          onPressed: store.dismissOrphanedSummary,
          child: const Text('Dismiss previous edits'),
        ),
      ],
    ),
  );

  Widget _warningNote() => Container(
    margin: const EdgeInsets.only(top: 4),
    padding: const EdgeInsets.all(13),
    decoration: BoxDecoration(
      color: _goldDim,
      border: Border.all(color: _gold.withValues(alpha: .35)),
      borderRadius: BorderRadius.circular(5),
    ),
    child: const Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(Icons.warning_amber_rounded, color: _gold, size: 17),
        SizedBox(width: 10),
        Expanded(
          child: Text(
            'Keep unresolved questions visible for the next operator. This record documents decisions and does not execute spacecraft commands.',
            style: TextStyle(color: _gold, fontSize: 11, height: 1.5),
          ),
        ),
      ],
    ),
  );

  Widget _errorBanner(BuildContext context) => Container(
    margin: const EdgeInsets.only(bottom: 16),
    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
    decoration: BoxDecoration(
      color: const Color(0xff2a1c20),
      border: Border.all(
        color: Theme.of(context).colorScheme.error.withValues(alpha: .5),
      ),
      borderRadius: BorderRadius.circular(5),
    ),
    child: Row(
      children: [
        Icon(
          Icons.error_outline_rounded,
          color: Theme.of(context).colorScheme.error,
          size: 18,
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Text(
            store.error!,
            style: TextStyle(
              color: Theme.of(context).colorScheme.error,
              fontSize: 12,
              height: 1.5,
            ),
          ),
        ),
        TextButton(
          onPressed: store.busy
              ? null
              : store.uncertainWrite
              ? store.retryUncertainWrite
              : store.reload,
          child: Text(store.uncertainWrite ? 'Retry unchanged' : 'Reload'),
        ),
      ],
    ),
  );

  Widget _panelCard({required Widget child}) => Container(
    padding: const EdgeInsets.all(24),
    decoration: BoxDecoration(
      color: _panel,
      border: Border.all(color: _line),
      borderRadius: BorderRadius.circular(7),
    ),
    child: child,
  );

  Widget _sectionHeading(String eyebrow, String title) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        eyebrow,
        style: const TextStyle(
          color: _muted,
          fontSize: 10,
          fontWeight: FontWeight.w700,
          letterSpacing: 1.2,
        ),
      ),
      const SizedBox(height: 8),
      Text(
        title,
        style: const TextStyle(
          color: _text,
          fontSize: 16,
          fontWeight: FontWeight.w500,
        ),
      ),
    ],
  );

  Widget _smallBadge(String label, Color color) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 4),
    decoration: BoxDecoration(
      color: color.withValues(alpha: .10),
      border: Border.all(color: color.withValues(alpha: .35)),
      borderRadius: BorderRadius.circular(4),
    ),
    child: Text(
      label,
      style: TextStyle(
        color: color,
        fontSize: 9,
        fontWeight: FontWeight.w700,
        letterSpacing: .7,
      ),
    ),
  );

  InputDecoration _inputDecoration(String label) => InputDecoration(
    labelText: label,
    labelStyle: const TextStyle(color: _muted, fontSize: 10, letterSpacing: .5),
    filled: true,
    fillColor: _pageBackground,
    border: OutlineInputBorder(
      borderRadius: BorderRadius.circular(5),
      borderSide: const BorderSide(color: _line),
    ),
    enabledBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(5),
      borderSide: const BorderSide(color: _line),
    ),
    focusedBorder: const OutlineInputBorder(
      borderSide: BorderSide(color: _mint),
    ),
  );
}
