const fs = require('fs');
const app = fs.readFileSync('static/app.js', 'utf8');
const html = fs.readFileSync('static/index.html', 'utf8');
for (const text of ['context-import', 'proyecta.context.v1', 'Revisar importación',
  'Incorporar selección revisada', 'Origen declarado:', '/api/context-import/preview',
  '/api/context-import/apply', '/api/context-dossier/']) {
  if (!app.includes(text) && !html.includes(text)) throw new Error(`Falta la integración de importación: ${text}`);
}
for (const provider of ['ChatGPT Personal', 'ChatGPT Business', 'Claude', 'Codex / Cloud']) {
  if (!app.includes(provider)) throw new Error(`Falta el proveedor: ${provider}`);
}
console.log('Context import UI contract passed');
