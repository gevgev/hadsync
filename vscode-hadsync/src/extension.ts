import * as vscode from 'vscode';
import { HadsyncCompletionProvider } from './completion';
import { registerCommands } from './commands';
import { HadsyncDiagnosticsProvider } from './diagnostics';
import { HadsyncStatusBar } from './statusBar';
import { getWorkspaceCwd } from './runner';

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

      await diagnostics.validateDocument(doc.uri);
      statusBar.refresh(cwd);

      if (config.get<boolean>('autoPushOnSave', false)) {
        // Only auto-push if validation produced no errors
        const { dashboardIdFromUri } = await import('./runner');
        const id = dashboardIdFromUri(doc.uri, cwd);
        const result = await diagnostics.validate(cwd, id);
        if (result && result.total_errors === 0) {
          const args = id ? ['push', id, '--yes'] : ['push', '--yes'];
          vscode.commands.executeCommand('workbench.action.terminal.clear');
          const { runHadsync } = await import('./runner');
          await runHadsync(args, cwd);
          statusBar.refresh(cwd);
        }
      }
    })
  );

  // Entity ID autocomplete in lovelace.yaml files
  context.subscriptions.push(
    vscode.languages.registerCompletionItemProvider(
      [
        { scheme: 'file', pattern: '**/lovelace.yaml' },
      ],
      new HadsyncCompletionProvider(),
      ':', ' ', '-'
    )
  );

  context.subscriptions.push(diagnostics, statusBar);

  // Initial status bar refresh
  const cwd = getWorkspaceCwd();
  if (cwd) statusBar.refresh(cwd);

  // Validate all dashboards on activation if workspace has .hadsync.yaml
  if (cwd) {
    const config = vscode.workspace.getConfiguration('hadsync');
    if (config.get<boolean>('validateOnSave', true)) {
      diagnostics.validate(cwd);
    }
  }
}

export function deactivate(): void {
  // Nothing to clean up beyond what VS Code disposes via subscriptions
}
