import 'package:flutter/material.dart';

const caseBackground = Color(0xff070d15);
const casePanel = Color(0xff0d151f);
const caseLine = Color(0xff202a36);
const caseMint = Color(0xff95cfbc);
const caseGold = Color(0xffc7b985);
const caseText = Color(0xffd4dfe8);
const caseMuted = Color(0xff94a4b7);

/// A compact status treatment used by the operator case workflow.
class CaseBadge extends StatelessWidget {
  const CaseBadge({super.key, required this.label, this.tone = CaseTone.quiet});

  final String label;
  final CaseTone tone;

  @override
  Widget build(BuildContext context) {
    final colors = switch (tone) {
      CaseTone.mint => (caseMint, const Color(0xff10221e)),
      CaseTone.gold => (caseGold, const Color(0xff211e15)),
      CaseTone.red => (const Color(0xffed9c96), const Color(0xff28191a)),
      CaseTone.quiet => (caseMuted, const Color(0xff121d29)),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: colors.$2,
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: colors.$1.withValues(alpha: .32)),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: colors.$1,
          fontSize: 10,
          fontWeight: FontWeight.w700,
          letterSpacing: .35,
        ),
      ),
    );
  }
}

enum CaseTone { mint, gold, red, quiet }

/// Surface shared by the responsive case panels.
class CasePanel extends StatelessWidget {
  const CasePanel({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(22),
  });

  final Widget child;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) => Container(
    padding: padding,
    decoration: BoxDecoration(
      color: casePanel,
      borderRadius: BorderRadius.circular(9),
      border: Border.all(color: caseLine),
    ),
    child: child,
  );
}

/// Formats server timestamps without treating them as local mission time.
String caseTime(String value) {
  final parsed = DateTime.tryParse(value);
  if (parsed == null) return value;
  return '${parsed.toUtc().toIso8601String().replaceFirst('T', ' ').split('.').first} UTC';
}

String caseLabel(String value) => value.replaceAll('_', ' ');

CaseTone casePriorityTone(String priority) => switch (priority) {
  'urgent' => CaseTone.red,
  'review' => CaseTone.gold,
  _ => CaseTone.quiet,
};

/// A concise asynchronous or unavailable data state.
class CaseStateMessage extends StatelessWidget {
  const CaseStateMessage({
    super.key,
    required this.icon,
    required this.title,
    required this.message,
    this.action,
  });

  final IconData icon;
  final String title;
  final String message;
  final Widget? action;

  @override
  Widget build(BuildContext context) => CasePanel(
    child: Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 28, horizontal: 16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 30, color: caseMuted),
            const SizedBox(height: 12),
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 7),
            Text(
              message,
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: caseMuted,
                fontSize: 12,
                height: 1.5,
              ),
            ),
            if (action != null) ...[const SizedBox(height: 15), action!],
          ],
        ),
      ),
    ),
  );
}

/// Standard form decoration that keeps dark input controls legible.
InputDecoration caseInputDecoration(
  String label, {
  String? hint,
  String? helper,
}) => InputDecoration(
  labelText: label,
  hintText: hint,
  helperText: helper,
  alignLabelWithHint: true,
  filled: true,
  fillColor: caseBackground,
  labelStyle: const TextStyle(color: caseMuted),
  hintStyle: const TextStyle(color: Color(0xff687889)),
  enabledBorder: OutlineInputBorder(
    borderRadius: BorderRadius.circular(6),
    borderSide: const BorderSide(color: Color(0xff2b3948)),
  ),
  focusedBorder: OutlineInputBorder(
    borderRadius: BorderRadius.circular(6),
    borderSide: const BorderSide(color: caseMint),
  ),
);
