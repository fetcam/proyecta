# Importación de contexto y continuidad técnica

## Objetivo

Permitir que Proyecta incorpore proyectos ya trabajados en ChatGPT Personal, ChatGPT Business/Work, Codex Cloud y otras herramientas de IA. A partir del contexto seleccionado, debe reconstruir un expediente técnico actual, mostrar qué está confirmado y qué falta, y permitir continuar el desarrollo sin volver a capturar manualmente toda la información.

Esta capacidad extiende el intercambio revisado de Proyecta 1.2. No implica acceso secreto a cuentas, lectura indiscriminada de conversaciones ni ejecución automática de cambios.

## Resultado para el usuario

Desde un proyecto, la persona podrá elegir **Importar o actualizar contexto** y asociar una o varias fuentes. Proyecta generará una propuesta de estado y un expediente versionado para revisar. Tras aprobar los elementos, ofrecerá **Continuar desarrollo** con el repositorio, la rama, las decisiones, el backlog y la evidencia técnica relevantes.

El expediente debe responder, como mínimo:

- ¿Qué producto, módulo o problema se está desarrollando y cuál es su objetivo?
- ¿Cuál es el diseño funcional y técnico vigente?
- ¿Qué existe, qué está parcial, qué está pendiente, qué está bloqueado y qué se descartó?
- ¿Qué decisiones se aprobaron y cuáles están en conflicto o pendientes de confirmar?
- ¿Cuál es el repositorio canónico, rama activa, commit, PR y entorno relacionado?
- ¿Qué pruebas se ejecutaron, con qué resultado y cuándo?
- ¿Cuál es el nivel de desarrollo por fase o componente y en qué evidencia se basa?
- ¿Qué desarrollos se esperan, en qué orden y con qué criterios de aceptación?
- ¿Cuál es la siguiente acción recomendada y qué contexto necesita el agente para ejecutarla?

## Fuentes de verdad

Proyecta debe conservar la procedencia por afirmación y distinguir estas fuentes:

| Tipo de información | Fuente preferida | Tratamiento |
|---|---|---|
| Intención, alcance y decisiones | Proyecto/conversaciones de IA y documentos aprobados | Importar como afirmación con fuente, fecha y revisión; detectar contradicciones |
| Código y estructura técnica | Repositorio GitHub asociado | Verificar contra rama, commit y archivos cuando exista integración de lectura |
| Trabajo integrado | Commits y PRs | Usar estado y referencias como evidencia; no inferir que un PR abierto está terminado |
| Ejecución de pruebas | Salidas de CI o evidencia registrada | Guardar fecha, comando/ejecución y resultado; no marcar probado por una afirmación sin evidencia |
| Estado consolidado del proyecto | Expediente versionado de Proyecta | Vista reconciliada con enlaces a sus fuentes; no reemplaza las fuentes originales |

El expediente marcará el nivel de certeza de cada componente: **confirmado por código**, **confirmado por prueba**, **declarado en fuente**, **inferido** o **pendiente de validar**. Las inferencias no deben presentarse como trabajo realizado.

## Flujo de importación

1. Seleccionar el proyecto destino de Proyecta o crear uno nuevo.
2. Añadir cada fuente por separado: proveedor/espacio, nombre del proyecto, enlace cuando exista, intervalo o chats seleccionados, y repositorio/organización asociados.
3. Obtener contenido mediante una vía explícita admitida por esa fuente: prompt de extracción copiado en el proyecto de IA, archivo que el usuario seleccionó, documento compartido, conexión oficial con permisos limitados o datos de GitHub.
4. Convertir el material a un formato normalizado de importación. Cada elemento lleva tipo, texto, fuente, referencia, fecha, nivel de certeza y, si aplica, evidencia técnica.
5. Comparar con el expediente actual y mostrar diferencias: nuevo, actualizado, duplicado, contradictorio o sin confirmar.
6. Permitir aceptar, editar u omitir cada elemento. No reemplazar silenciosamente estado o decisiones existentes.
7. Guardar un snapshot versionado y generar los documentos actualizados.
8. Crear o actualizar tareas del backlog solo después de la revisión; cada tarea debe tener alcance y criterio de aceptación.

