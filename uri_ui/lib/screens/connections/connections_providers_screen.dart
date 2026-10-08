import 'package:flutter/material.dart';

import '../../theme/uri_theme.dart';
import '../settings/providers_screen.dart';
import '../settings/capabilities_settings_screen.dart';
import 'connections_screen.dart';
import 'harnesses_screen.dart';

/// User-selected subsystem tabs; existing provider and OAuth flows preserved.
class ConnectionsProvidersScreen extends StatelessWidget {
  const ConnectionsProvidersScreen({super.key, this.initialTab = 0});
  final int initialTab;
  @override
  Widget build(BuildContext context) => DefaultTabController(
    length: 3,
    initialIndex: initialTab,
    child: Column(
      children: [
        const TabBar(
          tabs: [
            Tab(key: ValueKey('connections-models'), text: 'Models'),
            Tab(key: ValueKey('connections-plugins'), text: 'Plugins'),
            Tab(key: ValueKey('connections-harnesses'), text: 'Harnesses'),
          ],
        ),
        Expanded(
          child: TabBarView(
            children: [
              const SingleChildScrollView(
                padding: EdgeInsets.all(UriSpace.xl),
                child: ProvidersScreen(),
              ),
              SingleChildScrollView(
                padding: const EdgeInsets.all(UriSpace.xl),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const ConnectionsScreen(),
                    const SizedBox(height: UriSpace.lg),
                    Text(
                      'Available capabilities',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const Text(
                      'Availability does not authorize an operation. URI checks permissions and approvals when you use a capability.',
                    ),
                    const SizedBox(height: UriSpace.md),
                    const CapabilitiesSettingsScreen(),
                  ],
                ),
              ),
              const HarnessesScreen(),
            ],
          ),
        ),
      ],
    ),
  );
}
