import * as vscode from 'vscode';
import { dashboardIdFromUri, getWorkspaceCwd, runHadsync } from './runner';
import { HadsyncDiagnosticsProvider } from './diagnostics';
import { HadsyncStatusBar } from './statusBar';

const out = vscode.window.createOutputChannel('hadsync');

function showOutput(): void {
  out.show(true);  // preservesFocus = true
}

function appendLine(text: string): void {
  // Strip ANSI escape codes produced by Rich terminal output
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

/** Open VS Code settings filtered to the hadsync section. */
function openSettings(): void {
  vscode.commands.executeCommand('workbench.action.openSettings', 'hadsync');
}

/**
 * Show an error popup appropriate to the failure.
 * If the executable was not found, offer to open Settings.
 * Otherwise, offer to show the output panel.
 */
function showFailureNotification(label: string, notFound: boolean): void {
  if (notFound) {
    vscode.window
      .showErrorMessage(
        `hadsync: executable not found. Install hadsync or set hadsync.executablePath.`,
        'Open Settings'
      )
      .then(choice => { if (choice === 'Open Settings') openSettings(); });
  } else {
    vscode.window
      .showErrorMessage(
        `hadsync: ${label} failed — see output for details.`,
        'Show Output'
      )
      .then(choice => { if (choice === 'Show Output') out.show(); });
  }
}

/**
 * Run a hadsync command, stream its output to the output channel, and show an
 * error notification if it exits non-zero. Returns true on success.
 */
async function runWithProgress(
  label: string,
  args: string[],
  cwd: string,
  statusBar: HadsyncStatusBar
): Promise<boolean> {
  statusBar.setWorking(label);
  out.clear();
  showOutput();

  let result = { stdout: '', stderr: '', exitCode: 0, notFound: false };

  await vscode.window.withProgress(
    { location: vscode.ProgressLocation.Window, title: `hadsync: ${label}` },
    async () => {
      result = await runHadsync(args, cwd, chunk => appendLine(chunk));
      if (result.stderr) appendLine(result.stderr);
    }
  );

  statusBar.refresh(cwd);

  if (result.exitCode !== 0) {
    showFailureNotification(label, result.notFound);
    return false;
  }
  return true;
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
      const ok = await runWithProgress('Pulling dashboards…', ['pull'], cwd, statusBar);
      if (ok) await diagnostics.validate(cwd);
    })
  );

  // ── pull (active file's dashboard) ────────────────────────────────────────
  context.subscriptions.push(
    vscode.commands.registerCommand('hadsync.pullOne', async () => {
      const cwd = await requireCwd();
      if (!cwd) return;
      const id = activeDashboardId();
      const args = id ? ['pull', id] : ['pull'];
      const ok = await runWithProgress(`Pulling ${id ?? 'all'}…`, args, cwd, statusBar);
      if (ok && id) await diagnostics.validate(cwd, id);
    })
  );

  // ── push (all) ────────────────────────────────────────────────────────────
  context.subscriptions.push(
    vscode.commands.registerCommand('hadsync.push', async () => {
      const cwd = await requireCwd();
      if (!cwd) return;
      const confirmed = await vscode.window.showWarningMessage(
        'Push ALL dashboards to Home Assistant?',
        { modal: true },
        'Push'
      );
      if (confirmed !== 'Push') return;
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
        vscode.window.showWarningMessage(
          'hadsync: Open a lovelace.yaml file to push a specific dashboard.'
        );
        return;
      }
      const confirmed = await vscode.window.showWarningMessage(
        `Push '${id}' to Home Assistant?`,
        { modal: true },
        'Push'
      );
      if (confirmed !== 'Push') return;
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
      if (result === undefined) {
        // diagnostics.validate already showed an error notification
        return;
      }
      const msg =
        result.total_errors > 0
          ? `${result.total_errors} error(s), ${result.total_warnings} warning(s)`
          : result.total_warnings > 0
            ? `0 errors, ${result.total_warnings} warning(s) — review before pushing`
            : 'All dashboards passed';
      if (result.total_errors > 0) {
        vscode.window.showErrorMessage(`hadsync validate: ${msg}`, 'Show Problems').then(
          choice => { if (choice === 'Show Problems') vscode.commands.executeCommand('workbench.actions.view.problems'); }
        );
      } else {
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
      if (result === undefined) return;
      const dashboard = id ? result.dashboards[id] : undefined;
      const issues = dashboard?.issues ?? [];
      const errs = issues.filter(i => i.severity === 'ERROR').length;
      const warns = issues.filter(i => i.severity === 'WARN').length;
      const label = id ?? 'all dashboards';
      if (errs > 0) {
        vscode.window.showErrorMessage(`hadsync: ${label} — ${errs} error(s), ${warns} warning(s)`, 'Show Problems').then(
          choice => { if (choice === 'Show Problems') vscode.commands.executeCommand('workbench.actions.view.problems'); }
        );
      } else if (warns > 0) {
        vscode.window.showWarningMessage(`hadsync: ${label} — ${warns} warning(s)`);
      } else {
        vscode.window.showInformationMessage(`hadsync: ${label} passed`);
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
      const ok = await runWithProgress(
        'Refreshing entity cache…', ['entities', 'refresh'], cwd, statusBar
      );
      if (ok) vscode.window.showInformationMessage('hadsync: Entity cache refreshed.');
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
