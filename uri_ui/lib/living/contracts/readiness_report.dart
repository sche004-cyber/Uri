import 'package:flutter/foundation.dart';

import '../widgets/status_badge.dart';

/// PROPOSED adapter contract (see `docs/ui_phase/UI_INTERFACE_CONTRACTS.md`
/// section 2): read-only readiness facts for onboarding and the
/// Dashboard. Shapes mirror what already exists in the Phase 2 worker
/// protocol by name (`preflight`, `harness_discover`: installed, auth
/// state, qualification, required action, usable; qualification report
/// rows; client grants) so a real adapter can be a thin projection.
///
/// A visualization built on this never selects, approves or qualifies
/// anything; `requiredAction` is shown to the owner verbatim.

@immutable
class HarnessFact {
  const HarnessFact({
    required this.id,
    required this.displayName,
    required this.installed,
    required this.authState,
    required this.qualification,
    required this.usable,
    this.requiredAction,
    this.models = const [],
    this.simulated = true,
  });

  final String id;
  final String displayName;
  final bool installed;

  /// e.g. `logged_in`, `logged_out`, `unknown`.
  final String authState;

  /// e.g. `native_qualified`, `fixture_only`, `not_qualified`.
  final String qualification;
  final bool usable;
  final String? requiredAction;
  final List<String> models;
  final bool simulated;

  TruthStatus get truth {
    if (simulated) return TruthStatus.simulated;
    if (!installed) return TruthStatus.unavailable;
    if (usable) return TruthStatus.qualified;
    return TruthStatus.configured;
  }
}

@immutable
class ClientFact {
  const ClientFact({
    required this.deviceId,
    required this.label,
    required this.platform,
    required this.lastSeen,
    required this.isThisDevice,
    this.simulated = true,
  });
  final String deviceId;
  final String label;
  final String platform;
  final DateTime lastSeen;
  final bool isThisDevice;
  final bool simulated;
}

@immutable
class PermissionFact {
  const PermissionFact({
    required this.id,
    required this.label,
    required this.granted,
    required this.requiresApproval,
    this.simulated = true,
  });
  final String id;
  final String label;
  final bool granted;

  /// True when every use still needs an explicit approval card.
  final bool requiresApproval;
  final bool simulated;
}

@immutable
class ReadinessCheck {
  const ReadinessCheck({
    required this.id,
    required this.label,
    required this.status,
    this.detail,
  });
  final String id;
  final String label;
  final TruthStatus status;
  final String? detail;
}

abstract class ReadinessSource extends ChangeNotifier {
  List<HarnessFact> get harnesses;
  List<ClientFact> get clients;
  List<PermissionFact> get permissions;
  List<ReadinessCheck> get checks;
  bool get isSimulated;

  /// Re-run the checks (a real adapter would call `preflight`).
  Future<void> refresh();
}

/// Mock readiness: everything flagged simulated. Values are chosen to
/// exercise every badge (qualified / configured / unavailable) so the
/// screens are tested against the full vocabulary.
class MockReadinessSource extends ReadinessSource {
  MockReadinessSource({DateTime Function()? clock}) : _clock = clock ?? DateTime.now;

  final DateTime Function() _clock;
  bool _refreshing = false;
  bool get isRefreshing => _refreshing;

  @override
  bool get isSimulated => true;

  @override
  List<HarnessFact> get harnesses => const [
        HarnessFact(
          id: 'codex_native',
          displayName: 'Codex (native CLI)',
          installed: true,
          authState: 'logged_in',
          qualification: 'native_qualified',
          usable: true,
          models: ['gpt-5-codex'],
        ),
        HarnessFact(
          id: 'claude_cli',
          displayName: 'Claude Code CLI',
          installed: true,
          authState: 'logged_out',
          qualification: 'not_qualified',
          usable: false,
          requiredAction: 'Sign in to the CLI in the client profile, then re-run qualification.',
        ),
        HarnessFact(
          id: 'antigravity',
          displayName: 'Antigravity',
          installed: false,
          authState: 'unknown',
          qualification: 'not_qualified',
          usable: false,
          requiredAction: 'Not installed on this machine.',
        ),
      ];

  @override
  List<ClientFact> get clients => [
        ClientFact(
          deviceId: 'this-pc',
          label: 'This PC',
          platform: 'Windows',
          lastSeen: _clock(),
          isThisDevice: true,
        ),
        ClientFact(
          deviceId: 'phone-1',
          label: 'Pixel (demo)',
          platform: 'Android',
          lastSeen: _clock().subtract(const Duration(hours: 2)),
          isThisDevice: false,
        ),
      ];

  @override
  List<PermissionFact> get permissions => const [
        PermissionFact(id: 'files.read', label: 'Read files you share', granted: true, requiresApproval: false),
        PermissionFact(id: 'files.write', label: 'Save documents', granted: true, requiresApproval: true),
        PermissionFact(id: 'email.send', label: 'Send email', granted: false, requiresApproval: true),
        PermissionFact(id: 'harness.run', label: 'Run a qualified harness', granted: true, requiresApproval: true),
      ];

  @override
  List<ReadinessCheck> get checks => const [
        ReadinessCheck(id: 'server', label: 'URI server reachable', status: TruthStatus.simulated, detail: 'Mock client, no server'),
        ReadinessCheck(id: 'brain', label: 'Brain selected', status: TruthStatus.simulated, detail: 'Mock provider'),
        ReadinessCheck(id: 'harness', label: 'One qualified harness', status: TruthStatus.simulated, detail: 'Codex (native) in the mock'),
        ReadinessCheck(id: 'approvals', label: 'Approval boundary set', status: TruthStatus.configured, detail: 'Ask every time'),
        ReadinessCheck(id: 'voice', label: 'Voice', status: TruthStatus.unavailable, detail: 'No listener in this build'),
      ];

  @override
  Future<void> refresh() async {
    _refreshing = true;
    notifyListeners();
    await Future<void>.delayed(const Duration(milliseconds: 350));
    _refreshing = false;
    notifyListeners();
  }
}
