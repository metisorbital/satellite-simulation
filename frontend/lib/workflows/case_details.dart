import 'package:flutter/material.dart';

import '../api/cases_generated.dart' as cases;
import 'case_shared.dart';

/// Renders one durable operator case and its revision-controlled workflow.
class CaseDetails extends StatefulWidget {
  const CaseDetails({
    super.key,
    required this.record,
    required this.canCaptureEvidence,
    required this.onUpdate,
    required this.onDirtyChanged,
  });

  final cases.CaseRecord record;
  final bool canCaptureEvidence;
  final Future<bool> Function(String action, Map<String, dynamic> body)
  onUpdate;
  final ValueChanged<bool> onDirtyChanged;

  @override
  State<CaseDetails> createState() => _CaseDetailsState();
}

class _CaseDetailsState extends State<CaseDetails> {
  late final TextEditingController _assessment;
  late final TextEditingController _missing;
  late final TextEditingController _recommendation;
  late final TextEditingController _effect;
  late final TextEditingController _tradeoffs;
  late final TextEditingController _reason;
  late final TextEditingController _revisedRecommendation;
  late final TextEditingController _outcomeNotes;
  bool _editAssessment = false;
  bool _editRecommendation = false;
  String? _decision;
  String _outcome = 'awaiting_observation';
  bool _closeCase = false;
  bool _populating = false;

  List<TextEditingController> get _controllers => [
    _assessment,
    _missing,
    _recommendation,
    _effect,
    _tradeoffs,
    _reason,
    _revisedRecommendation,
    _outcomeNotes,
  ];

  @override
  void initState() {
    super.initState();
    _assessment = TextEditingController();
    _missing = TextEditingController();
    _recommendation = TextEditingController();
    _effect = TextEditingController();
    _tradeoffs = TextEditingController();
    _reason = TextEditingController();
    _revisedRecommendation = TextEditingController();
    _outcomeNotes = TextEditingController();
    for (final controller in _controllers) {
      controller.addListener(_notifyDirty);
    }
    _loadRecord();
  }

