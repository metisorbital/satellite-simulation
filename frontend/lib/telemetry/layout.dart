import 'dart:convert';

import 'package:flutter/material.dart';

import 'layout_storage.dart';
import 'panels.dart';

const _storageKey = 'metis.telemetry.layout.v1';

/// User preferences for arranging telemetry panels.
///
/// The layout stores presentation preferences only. It never stores telemetry
/// values, simulation state, or user identity.
class TelemetryLayout {
  TelemetryLayout({
    Map<String, List<String>> orderByTab = const {},
    Map<String, List<String>> hiddenByTab = const {},
    Map<String, bool> wideByPanel = const {},
    Map<String, bool> tallByPanel = const {},
    this.columns = 2,
  }) : orderByTab = {
         for (final entry in orderByTab.entries)
           entry.key: List<String>.of(entry.value),
       },
       hiddenByTab = {
         for (final entry in hiddenByTab.entries)
           entry.key: List<String>.of(entry.value),
       },
       wideByPanel = Map<String, bool>.of(wideByPanel),
       tallByPanel = Map<String, bool>.of(tallByPanel) {
    columns = columns.clamp(1, 3).toInt();
  }

  /// Panel order for each tab, keyed by tab and panel title.
  final Map<String, List<String>> orderByTab;

  /// Hidden panel titles for each tab.
  final Map<String, List<String>> hiddenByTab;

  /// Width preference keyed by panel title.
  final Map<String, bool> wideByPanel;

  /// Height preference keyed by panel title.
  final Map<String, bool> tallByPanel;

  /// Number of dashboard columns, constrained to one through three.
  int columns;

  /// Loads persisted presentation preferences, returning defaults on bad data.
  static TelemetryLayout load() {
    try {
      final raw = readTelemetryLayout(_storageKey);
      if (raw == null || raw.isEmpty) return TelemetryLayout();
      final decoded = jsonDecode(raw);
      if (decoded is! Map<String, dynamic> || decoded['version'] != 1) {
        return TelemetryLayout();
      }
      return TelemetryLayout(
        orderByTab: _readStringLists(decoded['orderByTab']),
        hiddenByTab: _readStringLists(decoded['hiddenByTab']),
        wideByPanel: _readBoolMap(decoded['wideByPanel']),
        tallByPanel: _readBoolMap(decoded['tallByPanel']),
        columns: decoded['columns'] is int ? decoded['columns'] as int : 2,
      );
    } catch (_) {
      return TelemetryLayout();
    }
  }

  /// Returns visible panels in the saved tab order.
  List<TelemetryPanel> visiblePanels(String tab, List<TelemetryPanel> panels) {
    final byTitle = {for (final panel in panels) panel.title: panel};
    final order = _normalizedOrder(tab, panels);
    final hidden = hiddenByTab[tab]?.toSet() ?? <String>{};
    return [
      for (final title in order)
        if (!hidden.contains(title))
          if (byTitle[title] != null) byTitle[title]!,
    ];
  }

  /// Whether [panel] should span two dashboard columns.
  bool isWide(TelemetryPanel panel) => wideByPanel[panel.title] ?? false;

  /// Whether [panel] should use the tall presentation height.
  bool isTall(TelemetryPanel panel) => tallByPanel[panel.title] ?? false;

  /// Sets whether [panel] spans two dashboard columns.
  void setWide(TelemetryPanel panel, bool value) {
    _setPreference(wideByPanel, panel.title, value);
  }

  /// Sets whether [panel] uses the tall presentation height.
  void setTall(TelemetryPanel panel, bool value) {
    _setPreference(tallByPanel, panel.title, value);
  }

  /// Saves layout preferences to browser storage when available.
  void save() {
    final value = jsonEncode({
      'version': 1,
      'columns': columns.clamp(1, 3).toInt(),
      'orderByTab': orderByTab,
      'hiddenByTab': hiddenByTab,
      'wideByPanel': wideByPanel,
      'tallByPanel': tallByPanel,
    });
    writeTelemetryLayout(_storageKey, value);
  }

  List<String> _normalizedOrder(String tab, List<TelemetryPanel> panels) {
    final titles = panels.map((panel) => panel.title).toList();
    final existing = orderByTab[tab] ?? const <String>[];
    return [
      ...existing.where(titles.contains).toSet(),
      ...titles.where((title) => !existing.contains(title)),
    ];
  }

  void _setPreference(Map<String, bool> preferences, String title, bool value) {
    if (value) {
      preferences[title] = true;
    } else {
      preferences.remove(title);
    }
  }

  static Map<String, List<String>> _readStringLists(Object? value) {
    if (value is! Map) return {};
    return {
      for (final entry in value.entries)
        if (entry.key is String && entry.value is List)
          entry.key as String: [
            for (final item in entry.value as List)
              if (item is String) item,
          ],
    };
  }

  static Map<String, bool> _readBoolMap(Object? value) {
    if (value is! Map) return {};
    return {
      for (final entry in value.entries)
        if (entry.key is String && entry.value is bool)
          entry.key as String: entry.value as bool,
    };
  }
}