La deduplicación debe conservar cambios históricos: una secuencia A→B→A es válida si representa una reversión posterior. Cada importación mantiene su fecha y referencia para auditar cómo cambió el expediente.

## Adaptadores por fuente

### ChatGPT Personal

- Permitir el flujo guiado por prompt y la importación de un archivo seleccionado por el usuario.
- Aceptar exportación de datos personales cuando el usuario la solicite; filtrar por proyecto/conversaciones seleccionadas y normalizar antes de guardar.
- No almacenar la exportación íntegra por defecto. Conservar solo elementos aceptados y metadatos mínimos de procedencia.

### ChatGPT Business / Work

- Ofrecer prompt de extracción y carga/pegado de respuesta estructurada dentro del proyecto de ChatGPT elegido.
- Permitir referencias a proyectos o conversaciones compartidas a las que la persona ya tenga acceso.
- No asumir que Proyecta puede leer el historial del espacio ni importar una exportación general. La documentación actual de OpenAI indica que la exportación autoservicio no está disponible en ChatGPT Business; los historiales individuales tampoco son visibles automáticamente para otros miembros.
- Si aparece una API o conexión oficial habilitada por el workspace, implementarla como adaptador optativo, con permiso y alcance explícitos.

### Codex Cloud y repositorios remotos

- Vincular tarea Cloud con repositorio, rama, commit y PR cuando la información esté disponible.
- Priorizar GitHub como fuente verificable del código y del trabajo integrado; obtener acceso mediante una app/API oficial de lectura con permisos mínimos.
- En la primera entrega, admitir referencias y reportes de tarea proporcionados por el usuario/agente. No depender de endpoints privados ni de cookies del navegador.
- Más adelante, añadir sincronización de estado de PR, commits y ejecuciones de CI mediante GitHub OAuth/App y webhooks cuando sea necesario.

### Claude / Claude Code y otros agentes

- Mantener el formato normalizado de intercambio y los perfiles de fuente existentes.
- Producir prompts de captura compatibles y recibir resúmenes estructurados con fuente y fecha.
- Usar MCP local para entregar el expediente al agente con alcance fijado a un proyecto. Las conexiones de cuenta a nube son adaptadores independientes, no prerrequisito del núcleo.

## Documentos generados

Al menos un paquete de contexto en Markdown, regenerable y versionado, con:

1. **Resumen ejecutivo:** objetivo, estado, último avance y siguiente paso.
2. **Diseño funcional:** usuarios, flujos, alcance, reglas y criterios de aceptación.
3. **Diseño técnico:** arquitectura, stack, módulos/modelos/componentes, integraciones, repositorio, ramas y entornos.
4. **Matriz de avance:** componente, nivel/estado, evidencia, fecha, fuente y brecha restante.
5. **Backlog priorizado:** esperado, dependencias, aceptación, responsable/agente sugerido y estado.
6. **Decisiones y riesgos:** decisiones vigentes, alternativas descartadas, contradicciones y preguntas pendientes.
7. **Validación y entrega:** pruebas, resultados, PRs, despliegues y enlaces a evidencia.
8. **Prompt de continuidad:** instrucciones compactas para retomar la siguiente tarea en Codex, Claude Code u otro agente.

Los documentos deben indicar fecha de corte y commit revisado. Deben poder exportarse como Markdown y ZIP. El usuario elige si se guardan localmente, en GitHub o en Drive; el sistema no debe copiar documentación a Drive por defecto.

## Interfaz de trabajo

- Acciones visibles en la ficha: **Importar contexto**, **Revisar diferencias**, **Generar expediente**, **Planificar siguiente desarrollo** y **Continuar desarrollo**.
- Mostrar avance por fases y por componentes, separado del estado general del proyecto.
- Cada cifra o estado derivado debe abrir su evidencia y fuente.
- El Asesor de skills debe sugerir skills para planificar, implementar, revisar o probar; explicar el motivo y permitir seleccionar alternativas.
- Mantener una interfaz de tablero/editor de trabajo convencional. No usar metáforas o elementos tipo juego.

