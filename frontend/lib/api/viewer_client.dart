import 'dart:convert';
import 'dart:math';
import 'package:http/http.dart' as http;
import '../scene/playback.dart';

/// A failed viewer request with its HTTP status preserved for session expiry.
class ViewerRequestException implements Exception {
  const ViewerRequestException(this.message, this.statusCode);
  final String message;
  final int statusCode;
  @override
  String toString() => message;
}

/// Same-origin JSON transport. Demo passwords are sent only in the login body.
class ViewerClient {
  ViewerClient({http.Client? client, Uri? baseUri})
    : _client = client ?? http.Client(),
      _baseUri = baseUri ?? Uri.base;

  final http.Client _client;
  final Uri _baseUri;

  Future<JsonMap> request(
    String path, {
    JsonMap? body,
    String? csrfToken,
  }) async {
    final uri = _baseUri.resolve(path);
    final response =
        await (body == null
                ? _client.get(uri)
                : _client.post(
                    uri,
                    headers: {
                      'Content-Type': 'application/json',
                      'X-CSRF-Token': ?csrfToken,
                      'Idempotency-Key':
                          '${DateTime.now().microsecondsSinceEpoch}-${Random.secure().nextInt(0x7fffffff)}',
                    },
                    body: jsonEncode(body),
                  ))
            .timeout(const Duration(seconds: 20));
    dynamic decoded;
    try {
      decoded = jsonDecode(response.body);
    } on FormatException {
      throw ViewerRequestException(
        'The mission service is unavailable. Please try again.',
        response.statusCode,
      );
    }
    if (response.statusCode >= 400) {
      final detail = decoded is Map ? decoded['detail'] : null;
      final message = decoded is Map && decoded['message'] is String
          ? decoded['message'] as String
          : detail is String
          ? detail
          : detail is Map && detail['message'] is String
          ? detail['message'] as String
          : 'Request failed (${response.statusCode}). Please try again.';
      throw ViewerRequestException(message, response.statusCode);
    }
    if (decoded is! Map) {
      throw const ViewerRequestException(
        'Unexpected mission service response.',
        502,
      );
    }
    return Map<String, dynamic>.from(decoded);
  }

  void close() => _client.close();
}
