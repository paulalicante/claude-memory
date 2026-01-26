# Claude Memory Saver - VS Code Extension

Save your Claude Code conversations to Claude Memory with one click!

## Features

- **Status Bar Button**: Click "💾 Save to CM" in the bottom right to instantly save your conversation
- **Command Palette**: Run "Save Conversation to Claude Memory" from the command palette (Ctrl+Shift+P)
- **Automatic Detection**: Finds your most recent Claude Code conversation automatically
- **Full Formatting**: Preserves all messages with role markers ([USER], [ASSISTANT])

## Installation

### Option 1: Load Unpacked (Development)

1. Open VS Code
2. Go to Extensions view (Ctrl+Shift+X)
3. Click the "..." menu at the top of the Extensions view
4. Select "Install from VSIX..." (you'll need to package first, see below)

OR for development:

1. Copy the `vscode-memory-extension` folder to your VS Code extensions folder:
   - Windows: `%USERPROFILE%\.vscode\extensions\`
   - Mac/Linux: `~/.vscode/extensions/`
2. Restart VS Code
3. The "💾 Save to CM" button should appear in the status bar (bottom right)

### Option 2: Package as VSIX

```bash
# Install vsce (VS Code Extension Manager)
npm install -g @vscode/vsce

# Navigate to the extension folder
cd vscode-memory-extension

# Package the extension
vsce package

# Install the generated .vsix file
# In VS Code: Extensions > ... > Install from VSIX
```

## Requirements

- **Claude Memory app** must be running (the HTTP server on port 8765)
- **VS Code** version 1.80.0 or higher
- Active Claude Code conversation

## Usage

### Method 1: Status Bar Button
1. Start a conversation with Claude Code in VS Code
2. Click the **"💾 Save to CM"** button in the bottom right corner of VS Code
3. You'll see a confirmation message with the number of messages saved

### Method 2: Command Palette
1. Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac)
2. Type "Save Conversation to Claude Memory"
3. Press Enter

### What Gets Saved

- **Title**: "Claude Conversation - [timestamp]"
- **Content**: All messages formatted with [USER] and [ASSISTANT] role markers
- **Category**: "Conversation"
- **Tags**: "claude,ai,chat,vscode"

## Configuration

You can configure the Claude Memory server port in VS Code settings:

```json
{
  "claudeMemory.serverPort": 8765
}
```

## Troubleshooting

### "Could not connect to Claude Memory server"
- Make sure the Claude Memory app is running
- Check that the HTTP server is running on the configured port (default: 8765)
- Restart the Claude Memory app if needed

### "No Claude Code conversation found"
- Make sure you have an active conversation with Claude Code
- Check that conversation files exist in `~/.claude/projects/`

### Button not showing
- Reload VS Code window (Ctrl+Shift+P > "Reload Window")
- Check that the extension is enabled in the Extensions view

## How It Works

1. Finds the most recent `.jsonl` conversation file in `~/.claude/projects/`
2. Parses all message objects from the JSONL format
3. Formats messages with role markers
4. POSTs to `http://localhost:8765/memory` (your Claude Memory HTTP server)
5. Shows success notification

## Similar To

This works just like the Gmail Memory Extension for Chrome:
- Chrome extension adds button to Gmail → saves emails to Claude Memory
- VS Code extension adds button to VS Code → saves conversations to Claude Memory

Both use the same HTTP server endpoint for consistency!

## License

MIT
