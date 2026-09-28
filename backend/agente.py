"""
La sesión con Claude detrás de cada tarea.

Mismo mecanismo que el panel de `tup-campus-navigator` (Agent SDK sobre el Claude
Code del propio tutor: sin API key), con dos diferencias pensadas para quien no
usa la consola:

1. **Las preguntas del agente se contestan con botones.** Cuando una skill necesita
   una decisión (p. ej. rubrica-builder en modo CURAR), llama a `AskUserQuestion`.
   El asistente la intercepta en `can_use_tool`, muestra las opciones en pantalla y
   devuelve las respuestas como `answers` del input, que es exactamente el hueco
   que la tool deja para eso.

2. **Los pasos se cuentan en castellano.** Cada tool que corre se traduce a una
   frase ("Revisando entregas en el campus"), no a su nombre técnico.

El freno de escritura es el mismo que el del panel y lo aplica el harness: ninguna
escritura al campus corre sin un OK explícito en pantalla.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    PermissionResultAllow,
    PermissionResultDeny,
    ResultMessage,
    ToolUseBlock,
)

from . import config

# --------------------------------------------------------------------------- #
# Freno de escritura
# --------------------------------------------------------------------------- #

# Escriben en el campus: irreversibles desde la API.
TOOLS_QUE_ESCRIBEN = {
    "cargar_nota",
    "confirmar_cola",
    "responder_mensaje",
    "responder_foro",
    "crear_discusion",
    "corregir_con_active_ia",
}
# Tocan la configuración local de la skill: no dañan el campus pero no deberían pasar calladas.
TOOLS_SENSIBLES = {"configurar", "actualizar_skill", "guardar_mis_datos", "guardar_clickup_id", "guardar_accion"}
TOOLS_DE_ARCHIVO = {"Write", "Edit", "NotebookEdit", "MultiEdit"}


def _corto(tool: str) -> str:
    return tool.rsplit("__", 1)[-1]


def _es_escritura(tool: str, entrada: dict[str, Any]) -> bool:
    corto = _corto(tool)
    if corto in TOOLS_QUE_ESCRIBEN or corto in TOOLS_SENSIBLES:
        return True
    # La skill marca sus escrituras con `confirmado`: una tool nueva queda frenada sola.
    return tool.startswith("mcp__") and "confirmado" in entrada


def _servidor_acciones():
    """
    Herramienta propia del asistente (corre en este mismo proceso): deja que Claude guarde una
    acción propia. La persona ve y confirma lo que se va a guardar antes de que se ejecute
    (está en TOOLS_SENSIBLES) y `acciones.guardar` valida todo de nuevo.
    """
    from claude_agent_sdk import create_sdk_mcp_server, tool

    from . import acciones

    esquema = {
        "type": "object",
        "properties": {
            "titulo": {"type": "string", "description": "Nombre corto de la acción (hasta 70 caracteres)."},
            "bajada": {"type": "string", "description": "Descripción de una frase."},
            "resultado": {"type": "string", "description": "Qué va a obtener la persona al usarla."},
            "campos": {
                "type": "array",
                "description": "Los datos que se piden cada vez que se usa la acción.",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "Identificador en minúsculas, sin espacios (ej. materia)."},
                        "tipo": {"type": "string", "enum": list(acciones.TIPOS)},
                        "etiqueta": {"type": "string"},
                        "opcional": {"type": "boolean"},
                        "ayuda": {"type": "string"},
                        "opciones": {"type": "array", "items": {"type": "string"}, "description": "Sólo para tipo opcion."},
                    },
                    "required": ["id", "tipo", "etiqueta"],
                },
            },
            "pedido": {"type": "string", "description": "La instrucción completa, con {id} donde va cada dato."},
        },
        "required": ["titulo", "bajada", "pedido"],
    }

    @tool("guardar_accion", "Guarda una acción propia de la persona (un botón nuevo en «Mis acciones»).", esquema)
    async def guardar_accion(args: dict[str, Any]) -> dict[str, Any]:
        try:
            g = acciones.guardar(args)
        except ValueError as e:
            return {"content": [{"type": "text", "text": f"No se guardó: {e} Corregilo y volvé a llamar."}], "is_error": True}
        return {"content": [{"type": "text", "text": f"Listo: la acción «{g['titulo']}» quedó guardada en «Mis acciones»."}]}

    return create_sdk_mcp_server("asistente", tools=[guardar_accion])


def _carpetas_escribibles(trabajo: Path) -> list[Path]:
    return [
        p.resolve()
        for p in (trabajo, config.moodle_skill_dir(), config.datos_dir(), config.CAMPUS_SKILL, Path(tempfile.gettempdir()))
        if p.exists()
    ]


def _dentro(ruta: str, bases: list[Path]) -> bool:
    try:
        destino = Path(ruta).expanduser().resolve()
    except (OSError, ValueError):
        return False
    return any(destino == b or b in destino.parents for b in bases)


# --------------------------------------------------------------------------- #
# Pasos en castellano
# --------------------------------------------------------------------------- #

PASOS = {
    "mis_datos": "Leyendo tus materias y comisiones",
    "guardar_accion": "Guardar esta acción en «Mis acciones»",
    "mapear_mis_datos": "Buscando tus materias y comisiones asignadas",
    "aulas": "Leyendo tus materias y comisiones",
    "mi_comision": "Mirando tu comisión",
    "descubrir_cursos": "Buscando tus materias en el campus",
    "descubrir_comisiones": "Buscando tus comisiones en el campus",
    "listar_tareas": "Listando las tareas de la materia",
    "pendientes_por_corregir": "Buscando entregas sin corregir",
    "sumario": "Contando entregas por tarea",
    "entregas_tarea": "Revisando quién entregó",
    "sin_entrar_al_aula": "Viendo quién no entra a la materia",
    "alumnos_en_riesgo": "Cruzando inactividad con entregas",
    "buscar_alumno": "Buscando al alumno",
    "ver_entrega": "Abriendo la entrega del alumno",
    "preparar_correccion": "Preparando la corrección",
    "siguiente_para_corregir": "Pasando a la siguiente entrega",
    "cargar_nota": "Cargando la nota en el campus",
    "confirmar_cola": "Cargando las notas en el campus",
    "mensajes_pendientes": "Revisando mensajes sin responder",
    "leer_mensajes": "Leyendo mensajes",
    "leer_conversacion": "Leyendo la conversación",
    "responder_mensaje": "Enviando la respuesta",
    "foros_pendientes": "Revisando los foros",
    "listar_foros": "Revisando los foros",
    "leer_foro": "Leyendo el foro",
    "leer_discusion": "Leyendo la discusión",
    "responder_foro": "Publicando en el foro",
    "informe_alumnos": "Armando el informe",
    "armar_informe": "Armando el informe en PDF",
    "informes_nexos": "Armando los informes para Tutores Nexo",
    "reporte_coordinacion": "Armando el panorama del curso",
    "demora_correccion": "Midiendo la demora de corrección",
    "auditar_aula": "Auditando el aula",
    "errores_frecuentes": "Buscando errores que se repiten",
    "corregir_con_active_ia": "Corrigiendo con Active-IA",
    "Skill": "Abriendo las instrucciones de la herramienta",
    "Read": "Leyendo archivos",
    "Glob": "Buscando archivos",
    "Grep": "Buscando dentro de archivos",
    "Write": "Guardando un archivo",
    "Edit": "Editando un archivo",
    "Bash": "Procesando",
    "PowerShell": "Procesando",
    "WebFetch": "Consultando una página web",
    "WebSearch": "Buscando en internet",
    "TodoWrite": "Organizando los pasos",
    "ToolSearch": "Preparando herramientas",
}


def _paso(tool: str, entrada: dict[str, Any]) -> str:
    corto = _corto(tool)
    texto = PASOS.get(corto)
    if texto is None:
        texto = "Consultando el campus" if tool.startswith("mcp__moodle-tutor__") else "Trabajando"
    if corto in {"Read", "Write", "Edit"} and entrada.get("file_path"):
        texto += f" · {Path(str(entrada['file_path'])).name}"
    return texto


# --------------------------------------------------------------------------- #
# Sesión
# --------------------------------------------------------------------------- #

INSTRUCCIONES = """\
Estás corriendo dentro del **Asistente TUP**, una pantalla con botones pensada para
docentes que no usan la consola. La persona eligió una acción de un menú y completó un
formulario; el pedido que recibís lo armó la pantalla.

