# Proyecta — estado maestro

Repositorio central y fuente técnica: https://github.com/fetcam/proyecta
Rama de desarrollo: `unlazy/tree3-skill-advisor-production`. La rama principal `main` se conserva sin cambios.

Versión en desarrollo: 1.2.0.

Implementado en esta rama: flujo de tareas de producción (estados, aceptación, dependencias, rol/IA, contexto de entrega, pruebas y reanudación); Asesor de skills con descubrimiento acotado de rutas locales Codex/Claude Code, importación y escaneo con un clic, carpetas descargadas etiquetadas por plataforma ChatGPT, catálogo de metadatos, ranking explicable, alternativas, selección y opciones de sugerencia. La aplicación sigue siendo local-first y no incorpora ejecución/dispatch de agentes, acceso a cuentas ChatGPT ni lectura automática de historiales.

Verificación de esta revisión: 27 pruebas unitarias de Store, integraciones y Asesor; sintaxis Python/JavaScript; contratos estáticos de la UI del Asesor y del flujo de tareas. Sin validación visual Chromium ni instalación en Linux Mint del usuario. Los flujos DOM de regresión existentes dependen de `jsdom`, ausente en el entorno.

Siguiente paso: publicar/revisar la rama cuando el checkout tenga remoto GitHub disponible y probar interfaz/migración sobre una copia de datos del usuario. La importación de contexto de proyectos de IA/Cloud queda especificada en `IMPORTACION_CONTEXTO_Y_CONTINUIDAD_TECNICA.md`; el descubrimiento e importación de skills por plataforma está detallado en `EXPLORACION_E_IMPORTACION_DE_SKILLS.md`.
