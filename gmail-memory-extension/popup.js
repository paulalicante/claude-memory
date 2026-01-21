/**
 * Gmail to Claude Memory - Popup Script
 */

const DEFAULT_SERVER_URL = 'http://127.0.0.1:8765';

const statusEl = document.getElementById('status');
const statusTextEl = document.getElementById('status-text');
const serverUrlInput = document.getElementById('server-url');
const saveBtn = document.getElementById('save-btn');
const savedMsg = document.getElementById('saved-msg');

/**
 * Load settings from storage
 */
async function loadSettings() {
  try {
    const result = await chrome.storage.sync.get(['serverUrl']);
    serverUrlInput.value = result.serverUrl || DEFAULT_SERVER_URL;
  } catch (e) {
    serverUrlInput.value = DEFAULT_SERVER_URL;
  }
}

/**
 * Save settings to storage
 */
async function saveSettings() {
  const serverUrl = serverUrlInput.value.trim() || DEFAULT_SERVER_URL;

  try {
    await chrome.storage.sync.set({ serverUrl });

    // Show saved message
    savedMsg.classList.add('show');
    setTimeout(() => savedMsg.classList.remove('show'), 2000);

    // Re-check health
    checkHealth();
  } catch (e) {
    console.error('Failed to save settings:', e);
  }
}

/**
 * Check server health
 */
async function checkHealth() {
  statusEl.className = 'status status-checking';
  statusTextEl.textContent = 'Checking connection...';

  try {
    const response = await chrome.runtime.sendMessage({ action: 'checkHealth' });

    if (response.online) {
      statusEl.className = 'status status-online';
      statusTextEl.textContent = 'Connected to Claude Memory';
    } else {
      statusEl.className = 'status status-offline';
      statusTextEl.textContent = response.error || 'Cannot connect';
    }
  } catch (e) {
    statusEl.className = 'status status-offline';
    statusTextEl.textContent = 'Cannot connect';
  }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  loadSettings();
  checkHealth();
});

// Save button click
saveBtn.addEventListener('click', saveSettings);

// Save on Enter key
serverUrlInput.addEventListener('keypress', (e) => {
  if (e.key === 'Enter') {
    saveSettings();
  }
});
