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
  // INBOX MONITORING - Auto-save emails from trusted contacts
  // ============================================================================

  let lastCheckedEmailId = null;
  let checkingEmail = false;

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
   * Save an incoming email from a trusted contact
   */
  function saveIncomingEmail(emailData) {
    const title = `Email from ${emailData.sender}: ${emailData.subject || '(no subject)'}`;

    const memoryData = {
      title: title.substring(0, 200),
      content: emailData.bodyText || emailData.body, // Use plain text for search
      category: 'email',
      tags: 'gmail, received-email, trusted-sender, html-email',
      metadata: {
        sender: emailData.sender,
        subject: emailData.subject,
        gmail_id: emailData.gmailId,
        date: emailData.timestamp,
        html_content: emailData.body, // Store HTML separately
        content_type: 'html'
      }
    };

    sendMessageSafe({
      action: 'saveMemory',
      data: memoryData
    }, response => {
      if (response && response.success) {
        // Mark as saved to prevent re-saving
        sendMessageSafe({
          action: 'markEmailSaved',
          gmailId: emailData.gmailId,
          entryId: response.id
        });
        showToast('Auto-saved email from trusted contact!', 'success');
      }
    });
  }

  /**
   * Check current email view and auto-save if from trusted contact
   */
  async function checkCurrentEmail() {
    if (checkingEmail) return;

    const gmailId = getGmailIdFromUrl();
    if (!gmailId || gmailId === lastCheckedEmailId) {
      return; // No email view or already checked
    }

    checkingEmail = true;
    lastCheckedEmailId = gmailId;

    try {
      // First check if already saved
      const savedCheck = await new Promise(resolve => {
        sendMessageSafe(
          { action: 'checkEmailSaved', gmailId },
          response => resolve(response || { saved: false })
        );
      });

      if (savedCheck && savedCheck.saved) {
        console.log('Email already saved, skipping');
        return;
      }

      // Extract email data
      const emailData = extractViewedEmailData();
      if (!emailData.sender || !emailData.body) {
        return;
      }

      // Check if sender is trusted
      const trustedCheck = await new Promise(resolve => {
        sendMessageSafe(
          { action: 'checkTrustedContact', email: emailData.sender },
          response => resolve(response || { trusted: false })
        );
      });

      if (trustedCheck && trustedCheck.trusted) {
        console.log('Trusted sender detected:', emailData.sender);
        saveIncomingEmail(emailData);
      }
    } finally {
      checkingEmail = false;
    }
  }

  /**
   * Setup inbox monitoring
   */
  function setupInboxMonitor() {
    // Check on URL changes (when user opens an email)
    let lastUrl = window.location.href;

    const urlObserver = setInterval(() => {
      if (window.location.href !== lastUrl) {
        lastUrl = window.location.href;
        // Wait a moment for email content to load
        setTimeout(checkCurrentEmail, 1000);
      }
    }, 500);

    // Also check when page content changes significantly
    const contentObserver = new MutationObserver((mutations) => {
      // Debounce - only check if we haven't recently
      if (!checkingEmail && getGmailIdFromUrl() !== lastCheckedEmailId) {
        setTimeout(checkCurrentEmail, 500);
      }
    });

    const mainContent = document.querySelector('div[role="main"]');
    if (mainContent) {
      contentObserver.observe(mainContent, {
        childList: true,
        subtree: true
      });
    }

    console.log('Gmail inbox monitor: Active');
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
        setupInboxMonitor();
        console.log('Gmail to Claude Memory: Ready (send + inbox monitoring)');
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
