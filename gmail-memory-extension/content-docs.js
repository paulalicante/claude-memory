/**
 * Google Docs to Claude Memory - Content Script
 * Adds a floating button to save document content to Claude Memory
 */

(function() {
  'use strict';

  let floatingButton = null;
  let isMinimized = false;

  /**
   * Get the document title
   */
  function getDocumentTitle() {
    const titleInput = document.querySelector('input.docs-title-input');
    if (titleInput && titleInput.value) {
      return titleInput.value;
    }
    const pageTitle = document.title.replace(' - Google Docs', '').trim();
    return pageTitle || 'Untitled Document';
  }

  /**
   * Get document content via Python backend (sends real keystrokes)
   */
  async function getDocumentContent() {
    console.log('CM: Requesting copy via Python backend...');

    try {
      // Get server URL from storage
      const result = await chrome.storage.sync.get(['serverUrl']);
      const serverUrl = result.serverUrl || 'http://127.0.0.1:8765';

      // Call the Python backend to send real Ctrl+A, Ctrl+C
      const response = await fetch(`${serverUrl}/api/copy-document`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      const data = await response.json();

      if (data.success && data.content) {
        console.log('CM: Got', data.length, 'chars from backend');
        return data.content;
      } else {
        console.log('CM: Backend copy failed:', data.error);
        return '';
      }
    } catch (e) {
      console.log('CM: Backend request failed:', e);
      return '';
    }
  }

  /**
   * Create the floating save button
   */
  function createFloatingButton() {
    if (floatingButton) return;

    floatingButton = document.createElement('div');
    floatingButton.id = 'cm-docs-floating-btn';
    floatingButton.innerHTML = `
      <div class="cm-docs-btn-content">
        <button class="cm-docs-save-btn" title="Save document to Claude Memory">
          <span class="cm-docs-icon">CM</span>
          <span class="cm-docs-label">Save to Memory</span>
        </button>
        <button class="cm-docs-minimize-btn" title="Minimize">
          <span>_</span>
        </button>
      </div>
    `;

    const saveBtn = floatingButton.querySelector('.cm-docs-save-btn');
    const minimizeBtn = floatingButton.querySelector('.cm-docs-minimize-btn');

    saveBtn.addEventListener('click', handleSave);
    minimizeBtn.addEventListener('click', toggleMinimize);

    document.body.appendChild(floatingButton);
  }

  /**
   * Toggle minimized state
   */
  function toggleMinimize() {
    isMinimized = !isMinimized;
    floatingButton.classList.toggle('cm-minimized', isMinimized);

    const label = floatingButton.querySelector('.cm-docs-label');
    const minBtn = floatingButton.querySelector('.cm-docs-minimize-btn span');

    if (isMinimized) {
      label.style.display = 'none';
      minBtn.textContent = '+';
    } else {
      label.style.display = 'inline';
      minBtn.textContent = '_';
    }
  }

  /**
   * Handle save button click - one click, Python backend handles keystrokes
   */
  async function handleSave() {
    const saveBtn = floatingButton.querySelector('.cm-docs-save-btn');
    const originalHTML = saveBtn.innerHTML;

    // IMPORTANT: Blur the button immediately to return focus to the document
    // This must happen BEFORE we update the button text
    saveBtn.blur();

    // Click on the document editor to ensure it has focus
    const editor = document.querySelector('.kix-appview-editor');
    if (editor) {
      editor.click();
    }

    saveBtn.innerHTML = '<span class="cm-docs-icon">...</span><span class="cm-docs-label">Copying...</span>';
    saveBtn.disabled = true;

    // Python backend sends real Ctrl+A, Ctrl+C and returns content
    const content = await getDocumentContent();
    const title = getDocumentTitle();

    if (!content) {
      saveBtn.innerHTML = originalHTML;
      saveBtn.disabled = false;
      showToast('Could not copy document - is Claude Memory running?', 'error');
      return;
    }

    const memoryData = {
      title: 'Doc: ' + title,
      content: content,
      category: 'document',
      tags: 'google-docs',
      metadata: {
        source: 'google-docs',
        documentTitle: title,
        url: window.location.href,
        date: new Date().toISOString()
      }
    };

    saveBtn.innerHTML = '<span class="cm-docs-icon">...</span><span class="cm-docs-label">Saving...</span>';

    chrome.runtime.sendMessage({
      action: 'saveMemory',
      data: memoryData
    }, function(response) {
      saveBtn.innerHTML = originalHTML;
      saveBtn.disabled = false;

      if (response && response.success) {
        showToast('Saved to Claude Memory!', 'success');
      } else {
        showToast('Failed: ' + (response ? response.error : 'Unknown error'), 'error');
      }
    });
  }

  /**
   * Show a toast notification
   */
  function showToast(message, type) {
    const toast = document.createElement('div');
    toast.className = 'cm-toast cm-toast-' + type;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(function() {
      toast.classList.add('cm-toast-fade');
      setTimeout(function() { toast.remove(); }, 300);
    }, 3000);
  }

  /**
   * Initialize
   */
  function init() {
    console.log('Google Docs to Claude Memory: Initializing...');

    var checkCount = 0;
    var checkReady = setInterval(function() {
      checkCount++;
      var editor = document.querySelector('.kix-appview-editor, .docs-editor-container');
      if (editor) {
        clearInterval(checkReady);
        createFloatingButton();
        console.log('Google Docs to Claude Memory: Ready');
      }
      if (checkCount > 30) {
        clearInterval(checkReady);
      }
    }, 1000);
  }

  // Start
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
