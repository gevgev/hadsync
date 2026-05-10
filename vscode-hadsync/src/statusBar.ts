import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';

interface DashboardState {
  last_pull?: string;
  last_push?: string;
}

interface StateFile {
  dashboards: Record<string, DashboardState>;
}

function readState(cwd: string): StateFile | undefined {
  const p = path.join(cwd, '.hadsync-state.json');
  try {
    return JSON.parse(fs.readFileSync(p, 'utf8')) as StateFile;
  } catch {
    return undefined;
  }
}

function formatRelative(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(ms / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

/**
 * Returns true if the lovelace.yaml for a given dashboard has been modified
 * on disk since the last pull — matching the same mtime logic used by
 * 'hadsync status' in the CLI.
 */
function isLocallyModified(cwd: string, urlPath: string, lastPull: string): boolean {
  try {
    const yamlPath = path.join(cwd, urlPath, 'lovelace.yaml');
    const stat = fs.statSync(yamlPath);
    const pullTime = new Date(lastPull).getTime();
    return stat.mtimeMs > pullTime;
  } catch {
    return false;
  }
}

export class HadsyncStatusBar implements vscode.Disposable {
  private readonly item: vscode.StatusBarItem;

  constructor() {
    this.item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 10);
    this.item.command = 'hadsync.status';
    this.item.tooltip = 'Click to show hadsync sync status';
    this.item.show();
    this.setIdle();
  }

  setIdle(): void {
    this.item.text = '$(sync) hadsync';
  }

  setWorking(label: string): void {
    this.item.text = `$(loading~spin) hadsync: ${label}`;
  }

  refresh(cwd: string): void {
    const state = readState(cwd);
    if (!state) {
      this.item.text = '$(sync) hadsync: no pulls yet';
      return;
    }

    const entries = Object.entries(state.dashboards);
    if (entries.length === 0) {
      this.setIdle();
      return;
    }

    // Most recent pull across all dashboards
    const lastPull = entries
      .map(([, d]) => d.last_pull)
      .filter((ts): ts is string => Boolean(ts))
      .sort()
      .at(-1);

    // A dashboard is "locally modified" only when its lovelace.yaml mtime is
    // newer than last_pull — the same check 'hadsync status' uses.
    // "Never pushed" alone is NOT a modification.
    const modified = entries.filter(([urlPath, d]) =>
      d.last_pull ? isLocallyModified(cwd, urlPath, d.last_pull) : false
    ).length;

    if (modified > 0) {
      this.item.text = `$(sync-ignored) hadsync: ${modified} modified`;
    } else if (lastPull) {
      this.item.text = `$(check) hadsync: pulled ${formatRelative(lastPull)}`;
    } else {
      this.setIdle();
    }
  }

  dispose(): void {
    this.item.dispose();
  }
}
