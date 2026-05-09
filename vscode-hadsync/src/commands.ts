import * as vscode from 'vscode';
import { dashboardIdFromUri, getWorkspaceCwd, runHadsync } from './runner';
import { HadsyncDiagnosticsProvider } from './diagnostics';
import { HadsyncStatusBar } from './statusBar';

const out = vscode.window.createOutputChannel('hadsync');

function showOutput(): void {
  out.show(true);  // preservesFocus = true
}

function appendLine(text: string): void {
  // Strip ANSI escape codes (Rich terminal output)
  out.appendLine(text.replace(/\x1b\[[0-9;]*m/g, ''));
}

async function requireCwd(): Promise<string | undefined> {
  const cwd = getWorkspaceCwd();
  if (!cwd) {
    vscode.window.showErrorMessage(
      'hadsync: No .hadsync.yaml found in workspace. Run "hadsync init" first.'
    );
  }
  return cwd;
}

function activeDashboardId(): string | undefined {
  const editor = vscode.window.activeTextEditor;
  const cwd = getWorkspaceCwd();
  if (!editor || !cwd) return undefined;
  return dashboardIdFromUri(editor.document.uri, cwd);
}

async function runWithProgress(
  label: string,
  args: string[],
  cwd: string,
  statusBar: HadsyncStatusBar
): Promise<void> {
  statusBar.setWorking(label);
  out.clear();
  showOutput();

  await vscode.window.withProgress(
    { location: vscode.ProgressLocation.Window, title: `hadsync: ${label}` },
    async () => {
      const result = await runHadsync(args, cwd, chunk => appendLine(chunk));
      if (result.stderr) appendLine(result.stderr);
    }
  );

  statusBar.refresh(cwd);
}

export function registerCommands(
  context: vscode.ExtensionContext,
  diagnostics: HadsyncDiagnosticsProvider,
  statusBar: HadsyncStatusBar
): void {

  // ── pull (all) ────────────────────────────────────────────────────────────
  context.subscriptions.push(
    vscode.commands.registerCommand('hadsync.pull', async () => {
      const cwd = await requireCwd();
      if (!cwd) return;
      await runWithProgress('Pulling dashboards…', ['pull'], cwd, statusBar);
      await diagnostics.validate(cwd);
    })
  );

  // ── pull (active file's dashboard) ────────────────────────────────────────
  context.subscriptions.push(
    vscode.commands.registerCommand('hadsync.pullOne', async () => {
      const cwd = await requireCwd();
      if (!cwd) return;
      const id = activeDashboardId();
      const args = id ? ['pull', id] : ['pull'];
      await runWithProgress(`Pulling ${id ?? 'all'}…`, args, cwd, statusBar);
      if (id) await diagnostics.validate(cwd, id);
    })
  );

  // ── push (all) ────────────────────────────────────────────────────────────
  context.subscriptions.push(
    vscode.commands.registerCommand('hadsync.push', async () => {
      const cwd = await requireCwd();
      if (!cwd) return;
      const ok = await vscode.window.showWarningMessage(
        'Push ALL dashboards to Home Assistant?',
        { modal: true },
        'Push'
      );
      if (ok !== 'Push') return;
      await runWithProgress('Pushing dashboards…', ['push', '--yes'], cwd, statusBar);
    })
  );

  // ── push (active file's dashboard) ────────────────────────────────────────
  context.subscriptions.push(
    vscode.commands.registerCommand('hadsync.pushOne', async () => {
      const cwd = await requireCwd();
      if (!cwd) return;
      const id = activeDashboardId();
      if (!id) {
        vscode.window.showWarningMessage('hadsync: Open a lovelace.yaml file to push a specific dashboard.');
        return;
      }
      const ok = await vscode.window.showWarningMessage(
        `Push '${id}' to Home Assistant?`,
        { modal: true },
        'Push'
      );
      if (ok !== 'Push') return;
      await runWithProgress(`Pushing ${id}…`, ['push', id, '--yes'], cwd, statusBar);
    })
  );

  // ── validate (all) ────────────────────────────────────────────────────────
  context.subscriptions.push(
    vscode.commands.registerCommand('hadsync.validate', async () => {
      const cwd = await requireCwd();
      if (!cwd) return;
      statusBar.setWorking('Validating…');
      const result = await diagnostics.validate(cwd);
      statusBar.refresh(cwd);
      if (result) {
        const msg = result.total_errors > 0
          ? `${result.total_errors} error(s), ${result.total_warnings} warning(s)`
          : result.total_warnings > 0
            ? `0 errors, ${result.total_warnings} warning(s)`
            : 'All dashboards passed';
        vscode.window.showInformationMessage(`hadsync validate: ${msg}`);
      }
    })
  );

  // ── validate (active dashboard) ───────────────────────────────────────────
  context.subscriptions.push(
    vscode.commands.registerCommand('hadsync.validateOne', async () => {
      const cwd = await requireCwd();
      if (!cwd) return;
      const id = activeDashboardId();
      statusBar.setWorking('Validating…');
      const result = await diagnostics.validate(cwd, id);
      statusBar.refresh(cwd);
      if (result) {
        const dashboard = id ? result.dashboards[id] : undefined;
        const issues = dashboard?.issues ?? [];
        const errs = issues.filter(i => i.severity === 'ERROR').length;
        const warns = issues.filter(i => i.severity === 'WARN').length;
        const label = id ?? 'all dashboards';
        if (errs > 0) {
          vscode.window.showErrorMessage(`hadsync: ${label} — ${errs} error(s), ${warns} warning(s)`);
        } else if (warns > 0) {
          vscode.window.showWarningMessage(`hadsync: ${label} — ${warns} warning(s)`);
        } else {
          vscode.window.showInformationMessage(`hadsync: ${label} passed`);
        }
      }
    })
  );

  // ── diff ──────────────────────────────────────────────────────────────────
  context.subscriptions.push(
    vscode.commands.registerCommand('hadsync.diff', async () => {
      const cwd = await requireCwd();
      if (!cwd) return;
      const id = activeDashboardId();
      const args = id ? ['diff', id, '--show'] : ['diff', '--show'];
      await runWithProgress(`Diff ${id ?? 'all'}…`, args, cwd, statusBar);
    })
  );

  // ── status ────────────────────────────────────────────────────────────────
  context.subscriptions.push(
    vscode.commands.registerCommand('hadsync.status', async () => {
      const cwd = await requireCwd();
      if (!cwd) return;
      await runWithProgress('Status…', ['status'], cwd, statusBar);
    })
  );

  // ── list ──────────────────────────────────────────────────────────────────
  context.subscriptions.push(
    vscode.commands.registerCommand('hadsync.list', async () => {
      const cwd = await requireCwd();
      if (!cwd) return;
      await runWithProgress('Listing dashboards…', ['list'], cwd, statusBar);
    })
  );

  // ── entities refresh ──────────────────────────────────────────────────────
  context.subscriptions.push(
    vscode.commands.registerCommand('hadsync.entitiesRefresh', async () => {
      const cwd = await requireCwd();
      if (!cwd) return;
      await runWithProgress('Refreshing entity cache…', ['entities', 'refresh'], cwd, statusBar);
      vscode.window.showInformationMessage('hadsync: Entity cache refreshed.');
    })
  );

  // ── entities search ───────────────────────────────────────────────────────
  context.subscriptions.push(
    vscode.commands.registerCommand('hadsync.entitiesSearch', async () => {
      const cwd = await requireCwd();
      if (!cwd) return;
      const filter = await vscode.window.showInputBox({
        placeHolder: 'Filter by domain or name (e.g. light, roomba)',
        prompt: 'Search entity cache',
      });
      if (filter === undefined) return;
      const args = filter ? ['entities', 'list', filter] : ['entities', 'list'];
      await runWithProgress('Entity search…', args, cwd, statusBar);
    })
  );
}
