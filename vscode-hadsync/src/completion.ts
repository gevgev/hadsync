import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import { getWorkspaceCwd } from './runner';

interface EntityInfo {
  friendly_name: string;
  domain: string;
}

interface EntityCache {
  refreshed_at: string;
  entities: Record<string, EntityInfo>;
}

/** Provides entity ID completions inside lovelace.yaml files. */
export class HadsyncCompletionProvider implements vscode.CompletionItemProvider {
  provideCompletionItems(
    document: vscode.TextDocument,
    position: vscode.Position
  ): vscode.CompletionItem[] {
    const cwd = getWorkspaceCwd();
    if (!cwd) return [];

    const cachePath = path.join(cwd, '.ha-entities.json');
    if (!fs.existsSync(cachePath)) return [];

    const lineText = document.lineAt(position).text.substring(0, position.character);

    // Trigger after "entity: ", "- entity: ", or bare "- " in an entities list
    const isEntityField = /entity\s*:\s*\S*$/.test(lineText);
    const isListItem = /^\s*-\s*\S*$/.test(lineText);
    if (!isEntityField && !isListItem) return [];

    let cache: EntityCache;
    try {
      cache = JSON.parse(fs.readFileSync(cachePath, 'utf8')) as EntityCache;
    } catch {
      return [];
    }

    return Object.entries(cache.entities).map(([entityId, info]) => {
      const item = new vscode.CompletionItem(entityId, vscode.CompletionItemKind.Value);
      item.detail = info.friendly_name || '';
      item.documentation = new vscode.MarkdownString(
        `**Domain:** ${info.domain}\n\n**Friendly name:** ${info.friendly_name || '—'}`
      );
      // Replace the partial text already typed
      item.filterText = entityId;
      item.insertText = entityId;
      return item;
    });
  }
}
