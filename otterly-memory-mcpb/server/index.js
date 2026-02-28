#!/usr/bin/env node

/**
 * Otterly Memory Saver - MCP Server for Claude Desktop
 * 
 * Saves conversation turns to Otterly Memory SQLite database.
 * Uses Python's built-in sqlite3 via child_process to avoid
 * native Node module version mismatches with Claude Desktop's Node.js.
 */

const { Server } = require('@modelcontextprotocol/sdk/server/index.js');
const { StdioServerTransport } = require('@modelcontextprotocol/sdk/server/stdio.js');
const {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} = require('@modelcontextprotocol/sdk/types.js');

const { execFile } = require('child_process');
const fs = require('fs');
const path = require('path');

// Database path with hardcoded fallback
const DB_PATH = process.env.OTTERLY_DB_PATH || 'G:\\My Drive\\MyProjects\\ClaudeMemory\\memory.db';
const PYTHON_PATH = 'C:\\Python314\\python.exe';

console.error(`Otterly Memory Saver v1.2: DB=${DB_PATH}, Python=${PYTHON_PATH}`);
console.error(`DB exists: ${fs.existsSync(DB_PATH)}, Python exists: ${fs.existsSync(PYTHON_PATH)}`);

/**
 * Execute a Python script that does the SQLite work.
 */
function runPythonSqlite(userMessage, assistantMessage, conversationId) {
  return new Promise((resolve, reject) => {
    const pythonScript = `
import sqlite3
import json
import sys
from datetime import datetime

db_path = sys.argv[1]
user_msg = sys.argv[2]
assistant_msg = sys.argv[3]
conv_id = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] != 'null' else None

now = datetime.now()
session_id = conv_id or now.strftime('%Y-%m-%d-%H')
date_str = now.strftime('%Y-%m-%d')

content = f"**Human:**\\n{user_msg}\\n\\n---\\n\\n**Claude:**\\n{assistant_msg}"

title_text = user_msg.strip()[:55]
if len(user_msg.strip()) > 55:
    title_text = title_text[:52] + '...'
title = f"Chat: {title_text}"

source_json = json.dumps({"source": "claude-desktop", "timestamp": now.isoformat()})

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO entries (session_id, date, category, tags, title, content, source_conversation, archived) VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
        (session_id, date_str, 'conversation', 'claude-desktop, auto-save', title, content, source_json)
    )
    entry_id = cursor.lastrowid
    try:
        cursor.execute(
            "INSERT INTO entries_fts (rowid, title, content, tags) VALUES (?, ?, ?, ?)",
            (entry_id, title, content, 'claude-desktop, auto-save')
        )
    except Exception:
        pass
    conn.commit()
    conn.close()
    print(json.dumps({"success": True, "entry_id": entry_id, "message": f"Saved conversation turn (ID: {entry_id})"}))
except Exception as e:
    print(json.dumps({"success": False, "error": str(e)}))
`;

    const args = ['-c', pythonScript, DB_PATH, userMessage, assistantMessage, conversationId || 'null'];

    execFile(PYTHON_PATH, args, { timeout: 10000, maxBuffer: 1024 * 1024 }, (error, stdout, stderr) => {
      if (stderr) console.error('Python stderr:', stderr);
      if (error) {
        console.error('Python exec error:', error.message);
        resolve({ success: false, error: error.message });
        return;
      }
      try {
        resolve(JSON.parse(stdout.trim()));
      } catch (parseError) {
        console.error('Failed to parse Python output:', stdout);
        resolve({ success: false, error: `Parse error: ${parseError.message}` });
      }
    });
  });
}

const server = new Server(
  { name: 'otterly-memory-saver', version: '1.2.0' },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [{
      name: 'save_conversation_turn',
      description: 'Saves a user message and assistant response to the Otterly Memory database. Call this after every response to maintain conversation history.',
      inputSchema: {
        type: 'object',
        properties: {
          user_message: { type: 'string', description: "The user's message or question" },
          assistant_message: { type: 'string', description: "Claude's complete response to the user" },
          conversation_id: { type: 'string', description: 'Optional identifier to group messages from the same conversation' },
        },
        required: ['user_message', 'assistant_message'],
      },
    }],
  };
});

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  if (name === 'save_conversation_turn') {
    const { user_message, assistant_message, conversation_id } = args;
    if (!user_message || !assistant_message) {
      return { content: [{ type: 'text', text: JSON.stringify({ success: false, error: 'Both fields required' }) }] };
    }
    const result = await runPythonSqlite(user_message, assistant_message, conversation_id);
    return { content: [{ type: 'text', text: JSON.stringify(result) }] };
  }

  return { content: [{ type: 'text', text: JSON.stringify({ success: false, error: `Unknown tool: ${name}` }) }] };
});

process.on('SIGINT', () => process.exit(0));
process.on('SIGTERM', () => process.exit(0));

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('Otterly Memory Saver MCP server running (Python sqlite3 backend)');
}

main().catch((error) => {
  console.error('Server error:', error);
  process.exit(1);
});
