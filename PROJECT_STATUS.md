# Proyecta — estado maestro

Repositorio central y fuente técnica: https://github.com/fetcam/proyecta
Rama de desarrollo: `unlazy/tree3-skill-advisor-production`. La rama principal `main` se conserva sin cambios.

Versión en desarrollo: 1.3.0.

Implementado en esta rama: importación guiada de contexto de proyectos desde ChatGPT Personal/Business/Work, Claude, Claude Code y Codex/Cloud con revisión selectiva, comparación de valores, deduplicación, procedencia por elemento, control de versión, tareas pendientes y expediente técnico Markdown; flujo de tareas de producción (estados, aceptación, dependencias, rol/IA, contexto de entrega, pruebas y reanudación); Asesor de skills con descubrimiento acotado de rutas locales Codex/Claude Code, importación y escaneo con un clic, carpetas descargadas etiquetadas por plataforma ChatGPT, catálogo de metadatos, ranking explicable, alternativas, selección y opciones de sugerencia. La aplicación sigue siendo local-first y no incorpora ejecución/dispatch de agentes, acceso a cuentas ChatGPT ni lectura automática de historiales.

Verificación de esta revisión: pruebas unitarias de Store, integraciones, Asesor e importación de contexto; sintaxis Python/JavaScript; contratos estáticos de la UI. Los tests que abren un servidor HTTP no pueden enlazar loopback en este entorno. Sin validación visual Chromium ni instalación en Linux Mint del usuario. Los flujos DOM de regresión existentes dependen de `jsdom`, ausente en el entorno.

Siguiente paso: revisar la interfaz en un navegador de escritorio y probar la actualización de respaldo en una copia de datos del usuario. La importación guiada y sus limitaciones por proveedor están descritas en `IMPORTACION_CONTEXTO_Y_CONTINUIDAD_TECNICA.md`; el descubrimiento e importación de skills por plataforma está detallado en `EXPLORACION_E_IMPORTACION_DE_SKILLS.md`.
