# Proyecta 1.2 — Centro de control local

Repositorio central: https://github.com/fetcam/proyecta

Python 3.10+ y SQLite. Sin dependencias para ejecutar la aplicación. Linux Mint primero; código portable para Windows y macOS. No probado en esos equipos.

## Arranque y actualización desde 1.0 o 1.1

1. Detén la versión que estés usando y descarga un respaldo desde la aplicación.
2. Extrae este paquete en una carpeta nueva; no borres el directorio de datos.
3. En la carpeta con `app.py`, ejecuta `python3 app.py` (Windows: `python app.py`).
4. Abre http://127.0.0.1:8765.

Usa el mismo `--data-dir` si lo habías personalizado. Los datos existentes se conservan y las nuevas tablas se crean al arrancar. No ejecutes dos versiones simultáneamente. La migración 1.2 agrega campos de tareas y tablas para el catálogo sin borrar los datos existentes. El respaldo 1.2 incluye perfiles, selecciones, deduplicación, skills y preferencias. Los respaldos 1.0/1.1 se aceptan; restaurarlos reemplaza el estado actual y los campos nuevos toman valores predeterminados.

`start.sh`, `start.bat` e `install_desktop.py` conservan el arranque y acceso de escritorio originales.

## Qué incorpora esta versión

- Flujo de tareas de producción: pendiente, lista, en curso, bloqueada, revisión, validación y completada; criterios de aceptación, dependencias, IA/rol, entorno, rama, commit, PR, pruebas y punto de reanudación. No permite completar con dependencias pendientes ni sin evidencia.

- Tablero con proyecto, empresa, fase/estado, último avance, próximo paso, IA usada, GitHub y Drive.
- Fases: Diseño, MVP, Desarrollo, Pruebas y Listo. Separadas del estado operativo activo/pausado/completado.
- Perfiles independientes para ChatGPT Personal, Business, Work, Codex, Claude y Claude Code. Puedes registrar varios perfiles del mismo proveedor y distinguir sus espacios.
- Selección de estado y/o decisiones por perfil y proyecto.
- Intercambio de resúmenes JSON con revisión por elemento, comparación con el estado actual, deduplicación y protección contra cambios simultáneos.
- Procedencia en el historial: herramienta, etiqueta del perfil y referencia del resumen.
- Puente MCP local para clientes compatibles, limitado a un proyecto y perfil.

## Asesor de skills

En **Asesor de skills**, Proyecta lista si existen ubicaciones habituales (`~/.agents/skills`, `~/.codex/skills`, `~/.claude/skills` y equivalentes del proyecto) sin recorrer otras carpetas. Elige qué directorio agregar, asigna cada fuente a un entorno (por ejemplo Codex o Claude Code) y escanéala. Puedes indicar una carpeta individual con `SKILL.md` o una carpeta padre con subcarpetas de skills. El catálogo solo guarda nombre, descripción, etiquetas, ruta relativa y huella. El escaneo lee hasta 64 KB por `SKILL.md`, no sigue enlaces simbólicos y tiene límites de cantidad.

Las recomendaciones locales comparan el título, objetivo, criterios, notas y etapa con el nombre, descripción y etiquetas. Muestran los términos coincidentes y compatibilidad del proveedor. Puedes revisar hasta tres opciones, seleccionarlas, asociarlas a una tarea u omitirlas. En preferencias eliges sugerencia manual, al abrir una tarea o al editar su alcance. Proyecta no ejecuta ni instala skills; al quitar una fuente, sus referencias se retiran de las tareas y queda una nota de actividad.

## Configurar un proyecto

En **Editar proyecto**, registra:

- GitHub: repositorio canónico del código; rama activa y restricciones autorizadas.
- Google Drive: carpeta o documento maestro de especificaciones, reuniones y materiales.
- Empresa, objetivo, fase y próxima acción.

En **Perfiles e intercambio**, crea los perfiles que usas. Estos son registros locales de procedencia, no sesiones autenticadas. Puedes usar una etiqueta como `Samuel Business / Savetek`; no ingreses contraseñas, cookies ni claves API.

Abre cada proyecto y marca cuáles perfiles pueden incorporar **Estado**, **Decisiones** o ambos. Guarda la selección.

## ChatGPT Personal / Business / Work y Claude: intercambio revisado

1. En **Perfiles e intercambio**, elige el proyecto y un perfil habilitado.
2. Prepara o descarga el prompt de resumen.
3. Pégalo en la conversación pertinente de esa cuenta. Solicita solamente el estado vigente y decisiones aprobadas.
4. Copia el JSON devuelto o guárdalo como `.json`. Pégalo o cárgalo en Proyecta.
5. Pulsa **Revisar elementos**. Selecciona exactamente lo que quieres incorporar.
6. Pulsa **Incorporar selección**.

