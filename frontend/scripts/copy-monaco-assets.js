const fs = require('fs');
const path = require('path');

const src = path.resolve(__dirname, '../node_modules/monaco-editor/min/vs');
const dest = path.resolve(__dirname, '../public/monaco/vs');

if (!fs.existsSync(src)) {
  console.warn('[copy-monaco] monaco-editor/min/vs not found — skip');
  process.exit(0);
}

fs.rmSync(dest, { recursive: true, force: true });
fs.mkdirSync(path.dirname(dest), { recursive: true });
fs.cpSync(src, dest, { recursive: true });
console.log('[copy-monaco] copied monaco assets to public/monaco/vs');
