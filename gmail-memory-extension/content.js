/**
 * Gmail to Claude Memory - Content Script
 * Monitors Gmail for sent emails and prompts user to save to Claude Memory
 */

(function() {
  'use strict';

  // State
  let pendingEmail = null;
  let promptElement = null;

  /**
   * Extract email data from the compose window
   */
  function extractEmailData(composeWindow) {
    const email = {
      recipients: [],
      subject: '',
      body: '',
      timestamp: new Date().toISOString()
    };

    // Get recipients (To field)
    // Gmail uses multiple possible selectors
    const toFields = composeWindow.querySelectorAll(
      'input[name="to"], ' +
      'div[aria-label="To"] span[email], ' +
      'div[name="to"] span[email], ' +
      'span[email]'
    );
    toFields.forEach(el => {
      const emailAddr = el.getAttribute('email') || el.value;
      if (emailAddr && !email.recipients.includes(emailAddr)) {
        email.recipients.push(emailAddr);
      }
    });

    // Also check for email chips in the To area
    const toContainer = composeWindow.querySelector('div[aria-label="To"]');
    if (toContainer) {
      const chips = toContainer.querySelectorAll('[data-hovercard-id]');
      chips.forEach(chip => {
        const addr = chip.getAttribute('data-hovercard-id');
        if (addr && addr.includes('@') && !email.recipients.includes(addr)) {
          email.recipients.push(addr);
        }
      });
    }

    // Get subject
    const subjectInput = composeWindow.querySelector(
      'input[name="subjectbox"], ' +
      'input[aria-label="Subject"]'
    );
    if (subjectInput) {
      email.subject = subjectInput.value || '';
    }

    // Get body
    const bodyDiv = composeWindow.querySelector(
      'div[aria-label="Message Body"], ' +
      'div[contenteditable="true"][aria-label*="Message"], ' +
      'div[role="textbox"][aria-label*="Message"], ' +
      'div.editable[contenteditable="true"]'
    );
    if (bodyDiv) {
      email.body = bodyDiv.innerText || bodyDiv.textContent || '';
    }

    return email;
  }

  /**
   * Create and show the save prompt
   */
  function showSavePrompt(emailData) {
    // Remove existing prompt if any
    hideSavePrompt();

    // Create prompt element
    promptElement = document.createElement('div');
    promptElement.id = 'claude-memory-prompt';
    promptElement.innerHTML = `
      <div class="cm-prompt-content">
        <div class="cm-prompt-header">
          <span class="cm-prompt-icon">💾</span>
          <span class="cm-prompt-title">Save to Claude Memory?</span>
        </div>
        <div class="cm-prompt-preview">
          <strong>To:</strong> ${emailData.recipients.join(', ') || '(no recipients)'}<br>
          <strong>Subject:</strong> ${emailData.subject || '(no subject)'}
        </div>
        <div class="cm-prompt-buttons">
          <button class="cm-btn cm-btn-save">Save</button>
          <button class="cm-btn cm-btn-cancel">Skip</button>
        </div>
      </div>
    `;

    // Add event listeners
    const saveBtn = promptElement.querySelector('.cm-btn-save');
    const cancelBtn = promptElement.querySelector('.cm-btn-cancel');

    saveBtn.addEventListener('click', () => {
      saveToMemory(emailData);
      hideSavePrompt();
    });

    cancelBtn.addEventListener('click', () => {
      hideSavePrompt();
    });

    // Add to page
    document.body.appendChild(promptElement);

    // Auto-hide after 15 seconds
    setTimeout(() => {
      if (promptElement) {
        hideSavePrompt();
      }
    }, 15000);
  }

  /**
   * Hide the save prompt
   */
  function hideSavePrompt() {
    if (promptElement) {
      promptElement.remove();
      promptElement = null;
    }
    pendingEmail = null;
  }

  /**
   * Send message to background with error handling for context invalidation
   */
  function sendMessageSafe(message, callback) {
    try {
      chrome.runtime.sendMessage(message, response => {
        // Check for extension context error
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
   * Save email to Claude Memory via background script
   */
  function saveToMemory(emailData) {
    const recipientStr = emailData.recipients.join(', ');
    const title = `Email to ${recipientStr}: ${emailData.subject || '(no subject)'}`;

    const memoryData = {
      title: title.substring(0, 200), // Limit title length
      content: emailData.body,
      category: 'email',
      tags: 'gmail, sent-email',
      metadata: {
        recipients: emailData.recipients,
        subject: emailData.subject,
        date: emailData.timestamp
      }
    };

    // Send to background script with error handling
    sendMessageSafe({
      action: 'saveMemory',
      data: memoryData
    }, response => {
      if (response && response.success) {
        showToast('Saved to Claude Memory!', 'success');

        // Fire-and-forget: register recipients as trusted contacts
        if (emailData.recipients.length > 0) {
          setTimeout(() => {
            sendMessageSafe({
              action: 'addTrustedContacts',
              emails: emailData.recipients
            });
          }, 100);
        }
      } else {
        showToast('Failed to save: ' + (response?.error || 'Unknown error'), 'error');
      }
    });
  }

  /**
   * Show a toast notification
   */
  function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `cm-toast cm-toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
      toast.classList.add('cm-toast-fade');
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  /**
   * Monitor for Send button clicks
   */
  function setupSendMonitor() {
    // Use MutationObserver to watch for compose windows
    const observer = new MutationObserver((mutations) => {
      mutations.forEach(mutation => {
        mutation.addedNodes.forEach(node => {
          if (node.nodeType === Node.ELEMENT_NODE) {
            // Check for compose dialogs
            const composeWindows = node.querySelectorAll ?
              node.querySelectorAll('div[role="dialog"]') : [];

            composeWindows.forEach(setupComposeWindow);

            // Also check if the node itself is a compose dialog
            if (node.matches && node.matches('div[role="dialog"]')) {
              setupComposeWindow(node);
            }
          }
        });
      });
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true
    });

    // Also setup any existing compose windows
    document.querySelectorAll('div[role="dialog"]').forEach(setupComposeWindow);
  }

  /**
   * Setup monitoring for a compose window
   */
  function setupComposeWindow(composeWindow) {
    // Check if already setup
    if (composeWindow.dataset.cmMonitored) return;
    composeWindow.dataset.cmMonitored = 'true';

    // Find Send button
    const sendButtons = composeWindow.querySelectorAll(
      'div[aria-label*="Send"][role="button"], ' +
      'div[data-tooltip*="Send"][role="button"], ' +
      'div[aria-label="Send"][role="button"]'
    );

    sendButtons.forEach(sendBtn => {
      if (sendBtn.dataset.cmMonitored) return;
      sendBtn.dataset.cmMonitored = 'true';

      // Capture click on Send button
      sendBtn.addEventListener('click', (e) => {
        // Extract email data before it disappears
        const emailData = extractEmailData(composeWindow);

        if (emailData.body || emailData.subject) {
          // Store for later (Gmail may take a moment to send)
          pendingEmail = emailData;

          // Wait a bit for send to complete, then show prompt
          setTimeout(() => {
            if (pendingEmail) {
              showSavePrompt(pendingEmail);
            }
          }, 1500);
        }
      }, true); // Use capture phase
    });
  }

  // ============================================================================
  // MANUAL EMAIL SAVING - Button to save currently viewed email
  // ============================================================================

  let currentEmailButton = null;
  let lastViewedEmailId = null;

  /**
   * Extract Gmail message ID from URL
   * Gmail URLs look like: https://mail.google.com/mail/u/0/#inbox/FMfcgzQXJWDsKmPjBvhTkqnLxRgNwMrl
   */
  function getGmailIdFromUrl() {
    const hash = window.location.hash;
    // Match patterns like #inbox/ID, #sent/ID, #label/name/ID, etc.
    const match = hash.match(/#[^/]+\/([A-Za-z0-9]+)$/);
    if (match) {
      return match[1];
    }
    // Also try #inbox/ID format for thread views
    const threadMatch = hash.match(/\/([A-Za-z0-9]{16,})$/);
    return threadMatch ? threadMatch[1] : null;
  }

  /**
   * Extract sender email from the currently viewed email
   */
  function extractSenderEmail() {
    // Try various Gmail selectors for the sender
    const selectors = [
      'span[email]', // Most common - email attribute on span
      'h3[data-hovercard-id]', // Sometimes used for sender
      'span[data-hovercard-id]',
      'table[role="presentation"] span[email]' // In email header
    ];

    for (const selector of selectors) {
      const el = document.querySelector(selector);
      if (el) {
        const email = el.getAttribute('email') || el.getAttribute('data-hovercard-id');
        if (email && email.includes('@')) {
          return email.toLowerCase();
        }
      }
    }
    return null;
  }

  /**
   * Extract full email content from the viewed email
   */
  function extractViewedEmailData() {
    const data = {
      sender: null,
      subject: '',
      body: '',
      gmailId: getGmailIdFromUrl(),
      timestamp: new Date().toISOString()
    };

    // Get sender
    data.sender = extractSenderEmail();

    // Get subject from the email view header
    const subjectEl = document.querySelector('h2[data-thread-perm-id]') ||
                      document.querySelector('h2.hP') ||
                      document.querySelector('div[role="main"] h2');
    if (subjectEl) {
      data.subject = subjectEl.textContent.trim();
    }

    // Get email body - look for the message content
    const bodyEl = document.querySelector('div[data-message-id] div.a3s') ||
                   document.querySelector('div.ii.gt div') ||
                   document.querySelector('div[role="main"] div.a3s');
    if (bodyEl) {
      // Capture HTML to preserve layout
      data.body = bodyEl.innerHTML || '';
      data.bodyText = bodyEl.innerText || bodyEl.textContent || ''; // Also save plain text for search
    }

    return data;
  }

  /**
   * Create and inject floating save button
   */
  function createSaveButton() {
    // Remove existing button if any
    if (currentEmailButton) {
      currentEmailButton.remove();
      currentEmailButton = null;
    }

    // Check if we're actually viewing an email
    const emailHeader = document.querySelector('div[data-message-id]');
    if (!emailHeader) {
      console.log('CM: Not viewing an email (no data-message-id found)');
      return;
    }

    console.log('CM: Creating floating save button for email');

    // Create floating action button
    const saveBtn = document.createElement('div');
    saveBtn.className = 'cm-floating-save-btn';
    saveBtn.style.cssText = `
      position: fixed;
      bottom: 80px;
      right: 30px;
      z-index: 10000;
      background: #4A90E2;
      color: white;
      border: none;
      border-radius: 50px;
      padding: 12px 20px;
      font-size: 14px;
      font-weight: 500;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 8px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
      transition: all 0.3s;
      user-select: none;
    `;
    saveBtn.innerHTML = `💾 Save to Memory`;

    // Hover effects
    saveBtn.onmouseenter = function() {
      this.style.background = '#357ABD';
      this.style.transform = 'scale(1.05)';
      this.style.boxShadow = '0 6px 16px rgba(0,0,0,0.4)';
    };
    saveBtn.onmouseleave = function() {
      this.style.background = '#4A90E2';
      this.style.transform = 'scale(1)';
      this.style.boxShadow = '0 4px 12px rgba(0,0,0,0.3)';
    };

    saveBtn.addEventListener('click', saveCurrentEmail);

    // Append to body for fixed positioning
    document.body.appendChild(saveBtn);
    currentEmailButton = saveBtn;

    console.log('CM: Floating save button created successfully');
  }

  /**
   * Save the currently viewed email
   */
  function saveCurrentEmail() {
    const emailData = extractViewedEmailData();

    if (!emailData.body || !emailData.subject) {
      showToast('Could not extract email content', 'error');
      return;
    }

    const title = `Email: ${emailData.subject || '(no subject)'}`;
    const senderInfo = emailData.sender ? ` from ${emailData.sender}` : '';

    const memoryData = {
      title: (title + senderInfo).substring(0, 200),
      content: emailData.bodyText || emailData.body,
      category: 'email',
      tags: 'gmail, saved-email, html-email',
      metadata: {
        sender: emailData.sender,
        subject: emailData.subject,
        gmail_id: emailData.gmailId,
        date: emailData.timestamp,
        html_content: emailData.body,
        content_type: 'html'
      }
    };

    sendMessageSafe({
      action: 'saveMemory',
      data: memoryData
    }, response => {
      if (response && response.success) {
        showToast('Email saved to Claude Memory!', 'success');
      } else {
        showToast('Failed to save: ' + (response?.error || 'Unknown error'), 'error');
      }
    });
  }

  /**
   * Check current email view and inject save button
   */
  function checkCurrentEmailView() {
    const gmailId = getGmailIdFromUrl();

    // If viewing an email (has ID) and it's different from last viewed
    if (gmailId && gmailId !== lastViewedEmailId) {
      lastViewedEmailId = gmailId;

      // Wait a moment for email to fully load, then inject button
      setTimeout(() => {
        createSaveButton();
      }, 500);
    } else if (!gmailId && currentEmailButton) {
      // Not viewing an email anymore, remove button
      currentEmailButton.remove();
      currentEmailButton = null;
      lastViewedEmailId = null;
    }
  }

  /**
   * Setup email view monitoring to inject save button
   */
  function setupEmailViewMonitor() {
    // Check on URL changes (when user opens an email)
    let lastUrl = window.location.href;

    const urlObserver = setInterval(() => {
      if (window.location.href !== lastUrl) {
        lastUrl = window.location.href;
        checkCurrentEmailView();
      }
    }, 500);

    // Also check when page content changes significantly
    const contentObserver = new MutationObserver((mutations) => {
      // Check if we need to inject button
      const gmailId = getGmailIdFromUrl();
      if (gmailId && gmailId !== lastViewedEmailId) {
        checkCurrentEmailView();
      }
    });

    const mainContent = document.querySelector('div[role="main"]');
    if (mainContent) {
      contentObserver.observe(mainContent, {
        childList: true,
        subtree: true
      });
    }

    console.log('Gmail save button monitor: Active');
  }

  /**
   * Initialize the extension
   */
  function init() {
    console.log('Gmail to Claude Memory: Initializing...');

    // Wait for Gmail to fully load
    const checkReady = setInterval(() => {
      if (document.querySelector('div[role="main"]')) {
        clearInterval(checkReady);
        setupSendMonitor();
        setupEmailViewMonitor();
        console.log('Gmail to Claude Memory: Ready (send monitor + save button)');
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
