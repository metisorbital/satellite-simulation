import 'package:flutter/foundation.dart';
import '../api/viewer_client.dart';
import '../scene/playback.dart';

/// Owns the mock operator session independently of mission telemetry.
class OperatorSession extends ChangeNotifier {
  OperatorSession({ViewerClient? client}) : _client = client ?? ViewerClient();
  final ViewerClient _client;
  JsonMap? bootstrap;
  String? error;
  bool restoring = true;
  bool busy = false;
  bool logoutPending = false;
  String? _logoutToken;
  bool _disposed = false;
  int _generation = 0;

  bool _current(int generation) => !_disposed && generation == _generation;

  JsonMap _operatorSession(JsonMap response) {
    if (response['operator'] is! Map || response['csrf_token'] is! String) {
      throw const ViewerRequestException(
        'Please log in with a demo operator.',
        401,
      );
    }
    return response;
  }

  Future<void> restore() async {
    final generation = ++_generation;
    restoring = true;
    error = null;
    notifyListeners();
    try {
      final response = await _client.request('/v1/viewer/session');
      if (_current(generation)) bootstrap = _operatorSession(response);
    } catch (exception) {
      if (_current(generation)) {
        bootstrap = null;
        if (exception is! ViewerRequestException ||
            exception.statusCode != 401) {
          error =
              'Could not restore your session. Check the connection and try again.';
        }
      }
    } finally {
      if (_current(generation)) {
        restoring = false;
        notifyListeners();
      }
    }
  }

  Future<void> login(String login, String password) async {
    if (_disposed || busy || restoring || logoutPending) return;
    final generation = ++_generation;
    busy = true;
    error = null;
    notifyListeners();
    try {
      final response = await _client.request(
        '/v1/viewer/login',
        body: {'login': login.trim(), 'password': password},
        timeout: const Duration(minutes: 3),
      );
      if (_current(generation)) bootstrap = _operatorSession(response);
    } catch (exception) {
      if (_current(generation)) {
        error = exception is ViewerRequestException
            ? exception.message
            : 'Could not log in. Check the connection and try again.';
      }
    } finally {
      if (_current(generation)) {
        busy = false;
        notifyListeners();
      }
    }
  }

  Future<void> logout({String? csrfToken}) async {
    if (_disposed || busy) return;
    _logoutToken ??= csrfToken ?? bootstrap?['csrf_token'] as String?;
    final generation = ++_generation;
    bootstrap = null;
    logoutPending = true;
    busy = true;
    error = null;
    notifyListeners();
    try {
      await _client.request(
        '/v1/viewer/logout',
        body: {},
        csrfToken: _logoutToken,
      );
      if (_current(generation)) {
        logoutPending = false;
        _logoutToken = null;
      }
    } catch (exception) {
      if (_current(generation)) {
        if (exception is ViewerRequestException &&
            exception.statusCode == 401) {
          logoutPending = false;
          _logoutToken = null;
        } else {
          error =
              'Log out did not finish. Retry to end this operator’s demo session.';
        }
      }
    } finally {
      if (_current(generation)) {
        busy = false;
        notifyListeners();
      }
    }
  }

  void expire() {
    if (_disposed) return;
    _generation++;
    bootstrap = null;
    busy = false;
    restoring = false;
    error = 'Your demo session expired. Log in to continue.';
    notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    _generation++;
    _client.close();
    super.dispose();
  }
}
