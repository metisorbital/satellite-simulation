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
    'first visit waits for session then opens the default workspace',
    (tester) async {
      final response = Completer<http.Response>();
      final paths = <String>[];
      final session = OperatorSession(
        client: transport((request) {
          paths.add(request.url.path);
          return request.url.path.endsWith('/session')
              ? response.future
              : Future.value(reply(bootstrap('operator1')));
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
      expect(find.text('Opening operator workspace…'), findsOneWidget);
      expect(missionBuilds, 0);
      response.complete(reply({'detail': 'Log in'}, 401));
      await tester.pumpAndSettle();
      expect(find.text('Mission'), findsOneWidget);
      expect(missionBuilds, 1);
      expect(paths, ['/v1/viewer/session', '/v1/viewer/login']);
      expect(session.bootstrap!['operator']['login'], 'operator1');
      expect(session.error, isNull);
    },
  );

  testWidgets('automatic login and operator switch create fresh workspace', (
    tester,
  ) async {
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
          missionBuilder: (_, data, switchOperator, _) => _Workspace(
            login: data['operator']['login'] as String,
            switchOperator: () => switchOperator('operator2', 'rotated-csrf'),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('operator1 selection 0'), findsOneWidget);
    await tester.tap(find.text('Select spacecraft'));
    await tester.pump();
    expect(find.text('operator1 selection 1'), findsOneWidget);
    await tester.tap(find.text('Switch operator'));
    await tester.pumpAndSettle();
    expect(find.text('operator2 selection 0'), findsOneWidget);
    expect(find.textContaining('operator1 selection'), findsNothing);
    expect(logins, [
      {'login': 'operator1', 'password': 'demo'},
      {'login': 'operator2', 'password': 'demo'},
    ]);
  });

  testWidgets(
    'failed automatic login can be retried without narrow layout overflow',
    (tester) async {
      tester.view.physicalSize = const Size(360, 780);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      var loginRequests = 0;
      final session = OperatorSession(
        client: transport((request) async {
          if (request.url.path.endsWith('/session')) return reply({}, 401);
          return ++loginRequests == 1
              ? reply({'detail': 'Service unavailable'}, 503)
              : reply(bootstrap('operator1'));
        }),
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
      expect(
        find.text(
          'Could not open the operator workspace. Check the connection and try again.',
        ),
        findsOneWidget,
      );
      expect(find.text('Mission'), findsNothing);
      expect(tester.takeException(), isNull);
      await tester.tap(find.text('Retry'));
      await tester.pumpAndSettle();
      expect(find.text('Mission'), findsOneWidget);
      expect(loginRequests, 2);
      expect(tester.takeException(), isNull);
    },
  );

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
      await session.switchOperator('operator2', csrfToken: 'rotated');
      expect(session.bootstrap, isNull);
      expect(session.logoutPending, isTrue);
      expect(session.error, contains('retry'));
      await session.switchOperator('operator2');
      expect(loginRequests, 0);
      await session.retry();
      expect(session.logoutPending, isFalse);
      expect(loginRequests, 1);
      expect(logoutRequests, 2);
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
      final pending = session.restore();
      await Future<void>.delayed(Duration.zero);
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
  const _Workspace({required this.login, required this.switchOperator});
  final String login;
  final VoidCallback switchOperator;
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
        TextButton(
          onPressed: widget.switchOperator,
          child: const Text('Switch operator'),
        ),
      ],
    ),
  );
}
