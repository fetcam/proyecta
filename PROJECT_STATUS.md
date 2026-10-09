# Proyecta — estado maestro

Repositorio central y fuente de verdad técnica: https://github.com/fetcam/proyecta
Decisión del usuario: 2026-10-09. Acceso de lectura y escritura confirmado.
Repositorio público, rama principal: main.
Publicación inicial: código Proyecta 1.1, pruebas y documentación.

Versión: 1.1.0. Fecha: 2026-10-08.

Implementado: almacenamiento local, proyectos, tareas, decisiones, historial, atención, respaldos; perfiles IA y roles; selección por proyecto de estado y decisiones; intercambio JSON revisado; deduplicación y conflictos; puente MCP stdio; tablero con fase, avance, próxima acción, IA y enlaces GitHub/Drive.

Verificación: 23 pruebas Python y dos flujos DOM. Sin prueba visual Chromium ni instalación en equipos del usuario.

Pendientes: autenticar y probar clientes MCP reales; conectar GitHub y Google Drive con OAuth y lectura de contenido. No existe acceso automático al historial de cuentas de ChatGPT/Claude.

Próximo paso: instalar 1.1 en Linux Mint sobre el mismo directorio de datos y configurar perfiles y fuentes para un proyecto piloto.
