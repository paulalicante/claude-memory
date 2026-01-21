/**
 * Claude.ai to Claude Memory - Content Script
 * Accumulates conversation turns and saves to Claude Memory
 */

(function() {
  'use strict';

  // Buffer configuration
  const CONFIG = {
    maxBufferChars: 15000,  // Max chars before prompting to save
    autoSaveThreshold: 0.9, // Auto-prompt at 90% full
    checkInterval: 2000     // How often to check for new messages (ms)
  };

  // State
  let messageBuffer = [];
  let floatingButton = null;
  let totalBufferChars = 0;
  let conversationTitle = '';
  let debugPanel = null;
  let debugMode = true; // Set to true to show debug panel
  let savedContentHashes = new Set(); // Track saved content to prevent re-adding

  /**
   * Get a simple hash for content deduplication
   */
  function getContentHash(role, content) {
    // Use role + first 100 chars normalized as hash
    const normalized = content.replace(/\s+/g, ' ').toLowerCase().substring(0, 100);
    return `${role}:${normalized}`;
  }

  /**
   * Create debug panel
   */
  function createDebugPanel() {
    if (debugPanel || !debugMode) return;

    debugPanel = document.createElement('div');
    debugPanel.id = 'cm-debug-panel';
    debugPanel.innerHTML = `
      <div class="cm-debug-header">
        <span>CM Debug</span>
        <button class="cm-debug-close">×</button>
      </div>
      <div class="cm-debug-content">
        <div class="cm-debug-section">
          <strong>Status:</strong> <span id="cm-debug-status">Initializing...</span>
        </div>
        <div class="cm-debug-section">
          <strong>Found Elements:</strong>
          <pre id="cm-debug-elements" style="max-height:150px;overflow:auto;font-size:10px;background:#f5f5f5;padding:4px;margin:4px 0;"></pre>
        </div>
        <div class="cm-debug-section">
          <strong>Messages in Buffer:</strong>
          <pre id="cm-debug-buffer" style="max-height:200px;overflow:auto;font-size:10px;background:#f5f5f5;padding:4px;margin:4px 0;"></pre>
        </div>
      </div>
    `;

    const style = document.createElement('style');
    style.textContent = `
      #cm-debug-panel {
        position: fixed;
        top: 10px;
        right: 10px;
        width: 400px;
        max-height: 500px;
        background: white;
        border: 2px solid #1a73e8;
        border-radius: 8px;
        z-index: 999999;
        font-family: monospace;
        font-size: 11px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
      }
      .cm-debug-header {
        background: #1a73e8;
        color: white;
        padding: 8px 12px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-weight: bold;
      }
      .cm-debug-close {
        background: none;
        border: none;
        color: white;
        font-size: 18px;
        cursor: pointer;
      }
      .cm-debug-content {
        padding: 10px;
        max-height: 450px;
        overflow-y: auto;
      }
      .cm-debug-section {
        margin-bottom: 10px;
      }
      .cm-debug-section strong {
        color: #1a73e8;
      }
    `;
    document.head.appendChild(style);
    document.body.appendChild(debugPanel);

    debugPanel.querySelector('.cm-debug-close').addEventListener('click', () => {
      debugPanel.remove();
      debugPanel = null;
      debugMode = false;
    });
  }

  /**
   * Update debug panel
   */
  function debugLog(section, content) {
    if (!debugPanel) return;
    const el = document.getElementById('cm-debug-' + section);
    if (el) {
      if (el.tagName === 'PRE') {
        el.textContent = content;
      } else {
        el.textContent = content;
      }
    }
  }

  /**
   * Get the conversation title from the page
   */
  function getConversationTitle() {
    // Try to get from the chat title/header
    const titleEl = document.querySelector('[data-testid="chat-title"]') ||
                    document.querySelector('h1') ||
                    document.querySelector('[class*="ConversationTitle"]');
    if (titleEl && titleEl.textContent.trim()) {
      return titleEl.textContent.trim();
    }
    // Fallback to first user message or generic title
    if (messageBuffer.length > 0) {
      const firstUserMsg = messageBuffer.find(m => m.role === 'user');
      if (firstUserMsg) {
        return firstUserMsg.content.substring(0, 50) + '...';
      }
    }
    return 'Claude Conversation ' + new Date().toLocaleDateString();
  }

  /**
   * Extract messages from the conversation
   */
  function extractMessages() {
    const messages = [];
    const debugInfo = [];

    // Use main or body, but filter out sidebar content
    const conversationArea = document.querySelector('main') || document.body;

    debugInfo.push(`Conversation area: ${conversationArea.tagName}`);

    // Collect all messages with their positions for ordering
    const orderedMessages = [];
    const processedElements = new Set();

    // Helper to check if element is in sidebar
    function isInSidebar(el) {
      return el.closest('[class*="sidebar"]') ||
             el.closest('[class*="Sidebar"]') ||
             el.closest('[class*="nav-"]') ||
             el.closest('[class*="project"]') ||
             el.closest('[class*="Project"]') ||
             el.closest('[data-testid*="sidebar"]') ||
             el.closest('[data-testid*="nav"]');
    }

    // Helper to get element signature for dedup
    function getSignature(el) {
      const rect = el.getBoundingClientRect();
      return `${Math.round(rect.top)}-${Math.round(rect.left)}-${el.tagName}`;
    }

    // ==========================================
    // STRATEGY 1: Find conversation turns/blocks
    // Look for turn containers that group user + assistant messages
    // ==========================================
    debugInfo.push(`\n--- STRATEGY 1: Turn containers ---`);

    // Try various turn container selectors
    const turnSelectors = [
      '[data-testid*="turn"]',
      '[data-testid*="message"]',
      '[class*="turn"]',
      '[class*="Turn"]',
      '[class*="message-"]',
      '[class*="Message"]'
    ];

    let turnContainers = [];
    for (const sel of turnSelectors) {
      const found = conversationArea.querySelectorAll(sel);
      if (found.length > 0) {
        debugInfo.push(`  ${sel}: ${found.length} elements`);
        turnContainers = [...turnContainers, ...found];
      }
    }

    // ==========================================
    // STRATEGY 2: Find Claude responses via .standard-markdown
    // ==========================================
    debugInfo.push(`\n--- STRATEGY 2: Claude responses ---`);

    const allMarkdown = conversationArea.querySelectorAll('.standard-markdown');
    const processedMarkdown = new Set();

    debugInfo.push(`Found ${allMarkdown.length} .standard-markdown elements`);

    allMarkdown.forEach((el, idx) => {
      if (isInSidebar(el)) {
        debugInfo.push(`  [${idx}] SKIP sidebar`);
        return;
      }

      // Find outermost standard-markdown
      let current = el;
      let parent = current.parentElement;
      while (parent) {
        if (parent.classList?.contains('standard-markdown')) {
          current = parent;
        }
        parent = parent.parentElement;
      }

      const sig = getSignature(current);
      if (processedMarkdown.has(sig)) {
        return; // Skip duplicates silently
      }
      processedMarkdown.add(sig);

      const content = current.innerText || current.textContent;
      if (content && content.trim().length > 10) {
        const rect = current.getBoundingClientRect();
        orderedMessages.push({
          role: 'assistant',
          content: content.trim(),
          top: rect.top,
          el: current
        });
        debugInfo.push(`  [${idx}] ASSISTANT (${content.trim().length}ch) y=${Math.round(rect.top)}: "${content.trim().substring(0, 40)}..."`);
      }
    });

    // ==========================================
    // STRATEGY 3: Find user messages - multiple approaches
    // ==========================================
    debugInfo.push(`\n--- STRATEGY 3: User messages ---`);

    // Approach 3a: Look for elements with data-testid containing "human" or "user"
    const userSelectors = [
      '[data-testid*="human"]',
      '[data-testid*="user"]',
      '[class*="human"]',
      '[class*="Human"]',
      '[class*="user-message"]',
      '[class*="UserMessage"]'
    ];

    let userElements = [];
    for (const sel of userSelectors) {
      const found = conversationArea.querySelectorAll(sel);
      if (found.length > 0) {
        debugInfo.push(`  ${sel}: ${found.length} elements`);
        userElements = [...userElements, ...found];
      }
    }

    // Approach 3b: white-space styled elements (original approach)
    const whiteSpaceEls = conversationArea.querySelectorAll('[style*="white-space"]');
    debugInfo.push(`  white-space style: ${whiteSpaceEls.length} elements`);

    // Approach 3c: Find text blocks that are NOT inside .standard-markdown
    // These could be user messages
    const allTextBlocks = conversationArea.querySelectorAll('p, div');
    let potentialUserBlocks = 0;

    // Process user elements from all approaches
    const processUserElement = (el, source) => {
      if (isInSidebar(el)) return false;
      if (el.closest('.standard-markdown')) return false;

      const sig = getSignature(el);
      if (processedElements.has(sig)) return false;

      const content = el.innerText || el.textContent;
      if (!content || content.trim().length < 3) return false;

      const trimmed = content.trim();

      // Skip if looks like UI element
      if (trimmed.length < 3) return false;
      if (trimmed.split('\n').length > 5 && trimmed.length < 50) return false;

      processedElements.add(sig);
      const rect = el.getBoundingClientRect();

      // Only include if within visible conversation area (not at top nav or bottom)
      if (rect.top < 50 || rect.height < 10) return false;

      orderedMessages.push({
        role: 'user',
        content: trimmed,
        top: rect.top,
        el: el
      });
      debugInfo.push(`  USER (${source}) (${trimmed.length}ch) y=${Math.round(rect.top)}: "${trimmed.substring(0, 40)}..."`);
      return true;
    };

    // Process user elements from selectors
    userElements.forEach(el => processUserElement(el, 'selector'));

    // Process white-space elements
    whiteSpaceEls.forEach(el => processUserElement(el, 'whitespace'));

    // ==========================================
    // Sort by vertical position
    // ==========================================
    orderedMessages.sort((a, b) => a.top - b.top);

    // ==========================================
    // Deduplicate - keep LONGEST version, use first 50 chars for matching
    // ==========================================
    debugInfo.push(`\n--- DEDUPLICATION ---`);
    debugInfo.push(`Before dedup: ${orderedMessages.length} messages`);

    const finalMessages = [];
    orderedMessages.forEach(msg => {
      const normalizedNew = msg.content.replace(/\s+/g, ' ').toLowerCase();
      const compareLen = Math.min(50, normalizedNew.length);
      const newStart = normalizedNew.substring(0, compareLen);

      let dominated = false;
      for (let i = 0; i < finalMessages.length; i++) {
        const existing = finalMessages[i];
        const normalizedExisting = existing.content.replace(/\s+/g, ' ').toLowerCase();
        const existingStart = normalizedExisting.substring(0, compareLen);

        // Same role and similar start = likely duplicate
        if (msg.role === existing.role) {
          if (normalizedExisting.includes(newStart) || normalizedNew.includes(existingStart)) {
            // Keep the longer one
            if (msg.content.length > existing.content.length) {
              debugInfo.push(`  Replaced shorter ${msg.role} with longer version`);
              finalMessages[i] = msg;
            } else {
              debugInfo.push(`  Skipped shorter ${msg.role} duplicate`);
            }
            dominated = true;
            break;
          }
        }
      }

      if (!dominated) {
        finalMessages.push(msg);
      }
    });

    debugInfo.push(`After dedup: ${finalMessages.length} messages`);

    // Build final message list
    finalMessages.forEach((msg, idx) => {
      messages.push({
        index: idx,
        role: msg.role,
        content: msg.content,
        timestamp: Date.now()
      });
    });

    const userCount = messages.filter(m => m.role === 'user').length;
    const assistantCount = messages.filter(m => m.role === 'assistant').length;

    // Update debug panel
    debugInfo.push(`\n--- FINAL RESULTS ---`);
    debugInfo.push(`Total: ${messages.length} (${userCount} user, ${assistantCount} assistant)`);
    messages.forEach((msg, i) => {
      debugInfo.push(`  ${i+1}. [${msg.role.toUpperCase()}] "${msg.content.substring(0, 50)}..."`);
    });

    debugLog('elements', debugInfo.join('\n'));
    debugLog('status', `Found ${messages.length} messages (${userCount} user, ${assistantCount} assistant)`);

    return messages;
  }

  /**
   * Process new messages and add to buffer
   */
  function processNewMessages() {
    const allMessages = extractMessages();

    // Add any messages not already in buffer or already saved
    let addedCount = 0;
    allMessages.forEach(msg => {
      // Skip if this content was already saved
      const hash = getContentHash(msg.role, msg.content);
      if (savedContentHashes.has(hash)) {
        return; // Already saved, don't re-add
      }

      const normalizedNew = msg.content.replace(/\s+/g, ' ').toLowerCase();
      const newStart = normalizedNew.substring(0, 50);

      // Check for duplicates in current buffer
      let foundIdx = -1;
      for (let i = 0; i < messageBuffer.length; i++) {
        const existing = messageBuffer[i];
        if (existing.role !== msg.role) continue;

        const normalizedExisting = existing.content.replace(/\s+/g, ' ').toLowerCase();
        const existingStart = normalizedExisting.substring(0, 50);

        // Check if starts match (substring comparison for partial matches)
        if (normalizedExisting.includes(newStart) || normalizedNew.includes(existingStart)) {
          foundIdx = i;
          break;
        }
      }

      if (foundIdx === -1) {
        // New message - add it
        messageBuffer.push(msg);
        totalBufferChars += msg.content.length;
        addedCount++;
        console.log(`CM: Buffered NEW ${msg.role} message (${msg.content.length} chars)`);
      } else if (msg.content.length > messageBuffer[foundIdx].content.length) {
        // Longer version - replace
        const oldLen = messageBuffer[foundIdx].content.length;
        totalBufferChars = totalBufferChars - oldLen + msg.content.length;
        messageBuffer[foundIdx] = msg;
        console.log(`CM: Updated ${msg.role} message (${oldLen} -> ${msg.content.length} chars)`);
      }
      // else: shorter or same - skip silently
    });

    if (addedCount > 0) {
      updateButtonState();

      // Check if we should prompt to save
      if (totalBufferChars >= CONFIG.maxBufferChars * CONFIG.autoSaveThreshold) {
        promptToSave();
      }
    }

    // Update debug panel with buffer state
    const bufferInfo = messageBuffer.map((msg, i) =>
      `${i+1}. [${msg.role.toUpperCase()}] (${msg.content.length}ch) "${msg.content.substring(0, 50)}..."`
    ).join('\n');
    debugLog('buffer', bufferInfo || '(empty - ${savedContentHashes.size} saved)');
  }

  /**
   * Calculate buffer fill percentage
   */
  function getBufferFillPercent() {
    return Math.min(100, (totalBufferChars / CONFIG.maxBufferChars) * 100);
  }

  /**
   * Get color based on buffer fill
   */
  function getBufferColor() {
    const percent = getBufferFillPercent();
    if (percent < 25) return '#34a853';      // Green
    if (percent < 50) return '#7cb342';      // Light green
    if (percent < 75) return '#fbc02d';      // Yellow
    if (percent < 90) return '#ff9800';      // Orange
    return '#ea4335';                         // Red
  }

  /**
   * Create the floating buffer button
   */
  function createFloatingButton() {
    if (floatingButton) return;

    floatingButton = document.createElement('div');
    floatingButton.id = 'cm-claude-floating-btn';
    floatingButton.innerHTML = `
      <div class="cm-claude-btn-content">
        <button class="cm-claude-save-btn" title="Save conversation buffer to Claude Memory">
          <span class="cm-claude-icon">CM</span>
          <span class="cm-claude-count">0</span>
        </button>
        <div class="cm-claude-progress">
          <div class="cm-claude-progress-bar"></div>
        </div>
      </div>
    `;

    // Add styles
    const style = document.createElement('style');
    style.textContent = `
      #cm-claude-floating-btn {
        position: fixed;
        bottom: 100px;
        right: 24px;
        z-index: 999999;
        animation: cm-slide-in 0.3s ease-out;
      }
      @keyframes cm-slide-in {
        from { transform: translateY(100%); opacity: 0; }
        to { transform: translateY(0); opacity: 1; }
      }
      .cm-claude-btn-content {
        display: flex;
        flex-direction: column;
        align-items: center;
        background: #ffffff;
        border-radius: 12px;
        box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
        padding: 8px;
        border: 1px solid #e0e0e0;
        min-width: 60px;
      }
      .cm-claude-save-btn {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 4px;
        padding: 8px 12px;
        background: #34a853;
        color: white;
        border: none;
        border-radius: 8px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        font-size: 12px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s ease;
      }
      .cm-claude-save-btn:hover {
        filter: brightness(0.9);
        transform: scale(1.05);
      }
      .cm-claude-save-btn:disabled {
        opacity: 0.7;
        cursor: wait;
      }
      .cm-claude-icon {
        font-weight: 700;
        font-size: 14px;
      }
      .cm-claude-count {
        font-size: 11px;
        opacity: 0.9;
      }
      .cm-claude-progress {
        width: 100%;
        height: 4px;
        background: #e0e0e0;
        border-radius: 2px;
        margin-top: 6px;
        overflow: hidden;
      }
      .cm-claude-progress-bar {
        height: 100%;
        background: #34a853;
        border-radius: 2px;
        transition: width 0.3s ease, background-color 0.3s ease;
        width: 0%;
      }
      .cm-toast {
        position: fixed;
        bottom: 24px;
        left: 50%;
        transform: translateX(-50%);
        padding: 12px 24px;
        border-radius: 8px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        font-size: 14px;
        z-index: 9999999;
        animation: cm-toast-in 0.3s ease-out;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
      }
      @keyframes cm-toast-in {
        from { transform: translateX(-50%) translateY(20px); opacity: 0; }
        to { transform: translateX(-50%) translateY(0); opacity: 1; }
      }
      .cm-toast-fade {
        animation: cm-toast-out 0.3s ease-in forwards;
      }
      @keyframes cm-toast-out {
        to { transform: translateX(-50%) translateY(20px); opacity: 0; }
      }
      .cm-toast-success { background: #34a853; color: white; }
      .cm-toast-error { background: #ea4335; color: white; }
      .cm-toast-info { background: #4285f4; color: white; }
    `;
    document.head.appendChild(style);

    const saveBtn = floatingButton.querySelector('.cm-claude-save-btn');
    saveBtn.addEventListener('click', handleSave);

    document.body.appendChild(floatingButton);
    updateButtonState();
  }

  /**
   * Update button appearance based on buffer state
   */
  function updateButtonState() {
    if (!floatingButton) return;

    const btn = floatingButton.querySelector('.cm-claude-save-btn');
    const countEl = floatingButton.querySelector('.cm-claude-count');
    const progressBar = floatingButton.querySelector('.cm-claude-progress-bar');

    const color = getBufferColor();
    const percent = getBufferFillPercent();

    btn.style.background = color;
    countEl.textContent = messageBuffer.length + ' msgs';
    progressBar.style.width = percent + '%';
    progressBar.style.background = color;

    // Update title with details
    btn.title = `Buffer: ${totalBufferChars.toLocaleString()} / ${CONFIG.maxBufferChars.toLocaleString()} chars\n` +
                `${messageBuffer.length} messages\n` +
                `Click to save to Claude Memory`;
  }

  /**
   * Prompt user to save when buffer is nearly full
   */
  function promptToSave() {
    showToast('Buffer nearly full! Click to save conversation.', 'info');
  }

  /**
   * Handle save button click
   */
  async function handleSave() {
    // Debug: Log buffer state
    console.log('CM: Save clicked. Buffer has', messageBuffer.length, 'messages');
    messageBuffer.forEach((msg, i) => {
      console.log(`CM: Message ${i}: role=${msg.role}, length=${msg.content.length}, preview="${msg.content.substring(0, 80)}..."`);
    });

    if (messageBuffer.length === 0) {
      showToast('Nothing to save yet', 'info');
      return;
    }

    const saveBtn = floatingButton.querySelector('.cm-claude-save-btn');
    saveBtn.disabled = true;

    conversationTitle = getConversationTitle();

    // Format buffer as conversation
    let content = messageBuffer.map(msg => {
      const prefix = msg.role === 'user' ? 'Human' : 'Claude';
      return `**${prefix}:**\n${msg.content}`;
    }).join('\n\n---\n\n');

    // Debug: Log what we're about to save
    console.log('CM: Content to save (length=' + content.length + '):', content.substring(0, 500) + '...');

    const memoryData = {
      title: 'Chat: ' + conversationTitle,
      content: content,
      category: 'conversation',
      tags: 'claude-web, chat',
      metadata: {
        source: 'claude-web',
        messageCount: messageBuffer.length,
        url: window.location.href,
        date: new Date().toISOString()
      }
    };

    try {
      // Get server URL - chrome.storage may not be available in all contexts
      let serverUrl = 'http://127.0.0.1:8765';
      try {
        if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.sync) {
          const result = await chrome.storage.sync.get(['serverUrl']);
          serverUrl = result.serverUrl || serverUrl;
        }
      } catch (storageErr) {
        console.log('CM: Could not access chrome.storage, using default URL');
      }

      const response = await fetch(`${serverUrl}/api/memories`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(memoryData)
      });

      const data = await response.json();
      console.log('CM: Server response:', data);

      if (data.success) {
        console.log('CM: Successfully saved! Memory ID:', data.id);
        showToast(`Saved ${messageBuffer.length} messages to Memory!`, 'success');

        // Mark all buffered messages as saved so they won't be re-added
        messageBuffer.forEach(msg => {
          const hash = getContentHash(msg.role, msg.content);
          savedContentHashes.add(hash);
        });
        console.log(`CM: Marked ${messageBuffer.length} messages as saved (${savedContentHashes.size} total)`);

        // Clear buffer after successful save
        messageBuffer = [];
        totalBufferChars = 0;
        updateButtonState();
      } else {
        showToast('Failed: ' + (data.error || 'Unknown error'), 'error');
      }
    } catch (e) {
      showToast('Could not connect to Claude Memory', 'error');
      console.error('CM: Save error:', e);
    }

    saveBtn.disabled = false;
  }

  /**
   * Show toast notification
   */
  function showToast(message, type) {
    const toast = document.createElement('div');
    toast.className = 'cm-toast cm-toast-' + type;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
      toast.classList.add('cm-toast-fade');
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  /**
   * Initialize
   */
  function init() {
    console.log('Claude.ai to Claude Memory: Initializing...');

    // Wait for conversation to load
    let checkCount = 0;
    const checkReady = setInterval(() => {
      checkCount++;

      // Look for conversation container
      const conversation = document.querySelector(
        '[class*="conversation"], [class*="Conversation"], ' +
        '[data-testid="conversation"], main, [role="main"]'
      );

      if (conversation) {
        clearInterval(checkReady);
        createDebugPanel();  // Create debug panel first
        createFloatingButton();

        // Initial message scan
        processNewMessages();

        // Set up periodic checking for new messages
        setInterval(processNewMessages, CONFIG.checkInterval);

        // Also use MutationObserver for faster detection
        const observer = new MutationObserver((mutations) => {
          // Debounce - only process if we see content changes
          const hasRelevantChanges = mutations.some(m =>
            m.addedNodes.length > 0 || m.type === 'characterData'
          );
          if (hasRelevantChanges) {
            setTimeout(processNewMessages, 500); // Small delay to let DOM settle
          }
        });

        observer.observe(conversation, {
          childList: true,
          subtree: true,
          characterData: true
        });

        console.log('Claude.ai to Claude Memory: Ready');
      }

      if (checkCount > 30) {
        clearInterval(checkReady);
        console.log('Claude.ai to Claude Memory: Could not find conversation container');
      }
    }, 1000);
  }

  // Start
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
