import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:metis_orbital_viewer/api/mission.dart';
import 'package:metis_orbital_viewer/api/viewer_client.dart';
import 'package:metis_orbital_viewer/auth/operator_gate.dart';
import 'package:metis_orbital_viewer/auth/operator_session.dart';
import 'package:metis_orbital_viewer/scene/playback.dart';

JsonMap bootstrap(String login) => {
  'csrf_token': 'csrf-$login',
  'allowed_actions': ['start', 'pause', 'resume', 'stop'],
  'operator': {'user_id': 'user-$login', 'login': login, 'display_name': login},
  'run': {
    'run_id': 'run-$login',
    'status': 'created',
    'epoch_utc': '2026-09-21T00:00:00Z',
    'duration_s': 100,
    'committed_tick': -1,
    'status_revision': 0,
    'committed_at': null,
    'requested_speed': 1,
    'effective_speed': 0,
    'wall_lag_s': 0,
    'satellites': [],
    'source_kind': 'synthetic',
    'model_provenance': {},
    'frame_count': 0,
    'diagnostic': null,
  },
};

http.Response reply(Object body, [int status = 200]) =>
    http.Response(jsonEncode(body), status);
ViewerClient transport(Future<http.Response> Function(http.Request) handler) =>
    ViewerClient(
      client: MockClient(handler),
      baseUri: Uri.parse('http://localhost'),
    );