Cómo trabajar acá:
- Hablá en castellano rioplatense, claro y sin jerga técnica. No muestres comandos, rutas
  de código ni nombres de tools salvo que te los pidan.
- Si necesitás que la persona elija algo, usá la herramienta AskUserQuestion con opciones
  concretas: en esta pantalla aparecen como botones. No termines el turno con una pregunta
  abierta si se puede plantear como opciones.
- Todo lo que escribe en el campus se frena y la persona lo confirma en pantalla: proponé,
  no preguntes "¿lo cargo?" en texto.
- Guardá los archivos que produzcas dentro de la carpeta de trabajo ({trabajo}), en la
  subcarpeta que indique el pedido.
- Terminá con un resumen corto: qué hiciste, qué encontraste y qué archivos quedaron
  (nombre del archivo). La pantalla ya muestra un botón para abrir cada archivo nuevo.
"""


@dataclass
class Sesion:
    id: str
    client: ClaudeSDKClient
    trabajo: Path
    pendientes: dict[str, asyncio.Future] = field(default_factory=dict)
    eventos: asyncio.Queue = field(default_factory=asyncio.Queue)
    ocupada: bool = False


SESIONES: dict[str, Sesion] = {}


def _opciones(holder: dict[str, Sesion | None], trabajo: Path) -> ClaudeAgentOptions:
    escribibles = _carpetas_escribibles(trabajo)

    async def esperar_respuesta(sesion: Sesion, evento: dict) -> dict:
        futuro: asyncio.Future = asyncio.get_running_loop().create_future()
        sesion.pendientes[evento["id"]] = futuro
        await sesion.eventos.put(evento)
        try:
            return await futuro
        finally:
            sesion.pendientes.pop(evento["id"], None)

    async def puede_usar(tool: str, entrada: dict[str, Any], contexto: Any):
        sesion = holder.get("s")
        tid = getattr(contexto, "tool_use_id", None) or str(uuid.uuid4())

        if tool == "AskUserQuestion" and sesion is not None:
            decision = await esperar_respuesta(
                sesion, {"tipo": "pregunta", "id": tid, "preguntas": entrada.get("questions") or []}
            )
            if not decision.get("ok"):
                return PermissionResultDeny(message="La persona prefirió no contestar.", interrupt=False)
            return PermissionResultAllow(updated_input={**entrada, "answers": decision.get("respuestas") or {}})

        if tool in TOOLS_DE_ARCHIVO:
            destino = entrada.get("file_path") or entrada.get("notebook_path") or ""
            if destino and not _dentro(str(destino), escribibles):
                return PermissionResultDeny(
                    message=f"El asistente sólo guarda archivos dentro de {trabajo}. Usá una subcarpeta de ahí.",
                    interrupt=False,
                )
            return PermissionResultAllow()

        if sesion is None or not _es_escritura(tool, entrada):
            return PermissionResultAllow()

        decision = await esperar_respuesta(
            sesion,
            {
                "tipo": "confirmacion",
                "id": tid,
                "tool": _corto(tool),
                "accion": _paso(tool, entrada),
                "irreversible": _corto(tool) in TOOLS_QUE_ESCRIBEN,
                "entrada": entrada,
            },
        )
        if decision.get("ok"):
            cambios = decision.get("entrada")
            if cambios and cambios != entrada:
                return PermissionResultAllow(updated_input=cambios)
            return PermissionResultAllow()
        return PermissionResultDeny(
            message=decision.get("motivo") or "La persona no confirmó la operación.", interrupt=False
        )

    mcp = {"asistente": _servidor_acciones()}
    campus = config.mcp_campus_activo()
    if campus:
        mcp["moodle-tutor"] = campus

    return ClaudeAgentOptions(
        cwd=str(trabajo),
        setting_sources=["user", "project"],
        mcp_servers=mcp,
        # Sólo el MCP del campus: el freno de arriba conoce sus escrituras, no las de
        # Notion o Drive que el tutor pueda tener enchufados en su Claude Code.
        strict_mcp_config=True,
        permission_mode="default",
        can_use_tool=puede_usar,
        include_partial_messages=True,
        system_prompt={
            "type": "preset",
            "preset": "claude_code",
            "append": INSTRUCCIONES.format(trabajo=trabajo),
        },
    )


async def abrir_sesion(trabajo: Path) -> Sesion:
    trabajo.mkdir(parents=True, exist_ok=True)
    holder: dict[str, Sesion | None] = {"s": None}
    client = ClaudeSDKClient(options=_opciones(holder, trabajo))
    await client.connect()
    sesion = Sesion(id=str(uuid.uuid4()), client=client, trabajo=trabajo)
    holder["s"] = sesion
    SESIONES[sesion.id] = sesion
    return sesion


async def cerrar_sesion(sid: str) -> None:
    sesion = SESIONES.pop(sid, None)
    if sesion is not None:
        for f in sesion.pendientes.values():
            if not f.done():
                f.set_result({"ok": False, "motivo": "Se cerró la tarea."})
        try:
            await sesion.client.disconnect()
        except Exception:
            pass


def responder(sid: str, evento_id: str, decision: dict) -> bool:
    sesion = SESIONES.get(sid)
    futuro = sesion.pendientes.get(evento_id) if sesion else None
    if futuro is None or futuro.done():
        return False
    futuro.set_result(decision)
    return True


def _delta(msg: Any) -> str | None:
    evento = getattr(msg, "event", None)
    if isinstance(evento, dict) and evento.get("type") == "content_block_delta":
        delta = evento.get("delta") or {}
        if delta.get("type") == "text_delta":
            return delta.get("text")
    return None


async def conversar(sesion: Sesion, prompt: str):
    """Manda el turno y va emitiendo eventos simples para la pantalla."""
    sesion.ocupada = True
    await sesion.client.query(prompt)

    async def bombear():
        try:
            async for msg in sesion.client.receive_response():
                d = _delta(msg)
                if d:
                    await sesion.eventos.put({"tipo": "texto", "delta": d})
                    continue
                if isinstance(msg, AssistantMessage):
                    for b in msg.content:
                        if isinstance(b, ToolUseBlock) and b.name != "AskUserQuestion":
                            await sesion.eventos.put(
                                {"tipo": "paso", "texto": _paso(b.name, b.input), "campus": b.name.startswith("mcp__")}
                            )
                    # Corte entre bloques de texto de mensajes distintos.
                    await sesion.eventos.put({"tipo": "corte"})
                elif isinstance(msg, ResultMessage):
                    if msg.is_error:
                        await sesion.eventos.put({"tipo": "error", "mensaje": str(msg.result or msg.subtype)})
                    await sesion.eventos.put({"tipo": "fin"})
                    return
        except Exception as exc:
            await sesion.eventos.put({"tipo": "error", "mensaje": _explicar_error(exc)})
            await sesion.eventos.put({"tipo": "fin"})

    tarea = asyncio.create_task(bombear())
    try:
        while True:
            evento = await sesion.eventos.get()
            yield evento
            if evento.get("tipo") == "fin":
                return
    finally:
        sesion.ocupada = False
        if not tarea.done():
            tarea.cancel()


def _explicar_error(exc: Exception) -> str:
    texto = str(exc)
    bajo = texto.lower()
    if "not found" in bajo and "claude" in bajo:
        return "No encontré Claude Code en esta computadora. Revisá la pantalla «¿Está todo listo?»."
    if "login" in bajo or "auth" in bajo or "401" in bajo:
        return "Claude Code no tiene la sesión iniciada. Abrí Claude Code una vez e iniciá sesión."
    return texto


def sse(evento: dict) -> str:
    return f"data: {json.dumps(evento, ensure_ascii=False, default=str)}\n\n"