  @override
  void didUpdateWidget(covariant CaseDetails oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.record.case_id != widget.record.case_id ||
        oldWidget.record.revision != widget.record.revision) {
      _syncRecord(oldWidget.record);
    }
  }

  void _loadRecord() {
    _populating = true;
    _assessment.text = widget.record.assessment;
    _missing.text = widget.record.missing_information;
    _recommendation.text = widget.record.recommendation;
    _effect.text = widget.record.expected_effect;
    _tradeoffs.text = widget.record.tradeoffs;
    _reason.text = widget.record.decision_reason;
    _revisedRecommendation.text = '';
    _outcomeNotes.text = widget.record.outcome_notes;
    _outcome = widget.record.outcome;
    _closeCase = widget.record.status == 'closed';
    _populating = false;
  }

  void _syncRecord(cases.CaseRecord previous) {
    _populating = true;
    _replaceIfUnchanged(
      _assessment,
      previous.assessment,
      widget.record.assessment,
    );
    _replaceIfUnchanged(
      _missing,
      previous.missing_information,
      widget.record.missing_information,
    );
    _replaceIfUnchanged(
      _recommendation,
      previous.recommendation,
      widget.record.recommendation,
    );
    _replaceIfUnchanged(
      _effect,
      previous.expected_effect,
      widget.record.expected_effect,
    );
    _replaceIfUnchanged(
      _tradeoffs,
      previous.tradeoffs,
      widget.record.tradeoffs,
    );
    _replaceIfUnchanged(
      _reason,
      previous.decision_reason,
      widget.record.decision_reason,
    );
    _replaceIfUnchanged(
      _outcomeNotes,
      previous.outcome_notes,
      widget.record.outcome_notes,
    );
    if (_outcome == previous.outcome) _outcome = widget.record.outcome;
    if (_closeCase == (previous.status == 'closed')) {
      _closeCase = widget.record.status == 'closed';
    }
    if (_decision == widget.record.decision) _decision = null;
    if (_assessment.text == widget.record.assessment &&
        _missing.text == widget.record.missing_information) {
      _editAssessment = false;
    }
    if (_recommendation.text == widget.record.recommendation &&
        _effect.text == widget.record.expected_effect &&
        _tradeoffs.text == widget.record.tradeoffs) {
      _editRecommendation = false;
    }
    _populating = false;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) widget.onDirtyChanged(_hasDraft);
    });
  }

  void _replaceIfUnchanged(
    TextEditingController controller,
    String previous,
    String next,
  ) {
    if (controller.text == previous) controller.text = next;
  }

  void _notifyDirty() {
    if (_populating || !mounted) return;
    setState(() {});
    widget.onDirtyChanged(_hasDraft);
  }

  bool get _hasDraft =>
      _editAssessment ||
      _editRecommendation ||
      _decision != null ||
      _outcome != widget.record.outcome ||
      _closeCase != (widget.record.status == 'closed') ||
      _assessment.text != widget.record.assessment ||
      _missing.text != widget.record.missing_information ||
      _recommendation.text != widget.record.recommendation ||
      _effect.text != widget.record.expected_effect ||
      _tradeoffs.text != widget.record.tradeoffs ||
      _reason.text != widget.record.decision_reason ||
      _revisedRecommendation.text.isNotEmpty ||
      _outcomeNotes.text != widget.record.outcome_notes;

  @override
  void dispose() {
    for (final controller in _controllers) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> _save(String action, Map<String, dynamic> body) async {
    final submittedRevision = body['revised_recommendation'] as String?;
    final saved = await widget.onUpdate(action, body);
    if (!saved || !mounted) return;
    if (submittedRevision != null &&
        _revisedRecommendation.text == submittedRevision) {
      _revisedRecommendation.clear();
    }
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) widget.onDirtyChanged(_hasDraft);
    });
  }

  @override
  Widget build(BuildContext context) {
    final record = widget.record;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        CasePanel(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  CaseBadge(
                    label: caseLabel(record.priority),
                    tone: casePriorityTone(record.priority),
                  ),
                  CaseBadge(
                    label: record.status == 'open' ? 'Open' : 'Closed',
                    tone: record.status == 'open'
                        ? CaseTone.gold
                        : CaseTone.quiet,
                  ),
                  CaseBadge(label: 'Revision ${record.revision}'),
                ],
              ),
              const SizedBox(height: 14),
              Text(
                record.title,
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(height: 7),
              Text(
                record.summary,
                style: const TextStyle(color: caseMuted, height: 1.55),
              ),
              const SizedBox(height: 16),
              Text(
                'Created ${caseTime(record.created_at)} · ${record.satellite_id}',
                style: const TextStyle(color: caseMuted, fontSize: 11),
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        _EvidencePanel(evidence: record.evidence),
        const SizedBox(height: 16),
        _EditablePanel(
          title: 'Assessment and missing context',
          subtitle:
              'Operator-authored assessment. Record what is known and what must still be checked.',
          editing: _editAssessment,
          onEdit: () => setState(() => _editAssessment = true),
          onCancel: () => setState(() {
            _assessment.text = record.assessment;
            _missing.text = record.missing_information;
            _editAssessment = false;
            _notifyDirty();
          }),
          onSave: () => _save('assessment', {
            'revision': record.revision,
            'assessment': _assessment.text,
            'missing_information': _missing.text,
          }),
          child: _editAssessment
              ? Column(
                  children: [
                    TextField(
                      controller: _assessment,
                      maxLines: 4,
                      decoration: caseInputDecoration('Assessment'),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: _missing,
                      maxLines: 3,
                      decoration: caseInputDecoration('Missing information'),
                    ),
                  ],
                )
              : _ReadOnlyFields(
                  items: [
                    ('Assessment', record.assessment),
                    ('Missing information', record.missing_information),
                  ],
                ),
        ),
        const SizedBox(height: 16),
        _EditablePanel(
          title: 'Recommendation',
          subtitle:
              'Approval records your decision. For a linked recorded mission, approving the unchanged model proposal applies its planning schedule and resumes playback. Edited recommendations remain narrative; playback keeps the original plan. No spacecraft command is sent.',
          editing: _editRecommendation,
          onEdit: () => setState(() => _editRecommendation = true),
          onCancel: () => setState(() {
            _recommendation.text = record.recommendation;
            _effect.text = record.expected_effect;
            _tradeoffs.text = record.tradeoffs;
            _editRecommendation = false;
            _notifyDirty();
          }),
          onSave: () => _save('recommendation', {
            'revision': record.revision,
            'recommendation': _recommendation.text,
            'expected_effect': _effect.text,
            'tradeoffs': _tradeoffs.text,
          }),
          child: _editRecommendation
              ? Column(
                  children: [
                    TextField(
                      controller: _recommendation,
                      maxLines: 4,
                      decoration: caseInputDecoration('Recommendation'),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: _effect,
                      maxLines: 3,
                      decoration: caseInputDecoration('Expected effect'),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: _tradeoffs,
                      maxLines: 3,
                      decoration: caseInputDecoration('Tradeoffs'),
                    ),
                  ],
                )
              : _ReadOnlyFields(
                  items: [
                    ('Recommendation', record.recommendation),
                    ('Expected effect', record.expected_effect),
                    ('Tradeoffs', record.tradeoffs),
                  ],
                ),
        ),
        const SizedBox(height: 16),
        CasePanel(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Decision', style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 5),
              const Text(
                'A persisted operator decision. It does not validate the recommendation or command the spacecraft.',
                style: TextStyle(color: caseMuted, fontSize: 12, height: 1.5),
              ),
              const SizedBox(height: 14),
              if (record.decision != 'pending' && _decision == null)
                _ReadOnlyFields(
                  items: [
                    ('Recorded decision', caseLabel(record.decision)),
                    ('Reason', record.decision_reason),
                  ],
                )
              else ...[
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    for (final decision in const [
                      'approved',
                      'rejected',
                      'revised',
                    ])
                      ChoiceChip(
                        label: Text(caseLabel(decision)),
                        selected: _decision == decision,
                        onSelected: (_) => setState(() {
                          _decision = decision;
                          _notifyDirty();
                        }),
                      ),
                  ],
                ),
                if (_decision != null) ...[
                  const SizedBox(height: 12),
                  TextField(
                    controller: _reason,
                    maxLines: 3,
                    decoration: caseInputDecoration('Decision reason'),
                  ),
                  if (_decision == 'revised') ...[
                    const SizedBox(height: 12),
                    TextField(
                      controller: _revisedRecommendation,
                      maxLines: 3,
                      decoration: caseInputDecoration('Revised recommendation'),
                    ),
                  ],
                  const SizedBox(height: 12),
                  FilledButton.icon(
                    onPressed:
                        record.recommendation.trim().isEmpty ||
                            _reason.text.trim().isEmpty ||
                            (_decision == 'revised' &&
                                _revisedRecommendation.text.trim().isEmpty)
                        ? null
                        : () => _save('decision', {
                            'revision': record.revision,
                            'decision': _decision,
                            'reason': _reason.text,
                            if (_decision == 'revised')
                              'revised_recommendation':
                                  _revisedRecommendation.text,
                          }),
                    icon: const Icon(Icons.fact_check_outlined, size: 17),
                    label: const Text('Record decision'),
                  ),
                  if (record.recommendation.trim().isEmpty)
                    const Padding(
                      padding: EdgeInsets.only(top: 8),
                      child: Text(
                        'Record a recommendation before recording a decision.',
                        style: TextStyle(color: caseMuted, fontSize: 11),
                      ),
                    ),
                ] else
                  Padding(
                    padding: const EdgeInsets.only(top: 12),
                    child: OutlinedButton.icon(
                      onPressed: () => setState(() => _decision = 'approved'),
                      icon: const Icon(Icons.edit_outlined, size: 17),
                      label: const Text('Record a new decision'),
                    ),
                  ),
              ],
            ],
          ),
        ),
        const SizedBox(height: 16),
        CasePanel(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Later observation',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 5),
              const Text(
                'Outcome remains separate from approval and may support, correct, or leave a recommendation inconclusive.',
                style: TextStyle(color: caseMuted, fontSize: 12, height: 1.5),
              ),
              const SizedBox(height: 14),
              DropdownButtonFormField<String>(
                key: ValueKey(_outcome),
                initialValue: _outcome,
                decoration: caseInputDecoration('Outcome'),
                items: const [
                  DropdownMenuItem(
                    value: 'awaiting_observation',
                    child: Text('Awaiting observation'),
                  ),
                  DropdownMenuItem(
                    value: 'supported',
                    child: Text('Supported'),
                  ),
                  DropdownMenuItem(
                    value: 'corrected',
                    child: Text('Corrected'),
                  ),
                  DropdownMenuItem(
                    value: 'inconclusive',
                    child: Text('Inconclusive'),
                  ),
                ],
                onChanged: record.status == 'closed'
                    ? null
                    : (value) => setState(() {
                        _outcome = value!;
                        _notifyDirty();
                      }),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _outcomeNotes,
                maxLines: 3,
                decoration: caseInputDecoration('Observation notes'),
              ),
              CheckboxListTile(
                value: _closeCase,
                onChanged: record.status == 'closed'
                    ? null
                    : (value) => setState(() {
                        _closeCase = value ?? false;
                        _notifyDirty();
                      }),
                title: const Text(
                  'Close this case after recording the outcome',
                  style: TextStyle(fontSize: 12),
                ),
                contentPadding: EdgeInsets.zero,
                controlAffinity: ListTileControlAffinity.leading,
              ),
              Wrap(
                spacing: 10,
                runSpacing: 8,
                children: [
                  FilledButton.icon(
                    onPressed:
                        record.status == 'closed' ||
                            (_outcome != 'awaiting_observation' &&
                                _outcomeNotes.text.trim().isEmpty)
                        ? null
                        : () => _save('outcome', {
                            'revision': record.revision,
                            'outcome': _outcome,
                            'outcome_notes': _outcomeNotes.text,
                            'close_case': _closeCase,
                          }),
                    icon: const Icon(Icons.visibility_outlined, size: 17),
                    label: const Text('Record outcome'),
                  ),
                  OutlinedButton.icon(
                    onPressed:
                        record.status == 'closed' || !widget.canCaptureEvidence
                        ? null
                        : () =>
                              _save('evidence', {'revision': record.revision}),
                    icon: const Icon(Icons.camera_alt_outlined, size: 17),
                    label: const Text('Capture committed evidence'),
                  ),
                ],
              ),
              if (!widget.canCaptureEvidence)
                const Padding(
                  padding: EdgeInsets.only(top: 10),
                  child: Text(
                    'This case belongs to a historical run. Its existing snapshot remains immutable; current telemetry cannot be attached.',
                    style: TextStyle(
                      color: caseMuted,
                      fontSize: 11,
                      height: 1.45,
                    ),
                  ),
                ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        _ActivityTimeline(
          activities: record.activities,
          activityCount: record.activity_count,
          truncated: record.activities_truncated,
        ),
      ],
    );
  }
}

