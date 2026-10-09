# Validación de Proyecta 1.2

## Checks locales

```bash
PYTHONPATH=tests python3 -m unittest test_app.StoreTests test_integrations.IntegrationTests test_skills -v
node --check static/app.js
python3 -m py_compile app.py integrations.py skills.py
node tests/ui-skill-advisor.cjs
```

La suite de datos cubre ciclo de vida de tareas, dependencias, evidencia obligatoria, checkpoints y exportación de contexto; importación compatible con respaldos anteriores; catálogo, límites de escaneo, enlaces simbólicos, ranking, preferencias, detección Claude/Codex y ausencia de rutas inventadas para cuentas ChatGPT. El contrato UI comprueba los puntos de entrada y acciones del Asesor.

## Límites pendientes de verificación

- Los tests DOM anteriores (`ui-smoke.cjs`, `ui-integrations.cjs`) requieren `jsdom`, que no está instalado en el entorno actual.
- No se validó renderizado Chromium ni accesibilidad visual/responsive.
- No se instaló en Linux Mint real ni se probó Windows/macOS.
- El escáner solo revisa rutas convencionales o directorios agregados y sus subdirectorios directos. ChatGPT requiere una carpeta local descargada; no se conecta a la cuenta.
- No hay dispatch/ejecución de agentes, instalación automática de skills, autenticación ni sincronización automática de historiales.
