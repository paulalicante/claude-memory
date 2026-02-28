#!/usr/bin/env node

/**
 * Simple test for Otterly Memory Saver server
 * Tests direct database insertion without MCP protocol
 */

const Database = require('better-sqlite3');
const path = require('path');

// Use the actual database path
const DB_PATH = process.env.OTTERLY_DB_PATH || 'G:\\My Drive\\MyProjects\\ClaudeMemory\\memory.db';

console.log('Testing Otterly Memory Saver...');
console.log('Database path:', DB_PATH);

try {
  const db = new Database(DB_PATH, { fileMustExist: true });
  db.pragma('journal_mode = WAL');
  console.log('Database connected successfully');

  // Test insert
  const testTitle = `[TEST] Chat: Testing MCPB extension...`;
  const testContent = `**Human:**\nThis is a test message from the MCPB extension test script.\n\n---\n\n**Claude:**\nThis is a simulated response to verify the database connection works correctly.`;

  const sessionId = new Date().toISOString().split('T')[0] + '-test';
  const dateStr = new Date().toISOString().split('T')[0];

  const stmt = db.prepare(`
    INSERT INTO entries (session_id, date, category, tags, title, content, source_conversation, archived)
    VALUES (?, ?, ?, ?, ?, ?, ?, 0)
  `);

  const result = stmt.run(
    sessionId,
    dateStr,
    'conversation',
    'claude-desktop, auto-save, test',
    testTitle,
    testContent,
    JSON.stringify({ source: 'mcpb-test', timestamp: new Date().toISOString() })
  );

  console.log('Test entry inserted with ID:', result.lastInsertRowid);

  // Update FTS index
  const ftsStmt = db.prepare(`
    INSERT INTO entries_fts (rowid, title, content, tags)
    VALUES (?, ?, ?, ?)
  `);
  ftsStmt.run(result.lastInsertRowid, testTitle, testContent, 'claude-desktop, auto-save, test');
  console.log('FTS index updated');

  // Verify by reading back
  const readStmt = db.prepare('SELECT id, title FROM entries WHERE id = ?');
  const entry = readStmt.get(result.lastInsertRowid);
  console.log('Verified entry:', entry);

  db.close();
  console.log('\nTest PASSED! Extension can write to database.');
  console.log('Check Otterly Memory app for entry titled:', testTitle);

} catch (error) {
  console.error('Test FAILED:', error.message);
  process.exit(1);
}
