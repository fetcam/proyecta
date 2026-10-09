# Proyecta — estado maestro

Repositorio central y fuente técnica: https://github.com/fetcam/proyecta
Rama de desarrollo: `unlazy/tree3-skill-advisor-production`. La rama principal `main` se conserva sin cambios.

Versión en desarrollo: 1.2.0.

Implementado en esta rama: flujo de tareas de producción (estados, aceptación, dependencias, rol/IA, contexto de entrega, pruebas y reanudación); Asesor de skills con fuentes locales explícitas, catálogo de metadatos, ranking explicable, alternativas, selección y opciones de sugerencia. La aplicación sigue siendo local-first y no incorpora ejecución/dispatch de agentes ni lectura automática de historiales.

Verificación de esta revisión: pruebas unitarias de Store, integraciones y Asesor; sintaxis Python/JavaScript; contrato estático de la UI. Sin validación visual Chromium ni instalación en Linux Mint del usuario. Los flujos DOM de regresión existentes dependen de `jsdom`, ausente en el entorno.

Siguiente paso: revisar la rama y probar la interfaz y migración sobre una copia del directorio de datos del usuario.