class _EditablePanel extends StatelessWidget {
  const _EditablePanel({
    required this.title,
    required this.subtitle,
    required this.editing,
    required this.onEdit,
    required this.onCancel,
    required this.onSave,
    required this.child,
  });
  final String title;
  final String subtitle;
  final bool editing;
  final VoidCallback onEdit;
  final VoidCallback onCancel;
  final Future<void> Function() onSave;
  final Widget child;

  @override
  Widget build(BuildContext context) => CasePanel(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                title,
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
            if (!editing)
              TextButton.icon(
                onPressed: onEdit,
                icon: const Icon(Icons.edit_outlined, size: 16),
                label: const Text('Edit'),
              ),
          ],
        ),
        const SizedBox(height: 5),
        Text(
          subtitle,
          style: const TextStyle(color: caseMuted, fontSize: 12, height: 1.5),
        ),
        const SizedBox(height: 14),
        child,
        if (editing)
          Padding(
            padding: const EdgeInsets.only(top: 12),
            child: Wrap(
              spacing: 9,
              children: [
                FilledButton(onPressed: onSave, child: const Text('Save')),
                OutlinedButton(
                  onPressed: onCancel,
                  child: const Text('Cancel'),
                ),
              ],
            ),
          ),
      ],
    ),
  );
}

