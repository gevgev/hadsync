import * as vscode from 'vscode';
import { getWorkspaceCwd, runHadsync } from './runner';

interface Issue {
  severity: 'ERROR' | 'WARN';
  message: string;
  line: number | null;
}

interface DashboardResult {
  file: string;
  passed: boolean;
  issues: Issue[];
}

export interface ValidationOutput {
  dashboards: Record<string, DashboardResult>;
  total_errors: number;
  total_warnings: number;
}

export class HadsyncDiagnosticsProvider implements vscode.Disposable {
  private readonly collection: vscode.DiagnosticCollection;

  constructor() {
    this.collection = vscode.languages.createDiagnosticCollection('hadsync');
  }

  /**
   * Run validate --json-output and populate the Problems panel.
   *
   * Returns the parsed ValidationOutput on success.
   * Returns undefined if hadsync could not be run or returned non-JSON output,
   * and shows an error notification explaining what went wrong.
   */
  async validate(cwd: string, dashboardId?: string): Promise<ValidationOutput | undefined> {
    const args = ['--json-output', 'validate'];
    if (dashboardId) args.push(dashboardId);

    const result = await runHadsync(args, cwd);

    // Executable not found — give an actionable message
    if (result.notFound) {
      vscode.window
        .showErrorMessage(
          'hadsync: executable not found. Install it or set hadsync.executablePath in settings.',
          'Open Settings'
        )
        .then(choice => {
          if (choice === 'Open Settings') {
            vscode.commands.executeCommand('workbench.action.openSettings', 'hadsync');
          }
        });
      return undefined;
    }

    let data: ValidationOutput;
    try {
      data = JSON.parse(result.stdout);
    } catch {
      // stdout is not JSON — hadsync may have printed a startup error or traceback
      const hint = result.stdout.trim() || result.stderr.trim() || 'no output received';
      vscode.window.showErrorMessage(
        `hadsync: validation output could not be parsed. ${hint.slice(0, 120)}`,
        'Show Output'
      );
      return undefined;
    }

    // Populate Problems panel for each dashboard
    for (const dashboard of Object.values(data.dashboards)) {
      const uri = vscode.Uri.file(dashboard.file);
      const diagnostics: vscode.Diagnostic[] = dashboard.issues.map(issue => {
        const lineNo = Math.max(0, (issue.line ?? 1) - 1);
        const range = new vscode.Range(lineNo, 0, lineNo, Number.MAX_SAFE_INTEGER);
        const severity =
          issue.severity === 'ERROR'
            ? vscode.DiagnosticSeverity.Error
            : vscode.DiagnosticSeverity.Warning;
        const diag = new vscode.Diagnostic(range, issue.message, severity);
        diag.source = 'hadsync';
        return diag;
      });
      this.collection.set(uri, diagnostics);
    }

    return data;
  }

  /** Validate the dashboard that contains the given lovelace.yaml URI. */
  async validateDocument(uri: vscode.Uri): Promise<void> {
    const cwd = getWorkspaceCwd();
    if (!cwd) return;
    const id = dashboardIdFromUri(uri, cwd);
    await this.validate(cwd, id);
  }

  clearAll(): void {
    this.collection.clear();
  }

  dispose(): void {
    this.collection.dispose();
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
