import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';

import '../services/desktop_harness_test_client.dart';
import '../theme/uri_theme.dart';
import 'harness_checkpoint_inspector.dart';

/// Management in real UriApp; never changes Brain configuration.
class DesktopHarnessTest extends StatefulWidget {
  static Map<String, dynamic>? lastRunReceipt;
  static final captureKey = GlobalKey();
  const DesktopHarnessTest({
    super.key,
    required this.client,
    required this.child,
    this.navigatorKey,
  });
  final DesktopHarnessTestClient client;
  final Widget child;
  final GlobalKey<NavigatorState>? navigatorKey;
  @override
  State<DesktopHarnessTest> createState() => _DesktopHarnessTestState();
}

/// Presentation access only. Backend authorization remains independent.
class HarnessAccess extends InheritedWidget {
  const HarnessAccess({
    super.key,
    required super.child,
    required this.providers,
    required this.selected,
    required this.refresh,
    required this.select,
    required this.workspaceBuilder,
  });
  final List<Map<String, dynamic>> providers;
  final String? selected;
  final Future<void> Function() refresh;
  final void Function(String) select;
  final WidgetBuilder workspaceBuilder;
  static HarnessAccess? maybeOf(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<HarnessAccess>();
  @override
  bool updateShouldNotify(HarnessAccess oldWidget) => true;
}

class _DesktopHarnessTestState extends State<DesktopHarnessTest> {
  List<Map<String, dynamic>> providers = [];
  String? selected;
  Map<String, dynamic>? pending, task;
  List<Map<String, dynamic>> savedTasks = [];
  String? timedTaskId;
  int? desktopDurationMs;
  String message = 'Open Harness Management and choose an executor.';
  bool busy = false, pollingActive = false;
  Timer? timer;
  final elapsed = Stopwatch();
  String? ownerToken;
  @override
  void dispose() {
    timer?.cancel();
    super.dispose();
  }

  Map<String, dynamic>? get selectedRow {
    for (final row in providers) {
      if (row['id'] == selected) return row;
    }
    return null;
  }

  Future<void> refresh() async {
    final result = await widget.client.providers(refresh: true);
    final saved = await widget.client.tasks();
    if (!mounted) return;
    setState(() {
      providers = (result['providers'] as List).cast<Map<String, dynamic>>();
      if (selectedRow?['eligible'] != true) {
        selected = null;
        pending = null;
      }
      final tasks = saved['tasks'] as List;
      savedTasks = tasks.cast<Map<String, dynamic>>();
      if (task == null && tasks.isNotEmpty) {
        task = tasks.first as Map<String, dynamic>;
      }
    });
  }

