import 'dart:async';

import 'package:flutter/material.dart';
import 'package:pointer_interceptor/pointer_interceptor.dart';

import '../api/mission.dart';
import '../api/shift_log_generated.dart';
import '../scene/playback.dart';

/// The signed-in operator's durable notes, decisions, and shift handover.
class ShiftLogDialog extends StatefulWidget {
  const ShiftLogDialog({
    super.key,
    required this.mission,
    required this.runId,
    required this.operatorName,
  });

  final Mission mission;
  final String runId;
  final String operatorName;

  @override
  State<ShiftLogDialog> createState() => _ShiftLogDialogState();
}

class _ShiftLogDialogState extends State<ShiftLogDialog> {
  static const kinds = {
    'note': 'Note',
    'decision': 'Decision',
    'action': 'Action',
    'unresolved_issue': 'Unresolved issue',
    'event': 'Event',
  };
  final _entry = TextEditingController();
  final _summary = TextEditingController();
  List<ShiftLog> _logs = [];
  String _kind = 'note';
  String? _error;
  bool _busy = true;
  bool _loaded = false;
  bool _closing = false;
  bool _confirmClose = false;
  bool _uncertainWrite = false;
  String? _orphanedSummary;
  late final String? _userId;

  bool get _validSession =>
      !_closing &&
      widget.mission.canUseShiftLog &&
      widget.mission.operatorUserId == _userId &&
      widget.mission.status?['run_id'] == widget.runId;

  void _sessionChanged() {
    if (!mounted || _closing || _validSession) return;
    _closing = true;
    _logs = [];
    // Defer navigation until a possible parent teardown has completed.
    scheduleMicrotask(() {
      if (!mounted) return;
      _entry.clear();
      _summary.clear();
      final route = ModalRoute.of(context);
      if (route != null) Navigator.of(context).removeRoute(route);
    });
  }

  void _close() {
    if (_busy) return;
    if (_entry.text.isNotEmpty ||
        _summaryChanged ||
        _orphanedSummary != null ||
        _uncertainWrite) {
      setState(() => _confirmClose = true);
    } else {
      Navigator.of(context).pop();
    }
  }

  ShiftLog? get _draft =>
      _logs.where((log) => log.status == 'draft').firstOrNull;
  bool get _summaryChanged => _summary.text != (_draft?.summary ?? '');
  bool get _canWrite =>
      _loaded &&
      !_busy &&
      widget.mission.canUseShiftLog &&
      widget.mission.status?['run_id'] == widget.runId;

  @override
  void initState() {
    super.initState();
    _userId = widget.mission.operatorUserId;
    widget.mission.addListener(_sessionChanged);
    _load();
  }

  @override
  void dispose() {
    widget.mission.removeListener(_sessionChanged);
    _entry.dispose();
    _summary.dispose();
    super.dispose();
  }

  Future<void> _refresh({bool resetSummary = false}) async {
    final logs = await widget.mission.shiftLogs(widget.runId);
    if (!mounted || !_validSession) return;
    final nextDraft = logs.where((log) => log.status == 'draft').firstOrNull;
    final changedDraft = _draft?.shift_id != nextDraft?.shift_id;
    final hadEdits = !resetSummary && _summaryChanged;
    final keepSummary = hadEdits && !changedDraft;
    setState(() {
      if (hadEdits && changedDraft) _orphanedSummary = _summary.text;
      _logs = logs;
      _loaded = true;
      if (!keepSummary) _summary.text = _draft?.summary ?? '';
    });
  }

