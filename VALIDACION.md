# Validación de Proyecta 1.3

## Checks locales

```bash
PYTHONPATH=tests python3 -m unittest test_app.StoreTests test_integrations.IntegrationTests test_skills test_context_imports -v
node --check static/app.js
python3 -m py_compile app.py integrations.py skills.py context_imports.py
node tests/ui-skill-advisor.cjs
node tests/ui-production-workflow.cjs
node tests/ui-context-import.cjs
```

La suite de datos cubre ciclo de vida de tareas, dependencias, evidencia obligatoria, checkpoints, importación de proyectos, revisión selectiva, deduplicación, procedencia, control de versión, dossier técnico y respaldos anteriores; catálogo, límites de escaneo, enlaces simbólicos, ranking, preferencias, detección Claude/Codex y ausencia de rutas inventadas para cuentas ChatGPT. Los contratos UI comprueban los flujos del Asesor, tareas e importación de contexto. Los tests HTTP requieren abrir un socket local; este entorno no permite enlazar loopback.

## Límites pendientes de verificación

- Los tests DOM anteriores (`ui-smoke.cjs`, `ui-integrations.cjs`) requieren `jsdom`, que no está instalado en el entorno actual.
- No se validó renderizado Chromium ni accesibilidad visual/responsive.
- No se instaló en Linux Mint real ni se probó Windows/macOS.
- El escáner solo revisa rutas convencionales o directorios agregados y sus subdirectorios directos. ChatGPT requiere una carpeta local descargada; no se conecta a la cuenta.
- No hay dispatch/ejecución de agentes, instalación automática de skills, autenticación ni sincronización automática de historiales.
