import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import { spawn } from 'child_process';

export interface RunResult {
  stdout: string;
  stderr: string;
  exitCode: number;
  /** True when the process could not be started (executable not found). */
  notFound: boolean;
}

/** Finds the hadsync executable: config setting → PATH. */
function getExecutable(): string {
  const configured = vscode.workspace
    .getConfiguration('hadsync')
    .get<string>('executablePath', '');
  return configured.trim() || 'hadsync';
}

/** Returns the workspace directory that contains .hadsync.yaml, or undefined. */
export function getWorkspaceCwd(): string | undefined {
  const folders = vscode.workspace.workspaceFolders;
  if (!folders) return undefined;
  for (const folder of folders) {
    if (fs.existsSync(path.join(folder.uri.fsPath, '.hadsync.yaml'))) {
      return folder.uri.fsPath;
    }
  }
  return folders[0]?.uri.fsPath;
}

/** Extracts dashboard ID (url_path) from an open lovelace.yaml path. */
export function dashboardIdFromUri(uri: vscode.Uri, cwd: string): string | undefined {
  const rel = path.relative(cwd, uri.fsPath);
  const parts = rel.split(path.sep);
  if (parts.length >= 2 && parts[parts.length - 1] === 'lovelace.yaml') {
    return parts[parts.length - 2];
  }
  return undefined;
}

/** Default timeout for any hadsync subprocess (ms). Prevents a hung process from freezing VS Code. */
const DEFAULT_TIMEOUT_MS = 60_000;

/**
 * Spawns hadsync with the given args, streams stdout/stderr, resolves on exit.
 * Always resolves — never rejects. Check `result.notFound` and `result.exitCode`.
 */
export function runHadsync(
  args: string[],
  cwd: string,
  onData?: (chunk: string) => void
): Promise<RunResult> {
  return new Promise(resolve => {
    const exe = getExecutable();
    const proc = spawn(exe, args, {
      cwd,
      env: { ...process.env },
      shell: process.platform === 'win32',
    });

    let stdout = '';
    let stderr = '';
    let settled = false;

    const timer = setTimeout(() => {
      if (!settled) {
        settled = true;
        proc.kill();
        resolve({
          stdout,
          stderr: `hadsync timed out after ${DEFAULT_TIMEOUT_MS / 1000}s`,
          exitCode: 1,
          notFound: false,
        });
      }
    }, DEFAULT_TIMEOUT_MS);

    proc.stdout.on('data', (d: Buffer) => {
      const chunk = d.toString();
      stdout += chunk;
      onData?.(chunk);
    });
    proc.stderr.on('data', (d: Buffer) => {
      stderr += d.toString();
    });
    proc.on('close', code => {
      if (!settled) {
        settled = true;
        clearTimeout(timer);
        resolve({ stdout, stderr, exitCode: code ?? 0, notFound: false });
      }
    });
    proc.on('error', err => {
      if (!settled) {
        settled = true;
        clearTimeout(timer);
        // ENOENT means the executable was not found on PATH
        const notFound = (err as NodeJS.ErrnoException).code === 'ENOENT';
        resolve({ stdout, stderr: err.message, exitCode: 1, notFound });
      }
    });
  });
}
