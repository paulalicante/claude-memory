/**
 * WhatsApp Web to Claude Memory - Content Script
 * Monitors WhatsApp Web for messages you send and saves them to Claude Memory
 */

(function() {
  'use strict';

  console.log('WhatsApp to Claude Memory: Loading...');

  // Track messages we've already captured to avoid duplicates
  const capturedMessages = new Set();
  const capturedIncoming = new Set();  // Track incoming messages separately
  let lastMessageText = '';
  let currentContact = '';

  /**
   * Send message to background with error handling
   */
  function sendMessageSafe(message, callback) {
    try {
      chrome.runtime.sendMessage(message, response => {
        if (chrome.runtime.lastError) {
          console.warn('Extension message error:', chrome.runtime.lastError.message);
          if (callback) callback({ success: false, error: chrome.runtime.lastError.message });
          return;
        }
        if (callback) callback(response);
      });
    } catch (err) {
      console.error('Failed to send message:', err);
      if (callback) callback({ success: false, error: err.message });
    }
  }

  /**
   * Show a toast notification
   */
  function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.style.cssText = `
      position: fixed;
      bottom: 80px;
      left: 20px;
      padding: 12px 20px;
      background: ${type === 'success' ? '#25D366' : type === 'error' ? '#EF4444' : '#3B82F6'};
      color: white;
      border-radius: 8px;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      font-size: 14px;
      z-index: 999999;
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
      transition: opacity 0.3s;
    `;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  /**
   * Get the current contact/chat name
   */
  function getCurrentContact() {
    // WhatsApp Web chat header selectors
    const headerSelectors = [
      'header span[dir="auto"][title]',
      'header span[data-testid="conversation-info-header-chat-title"]',
      '#main header span[title]',
      'div[data-testid="conversation-panel-wrapper"] header span[title]'
    ];

    for (const selector of headerSelectors) {
      const el = document.querySelector(selector);
      if (el) {
        return el.getAttribute('title') || el.textContent.trim();
      }
    }
    return 'Unknown contact';
  }

  /**
   * Save a message to Claude Memory
   */
  function saveMessage(messageText, contact) {
    // Create a hash to track this message
    const messageHash = `${messageText.substring(0, 50)}-${contact}-${Date.now()}`;
    if (capturedMessages.has(messageHash)) {
      return; // Already captured
    }
    capturedMessages.add(messageHash);

    // Limit captured messages set size
    if (capturedMessages.size > 100) {
      const first = capturedMessages.values().next().value;
      capturedMessages.delete(first);
    }

    const title = `WhatsApp to ${contact}`;
    const content = `Message to ${contact}:\n\n${messageText}`;

    const memoryData = {
      title: title.substring(0, 200),
      content: content,
      category: 'conversation',
      tags: 'whatsapp, message',
      metadata: {
        platform: 'whatsapp',
        contact: contact,
        date: new Date().toISOString()
      }
    };

    sendMessageSafe({
      action: 'saveMemory',
      data: memoryData
    }, response => {
      if (response && response.success) {
        // Silent save - no toast for WhatsApp (too frequent)
        console.log('WhatsApp message saved to Claude Memory');
      } else {
        console.error('Failed to save WhatsApp message:', response?.error);
      }
    });
  }

  /**
   * Save an incoming message to Claude Memory
   */
  function saveIncomingMessage(messageText, contact) {
    // Create a hash to track this message (use first 100 chars + contact for uniqueness)
    const messageHash = `in-${messageText.substring(0, 100)}-${contact}`;
    if (capturedIncoming.has(messageHash)) {
      return; // Already captured
    }
    capturedIncoming.add(messageHash);

    // Limit captured messages set size
    if (capturedIncoming.size > 200) {
      const first = capturedIncoming.values().next().value;
      capturedIncoming.delete(first);
    }

    const title = `WhatsApp from ${contact}`;
    const content = `Message from ${contact}:\n\n${messageText}`;

    const memoryData = {
      title: title.substring(0, 200),
      content: content,
      category: 'conversation',
      tags: 'whatsapp, message, received',
      metadata: {
        platform: 'whatsapp',
        contact: contact,
        direction: 'incoming',
        date: new Date().toISOString()
      }
    };

    sendMessageSafe({
      action: 'saveMemory',
      data: memoryData
    }, response => {
      if (response && response.success) {
        console.log('WhatsApp incoming message saved to Claude Memory');
      } else {
        console.error('Failed to save incoming WhatsApp message:', response?.error);
      }
    });
  }

  /**
   * Monitor for incoming messages in the chat
   */
  function setupIncomingMessageMonitor() {
    // Find the main chat container
    const messageContainer = document.querySelector('#main') || document.querySelector('div[data-testid="conversation-panel-body"]');

    if (!messageContainer) {
      console.log('WhatsApp: No message container found');
      return;
    }

    if (messageContainer.dataset.cmIncomingMonitored) return;
    messageContainer.dataset.cmIncomingMonitored = 'true';

    console.log('WhatsApp: Monitoring incoming messages...');

    // Process a copyable-text element that has data-pre-plain-text (contains sender info)
    function processCopyableText(copyableEl) {
      if (copyableEl.dataset.cmProcessed) return;

      // Get the data-pre-plain-text attribute which contains sender info
      // Format: "[18:34, 1/21/2026] Sender Name: "
      const prePlainText = copyableEl.getAttribute('data-pre-plain-text');
      if (!prePlainText) return;

      // Check if this is from someone else (incoming) vs from us (outgoing)
      // Outgoing messages don't have the sender name, or it might just have time
      // Incoming format: "[time, date] Contact Name: "
      // We check if there's a name before the colon
      const match = prePlainText.match(/\]\s*(.+?):\s*$/);
      if (!match) {
        // No sender name found - this is likely our own message
        return;
      }

      const senderName = match[1].trim();
      if (!senderName) return;

      // Mark as processed
      copyableEl.dataset.cmProcessed = 'true';

      // Get the message text from the selectable-text span
      const textEl = copyableEl.querySelector('span[data-testid="selectable-text"]');
      if (!textEl) {
        console.log('WhatsApp: No text element found');
        return;
      }

      const messageText = textEl.textContent.trim();
      if (!messageText || messageText.length < 1) {
        console.log('WhatsApp: Empty message text');
        return;
      }

      console.log('WhatsApp: Incoming from', senderName, ':', messageText.substring(0, 30));
      saveIncomingMessage(messageText, senderName);
    }

    // Watch for new messages being added
    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        for (const node of mutation.addedNodes) {
          if (node.nodeType !== Node.ELEMENT_NODE) continue;

          // Check if this node is a copyable-text with data-pre-plain-text
          if (node.classList && node.classList.contains('copyable-text') && node.hasAttribute('data-pre-plain-text')) {
            processCopyableText(node);
          }

          // Also check children
          if (node.querySelectorAll) {
            const copyableTexts = node.querySelectorAll('div.copyable-text[data-pre-plain-text]');
            copyableTexts.forEach(el => processCopyableText(el));
          }
        }
      }
    });

    observer.observe(messageContainer, {
      childList: true,
      subtree: true
    });

    // Process recent existing messages (only last 3 to avoid flooding)
    const existingMessages = messageContainer.querySelectorAll('div.copyable-text[data-pre-plain-text]');
    console.log('WhatsApp: Found', existingMessages.length, 'existing messages with metadata');
    const recentMessages = Array.from(existingMessages).slice(-3);
    recentMessages.forEach(el => processCopyableText(el));
  }

  /**
   * Monitor for message sends
   */
  function setupMessageMonitor() {
    // WhatsApp message input selectors
    const inputSelectors = [
      'div[data-testid="conversation-compose-box-input"]',
      'footer div[contenteditable="true"]',
      'div[contenteditable="true"][data-tab="10"]',
      '#main footer div[contenteditable="true"]'
    ];

    // Send button selectors
    const sendButtonSelectors = [
      'button[data-testid="send"]',
      'span[data-testid="send"]',
      'button[aria-label="Send"]',
      'span[data-icon="send"]'
    ];

    // Function to find and monitor input
    function monitorInput() {
      let input = null;
      for (const selector of inputSelectors) {
        input = document.querySelector(selector);
        if (input) break;
      }

      if (!input || input.dataset.cmMonitored) return;
      input.dataset.cmMonitored = 'true';

      console.log('WhatsApp: Found message input, monitoring...');

      // Track input changes
      const inputObserver = new MutationObserver(() => {
        lastMessageText = input.textContent.trim();
        currentContact = getCurrentContact();
      });
      inputObserver.observe(input, { childList: true, characterData: true, subtree: true });

      // Also track on input event
      input.addEventListener('input', () => {
        lastMessageText = input.textContent.trim();
        currentContact = getCurrentContact();
      });
    }

    // Function to find and monitor send button
    function monitorSendButton() {
      for (const selector of sendButtonSelectors) {
        const buttons = document.querySelectorAll(selector);
        buttons.forEach(button => {
          // Get the actual clickable element (might be parent)
          const clickTarget = button.closest('button') || button;
          if (clickTarget.dataset.cmMonitored) return;
          clickTarget.dataset.cmMonitored = 'true';

          console.log('WhatsApp: Found send button, monitoring...');

          clickTarget.addEventListener('click', () => {
            const messageText = lastMessageText;
            const contact = currentContact || getCurrentContact();

            if (messageText && messageText.length > 0) {
              // Wait a moment for the message to be sent
              setTimeout(() => {
                saveMessage(messageText, contact);
                lastMessageText = ''; // Reset
              }, 300);
            }
          }, true);
        });
      }
    }

    // Monitor for Enter key to send
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        const activeEl = document.activeElement;
        // Check if we're in the message input
        if (activeEl && activeEl.getAttribute('contenteditable') === 'true') {
          const isInFooter = activeEl.closest('footer') !== null;
          const isComposeBox = activeEl.closest('[data-testid="conversation-compose-box-input"]') !== null;

          if (isInFooter || isComposeBox) {
            const messageText = activeEl.textContent.trim();
            const contact = getCurrentContact();

            if (messageText && messageText.length > 0) {
              setTimeout(() => {
                saveMessage(messageText, contact);
              }, 300);
            }
          }
        }
      }
    }, true);

    // Use MutationObserver to watch for dynamically added inputs
    const observer = new MutationObserver((mutations) => {
      monitorInput();
      monitorSendButton();
      // Also re-check for incoming messages when chat changes
      setupIncomingMessageMonitor();
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true
    });

    // Initial check
    monitorInput();
    monitorSendButton();
  }

  /**
   * Initialize
   */
  function init() {
    console.log('WhatsApp to Claude Memory: Initializing...');

    // Wait for WhatsApp Web to be ready
    const checkReady = setInterval(() => {
      // WhatsApp is ready when we see the main app container
      if (document.querySelector('#app') && document.querySelector('#main, div[data-testid="chat-list"]')) {
        clearInterval(checkReady);
        setupMessageMonitor();
        setupIncomingMessageMonitor();
        console.log('WhatsApp to Claude Memory: Ready');
      }
    }, 1000);

    // Timeout after 60 seconds (WhatsApp can be slow to load)
    setTimeout(() => clearInterval(checkReady), 60000);
  }

  // Start when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
