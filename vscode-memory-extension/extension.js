const vscode = require('vscode');
const fs = require('fs');
const path = require('path');
const http = require('http');

let statusBarItem;
let saveNowItem;
let autoSaver;

/**
 * Convert a workspace path to Claude's project directory name.
 * e.g. "g:\My Drive\MyProjects\ClaudeMemory" → "g--My-Drive-MyProjects-ClaudeMemory"
 */
function workspaceToProjectDir(workspacePath) {
    // Normalize to forward slashes first
    let normalized = workspacePath.replace(/\\/g, '/');
    // Remove trailing slash
    normalized = normalized.replace(/\/$/, '');
    // Replace drive letter + colon + slash: "g:/" → "g--"
    normalized = normalized.replace(/^([a-zA-Z]):\//, '$1--');
    // Replace remaining slashes with hyphens
    normalized = normalized.replace(/\//g, '-');
    // Replace spaces with hyphens
    normalized = normalized.replace(/ /g, '-');
    return normalized;
}

/**
 * Find the Claude projects base directory.
 */
function getClaudeProjectsDir() {
    const homeDir = process.env.HOME || process.env.USERPROFILE;
    return path.join(homeDir, '.claude', 'projects');
}

/**
 * Find the most recent .jsonl conversation file in a project directory.
 */
function findActiveConversation(projectDir) {
    if (!fs.existsSync(projectDir)) {
        return null;
    }

    let mostRecentFile = null;
    let mostRecentTime = 0;

    const entries = fs.readdirSync(projectDir);
    for (const name of entries) {
        if (!name.endsWith('.jsonl')) continue;
        const filePath = path.join(projectDir, name);
        try {
            const stat = fs.statSync(filePath);
            if (stat.mtimeMs > mostRecentTime) {
                mostRecentTime = stat.mtimeMs;
                mostRecentFile = filePath;
            }
        } catch (e) {
            // Skip unreadable files
        }
    }

    return mostRecentFile;
}

/**
 * Read all lines from a file starting at a byte offset.
 * Returns { lines: string[], newOffset: number }
 */
function readNewLines(filePath, byteOffset) {
    const stat = fs.statSync(filePath);
    if (stat.size <= byteOffset) {
        return { lines: [], newOffset: byteOffset };
    }

    const fd = fs.openSync(filePath, 'r');
    const bufSize = stat.size - byteOffset;
    const buf = Buffer.alloc(bufSize);
    fs.readSync(fd, buf, 0, bufSize, byteOffset);
    fs.closeSync(fd);

    const text = buf.toString('utf8');
    const lines = text.split('\n').filter(l => l.trim());
    return { lines, newOffset: stat.size };
}

/**
 * Parse JSONL lines and extract user/assistant messages.
 * Returns { messages: [{role, content}], firstPrompt: string }
 */
function parseMessages(lines) {
    const messages = [];
    let firstPrompt = '';

    for (const line of lines) {
        let parsed;
        try {
            parsed = JSON.parse(line);
        } catch (e) {
            continue;
        }

        // Only process user and assistant message types
        if (parsed.type !== 'user' && parsed.type !== 'assistant') {
            continue;
        }

        const msg = parsed.message;
        if (!msg || !msg.role) continue;

        // Extract text content
        let content = '';
        if (typeof msg.content === 'string') {
            content = msg.content;
        } else if (Array.isArray(msg.content)) {
            const textParts = [];
            for (const item of msg.content) {
                if (item.type === 'text' && item.text) {
                    textParts.push(item.text);
                }
            }
            content = textParts.join('\n');
        }

        // Strip IDE metadata tags (e.g., <ide_opened_file>...</ide_opened_file>)
        content = content.replace(/<[^>]+>[^<]*<\/[^>]+>/g, '').trim();

        if (!content) continue;

        // Track first user prompt for title (skip very short/empty prompts)
        if (msg.role === 'user' && !firstPrompt && content.length > 5) {
            firstPrompt = content.substring(0, 80);
        }

        messages.push({ role: msg.role, content });
    }

    return { messages, firstPrompt };
}

/**
 * Format messages into readable text.
 */
function formatMessages(messages) {
    return messages.map(msg => {
        const prefix = msg.role === 'user' ? 'Human' : 'Claude';
        return `**${prefix}:**\n${msg.content}`;
    }).join('\n\n---\n\n');
}

/**
 * Extract key topics from conversation content for a descriptive title.
 * Looks for: file names, function names, abbreviations, tech terms, action verbs.
 */
function extractTopics(messages, maxTopics = 3) {
    // Strip IDE tags from text before analysis
    const text = messages.map(m => m.content).join(' ').replace(/<[^>]+>[^<]*<\/[^>]+>/g, '');
    const topics = [];
    const seen = new Set();

    function addTopic(t) {
        const key = t.toLowerCase();
        if (!seen.has(key)) {
            seen.add(key);
            topics.push(t);
        }
    }

    // 1. File names (highest priority)
    const filePattern = /\b([a-zA-Z_][\w-]*\.(py|js|ts|tsx|jsx|json|md|html|css|bat|sh|yaml|yml|toml|sql))\b/gi;
    let match;
    while ((match = filePattern.exec(text)) !== null) {
        addTopic(match[1]);
        if (topics.length >= maxTopics) return topics.join(', ');
    }

    // 2. Abbreviations and tech terms (e.g., MSIX, API, CORS, OAuth, PyQt6)
    const abbrPattern = /\b([A-Z][A-Z0-9]{2,}[a-z]*|[A-Z][a-z]+[A-Z]\w*)\b/g;
    const skipAbbrs = new Set(['THE', 'AND', 'FOR', 'BUT', 'NOT', 'YOU', 'ALL', 'CAN', 'HAS', 'HER', 'WAS', 'ONE', 'OUR', 'OUT', 'ARE', 'HIS', 'HOW', 'ITS', 'LET', 'MAY', 'NEW', 'NOW', 'OLD', 'SEE', 'WAY', 'WHO', 'DID', 'GET', 'GOT', 'HAD', 'HIM', 'USE', 'WILL', 'BEEN', 'EACH', 'MAKE', 'LIKE', 'LONG', 'LOOK', 'MANY', 'SOME', 'THEM', 'THEN', 'THIS', 'WHAT', 'WITH', 'HAVE', 'FROM', 'THAT', 'THEY', 'BEEN', 'SAID', 'JUST', 'ALSO', 'INTO', 'OVER', 'SUCH', 'TAKE', 'THAN', 'VERY', 'WHEN', 'COME', 'COULD', 'ABOUT', 'AFTER', 'BACK', 'ONLY', 'DONE', 'HERE', 'MUST', 'SURE', 'YEAH', 'DOES', 'STILL', 'WELL', 'DONT', 'WANT', 'RIGHT', 'KNOW', 'NEED']);
    while ((match = abbrPattern.exec(text)) !== null) {
        const term = match[1];
        if (!skipAbbrs.has(term.toUpperCase()) && term.length >= 3) {
            addTopic(term);
            if (topics.length >= maxTopics) return topics.join(', ');
        }
    }

    // 3. Function/method names
    const funcPattern = /\b(?:def|function|async|class)\s+([a-zA-Z_]\w+)/gi;
    while ((match = funcPattern.exec(text)) !== null) {
        addTopic(match[1]);
        if (topics.length >= maxTopics) return topics.join(', ');
    }

    // 4. Action keywords (lowest priority)
    const keywords = [
        'commit', 'push', 'merge', 'deploy', 'fix', 'bug', 'error', 'crash',
        'install', 'update', 'upgrade', 'test', 'build', 'refactor', 'optimize',
        'database', 'api', 'server', 'login', 'auth', 'payment',
        'debug', 'config', 'setup', 'migrate', 'docker', 'git'
    ];
    const lowerText = text.toLowerCase();
    for (const kw of keywords) {
        if (lowerText.includes(kw)) {
            addTopic(kw);
            if (topics.length >= maxTopics) return topics.join(', ');
        }
    }

    return topics.length > 0 ? topics.join(', ') : null;
}

/**
 * Send a memory entry to the Claude Memory HTTP server.
 */
function sendToMemoryServer(memoryEntry, port) {
    return new Promise((resolve, reject) => {
        const postData = JSON.stringify(memoryEntry);

        const options = {
            hostname: 'localhost',
            port: port,
            path: '/api/memories',
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(postData)
            }
        };

        const req = http.request(options, (res) => {
            let data = '';
            res.on('data', (chunk) => { data += chunk; });
            res.on('end', () => {
                if (res.statusCode >= 200 && res.statusCode < 300) {
                    resolve(data);
                } else {
                    reject(new Error(`Server returned status ${res.statusCode}`));
                }
            });
        });

        req.on('error', (e) => {
            reject(new Error(`Could not connect to Claude Memory on port ${port}. Is the app running?`));
        });

        req.write(postData);
        req.end();
    });
}

// =============================================
// AutoSaver
// =============================================

class AutoSaver {
    constructor(context) {
        this.context = context;
        this.timer = null;
        this.isRunning = false;
        this.isSaving = false;

        // State persisted across sessions via workspaceState
        this.lastByteOffset = context.workspaceState.get('cm.lastByteOffset', 0);
        this.lastFilePath = context.workspaceState.get('cm.lastFilePath', '');
        this.partNumber = context.workspaceState.get('cm.partNumber', 0);
        this.firstPrompt = context.workspaceState.get('cm.firstPrompt', '');
        this.totalMessagesSaved = context.workspaceState.get('cm.totalMessagesSaved', 0);
    }

    /**
     * Persist current state to workspace storage.
     */
    async _saveState() {
        await this.context.workspaceState.update('cm.lastByteOffset', this.lastByteOffset);
        await this.context.workspaceState.update('cm.lastFilePath', this.lastFilePath);
        await this.context.workspaceState.update('cm.partNumber', this.partNumber);
        await this.context.workspaceState.update('cm.firstPrompt', this.firstPrompt);
        await this.context.workspaceState.update('cm.totalMessagesSaved', this.totalMessagesSaved);
    }

    /**
     * Start the auto-save polling timer.
     */
    start() {
        if (this.isRunning) return;

        const config = vscode.workspace.getConfiguration('claudeMemory');
        const intervalSec = config.get('autoSaveInterval', 60);

        this.isRunning = true;
        this.timer = setInterval(() => this.check(), intervalSec * 1000);

        // Also run an immediate check
        this.check();

        console.log(`CM: Auto-save started (every ${intervalSec}s)`);
    }

    /**
     * Stop the auto-save timer.
     */
    stop() {
        if (this.timer) {
            clearInterval(this.timer);
            this.timer = null;
        }
        this.isRunning = false;
        console.log('CM: Auto-save stopped');
    }

    /**
     * Restart with potentially new interval.
     */
    restart() {
        this.stop();
        this.start();
    }

    /**
     * Find the project directory for the current workspace.
     */
    _getProjectDir() {
        const folders = vscode.workspace.workspaceFolders;
        if (!folders || folders.length === 0) return null;

        const workspacePath = folders[0].uri.fsPath;
        const projectDirName = workspaceToProjectDir(workspacePath);
        const claudeDir = getClaudeProjectsDir();

        return path.join(claudeDir, projectDirName);
    }

    /**
     * Check for new conversation content and auto-save if found.
     */
    async check() {
        if (this.isSaving) return;

        try {
            const projectDir = this._getProjectDir();
            if (!projectDir) return;

            const conversationFile = findActiveConversation(projectDir);
            if (!conversationFile) return;

            // If conversation file changed (new session), reset offset
            if (conversationFile !== this.lastFilePath) {
                console.log(`CM: New conversation detected: ${path.basename(conversationFile)}`);
                this.lastFilePath = conversationFile;
                this.lastByteOffset = 0;
                this.partNumber = 0;
                this.firstPrompt = '';
                this.totalMessagesSaved = 0;
                await this._saveState();
            }

            // Check if file has grown
            let stat;
            try {
                stat = fs.statSync(conversationFile);
            } catch (e) {
                return;
            }

            if (stat.size <= this.lastByteOffset) {
                // No new content
                updateStatusBar('saved');
                return;
            }

            // Read new lines
            const { lines, newOffset } = readNewLines(conversationFile, this.lastByteOffset);
            if (lines.length === 0) {
                this.lastByteOffset = newOffset;
                await this._saveState();
                return;
            }

            // Parse messages
            const { messages, firstPrompt } = parseMessages(lines);
            if (messages.length === 0) {
                // New lines but no user/assistant messages (just progress events etc.)
                this.lastByteOffset = newOffset;
                await this._saveState();
                return;
            }

            // Skip saving if content is too short to be useful
            const totalContentLen = messages.reduce((sum, m) => sum + m.content.length, 0);
            if (totalContentLen < 100) {
                // Too little content — accumulate more before saving
                this.lastByteOffset = newOffset;
                await this._saveState();
                return;
            }

            // Track first prompt for title
            if (!this.firstPrompt && firstPrompt) {
                this.firstPrompt = firstPrompt;
            }

            // Format and save
            this.isSaving = true;
            updateStatusBar('syncing');

            this.partNumber++;
            const formattedText = formatMessages(messages);

            // Build descriptive title from topics in this batch
            const topics = extractTopics(messages);
            let title;
            if (topics) {
                title = `Claude Code: ${topics} (Part ${this.partNumber})`;
            } else {
                const titleBase = this.firstPrompt || 'Conversation';
                const titlePrompt = titleBase.length > 50 ? titleBase.substring(0, 50) + '...' : titleBase;
                title = `Claude Code: ${titlePrompt} (Part ${this.partNumber})`;
            }

            const config = vscode.workspace.getConfiguration('claudeMemory');
            const port = config.get('serverPort', 8765);

            const memoryEntry = {
                title: title,
                content: formattedText,
                category: 'conversation',
                tags: 'claude-code, auto-save, vscode'
            };

            try {
                await sendToMemoryServer(memoryEntry, port);

                this.lastByteOffset = newOffset;
                this.totalMessagesSaved += messages.length;
                await this._saveState();

                updateStatusBar('saved');
                console.log(`CM: Auto-saved Part ${this.partNumber} (${messages.length} messages, ${this.totalMessagesSaved} total)`);
            } catch (e) {
                updateStatusBar('error');
                console.error('CM: Auto-save failed:', e.message);
            }

            this.isSaving = false;

        } catch (e) {
            this.isSaving = false;
            updateStatusBar('error');
            console.error('CM: Auto-save check error:', e);
        }
    }
}

// =============================================
// Status bar
// =============================================

function updateStatusBar(state) {
    if (!statusBarItem) return;

    switch (state) {
        case 'auto':
            statusBarItem.text = '$(sync) CM: Auto';
            statusBarItem.tooltip = 'Claude Memory: Auto-save enabled. Click to toggle.';
            statusBarItem.backgroundColor = undefined;
            break;
        case 'syncing':
            statusBarItem.text = '$(sync~spin) CM: Saving...';
            statusBarItem.tooltip = 'Claude Memory: Saving conversation...';
            statusBarItem.backgroundColor = undefined;
            break;
        case 'saved':
            statusBarItem.text = '$(check) CM: Saved';
            statusBarItem.tooltip = `Claude Memory: Up to date (${autoSaver ? autoSaver.totalMessagesSaved : 0} msgs saved). Click to toggle.`;
            statusBarItem.backgroundColor = undefined;
            break;
        case 'off':
            statusBarItem.text = '$(circle-slash) CM: Off';
            statusBarItem.tooltip = 'Claude Memory: Auto-save disabled. Click to enable.';
            statusBarItem.backgroundColor = undefined;
            break;
        case 'error':
            statusBarItem.text = '$(error) CM: Err';
            statusBarItem.tooltip = 'Claude Memory: Connection error. Is the app running?';
            statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.errorBackground');
            break;
    }
}

// =============================================
// Manual save (full conversation)
// =============================================

async function saveConversationManual() {
    try {
        if (!autoSaver) {
            vscode.window.showWarningMessage('Claude Memory auto-saver not initialized.');
            return;
        }

        const projectDir = autoSaver._getProjectDir();
        if (!projectDir) {
            vscode.window.showWarningMessage('No workspace folder open.');
            return;
        }

        const conversationFile = findActiveConversation(projectDir);
        if (!conversationFile) {
            vscode.window.showWarningMessage('No Claude Code conversation found.');
            return;
        }

        // Read entire file
        const { lines } = readNewLines(conversationFile, 0);
        const { messages, firstPrompt } = parseMessages(lines);

        if (messages.length === 0) {
            vscode.window.showWarningMessage('Conversation is empty.');
            return;
        }

        const formattedText = formatMessages(messages);
        const timestamp = new Date().toISOString().replace('T', ' ').substring(0, 16);
        const titlePrompt = firstPrompt ? firstPrompt.substring(0, 50) : 'Conversation';

        const config = vscode.workspace.getConfiguration('claudeMemory');
        const port = config.get('serverPort', 8765);

        const memoryEntry = {
            title: `Claude Code: ${titlePrompt} - ${timestamp}`,
            content: formattedText,
            category: 'conversation',
            tags: 'claude-code, manual-save, vscode'
        };

        await sendToMemoryServer(memoryEntry, port);

        vscode.window.showInformationMessage(
            `Saved ${messages.length} messages to Claude Memory!`
        );

    } catch (error) {
        vscode.window.showErrorMessage(`Failed to save: ${error.message}`);
    }
}

// =============================================
// Toggle auto-save
// =============================================

function toggleAutoSave() {
    const config = vscode.workspace.getConfiguration('claudeMemory');
    const current = config.get('autoSave', true);

    config.update('autoSave', !current, vscode.ConfigurationTarget.Global).then(() => {
        if (!current) {
            // Turning on
            autoSaver.start();
            updateStatusBar('auto');
            vscode.window.showInformationMessage('Claude Memory: Auto-save enabled');
        } else {
            // Turning off
            autoSaver.stop();
            updateStatusBar('off');
            vscode.window.showInformationMessage('Claude Memory: Auto-save disabled');
        }
    });
}

// =============================================
// Extension lifecycle
// =============================================

/**
 * @param {vscode.ExtensionContext} context
 */
function activate(context) {
    console.log('Claude Memory Saver v2.0 active');

    // Status bar — auto-save indicator (click to toggle)
    statusBarItem = vscode.window.createStatusBarItem(
        vscode.StatusBarAlignment.Right,
        100
    );
    statusBarItem.command = 'claude-memory.toggleAutoSave';
    statusBarItem.show();

    // Status bar — Save Now button
    saveNowItem = vscode.window.createStatusBarItem(
        vscode.StatusBarAlignment.Right,
        99
    );
    saveNowItem.text = '$(cloud-upload) CM Save';
    saveNowItem.tooltip = 'Save full conversation to Claude Memory now';
    saveNowItem.command = 'claude-memory.saveConversation';
    saveNowItem.show();

    // AutoSaver
    autoSaver = new AutoSaver(context);

    // Start auto-save if enabled
    const config = vscode.workspace.getConfiguration('claudeMemory');
    if (config.get('autoSave', true)) {
        autoSaver.start();
        updateStatusBar('auto');
    } else {
        updateStatusBar('off');
    }

    // Commands
    const saveCmd = vscode.commands.registerCommand(
        'claude-memory.saveConversation',
        saveConversationManual
    );

    const toggleCmd = vscode.commands.registerCommand(
        'claude-memory.toggleAutoSave',
        toggleAutoSave
    );

    // Watch for settings changes
    const configWatcher = vscode.workspace.onDidChangeConfiguration(e => {
        if (e.affectsConfiguration('claudeMemory.autoSaveInterval')) {
            if (autoSaver.isRunning) {
                autoSaver.restart();
            }
        }
        if (e.affectsConfiguration('claudeMemory.autoSave')) {
            const enabled = vscode.workspace.getConfiguration('claudeMemory').get('autoSave', true);
            if (enabled && !autoSaver.isRunning) {
                autoSaver.start();
                updateStatusBar('auto');
            } else if (!enabled && autoSaver.isRunning) {
                autoSaver.stop();
                updateStatusBar('off');
            }
        }
    });

    context.subscriptions.push(saveCmd, toggleCmd, statusBarItem, saveNowItem, configWatcher);
}

function deactivate() {
    if (autoSaver) {
        autoSaver.stop();
    }
    if (statusBarItem) {
        statusBarItem.dispose();
    }
}

module.exports = {
    activate,
    deactivate
};
