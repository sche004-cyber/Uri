import 'package:flutter/material.dart';

import '../../theme/uri_theme.dart';
import '../../widgets/desktop_harness_test.dart';
import '../../widgets/app_shell.dart';

class HarnessesScreen extends StatefulWidget {
  const HarnessesScreen({super.key});
  @override
  State<HarnessesScreen> createState() => _HarnessesScreenState();
}

class _HarnessesScreenState extends State<HarnessesScreen> {
  String? detail;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) HarnessAccess.maybeOf(context)?.refresh();
    });
  }

  @override
  Widget build(BuildContext context) {
    final access = HarnessAccess.maybeOf(context);
    return SingleChildScrollView(
      padding: const EdgeInsets.all(UriSpace.xl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Execution harnesses',
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: UriSpace.sm),
          const Text(
            'Choose the executor explicitly. URI verifies each result and preserves interrupted work.',
          ),
          const SizedBox(height: UriSpace.lg),
          if (access == null)
            const Text(
              'Harness management is unavailable in this installation. Use the isolated candidate launcher for qualification; production integration awaits independent acceptance.',
            ),
          if (access != null) ...[
            OutlinedButton(
              onPressed: access.refresh,
              child: const Text('Refresh installation and authentication'),
            ),
            if (access.providers.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: UriSpace.lg),
                child: Text(
                  'No discovery result yet. Refresh to check the installed native CLIs.',
                ),
              ),
            if (detail != null)
              TextButton(
                onPressed: () => setState(() => detail = null),
                child: const Text('Back to harnesses'),
              ),
            for (final row in access.providers.where(
              (row) => detail == null || row['id'] == detail,
            )) ...[
              const Divider(height: 32),
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text(row['label'] as String),
                subtitle: Text(
                  '${row['installed'] == true ? 'Installed' : 'Not installed'} · ${row['authentication']} · ${row['qualification']}',
                ),
                trailing: TextButton(
                  key: ValueKey('harness-details-${row['id']}'),
                  onPressed: () => setState(
                    () => detail = detail == row['id'] ? null : row['id'],
                  ),
                  child: Text(
                    detail == row['id'] ? 'Close details' : 'Details',
                  ),
                ),
              ),
              if (detail == row['id']) ...[
                SelectableText(
                  'Version: ${row['version']}\nAuthentication evidence: ${row['authentication_evidence']}\nQuota: ${row['quota']}\nModels: ${(row['models'] as List).isEmpty ? 'Not discovered' : (row['models'] as List).join(', ')}\nFile tools: ${(row['native_tools'] as List).join(', ')}\nInventory: ${row['inventory_status']}\nCurrent running tasks: ${row['running_sessions']}\nPermissions: ${row['permissions']}',
                ),
                const SizedBox(height: UriSpace.sm),
                Text(row['blocked_reason'].toString()),
                Text('Setup: ${row['onboarding']}'),
                Text('Configuration: ${row['configuration']}'),
                for (final capability in row['capabilities'] as List)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Text(capability['name'].toString()),
                    subtitle: Text(
                      'Installed · Available: ${capability['available']} · Authorized: ${capability['authorized']} · Qualified: ${capability['tested']} · Blocked: ${capability['blocked']}',
                    ),
                  ),
              ],
              Align(
                alignment: Alignment.centerLeft,
                child: OutlinedButton(
                  onPressed: row['eligible'] == true
                      ? () {
                          access.select(row['id'] as String);
                          context
                              .findAncestorStateOfType<AppShellState>()
                              ?.goTo(ShellIndex.chat);
                        }
                      : null,
                  child: Text('Use ${row['label']} in Workspace'),
                ),
              ),
            ],
          ],
        ],
      ),
    );
  }
}
