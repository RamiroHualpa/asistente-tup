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


CAMPUS_DIR = CONFIG_DIR / "campus"
CAMPUS_REGISTRO = CONFIG_DIR / "campus.json"

TUP_ID = "tup"
TUP_NOMBRE = "TUP (UTN)"
TUP_URL = "https://tup.sied.utn.edu.ar"

# Variables de entorno con las que la skill del campus (sin modificar) elige a qué campus
# y con qué credenciales opera: `MOODLE_SKILL_HOME` (carpeta de datos) y las del `.env`.
_ENTORNO_CAMPUS = ("MOODLE_URL", "MOODLE_USER", "MOODLE_PASS", "ACTIVEIA_USER", "ACTIVEIA_PASS", "MOODLE_SKILL_HOME")


# --------------------------------------------------------------------------- #
# Campus (multi-campus, todo del lado del asistente)
#
# La skill del campus es de un solo campus por proceso: toma la carpeta de datos de
# `MOODLE_SKILL_HOME` y la URL/credenciales del entorno o de su `.env`. El asistente no
# la toca: guarda acá los campus dados de alta y, en cada tarea, arranca el MCP con el
# entorno del campus activo. TUP es el de siempre (la carpeta `~/.moodle-skill` y la URL
# de la config de Claude Code) y no se guarda en el registro.
# --------------------------------------------------------------------------- #


def moodle_skill_dir() -> Path:
    """Carpeta de datos de la skill del campus para TUP (el campus de siempre): `~/.moodle-skill`."""
    return HOME / ".moodle-skill"


def _registro() -> dict:
    """`~/.asistente-tup/campus.json`: `{"activo": id, "campus": [{id, nombre, url}]}` (sin TUP)."""
    try:
        d = json.loads(CAMPUS_REGISTRO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def _guardar_registro(datos: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CAMPUS_REGISTRO.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


def _url_tup() -> str:
    return ((mcp_campus() or {}).get("env") or {}).get("MOODLE_URL") or TUP_URL


def listar_campus() -> list[dict]:
    """TUP primero (siempre) y después los campus dados de alta, cada uno `{id, nombre, url}`."""
    extra = [
        {"id": c["id"], "nombre": c.get("nombre") or c["id"], "url": c.get("url", "")}
        for c in (_registro().get("campus") or [])
        if isinstance(c, dict) and isinstance(c.get("id"), str) and c["id"] and c["id"] != TUP_ID
    ]
    return [{"id": TUP_ID, "nombre": TUP_NOMBRE, "url": _url_tup()}, *extra]


def tenant_activo() -> str:
    """Campus activo; si el guardado ya no existe (o no hay), TUP."""
    activo = _registro().get("activo")
    return activo if isinstance(activo, str) and activo in {c["id"] for c in listar_campus()} else TUP_ID


def campus_activo() -> dict:
    activo = tenant_activo()
    return next(c for c in listar_campus() if c["id"] == activo)


def datos_dir(tenant_id: str | None = None) -> Path:
    """Carpeta de datos (`.env`, `mis_datos.json`, `salidas/`) de un campus."""
    tid = tenant_id or tenant_activo()
    return moodle_skill_dir() if tid == TUP_ID else CAMPUS_DIR / tid


def salidas_campus() -> Path:
    return datos_dir() / "salidas"


def mis_datos_path() -> Path:
    return datos_dir() / "mis_datos.json"


def set_tenant_activo(tenant_id: str) -> None:
    """Cambia el campus activo. Sólo ids dados de alta."""
    if tenant_id not in {c["id"] for c in listar_campus()}:
        raise ValueError(f"El campus «{tenant_id}» no está dado de alta.")
    _guardar_registro({**_registro(), "activo": tenant_id})


def registrar_campus(tenant_id: str, nombre: str, url: str) -> None:
    """Da de alta un campus (sin activarlo). Rechaza TUP y los ids ya usados."""
    if tenant_id.lower() in {c["id"].lower() for c in listar_campus()}:
        raise ValueError(f"Ya existe un campus «{tenant_id}».")
    reg = _registro()
    reg["campus"] = [*(reg.get("campus") or []), {"id": tenant_id, "nombre": nombre, "url": url}]
    _guardar_registro(reg)


def escribir_env(tenant_id: str, valores: dict[str, str]) -> Path:
    """
    Guarda las credenciales del campus en su `.env` (el mismo formato que lee la skill).
    En Windows el `chmod 600` sólo marca el archivo como de sólo lectura; en Linux/macOS sí
    restringe el acceso.
    """
    carpeta = datos_dir(tenant_id)
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / ".env"
    cuerpo = "# Credenciales del campus. NO subir a git.\n" + "".join(f"{k}={v}\n" for k, v in valores.items() if v)
    ruta.write_text(cuerpo, encoding="utf-8")
    try:
        os.chmod(ruta, 0o600)
    except OSError:
        pass
    return ruta


def mcp_campus_activo() -> dict | None:
    """
    La definición del MCP `moodle-tutor` para el campus activo. TUP: la de siempre. Otro
    campus: la misma skill, con su carpeta de datos y su URL en el entorno (las credenciales
    las lee la skill del `.env` de esa carpeta, así no viajan por argumentos).
    """
    base = mcp_campus()
    if not base:
        return None
    activo = campus_activo()
    if activo["id"] == TUP_ID:
        return base
    entorno = {k: v for k, v in (base.get("env") or {}).items() if k not in _ENTORNO_CAMPUS}
    entorno.update({"MOODLE_SKILL_HOME": str(datos_dir(activo["id"])), "MOODLE_URL": activo["url"]})
    return {**base, "env": entorno}


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
