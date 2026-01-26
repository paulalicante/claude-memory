# Glossy Button Demo - Electron

A simple Electron app showcasing glossy 3D pill-shaped buttons with perfect CSS rendering.

## Features

- Deep blue glossy buttons with gradient backgrounds
- Strong white highlight on top (glossy effect)
- Smooth hover animations (lifts up)
- Click feedback (presses down)
- Perfect rendering using Chromium engine
- Three color variants to choose from

## Installation

1. Install Node.js if you don't have it: https://nodejs.org/

2. Install dependencies:
```bash
npm install
```

## Running

```bash
npm start
```

Or just double-click `run.bat`

## Building for Production

If you want to package this as a standalone app:

```bash
npm install --save-dev electron-builder
npx electron-builder
```

## Why Electron?

- Perfect CSS rendering (same as web browsers)
- No tkinter rendering issues
- Cross-platform (Windows, Mac, Linux)
- Easy to customize and extend
- Can reuse web components across projects