Los campos de estado seleccionados reemplazan sus valores; las decisiones se agregan. Los duplicados se omiten. Si otro usuario o agente modifica el proyecto después de revisar, la incorporación se rechaza: recarga y vuelve a revisar. No se combinan automáticamente decisiones contradictorias; revisa su vigencia.

Ejemplo en `examples/resumen.json`. No se admiten archivos completos de conversaciones ni exportaciones originales de cuentas. Resume primero lo pertinente dentro de la IA y revisa sus afirmaciones. Una decisión registrada por la IA no constituye evidencia de que el código fue implementado o probado.

## Roles asignados

| Herramienta | Rol |
|---|---|
| ChatGPT Business / Work | Dirección y orquestación del proyecto |
| Codex | Implementación, debugging, tests y repositorios |
| Claude Code | Segunda implementación o trabajos aislados |
| Claude | Arquitectura, crítica, revisión de especificaciones y segunda opinión |
| ChatGPT Personal | Exploración y borradores |

Estos roles se incluyen en los prompts; no ejecutan ni delegan tareas por sí solos.

## Integración MCP local: Claude Code o Codex

MCP usa entrada/salida estándar, sin abrir un puerto adicional ni enviar datos a un proveedor desde Proyecta. El cliente IA ejecuta el puente en tu computadora y puede incluir lo consultado en su propio contexto.

El número de proyecto aparece en **Fuentes de IA**. El número de perfil aparece en su tarjeta. Configura el puente en el cliente MCP con rutas absolutas:

```json
{
  "mcpServers": {
    "proyecta-ripo": {
      "command": "python3",
      "args": ["/ruta/Proyecta/mcp_bridge.py", "--project", "1", "--account", "1"]
    }
  }
}
```

Este objeto es una plantilla para clientes que aceptan `mcpServers`. Adapta al formato de tu cliente; Proyecta no modifica su configuración. En Windows usa `python` y rutas absolutas de Windows. Si personalizaste el directorio de datos, agrega `--data-dir` y su ruta.

Por defecto están disponibles `project_context` y `preview_summary`. Para habilitar incorporación, agrega `--allow-write`. Aparece `apply_summary`, que exige el resumen, la versión revisada y los `digest` seleccionados. Las selecciones por proyecto siguen siendo obligatorias. Cada proceso queda fijado a un único proyecto y perfil; crea una configuración separada para otro proyecto o herramienta. Mantén habilitados los controles de aprobación de tu cliente.

Puedes pedir al agente: «Consulta project_context, devuelve solo el estado y decisiones de esta sesión, ejecuta preview_summary y presenta la selección antes de apply_summary».

El puente no inicia sesión en Claude o ChatGPT: utiliza la sesión que ya tiene el cliente. La compatibilidad del protocolo fue probada con solicitudes simuladas; no se probó una conexión real con las cuentas del usuario.

## Alcance real de las integraciones

| Fuente | Disponible en 1.2 | Pendiente |
|---|---|---|
| ChatGPT Personal, Business, Work | Perfiles y resúmenes revisados | Acceso automático al historial / OAuth de cuenta |
| Claude | Perfiles y resúmenes revisados | Acceso automático al historial |
| Claude Code / Codex | Puente MCP local | Configuración y prueba en tu cliente real |
| GitHub | Asociación de repositorio y rama; enlace del tablero | OAuth, lectura de commits/PR y webhooks |
| Google Drive | Asociación de carpeta/documento; enlace del tablero | OAuth e importación del contenido |

Iniciar sesión con ChatGPT no concede acceso a sus conversaciones. La API de conversaciones de OpenAI no equivale al historial de una cuenta ChatGPT. Esta versión no ofrece botones de conexión ficticios ni reutiliza cookies del navegador.

Documentación consultada: https://developers.openai.com/siwc/quickstart y https://support.claude.com/es/articles/13346720-exporta-los-datos-de-tu-organizacion (8 octubre 2026).

## Verificación

```bash
PYTHONPATH=tests python3 -m unittest test_app.StoreTests test_integrations.IntegrationTests test_skills -v
node --check static/app.js
node tests/ui-skill-advisor.cjs
```

La prueba de regresión cubre tareas, dependencias, importación anterior, perfiles, intercambio, MCP simulado y el catálogo del Asesor. El contrato estático de UI valida las acciones y textos principales; los flujos DOM antiguos requieren `jsdom`, que no está instalado aquí. No se validó el renderizado Chromium ni una instalación real en Linux Mint/Windows/macOS.
