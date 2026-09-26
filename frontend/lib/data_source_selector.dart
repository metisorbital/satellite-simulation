import 'package:flutter/material.dart';
import 'package:pointer_interceptor/pointer_interceptor.dart';

import 'api/mission.dart';

/// Selects the producer for a new run while keeping run controls unchanged.
class DataSourceSelector extends StatelessWidget {
  const DataSourceSelector({
    super.key,
    required this.mission,
    this.compact = false,
  });

  final Mission mission;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final currentDataset = mission.status?['dataset_id'] as String?;
    final value = mission.isObserved ? 'dataset:$currentDataset' : 'physics';
    final enabled = !mission.busy && mission.canReplaceRun;
    final guidance = !mission.canReplaceRun && mission.canControl
        ? 'Stop this run to change its data source.'
        : mission.isObserved
        ? 'Start run replays from the selected source time. Choose a position in Overview.'
        : 'Start run generates measurements from the configured physics model.';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Icon(Icons.storage_outlined, size: 15),
            const SizedBox(width: 9),
            const Text('Data source', style: TextStyle(fontSize: 11)),
            const SizedBox(width: 12),
            Expanded(
              child: DropdownButtonHideUnderline(
                child: DropdownButton<String>(
                  value: value,
                  isExpanded: true,
                  isDense: true,
                  style: const TextStyle(
                    fontSize: 12,
                    color: Color(0xffd4dfe8),
                  ),
                  items: [
                    DropdownMenuItem(
                      value: 'physics',
                      child: PointerInterceptor(
                        child: const Text('Physics simulation · synthetic'),
                      ),
                    ),
                    for (final dataset in mission.datasets)
                      DropdownMenuItem(
                        value: 'dataset:${dataset['dataset_id']}',
                        child: PointerInterceptor(
                          child: Text(
                            'Real data · ${dataset['title'] ?? dataset['dataset_title'] ?? dataset['dataset_id']}',
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ),
                    if (mission.isObserved &&
                        !mission.datasets.any(
                          (dataset) => dataset['dataset_id'] == currentDataset,
                        ))
                      DropdownMenuItem(
                        value: value,
                        child: Text(
                          'Real data · ${mission.status?['dataset_title'] ?? currentDataset}',
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    if (mission.datasets.isEmpty && !mission.isObserved)
                      DropdownMenuItem(
                        value: 'unavailable',
                        enabled: false,
                        child: Text(
                          mission.datasetsLoading
                              ? 'Loading recorded datasets…'
                              : 'Real data · no dataset available',
                        ),
                      ),
                  ],
                  onChanged: !enabled
                      ? null
                      : (selected) {
                          if (selected == null) return;
                          if (selected == 'physics') {
                            mission.selectSource('physics');
                          } else if (selected.startsWith('dataset:')) {
                            mission.selectSource(
                              'satellitecots',
                              datasetId: selected.substring(8),
                            );
                          }
                        },
                ),
              ),
            ),
            if (compact)
              Padding(
                padding: const EdgeInsets.only(left: 8),
                child: Tooltip(
                  message: guidance,
                  child: const Icon(Icons.info_outline, size: 15),
                ),
              ),
            if (mission.datasetsError != null)
              IconButton(
                tooltip: 'Retry loading recorded datasets',
                onPressed: mission.datasetsLoading
                    ? null
                    : mission.loadDatasets,
                icon: const Icon(Icons.refresh, size: 17),
              ),
          ],
        ),
        if (!compact) ...[
          const SizedBox(height: 7),
          Text(
            guidance,
            style: const TextStyle(fontSize: 10, color: Color(0xff94a4b7)),
          ),
        ],
        if (mission.datasetsError != null)
          const Padding(
            padding: EdgeInsets.only(top: 5),
            child: Text(
              'Recorded dataset availability could not be loaded. Use refresh to retry.',
              style: TextStyle(fontSize: 10, color: Color(0xffc7b985)),
            ),
          ),
      ],
    );
  }
}
