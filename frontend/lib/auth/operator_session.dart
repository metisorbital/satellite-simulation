import 'package:flutter/foundation.dart';

import '../api/viewer_client.dart';
import '../scene/playback.dart';

/// Owns the demo operator session independently of mission telemetry.
class OperatorSession extends ChangeNotifier {
  OperatorSession({ViewerClient? client}) : _client = client ?? ViewerClient();

  final ViewerClient _client;
  JsonMap? bootstrap;
  String? error;
  bool restoring = true;
  bool busy = false;
  bool logoutPending = false;
  String? _logoutToken;
  String? _targetLogin;
  bool _disposed = false;
  int _generation = 0;

  bool _current(int generation) => !_disposed && generation == _generation;

  JsonMap _operatorSession(JsonMap response) {
    if (response['operator'] is! Map || response['csrf_token'] is! String) {
      throw const ViewerRequestException(
        'The mission service returned an invalid operator session.',
        502,
      );
    }
    return response;
  }

  /// Resume the current workspace or open operator1 on a first visit.
  Future<void> restore() async {
    if (_disposed || busy || logoutPending) return;
    final generation = ++_generation;
    restoring = true;
    error = null;
    notifyListeners();
    try {
      JsonMap response;
      try {
        response = await _client.request('/v1/viewer/session');
      } on ViewerRequestException catch (exception) {
        if (exception.statusCode != 401) rethrow;
        response = await _client.request(
          '/v1/viewer/login',
          body: {'login': 'operator1', 'password': 'demo'},
          timeout: const Duration(minutes: 3),
        );
      }
      if (_current(generation)) bootstrap = _operatorSession(response);
    } catch (_) {
      if (_current(generation)) {
        bootstrap = null;
        error =
            'Could not open the operator workspace. Check the connection and try again.';
      }
    } finally {
      if (_current(generation)) {
        restoring = false;
        notifyListeners();
      }
    }
  }

  /// End the active demo session and open another operator's workspace.
  Future<void> switchOperator(String login, {String? csrfToken}) async {
    if (_disposed || busy || restoring || logoutPending || bootstrap == null) {
      return;
    }
    if (login == (bootstrap!['operator'] as Map)['login']) return;
    _targetLogin = login;
    _logoutToken = csrfToken ?? bootstrap!['csrf_token'] as String;
    // Remove the old mission tree before either request can complete.
    bootstrap = null;
    logoutPending = true;
    error = null;
    notifyListeners();
    await _finishSwitch();
  }

  /// Retry the failed step of a switch, or reopen the default workspace.
  Future<void> retry() async {
    if (_disposed || busy || restoring) return;
    if (_targetLogin != null) {
      await _finishSwitch();
    } else {
      await restore();
    }
  }

  Future<void> _finishSwitch() async {
    if (_disposed || busy || _targetLogin == null) return;
    final generation = ++_generation;
    busy = true;
    error = null;
    notifyListeners();
    try {
      if (logoutPending) {
        try {
          await _client.request(
            '/v1/viewer/logout',
            body: {},
            csrfToken: _logoutToken,
          );
        } on ViewerRequestException catch (exception) {
          if (exception.statusCode != 401) rethrow;
        }
        if (!_current(generation)) return;
        logoutPending = false;
        _logoutToken = null;
      }
      // The endpoint accepts any nonempty password for packaged demo users.
      final response = await _client.request(
        '/v1/viewer/login',
        body: {'login': _targetLogin, 'password': 'demo'},
        timeout: const Duration(minutes: 3),
      );
      if (_current(generation)) {
        bootstrap = _operatorSession(response);
        _targetLogin = null;
      }
    } catch (_) {
      if (_current(generation)) {
        error = logoutPending
            ? 'Could not end the previous session. Check the connection and retry.'
            : 'Could not open $_targetLogin. Check the connection and retry.';
      }
    } finally {
      if (_current(generation)) {
        busy = false;
        notifyListeners();
      }
    }
  }

  /// Discard an expired workspace so a fresh default session can be opened.
  void expire() {
    if (_disposed) return;
    _generation++;
    bootstrap = null;
    busy = false;
    restoring = false;
    logoutPending = false;
    _logoutToken = null;
    _targetLogin = null;
    error = 'The operator session expired. Retry to open the workspace.';
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
