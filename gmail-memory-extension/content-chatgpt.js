/**
 * ChatGPT Adapter for Claude Memory
 * Platform-specific message extraction for chatgpt.com / chat.openai.com
 * Requires content-shared.js to be loaded first.
 */

(function() {
  'use strict';

  if (!window.CM) {
    console.error('CM: content-shared.js must be loaded before content-chatgpt.js');
    return;
  }

  const { isInSidebar, getElementSignature, deduplicateMessages, debugLog } = CM.helpers;

  /**
   * Get conversation title from ChatGPT page
   */
  function getTitle(messageBuffer) {
    // ChatGPT shows title in the active nav item or page heading
    const titleEl = document.querySelector('nav [class*="active"]') ||
                    document.querySelector('h1') ||
                    document.querySelector('[data-testid*="title"]') ||
                    document.querySelector('title');
    if (titleEl) {
      const text = titleEl.textContent.trim();
      // Skip generic titles
      if (text && text !== 'ChatGPT' && text !== 'New chat' && text.length > 2) {
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
    return 'ChatGPT Conversation ' + new Date().toLocaleDateString();
  }

  /**
   * Check if text looks like boilerplate (T&C, footer, disclaimers)
   */
  const BOILERPLATE_PATTERNS = [
    /terms\s+(of\s+)?(use|service)/i,
    /privacy\s+policy/i,
    /chatgpt\s+can\s+make\s+mistakes/i,
    /check\s+important\s+info/i,
    /openai/i,
    /\bcookies?\b.*\bpolicy\b/i,
    /\bcopyright\b/i
  ];

  function isBoilerplate(text) {
    const trimmed = text.trim();
    // Very short text that matches boilerplate
    if (trimmed.length < 200) {
      for (const pattern of BOILERPLATE_PATTERNS) {
        if (pattern.test(trimmed)) return true;
      }
    }
    return false;
  }

  /**
   * Extract the actual message content from a ChatGPT message element,
   * excluding action buttons, footers, and other UI elements.
   */
  function getMessageContent(el, role) {
    // For assistant messages, look for the markdown/prose container specifically
    if (role === 'assistant') {
      const markdownEl = el.querySelector('[class*="markdown"], [class*="prose"]');
      if (markdownEl) {
        return markdownEl.innerText || markdownEl.textContent;
      }
    }

    // For user messages, look for the text content container
    // ChatGPT wraps user text in a specific div — try to find it
    const userTextEl = el.querySelector('[data-message-author-role="user"] > div > div') ||
                       el.querySelector('[class*="whitespace"]') ||
                       el.querySelector('p');
    if (userTextEl) {
      return userTextEl.innerText || userTextEl.textContent;
    }

    // Fallback: get all text but try to exclude button/action areas
    // Clone the element, remove known UI elements, then get text
    const clone = el.cloneNode(true);
    clone.querySelectorAll('button, [class*="btn"], [class*="action"], [class*="toolbar"], [class*="footer"], [role="toolbar"], nav').forEach(n => n.remove());
    return clone.innerText || clone.textContent;
  }

  /**
   * Extract messages from ChatGPT conversation DOM.
   * ChatGPT uses data-message-author-role attributes on message containers.
   */
  function extractMessages(conversationArea) {
    const messages = [];
    const debugInfo = [];
    const orderedMessages = [];

    debugInfo.push(`ChatGPT - Conversation area: ${conversationArea.tagName}`);

    // ==========================================
    // STRATEGY 1: data-message-author-role (most reliable)
    // ChatGPT marks messages with data-message-author-role="user"|"assistant"
    // ==========================================
    debugInfo.push(`\n--- STRATEGY 1: data-message-author-role ---`);

    const roleMessages = conversationArea.querySelectorAll('[data-message-author-role]');
    debugInfo.push(`Found ${roleMessages.length} elements with data-message-author-role`);

    roleMessages.forEach((el, idx) => {
      if (isInSidebar(el)) return;

      const role = el.getAttribute('data-message-author-role');
      if (role !== 'user' && role !== 'assistant') {
        debugInfo.push(`  [${idx}] SKIP role="${role}"`);
        return;
      }

      const content = getMessageContent(el, role);

      if (content && content.trim().length > 3 && !isBoilerplate(content)) {
        const rect = el.getBoundingClientRect();
        orderedMessages.push({
          role: role,
          content: content.trim(),
          top: rect.top
        });
        debugInfo.push(`  [${idx}] ${role.toUpperCase()} (${content.trim().length}ch) y=${Math.round(rect.top)}: "${content.trim().substring(0, 40)}..."`);
      } else if (content && isBoilerplate(content)) {
        debugInfo.push(`  [${idx}] SKIP boilerplate: "${content.trim().substring(0, 40)}..."`);
      }
    });

    // ==========================================
    // STRATEGY 2: Fallback - conversation turn containers
    // Look for turn-based grouping if Strategy 1 found nothing
    // ==========================================
    if (orderedMessages.length === 0) {
      debugInfo.push(`\n--- STRATEGY 2: Turn containers (fallback) ---`);

      const turnSelectors = [
        '[data-testid*="conversation-turn"]',
        '[class*="ConversationItem"]',
        '[class*="group"]'
      ];

      for (const sel of turnSelectors) {
        const turns = conversationArea.querySelectorAll(sel);
        if (turns.length > 0) {
          debugInfo.push(`  ${sel}: ${turns.length} elements`);

          turns.forEach((turn, idx) => {
            if (isInSidebar(turn)) return;

            // Try to determine role from content structure
            const hasMarkdown = turn.querySelector('[class*="markdown"], [class*="prose"]');
            const role = hasMarkdown ? 'assistant' : 'user';

            const content = turn.innerText || turn.textContent;
            if (content && content.trim().length > 3) {
              const rect = turn.getBoundingClientRect();
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
    // STRATEGY 3: Generic article/message containers
    // ==========================================
    if (orderedMessages.length === 0) {
      debugInfo.push(`\n--- STRATEGY 3: Generic containers (fallback) ---`);

      const genericSelectors = [
        '[role="article"]',
        'article',
        '[class*="message"]',
        '[class*="Message"]'
      ];

      const processedSigs = new Set();

      for (const sel of genericSelectors) {
        const elements = conversationArea.querySelectorAll(sel);
        if (elements.length > 0) {
          debugInfo.push(`  ${sel}: ${elements.length} elements`);

          elements.forEach((el, idx) => {
            if (isInSidebar(el)) return;

            const sig = getElementSignature(el);
            if (processedSigs.has(sig)) return;
            processedSigs.add(sig);

            const hasMarkdown = el.querySelector('[class*="markdown"], [class*="prose"]');
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

  // Initialize with ChatGPT config
  CM.init({
    name: 'ChatGPT',
    source: 'chatgpt-web',
    tags: 'chatgpt, chat, openai',
    roleLabels: { user: 'User', assistant: 'ChatGPT' },
    containerSelectors: 'main, [role="main"], [class*="conversation"], [class*="thread"]',
    extractMessages: extractMessages,
    getTitle: getTitle
  });

})();
