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

    const dashboards = Object.values(state.dashboards);
    if (dashboards.length === 0) {
      this.setIdle();
      return;
    }

    // Find most recent pull
    const lastPull = dashboards
      .map(d => d.last_pull)
      .filter(Boolean)
      .sort()
      .at(-1);

    // Count modified (has pull but no push, or push before pull)
    const modified = dashboards.filter(d => {
      if (!d.last_pull) return false;
      if (!d.last_push) return true;
      return new Date(d.last_push) < new Date(d.last_pull);
    }).length;

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
