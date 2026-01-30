/**
 * Claude.ai Adapter for Claude Memory
 * Platform-specific message extraction for claude.ai
 * Requires content-shared.js to be loaded first.
 */

(function() {
  'use strict';

  if (!window.CM) {
    console.error('CM: content-shared.js must be loaded before content-claude.js');
    return;
  }

  const { isInSidebar, getElementSignature, deduplicateMessages, debugLog } = CM.helpers;

  /**
   * Get conversation title from Claude.ai page
   */
  function getTitle(messageBuffer) {
    const titleEl = document.querySelector('[data-testid="chat-title"]') ||
                    document.querySelector('h1') ||
                    document.querySelector('[class*="ConversationTitle"]');
    if (titleEl && titleEl.textContent.trim()) {
      return titleEl.textContent.trim();
    }
    if (messageBuffer.length > 0) {
      const firstUserMsg = messageBuffer.find(m => m.role === 'user');
      if (firstUserMsg) {
        return firstUserMsg.content.substring(0, 50) + '...';
      }
    }
    return 'Claude Conversation ' + new Date().toLocaleDateString();
  }

  /**
   * Extract messages from Claude.ai conversation DOM.
   * Uses 3-strategy approach for robustness.
   */
  function extractMessages(conversationArea) {
    const messages = [];
    const debugInfo = [];
    const orderedMessages = [];
    const processedElements = new Set();

    debugInfo.push(`Conversation area: ${conversationArea.tagName}`);

    // ==========================================
    // STRATEGY 1: Turn containers
    // ==========================================
    debugInfo.push(`\n--- STRATEGY 1: Turn containers ---`);

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
    // STRATEGY 2: Claude responses via .standard-markdown
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

      const sig = getElementSignature(current);
      if (processedMarkdown.has(sig)) {
        return;
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
    // STRATEGY 3: User messages - multiple approaches
    // ==========================================
    debugInfo.push(`\n--- STRATEGY 3: User messages ---`);

    // Approach 3a: data-testid / class selectors
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

    // Approach 3b: white-space styled elements
    const whiteSpaceEls = conversationArea.querySelectorAll('[style*="white-space"]');
    debugInfo.push(`  white-space style: ${whiteSpaceEls.length} elements`);

    const processUserElement = (el, source) => {
      if (isInSidebar(el)) return false;
      if (el.closest('.standard-markdown')) return false;

      const sig = getElementSignature(el);
      if (processedElements.has(sig)) return false;

      const content = el.innerText || el.textContent;
      if (!content || content.trim().length < 3) return false;

      const trimmed = content.trim();
      if (trimmed.length < 3) return false;
      if (trimmed.split('\n').length > 5 && trimmed.length < 50) return false;

      processedElements.add(sig);
      const rect = el.getBoundingClientRect();

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

    userElements.forEach(el => processUserElement(el, 'selector'));
    whiteSpaceEls.forEach(el => processUserElement(el, 'whitespace'));

    // Sort by vertical position
    orderedMessages.sort((a, b) => a.top - b.top);

    // Deduplicate
    debugInfo.push(`\n--- DEDUPLICATION ---`);
    debugInfo.push(`Before dedup: ${orderedMessages.length} messages`);

    const finalMessages = deduplicateMessages(orderedMessages);

    debugInfo.push(`After dedup: ${finalMessages.length} messages`);

    // Build output
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

    debugInfo.push(`\n--- FINAL RESULTS ---`);
    debugInfo.push(`Total: ${messages.length} (${userCount} user, ${assistantCount} assistant)`);
    messages.forEach((msg, i) => {
      debugInfo.push(`  ${i+1}. [${msg.role.toUpperCase()}] "${msg.content.substring(0, 50)}..."`);
    });

    debugLog('elements', debugInfo.join('\n'));
    debugLog('status', `Found ${messages.length} messages (${userCount} user, ${assistantCount} assistant)`);

    return messages;
  }

  // Initialize with Claude.ai config
  CM.init({
    name: 'Claude',
    source: 'claude-web',
    tags: 'claude-web, chat',
    roleLabels: { user: 'Human', assistant: 'Claude' },
    containerSelectors: '[class*="conversation"], [class*="Conversation"], [data-testid="conversation"], main, [role="main"]',
    extractMessages: extractMessages,
    getTitle: getTitle
  });

})();
