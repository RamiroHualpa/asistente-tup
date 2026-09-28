# Asistente TUP

Las skills de Claude Code con botones, para quien no usa la consola.

La persona elige qué quiere hacer en un menú («¿Qué me falta corregir?», «Armar una
rúbrica nueva», «Convertir un apunte en página de estudio»…), completa un formulario
corto y mira los pasos en castellano mientras Claude trabaja. Cuando Claude necesita
una decisión, aparece como botones. Antes de escribir en el campus, aparece una tarjeta
roja con la nota o el texto, editable, y no pasa nada sin «Confirmar». Los archivos que
se generan quedan listados con un botón «Abrir».

Además, cada tutor puede armar **sus propias acciones** (sección «Mis acciones») y trabajar con **más de un campus Moodle**. Cubre las cuatro skills: `tup-campus-navigator`, `rubrica-builder`,
`apunte-interactivo` y `tutorial-video-agente`.

## Para usarlo

**Paso a paso con capturas: [GUIA.md](GUIA.md)** (también está dentro del asistente,
en el botón «Ayuda»).

1. Tener **Claude Code** instalado y con la sesión iniciada (abrirlo una vez).
2. Tener **Python 3.10+**.
3. Bajar este repo (botón verde **Code → Download ZIP**) y descomprimirlo.
4. Abrirlo:
   - **Windows:** doble clic en `Instalar.bat` (una sola vez) y después en `Abrir asistente.bat`.
   - **Mac:** doble clic en `Abrir asistente.command` (la primera vez se instala solo).
   - **Linux:** `./abrir.sh` (la primera vez se instala solo).

Se abre el navegador en `http://127.0.0.1:8790`. Para cerrarlo: botón «Cerrar
asistente», arriba a la derecha.

No hace falta API key: usa la sesión de Claude Code de cada uno, igual que la terminal.
Tampoco hace falta Node.

## Qué necesita de cada skill

La pantalla «¿Está todo listo?» (arriba a la derecha) revisa todo y dice qué falta:

- **Campus**: la skill `tup-campus-navigator` instalada y configurada. TUP es el campus por
  omisión (`~/.moodle-skill`, con la URL del `moodle-tutor` de `~/.claude.json`); desde el
  botón **Campus** se pueden **agregar otros** (el asistente guarda sus datos en
  `~/.asistente-tup/campus/<id>/` y arranca el MCP de la skill —sin modificarla— con la
  carpeta y la URL del campus activo), cambiar de campus y **elegir cuáles son las
  materias y comisiones propias** de cada uno (`mis_datos.json`). De ahí salen los
  desplegables de materia, comisión y tarea.
- **Rúbricas, apuntes, videos**: la skill instalada en `~/.claude/skills/` o en la
  carpeta de trabajo (`.claude/skills/`).
- **Videos**, además: `ffmpeg` (Windows: `winget install Gyan.FFmpeg`; en Linux también
  `xdotool` y `wmctrl`). Si falta, la sección aparece deshabilitada con el comando para
  instalarlo.

## Carpetas

Se configuran desde «¿Está todo listo?» y se guardan en `~/.asistente-tup/config.json`
(fuera de esta carpeta, porque las rutas de cada uno son distintas):

- **Carpeta de trabajo**: donde Claude trabaja, donde caen los archivos que se suben
  (`Subidos/<fecha>/`) y donde deja lo que produce (`TPs_rubrica/`, `Apuntes/`…).
  Por omisión, `Documentos/Asistente TUP`.
- **Carpeta de informes**: los PDF que la skill del campus genera en
  `~/.moodle-skill/salidas` se copian acá al terminar cada tarea.

## Cómo está armado

```
backend/
  app.py      FastAPI: sirve la pantalla y la API. Escucha SÓLO en 127.0.0.1.
  agente.py   La sesión con Claude (Agent SDK), el freno de escritura y la traducción de pasos.
  recetas.py  El catálogo: cada acción del menú, su formulario y el pedido que recibe Claude.
  config.py   Carpetas, detección de skills, y los campus (registro, activo, «Mis datos», MCP por campus).
  acciones.py Acciones propias de cada tutor (~/.asistente-tup/acciones.json): validación y persistencia.
  alta_campus.py  Prueba de login y descubrimiento de un campus nuevo (corre con el Python de la skill).
web/          HTML + CSS + JS sin build. Misma piel que el panel de tup-campus-navigator.
```

**Sumar una acción** = agregar un dict en `RECETAS` (`backend/recetas.py`). El
formulario se arma solo a partir de `campos`.

**El freno de escritura lo aplica el harness, no el prompt.** `can_use_tool` corre antes
de cada tool: las que escriben en el campus (`cargar_nota`, `responder_mensaje`,
`responder_foro`, `crear_discusion`, `confirmar_cola`, `corregir_con_active_ia`) y
cualquier tool del MCP con un parámetro `confirmado` frenan hasta el OK en pantalla. Los
archivos sólo se escriben dentro de la carpeta de trabajo. Sólo se conecta el MCP del
campus (`strict_mcp_config`): los demás servidores que cada uno tenga en su Claude Code
no entran, porque el freno no conoce sus escrituras.

**Las preguntas de Claude son botones.** Cuando una skill llama a `AskUserQuestion`, el
asistente la intercepta, muestra las opciones y devuelve la elección en el campo
`answers` de la tool.

Relación con el panel de `tup-campus-navigator`: comparte el mecanismo (Agent SDK +
freno en `can_use_tool`) y la piel, pero no toca ese repo. El panel arranca en un chat y
cubre sólo el campus. Este arranca en un menú guiado y cubre las cuatro skills.

Log: `~/.asistente-tup/asistente.log`.
