const { app, BrowserWindow } = require('electron');
const path = require('path');

function createWindow() {
  const win = new BrowserWindow({
    width: 600,
    height: 400,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true
    },
    backgroundColor: '#F0F0F0',
    autoHideMenuBar: true
  });

  win.loadFile('index.html');

  // Always show on current desktop
  win.setAlwaysOnTop(true);
  setTimeout(() => {
    win.setAlwaysOnTop(false);
  }, 500);
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
