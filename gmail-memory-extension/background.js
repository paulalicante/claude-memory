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

// =============================================
// Dynamic extension icon - lights up when connected
// =============================================

/**
 * Draw the CM icon on an OffscreenCanvas
 * @param {number} size - Icon size (16, 32, 48, 128)
 * @param {boolean} active - Whether server is connected
 * @returns {ImageData}
 */
function drawIcon(size, active) {
  const canvas = new OffscreenCanvas(size, size);
  const ctx = canvas.getContext('2d');

  const bgColor = active ? '#268BD2' : '#93A1A1';      // Blue when active, gray when not
  const glowColor = active ? '#34a853' : 'transparent'; // Green glow when active
  const textColor = '#FFFFFF';

  // Background circle
  const cx = size / 2;
  const cy = size / 2;
  const r = size * 0.45;

  // Glow effect when active
  if (active) {
    ctx.beginPath();
    ctx.arc(cx, cy, r + size * 0.05, 0, Math.PI * 2);
    ctx.fillStyle = glowColor;
    ctx.globalAlpha = 0.4;
    ctx.fill();
    ctx.globalAlpha = 1.0;
  }

  // Main circle
  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, Math.PI * 2);
  ctx.fillStyle = bgColor;
  ctx.fill();

  // "CM" text
  const fontSize = Math.round(size * 0.38);
  ctx.font = `bold ${fontSize}px sans-serif`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillStyle = textColor;
  ctx.fillText('CM', cx, cy + size * 0.02);

  // Small status dot (bottom-right)
  const dotR = size * 0.12;
  const dotX = cx + r * 0.65;
  const dotY = cy + r * 0.65;
  ctx.beginPath();
  ctx.arc(dotX, dotY, dotR + 1, 0, Math.PI * 2);
  ctx.fillStyle = '#FFFFFF'; // White border
  ctx.fill();
  ctx.beginPath();
  ctx.arc(dotX, dotY, dotR, 0, Math.PI * 2);
  ctx.fillStyle = active ? '#34a853' : '#ea4335'; // Green or red dot
  ctx.fill();

  return ctx.getImageData(0, 0, size, size);
}

/**
 * Update the extension icon based on server status
 */
let lastIconState = null;

async function updateIcon() {
  const health = await checkServerHealth();
  const active = health.online;

  // Skip if state hasn't changed
  if (lastIconState === active) return;
  lastIconState = active;

  try {
    const imageData = {
      16: drawIcon(16, active),
      32: drawIcon(32, active),
      48: drawIcon(48, active),
    };

    await chrome.action.setIcon({ imageData });
    await chrome.action.setTitle({
      title: active
        ? 'Claude Memory - Connected'
        : 'Claude Memory - Not connected'
    });
  } catch (e) {
    console.error('Failed to update icon:', e);
  }
}

// Check health and update icon periodically
updateIcon();
setInterval(updateIcon, 15000); // Every 15 seconds

// Also update when the service worker wakes up
chrome.runtime.onStartup.addListener(updateIcon);
chrome.runtime.onInstalled.addListener(updateIcon);

// Log when extension loads
console.log('Gmail to Claude Memory: Background service worker loaded');