class _ReadOnlyFields extends StatelessWidget {
  const _ReadOnlyFields({required this.items});
  final List<(String, String)> items;
  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      for (final item in items) ...[
        Text(
          item.$1.toUpperCase(),
          style: const TextStyle(
            color: caseMuted,
            fontSize: 10,
            fontWeight: FontWeight.w700,
            letterSpacing: .7,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          item.$2.isEmpty ? 'Not recorded.' : item.$2,
          style: const TextStyle(height: 1.5),
        ),
        const SizedBox(height: 13),
      ],
    ],
  );
}

class _EvidencePanel extends StatelessWidget {
  const _EvidencePanel({required this.evidence});
  final cases.CaseEvidence? evidence;
  @override
  Widget build(BuildContext context) {
    final snapshot = evidence;
    if (snapshot == null) {
      return const CaseStateMessage(
        icon: Icons.inventory_2_outlined,
        title: 'No captured evidence yet',
        message:
            'The case has no immutable committed telemetry snapshot. Capture evidence after a committed sample is available.',
      );
    }
    return CasePanel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Evidence snapshot',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 5),
          Text(
            'Immutable public provenance captured from committed telemetry.',
            style: const TextStyle(color: caseMuted, fontSize: 12),
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 16,
            runSpacing: 9,
            children: [
              _provenance('Satellite', snapshot.satellite_id),
              _provenance('Sequence', '${snapshot.sequence}'),
              _provenance('Observed', caseTime(snapshot.observed_at)),
              _provenance('Catalog', snapshot.catalog_version),
              _provenance(
                'Source',
                '${snapshot.source_kind} · ${snapshot.time_domain}',
              ),
              _provenance('Payload hash', snapshot.payload_hash),
            ],
          ),
          const SizedBox(height: 14),
          _EvidenceReadings(readings: snapshot.readings),
        ],
      ),
    );
  }

  Widget _provenance(String label, String value) => SizedBox(
    width: 150,
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label.toUpperCase(),
          style: const TextStyle(
            color: caseMuted,
            fontSize: 9,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 3),
        Text(
          value,
          style: const TextStyle(fontSize: 11),
          overflow: TextOverflow.ellipsis,
        ),
      ],
    ),
  );
}