/// Opens the editor and applies changes only when the user selects Apply.
Future<bool> editTelemetryLayout(
  BuildContext context,
  TelemetryLayout layout,
  String tab,
  List<TelemetryPanel> panels,
) async {
  final result = await showDialog<_LayoutDraft>(
    context: context,
    builder: (context) =>
        _LayoutEditorDialog(tab: tab, panels: panels, layout: layout),
  );
  if (result == null) return false;

  layout.orderByTab[tab] = result.panels.map((panel) => panel.title).toList();
  layout.hiddenByTab[tab] = [
    for (var index = 0; index < result.panels.length; index++)
      if (!result.visible[index]) result.panels[index].title,
  ];
  for (var index = 0; index < result.panels.length; index++) {
    layout.setWide(result.panels[index], result.wide[index]);
    layout.setTall(result.panels[index], result.tall[index]);
  }
  layout.columns = result.columns;
  layout.save();
  return true;
}

class _LayoutDraft {
  const _LayoutDraft({
    required this.panels,
    required this.visible,
    required this.wide,
    required this.tall,
    required this.columns,
  });

  final List<TelemetryPanel> panels;
  final List<bool> visible;
  final List<bool> wide;
  final List<bool> tall;
  final int columns;
}

class _LayoutEditorDialog extends StatefulWidget {
  const _LayoutEditorDialog({
    required this.tab,
    required this.panels,
    required this.layout,
  });

  final String tab;
  final List<TelemetryPanel> panels;
  final TelemetryLayout layout;

  @override
  State<_LayoutEditorDialog> createState() => _LayoutEditorDialogState();
}

class _LayoutEditorDialogState extends State<_LayoutEditorDialog> {
  late List<TelemetryPanel> _panels;
  late List<bool> _visible;
  late List<bool> _wide;
  late List<bool> _tall;
  late int _columns;

  @override
  void initState() {
    super.initState();
    final savedOrder = widget.layout.orderByTab[widget.tab] ?? const [];
    final byTitle = {for (final panel in widget.panels) panel.title: panel};
    _panels = [
      ...savedOrder
          .where(byTitle.containsKey)
          .toSet()
          .map((title) => byTitle[title]!),
      ...widget.panels.where((panel) => !savedOrder.contains(panel.title)),
    ];
    final hidden = widget.layout.hiddenByTab[widget.tab]?.toSet() ?? <String>{};
    _visible = _panels.map((panel) => !hidden.contains(panel.title)).toList();
    _wide = _panels.map(widget.layout.isWide).toList();
    _tall = _panels.map(widget.layout.isTall).toList();
    _columns = widget.layout.columns;
  }

  @override
  Widget build(BuildContext context) {
    final media = MediaQuery.sizeOf(context);
    // Keep the dialog inside the viewport when the dashboard is shown on a
    // phone or in a short browser window.  The explicit inset matches the
    // available width used below instead of relying on AlertDialog's larger
    // desktop margin.
    final width = media.width < 560 ? media.width - 32 : 520.0;
    final maxHeight = (media.height - 32).clamp(220, 620).toDouble();
    return AlertDialog(
      insetPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      backgroundColor: telemetrySurface,
      title: Text('Edit ${widget.tab} dashboard'),
      content: SizedBox(
        width: width.clamp(220, 520).toDouble(),
        height: maxHeight,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                const Expanded(child: Text('Dashboard columns')),
                DropdownButton<int>(
                  value: _columns,
                  dropdownColor: telemetrySurface,
                  items: [
                    for (var count = 1; count <= 3; count++)
                      DropdownMenuItem(value: count, child: Text('$count')),
                  ],
                  onChanged: (value) => setState(() => _columns = value ?? 2),
                ),
              ],
            ),
            const Divider(color: telemetryBorder),
            Expanded(
              child: ReorderableListView.builder(
                itemCount: _panels.length,
                onReorderItem: (oldIndex, newIndex) {
                  setState(() {
                    final panel = _panels.removeAt(oldIndex);
                    final visible = _visible.removeAt(oldIndex);
                    final wide = _wide.removeAt(oldIndex);
                    final tall = _tall.removeAt(oldIndex);
                    _panels.insert(newIndex, panel);
                    _visible.insert(newIndex, visible);
                    _wide.insert(newIndex, wide);
                    _tall.insert(newIndex, tall);
                  });
                },
                itemBuilder: (context, index) {
                  final panel = _panels[index];
                  return CheckboxListTile(
                    key: ValueKey(panel.title),
                    dense: true,
                    activeColor: telemetryAccent,
                    value: _visible[index],
                    title: Text(
                      panel.title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    subtitle: Text(
                      '${_wide[index] ? 'Wide' : 'Standard'} · ${_tall[index] ? 'Tall' : 'Compact'}',
                      style: const TextStyle(
                        color: telemetryMuted,
                        fontSize: 12,
                      ),
                    ),
                    onChanged: (value) =>
                        setState(() => _visible[index] = value ?? true),
                  );
                },
              ),
            ),
            const SizedBox(height: 6),
            Text(
              'Use each panel menu to change its size.',
              style: Theme.of(
                context,
              ).textTheme.bodySmall?.copyWith(color: telemetryMuted),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => setState(() {
            _panels = List.of(widget.panels);
            _visible = List<bool>.filled(_panels.length, true);
            _wide = List<bool>.filled(_panels.length, false);
            _tall = List<bool>.filled(_panels.length, false);
            _columns = 2;
          }),
          child: const Text('Reset defaults'),
        ),
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(
            context,
            _LayoutDraft(
              panels: List.of(_panels),
              visible: List.of(_visible),
              wide: List.of(_wide),
              tall: List.of(_tall),
              columns: _columns,
            ),
          ),
          child: const Text('Apply'),
        ),
      ],
    );
  }
}
