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

interface ValidationOutput {
  dashboards: Record<string, DashboardResult>;
  total_errors: number;
  total_warnings: number;
}

export class HadsyncDiagnosticsProvider implements vscode.Disposable {
  private readonly collection: vscode.DiagnosticCollection;

  constructor() {
    this.collection = vscode.languages.createDiagnosticCollection('hadsync');
  }

  /** Run validate --json-output and populate the Problems panel. */
  async validate(cwd: string, dashboardId?: string): Promise<ValidationOutput | undefined> {
    const args = ['--json-output', 'validate'];
    if (dashboardId) args.push(dashboardId);

    const result = await runHadsync(args, cwd);

    let data: ValidationOutput;
    try {
      data = JSON.parse(result.stdout);
    } catch {
      return undefined;
    }

    // Clear only the dashboards we just validated
    for (const [, dashboard] of Object.entries(data.dashboards)) {
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

    // Derive dashboard ID from the file path
    const { dashboardIdFromUri } = await import('./runner');
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
