import 'package:flutter/material.dart';
import '../scene/playback.dart';
import 'operator_session.dart';

typedef OperatorMissionBuilder =
    Widget Function(
      BuildContext context,
      JsonMap bootstrap,
      Future<void> Function(String csrfToken) logout,
      VoidCallback sessionExpired,
    );

/// Keeps mission state outside the widget tree until a mock operator logs in.
class OperatorGate extends StatefulWidget {
  const OperatorGate({super.key, required this.missionBuilder, this.session});
  final OperatorMissionBuilder missionBuilder;
  final OperatorSession? session;
  @override
  State<OperatorGate> createState() => _OperatorGateState();
}

class _OperatorGateState extends State<OperatorGate> {
  late final OperatorSession session;
  @override
  void initState() {
    super.initState();
    session = widget.session ?? OperatorSession();
    session.addListener(_refresh);
    session.restore();
  }

  void _refresh() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    session.removeListener(_refresh);
    session.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final bootstrap = session.bootstrap;
    if (session.restoring) {
      return const Scaffold(
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              CircularProgressIndicator(),
              SizedBox(height: 20),
              Text('Opening your workspace…'),
            ],
          ),
        ),
      );
    }
    if (bootstrap != null) {
      return KeyedSubtree(
        key: ValueKey(bootstrap['csrf_token']),
        child: widget.missionBuilder(
          context,
          bootstrap,
          (token) => session.logout(csrfToken: token),
          session.expire,
        ),
      );
    }
    return _LoginPanel(session: session);
  }
}

class _LoginPanel extends StatefulWidget {
  const _LoginPanel({required this.session});
  final OperatorSession session;
  @override
  State<_LoginPanel> createState() => _LoginPanelState();
}

class _LoginPanelState extends State<_LoginPanel> {
  final _form = GlobalKey<FormState>();
  final _login = TextEditingController();
  final _password = TextEditingController();
  final _passwordFocus = FocusNode();

  @override
  void dispose() {
    _login.dispose();
    _password.dispose();
    _passwordFocus.dispose();
    super.dispose();
  }

  void _submit() {
    if (widget.session.busy || !_form.currentState!.validate()) return;
    final password = _password.text;
    _password.clear();
    widget.session.login(_login.text, password);
  }

