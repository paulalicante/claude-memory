const vscode = require('vscode');
const fs = require('fs');
const path = require('path');
const http = require('http');

let statusBarItem;

/**
 * @param {vscode.ExtensionContext} context
 */
function activate(context) {
    console.log('Claude Memory Saver extension is now active');

    // Create status bar item
    statusBarItem = vscode.window.createStatusBarItem(
        vscode.StatusBarAlignment.Right,
        100
    );
    statusBarItem.text = '$(save) Save to CM';
    statusBarItem.tooltip = 'Save current conversation to Claude Memory';
    statusBarItem.command = 'claude-memory.saveConversation';
    statusBarItem.show();

    // Register command
    let disposable = vscode.commands.registerCommand(
        'claude-memory.saveConversation',
        saveConversation
    );

    context.subscriptions.push(disposable, statusBarItem);
}

async function saveConversation() {
    try {
        // Find the most recent conversation file
        const conversationFile = await findMostRecentConversation();

        if (!conversationFile) {
            vscode.window.showWarningMessage(
                'No Claude Code conversation found. Make sure you have an active conversation.'
            );
            return;
        }

        // Parse the conversation
        const conversation = parseConversation(conversationFile);

        if (conversation.messages.length === 0) {
            vscode.window.showWarningMessage('Conversation file is empty.');
            return;
        }

        // Format the conversation
        const formattedText = formatConversation(conversation.messages);
        const timestamp = new Date().toISOString().replace('T', ' ').substring(0, 16);

        // Create memory entry
        const memoryEntry = {
            title: `Claude Conversation - ${timestamp}`,
            content: formattedText,
            category: 'Conversation',
            tags: 'claude,ai,chat,vscode'
        };

        // Send to Claude Memory server
        const config = vscode.workspace.getConfiguration('claudeMemory');
        const port = config.get('serverPort', 8765);

        await sendToMemoryServer(memoryEntry, port);

        vscode.window.showInformationMessage(
            `✅ Saved conversation (${conversation.messages.length} messages) to Claude Memory!`
        );

    } catch (error) {
        console.error('Error saving conversation:', error);
        vscode.window.showErrorMessage(
            `Failed to save conversation: ${error.message}`
        );
    }
}

async function findMostRecentConversation() {
    const homeDir = process.env.HOME || process.env.USERPROFILE;
    const claudeDir = path.join(homeDir, '.claude', 'projects');

    if (!fs.existsSync(claudeDir)) {
        return null;
    }

    // Get all project folders
    const projectFolders = fs.readdirSync(claudeDir)
        .map(name => path.join(claudeDir, name))
        .filter(p => fs.statSync(p).isDirectory());

    // Find most recent .jsonl file
    let mostRecentFile = null;
    let mostRecentTime = 0;

    for (const folder of projectFolders) {
        const jsonlFiles = fs.readdirSync(folder)
            .filter(name => name.endsWith('.jsonl'))
            .map(name => path.join(folder, name));

        for (const file of jsonlFiles) {
            const stat = fs.statSync(file);
            if (stat.mtimeMs > mostRecentTime) {
                mostRecentTime = stat.mtimeMs;
                mostRecentFile = file;
            }
        }
    }

    return mostRecentFile;
}

function parseConversation(filePath) {
    const content = fs.readFileSync(filePath, 'utf8');
    const lines = content.split('\n').filter(line => line.trim());

    const messages = [];

    for (const line of lines) {
        try {
            const msg = JSON.parse(line);
            messages.push(msg);
        } catch (e) {
            // Skip invalid lines
        }
    }

    return { messages };
}

function formatConversation(messages) {
    const formattedMessages = [];

    for (const msg of messages) {
        const role = (msg.role || 'unknown').toUpperCase();
        let content = msg.content || '';

        // Handle array content (like assistant messages with text blocks)
        if (Array.isArray(content)) {
            const textParts = [];
            for (const item of content) {
                if (typeof item === 'object' && item.type === 'text') {
                    textParts.push(item.text || '');
                } else if (typeof item === 'string') {
                    textParts.push(item);
                }
            }
            content = textParts.join('\n');
        }

        if (content.trim()) {
            formattedMessages.push(`[${role}]\n${content}\n`);
        }
    }

    return formattedMessages.join('\n');
}

function sendToMemoryServer(memoryEntry, port) {
    return new Promise((resolve, reject) => {
        const postData = JSON.stringify(memoryEntry);

        const options = {
            hostname: 'localhost',
            port: port,
            path: '/memory',
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(postData)
            }
        };

        const req = http.request(options, (res) => {
            let data = '';

            res.on('data', (chunk) => {
                data += chunk;
            });

            res.on('end', () => {
                if (res.statusCode === 200) {
                    resolve(data);
                } else {
                    reject(new Error(
                        `Server returned status ${res.statusCode}. ` +
                        `Make sure Claude Memory is running.`
                    ));
                }
            });
        });

        req.on('error', (e) => {
            reject(new Error(
                `Could not connect to Claude Memory server on port ${port}. ` +
                `Make sure the app is running.`
            ));
        });

        req.write(postData);
        req.end();
    });
}

function deactivate() {
    if (statusBarItem) {
        statusBarItem.dispose();
    }
}

module.exports = {
    activate,
    deactivate
};
