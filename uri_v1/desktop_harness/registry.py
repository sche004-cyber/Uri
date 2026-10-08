"""Read-only native CLI discovery. Discovery never authorizes task execution."""
import json
from pathlib import Path
import re
import subprocess
import time

from uri_v1.execution.harness.discovery import probe_version, resolve_command
from uri_v1.execution.harness.process import harness_env

NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:@/ -]{0,127}$')


def native_query(executable, args):
    command = resolve_command(executable)
    if not command:
        return None
    try:
        result = subprocess.run([*command, *args], cwd=str(Path(__file__).parent),
            env=harness_env(), capture_output=True, text=True, timeout=12)
        if executable == 'codex' and args == ['login', 'status']:
            # Native status goes to stderr in current CLI; retain only known status.
            if result.returncode == 0 and 'Logged in using ChatGPT' in result.stdout + result.stderr:
                return 'Logged in using ChatGPT'
            return None
        return result.stdout if result.returncode == 0 and len(result.stdout) <= 2_000_000 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


class AntigravityAdapter:
    """Experimental adapter: no task can spawn before containment qualification."""
    identifier = 'antigravity'

    def probe(self):
        # Installed help has no --version. Installation alone is not authentication.
        command = resolve_command('agy')
        return {'installed': bool(command), 'version': 'unknown'}

    def execute(self, *args, **kwargs):
        raise PermissionError('ANTIGRAVITY_CONTAINMENT_UNQUALIFIED')


class HarnessRegistry:
    def __init__(self, claude, query=native_query):
        self.claude, self.query = claude, query
        self.cached = None
        self.checked_at = 0
        self.quota_blocked = set()

    def snapshot(self, refresh=False):
        if self.cached is None or refresh or time.monotonic() - self.checked_at > 60:
            self.cached = self._discover()
            self.checked_at = time.monotonic()
        # Make fresh copies; running-session counters are added by the controller.
        rows = json.loads(json.dumps(self.cached))
        for row in rows:
            if row['id'] in self.quota_blocked:
                row.update(quota='exhausted', eligible=False, blocked_reason='Quota interruption; authorize recovery first')
        return rows

    def _discover(self):
        rows = []
        for identifier, label, executable in [('claude_code', 'Claude Code', 'claude'),
                ('antigravity', 'Antigravity', 'agy'), ('codex', 'Codex', 'codex')]:
            try:
                probe = self.claude.probe() if identifier == 'claude_code' else (
                    AntigravityAdapter().probe() if identifier == 'antigravity' else probe_version(executable))
            except Exception:
                probe = {'installed': False, 'version': 'unknown'}
            installed = bool(probe.get('installed'))
            auth = 'unknown'
            if installed and identifier == 'claude_code':
                raw = self.query(executable, ['auth', 'status', '--json'])
                try:
                    data = json.loads(raw or '{}')
                    if data.get('loggedIn') is True and data.get('authMethod') == 'claude.ai':
                        auth = 'authenticated_subscription'
                    elif data.get('loggedIn') is False:
                        auth = 'signed_out'
                    elif data.get('loggedIn') is True:
                        auth = 'unsupported_authentication'
                except (ValueError, AttributeError):
                    pass
            if installed and identifier == 'codex':
                raw = self.query(executable, ['login', 'status'])
                if raw and 'Logged in using ChatGPT' in raw:
                    auth = 'authenticated_subscription'
                elif raw and 'Not logged in' in raw:
                    auth = 'signed_out'
            models, capabilities, inventory = [], [], 'unknown'
            if installed and identifier == 'antigravity':
                raw = self.query(executable, ['models'])
                if raw is not None:
                    models = [line.split('\t')[0] for line in raw.splitlines()
                              if NAME.fullmatch(line.split('\t')[0])][:100]
                raw = self.query(executable, ['plugin', 'list'])
                if raw is not None and 'No imported plugins.' in raw:
                    inventory = 'plugins_empty; MCP unknown; skills unknown'
                # Do not parse human-readable MCP configuration (may carry credentials).
            elif installed and identifier == 'claude_code':
                raw = self.query(executable, ['plugin', 'list', '--json'])
                try:
                    plugins = json.loads(raw or 'null')
                    if isinstance(plugins, list):
                        inventory = 'plugins_discovered; MCP unknown; skills unknown'
                        for plugin in plugins[:100]:
                            name = plugin.get('id') if isinstance(plugin, dict) else None
                            if isinstance(name, str) and NAME.fullmatch(name):
                                capabilities.append({'name': name, 'kind': 'plugin',
                                    'discovered': True, 'available': plugin.get('enabled') is True,
                                    'authorized': False, 'tested': False, 'blocked': True,
                                    'reason': 'Native plugin execution has no qualified grant in this profile'})
                except ValueError:
                    pass
            eligible = identifier == 'claude_code' and installed and auth == 'authenticated_subscription'
            reason = '' if eligible else ('CLI unavailable' if not installed else
                'Per-task containment unqualified' if identifier == 'antigravity' else
                'Selected for qualification; native elevated sandbox rejects workspace-only read containment. Execution disabled.' if identifier == 'codex' else 'Subscription authentication required')
            rows.append({'id': identifier, 'label': label, 'installed': installed,
                'version': probe.get('version') or 'unknown', 'authentication': auth,
                'authentication_evidence': 'Native auth status' if auth != 'unknown' else
                    'Prior native-account probe passed on 2026-10-03; current status unknown' if identifier == 'antigravity' else 'Native login status' if identifier == 'codex' and auth != 'unknown' else 'No supported status check used',
                'quota': 'unknown', 'models': models, 'model_selection': False,
                'native_tools': ['Read', 'Edit', 'Write', 'Glob', 'Grep'] if identifier == 'claude_code' else [],
                'inventory_status': inventory, 'capabilities': capabilities,
                'task_categories': ['disposable_script_workbook_repair'] if identifier == 'claude_code' else [],
                'qualification': 'provisional_fixed_repair' if identifier == 'claude_code' else 'unqualified',
                'eligible': eligible, 'blocked_reason': reason, 'available': installed,
                'authorized': False, 'tested': False, 'blocked': not eligible,
                'permissions': 'Disposable copy only; file tools; no shell/web/native plugins/MCP/write-back',
                'streaming': 'native_events; desktop_status_polling' if identifier != 'codex' else 'unqualified',
                'session_continuation': False, 'running_sessions': 0,
                'onboarding': 'Sign in using the native CLI application; URI never handles account tokens',
                'configuration': 'Native configuration remains external; this profile grants no native integrations'})
        return rows
