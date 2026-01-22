/**
 * TikTok to Claude Memory - Content Script
 * Monitors TikTok for comments you post and saves them to Claude Memory
 */

(function() {
  'use strict';

  console.log('TikTok to Claude Memory: Loading...');

  // Track comments we've already captured to avoid duplicates
  const capturedComments = new Set();

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
      right: 20px;
      padding: 12px 20px;
      background: ${type === 'success' ? '#10B981' : type === 'error' ? '#EF4444' : '#3B82F6'};
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
   * Extract video context from the current page
   */
  function getVideoContext() {
    const context = {
      url: window.location.href,
      creator: '',
      description: '',
      timestamp: new Date().toISOString()
    };

    // Try to get creator username
    // TikTok has various selectors depending on the view
    const creatorSelectors = [
      'a[data-e2e="browse-username"]',
      'a[data-e2e="video-author-uniqueid"]',
      'span[data-e2e="browse-username"]',
      'h3[data-e2e="browse-username"] a',
      'a.author-uniqueId',
      '[class*="AuthorTitle"] a',
      '[class*="author-uniqueId"]'
    ];

    for (const selector of creatorSelectors) {
      const el = document.querySelector(selector);
      if (el) {
        context.creator = el.textContent.trim().replace('@', '');
        break;
      }
    }

    // Try to get video description/caption
    const descSelectors = [
      'div[data-e2e="browse-video-desc"]',
      'div[data-e2e="video-desc"]',
      'span[data-e2e="new-desc-span"]',
      '[class*="DivVideoInfoContainer"] span',
      'h1[data-e2e="browse-video-desc"]'
    ];

    for (const selector of descSelectors) {
      const el = document.querySelector(selector);
      if (el) {
        context.description = el.textContent.trim().substring(0, 200);
        break;
      }
    }

    return context;
  }

  /**
   * Save a comment to Claude Memory
   */
  function saveComment(commentText, videoContext) {
    // Create a hash to track this comment
    const commentHash = `${commentText.substring(0, 50)}-${videoContext.url}`;
    if (capturedComments.has(commentHash)) {
      return; // Already captured
    }
    capturedComments.add(commentHash);

    const creatorStr = videoContext.creator ? `@${videoContext.creator}` : 'unknown creator';
    const title = `TikTok comment on ${creatorStr}'s video`;

    let content = `My comment: "${commentText}"`;
    if (videoContext.description) {
      content += `\n\nVideo caption: ${videoContext.description}`;
    }
    content += `\n\nVideo URL: ${videoContext.url}`;

    const memoryData = {
      title: title.substring(0, 200),
      content: content,
      category: 'social',
      tags: 'tiktok, comment',
      metadata: {
        platform: 'tiktok',
        creator: videoContext.creator,
        video_url: videoContext.url,
        date: videoContext.timestamp
      }
    };

    sendMessageSafe({
      action: 'saveMemory',
      data: memoryData
    }, response => {
      if (response && response.success) {
        showToast('TikTok comment saved!', 'success');
      } else {
        console.error('Failed to save TikTok comment:', response?.error);
      }
    });
  }

  /**
   * Monitor for comment submissions
   */
  function setupCommentMonitor() {
    // TikTok comment input selectors
    const inputSelectors = [
      'div[data-e2e="comment-input"] div[contenteditable="true"]',
      'div[class*="DivInputEditorContainer"] div[contenteditable="true"]',
      'div[class*="CommentInputContainer"] div[contenteditable="true"]',
      'div[contenteditable="true"][data-placeholder*="comment"]',
      'div[contenteditable="true"][data-placeholder*="Add comment"]'
    ];

    // Post button selectors
    const postButtonSelectors = [
      'div[data-e2e="comment-post"]',
      'button[data-e2e="comment-post"]',
      '[class*="DivPostButton"]',
      '[class*="PostButton"]'
    ];

    let lastInputText = '';

    // Function to find and monitor comment input
    function monitorCommentInput() {
      let input = null;
      for (const selector of inputSelectors) {
        input = document.querySelector(selector);
        if (input) break;
      }

      if (!input || input.dataset.cmMonitored) return;
      input.dataset.cmMonitored = 'true';

      console.log('TikTok: Found comment input, monitoring...');

      // Track input changes
      const inputObserver = new MutationObserver(() => {
        lastInputText = input.textContent.trim();
      });
      inputObserver.observe(input, { childList: true, characterData: true, subtree: true });

      // Also track on input event
      input.addEventListener('input', () => {
        lastInputText = input.textContent.trim();
      });
    }

    // Function to find and monitor post button
    function monitorPostButton() {
      for (const selector of postButtonSelectors) {
        const buttons = document.querySelectorAll(selector);
        buttons.forEach(button => {
          if (button.dataset.cmMonitored) return;
          button.dataset.cmMonitored = 'true';

          console.log('TikTok: Found post button, monitoring...');

          button.addEventListener('click', () => {
            // Capture the text before it gets cleared
            const commentText = lastInputText;

            if (commentText && commentText.length > 0) {
              // Wait a moment for the comment to be posted
              setTimeout(() => {
                const videoContext = getVideoContext();
                saveComment(commentText, videoContext);
                lastInputText = ''; // Reset
              }, 500);
            }
          }, true);
        });
      }
    }

    // Also monitor for Enter key in comment input
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        // Check if we're in a comment input
        const activeEl = document.activeElement;
        if (activeEl && activeEl.getAttribute('contenteditable') === 'true') {
          const commentText = activeEl.textContent.trim();
          if (commentText && commentText.length > 0) {
            setTimeout(() => {
              const videoContext = getVideoContext();
              saveComment(commentText, videoContext);
            }, 500);
          }
        }
      }
    }, true);

    // Use MutationObserver to watch for dynamically added inputs
    const observer = new MutationObserver((mutations) => {
      monitorCommentInput();
      monitorPostButton();
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true
    });

    // Initial check
    monitorCommentInput();
    monitorPostButton();
  }

  /**
   * Initialize
   */
  function init() {
    console.log('TikTok to Claude Memory: Initializing...');

    // Wait for page to be ready
    const checkReady = setInterval(() => {
      // TikTok is ready when we can find the main content area
      if (document.querySelector('div[id="app"]') || document.querySelector('main')) {
        clearInterval(checkReady);
        setupCommentMonitor();
        console.log('TikTok to Claude Memory: Ready');
      }
    }, 1000);

    // Timeout after 30 seconds
    setTimeout(() => clearInterval(checkReady), 30000);
  }

  // Start when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
