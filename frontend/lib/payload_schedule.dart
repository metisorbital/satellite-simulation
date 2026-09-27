import 'package:flutter/material.dart';

int? _wholeSeconds(String value) {
  final text = value.trim();
  return RegExp(r'^[0-9]+$').hasMatch(text) ? int.tryParse(text) : null;
}

/// Editable times and recurrence for one payload-active operation.
class PayloadTaskDraft {
  PayloadTaskDraft._({
    required int startS,
    required int durationS,
    required this.repeatEveryOrbit,
    this.taskFields = const {},
  }) : startController = TextEditingController(text: '$startS'),
       durationController = TextEditingController(text: '$durationS');

  /// First activation time in simulated seconds from run start.
  final TextEditingController startController;

  /// Time spent in payload-active mode for each activation, in seconds.
  final TextEditingController durationController;

  /// Whether the backend repeats this activation on each nominal orbit.
  bool repeatEveryOrbit;

  /// Task fields this editor does not change, such as `added_load_w`, `label` and `min_start_soc`.
  final Map<String, dynamic> taskFields;

  String? _validateStart(String? value) => _wholeSeconds(value ?? '') == null
      ? 'Use a whole number of seconds, 0 or greater'
      : null;

  String? _validateDuration(String? value, int runDurationS) {
    final duration = _wholeSeconds(value ?? '');
    if (duration == null || duration < 1) {
      return 'Use a whole number of seconds greater than 0';
    }
    final start = _wholeSeconds(startController.text);
    if (start != null && start + duration > runDurationS) {
      return 'First activation must end by $runDurationS s';
    }
    return null;
  }

  void _dispose() {
    startController.dispose();
    durationController.dispose();
  }
}

/// Holds one satellite's payload edits while preserving its other operations.
class PayloadScheduleDraft {
  /// Hydrates every payload activation without changing other operation modes.
  PayloadScheduleDraft.fromOperations(List<dynamic> operations) {
    for (final raw in operations) {
      final operation = Map<String, dynamic>.from(raw as Map);
      if (operation['mode'] == 'payload_active') {
        final startS = operation['start_s'] as int;
        final endS = operation['end_s'] as int;
        final task = PayloadTaskDraft._(
          startS: startS,
          durationS: endS - startS,
          repeatEveryOrbit: operation['repeat'] == 'orbit',
          taskFields: {
            for (final key in const ['added_load_w', 'label', 'min_start_soc'])
              if (operation[key] != null) key: operation[key],
          },
        );
        tasks.add(task);
        _allocatedTasks.add(task);
      } else {
        _otherOperations.add(operation);
      }
    }
    enabled = tasks.isNotEmpty;
  }

  /// Whether to include the payload tasks when saving this satellite.
  bool enabled = false;

  /// Active task rows; values remain available when scheduling is disabled.
  final List<PayloadTaskDraft> tasks = [];

  final List<PayloadTaskDraft> _allocatedTasks = [];
  final List<Map<String, dynamic>> _otherOperations = [];

  /// Adds a five-minute activation at run start that repeats every orbit.
  void addTask() {
    final task = PayloadTaskDraft._(
      startS: 0,
      durationS: 300,
      repeatEveryOrbit: true,
    );
    tasks.add(task);
    _allocatedTasks.add(task);
  }

  /// Removes a task while retaining its controllers until the editor closes.
  void removeTask(PayloadTaskDraft task) => tasks.remove(task);

  /// Validates active tasks and first windows; recurrence is checked by the API.
  String? validate(int runDurationS) {
    if (!enabled) return null;
    if (tasks.isEmpty) {
      return 'Add a payload task or turn off payload scheduling.';
    }
    final windows = <({int start, int end})>[];
    for (var index = 0; index < tasks.length; index++) {
      final task = tasks[index];
      final startIssue = task._validateStart(task.startController.text);
      if (startIssue != null) {
        return 'Payload task ${index + 1}: $startIssue.';
      }
      final durationIssue = task._validateDuration(
        task.durationController.text,
        runDurationS,
      );
      if (durationIssue != null) {
        return 'Payload task ${index + 1}: $durationIssue.';
      }
      final start = _wholeSeconds(task.startController.text)!;
      final end = start + _wholeSeconds(task.durationController.text)!;
      for (var previous = 0; previous < windows.length; previous++) {
        final window = windows[previous];
        if (start < window.end && window.start < end) {
          return 'Payload task ${index + 1} overlaps payload task ${previous + 1}.';
        }
      }
      for (final operation in _otherOperations) {
        final otherStart = operation['start_s'] as int;
        final otherEnd = operation['end_s'] as int;
        if (start < otherEnd && otherStart < end) {
          return 'Payload task ${index + 1} overlaps an existing '
              '${operation['mode']} operation.';
        }
      }
      windows.add((start: start, end: end));
    }
    return null;
  }

