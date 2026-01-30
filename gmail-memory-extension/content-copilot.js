/**
 * Microsoft Copilot Adapter for Claude Memory
 * Platform-specific message extraction for copilot.microsoft.com
 * Requires content-shared.js to be loaded first.
 *
 * Note: Copilot may use Shadow DOM for some components.
 * This adapter includes helpers to pierce shadow roots.
 */

(function() {
  'use strict';

  if (!window.CM) {
    console.error('CM: content-shared.js must be loaded before content-copilot.js');
    return;
  }

  const { isInSidebar, getElementSignature, deduplicateMessages, debugLog } = CM.helpers;

  // =============================================
  // Shadow DOM helpers
  // =============================================

  /**
   * Recursively query through shadow roots.
   * Returns all matching elements across shadow boundaries.
   */
  function deepQuerySelectorAll(root, selector) {
    let results = [...root.querySelectorAll(selector)];

    // Also search inside shadow roots
    const allElements = root.querySelectorAll('*');
    allElements.forEach(el => {
      if (el.shadowRoot) {
        results = [...results, ...deepQuerySelectorAll(el.shadowRoot, selector)];
      }
    });

    return results;
  }

  /**
   * Find the first matching element across shadow boundaries.
   */
  function deepQuerySelector(root, selector) {
    const result = root.querySelector(selector);
    if (result) return result;

    const allElements = root.querySelectorAll('*');
    for (const el of allElements) {
      if (el.shadowRoot) {
        const found = deepQuerySelector(el.shadowRoot, selector);
        if (found) return found;
      }
    }
    return null;
  }

  /**
   * Get conversation title from Copilot page
   */
  function getTitle(messageBuffer) {
    const titleEl = deepQuerySelector(document, '[class*="conversation-title"]') ||
                    deepQuerySelector(document, 'h1') ||
                    deepQuerySelector(document, '[class*="chat-title"]') ||
                    document.querySelector('title');
    if (titleEl) {
      const text = titleEl.textContent.trim();
      if (text && text !== 'Microsoft Copilot' && text !== 'Copilot' && text.length > 2) {
        return text;
      }
    }
    // Fallback to first user message
    if (messageBuffer.length > 0) {
      const firstUserMsg = messageBuffer.find(m => m.role === 'user');
      if (firstUserMsg) {
        return firstUserMsg.content.substring(0, 50) + '...';
      }
    }
    return 'Copilot Conversation ' + new Date().toLocaleDateString();
  }

  /**
   * Extract the clean text content from a Copilot message element.
   * Strips "You said" / "Copilot said" prefixes and grabs the actual content.
   */
  function getMessageContent(el, role) {
    if (role === 'user') {
      // User text lives in a child with class containing "user-text-message"
      const userTextEl = el.querySelector('[class*="user-text-message"]');
      if (userTextEl) return userTextEl.innerText || userTextEl.textContent;
    }

    if (role === 'assistant') {
      // Assistant text lives in a child with class containing "ai-message-item"
      const aiTextEl = el.querySelector('[class*="ai-message-item"]');
      if (aiTextEl) return aiTextEl.innerText || aiTextEl.textContent;
    }

    // Fallback: get full text but strip known prefixes
    let text = el.innerText || el.textContent || '';
    text = text.replace(/^(You said|Copilot said)\s*/i, '');
    return text;
  }

  /**
   * Extract messages from Microsoft Copilot conversation DOM.
   * Copilot uses [role="article"] elements with "You said" / "Copilot said" prefixes.
   * User text: child with class *="user-text-message"
   * Assistant text: child with class *="ai-message-item"
   */
  function extractMessages(conversationArea) {
    const messages = [];
    const debugInfo = [];
    const orderedMessages = [];
    const processedSigs = new Set();

    debugInfo.push(`Copilot - Conversation area: ${conversationArea.tagName}`);

    // Check for Shadow DOM
    const hasShadow = !!conversationArea.querySelector('*')?.shadowRoot;
    debugInfo.push(`Shadow DOM detected: ${hasShadow}`);

    const query = hasShadow ? deepQuerySelectorAll.bind(null, conversationArea) :
                              conversationArea.querySelectorAll.bind(conversationArea);

    // ==========================================
    // STRATEGY 1: [role="article"] elements (primary)
    // Each article is one message turn. Determine role from content/children.
    // ==========================================
    debugInfo.push(`\n--- STRATEGY 1: role="article" ---`);

    let articles;
    try {
      articles = query('[role="article"]');
    } catch (e) {
      articles = [];
    }

    debugInfo.push(`Found ${articles.length} [role="article"] elements`);

    articles.forEach((el, idx) => {
      if (isInSidebar(el)) return;

      const sig = getElementSignature(el);
      if (processedSigs.has(sig)) return;
      processedSigs.add(sig);

      // Determine role by checking for user vs ai child elements or text prefix
      const hasUserText = el.querySelector('[class*="user-text-message"]');
      const hasAiText = el.querySelector('[class*="ai-message"]');
      const fullText = (el.innerText || '').trim();

      let role;
      if (hasUserText || fullText.startsWith('You said')) {
        role = 'user';
      } else if (hasAiText || fullText.startsWith('Copilot said')) {
        role = 'assistant';
      } else {
        // Guess based on content structure
        role = el.querySelector('code, pre, [class*="markdown"]') ? 'assistant' : 'user';
      }

      const content = getMessageContent(el, role);
      if (content && content.trim().length > 3) {
        const rect = el.getBoundingClientRect();
        orderedMessages.push({
          role: role,
          content: content.trim(),
          top: rect.top
        });
        debugInfo.push(`  [${idx}] ${role.toUpperCase()} (${content.trim().length}ch) y=${Math.round(rect.top)}: "${content.trim().substring(0, 40)}..."`);
      }
    });

    // ==========================================
    // STRATEGY 2: Separate user + assistant selectors
    // Fallback if [role="article"] not found
    // ==========================================
    if (orderedMessages.length === 0) {
      debugInfo.push(`\n--- STRATEGY 2: Separate user/assistant selectors ---`);

      // User messages
      let userEls;
      try {
        userEls = query('[class*="user-text-message"]');
      } catch (e) {
        userEls = [];
      }
      debugInfo.push(`  User elements: ${userEls.length}`);

      userEls.forEach((el, idx) => {
        const sig = getElementSignature(el);
        if (processedSigs.has(sig)) return;
        processedSigs.add(sig);

        const content = el.innerText || el.textContent;
        if (content && content.trim().length > 3) {
          const rect = el.getBoundingClientRect();
          orderedMessages.push({ role: 'user', content: content.trim(), top: rect.top });
          debugInfo.push(`  [${idx}] USER (${content.trim().length}ch)`);
        }
      });

      // Assistant messages
      let aiEls;
      try {
        aiEls = query('[class*="ai-message-item"]');
      } catch (e) {
        aiEls = [];
      }
      debugInfo.push(`  AI elements: ${aiEls.length}`);

      aiEls.forEach((el, idx) => {
        const sig = getElementSignature(el);
        if (processedSigs.has(sig)) return;
        processedSigs.add(sig);

        const content = el.innerText || el.textContent;
        if (content && content.trim().length > 3) {
          const rect = el.getBoundingClientRect();
          orderedMessages.push({ role: 'assistant', content: content.trim(), top: rect.top });
          debugInfo.push(`  [${idx}] ASSISTANT (${content.trim().length}ch)`);
        }
      });
    }

    // ==========================================
    // STRATEGY 3: Generic fallback
    // ==========================================
    if (orderedMessages.length === 0) {
      debugInfo.push(`\n--- STRATEGY 3: Generic containers (fallback) ---`);

      const genericSelectors = [
        '[class*="message"]',
        '[class*="Message"]',
        'article',
        '[class*="response"]'
      ];

      for (const sel of genericSelectors) {
        let found;
        try {
          found = query(sel);
        } catch (e) {
          continue;
        }

        if (found.length > 0) {
          debugInfo.push(`  ${sel}: ${found.length} elements`);

          found.forEach((el) => {
            if (isInSidebar(el)) return;
            const sig = getElementSignature(el);
            if (processedSigs.has(sig)) return;
            processedSigs.add(sig);

            const hasMarkdown = el.querySelector('code, pre, [class*="markdown"]');
            const role = hasMarkdown ? 'assistant' : 'user';

            const content = el.innerText || el.textContent;
            if (content && content.trim().length > 10) {
              const rect = el.getBoundingClientRect();
              orderedMessages.push({ role: role, content: content.trim(), top: rect.top });
            }
          });

          if (orderedMessages.length > 0) break;
        }
      }
    }

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

    debugLog('elements', debugInfo.join('\n'));
    debugLog('status', `Found ${messages.length} messages (${userCount} user, ${assistantCount} assistant)`);

    return messages;
  }

  // Initialize with Copilot config
  CM.init({
    name: 'Copilot',
    source: 'copilot-web',
    tags: 'copilot, chat, microsoft',
    roleLabels: { user: 'User', assistant: 'Copilot' },
    containerSelectors: 'main, [role="main"], [class*="conversation"], [class*="chat-container"], [class*="thread"]',
    extractMessages: extractMessages,
    getTitle: getTitle
  });

})();