## Seguridad y privacidad

- Prohibido solicitar o guardar contraseñas, cookies o tokens en texto plano dentro de SQLite o expedientes.
- Preferir OAuth/credenciales almacenadas en el almacén seguro del sistema, con permisos de solo lectura en la fase de análisis.
- Mantener datos locales por defecto y permitir borrar fuente, snapshot y artefactos importados.
- No rastrear directorios o historiales completos. El usuario elige proyecto, fuente y alcance.
- Previsualizar antes de importar; registrar procedencia y quién aprobó los cambios.
- Separar los permisos para leer contexto, leer repositorio, crear rama/PR y desplegar. La lectura no autoriza escritura ni publicación.

## Entrega por fases

### Fase A — Expediente y captura revisada

- Formato normalizado de intercambio con procedencia por elemento.
- Prompts de captura para ChatGPT Personal/Business/Work, Codex Cloud y Claude.
- Importación de archivo/resumen seleccionado, revisión de diferencias e historial versionado.
- Generación del paquete Markdown de contexto y backlog.
- GitHub continúa como enlace manual; no hay OAuth ni lectura automática en esta fase.

### Fase B — Lectura técnica de GitHub

- Conexión oficial de solo lectura.
- Capturar repositorio, ramas, commits, PRs, etiquetas y estado de CI.
- Comparar los reportes de IA contra el código y los resultados de pruebas.
- Mantener repositorio canónico por proyecto y múltiples repositorios/componentes cuando aplique.

### Fase C — Continuidad de ejecución

- Adaptadores locales para iniciar y reanudar Codex CLI y Claude Code.
- Flujo de trabajo basado en objetivo → plan → tareas → cambio → revisión → pruebas → PR.
- Vista de logs, diff, checkpoints y resultados.
- Aprobación explícita para acciones de escritura, publicación o despliegue.
- gstack y otros conjuntos de workflows se registran como opciones del Asesor; Proyecta mantiene un adaptador de ejecución independiente.

## Criterios de aceptación

- Un usuario puede incorporar contexto de al menos dos fuentes al mismo proyecto y ver su procedencia.
- Un conflicto entre el resumen importado y el expediente vigente se muestra antes de guardar.
- Una afirmación de IA no eleva por sí sola un componente a “implementado” o “probado”.
- El expediente generado incluye diseño, estado técnico, brechas, backlog priorizado, repositorio/commit y pruebas disponibles.
- Una actualización genera diferencias respecto al snapshot anterior y conserva la historia.
- El proceso no requiere credenciales de ChatGPT pegadas en Proyecta ni cookies del navegador.
- Las funciones de escritura, merge y despliegue están desactivadas durante la importación y requieren permisos separados en fases posteriores.

## Hechos de producto y decisiones de diseño

- Los proyectos de ChatGPT agrupan chats, archivos e instrucciones de proyecto: <https://help.openai.com/en/articles/10169521-projects-in-chatgpt>.
- ChatGPT permite exportar datos de cuentas personales elegibles; la exportación autoservicio no está disponible en los espacios ChatGPT Business/Enterprise: <https://help.openai.com/en/articles/7260999-exporting-your-chatgpt-history-and-data>.
- En ChatGPT Business, cada miembro tiene su historial privado y los otros miembros no lo ven automáticamente: <https://help.openai.com/en/articles/8798634-managing-data-sharing-and-privacy-in-chatgpt-business>.
- Decisión de diseño para Proyecta: el núcleo no depende de scraping o APIs no documentadas; usa capturas explícitas y adaptadores oficiales cuando estén disponibles.
- Supuesto actual: “proyectos en Cloud” incluye tareas/proyectos de Codex Cloud. Si se refiere a otro servicio, se agrega como adaptador con el mismo contrato, sin cambiar el modelo de expediente.
