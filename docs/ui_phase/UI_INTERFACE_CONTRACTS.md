# UI interface contracts (proposed) for Brain connectivity

Date: 2026-10-08. Author: Claude. Status: PROPOSED. Nothing here is accepted or wired to Core, Supervisor or the paired worker. Each contract has exactly one implementation in this phase, a mock that flags itself `simulated`, and a Dart abstract class under `uri_ui/lib/living/` that a real adapter would implement without touching any screen.

Governing constraints carried forward from the accepted Phase 2 work (`docs/architecture/PHASE2OPS_UI_OPERATIONS.md`, C6 contract; `docs/architecture/PHASE2CLOSE_UI_READINESS.md` sections 3-4):

* The UI talks only to the client worker over framed stdio, never to the server, never holds credentials, never approves on its own, never defaults or switches an executor.
* Typed or spoken text never approves. Only a structured decision (`execution_begin` / `turn_decide`) does.
* A presentation state is a pure function of authoritative state; no state without a source.

## 1. Companion state (`CompanionStateSource`)

File: `uri_ui/lib/living/companion/companion_sources.dart`.

```dart
abstract class CompanionStateSource extends ChangeNotifier {
  CompanionSignal get signal;   // state, detail, progress, simulated, sourceName
  String get name;
}
```

Implemented now:

| Source | Derives from | Emits |
|---|---|---|
| `AppStateCompanionSource` | `AppState.connectionStatus`, `isSendingAsk`, last `UriTurn.stage` | error, thinking, awaitingApproval, working, success (held 4 s), idle. Never listening/speaking. `simulated: false`. |
| `MockCompanionSource` | explicit `emit()` | any state, `simulated: true` |
| `CompositeCompanionSource` | priority merge: error > awaitingApproval > working > thinking > speaking > listening > success > unavailable > idle | the winner |

Proposed real adapter (`SupervisedCompanionSource`, not built): reads the existing `SupervisedRuntime` (`uri_ui/lib/services/supervised_runtime.dart`) and maps, per the readiness document's table:

| Worker fact | CompanionState |
|---|---|
| preflight failed / no opt-in file | unavailable |
| `execution_list.active == null`, no pending turn | idle |
| `INTENT_CLARIFICATION` / `INTENT_CONFIRMATION_REQUIRED` | awaitingApproval (detail: clarification) |
| `approval_required` + `execution_proposal` | awaitingApproval (detail: proposal title) |
| `execution_status.state in {queued, approving, starting, running}` | working (progress: null; the worker reports no percentage) |
| `completed` only when corroborated (`SETTLED_VERIFIED`) | success |
| `uncertain`, `failed`, `quota_paused`, `APPROVAL_REFUSED_NOT_APPLIED` | error (detail: reason verbatim) |

Listening/speaking need a voice source that does not exist in this tree (the `_V1` line has a status strip; parity is a C6 owner decision).

## 2. Readiness (`ReadinessSource`)

File: `uri_ui/lib/living/contracts/readiness_report.dart`.

```dart
abstract class ReadinessSource extends ChangeNotifier {
  List<HarnessFact> get harnesses;     // id, displayName, installed, authState, qualification, usable, requiredAction, models
  List<ClientFact> get clients;        // deviceId, label, platform, lastSeen, isThisDevice
  List<PermissionFact> get permissions;// id, label, granted, requiresApproval
  List<ReadinessCheck> get checks;     // id, label, TruthStatus, detail
  bool get isSimulated;
  Future<void> refresh();
}
```

Field provenance for a real adapter: `harnesses` is a projection of the worker's `harness_discover` reply (installed, auth state, qualification, required action, usable) plus qualification report rows; `clients` from `GET /devices` (`DeviceSession`, already on `AppState.devices`) joined with the local device id; `permissions` from client grants (`GET /admin/users/{id}/grants` shape, `UserGrantsInfo`); `checks` from `preflight`. The UI shows `requiredAction` verbatim and never performs it.

## 3. Work items (`WorkItemSource`)

File: `uri_ui/lib/living/contracts/work_items.dart`.

```dart
abstract class WorkItemSource extends ChangeNotifier {
  List<WorkItem> get items;        // id, title, kind, state, progress, detail, outputName, approvalSummary, simulated
  List<WorkDocument> get documents;
  bool get isSimulated;
  String create({required String title, required WorkItemKind kind});
  void approve(String id);         // structured decision only
  void cancel(String id);
}
```

No backend serves this shape today. A real adapter would compose: pending approvals from `GET /tasks` (already `AppState.tasks`, rendered in the Tasks region through the existing `approveTask`/`cancelTask`), execution records from `execution_list`/`execution_status`, and a documents capability that does not exist yet. `create()` would become `turn_start` with a drafted request (the `TaskHandoff` seam), never an execution.

## 4. Intelligence snapshot (`IntelligenceSnapshotSource`)

File: `uri_ui/lib/living/contracts/intelligence_snapshot.dart`. In this phase the snapshot is derived in the UI (`deriveIntelligenceSnapshot`) from the signal, `AppState` and the other sources; the abstract source exists so a worker-backed adapter can replace the derivation.

Stages: request, intent, route (Edge/Core), harness, model, approval, execution, receipt. Each is idle/active/done/blocked/failed with an optional fact string. Forbidden by contract: reasoning text, token streams, invented timings, a "memory backend" claim. The memory graph is a prototype over `MemoryEntry` rows and says so on screen.

## 5. UI commands (`UiCommand`)

File: `uri_ui/lib/living/presentation/presentation_controller.dart`.

```dart
sealed class UiCommand {}
class ShowModeCommand extends UiCommand { UiPresentationMode mode; WorkspaceFocus? focus; }
```

That is the whole vocabulary. `UiPresentationController.apply(command, origin)` applies it with a cooldown and records the origin so the shell shows "URI opened Dashboard · Back". Today the only producer is `parseLocalUiCommand(String)` over text typed in the composer (`uri dashboard`, `uri workspace`, `uri companion|minimize|orb`, `uri tasks|documents|intelligence|settings|chat`). A Brain-originated command would arrive as a typed frame from the worker (proposed name `ui_present`, payload `{mode, focus?}`), be validated against this enum, and be applied with `origin: brain`. The controller cannot be made to send text, approve, choose an executor or change settings; those are not commands.

## 6. Effects and persistence

`EffectsSettings` (reducedEffects, reducedMotion) and the living preferences are device-local (`uri.living.*` keys in shared preferences). The one shared key written is the Hybrid `UserPreferences` store (onboarding completion, focus areas, autonomy level), deliberately, so a later integrated app sees the same preferences.