  @override
  Widget build(BuildContext context) {
    const mint = Color(0xff95cfbc);
    const muted = Color(0xff8b9bac);
    final session = widget.session;
    return Scaffold(
      body: DecoratedBox(
        decoration: const BoxDecoration(
          gradient: RadialGradient(
            center: Alignment(.5, -.7),
            radius: 1.5,
            colors: [Color(0xff18352f), Color(0xff070d15)],
          ),
        ),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 32),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 460),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Image.asset(
                          'assets/images/metis-mark.png',
                          width: 38,
                          height: 38,
                        ),
                        const SizedBox(width: 12),
                        const Text(
                          'metis',
                          style: TextStyle(
                            fontSize: 30,
                            fontWeight: FontWeight.w700,
                            letterSpacing: -1,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 10),
                    const Text(
                      'ORBITAL MISSION CONTROL',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: muted,
                        fontSize: 10,
                        letterSpacing: 2,
                      ),
                    ),
                    const SizedBox(height: 32),
                    Container(
                      padding: const EdgeInsets.all(28),
                      decoration: BoxDecoration(
                        color: const Color(0xff0d151f),
                        border: Border.all(color: const Color(0xff293c42)),
                        borderRadius: BorderRadius.circular(16),
                      ),
                      child: Form(
                        key: _form,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            const Row(
                              children: [
                                Icon(
                                  Icons.person_outline,
                                  color: mint,
                                  size: 18,
                                ),
                                SizedBox(width: 8),
                                Text(
                                  'DEMO WORKSPACE',
                                  style: TextStyle(
                                    color: mint,
                                    fontSize: 10,
                                    letterSpacing: 1.5,
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 20),
                            const Text(
                              'Operator login',
                              style: TextStyle(
                                fontSize: 26,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                            const SizedBox(height: 8),
                            const Text(
                              'Choose an operator to open your mission workspace.',
                              style: TextStyle(color: muted, height: 1.5),
                            ),
                            const SizedBox(height: 24),
                            if (session.logoutPending) ...[
                              Text(
                                session.busy
                                    ? 'Ending your demo session…'
                                    : 'Finish logging out before switching operators.',
                                style: const TextStyle(
                                  color: muted,
                                  height: 1.5,
                                ),
                              ),
                            ] else ...[
                              TextFormField(
                                controller: _login,
                                enabled: !session.busy,
                                autocorrect: false,
                                enableSuggestions: false,
                                textInputAction: TextInputAction.next,
                                decoration: const InputDecoration(
                                  labelText: 'Login',
                                  hintText: 'operator1',
                                  prefixIcon: Icon(Icons.person_outline),
                                  border: OutlineInputBorder(),
                                ),
                                validator: (value) =>
                                    value == null || value.trim().isEmpty
                                    ? 'Enter an operator login'
                                    : null,
                                onFieldSubmitted: (_) =>
                                    _passwordFocus.requestFocus(),
                              ),
                              const SizedBox(height: 16),
                              TextFormField(
                                controller: _password,
                                focusNode: _passwordFocus,
                                enabled: !session.busy,
                                obscureText: true,
                                autocorrect: false,
                                enableSuggestions: false,
                                textInputAction: TextInputAction.done,
                                decoration: const InputDecoration(
                                  labelText: 'Password',
                                  prefixIcon: Icon(Icons.lock_outline),
                                  border: OutlineInputBorder(),
                                ),
                                validator: (value) =>
                                    value == null || value.trim().isEmpty
                                    ? 'Enter any demo password'
                                    : null,
                                onFieldSubmitted: (_) => _submit(),
                              ),
                              const SizedBox(height: 12),
                              const Text(
                                'Mock demo only. Any non-empty password works; it is not saved. Use a made-up password.',
                                style: TextStyle(
                                  color: muted,
                                  fontSize: 12,
                                  height: 1.5,
                                ),
                              ),
                            ],
                            if (session.error != null) ...[
                              const SizedBox(height: 16),
                              Semantics(
                                liveRegion: true,
                                child: Text(
                                  session.error!,
                                  style: const TextStyle(
                                    color: Color(0xffffbba7),
                                    fontSize: 13,
                                    height: 1.5,
                                  ),
                                ),
                              ),
                            ],
                            const SizedBox(height: 24),
                            FilledButton(
                              onPressed: session.busy
                                  ? null
                                  : session.logoutPending
                                  ? () => session.logout()
                                  : _submit,
                              style: FilledButton.styleFrom(
                                backgroundColor: mint,
                                foregroundColor: const Color(0xff122a2e),
                                minimumSize: const Size.fromHeight(48),
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(8),
                                ),
                              ),
                              child: session.busy
                                  ? Row(
                                      mainAxisSize: MainAxisSize.min,
                                      children: [
                                        const SizedBox(
                                          width: 16,
                                          height: 16,
                                          child: CircularProgressIndicator(
                                            strokeWidth: 2,
                                          ),
                                        ),
                                        const SizedBox(width: 12),
                                        Text(
                                          session.logoutPending
                                              ? 'Logging out…'
                                              : 'Logging in…',
                                        ),
                                      ],
                                    )
                                  : Text(
                                      session.logoutPending
                                          ? 'Retry log out'
                                          : 'Log in',
                                    ),
                            ),
                            if (!session.logoutPending) ...[
                              const SizedBox(height: 24),
                              const Text(
                                'Demo operators',
                                style: TextStyle(color: muted, fontSize: 12),
                              ),
                              const SizedBox(height: 8),
                              Wrap(
                                spacing: 8,
                                runSpacing: 8,
                                children: [
                                  for (final login in [
                                    'operator1',
                                    'operator2',
                                    'operator3',
                                  ])
                                    ActionChip(
                                      label: Text(login),
                                      onPressed: session.busy
                                          ? null
                                          : () {
                                              _login.text = login;
                                              _passwordFocus.requestFocus();
                                            },
                                    ),
                                ],
                              ),
                            ],
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 20),
                    const Text(
                      'Synthetic mission data · Logging out ends your active demo run',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: muted, fontSize: 11, height: 1.6),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
