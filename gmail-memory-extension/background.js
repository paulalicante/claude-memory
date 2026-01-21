/**
 * Gmail to Claude Memory - Background Service Worker
 * Handles communication with the local Claude Memory HTTP server
 */

// Default server URL
const DEFAULT_SERVER_URL = 'http://127.0.0.1:8765';

/**
 * Get the server URL from storage or use default
 */
async function getServerUrl() {
  try {
    const result = await chrome.storage.sync.get(['serverUrl']);
    return result.serverUrl || DEFAULT_SERVER_URL;
  } catch (e) {
    return DEFAULT_SERVER_URL;
  }
}

/**
 * Save a memory to the Claude Memory server
 */
async function saveMemory(data) {
  const serverUrl = await getServerUrl();
  const endpoint = `${serverUrl}/api/memories`;

  try {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(data)
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || `HTTP ${response.status}`);
    }

    const result = await response.json();
    return { success: true, id: result.id };

  } catch (error) {
    console.error('Failed to save memory:', error);

    // Check if it's a connection error
    if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
      return {
        success: false,
        error: 'Cannot connect to Claude Memory. Is the app running?'
      };
    }

    return { success: false, error: error.message };
  }
}

/**
 * Check if the Claude Memory server is running
 */
async function checkServerHealth() {
  const serverUrl = await getServerUrl();
  const endpoint = `${serverUrl}/api/health`;

  try {
    const response = await fetch(endpoint, { method: 'GET' });
    if (response.ok) {
      const data = await response.json();
      return { online: true, status: data.status };
    }
    return { online: false, error: `HTTP ${response.status}` };
  } catch (error) {
    return { online: false, error: 'Cannot connect' };
  }
}


/**
 * Add email addresses as trusted contacts
 */
async function addTrustedContacts(emails) {
  const serverUrl = await getServerUrl();
  const endpoint = `${serverUrl}/api/contacts`;

  try {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ emails })
    });
    return await response.json();
  } catch (error) {
    return { success: false, error: error.message };
  }
}


/**
 * Check if an email address is a trusted contact
 */
async function checkTrustedContact(email) {
  const serverUrl = await getServerUrl();
  const endpoint = `${serverUrl}/api/contacts/check?email=${encodeURIComponent(email)}`;

  try {
    const response = await fetch(endpoint);
    const data = await response.json();
    return data.trusted || false;
  } catch (error) {
    return false;
  }
}


/**
 * Check if an email has already been saved
 */
async function checkEmailSaved(gmailId) {
  const serverUrl = await getServerUrl();
  const endpoint = `${serverUrl}/api/emails/check?gmail_id=${encodeURIComponent(gmailId)}`;

  try {
    const response = await fetch(endpoint);
    const data = await response.json();
    return data.saved || false;
  } catch (error) {
    return false;
  }
}


/**
 * Mark an email as saved
 */
async function markEmailSaved(gmailId, entryId) {
  const serverUrl = await getServerUrl();
  const endpoint = `${serverUrl}/api/emails/mark-saved`;

  try {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ gmail_id: gmailId, entry_id: entryId })
    });
    return await response.json();
  } catch (error) {
    return { success: false, error: error.message };
  }
}

// Listen for messages from content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'saveMemory') {
    saveMemory(message.data)
      .then(sendResponse)
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true; // Keep channel open for async response
  }

  if (message.action === 'checkHealth') {
    checkServerHealth()
      .then(sendResponse)
      .catch(err => sendResponse({ online: false, error: err.message }));
    return true;
  }

  if (message.action === 'getServerUrl') {
    getServerUrl()
      .then(url => sendResponse({ url }))
      .catch(err => sendResponse({ url: DEFAULT_SERVER_URL }));
    return true;
  }

  if (message.action === 'addTrustedContacts') {
    addTrustedContacts(message.emails)
      .then(sendResponse)
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true;
  }

  if (message.action === 'checkTrustedContact') {
    checkTrustedContact(message.email)
      .then(trusted => sendResponse({ trusted }))
      .catch(() => sendResponse({ trusted: false }));
    return true;
  }

  if (message.action === 'checkEmailSaved') {
    checkEmailSaved(message.gmailId)
      .then(saved => sendResponse({ saved }))
      .catch(() => sendResponse({ saved: false }));
    return true;
  }

  if (message.action === 'markEmailSaved') {
    markEmailSaved(message.gmailId, message.entryId)
      .then(sendResponse)
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true;
  }
});

// Log when extension loads
console.log('Gmail to Claude Memory: Background service worker loaded');