  Future<void> _load() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await _refresh();
    } catch (error) {
      if (mounted && _validSession) {
        setState(() => _error = 'Could not load shift logs: $error');
      }
    } finally {
      if (mounted && _validSession) setState(() => _busy = false);
    }
  }

  Future<void> _write(
    String resource,
    JsonMap body, {
    bool clearEntry = false,
    bool resetSummary = false,
  }) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    var saved = false;
    try {
      await widget.mission.writeShiftLog(widget.runId, resource, body);
      saved = true;
      if (!mounted || !_validSession) return;
      _uncertainWrite = false;
      if (clearEntry) _entry.clear();
      await _refresh(resetSummary: resetSummary);
    } catch (error) {
      if (mounted && _validSession) {
        setState(() {
          _uncertainWrite = !saved;
          // Block writes against a stale draft after an acknowledged mutation.
          if (saved) _loaded = false;
          _error = saved
              ? 'Saved, but the list could not refresh. Reload before continuing: $error'
              : 'Could not confirm the change. Retry unchanged to avoid duplicates: $error';
        });
      }
    } finally {
      if (mounted && _validSession) setState(() => _busy = false);
    }
  }

  String _timestamp(String value) {
    final parsed = DateTime.tryParse(value);
    return parsed == null
        ? value
        : '${parsed.toUtc().toIso8601String().replaceFirst('T', ' ').split('.').first} UTC';
  }

  String _author(String userId) => userId == widget.mission.operatorUserId
      ? '${widget.operatorName} · $userId'
      : userId;

  @override
  Widget build(BuildContext context) {
    if (!_validSession) return const SizedBox.shrink();
    final draft = _draft;
    return PopScope<void>(
      canPop: false,
      onPopInvokedWithResult: (didPop, result) {
        if (!didPop) _close();
      },
      child: PointerInterceptor(
        child: AlertDialog(
          title: const Text('Shift Log'),
          content: SizedBox(
            width: 700,
            height: MediaQuery.sizeOf(context).height * .72,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  'Run ${widget.runId}',
                  style: Theme.of(context).textTheme.labelSmall,
                ),
                const SizedBox(height: 6),
                const Text(
                  'Record decisions and hand over your shift. Logging an action or approval does not execute a spacecraft command.',
                ),
                if (_busy) const LinearProgressIndicator(),
                if (_error != null)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    child: Text(
                      _error!,
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                      ),
                    ),
                  ),
                Expanded(
                  child: ListView(
                    children: [
                      if (_loaded && _logs.isEmpty)
                        const Padding(
                          padding: EdgeInsets.symmetric(vertical: 16),
                          child: Text(
                            'No entries yet. A note or successful simulation control starts your first draft.',
                          ),
                        ),
                      for (final log in _logs) _record(log),
                      if (_orphanedSummary != null) ...[
                        const Divider(),
                        const Text(
                          'The draft changed elsewhere. These unsaved summary edits belong to the previous shift and were not applied to the new one:',
                        ),
                        SelectableText(_orphanedSummary!),
                        TextButton(
                          onPressed: () =>
                              setState(() => _orphanedSummary = null),
                          child: const Text('Dismiss previous edits'),
                        ),
                      ],
                      const Divider(),
                      DropdownButtonFormField<String>(
                        initialValue: _kind,
                        decoration: const InputDecoration(
                          labelText: 'Entry type',
                        ),
                        items: [
                          for (final kind in kinds.entries)
                            DropdownMenuItem(
                              value: kind.key,
                              child: Text(kind.value),
                            ),
                        ],
                        onChanged: _canWrite
                            ? (value) => setState(() => _kind = value!)
                            : null,
                      ),
                      TextField(
                        controller: _entry,
                        enabled: _canWrite,
                        minLines: 2,
                        maxLines: 4,
                        maxLength: 4000,
                        decoration: const InputDecoration(
                          labelText:
                              'What happened, what was decided, or what remains unresolved?',
                        ),
                        onChanged: (_) => setState(() {}),
                      ),
                      Align(
                        alignment: Alignment.centerRight,
                        child: FilledButton.icon(
                          onPressed: _canWrite && _entry.text.trim().isNotEmpty
                              ? () => _write(
                                  'entries',
                                  AddShiftLogEntryRequest(
                                    kind: _kind,
                                    text: _entry.text.trim(),
                                  ).toJson(),
                                  clearEntry: true,
                                )
                              : null,
                          icon: const Icon(Icons.add),
                          label: Text(
                            draft == null
                                ? 'Add entry and start draft'
                                : 'Add entry',
                          ),
                        ),
                      ),
                      if (draft != null) ...[
                        const SizedBox(height: 16),
                        TextField(
                          controller: _summary,
                          enabled: _canWrite,
                          minLines: 3,
                          maxLines: 6,
                          maxLength: 12000,
                          decoration: const InputDecoration(
                            labelText: 'Shift summary',
                            helperText:
                                'Save your summary before submitting the shift.',
                          ),
                          onChanged: (_) => setState(() {}),
                        ),
                        Wrap(
                          alignment: WrapAlignment.end,
                          spacing: 8,
                          children: [
                            TextButton(
                              onPressed: _canWrite && _summaryChanged
                                  ? () => _write(
                                      '${draft.shift_id}/summary',
                                      UpdateShiftLogSummaryRequest(
                                        summary: _summary.text,
                                      ).toJson(),
                                      resetSummary: true,
                                    )
                                  : null,
                              child: const Text('Save summary'),
                            ),
                            FilledButton(
                              onPressed:
                                  _canWrite &&
                                      !_summaryChanged &&
                                      _entry.text.trim().isEmpty
                                  ? () => _write(
                                      '${draft.shift_id}/submit',
                                      const SubmitShiftLogRequest().toJson(),
                                      resetSummary: true,
                                    )
                                  : null,
                              child: const Text('Submit shift'),
                            ),
                          ],
                        ),
                        const SizedBox(height: 6),
                        const Text(
                          'Submission locks this record. Your next entry or successful simulation control opens a new draft.',
                        ),
                      ],
                    ],
                  ),
                ),
              ],
            ),
          ),
          actions: [
            if (_confirmClose) ...[
              Text(
                _uncertainWrite
                    ? 'A change may have been saved. Close without confirming its outcome?'
                    : 'Discard unsaved text and close?',
              ),
              TextButton(
                onPressed: () => setState(() => _confirmClose = false),
                child: const Text('Keep editing'),
              ),
              TextButton(
                onPressed: _busy ? null : () => Navigator.of(context).pop(),
                child: const Text('Discard and close'),
              ),
            ] else ...[
              TextButton(
                onPressed: _busy ? null : _load,
                child: const Text('Reload'),
              ),
              TextButton(
                onPressed: _busy ? null : _close,
                child: const Text('Close'),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _record(ShiftLog log) => Card(
    margin: const EdgeInsets.symmetric(vertical: 8),
    child: Padding(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            log.status == 'submitted' ? 'Submitted shift' : 'Current draft',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          SelectableText(
            '${_author(log.user_id)}\nOpened ${_timestamp(log.created_at)}',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          if (log.submitted_at != null)
            Text('Submitted ${_timestamp(log.submitted_at!)}'),
          if (log.summary.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(log.summary),
            ),
          for (final entry in log.entries)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    kinds[entry.kind] ?? entry.kind.replaceAll('_', ' '),
                    style: Theme.of(context).textTheme.labelLarge,
                  ),
                  SelectableText(entry.text),
                  Text(
                    '${_author(entry.user_id)} · ${_timestamp(entry.created_at)}',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            ),
        ],
      ),
    ),
  );
}
