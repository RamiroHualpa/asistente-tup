"""
Configuración local del asistente.

Vive en la carpeta personal (`~/.asistente-tup/config.json`), no junto al código:
el código se comparte entre tutores y las rutas de uno no son las de otro.

    {
      "carpeta_trabajo":  "C:/Users/tutor/Documents/Asistente TUP",
      "carpeta_informes": "C:/Users/tutor/Documents/Asistente TUP/Informes"
    }

- `carpeta_trabajo`: donde el agente trabaja, recibe los archivos que se suben y deja
  lo que produce. Si tiene su propio `.claude/skills/`, esas skills también se cargan.
- `carpeta_informes`: los PDF que la skill del campus genera en `~/.moodle-skill/salidas`
  se copian acá al terminar cada tarea, para no tener que ir a buscarlos.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
CONFIG_DIR = HOME / ".asistente-tup"
CONFIG_FILE = CONFIG_DIR / "config.json"
LOG_FILE = CONFIG_DIR / "asistente.log"

CAMPUS_SKILL = HOME / ".claude" / "skills" / "tup-campus-navigator"

PUERTO = 8790


def moodle_skill_dir() -> Path:
    """
    Raíz (flat, legacy) de la skill del campus: ``~/.moodle-skill``. Sigue existiendo
    como función (no constante) porque varias cosas cuelgan de ella, pero para leer
    datos del tutor lo que hay que usar es `_tenant_dir()` / `salidas_campus()` /
    `mis_datos_path()`, que resuelven bajo el tenant activo.
    """
    return HOME / ".moodle-skill"


def _tenant_dir() -> Path:
    """
    Carpeta del tenant activo ahora mismo: `~/.moodle-skill/<tenant_activo()>/`.
    Función (no constante): el tutor puede tener más de un campus dado de alta
    (multi-tenant) y cambiar cuál está activo mientras este proceso sigue corriendo,
    así que no se puede fijar una sola vez al importar.
    """
    return moodle_skill_dir() / tenant_activo()


def salidas_campus() -> Path:
    """
    `salidas/` del tenant activo si ya existe (ahí escribe el MCP una vez migrado);
    si no, cae a la carpeta flat legacy `~/.moodle-skill/salidas` para no romper una
    instalación que todavía no tocó el layout por tenant.
    """
    por_tenant = _tenant_dir() / "salidas"
    if por_tenant.is_dir() or tenant_activo() != "tup":
        # Un campus que no es TUP nunca cae a la carpeta flat: es de TUP.
        return por_tenant
    return moodle_skill_dir() / "salidas"


def mis_datos_path() -> Path:
    """Igual que `salidas_campus()`: por tenant si existe, si no la flat legacy."""
    por_tenant = _tenant_dir() / "mis_datos.json"
    if por_tenant.is_file() or tenant_activo() != "tup":
        return por_tenant
    return moodle_skill_dir() / "mis_datos.json"


def tenant_activo() -> str:
    """
    Qué campus está activo ahora mismo, según `~/.moodle-skill/estado.json`
    (`tenant_activo`). Sin ese archivo, si no se puede leer/decodificar, o si su
    forma no es la esperada (no es un objeto, o `tenant_activo` no es un string),
    es una instalación de un solo campus: `"tup"`, el mismo default que usa la
    skill del campus.
    """
    archivo = moodle_skill_dir() / "estado.json"
    if archivo.is_file():
        try:
            estado = json.loads(archivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # ValueError cubre json.JSONDecodeError y UnicodeDecodeError (bytes no-UTF-8).
            estado = None
        if isinstance(estado, dict):
            tenant = estado.get("tenant_activo")
            if isinstance(tenant, str) and tenant.strip():
                return tenant
    return "tup"


def listar_campus() -> list[dict]:
    """Los campus dados de alta, desde `~/.moodle-skill/tenants.json`. Sin ese archivo, ninguno."""
    archivo = moodle_skill_dir() / "tenants.json"
    if archivo.is_file():
        try:
            datos = json.loads(archivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            datos = None
        if isinstance(datos, list):
            return [d for d in datos if isinstance(d, dict) and d.get("id")]
    return []


def set_tenant_activo(tenant_id: str) -> None:
    """Cambia el campus activo (mismo `estado.json` que lee la skill). Sólo ids dados de alta."""
    if tenant_id not in {c["id"] for c in listar_campus()}:
        raise ValueError(f"El campus «{tenant_id}» no está dado de alta.")
    archivo = moodle_skill_dir() / "estado.json"
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text(json.dumps({"tenant_activo": tenant_id}, ensure_ascii=False, indent=2), encoding="utf-8")


def campus_activo() -> dict | None:
    """La entrada de `tenants.json` del campus activo (`{id, nombre, url}`), si está registrada."""
    activo = tenant_activo()
    return next((c for c in listar_campus() if c["id"] == activo), None)


def catalogo_descubierto() -> dict:
    """
    Materias y comisiones del campus activo cuando no hay `mis_datos.json` (un campus
    recién agregado): salen de `aulas.json` / `comisiones.json`, lo que dejó
    `agregar_campus` al descubrirlas. Devuelve la misma forma que `mis_datos`
    (`{"cursos": [...]}`); comisiones = todas las del curso (no se conoce el reparto).
    """
    base = _tenant_dir()

    def leer_json(nombre: str) -> dict:
        try:
            d = json.loads((base / nombre).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return d if isinstance(d, dict) else {}

    comisiones = {
        m.get("course_id"): m.get("comisiones") or []
        for m in leer_json("comisiones.json").get("materias", [])
        if isinstance(m, dict)
    }
    cursos = []
    for m in leer_json("aulas.json").get("materias", []):
        if not isinstance(m, dict) or m.get("course_id") is None:
            continue
        cursos.append({
            "course_id": m["course_id"],
            "nombre": m.get("materia") or str(m["course_id"]),
            "comisiones_del_tutor": [
                {"group_id": g["group_id"], "comision": g.get("comision") or str(g["group_id"])}
                for g in comisiones.get(m["course_id"], [])
                if isinstance(g, dict) and "group_id" in g
            ],
            "tareas": [],
        })
    return {"cursos": cursos}


def _documentos() -> Path:
    # En un Linux en castellano la carpeta es «Documentos»; xdg-user-dir la sabe siempre.
    if shutil.which("xdg-user-dir"):
        try:
            ruta = subprocess.run(["xdg-user-dir", "DOCUMENTS"], capture_output=True, text=True, timeout=3).stdout.strip()
            if ruta and Path(ruta).is_dir() and Path(ruta) != HOME:
                return Path(ruta)
        except (OSError, subprocess.SubprocessError):
            pass
    for nombre in ("Documents", "Documentos"):
        if (HOME / nombre).is_dir():
            return HOME / nombre
    return HOME


def leer() -> dict:
    cfg: dict = {}
    if CONFIG_FILE.is_file():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            cfg = {}
    trabajo = Path(cfg.get("carpeta_trabajo") or _documentos() / "Asistente TUP").expanduser()
    informes = Path(cfg.get("carpeta_informes") or trabajo / "Informes").expanduser()
    return {"carpeta_trabajo": trabajo, "carpeta_informes": informes}


def guardar(carpeta_trabajo: str, carpeta_informes: str | None) -> dict:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    datos = {"carpeta_trabajo": carpeta_trabajo}
    if carpeta_informes:
        datos["carpeta_informes"] = carpeta_informes
    CONFIG_FILE.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    return leer()


def mcp_campus() -> dict | None:
    """
    La definición del MCP `moodle-tutor` tal como la tiene el Claude Code del tutor.

    Se reusa la suya y no una armada acá: ahí vive el `MOODLE_URL` (tup.sied o
    campustest) y el python del venv correcto. Si el tutor cambia de campus en su
    Claude Code, el asistente lo sigue sin tocar nada.
    """
    archivo = HOME / ".claude.json"
    if archivo.is_file():
        try:
            d = json.loads(archivo.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            d = {}
        srv = (d.get("mcpServers") or {}).get("moodle-tutor")
        if srv:
            return srv
        for proyecto in (d.get("projects") or {}).values():
            srv = (proyecto.get("mcpServers") or {}).get("moodle-tutor")
            if srv:
                return srv
    # Sin registro en Claude Code: se intenta con la instalación estándar de la skill.
    for py in (CAMPUS_SKILL / ".venv" / "Scripts" / "python.exe", CAMPUS_SKILL / ".venv" / "bin" / "python"):
        if py.is_file():
            return {"type": "stdio", "command": str(py), "args": [str(CAMPUS_SKILL / "mcp" / "server.py")]}
    return None


def skills_instaladas(trabajo: Path) -> set[str]:
    nombres: set[str] = set()
    for base in (HOME / ".claude" / "skills", trabajo / ".claude" / "skills", trabajo / ".agents" / "skills"):
        if base.is_dir():
            for d in base.iterdir():
                if (d / "SKILL.md").is_file():
                    nombres.add(d.name)
    return nombres


def claude_cli() -> str | None:
    return shutil.which("claude") or next(
        (str(p) for p in (HOME / ".local" / "bin" / "claude.exe", HOME / ".local" / "bin" / "claude") if p.is_file()),
        None,
    )


def es_windows() -> bool:
    return sys.platform.startswith("win") or os.name == "nt"
