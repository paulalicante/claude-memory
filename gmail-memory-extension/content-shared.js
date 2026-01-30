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
    checkInterval: 2000
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
  let conversationObserver = null;
  let isInitializing = false;

  // =============================================
  // Content hashing for deduplication
  // =============================================
  function getContentHash(role, content) {
    const normalized = content.replace(/\s+/g, ' ').toLowerCase().substring(0, 100);
    return `${role}:${normalized}`;
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
  // Floating save button
  // =============================================
  function createFloatingButton() {
    if (floatingButton) return;

    floatingButton = document.createElement('div');
    floatingButton.id = 'cm-floating-btn';
    floatingButton.innerHTML = `
      <div class="cm-btn-content">
        <button class="cm-save-btn" title="Save conversation buffer to Claude Memory">
          <span class="cm-icon">CM</span>
          <span class="cm-count">0</span>
        </button>
        <div class="cm-progress">
          <div class="cm-progress-bar"></div>
        </div>
      </div>
    `;

    // Inject styles once
    if (!document.getElementById('cm-shared-styles')) {
      const style = document.createElement('style');
      style.id = 'cm-shared-styles';
      style.textContent = `
        #cm-floating-btn {
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
        .cm-btn-content {
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
        .cm-save-btn {
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
        .cm-save-btn:hover {
          filter: brightness(0.9);
          transform: scale(1.05);
        }
        .cm-save-btn:disabled {
          opacity: 0.7;
          cursor: wait;
        }
        .cm-icon {
          font-weight: 700;
          font-size: 14px;
        }
        .cm-count {
          font-size: 11px;
          opacity: 0.9;
        }
        .cm-progress {
          width: 100%;
          height: 4px;
          background: #e0e0e0;
          border-radius: 2px;
          margin-top: 6px;
          overflow: hidden;
        }
        .cm-progress-bar {
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
    }

    const saveBtn = floatingButton.querySelector('.cm-save-btn');
    saveBtn.addEventListener('click', handleSave);

    document.body.appendChild(floatingButton);
    updateButtonState();
  }

  function updateButtonState() {
    if (!floatingButton) return;

    const btn = floatingButton.querySelector('.cm-save-btn');
    const countEl = floatingButton.querySelector('.cm-count');
    const progressBar = floatingButton.querySelector('.cm-progress-bar');

    const color = getBufferColor();
    const percent = getBufferFillPercent();

    btn.style.background = color;
    countEl.textContent = messageBuffer.length + ' msgs';
    progressBar.style.width = percent + '%';
    progressBar.style.background = color;

    btn.title = `Buffer: ${totalBufferChars.toLocaleString()} / ${CONFIG.maxBufferChars.toLocaleString()} chars\n` +
                `${messageBuffer.length} messages\n` +
                `Click to save to Claude Memory`;
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
  function promptToSave() {
    showToast('Buffer nearly full! Click CM to save conversation.', 'info');
  }

  async function handleSave() {
    console.log('CM: Save clicked. Buffer has', messageBuffer.length, 'messages');
    messageBuffer.forEach((msg, i) => {
      console.log(`CM: Message ${i}: role=${msg.role}, length=${msg.content.length}, preview="${msg.content.substring(0, 80)}..."`);
    });

    if (messageBuffer.length === 0) {
      showToast('Nothing to save yet', 'info');
      return;
    }

    const saveBtn = floatingButton.querySelector('.cm-save-btn');
    saveBtn.disabled = true;

    conversationTitle = platform.getTitle(messageBuffer);

    // Format buffer using platform-specific role labels
    const userLabel = platform.roleLabels.user;
    const assistantLabel = platform.roleLabels.assistant;

    let content = messageBuffer.map(msg => {
      const prefix = msg.role === 'user' ? userLabel : assistantLabel;
      return `**${prefix}:**\n${msg.content}`;
    }).join('\n\n---\n\n');

    console.log('CM: Content to save (length=' + content.length + '):', content.substring(0, 500) + '...');

    const memoryData = {
      title: 'Chat: ' + conversationTitle,
      content: content,
      category: 'conversation',
      tags: platform.tags,
      metadata: {
        source: platform.source,
        platform: platform.name,
        messageCount: messageBuffer.length,
        url: window.location.href,
        date: new Date().toISOString()
      }
    };

    try {
      const response = await chrome.runtime.sendMessage({
        action: 'saveMemory',
        data: memoryData
      });

      console.log('CM: Server response:', response);

      if (response.success) {
        console.log('CM: Successfully saved! Memory ID:', response.id);
        showToast(`Saved ${messageBuffer.length} messages to Memory!`, 'success');

        messageBuffer.forEach(msg => {
          const hash = getContentHash(msg.role, msg.content);
          savedContentHashes.add(hash);
        });
        console.log(`CM: Marked ${messageBuffer.length} messages as saved (${savedContentHashes.size} total)`);

        messageBuffer = [];
        totalBufferChars = 0;
        updateButtonState();
      } else {
        showToast('Failed: ' + (response.error || 'Unknown error'), 'error');
      }
    } catch (e) {
      showToast('Could not connect to Claude Memory. Is the app running?', 'error');
      console.error('CM: Save error:', e);
    }

    saveBtn.disabled = false;
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

      if (totalBufferChars >= CONFIG.maxBufferChars * CONFIG.autoSaveThreshold) {
        promptToSave();
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

  function ensureButtonExists() {
    if (document.getElementById('cm-floating-btn')) return;
    floatingButton = null;
    createFloatingButton();
    console.log('CM: Recreated missing button');
  }

  function setupNavigationDetection() {
    setInterval(() => {
      if (isInitializing) return;

      if (window.location.href !== currentUrl) {
        console.log('CM: URL changed, reinitializing...', currentUrl, '->', window.location.href);
        currentUrl = window.location.href;
        setTimeout(() => startInit(true), 1000);
        return;
      }

      ensureButtonExists();
    }, 2000);

    window.addEventListener('popstate', () => {
      console.log('CM: popstate detected, reinitializing...');
      currentUrl = window.location.href;
      setTimeout(() => startInit(true), 1000);
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
