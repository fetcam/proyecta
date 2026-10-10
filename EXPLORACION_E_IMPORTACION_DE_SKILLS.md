# Exploración e importación de skills por plataforma

## Objetivo

Evitar que la persona tenga que enumerar manualmente las skills locales ya instaladas. Proyecta debe detectar las ubicaciones conocidas del equipo, catalogar sus metadatos y agrupar las skills por plataforma. Para catálogos alojados en la nube, debe ofrecer un flujo de importación desde un paquete descargado cuando el producto permita descargarlo.

El catálogo de Proyecta es una vista local de referencia y recomendación. No sustituye los catálogos originales ni ejecuta, instala, sincroniza o cambia permisos de skills.

## Disponibilidad por plataforma

| Plataforma | Descubrimiento/importación en Proyecta | Alcance y límites |
|---|---|---|
| Codex | Explorar `~/.codex/skills`, `~/.agents/skills` y las rutas locales de proyecto reconocidas | Leer metadatos `SKILL.md`; clasificar como Codex o compartida según la fuente configurada |
| Claude Code | Explorar `~/.claude/skills` y fuentes locales de proyecto que la persona agregue | Leer metadatos `SKILL.md`; no leer credenciales ni archivos de configuración privados |
| ChatGPT Business / Work | Importar una carpeta local con el paquete de skill descargado desde el catálogo del producto, cuando la opción de descarga esté disponible | No hay directorio local de cuenta que Proyecta pueda recorrer. Las skills permanecen administradas en ChatGPT; la importación local no equivale a sincronización |
| ChatGPT Personal | Permitir catalogar una carpeta descargada/importada y etiquetarla para este entorno si la skill está disponible para esa cuenta | No asumir que Personal dispone del catálogo empresarial ni leer la cuenta automáticamente |
| Claude web u otras plataformas | Importación desde una carpeta local elegida y etiqueta manual del entorno | Sin descubrimiento automático de cuentas o historiales |

Los directorios de Codex y Claude Code son detectables en el disco porque sus skills se representan como carpetas con `SKILL.md`. Los skills de ChatGPT se administran en el catálogo de Skills del producto. ChatGPT permite instalar, crear, compartir y, para administradores elegibles, descargar skills; no documenta una ruta de instalación local de la cuenta. Proyecta no debe inventar rutas como `~/.chatgpt/skills` ni escanear carpetas arbitrarias con ese supuesto.

## Flujo de usuario

1. Al abrir el Asesor, Proyecta comprueba únicamente las rutas locales conocidas y muestra una lista por plataforma.
2. La persona puede importar y escanear cada ruta detectada con una acción. Para una carpeta ya agregada, puede actualizar el catálogo con **Escanear fuentes habilitadas**.
3. Para ChatGPT u otra fuente sin ruta local, la persona descarga el paquete desde el producto cuando esté disponible, lo extrae en una carpeta local y la selecciona en Proyecta. Al agregar la carpeta, elige la plataforma a la que corresponde.
4. Proyecta muestra el nombre, descripción, función, etiquetas, plataforma, fuente, ruta, última modificación y huella, agrupados por plataforma. Puede listar como relación tentativa otras skills que compartan etiquetas; debe rotularlo como coincidencia, no como dependencia confirmada. Las dependencias explícitas solo se muestran si aparecen en metadatos admitidos.
5. La persona revisa las coincidencias, activa o desactiva fuentes, pide sugerencias y selecciona qué skills asociar a cada tarea.

## Metadatos y relaciones

El lector indexa únicamente el encabezado YAML de `SKILL.md`: `name`, `description` y `tags`. La descripción debe explicar qué hace la skill; el nombre y las etiquetas ayudan a entender para qué tipo de trabajo sirve. El catálogo conserva fuente, plataforma, ruta relativa, fecha de modificación y huella SHA-256 para detectar cambios entre escaneos.

La descripción del skill es contenido declarado por su autor, no una verificación independiente. Proyecta debe separar:

- **Qué declara hacer:** nombre y descripción del encabezado.
- **Para qué tarea parece pertinente:** coincidencias explicables con objetivo, aceptación y etapa.
- **Con qué otras skills está relacionado:** solo relaciones explícitas encontradas en metadatos estructurados o un manifiesto admitido; en caso contrario, indicar que no se detectaron relaciones declaradas.
- **Compatibilidad:** plataforma asignada a la fuente y cualquier restricción declarada. No asumir que compartir formato `SKILL.md` hace una skill compatible con todos los clientes.

En esta primera iteración no se lee el cuerpo de instrucciones, scripts, credenciales ni datos de conversación. No se ejecutan los scripts de una skill. Si un paquete declara archivos relacionados, Proyecta puede mostrar sus nombres y rutas relativas como referencias, sin abrirlos.

## Seguridad y límites

- No recorrer el disco completo. Comprobar solo rutas conocidas y fuentes agregadas explícitamente.
- No seguir enlaces simbólicos ni leer archivos fuera de la fuente elegida.
- Limitar tamaño, número de skills y longitud del encabezado.
- No guardar contraseñas, cookies, tokens ni contenido completo de `SKILL.md`.
- Tratar los metadatos como texto no confiable y escapar su salida en la interfaz.
- La importación es local y revisable; no instala skills en Codex, Claude o ChatGPT.
- Mantener GitHub como fuente técnica del código de Proyecta; el inventario de skills no reclama que una skill esté instalada o habilitada en un servicio remoto si solo se importó una copia local.

## Criterios de aceptación

1. Una persona puede descubrir y catalogar fuentes locales convencionales de Codex y Claude Code sin enumerar cada skill.
2. El catálogo agrupa las skills por plataforma y muestra explicación, etiquetas, fuente, ruta, huella y estado de cambio.
3. Una carpeta de skill descargada puede agregarse y asociarse a ChatGPT Personal o Business sin afirmar que Proyecta leyó la cuenta.
4. La interfaz indica cuándo la fuente es un directorio local descubierto, una carpeta importada o una fuente todavía no disponible.
5. Las sugerencias presentan motivo, compatibilidad y opciones de usar, inspeccionar, elegir otra u omitir.
6. Proyecta no instala, ejecuta ni sincroniza automáticamente skills.
7. Pruebas verifican rutas conocidas, metadatos acotados, IDs estables, limpieza de asociaciones y ausencia de rutas inventadas para cuentas ChatGPT.

## Referencias de producto

- OpenAI Help Center, [Skills in ChatGPT](https://help.openai.com/en/articles/20001066-skills-in-chatgpt): catálogo de Skills, disponibilidad por plan, instalación, carga/descarga y administración desde ChatGPT.
- OpenAI Help Center, [ChatGPT Business release notes](https://help.openai.com/en/articles/11391654-chatgpt-business-release-notes): Skills y Work/desktop según disponibilidad del producto.
- OpenAI Developers, [Skills](https://developers.openai.com/api/docs/guides/tools-skills): formato de paquete de skill y manifiesto `SKILL.md`.
- Anthropic, [Claude Skills](https://www.anthropic.com/research/skills): skills como flujos reutilizables.

La disponibilidad de interfaz y planes puede variar por cuenta, espacio de trabajo y despliegue del producto. La integración local de Proyecta se basa en el directorio y paquete observables, no en inferencias sobre la cuenta.