  Future<void> action(Future<void> Function() operation) async {
    setState(() => busy = true);
    try {
      await operation();
    } catch (error) {
      if (mounted) {
        setState(
          () => message = '$error No automatic retry or provider switch.',
        );
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> prepare() async {
    final result = await widget.client.prepareSelected(selected!);
    if (mounted) {
      setState(() {
        pending = result;
        task = null;
        message = 'Review permissions, then authorize this run.';
      });
    }
  }

  Future<void> start() async {
    final id = pending!['approval_id'] as String;
    setState(() => pending = null);
    DesktopHarnessTest.lastRunReceipt = null;
    elapsed.reset();
    elapsed.start();
    final result = await widget.client.start(id);
    if (!mounted) return;
    setState(() => task = result);
    timedTaskId = result['task_id'] as String;
    desktopDurationMs = null;
    timer?.cancel();
    timer = Timer.periodic(const Duration(seconds: 1), (_) => poll());
  }

  Future<void> poll() async {
    if (pollingActive || task == null) return;
    pollingActive = true;
    try {
      final result = await widget.client.task(task!['task_id'] as String);
      if (!mounted) return;
      if (result['status'] != 'RUNNING') {
        timer?.cancel();
        elapsed.stop();
        final receipt = result['receipt'];
        if (timedTaskId == result['task_id']) {
          desktopDurationMs = elapsed.elapsedMilliseconds;
        }
        DesktopHarnessTest.lastRunReceipt = {
          ...result,
          if (receipt is Map<String, dynamic>) ...receipt,
          if (desktopDurationMs != null && timedTaskId == result['task_id'])
            'application_round_trip_ms': desktopDurationMs,
        };
        debugPrint(
          'URI_DESKTOP_HARNESS_RECEIPT ${jsonEncode(DesktopHarnessTest.lastRunReceipt)}',
        );
      }
      setState(() => task = result);
      if (result['status'] == 'QUOTA_INTERRUPTED') {
        setState(() {
          for (final row in providers) {
            if (row['id'] == result['provider']) {
              row['eligible'] = false;
              row['quota'] = 'exhausted';
            }
          }
        });
      }
    } catch (error) {
      timer?.cancel();
      if (mounted) {
        setState(
          () => message =
              '$error Checkpoint retained; refresh status before retrying.',
        );
      }
    } finally {
      pollingActive = false;
    }
  }

  Future<void> manage() async {
    await refresh();
    if (!mounted) return;
    setState(() => busy = false);
    await showDialog<void>(
      context: widget.navigatorKey?.currentContext ?? context,
      builder: (context) => StatefulBuilder(
        builder: (context, update) => AlertDialog(
          title: const Text('Harness Management'),
          content: SizedBox(
            width: 700,
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Execution is separate from the optional Main Brain. Provisional disposable repair only.',
                  ),
                  for (final row in providers) ...[
                    const Divider(height: 24),
                    Text(
                      row['label'] as String,
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    Text(
                      'Installation: ${row['installed'] == true ? 'Installed' : 'Unavailable'} · ${row['version']}',
                    ),
                    Text('Authentication: ${row['authentication']}'),
                    Text(row['authentication_evidence'] as String),
                    Text(
                      'Quota: ${row['quota']} · Qualification: ${row['qualification']}',
                    ),
                    Text(
                      'Models: ${(row['models'] as List).isEmpty ? 'Unknown' : (row['models'] as List).join(', ')}',
                    ),
                    Text(
                      'Native tools: ${(row['native_tools'] as List).isEmpty ? 'Unknown' : (row['native_tools'] as List).join(', ')}',
                    ),
                    Text('Inventory: ${row['inventory_status']}'),
                    Text(
                      'Running sessions: ${row['running_sessions']} · Continuation: unavailable here',
                    ),
                    if (row['eligible'] != true)
                      Text('Blocked: ${row['blocked_reason']}'),
                    Text(row['permissions'] as String),
                    if ((row['capabilities'] as List).isNotEmpty)
                      ExpansionTile(
                        title: Text(
                          'Native plugins (${(row['capabilities'] as List).length}) — no execution grants',
                        ),
                        children: [
                          for (final capability in row['capabilities'] as List)
                            Text(
                              '${capability['kind']}: ${capability['name']} · discovered · '
                              '${capability['available'] == true ? 'available' : 'unavailable'} · unauthorized · untested · blocked',
                            ),
                        ],
                      ),
                    Wrap(
                      spacing: 8,
                      children: [
                        TextButton(
                          key: ValueKey('select-${row['id']}'),
                          onPressed:
                              row['eligible'] != true ||
                                  task?['status'] == 'RUNNING'
                              ? null
                              : () {
                                  setState(() {
                                    selected = row['id'] as String;
                                    pending = null;
                                  });
                                  Navigator.pop(context);
                                },
                          child: Text('Select ${row['label']}'),
                        ),
                        TextButton(
                          onPressed: () => showDialog<void>(
                            context: context,
                            builder: (context) => AlertDialog(
                              title: Text(
                                '${row['label']} onboarding / reconnect',
                              ),
                              content: Text(
                                '${row['onboarding']}.\n${row['configuration']}.\n'
                                'Use native sign-in, then Refresh status here.',
                              ),
                              actions: [
                                TextButton(
                                  onPressed: () => Navigator.pop(context),
                                  child: const Text('Close'),
                                ),
                              ],
                            ),
                          ),
                          child: const Text('Onboarding / configuration'),
                        ),
                      ],
                    ),
                  ],
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () async {
                try {
                  await refresh();
                  update(() {});
                } catch (_) {
                  if (mounted) {
                    setState(
                      () => message = 'Refresh failed; no task submitted.',
                    );
                  }
                }
              },
              child: const Text('Refresh status'),
            ),
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Close'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> recovery(String choice) async {
    final result = await widget.client.recover(
      task!['task_id'] as String,
      choice,
    );
    if (mounted) {
      setState(() {
        task = result;
        message = result['recovery_result'] as String;
      });
    }
    await refresh();
  }

  @override
  Widget build(BuildContext context) {
    // A logout/account change must discard another user's visible receipt.
    if (ownerToken != widget.client.uri.authToken) {
      ownerToken = widget.client.uri.authToken;
      providers = [];
      selected = null;
      pending = null;
      task = null;
      savedTasks = [];
      timedTaskId = null;
      desktopDurationMs = null;
      timer?.cancel();
      DesktopHarnessTest.lastRunReceipt = null;
      message = 'Open Harness Management and choose an executor.';
    }
    return RepaintBoundary(
      key: DesktopHarnessTest.captureKey,
      child: HarnessAccess(
        providers: providers,
        selected: selected,
        refresh: () => action(refresh),
        select: (provider) => setState(() {
          selected = provider;
          pending = null;
        }),
        workspaceBuilder: buildWorkspace,
        child: widget.child,
      ),
    );
  }

  Widget buildWorkspace(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final colors = UriColors.of(context);
        final running = task?['status'] == 'RUNNING';
        final receipt = task?['receipt'] as Map<String, dynamic>?;
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Expanded(
              child: Material(
                color: colors.surface,
                child: SingleChildScrollView(
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Wrap(
                          spacing: 12,
                          crossAxisAlignment: WrapCrossAlignment.center,
                          children: [
                            const Text('Harness execution — provisional'),
                            TextButton(
                              key: const ValueKey('harness-management'),
                              onPressed: busy ? null : () => action(manage),
                              child: const Text('Harness Management'),
                            ),
                            TextButton(
                              key: const ValueKey('harness-saved-refresh'),
                              onPressed: busy ? null : () => action(refresh),
                              child: const Text('Refresh saved tasks'),
                            ),
                            Text(
                              'Selected: ${selectedRow?['label'] ?? 'Choose a harness'}',
                            ),
                          ],
                        ),
                        const Text(
                          'Disposable Amount-column repair. File tools only; no shell, web, native plugins, MCP or write-back.',
                        ),
                        if (pending != null)
                          Text(
                            'Workspace: ${pending!['workspace']} · Model: ${pending!['model']}\nPermissions: ${pending!['permissions']}',
                          ),
                        Wrap(
                          spacing: 8,
                          children: [
                            TextButton(
                              key: const ValueKey('desktop-harness-prepare'),
                              onPressed:
                                  busy ||
                                      running ||
                                      selectedRow?['eligible'] != true
                                  ? null
                                  : () => action(prepare),
                              child: const Text('Prepare disposable test'),
                            ),
                            TextButton(
                              key: const ValueKey('desktop-harness-approve'),
                              onPressed: busy || pending == null
                                  ? null
                                  : () => action(start),
                              child: Text(
                                'Authorize this ${selectedRow?['label'] ?? 'harness'} run',
                              ),
                            ),
                            if (running)
                              TextButton(
                                key: const ValueKey('harness-cancel'),
                                onPressed: busy
                                    ? null
                                    : () => action(() async {
                                        final result = await widget.client
                                            .cancel(task!['task_id'] as String);
                                        if (mounted) {
                                          setState(() => task = result);
                                        }
                                      }),
                                child: const Text('Cancel execution'),
                              ),
                            if (task != null)
                              TextButton(
                                onPressed: poll,
                                child: const Text('Refresh task status'),
                              ),
                            if (busy || running)
                              const SizedBox(
                                width: 20,
                                height: 20,
                                child: CircularProgressIndicator(),
                              ),
                          ],
                        ),
                        Text(message),
                        if (task != null) ...[
                          Text(
                            'Status: ${task!['status']} · ${task!['progress']}',
                          ),
                          SelectableText(
                            'Task checkpoint: ${task!['task_id']}',
                          ),
                          Text(task!['result'] as String),
                          if (receipt != null) ...[
                            Text(
                              'Tool calls: ${receipt['tool_calls'] ?? 'unknown'}',
                            ),
                            Text(
                              'URI verification: ${receipt['verification_status']} · Execution: ${receipt['execution_ok'] == true ? 'completed' : 'did not complete'}',
                            ),
                            Text(
                              'Harness: ${receipt['harness_duration_ms'] ?? 'unavailable'} ms · Core: ${receipt['core_duration_ms'] ?? 'unavailable'} ms · Desktop: ${timedTaskId == task!['task_id'] && desktopDurationMs != null ? '$desktopDurationMs ms' : 'unavailable'}',
                            ),
                          ],
                          if ((task!['recovery_choices'] as List)
                              .isNotEmpty) ...[
                            Text(task!['recommendation'] as String),
                            Wrap(
                              spacing: 8,
                              children: [
                                TextButton(
                                  onPressed: busy
                                      ? null
                                      : () => action(() => recovery('wait')),
                                  child: const Text(
                                    'Authorize wait and retry later',
                                  ),
                                ),
                                const TextButton(
                                  onPressed: null,
                                  child: Text('Another harness — unqualified'),
                                ),
                                const TextButton(
                                  onPressed: null,
                                  child: Text(
                                    'URI Local — unqualified for this repair',
                                  ),
                                ),
                                TextButton(
                                  onPressed: busy
                                      ? null
                                      : () => action(() => recovery('stop')),
                                  child: const Text('Stop and retain work'),
                                ),
                              ],
                            ),
                          ],
                        ],
                        HarnessCheckpointInspector(
                          key: ValueKey(ownerToken),
                          client: widget.client,
                          pending: pending,
                          task: task,
                          savedTasks: savedTasks,
                          desktopDurationMs: timedTaskId == task?['task_id']
                              ? desktopDurationMs
                              : null,
                          onSelect: running || busy
                              ? null
                              : (record) {
                                  timer?.cancel();
                                  setState(() => task = record);
                                },
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}