void main() {
  testWidgets(
    'first visit waits for session then shows login without mission flash',
    (tester) async {
      final response = Completer<http.Response>();
      final paths = <String>[];
      final session = OperatorSession(
        client: transport((request) {
          paths.add(request.url.path);
          return response.future;
        }),
      );
      var missionBuilds = 0;
      await tester.pumpWidget(
        MaterialApp(
          home: OperatorGate(
            session: session,
            missionBuilder: (_, _, _, _) {
              missionBuilds++;
              return const Text('Mission');
            },
          ),
        ),
      );
      expect(find.text('Opening your workspace…'), findsOneWidget);
      expect(missionBuilds, 0);
      response.complete(reply({'detail': 'Log in'}, 401));
      await tester.pumpAndSettle();
      expect(find.text('Operator login'), findsOneWidget);
      expect(missionBuilds, 0);
      expect(paths, ['/v1/viewer/session']);
      expect(session.error, isNull);
      final password = tester.widget<TextFormField>(
        find.widgetWithText(TextFormField, 'Password'),
      );
      expect(password.controller!.text, isEmpty);
      final editable = tester.widget<EditableText>(
        find.descendant(
          of: find.widgetWithText(TextFormField, 'Password'),
          matching: find.byType(EditableText),
        ),
      );
      expect(editable.obscureText, isTrue);
    },
  );

  testWidgets(
    'keyboard login, logout and operator switch create fresh workspace',
    (tester) async {
      final logins = <JsonMap>[];
      final session = OperatorSession(
        client: transport((request) async {
          if (request.url.path.endsWith('/session')) return reply({}, 401);
          if (request.url.path.endsWith('/logout')) {
            expect(request.headers['X-CSRF-Token'], 'rotated-csrf');
            return reply({});
          }
          final body = jsonDecode(request.body) as JsonMap;
          logins.add(body);
          return reply(bootstrap(body['login'] as String));
        }),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: OperatorGate(
            session: session,
            missionBuilder: (_, data, logout, _) => _Workspace(
              login: data['operator']['login'] as String,
              logout: () => logout('rotated-csrf'),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      Future<void> login(String user) async {
        await tester.ensureVisible(find.widgetWithText(ActionChip, user));
        await tester.tap(find.widgetWithText(ActionChip, user));
        await tester.enterText(
          find.widgetWithText(TextFormField, 'Password'),
          'anything',
        );
        await tester.testTextInput.receiveAction(TextInputAction.done);
        await tester.pumpAndSettle();
      }

      await login('operator1');
      expect(find.text('operator1 selection 0'), findsOneWidget);
      await tester.tap(find.text('Select spacecraft'));
      await tester.pump();
      expect(find.text('operator1 selection 1'), findsOneWidget);
      await tester.tap(find.text('Log out'));
      await tester.pumpAndSettle();
      expect(find.text('Operator login'), findsOneWidget);
      await login('operator2');
      expect(find.text('operator2 selection 0'), findsOneWidget);
      expect(find.textContaining('operator1 selection'), findsNothing);
      expect(logins, [
        {'login': 'operator1', 'password': 'anything'},
        {'login': 'operator2', 'password': 'anything'},
      ]);
    },
  );

  testWidgets('failed login is actionable and narrow layout has no overflow', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(360, 780);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final session = OperatorSession(
      client: transport(
        (request) async => request.url.path.endsWith('/session')
            ? reply({}, 401)
            : reply({'detail': 'Unknown demo operator'}, 401),
      ),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: OperatorGate(
          session: session,
          missionBuilder: (_, _, _, _) => const Text('Mission'),
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Login'),
      'unknown',
    );
    await tester.enterText(
      find.widgetWithText(TextFormField, 'Password'),
      'test',
    );
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pumpAndSettle();
    expect(find.text('Unknown demo operator'), findsOneWidget);
    expect(find.text('Mission'), findsNothing);
    expect(tester.takeException(), isNull);
    expect(
      tester
          .widget<TextFormField>(find.widgetWithText(TextFormField, 'Password'))
          .controller!
          .text,
      isEmpty,
    );
  });

  test(
    'failed logout clears workspace and requires retry before next login',
    () async {
      var logoutRequests = 0;
      var loginRequests = 0;
      final session = OperatorSession(
        client: transport((request) async {
          if (request.url.path.endsWith('/session')) {
            return reply(bootstrap('operator1'));
          }
          if (request.url.path.endsWith('/logout')) {
            expect(request.headers['X-CSRF-Token'], 'rotated');
            return ++logoutRequests == 1 ? reply({}, 503) : reply({});
          }
          loginRequests++;
          return reply(bootstrap('operator2'));
        }),
      );
      addTearDown(session.dispose);
      await session.restore();
      await session.logout(csrfToken: 'rotated');
      expect(session.bootstrap, isNull);
      expect(session.logoutPending, isTrue);
      expect(session.error, contains('Retry'));
      await session.login('operator2', 'test');
      expect(loginRequests, 0);
      await session.logout();
      expect(session.logoutPending, isFalse);
      await session.login('operator2', 'test');
      expect(session.bootstrap!['operator']['login'], 'operator2');
    },
  );

  test(
    'late login result cannot revive an expired or disposed session',
    () async {
      final response = Completer<http.Response>();
      final session = OperatorSession(
        client: transport(
          (request) async => request.url.path.endsWith('/session')
              ? reply({}, 401)
              : response.future,
        ),
      );
      await session.restore();
      final pending = session.login('operator1', 'test');
      session.expire();
      session.dispose();
      response.complete(reply(bootstrap('operator1')));
      await pending;
      expect(session.bootstrap, isNull);
    },
  );

  test(
    'old unauthorized response cannot expire a reconnected mission',
    () async {
      final oldTrajectory = Completer<http.Response>();
      final data = bootstrap('operator1');
      data['run']['committed_tick'] = 0;
      var trajectoryRequests = 0;
      var expired = false;
      final mission = Mission(
        onSessionExpired: () => expired = true,
        client: transport((request) async {
          if (request.url.path.endsWith('/session')) return reply(data);
          if (request.url.path.endsWith('/trajectory')) {
            trajectoryRequests++;
            if (trajectoryRequests == 1) return oldTrajectory.future;
            return reply({
              'run_id': 'run-operator1',
              'kind': 'prediction',
              'frame': 'ITRF',
              'satellites': [],
            });
          }
          return reply({'detail': 'Temporary snapshot failure'}, 503);
        }),
      );
      addTearDown(mission.dispose);
      await mission.connect(initial: data);
      await mission.connect();
      oldTrajectory.complete(reply({}, 401));
      await Future<void>.delayed(Duration.zero);
      expect(expired, isFalse);
      expect(mission.status!['run_id'], 'run-operator1');
      expect(mission.canControl, isTrue);
    },
  );

  test(
    'reconnect cannot switch the operator behind an existing workspace',
    () async {
      final paths = <String>[];
      var expired = false;
      final mission = Mission(
        onSessionExpired: () => expired = true,
        client: transport((request) async {
          paths.add(request.url.path);
          if (request.url.path.endsWith('/session')) {
            return reply(bootstrap('operator2'));
          }
          return reply({'detail': 'Temporary snapshot failure'}, 503);
        }),
      );
      addTearDown(mission.dispose);
      await mission.connect(initial: bootstrap('operator1'));
      expect(mission.status!['run_id'], 'run-operator1');
      await mission.connect();
      expect(expired, isTrue);
      expect(mission.status, isNull);
      expect(mission.canControl, isFalse);
      expect(paths, ['/v1/runs/run-operator1/snapshot', '/v1/viewer/session']);
    },
  );

  test(
    'logout invalidates delayed mission snapshot and never reconnects it',
    () async {
      final response = Completer<http.Response>();
      final paths = <String>[];
      final mission = Mission(
        client: transport((request) {
          paths.add(request.url.path);
          return response.future;
        }),
      );
      final data = bootstrap('operator1');
      final pending = mission.connect(initial: data);
      await Future<void>.delayed(Duration.zero);
      expect(mission.status!['run_id'], 'run-operator1');
      mission.suspend();
      mission.dispose();
      response.complete(reply({'status': data['run'], 'frames': []}));
      await pending;
      expect(mission.status, isNull);
      expect(mission.playback.frames, isEmpty);
      expect(mission.trajectory, isNull);
      expect(paths, ['/v1/runs/run-operator1/snapshot']);
    },
  );
}

class _Workspace extends StatefulWidget {
  const _Workspace({required this.login, required this.logout});
  final String login;
  final VoidCallback logout;
  @override
  State<_Workspace> createState() => _WorkspaceState();
}

class _WorkspaceState extends State<_Workspace> {
  var selection = 0;
  @override
  Widget build(BuildContext context) => Scaffold(
    body: Column(
      children: [
        Text('${widget.login} selection $selection'),
        TextButton(
          onPressed: () => setState(() => selection++),
          child: const Text('Select spacecraft'),
        ),
        TextButton(onPressed: widget.logout, child: const Text('Log out')),
      ],
    ),
  );
}
