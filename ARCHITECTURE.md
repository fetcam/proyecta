# Arquitectura 1.1

Python estándar, SQLite y frontend HTML/CSS/JavaScript. `app.py` mantiene el servidor local, registros y respaldos. `integrations.py` agrega perfiles, selección de fuentes, validación estricta del resumen, previsualización y escritura transaccional. `mcp_bridge.py` ofrece herramientas stdio acotadas a un proyecto/perfil.

La revisión no escribe datos. La incorporación valida nuevamente los permisos y la versión actual del proyecto. Los campos de estado admitidos son goal/status/next_action/latest_progress; las decisiones son textos. Los digests SHA-256 se deduplican por proyecto/perfil; no distinguen cambios históricos A→B→A, por lo que un estado importado previamente no se reaplica automáticamente. Para revertir, edita el proyecto o registra explícitamente una nueva decisión.

`accounts` conserva etiquetas y proveedor; no credenciales. `project_sources` conserva permisos de estado/decisiones. `imported_items` conserva digests para evitar repeticiones. Los resúmenes originales no se guardan completos: se guardan únicamente elementos elegidos en el proyecto y en el historial. Las decisiones no se reconcilian semánticamente.

GitHub y Drive son enlaces a las fuentes canónicas; el estado registrado no se presenta como comprobación de sus contenidos. La migración agrega tablas y phase sin borrar datos. El respaldo incluye las nuevas tablas, y el importador valida referencias antes de reemplazar datos.
