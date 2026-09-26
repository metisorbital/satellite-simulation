import 'dart:async';

import 'package:flutter/material.dart';

import '../api/cases_generated.dart' as cases;
import '../api/mission.dart';
import '../api/viewer_client.dart';
import '../scene/playback.dart';
import 'case_details.dart';
import 'case_shared.dart';

/// Durable operator workspace with a bounded case list and on-demand details.
class CaseWorkspace extends StatefulWidget {
  const CaseWorkspace({
    super.key,
    required this.mission,
    required this.section,
    required this.selectedSatellite,
    required this.onSelected,
    required this.onTelemetry,
    required this.onShiftLog,
  });

  final Mission mission;
  final String section;
  final String selectedSatellite;
  final ValueChanged<String> onSelected;
  final void Function(String satelliteId) onTelemetry;
  final VoidCallback onShiftLog;

  @override
  State<CaseWorkspace> createState() => CaseWorkspaceState();
}

/// Public state used by the shell to prevent accidental navigation from edits.
class CaseWorkspaceState extends State<CaseWorkspace> {
  final _title = TextEditingController();
  final _summary = TextEditingController();
  List<cases.CaseSummary> _summaries = const [];
  cases.CaseRecord? _detail;
  String? _selectedCaseId;
  String _priority = 'review';
  String? _error;
  String? _detailError;
  bool _loading = true;
  bool _detailLoading = false;
  bool _saving = false;
  bool _showCreate = false;
  bool _createDirty = false;
  bool _detailDirty = false;
  int _listRequest = 0;
  int _detailRequest = 0;
  int _editorEpoch = 0;
  int _total = 0;
  bool _hasMore = false;
  late String _identity;
  String? _reportSatellite;
  int? _reportSequence;

  String get _runId => widget.mission.status?['run_id'] as String? ?? '';
  String get _userId => widget.mission.operatorUserId ?? '';
  String get _identityValue => '$_userId/$_runId';
  bool get _validSession => widget.mission.canUseShiftLog && _runId.isNotEmpty;
  bool get _dirty => _createDirty || _detailDirty;
  cases.CaseSummary? get _selectedSummary =>
      _summaries.where((item) => item.case_id == _selectedCaseId).firstOrNull;
  cases.CaseRecord? get _selectedDetail =>
      _detail?.case_id == _selectedCaseId ? _detail : null;

  @override
  void initState() {
    super.initState();
    _identity = _identityValue;
    _title.addListener(_trackCreateDraft);
    _summary.addListener(_trackCreateDraft);
    widget.mission.addListener(_missionChanged);
    unawaited(_load());
  }

