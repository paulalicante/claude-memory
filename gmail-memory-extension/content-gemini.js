/**
 * Google Gemini Adapter for Claude Memory
 * Platform-specific message extraction for gemini.google.com
 * Requires content-shared.js to be loaded first.
 */

(function() {
  'use strict';

  if (!window.CM) {
    console.error('CM: content-shared.js must be loaded before content-gemini.js');
    return;
  }

  const { isInSidebar, getElementSignature, deduplicateMessages, debugLog } = CM.helpers;

  /**
   * Get conversation title from Gemini page
   */
  function getTitle(messageBuffer) {
    // Gemini shows title in header or sidebar active item
    const titleEl = document.querySelector('[class*="conversation-title"]') ||
                    document.querySelector('[data-conversation-title]') ||
                    document.querySelector('h1') ||
                    document.querySelector('[class*="title"]');
    if (titleEl) {
      const text = titleEl.textContent.trim();
      if (text && text !== 'Gemini' && text.length > 2) {
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
    return 'Gemini Conversation ' + new Date().toLocaleDateString();
  }

  /**
   * Extract messages from Google Gemini conversation DOM.
   * Gemini uses a turn-based layout with model/user role containers.
   */
  function extractMessages(conversationArea) {
    const messages = [];
    const debugInfo = [];
    const orderedMessages = [];
    const processedSigs = new Set();

    debugInfo.push(`Gemini - Conversation area: ${conversationArea.tagName}`);

    // ==========================================
    // STRATEGY 1: Turn-based containers with role attributes
    // Gemini often uses data attributes or class names to distinguish turns
    // ==========================================
    debugInfo.push(`\n--- STRATEGY 1: Turn/query containers ---`);

    // Gemini uses query/response pattern containers
    const turnSelectors = [
      '[data-message-role]',
      '[class*="query-content"]',
      '[class*="response-content"]',
      '[class*="model-response"]',
      '[class*="user-query"]',
      'message-content',           // custom element
      '[class*="message-content"]'
    ];

    for (const sel of turnSelectors) {
      const found = conversationArea.querySelectorAll(sel);
      if (found.length > 0) {
        debugInfo.push(`  ${sel}: ${found.length} elements`);

        found.forEach((el, idx) => {
          if (isInSidebar(el)) return;

          const sig = getElementSignature(el);
          if (processedSigs.has(sig)) return;
          processedSigs.add(sig);

          // Determine role from attributes or class names
          let role = 'assistant'; // default
          const roleAttr = el.getAttribute('data-message-role') || '';
          const className = el.className || '';

          if (roleAttr === 'user' ||
              className.includes('user') || className.includes('User') ||
              className.includes('query') || className.includes('Query')) {
            role = 'user';
          }

          const content = el.innerText || el.textContent;
          if (content && content.trim().length > 3) {
            const rect = el.getBoundingClientRect();
            orderedMessages.push({
              role: role,
              content: content.trim(),
              top: rect.top
            });
            debugInfo.push(`  [${idx}] ${role.toUpperCase()} (${content.trim().length}ch) y=${Math.round(rect.top)}`);
          }
        });
      }
    }

    // ==========================================
    // STRATEGY 2: Conversation turn groups
    // Some Gemini layouts group turns in containers
    // ==========================================
    if (orderedMessages.length === 0) {
      debugInfo.push(`\n--- STRATEGY 2: Conversation turn groups ---`);

      const groupSelectors = [
        '[class*="turn"]',
        '[class*="Turn"]',
        '[class*="conversation-turn"]',
        '[data-turn-id]'
      ];

      for (const sel of groupSelectors) {
        const groups = conversationArea.querySelectorAll(sel);
        if (groups.length > 0) {
          debugInfo.push(`  ${sel}: ${groups.length} groups`);

          groups.forEach((group, idx) => {
            if (isInSidebar(group)) return;

            const sig = getElementSignature(group);
            if (processedSigs.has(sig)) return;
            processedSigs.add(sig);

            // Determine role: if contains markdown/rendered content, likely model response
            const hasMarkdown = group.querySelector('[class*="markdown"], [class*="rendered"], code, pre');
            const role = hasMarkdown ? 'assistant' : 'user';

            const content = group.innerText || group.textContent;
            if (content && content.trim().length > 3) {
              const rect = group.getBoundingClientRect();
              orderedMessages.push({
                role: role,
                content: content.trim(),
                top: rect.top
              });
              debugInfo.push(`  [${idx}] ${role.toUpperCase()} (${content.trim().length}ch)`);
            }
          });

          if (orderedMessages.length > 0) break;
        }
      }
    }

    // ==========================================
    // STRATEGY 3: Generic content containers
    // Last resort: look for any content-holding elements
    // ==========================================
    if (orderedMessages.length === 0) {
      debugInfo.push(`\n--- STRATEGY 3: Generic containers (fallback) ---`);

      const containers = conversationArea.querySelectorAll(
        '[role="article"], article, [class*="message"], [class*="content-area"]'
      );

      debugInfo.push(`Found ${containers.length} generic containers`);

      containers.forEach((el, idx) => {
        if (isInSidebar(el)) return;

        const sig = getElementSignature(el);
        if (processedSigs.has(sig)) return;
        processedSigs.add(sig);

        // Heuristic: longer content with markdown = assistant
        const hasMarkdown = el.querySelector('code, pre, ul, ol, table, [class*="markdown"]');
        const role = hasMarkdown ? 'assistant' : 'user';

        const content = el.innerText || el.textContent;
        if (content && content.trim().length > 10) {
          const rect = el.getBoundingClientRect();
          orderedMessages.push({
            role: role,
            content: content.trim(),
            top: rect.top
          });
        }
      });
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

  // Initialize with Gemini config
  CM.init({
    name: 'Gemini',
    source: 'gemini-web',
    tags: 'gemini, chat, google',
    roleLabels: { user: 'User', assistant: 'Gemini' },
    containerSelectors: 'main, [role="main"], [class*="conversation"], [class*="chat-container"]',
    extractMessages: extractMessages,
    getTitle: getTitle
  });

})();