  /// Serializes enabled, validated tasks alongside unchanged other operations.
  List<Map<String, dynamic>> toOperations() => [
    for (final operation in _otherOperations)
      Map<String, dynamic>.from(operation),
    if (enabled)
      for (final task in tasks)
        {
          'start_s': _wholeSeconds(task.startController.text)!,
          'end_s':
              _wholeSeconds(task.startController.text)! +
              _wholeSeconds(task.durationController.text)!,
          'mode': 'payload_active',
          'repeat': task.repeatEveryOrbit ? 'orbit' : null,
          ...task.taskFields,
        },
  ];

  /// Releases all task controllers after the editor and its fields unmount.
  void dispose() {
    for (final task in _allocatedTasks) {
      task._dispose();
    }
  }
}

/// Per-satellite payload schedule controls hosted by the constellation form.
class PayloadScheduleEditor extends StatelessWidget {
  /// Builds controls for a stable [draft] using the configured run duration.
  const PayloadScheduleEditor({
    super.key,
    required this.draft,
    required this.runDurationS,
    required this.onChanged,
  });

  /// Satellite-specific draft retained by the containing editor.
  final PayloadScheduleDraft draft;

  /// Current run length in simulated seconds, used for first-window validation.
  final int runDurationS;

  /// Rebuilds the containing editor after draft changes.
  final VoidCallback onChanged;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          'PAYLOAD TASKS',
          style: theme.textTheme.labelSmall?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text('Schedule payload operations'),
          value: draft.enabled,
          onChanged: (enabled) {
            draft.enabled = enabled;
            if (enabled && draft.tasks.isEmpty) draft.addTask();
            onChanged();
          },
        ),
        Text(
          'Times are simulated seconds from run start. The mode selected above '
          'applies between scheduled windows. Payload tasks use the '
          'payload-active total load configured under Power System.',
          style: theme.textTheme.bodySmall?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
        if (draft.enabled) ...[
          for (var index = 0; index < draft.tasks.length; index++)
            _taskFields(context, draft.tasks[index], index),
          const SizedBox(height: 8),
          Align(
            alignment: Alignment.centerLeft,
            child: OutlinedButton.icon(
              onPressed: () {
                draft.addTask();
                onChanged();
              },
              icon: const Icon(Icons.add, size: 18),
              label: const Text('Add payload task'),
            ),
          ),
        ],
      ],
    );
  }

  Widget _taskFields(
    BuildContext context,
    PayloadTaskDraft task,
    int index,
  ) => Padding(
    key: ObjectKey(task),
    padding: const EdgeInsets.only(top: 12),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                'Payload task ${index + 1}',
                style: Theme.of(context).textTheme.titleSmall,
              ),
            ),
            IconButton(
              tooltip: 'Remove payload task ${index + 1}',
              onPressed: () {
                draft.removeTask(task);
                onChanged();
              },
              icon: const Icon(Icons.delete_outline, size: 20),
            ),
          ],
        ),
        TextFormField(
          controller: task.startController,
          decoration: const InputDecoration(
            labelText: 'Start time (s)',
            isDense: true,
          ),
          keyboardType: TextInputType.number,
          validator: task._validateStart,
          onChanged: (_) => onChanged(),
        ),
        const SizedBox(height: 12),
        TextFormField(
          controller: task.durationController,
          decoration: const InputDecoration(
            labelText: 'Duration (s)',
            helperText: '300 s = 5 minutes per activation',
            isDense: true,
          ),
          keyboardType: TextInputType.number,
          validator: (value) => task._validateDuration(value, runDurationS),
          onChanged: (_) => onChanged(),
        ),
        CheckboxListTile(
          contentPadding: EdgeInsets.zero,
          controlAffinity: ListTileControlAffinity.leading,
          title: const Text('Repeat every orbit'),
          subtitle: Text(
            task.repeatEveryOrbit
                ? 'Repeats from the first start on this satellite’s nominal '
                      'orbit cadence; the final activation may be shortened '
                      'by run end.'
                : 'Runs once at the start time above.',
          ),
          value: task.repeatEveryOrbit,
          onChanged: (repeat) {
            if (repeat == null) return;
            task.repeatEveryOrbit = repeat;
            onChanged();
          },
        ),
      ],
    ),
  );
}
