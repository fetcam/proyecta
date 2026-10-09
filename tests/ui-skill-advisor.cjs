const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const html = readFileSync('static/index.html', 'utf8');
const js = readFileSync('static/app.js', 'utf8');
const css = readFileSync('static/style.css', 'utf8');
for (const text of ['data-view="skills"', 'Asesor de skills', 'v1.2']) assert.ok(html.includes(text), `index.html should include ${text}`);
for (const text of ['/api/skills/discover', '/api/skills/source', '/api/skills/scan', '/api/skills/preferences', '/api/skills/recommend', 'Fuentes locales encontradas', 'Importar y escanear', 'ChatGPT Business / Work', 'ChatGPT Personal', 'carpeta de una skill descargada', 'renderSkillCatalog', 'skill-platform-catalog', 'Por qué se sugiere', 'Ver origen y etiquetas', 'Omitir selección', 'Asociar seleccionadas', 'on_task_open', 'on_task_edit', 'nunca instala ni ejecuta skills']) {
  assert.ok(js.toLowerCase().includes(text.toLowerCase()), `app.js should include ${text}`);
}
for (const text of ['skill-catalog', 'skill-results', 'skill-card']) assert.ok(css.includes(text), `style.css should include ${text}`);
console.error('Skill Advisor UI contract passed');
