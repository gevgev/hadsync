# TODO

## VS Code Marketplace — publish extension

The extension is packaged and ready (`vscode-hadsync/hadsync-0.2.3.vsix`).
Publishing requires a one-time setup:

1. Create publisher at https://marketplace.visualstudio.com/manage
   - Sign in with Microsoft account
   - Set publisher ID to `gevgev` (matches `package.json`)

2. Generate a Personal Access Token at https://dev.azure.com
   - User Settings → Personal Access Tokens → New token
   - Organization: **All accessible organizations**
   - Scope: **Marketplace → Manage**

3. Publish:
   ```bash
   cd vscode-hadsync
   # rebuild if needed: npm run compile && npx @vscode/vsce package --no-dependencies
   npx @vscode/vsce publish --no-dependencies --pat <your-token>
   ```

4. After publishing, update README to add the Marketplace install link:
   ```
   Install from VS Code: search "hadsync" in the Extensions panel,
   or visit https://marketplace.visualstudio.com/items?itemName=gevgev.hadsync
   ```

Current extension version: **0.2.3**
VSIX location: `vscode-hadsync/hadsync-0.2.3.vsix`
