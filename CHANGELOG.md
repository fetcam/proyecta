# Cambios

## 1.3.0 — 9 octubre 2026

Importación guiada de proyectos desde ChatGPT Personal/Business/Work, Claude, Claude Code y Codex/Cloud. El usuario prepara el JSON con un prompt, compara los elementos con el proyecto y selecciona qué guardar. Se registra procedencia por elemento, se omiten duplicados, se rechaza una revisión obsoleta y el backlog aprobado crea tareas pendientes. El expediente técnico se descarga como Markdown. Los respaldos pasan a schema 3 y siguen aceptando versiones 1 y 2.

La importación no inicia sesión ni procesa exportaciones nativas de conversaciones. El sistema conserva solo los elementos aceptados y clasifica avances/pruebas como declaraciones de la fuente.

## 1.2.0 — 9 octubre 2026

Asesor local de skills con fuentes explícitas, escaneo acotado de metadatos, recomendaciones explicables, preferencias por momento/proveedor y asociación manual a tareas. Flujo de tareas de producción con ciclo de vida, aceptación, dependencias, rol/IA, entorno, evidencia de código/pruebas, PR y checkpoint. Contextos de tarea y backups compatibles con datos anteriores.

Actualización de alcance: catálogo de skills agrupado por plataforma; descubrimiento limitado de directorios locales de Codex y Claude Code; importación de carpetas descargadas desde ChatGPT etiquetadas para Personal o Business; vista de skills relacionadas por etiquetas. No accede a cuentas ChatGPT ni instala o ejecuta skills.


## 1.1.0 — 8 octubre 2026

Perfiles de IA separados y roles asignados. Selección de estado/decisiones por perfil y proyecto. Revisión e incorporación de JSON con deduplicación, procedencia y control de versión. Puente MCP stdio con alcance fijo y escritura opcional. Tablero con fuentes GitHub/Drive, última IA, avance y fase. Migración aditiva desde 1.0 y respaldos que incluyen las integraciones.

Las cuentas no están autenticadas desde Proyecta. No existe sincronización del historial ni lectura automática de GitHub/Drive en este paquete.

## 1.0.0

MVP local con proyectos, tareas, decisiones, actividad, atención, respaldos y contexto portable.
