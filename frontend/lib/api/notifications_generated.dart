// Generated from Pydantic v2 contracts. Do not edit by hand.
// dart format off
// Regenerate: uv run python scripts/generate_contracts.py
// ignore_for_file: non_constant_identifier_names, unnecessary_non_null_assertion, prefer_null_aware_operators, use_null_aware_elements

/// Explicit acknowledgement of one visible notification version.
class MarkNotificationReadRequest {
  const MarkNotificationReadRequest({
    required this.key,
    required this.version,
  });

  final String key;
  final int version;

  factory MarkNotificationReadRequest.fromJson(Map<String, dynamic> json) => MarkNotificationReadRequest(
    key: json['key'] as String,
    version: json['version'] as int,
  );

  Map<String, dynamic> toJson() => {
    'key': key,
    'version': version,
  };
}

/// Visible items and their per-operator unread count.
class NotificationList {
  const NotificationList({
    required this.items,
    required this.unread_count,
  });

  final List<OperatorNotification> items;
  final int unread_count;

  factory NotificationList.fromJson(Map<String, dynamic> json) => NotificationList(
    items: (json['items'] as List).map((item) => OperatorNotification.fromJson(Map<String, dynamic>.from(item as Map))).toList(),
    unread_count: json['unread_count'] as int,
  );

  Map<String, dynamic> toJson() => {
    'items': items.map((item) => item.toJson()).toList(),
    'unread_count': unread_count,
  };
}

/// One visible warning or open investigation notification.
class OperatorNotification {
  const OperatorNotification({
    required this.key,
    required this.version,
    required this.category,
    required this.satellite_id,
    required this.title,
    required this.summary,
    required this.unread,
  });

  final String key;
  final int version;
  final String category;
  final String satellite_id;
  final String title;
  final String summary;
  final bool unread;

  factory OperatorNotification.fromJson(Map<String, dynamic> json) => OperatorNotification(
    key: json['key'] as String,
    version: json['version'] as int,
    category: json['category'] as String,
    satellite_id: json['satellite_id'] as String,
    title: json['title'] as String,
    summary: json['summary'] as String,
    unread: json['unread'] as bool,
  );

  Map<String, dynamic> toJson() => {
    'key': key,
    'version': version,
    'category': category,
    'satellite_id': satellite_id,
    'title': title,
    'summary': summary,
    'unread': unread,
  };
}
