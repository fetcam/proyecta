# Arquitectura 1.3

Python estándar, SQLite y frontend HTML/CSS/JavaScript. `app.py` mantiene el servidor local, registros y respaldos. `integrations.py` agrega perfiles, selección de fuentes, validación estricta del resumen, previsualización y escritura transaccional. `mcp_bridge.py` ofrece herramientas stdio acotadas a un proyecto/perfil.

La revisión no escribe datos. La incorporación valida nuevamente los permisos y la versión actual del proyecto. Los campos de estado admitidos son goal/status/next_action/latest_progress; las decisiones son textos. Los digests SHA-256 se deduplican por proyecto/perfil; no distinguen cambios históricos A→B→A, por lo que un estado importado previamente no se reaplica automáticamente. Para revertir, edita el proyecto o registra explícitamente una nueva decisión.

`accounts` conserva etiquetas y proveedor; no credenciales. `project_sources` conserva permisos de estado/decisiones. `imported_items` conserva digests para evitar repeticiones. Los resúmenes originales no se guardan completos: se guardan únicamente elementos elegidos en el proyecto y en el historial. Las decisiones no se reconcilian semánticamente.

GitHub y Drive son enlaces a las fuentes canónicas; el estado registrado no se presenta como comprobación de sus contenidos. La migración agrega tablas y phase sin borrar datos. El respaldo incluye las nuevas tablas, y el importador valida referencias antes de reemplazar datos.


## Tareas de producción y Asesor de skills

La migración SQLite es aditiva. `tasks` añade alcance, aceptación, dependencias JSON, proveedor IA, rol, skills seleccionadas, rama, commit, URL de PR, pruebas, checkpoint y entorno. Las dependencias se limitan al proyecto, no pueden formar ciclos y deben estar completadas antes de completar una tarea. La finalización requiere evidencia. El contexto de tarea exportado incorpora estos campos y las skills seleccionadas.

`skills.py` lista solo ubicaciones convencionales bajo el home y el directorio del proyecto, sin caminar el disco; las rutas detectadas se pueden importar y escanear directamente. Para ChatGPT, las carpetas locales descargadas se agregan como fuente con plataforma elegida: Proyecta no supone que existe un directorio local de cuenta ni accede al catálogo web. Conserva fuentes y metadatos extraídos de `SKILL.md`. El lector limita cada archivo a 64 KiB, solo sigue directorios directos regulares y omite enlaces simbólicos. No importa el cuerpo del archivo. Las recomendaciones son deterministas y explican coincidencias de palabras con nombre, etiquetas y descripción. Las asociaciones son referencias locales; Proyecta nunca instala, ejecuta ni delega en una skill. Al retirar del catálogo una skill, limpia sus asociaciones y deja una nota en el historial. El alcance de descubrimiento por plataforma está en `EXPLORACION_E_IMPORTACION_DE_SKILLS.md`.

El respaldo usa `schema_version: 3`; el importador acepta respaldos 1, 2 y 3, valida dependencias y referencias antes de reemplazar datos, y crea una copia previa. Las preferencias conservan el modo manual o sugerencias al abrir/editar una tarea; el valor predeterminado es manual.

`context_imports` y `context_import_items` guardan la procedencia y únicamente los elementos seleccionados por la persona. El formato `proyecta.context.v1` acepta el diseño, componentes, decisiones, backlog, pruebas declaradas, riesgos y avance. La revisión compara los valores actuales, señala duplicados y comprueba la versión del proyecto antes de escribir. El backlog se convierte en tareas pendientes; ninguna tarea importada queda completada. Las afirmaciones se etiquetan `declarado_en_fuente`; el dossier Markdown mantiene esa distinción y se descarga desde la ficha del proyecto. La captura usa prompts y JSON elegidos por la persona; no importa archivos nativos de conversación ni inicia sesión en ChatGPT o Claude.
