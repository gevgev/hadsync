import * as vscode from 'vscode';
import { HadsyncCompletionProvider } from './completion';
import { registerCommands } from './commands';
import { HadsyncDiagnosticsProvider } from './diagnostics';
import { HadsyncStatusBar } from './statusBar';
import { getWorkspaceCwd, runHadsync } from './runner';

/**
 * Check that the hadsync executable is reachable at activation time.
 * Shows a one-time error notification with a Settings link if it isn't.
 */
async function checkExecutable(cwd: string): Promise<void> {
  const result = await runHadsync(['--version'], cwd);
  if (result.notFound) {
    vscode.window
      .showErrorMessage(
        'hadsync extension: executable not found on PATH. '
        + 'Install hadsync (uv tool install /path/to/hadsync) or set hadsync.executablePath.',
        'Open Settings'
      )
      .then(choice => {
        if (choice === 'Open Settings') {
          vscode.commands.executeCommand('workbench.action.openSettings', 'hadsync');
        }
      });
  }
}

export function activate(context: vscode.ExtensionContext): void {
  const diagnostics = new HadsyncDiagnosticsProvider();
  const statusBar = new HadsyncStatusBar();

  registerCommands(context, diagnostics, statusBar);

  // Validate + optionally auto-push on lovelace.yaml save
  context.subscriptions.push(
    vscode.workspace.onDidSaveTextDocument(async doc => {
      if (!doc.fileName.endsWith('lovelace.yaml')) return;
      const cwd = getWorkspaceCwd();
      if (!cwd) return;
      const config = vscode.workspace.getConfiguration('hadsync');
      if (!config.get<boolean>('validateOnSave', true)) return;

      try {
        await diagnostics.validateDocument(doc.uri);
        statusBar.refresh(cwd);

        if (config.get<boolean>('autoPushOnSave', false)) {
          const id = dashboardIdFromUri(doc.uri, cwd);
          const result = await diagnostics.validate(cwd, id);
          // Only auto-push when validation is clean
          if (result && result.total_errors === 0) {
            const args = id ? ['push', id, '--yes'] : ['push', '--yes'];
            const pushResult = await runHadsync(args, cwd);
            if (pushResult.exitCode !== 0) {
              vscode.window.showErrorMessage(
                'hadsync: auto-push failed — see output for details.'
              );
            } else {
              statusBar.refresh(cwd);
            }
          }
        }
      } catch (err) {
        // Surface unexpected errors from the save hook rather than letting
        // them silently disappear into the extension host console
        vscode.window.showErrorMessage(`hadsync: unexpected error on save: ${err}`);
      }
    })
  );

  // Entity ID autocomplete in lovelace.yaml files
  context.subscriptions.push(
    vscode.languages.registerCompletionItemProvider(
      [{ scheme: 'file', pattern: '**/lovelace.yaml' }],
      new HadsyncCompletionProvider(),
      ':', ' ', '-'
    )
  );

  context.subscriptions.push(diagnostics, statusBar);

  const cwd = getWorkspaceCwd();
  if (cwd) {
    // Check the executable is reachable before doing anything else
    checkExecutable(cwd);
    statusBar.refresh(cwd);

    const config = vscode.workspace.getConfiguration('hadsync');
    if (config.get<boolean>('validateOnSave', true)) {
      // Initial validation on activation — fire and forget; errors handled inside validate()
      diagnostics.validate(cwd);
    }
  }
}

function dashboardIdFromUri(uri: vscode.Uri, cwd: string): string | undefined {
  const path = require('path') as typeof import('path');
  const rel = path.relative(cwd, uri.fsPath);
  const parts = rel.split(path.sep);
  if (parts.length >= 2 && parts[parts.length - 1] === 'lovelace.yaml') {
    return parts[parts.length - 2];
  }
  return undefined;
}

export function deactivate(): void {
  // Nothing to clean up beyond what VS Code disposes via subscriptions
}