  @override
  void didUpdateWidget(covariant CaseWorkspace oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.mission == widget.mission) return;
    oldWidget.mission.removeListener(_missionChanged);
    widget.mission.addListener(_missionChanged);
    _identity = _identityValue;
    _resetForIdentityChange(clearHistory: true);
    if (_validSession) unawaited(_load());
  }

  @override
  void dispose() {
    widget.mission.removeListener(_missionChanged);
    _title.dispose();
    _summary.dispose();
    super.dispose();
  }

  void _trackCreateDraft() {
    final dirty =
        _showCreate &&
        (_title.text.trim().isNotEmpty || _summary.text.trim().isNotEmpty);
    if (mounted && _createDirty != dirty) setState(() => _createDirty = dirty);
  }

  void _missionChanged() {
    final identity = _identityValue;
    if (identity == _identity) return;
    final userChanged = _identity.split('/').first != _userId;
    _identity = identity;
    _resetForIdentityChange(clearHistory: userChanged);
    if (_validSession) unawaited(_load());
  }

  void _resetForIdentityChange({required bool clearHistory}) {
    _listRequest++;
    _detailRequest++;
    _clearAllEditors();
    if (!mounted) return;
    setState(() {
      _saving = false;
      _loading = _validSession;
      _detailLoading = false;
      _error = null;
      _detailError = null;
      _selectedCaseId = null;
      _detail = null;
      if (clearHistory) {
        _summaries = const [];
        _total = 0;
        _hasMore = false;
      }
    });
  }

  void _clearCreateEditor() {
    _title.clear();
    _summary.clear();
    _priority = 'review';
    _showCreate = false;
    _createDirty = false;
    _reportSatellite = null;
    _reportSequence = null;
  }

  void _clearAllEditors() {
    _clearCreateEditor();
    _detailDirty = false;
    _editorEpoch++;
  }

  bool _currentList(String identity, int request) =>
      mounted && identity == _identity && request == _listRequest;

  bool _currentDetail(String identity, int request, String caseId) =>
      mounted &&
      identity == _identity &&
      request == _detailRequest &&
      _selectedCaseId == caseId;

  cases.CaseSummary _summaryFor(cases.CaseRecord record) =>
      cases.CaseSummary.fromJson(record.toJson());

  void _replaceSummary(cases.CaseRecord record, {bool first = false}) {
    final summary = _summaryFor(record);
    final existingIndex = _summaries.indexWhere(
      (item) => item.case_id == summary.case_id,
    );
    if (existingIndex < 0) {
      _summaries = first ? [summary, ..._summaries] : [..._summaries, summary];
      return;
    }
    if (first) {
      _summaries = [
        summary,
        ..._summaries.where((item) => item.case_id != summary.case_id),
      ];
      return;
    }
    _summaries = [
      ..._summaries.take(existingIndex),
      summary,
      ..._summaries.skip(existingIndex + 1),
    ];
  }

  Future<void> _load() async {
    if (!_validSession) {
      if (mounted) setState(() => _loading = false);
      return;
    }
    final identity = _identity;
    final request = ++_listRequest;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final listed = await widget.mission.cases();
      if (!_currentList(identity, request)) return;
      String? selection;
      setState(() {
        _summaries = listed.items;
        _total = listed.total;
        _hasMore = listed.has_more;
        selection = _summaries.any((item) => item.case_id == _selectedCaseId)
            ? _selectedCaseId
            : _summaries
                      .where(
                        (item) =>
                            item.status == 'open' &&
                            item.satellite_id == widget.selectedSatellite,
                      )
                      .firstOrNull
                      ?.case_id ??
                  _summaries.firstOrNull?.case_id;
        _selectedCaseId = selection;
        if (_detail?.case_id != selection) _detail = null;
      });
      if (selection != null) unawaited(_loadDetail(selection!));
    } catch (error) {
      if (_currentList(identity, request)) {
        setState(() => _error = 'Could not load operator cases: $error');
      }
    } finally {
      if (_currentList(identity, request)) setState(() => _loading = false);
    }
  }

  Future<void> _loadDetail(String caseId) async {
    final identity = _identity;
    final request = ++_detailRequest;
    if (_currentDetail(identity, request, caseId)) {
      setState(() {
        _detailLoading = true;
        _detailError = null;
        if (_detail?.case_id != caseId) _detail = null;
      });
    }
    try {
      final record = await widget.mission.readCase(caseId);
      if (!_currentDetail(identity, request, caseId)) return;
      setState(() {
        _detail = record;
        _replaceSummary(record);
      });
    } catch (error) {
      if (_currentDetail(identity, request, caseId)) {
        setState(() => _detailError = 'Could not load this case: $error');
      }
    } finally {
      if (_currentDetail(identity, request, caseId)) {
        setState(() => _detailLoading = false);
      }
    }
  }

  Future<void> _selectCase(String caseId) async {
    if (caseId == _selectedCaseId || !await canLeave()) return;
    if (!mounted) return;
    setState(() {
      _selectedCaseId = caseId;
      _detail = null;
      _detailError = null;
    });
    unawaited(_loadDetail(caseId));
  }

  Future<bool> _beginReport() async {
    if (_saving || !await canLeave() || !mounted) return false;
    final frame = _latestFrame(widget.selectedSatellite);
    setState(() {
      _clearCreateEditor();
      _reportSatellite = widget.selectedSatellite;
      _reportSequence = frame?['sequence'] is int
          ? frame!['sequence'] as int
          : null;
      _showCreate = true;
    });
    return true;
  }

  Future<void> _openSignal(_WarningSignal signal) async {
    if (!await _beginReport() || !mounted) return;
    setState(() {
      _priority = 'review';
      _title.text = signal.title;
      _summary.text = '${signal.summary}\n\nOperator assessment:';
      _createDirty = true;
    });
  }

  Future<void> _selectSatellite(String satelliteId) async {
    if (satelliteId == widget.selectedSatellite || !await canLeave()) return;
    if (!mounted) return;
    final caseId = _summaries
        .where(
          (item) => item.status == 'open' && item.satellite_id == satelliteId,
        )
        .firstOrNull
        ?.case_id;
    setState(() {
      _selectedCaseId = caseId;
      _detail = null;
      _detailError = null;
    });
    widget.onSelected(satelliteId);
    if (caseId != null) unawaited(_loadDetail(caseId));
  }

  Future<void> _create() async {
    if (!_validSession ||
        _saving ||
        _title.text.trim().isEmpty ||
        _summary.text.trim().isEmpty) {
      return;
    }
    final identity = _identity;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final created = await widget.mission.createCase({
        'satellite_id': _reportSatellite ?? widget.selectedSatellite,
        'title': _title.text.trim(),
        'summary': _summary.text.trim(),
        'priority': _priority,
        if (_reportSequence != null) 'sequence': _reportSequence,
      });
      if (!mounted || identity != _identity) return;
      setState(() {
        final alreadyListed = _summaries.any(
          (item) => item.case_id == created.case_id,
        );
        _replaceSummary(created, first: true);
        if (!alreadyListed) _total++;
        if (_summaries.length > 100) {
          _summaries = _summaries.take(100).toList();
          _hasMore = true;
        }
        _selectedCaseId = created.case_id;
        _detail = created;
        _detailError = null;
        _clearCreateEditor();
      });
    } catch (error) {
      if (mounted && identity == _identity) {
        setState(() => _error = 'Could not create the case: $error');
      }
    } finally {
      if (mounted && identity == _identity) setState(() => _saving = false);
    }
  }

  Future<bool> _update(
    cases.CaseRecord record,
    String action,
    Map<String, dynamic> body,
  ) async {
    if (!_validSession || _saving) return false;
    final identity = _identity;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final updated = await widget.mission.updateCase(
        record.case_id,
        action,
        body,
      );
      if (!mounted ||
          identity != _identity ||
          _selectedCaseId != record.case_id) {
        return false;
      }
      setState(() {
        _detail = updated;
        _replaceSummary(updated);
        _detailDirty = false;
      });
      return true;
    } on ViewerRequestException catch (error) {
      if (mounted && identity == _identity) {
        setState(
          () => _error = error.statusCode == 409
              ? 'This case changed before the save completed. Reload it before continuing; your unsaved draft is still shown.'
              : 'Could not save this case: $error',
        );
      }
      return false;
    } catch (error) {
      if (mounted && identity == _identity) {
        setState(() => _error = 'Could not save this case: $error');
      }
      return false;
    } finally {
      if (mounted && identity == _identity) setState(() => _saving = false);
    }
  }

  /// Ask before discarding a currently edited case or a new report.
  Future<bool> canLeave() async {
    if (_saving) return false;
    if (!_dirty) return true;
    if (!mounted) return false;
    final discard =
        await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Discard unsaved case changes?'),
            content: const Text(
              'Your operator-authored changes have not been saved.',
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: const Text('Keep editing'),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(context, true),
                child: const Text('Discard changes'),
              ),
            ],
          ),
        ) ??
        false;
    if (discard && mounted) setState(_clearAllEditors);
    return discard;
  }

  JsonMap? _latestFrame(String satelliteId) {
    final frames = widget.mission.playback.frames[satelliteId];
    return frames == null || frames.isEmpty ? null : frames.last;
  }

  List<_WarningSignal> _warnings() {
    final frame = _latestFrame(widget.selectedSatellite);
    if (frame == null) return const [];
    final signals = <_WarningSignal>[];
    final channels = frame['channels'];
    if (channels is Map) {
      final qualityChannels = <String, List<String>>{};
      for (final entry in channels.entries) {
        final reading = entry.value;
        if (reading is Map &&
            const {
              'missing',
              'invalid',
              'saturated',
            }.contains(reading['quality'])) {
          qualityChannels
              .putIfAbsent(reading['quality'] as String, () => [])
              .add(entry.key.toString());
        }
      }
      for (final entry in qualityChannels.entries) {
        final channelPreview = entry.value.take(4).join(', ');
        final remaining = entry.value.length - 4;
        final ids = remaining > 0
            ? '$channelPreview and $remaining more'
            : channelPreview;
        final meaning = entry.key == 'missing'
            ? 'A missing channel can mean this source does not supply it; confirm data availability before treating it as a spacecraft fault.'
            : 'Review the data quality before interpreting these values.';
        signals.add(
          _WarningSignal(
            title: '${entry.value.length} ${entry.key} telemetry readings',
            summary: 'Channels: $ids. $meaning',
            kind: 'data quality',
          ),
        );
      }
      final powerReading = channels['eps.unserved_power_w'];
      final power = scalar(frame, 'eps.unserved_power_w');
      if (powerReading is Map &&
          powerReading['quality'] == 'valid' &&
          power != null &&
          power > 0) {
        signals.add(
          _WarningSignal(
            title: 'Unserved EPS power',
            summary:
                'Committed eps.unserved_power_w is positive (${power.toStringAsFixed(2)} W).',
            kind: 'committed EPS reading',
          ),
        );
      }
    }
    if (frame['mode'] == 'safe') {
      signals.add(
        const _WarningSignal(
          title: 'Spacecraft reports safe mode',
          summary:
              'The current committed telemetry envelope explicitly reports mode: safe.',
          kind: 'committed mode',
        ),
      );
    }
    return signals;
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: widget.mission,
    builder: (context, _) {
      if (!_validSession) {
        return const CaseStateMessage(
          icon: Icons.lock_outline,
          title: 'Operator sign-in required',
          message:
              'Sign in to read and write your private case history. Telemetry remains separately available.',
        );
      }
      return LayoutBuilder(
        builder: (context, constraints) => SingleChildScrollView(
          padding: EdgeInsets.all(constraints.maxWidth < 640 ? 16 : 26),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 1320),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _header(context),
                  const SizedBox(height: 18),
                  if (_error != null) _errorBanner(),
                  if (_error != null) const SizedBox(height: 12),
                  if (_showCreate) ...[
                    _createPanel(),
                    const SizedBox(height: 16),
                  ],
                  if (_loading && _summaries.isEmpty)
                    const CaseStateMessage(
                      icon: Icons.hourglass_top_outlined,
                      title: 'Loading operator cases',
                      message: 'Reading the durable case history…',
                    )
                  else ...[
                    if (_loading) const LinearProgressIndicator(),
                    if (_loading) const SizedBox(height: 12),
                    _body(constraints),
                  ],
                ],
              ),
            ),
          ),
        ),
      );
    },
  );

  List<DropdownMenuItem<String>> _satelliteItems() {
    final satellites =
        widget.mission.status?['satellites'] as List? ?? const [];
    return [
      for (final raw in satellites)
        if (raw is Map && raw['satellite_id'] is String)
          DropdownMenuItem(
            value: raw['satellite_id'] as String,
            child: Text(
              raw['name'] as String? ?? raw['satellite_id'] as String,
              overflow: TextOverflow.ellipsis,
            ),
          ),
    ];
  }

  Widget _header(BuildContext context) {
    final title = switch (widget.section) {
      'warnings' => 'Early warnings',
      'history' => 'Case history',
      _ => 'Investigations',
    };
    final subtitle = switch (widget.section) {
      'warnings' =>
        'Committed data quality and explicit operating signals. Risk models are not connected.',
      'history' => 'Durable operator cases and their append-only activities.',
      _ =>
        'Review evidence, record operator judgment, and observe the outcome.',
    };
    final items = _satelliteItems();
    final hasCurrent = items.any(
      (item) => item.value == widget.selectedSatellite,
    );
    return Wrap(
      alignment: WrapAlignment.spaceBetween,
      crossAxisAlignment: WrapCrossAlignment.start,
      spacing: 18,
      runSpacing: 12,
      children: [
        SizedBox(
          width: 640,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title.toUpperCase(),
                style: const TextStyle(
                  color: caseMuted,
                  fontSize: 10,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 1.3,
                ),
              ),
              const SizedBox(height: 7),
              Text(title, style: Theme.of(context).textTheme.headlineMedium),
              const SizedBox(height: 6),
              Text(
                subtitle,
                style: const TextStyle(color: caseMuted, height: 1.5),
              ),
              if (items.length > 1) ...[
                const SizedBox(height: 14),
                Semantics(
                  label: 'Selected spacecraft',
                  child: SizedBox(
                    width: 300,
                    child: DropdownButtonFormField<String>(
                      key: ValueKey(widget.selectedSatellite),
                      initialValue: hasCurrent
                          ? widget.selectedSatellite
                          : null,
                      decoration: caseInputDecoration('Spacecraft'),
                      items: items,
                      onChanged: _saving
                          ? null
                          : (value) {
                              if (value != null) {
                                unawaited(_selectSatellite(value));
                              }
                            },
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
        Wrap(
          spacing: 9,
          runSpacing: 8,
          children: [
            OutlinedButton.icon(
              onPressed:
                  _selectedSummary == null || _selectedSummary!.run_id == _runId
                  ? () => widget.onTelemetry(widget.selectedSatellite)
                  : null,
              icon: const Icon(Icons.show_chart, size: 17),
              label: const Text('Open telemetry'),
            ),
            OutlinedButton.icon(
              onPressed: widget.mission.canUseShiftLog
                  ? widget.onShiftLog
                  : null,
              icon: const Icon(Icons.menu_book_outlined, size: 17),
              label: const Text('Shift log'),
            ),
            FilledButton.icon(
              onPressed: _saving ? null : () => unawaited(_beginReport()),
              icon: const Icon(Icons.add, size: 18),
              label: const Text('Report concern'),
            ),
          ],
        ),
      ],
    );
  }

  Widget _errorBanner() => CasePanel(
    padding: const EdgeInsets.all(13),
    child: Row(
      children: [
        const Icon(Icons.error_outline, color: caseGold),
        const SizedBox(width: 10),
        Expanded(
          child: Text(
            _error!,
            style: const TextStyle(color: caseText, fontSize: 12, height: 1.4),
          ),
        ),
        TextButton(
          onPressed: _saving ? null : () => unawaited(_load()),
          child: const Text('Reload'),
        ),
      ],
    ),
  );

  Widget _createPanel() => CasePanel(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                'Report operator concern',
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
            IconButton(
              tooltip: 'Close report form',
              onPressed: _saving ? null : () => setState(_clearCreateEditor),
              icon: const Icon(Icons.close),
            ),
          ],
        ),
        const Text(
          'Cases are operator-authored. A capture is limited to the current committed public sample.',
          style: TextStyle(color: caseMuted, fontSize: 12, height: 1.5),
        ),
        const SizedBox(height: 14),
        TextField(
          controller: _title,
          maxLength: 240,
          decoration: caseInputDecoration('Title'),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _summary,
          maxLines: 4,
          maxLength: 8000,
          decoration: caseInputDecoration('Summary'),
        ),
        const SizedBox(height: 12),
        DropdownButtonFormField<String>(
          key: ValueKey(_priority),
          initialValue: _priority,
          decoration: caseInputDecoration('Priority'),
          items: const [
            DropdownMenuItem(value: 'monitor', child: Text('Monitor')),
            DropdownMenuItem(value: 'review', child: Text('Review')),
            DropdownMenuItem(value: 'urgent', child: Text('Urgent')),
          ],
          onChanged: _saving
              ? null
              : (value) => setState(() {
                  _priority = value!;
                  _createDirty = true;
                }),
        ),
        const SizedBox(height: 14),
        Wrap(
          spacing: 9,
          children: [
            FilledButton.icon(
              onPressed: _saving ? null : _create,
              icon: const Icon(Icons.save_outlined, size: 17),
              label: Text(_saving ? 'Saving…' : 'Create case'),
            ),
            OutlinedButton(
              onPressed: _saving ? null : () => setState(_clearCreateEditor),
              child: const Text('Cancel'),
            ),
          ],
        ),
      ],
    ),
  );

  Widget _body(BoxConstraints constraints) => switch (widget.section) {
    'warnings' => _warningsView(),
    'history' => _historyView(),
    _ => _investigationView(constraints),
  };

  Widget _listLimitNote() => _hasMore
      ? Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: CasePanel(
            padding: const EdgeInsets.all(12),
            child: Text(
              'Showing latest ${_summaries.length} of $_total cases; older records are retained.',
              style: const TextStyle(color: caseMuted, fontSize: 12),
            ),
          ),
        )
      : const SizedBox.shrink();

  Widget _warningsView() {
    final stale = widget.mission.playback.isStale(widget.mission.now);
    final frame = _latestFrame(widget.selectedSatellite);
    final signals = _warnings();
    final openCases = _summaries
        .where(
          (item) =>
              item.status == 'open' &&
              item.satellite_id == widget.selectedSatellite,
        )
        .toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (stale || frame == null)
          CaseStateMessage(
            icon: stale ? Icons.wifi_off_outlined : Icons.sensors_off_outlined,
            title: stale
                ? 'Telemetry is stale or disconnected'
                : 'No committed sample is available',
            message: stale
                ? 'Last known data may be incomplete. Warning status is not a current health assessment.'
                : 'There is no committed sample for this spacecraft yet. Risk models are not connected.',
          ),
        if (stale || frame == null) const SizedBox(height: 16),
        if (signals.isEmpty && openCases.isEmpty && frame != null)
          const CaseStateMessage(
            icon: Icons.info_outline,
            title: 'No configured warning condition in this sample',
            message:
                'No missing, invalid, or saturated reading; positive unserved EPS power; safe mode; or open operator case was found. This does not establish spacecraft health.',
          ),
        for (final signal in signals) ...[
          CasePanel(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(Icons.warning_amber_rounded, color: caseGold),
                    const SizedBox(width: 10),
                    CaseBadge(label: signal.kind, tone: CaseTone.gold),
                    const Spacer(),
                    TextButton(
                      onPressed: _saving
                          ? null
                          : () => unawaited(_openSignal(signal)),
                      child: const Text('Review'),
                    ),
                  ],
                ),
                const SizedBox(height: 9),
                Text(
                  signal.title,
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 5),
                Text(
                  signal.summary,
                  style: const TextStyle(
                    color: caseMuted,
                    fontSize: 12,
                    height: 1.5,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
        ],
        if (openCases.isNotEmpty) ...[
          const Padding(
            padding: EdgeInsets.only(top: 4, bottom: 8),
            child: Text(
              'OPEN OPERATOR CASES',
              style: TextStyle(
                color: caseMuted,
                fontSize: 10,
                letterSpacing: 1,
              ),
            ),
          ),
          for (final record in openCases) ...[
            _caseRow(record),
            const SizedBox(height: 10),
          ],
        ],
      ],
    );
  }

  Widget _investigationView(BoxConstraints constraints) {
    if (_summaries.isEmpty) {
      return const CaseStateMessage(
        icon: Icons.manage_search_outlined,
        title: 'No operator cases yet',
        message:
            'Report a concern from telemetry or the warning view to begin an investigation.',
      );
    }
    final list = _summaries
        .where(
          (item) =>
              item.satellite_id == widget.selectedSatellite ||
              item.case_id == _selectedCaseId,
        )
        .toList();
    final details = _details();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _listLimitNote(),
        if (constraints.maxWidth >= 930)
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SizedBox(width: 310, child: _caseSelector(list)),
              const SizedBox(width: 16),
              Expanded(child: details),
            ],
          )
        else
          Column(
            children: [
              _caseSelector(list),
              const SizedBox(height: 16),
              details,
            ],
          ),
      ],
    );
  }

  Widget _historyView() => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      _listLimitNote(),
      if (_summaries.isEmpty)
        const CaseStateMessage(
          icon: Icons.history_toggle_off_outlined,
          title: 'No durable case history',
          message: 'No cases have been recorded for this operator.',
        ),
      for (final record in _summaries) ...[
        _caseRow(record),
        const SizedBox(height: 10),
      ],
      if (_selectedSummary != null) ...[const SizedBox(height: 6), _details()],
    ],
  );

  Widget _caseSelector(List<cases.CaseSummary> records) => CasePanel(
    padding: const EdgeInsets.symmetric(vertical: 7),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Padding(
          padding: EdgeInsets.fromLTRB(10, 8, 10, 6),
          child: Text(
            'CASES',
            style: TextStyle(
              color: caseMuted,
              fontSize: 10,
              fontWeight: FontWeight.w700,
              letterSpacing: 1,
            ),
          ),
        ),
        if (records.isEmpty)
          const Padding(
            padding: EdgeInsets.all(10),
            child: Text(
              'No cases for this spacecraft.',
              style: TextStyle(color: caseMuted, fontSize: 12),
            ),
          ),
        for (final record in records)
          ListTile(
            selected: record.case_id == _selectedCaseId,
            selectedTileColor: caseMint.withValues(alpha: .08),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(6),
            ),
            title: Text(
              record.title,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 12),
            ),
            subtitle: Padding(
              padding: const EdgeInsets.only(top: 5),
              child: Text(
                '${record.satellite_id} · ${caseLabel(record.decision)}',
                style: const TextStyle(color: caseMuted, fontSize: 10),
              ),
            ),
            trailing: CaseBadge(
              label: caseLabel(record.priority),
              tone: casePriorityTone(record.priority),
            ),
            onTap: () => unawaited(_selectCase(record.case_id)),
          ),
      ],
    ),
  );

  Widget _caseRow(cases.CaseSummary record) => InkWell(
    onTap: () => unawaited(_selectCase(record.case_id)),
    borderRadius: BorderRadius.circular(9),
    child: CasePanel(
      padding: const EdgeInsets.all(16),
      child: Row(
        children: [
          Icon(
            record.status == 'open'
                ? Icons.folder_open_outlined
                : Icons.task_alt_outlined,
            color: record.status == 'open' ? caseGold : caseMint,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  record.title,
                  style: const TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 13,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  '${record.satellite_id} · updated ${caseTime(record.updated_at)}',
                  style: const TextStyle(color: caseMuted, fontSize: 10),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              CaseBadge(
                label: caseLabel(record.priority),
                tone: casePriorityTone(record.priority),
              ),
              const SizedBox(height: 5),
              Text(
                caseLabel(record.status),
                style: const TextStyle(color: caseMuted, fontSize: 10),
              ),
            ],
          ),
        ],
      ),
    ),
  );

  Widget _details() {
    final summary = _selectedSummary;
    if (summary == null) {
      return const CaseStateMessage(
        icon: Icons.touch_app_outlined,
        title: 'Select a case',
        message: 'Choose a case to review its evidence and operator workflow.',
      );
    }
    final record = _selectedDetail;
    if (_detailLoading && record == null) {
      return const CaseStateMessage(
        icon: Icons.hourglass_top_outlined,
        title: 'Loading case record',
        message: 'Reading immutable evidence and recent operator activities…',
      );
    }
    if (_detailError != null && record == null) {
      return CaseStateMessage(
        icon: Icons.error_outline,
        title: 'Case record unavailable',
        message: _detailError!,
        action: OutlinedButton(
          onPressed: () => unawaited(_loadDetail(summary.case_id)),
          child: const Text('Retry'),
        ),
      );
    }
    if (record == null) {
      return const CaseStateMessage(
        icon: Icons.hourglass_empty_outlined,
        title: 'Preparing case record',
        message: 'The selected operator case is being loaded.',
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (_detailLoading) const LinearProgressIndicator(),
        if (_detailLoading) const SizedBox(height: 12),
        if (_detailError != null) ...[
          CasePanel(
            padding: const EdgeInsets.all(12),
            child: Text(
              _detailError!,
              style: const TextStyle(color: caseGold, fontSize: 12),
            ),
          ),
          const SizedBox(height: 12),
        ],
        CaseDetails(
          key: ValueKey('${record.case_id}-$_editorEpoch'),
          record: record,
          canCaptureEvidence: record.run_id == _runId,
          onDirtyChanged: (dirty) {
            if (mounted && _detailDirty != dirty) {
              setState(() => _detailDirty = dirty);
            }
          },
          onUpdate: (action, body) => _update(record, action, body),
        ),
      ],
    );
  }
}

class _WarningSignal {
  const _WarningSignal({
    required this.title,
    required this.summary,
    required this.kind,
  });
  final String title;
  final String summary;
  final String kind;
}