/// Keeps committed readings available without displacing the operator workflow.
class _EvidenceReadings extends StatelessWidget {
  const _EvidenceReadings({required this.readings});

  final List<cases.CaseEvidenceReading> readings;

  @override
  Widget build(BuildContext context) {
    final counts = <String, int>{};
    for (final reading in readings) {
      counts.update(reading.quality, (count) => count + 1, ifAbsent: () => 1);
    }
    final qualitySummary = counts.entries
        .map((entry) => '${entry.value} ${entry.key}')
        .join(' · ');
    return Container(
      decoration: BoxDecoration(
        border: Border.all(color: caseLine),
        borderRadius: BorderRadius.circular(6),
      ),
      child: ExpansionTile(
        title: Text('${readings.length} committed readings'),
        subtitle: Text(
          qualitySummary.isEmpty ? 'No readings captured.' : qualitySummary,
          style: const TextStyle(color: caseMuted, fontSize: 11),
        ),
        children: [
          for (final reading in readings)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      reading.channel_id,
                      style: const TextStyle(
                        fontFamily: 'monospace',
                        fontSize: 11,
                      ),
                    ),
                  ),
                  Expanded(
                    child: Text(
                      '${reading.value_text} ${reading.unit}'.trim(),
                      textAlign: TextAlign.right,
                      style: const TextStyle(fontSize: 11),
                    ),
                  ),
                  const SizedBox(width: 10),
                  CaseBadge(
                    label: reading.quality,
                    tone: reading.quality == 'valid'
                        ? CaseTone.mint
                        : CaseTone.gold,
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _ActivityTimeline extends StatelessWidget {
  const _ActivityTimeline({
    required this.activities,
    required this.activityCount,
    required this.truncated,
  });
  final List<cases.CaseActivity> activities;
  final int activityCount;
  final bool truncated;
  @override
  Widget build(BuildContext context) => CasePanel(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Case activity', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 10),
        if (truncated)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Text(
              'Showing latest 50 of $activityCount activities; older records are retained.',
              style: const TextStyle(
                color: caseMuted,
                fontSize: 11,
                height: 1.4,
              ),
            ),
          ),
        if (activities.isEmpty)
          const Text(
            'No activity has been recorded.',
            style: TextStyle(color: caseMuted, fontSize: 12),
          )
        else
          for (final activity in activities)
            Padding(
              padding: const EdgeInsets.only(top: 13),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(
                    activity.evidence == null
                        ? Icons.history
                        : Icons.camera_alt_outlined,
                    size: 17,
                    color: caseMint,
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          caseLabel(activity.kind),
                          style: const TextStyle(
                            fontWeight: FontWeight.w700,
                            fontSize: 12,
                          ),
                        ),
                        const SizedBox(height: 3),
                        Text(
                          activity.text,
                          style: const TextStyle(
                            color: caseMuted,
                            fontSize: 12,
                            height: 1.45,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          caseTime(activity.created_at),
                          style: const TextStyle(
                            color: caseMuted,
                            fontSize: 10,
                          ),
                        ),
                        if (activity.evidence != null) ...[
                          const SizedBox(height: 10),
                          Text(
                            'Captured evidence · sequence ${activity.evidence!.sequence}',
                            style: const TextStyle(
                              color: caseMuted,
                              fontSize: 10,
                            ),
                          ),
                          const SizedBox(height: 7),
                          _EvidenceReadings(
                            readings: activity.evidence!.readings,
                          ),
                        ],
                      ],
                    ),
                  ),
                ],
              ),
            ),
      ],
    ),
  );
}
