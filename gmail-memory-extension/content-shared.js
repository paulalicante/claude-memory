/**
 * Claude Memory - Shared Content Script Framework
 * Provides reusable infrastructure for capturing AI chat conversations.
 * Platform-specific scripts call CM.init(platformConfig) to activate.
 */

(function() {
  'use strict';

  // Prevent double-load
  if (window.CM) return;

  // =============================================
  // Configuration
  // =============================================
  const CONFIG = {
    maxBufferChars: 15000,
    autoSaveThreshold: 0.9,
    checkInterval: 2000,
    autoSaveIntervalMs: 60000
  };

  // =============================================
  // State
  // =============================================
  let platform = null;        // Set by CM.init()
  let messageBuffer = [];
  let floatingButton = null;
  let totalBufferChars = 0;
  let conversationTitle = '';
  let debugPanel = null;
  let debugMode = true;
  let savedContentHashes = new Set();

  let currentUrl = window.location.href;
  let messageCheckInterval = null;
  let autoSaveInterval = null;
  let conversationObserver = null;
  let isInitializing = false;
  let isSaving = false;
  let autoSavePartNumber = 0;
  let lastAutoSaveCount = 0;

  // =============================================
  // Content hashing for deduplication
  // =============================================
  function getContentHash(role, content) {
    const normalized = content.replace(/\s+/g, ' ').toLowerCase().substring(0, 100);
    return `${role}:${normalized}`;
  }

  // =============================================
  // Topic extraction for descriptive titles
  // =============================================
  function extractTopics(messages, maxTopics = 3) {
    const text = messages.map(m => m.content).join(' ');
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
      'install', 'update', 'test', 'build', 'refactor', 'optimize',
      'database', 'api', 'server', 'login', 'auth', 'payment',
      'debug', 'config', 'setup', 'migrate', 'docker', 'git'
    ];
    const lowerText = text.toLowerCase();
    for (const kw of keywords) {
      const regex = new RegExp(`\\b${kw}\\b`);
      if (regex.test(lowerText)) {
        addTopic(kw);
        if (topics.length >= maxTopics) return topics.join(', ');
      }
    }

    return topics.length > 0 ? topics.join(', ') : null;
  }

  // =============================================
  // Debug panel
  // =============================================
  function createDebugPanel() {
    if (debugPanel || !debugMode) return;

    debugPanel = document.createElement('div');
    debugPanel.id = 'cm-debug-panel';
    debugPanel.innerHTML = `
      <div class="cm-debug-header">
        <span>CM Debug (${platform.name})</span>
        <button class="cm-debug-close">\u00d7</button>
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

    // Styles injected once
    if (!document.getElementById('cm-debug-styles')) {
      const style = document.createElement('style');
      style.id = 'cm-debug-styles';
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
    }

    document.body.appendChild(debugPanel);

    debugPanel.querySelector('.cm-debug-close').addEventListener('click', () => {
      debugPanel.remove();
      debugPanel = null;
      debugMode = false;
    });
  }

  function debugLog(section, content) {
    if (!debugPanel) return;
    const el = document.getElementById('cm-debug-' + section);
    if (el) {
      el.textContent = content;
    }
  }

  // =============================================
  // Shared DOM helpers
  // =============================================

  /** Check if element is in a sidebar/nav region */
  function isInSidebar(el) {
    return el.closest('[class*="sidebar"]') ||
           el.closest('[class*="Sidebar"]') ||
           el.closest('[class*="nav-"]') ||
           el.closest('[class*="project"]') ||
           el.closest('[class*="Project"]') ||
           el.closest('[data-testid*="sidebar"]') ||
           el.closest('[data-testid*="nav"]');
  }

  /** Get position-based signature for dedup */
  function getElementSignature(el) {
    const rect = el.getBoundingClientRect();
    return `${Math.round(rect.top)}-${Math.round(rect.left)}-${el.tagName}`;
  }

  /**
   * Deduplicate ordered messages by role + first-N-chars matching.
   * Keeps the longer version when duplicates found.
   */
  function deduplicateMessages(orderedMessages) {
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

        if (msg.role === existing.role) {
          if (normalizedExisting.includes(newStart) || normalizedNew.includes(existingStart)) {
            if (msg.content.length > existing.content.length) {
              finalMessages[i] = msg;
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
    return finalMessages;
  }

  // =============================================
  // Buffer fill calculations
  // =============================================
  function getBufferFillPercent() {
    return Math.min(100, (totalBufferChars / CONFIG.maxBufferChars) * 100);
  }

  function getBufferColor() {
    const percent = getBufferFillPercent();
    if (percent < 25) return '#34a853';
    if (percent < 50) return '#7cb342';
    if (percent < 75) return '#fbc02d';
    if (percent < 90) return '#ff9800';
    return '#ea4335';
  }

  // =============================================
  // Status dot indicator
  // =============================================
  function createFloatingButton() {
    if (floatingButton) return;

    floatingButton = document.createElement('div');
    floatingButton.id = 'cm-floating-btn';

    // Inject styles once
    if (!document.getElementById('cm-shared-styles')) {
      const style = document.createElement('style');
      style.id = 'cm-shared-styles';
      style.textContent = `
        #cm-floating-btn {
          position: fixed;
          bottom: 12px;
          right: 12px;
          width: 10px;
          height: 10px;
          border-radius: 50%;
          background: #4285f4;
          z-index: 999999;
          opacity: 0.6;
          transition: background 0.3s ease, opacity 0.3s ease;
        }
        #cm-floating-btn:hover {
          opacity: 1;
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
    }

    document.body.appendChild(floatingButton);
    updateButtonState();
  }

  function updateButtonState() {
    if (!floatingButton) return;

    // Blue = connected & saved, green = buffering new messages, grey = disconnected/error
    if (messageBuffer.length === 0) {
      floatingButton.style.background = '#4285f4';
      floatingButton.title = `CM: Auto-saving (${lastAutoSaveCount} msgs saved)`;
    } else {
      floatingButton.style.background = '#34a853';
      floatingButton.title = `CM: ${messageBuffer.length} new messages buffered`;
    }
  }

  // =============================================
  // Toast notifications
  // =============================================
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

  // =============================================
  // Save flow
  // =============================================

  /**
   * Save current buffer to Claude Memory. Always silent (auto-save only).
   * @returns {boolean} - Whether save succeeded
   */
  async function doSave() {
    if (isSaving || messageBuffer.length === 0) return false;
    isSaving = true;

    const msgCount = messageBuffer.length;

    // Skip saving if content is too short to be useful
    const totalLen = messageBuffer.reduce((sum, m) => sum + m.content.length, 0);
    if (totalLen < 100) {
      console.log(`CM: Skipping save — content too short (${totalLen} chars)`);
      isSaving = false;
      return false;
    }

    console.log(`CM: Auto-saving. Buffer has ${msgCount} messages`);

    conversationTitle = platform.getTitle(messageBuffer);

    const userLabel = platform.roleLabels.user;
    const assistantLabel = platform.roleLabels.assistant;

    let content = messageBuffer.map(msg => {
      const prefix = msg.role === 'user' ? userLabel : assistantLabel;
      return `**${prefix}:**\n${msg.content}`;
    }).join('\n\n---\n\n');

    autoSavePartNumber++;
    // Try topic extraction first, fall back to platform title
    const topics = extractTopics(messageBuffer);
    let title;
    if (topics) {
      title = `${topics} (Part ${autoSavePartNumber})`;
    } else {
      const titleBase = conversationTitle || 'Conversation';
      title = `${titleBase} (Part ${autoSavePartNumber})`;
    }

    const memoryData = {
      title: title,
      content: content,
      category: 'conversation',
      tags: platform.tags + ', auto-save',
      metadata: {
        source: platform.source,
        platform: platform.name,
        messageCount: msgCount,
        partNumber: autoSavePartNumber,
        url: window.location.href,
        date: new Date().toISOString()
      }
    };

    let success = false;
    try {
      const response = await chrome.runtime.sendMessage({
        action: 'saveMemory',
        data: memoryData
      });

      if (response.success) {
        console.log(`CM: Saved Part ${autoSavePartNumber} (${msgCount} messages)`);

        messageBuffer.forEach(msg => {
          const hash = getContentHash(msg.role, msg.content);
          savedContentHashes.add(hash);
        });

        lastAutoSaveCount += msgCount;
        messageBuffer = [];
        totalBufferChars = 0;
        updateButtonState();
        success = true;
      } else {
        console.error('CM: Save failed:', response.error);
        autoSavePartNumber--;
        if (floatingButton) floatingButton.style.background = '#9e9e9e';
      }
    } catch (e) {
      console.error('CM: Save error:', e);
      autoSavePartNumber--;
      if (floatingButton) floatingButton.style.background = '#9e9e9e';
    }

    isSaving = false;
    return success;
  }

  /** Auto-save — triggered by timer or buffer threshold. */
  async function autoSave() {
    if (messageBuffer.length === 0) return;
    await doSave();
  }

  // =============================================
  // Message processing
  // =============================================
  function processNewMessages() {
    // Call platform-specific extraction
    const conversationArea = document.querySelector(platform.containerSelectors) || document.querySelector('main') || document.body;
    const allMessages = platform.extractMessages(conversationArea);

    let addedCount = 0;
    allMessages.forEach(msg => {
      const hash = getContentHash(msg.role, msg.content);
      if (savedContentHashes.has(hash)) return;

      const normalizedNew = msg.content.replace(/\s+/g, ' ').toLowerCase();
      const newStart = normalizedNew.substring(0, 50);

      let foundIdx = -1;
      for (let i = 0; i < messageBuffer.length; i++) {
        const existing = messageBuffer[i];
        if (existing.role !== msg.role) continue;

        const normalizedExisting = existing.content.replace(/\s+/g, ' ').toLowerCase();
        const existingStart = normalizedExisting.substring(0, 50);

        if (normalizedExisting.includes(newStart) || normalizedNew.includes(existingStart)) {
          foundIdx = i;
          break;
        }
      }

      if (foundIdx === -1) {
        messageBuffer.push(msg);
        totalBufferChars += msg.content.length;
        addedCount++;
        console.log(`CM: Buffered NEW ${msg.role} message (${msg.content.length} chars)`);
      } else if (msg.content.length > messageBuffer[foundIdx].content.length) {
        const oldLen = messageBuffer[foundIdx].content.length;
        totalBufferChars = totalBufferChars - oldLen + msg.content.length;
        messageBuffer[foundIdx] = msg;
        console.log(`CM: Updated ${msg.role} message (${oldLen} -> ${msg.content.length} chars)`);
      }
    });

    if (addedCount > 0) {
      updateButtonState();

      // Auto-save when buffer hits threshold instead of just prompting
      if (totalBufferChars >= CONFIG.maxBufferChars * CONFIG.autoSaveThreshold) {
        console.log('CM: Buffer threshold reached, auto-saving...');
        autoSave();
      }
    }

    // Update debug panel
    const bufferInfo = messageBuffer.map((msg, i) =>
      `${i+1}. [${msg.role.toUpperCase()}] (${msg.content.length}ch) "${msg.content.substring(0, 50)}..."`
    ).join('\n');
    debugLog('buffer', bufferInfo || `(empty - ${savedContentHashes.size} saved)`);
  }

  // =============================================
  // Cleanup
  // =============================================
  function cleanupUI() {
    const existingButton = document.getElementById('cm-floating-btn');
    const existingDebug = document.getElementById('cm-debug-panel');
    if (existingButton) existingButton.remove();
    if (existingDebug) existingDebug.remove();

    floatingButton = null;
    debugPanel = null;
  }

  function cleanupFull() {
    cleanupUI();
    if (autoSaveInterval) {
      clearInterval(autoSaveInterval);
      autoSaveInterval = null;
    }
    messageBuffer = [];
    totalBufferChars = 0;
    savedContentHashes.clear();
  }

  // =============================================
  // Initialization lifecycle
  // =============================================
  function startInit(fullReset) {
    if (isInitializing) return;
    isInitializing = true;

    console.log(`CM (${platform.name}): Initializing...` + (fullReset ? ' (full reset)' : ''));

    if (fullReset) {
      cleanupFull();
    } else {
      cleanupUI();
    }

    let checkCount = 0;
    const checkReady = setInterval(() => {
      checkCount++;

      const conversation = document.querySelector(platform.containerSelectors);

      if (conversation) {
        clearInterval(checkReady);
        createDebugPanel();
        createFloatingButton();

        processNewMessages();

        if (messageCheckInterval) clearInterval(messageCheckInterval);
        messageCheckInterval = setInterval(processNewMessages, CONFIG.checkInterval);

        // Start auto-save timer
        if (autoSaveInterval) clearInterval(autoSaveInterval);
        autoSaveInterval = setInterval(autoSave, CONFIG.autoSaveIntervalMs);
        console.log(`CM: Auto-save timer started (every ${CONFIG.autoSaveIntervalMs / 1000}s)`);

        if (conversationObserver) conversationObserver.disconnect();
        conversationObserver = new MutationObserver((mutations) => {
          const hasRelevantChanges = mutations.some(m =>
            m.addedNodes.length > 0 || m.type === 'characterData'
          );
          if (hasRelevantChanges) {
            setTimeout(processNewMessages, 500);
          }
        });

        conversationObserver.observe(conversation, {
          childList: true,
          subtree: true,
          characterData: true
        });

        isInitializing = false;
        console.log(`CM (${platform.name}): Ready`);
      }

      if (checkCount > 30) {
        clearInterval(checkReady);
        isInitializing = false;
        console.log(`CM (${platform.name}): Could not find conversation container`);
      }
    }, 1000);
  }

  function ensureStatusDot() {
    if (document.getElementById('cm-floating-btn')) return;
    floatingButton = null;
    createFloatingButton();
  }

  function setupNavigationDetection() {
    setInterval(() => {
      if (isInitializing) return;

      if (window.location.href !== currentUrl) {
        console.log('CM: URL changed, saving before reset...', currentUrl, '->', window.location.href);
        // Save any buffered messages before switching conversations
        if (messageBuffer.length > 0) {
          autoSave().then(() => {
            currentUrl = window.location.href;
            autoSavePartNumber = 0;
            lastAutoSaveCount = 0;
            setTimeout(() => startInit(true), 1000);
          });
        } else {
          currentUrl = window.location.href;
          autoSavePartNumber = 0;
          lastAutoSaveCount = 0;
          setTimeout(() => startInit(true), 1000);
        }
        return;
      }

      ensureStatusDot();
    }, 2000);

    window.addEventListener('popstate', () => {
      console.log('CM: popstate detected, saving before reset...');
      if (messageBuffer.length > 0) {
        autoSave().then(() => {
          currentUrl = window.location.href;
          autoSavePartNumber = 0;
          lastAutoSaveCount = 0;
          setTimeout(() => startInit(true), 1000);
        });
      } else {
        currentUrl = window.location.href;
        autoSavePartNumber = 0;
        lastAutoSaveCount = 0;
        setTimeout(() => startInit(true), 1000);
      }
    });
  }

  // =============================================
  // Public API
  // =============================================
  window.CM = {
    /**
     * Initialize the content script with platform-specific config.
     * @param {Object} platformConfig
     * @param {string} platformConfig.name - Display name (e.g. 'ChatGPT')
     * @param {string} platformConfig.source - Metadata source tag (e.g. 'chatgpt-web')
     * @param {string} platformConfig.tags - Comma-separated tags for saved memories
     * @param {Object} platformConfig.roleLabels - { user: 'User', assistant: 'ChatGPT' }
     * @param {string} platformConfig.containerSelectors - CSS selector(s) for conversation container
     * @param {function} platformConfig.extractMessages - (container) => [{role, content, top}]
     * @param {function} platformConfig.getTitle - (messageBuffer) => string
     */
    init: function(platformConfig) {
      platform = platformConfig;

      console.log(`CM: Loading ${platform.name} adapter`);

      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
          startInit(true);
          setupNavigationDetection();
        });
      } else {
        startInit(true);
        setupNavigationDetection();
      }
    },

    // Expose helpers for platform adapters
    helpers: {
      isInSidebar,
      getElementSignature,
      deduplicateMessages,
      debugLog
    }
  };

})();
