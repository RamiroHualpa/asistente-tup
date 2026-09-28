"""
Asistente TUP: las skills de Claude Code con botones, para quien no usa la consola.

Un solo proceso que sirve la pantalla y la API. Escucha SÓLO en 127.0.0.1: corre
con las credenciales del campus del tutor y puede escribir en él.

Arrancar:  .venv/Scripts/pythonw.exe -m backend.app   (o doble clic en «Abrir asistente.bat»)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import agente, config, recetas

RAIZ = Path(__file__).resolve().parent.parent
WEB = RAIZ / "web"

app = FastAPI(title="Asistente TUP", docs_url=None, redoc_url=None)
log = logging.getLogger("asistente")


# --------------------------------------------------------------------------- #
# Estado y catálogo
# --------------------------------------------------------------------------- #


def _mis_datos() -> dict:
    try:
        return json.loads(config.mis_datos_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _programas_faltantes(requiere: dict | None) -> list[str]:
    if not requiere:
        return []
    nombres = list(requiere.get("todos", []))
    if not config.es_windows():
        nombres += requiere.get("linux", [])
    return [n for n in nombres if shutil.which(n) is None]


@app.get("/api/estado")
async def estado():
    cfg = config.leer()
    instaladas = config.skills_instaladas(cfg["carpeta_trabajo"])
    datos = _mis_datos()
    campus = config.mcp_campus()
    chequeos = [
        {
            "id": "claude",
            "ok": bool(config.claude_cli()),
            "titulo": "Claude Code instalado",
            "si_falla": "Instalá Claude Code (claude.com/claude-code) y abrilo una vez para iniciar sesión.",
        },
        {
            "id": "campus",
            "ok": bool(campus),
            "titulo": "Conexión con el campus configurada",
            "detalle": (campus or {}).get("env", {}).get("MOODLE_URL", ""),
            "si_falla": "Instalá la skill tup-campus-navigator y seguí su instalación (install.sh).",
        },
        {
            "id": "mis_datos",
            "ok": bool(datos.get("cursos")),
            "titulo": "Tus materias y comisiones mapeadas",
            "detalle": ", ".join(c.get("nombre", "") for c in datos.get("cursos", [])),
            "si_falla": "Usá «Otra consulta sobre el campus» y escribí: «mapeá mis comisiones».",
        },
    ]
    skills = []
    for s in recetas.SKILLS:
        disponible = s["skill"] in instaladas
        faltan = _programas_faltantes(s.get("requiere"))
        if not disponible:
            motivo = f"La skill «{s['skill']}» no está instalada en esta computadora."
        elif faltan:
            motivo = f"Falta instalar {', '.join(faltan)}. {s['requiere']['como_instalar']}"
        else:
            motivo = ""
        skills.append({**s, "instalada": disponible, "bloqueada": bool(faltan), "motivo": motivo})
    return {
        "tutor": (datos.get("tutor") or {}).get("nombre", ""),
        "chequeos": chequeos,
        "skills": skills,
        "carpeta_trabajo": str(cfg["carpeta_trabajo"]),
        "carpeta_informes": str(cfg["carpeta_informes"]),
    }


@app.get("/api/campus")
async def campus():
    return {"campus": config.listar_campus(), "activo": config.tenant_activo()}


@app.get("/api/catalogo")
async def catalogo():
    datos = _mis_datos()
    cursos = [
        {
            "id": c["course_id"],
            "nombre": c.get("nombre", str(c["course_id"])),
            "comisiones": [
                {"id": g["group_id"], "nombre": g.get("comision", str(g["group_id"]))}
                for g in c.get("comisiones_del_tutor", [])
            ],
            "tareas": [{"id": t["assign_id"], "nombre": t.get("titulo", t["assign_id"])} for t in c.get("tareas", [])],
        }
        for c in datos.get("cursos", [])
        if "course_id" in c
    ]
    return {"recetas": recetas.RECETAS, "cursos": cursos}


class Carpetas(BaseModel):
    carpeta_trabajo: str
    carpeta_informes: str | None = None


@app.post("/api/config")
async def guardar_config(c: Carpetas):
    trabajo = Path(c.carpeta_trabajo).expanduser()
    if not trabajo.parent.exists():
        raise HTTPException(400, "Esa carpeta no existe.")
    trabajo.mkdir(parents=True, exist_ok=True)
    cfg = config.guardar(str(trabajo), c.carpeta_informes or None)
    return {k: str(v) for k, v in cfg.items()}


# --------------------------------------------------------------------------- #
# Archivos
# --------------------------------------------------------------------------- #

_NOMBRE_SEGURO = re.compile(r"[^\w.\- ()áéíóúñÁÉÍÓÚÑ]+")


@app.post("/api/subir")
async def subir(archivos: list[UploadFile] = File(...)):
    """Guarda lo que la persona elige en su carpeta de trabajo y devuelve las rutas."""
    destino = config.leer()["carpeta_trabajo"] / "Subidos" / datetime.now().strftime("%Y-%m-%d")
    destino.mkdir(parents=True, exist_ok=True)
    rutas = []
    for a in archivos:
        nombre = _NOMBRE_SEGURO.sub("_", Path(a.filename or "archivo").name).strip() or "archivo"
        ruta = destino / nombre
        n = 1
        while ruta.exists():
            ruta = destino / f"{Path(nombre).stem} ({n}){Path(nombre).suffix}"
            n += 1
        with ruta.open("wb") as f:
            shutil.copyfileobj(a.file, f)
        rutas.append({"nombre": ruta.name, "ruta": str(ruta)})
    return {"archivos": rutas}


_IGNORAR = {".git", ".venv", "node_modules", "__pycache__", ".claude", ".agents", "Subidos"}
_TOPE = 30_000
# La carpeta del propio asistente puede quedar adentro de la de trabajo: no es producto de una tarea.
_PROPIA = os.path.normcase(str(RAIZ.resolve()))


def _foto_archivos(bases: list[Path]) -> dict[str, float]:
    """mtime de cada archivo bajo las carpetas dadas. Sirve para saber qué produjo una tarea."""
    foto: dict[str, float] = {}
    pila = [b for b in bases if b.is_dir()]
    while pila and len(foto) < _TOPE:
        d = pila.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    if e.name in _IGNORAR or e.name.startswith("~$") or os.path.normcase(os.path.abspath(e.path)) == _PROPIA:
                        continue
                    try:
                        if e.is_dir(follow_symlinks=False):
                            pila.append(Path(e.path))
                        elif e.is_file(follow_symlinks=False):
                            foto[e.path] = e.stat().st_mtime
                    except OSError:
                        continue
        except OSError:
            continue
    return foto


def _nuevos(antes: dict[str, float], despues: dict[str, float]) -> list[str]:
    return sorted(
        (p for p, m in despues.items() if antes.get(p) != m),
        key=lambda p: despues[p],
        reverse=True,
    )[:40]


def _copiar_informes(nuevos: list[str], informes: Path) -> list[str]:
    """Los PDF que la skill del campus deja en ~/.moodle-skill/salidas se copian a la carpeta de informes."""
    salidas = config.salidas_campus().resolve()
    copiados = []
    for p in nuevos:
        ruta = Path(p)
        if ruta.suffix.lower() == ".pdf" and salidas in ruta.resolve().parents:
            informes.mkdir(parents=True, exist_ok=True)
            destino = informes / ruta.name
            shutil.copy2(ruta, destino)
            copiados.append(str(destino))
    return copiados


class Abrir(BaseModel):
    ruta: str
    carpeta: bool = False


def _permitida(ruta: Path) -> bool:
    cfg = config.leer()
    bases = [cfg["carpeta_trabajo"], cfg["carpeta_informes"], config.salidas_campus()]
    try:
        r = ruta.resolve()
    except OSError:
        return False
    return any(r == b.resolve() or b.resolve() in r.parents for b in bases)


@app.post("/api/abrir")
async def abrir(a: Abrir):
    ruta = Path(a.ruta)
    if not ruta.exists() or not _permitida(ruta):
        raise HTTPException(404, "No encuentro ese archivo.")
    if config.es_windows():
        if a.carpeta and ruta.is_file():
            subprocess.Popen(["explorer", "/select,", str(ruta)])
        else:
            os.startfile(str(ruta))  # type: ignore[attr-defined]
    else:
        objetivo = ruta.parent if a.carpeta and ruta.is_file() else ruta
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(objetivo)])
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Tareas
# --------------------------------------------------------------------------- #


class Pedido(BaseModel):
    receta: str | None = None
    valores: dict[str, str] = {}
    texto: str | None = None  # seguimiento libre dentro de la misma tarea
    sesion: str | None = None


class Respuesta(BaseModel):
    id: str
    ok: bool
    entrada: dict | None = None
    respuestas: dict | None = None
    motivo: str | None = None


@app.post("/api/tarea")
async def tarea(p: Pedido):
    if p.sesion and p.sesion in agente.SESIONES:
        sesion = agente.SESIONES[p.sesion]
        if sesion.ocupada:
            raise HTTPException(409, "Esta tarea todavía está trabajando.")
    else:
        sesion = None

    if p.receta:
        receta = recetas.por_id(p.receta)
        if receta is None:
            raise HTTPException(404, "Esa acción no existe.")
        if p.valores.get("campus"):
            permitidos = {f"{c.get('nombre')} (campus {c.get('id')})" for c in config.listar_campus()}
            if p.valores["campus"] not in permitidos:
                # Un valor de campus que no vino del selector (manipulado a mano) se
                # descarta como si no se hubiera completado, en vez de colarse tal cual
                # en el prompt: ahí podría inyectar texto con `[[`/`]]`.
                p.valores = {**p.valores, "campus": ""}
        falta = recetas.faltantes(receta, p.valores)
        if falta:
            raise HTTPException(400, "Falta completar: " + ", ".join(falta))
        skill = next(s["skill"] for s in recetas.SKILLS if s["id"] == receta["skill"])
        prompt = f"Usá la skill {skill}.\n\n" + recetas.armar_pedido(receta, p.valores)
    elif p.texto and p.texto.strip():
        prompt = p.texto.strip()
    else:
        raise HTTPException(400, "No hay nada para hacer.")

    cfg = config.leer()
    bases = [cfg["carpeta_trabajo"], config.salidas_campus()]

    async def stream():
        nonlocal sesion
        if sesion is None:
            yield agente.sse({"tipo": "paso", "texto": "Iniciando Claude"})
            try:
                sesion = await agente.abrir_sesion(cfg["carpeta_trabajo"])
            except Exception as exc:  # sin CLI, sin login, etc.
                log.exception("no se pudo abrir la sesión")
                yield agente.sse({"tipo": "error", "mensaje": agente._explicar_error(exc)})
                yield agente.sse({"tipo": "fin"})
                return
        yield agente.sse({"tipo": "sesion", "id": sesion.id, "pedido": prompt})
        antes = await asyncio.to_thread(_foto_archivos, bases)
        async for ev in agente.conversar(sesion, prompt):
            if ev.get("tipo") == "fin":
                despues = await asyncio.to_thread(_foto_archivos, bases)
                nuevos = _nuevos(antes, despues)
                copiados = _copiar_informes(nuevos, cfg["carpeta_informes"])
                lista = copiados + [n for n in nuevos if not _es_de_salidas(n, copiados)]
                archivos = [{"nombre": Path(x).name, "ruta": x} for x in dict.fromkeys(lista)]
                if archivos:
                    yield agente.sse({"tipo": "archivos", "archivos": archivos})
            yield agente.sse(ev)

    return StreamingResponse(
        stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


def _es_de_salidas(ruta: str, copiados: list[str]) -> bool:
    """Un PDF de salidas que ya se copió a Informes se muestra una sola vez: la copia."""
    nombres = {Path(c).name for c in copiados}
    return Path(ruta).name in nombres and config.salidas_campus().resolve() in Path(ruta).resolve().parents


@app.post("/api/tarea/{sid}/responder")
async def responder(sid: str, r: Respuesta):
    ok = agente.responder(
        sid, r.id, {"ok": r.ok, "entrada": r.entrada, "respuestas": r.respuestas, "motivo": r.motivo}
    )
    if not ok:
        raise HTTPException(409, "Esa pregunta ya no está esperando respuesta.")
    return {"ok": True}


@app.delete("/api/tarea/{sid}")
async def cerrar(sid: str):
    await agente.cerrar_sesion(sid)
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Proceso
# --------------------------------------------------------------------------- #


@app.get("/api/salud")
async def salud():
    return {"ok": True, "app": "asistente-tup"}


@app.post("/api/apagar")
async def apagar():
    async def _salir():
        await asyncio.sleep(0.3)
        for sid in list(agente.SESIONES):
            await agente.cerrar_sesion(sid)
        os._exit(0)

    asyncio.create_task(_salir())
    return {"ok": True}


@app.get("/api/guia")
async def guia():
    """La misma GUIA.md del repo: una sola fuente para GitHub y para la pantalla de Ayuda."""
    return {"texto": (RAIZ / "GUIA.md").read_text(encoding="utf-8")}


app.mount("/docs", StaticFiles(directory=RAIZ / "docs"), name="docs")
app.mount("/fuentes", StaticFiles(directory=WEB / "fuentes"), name="fuentes")
app.mount("/vendor", StaticFiles(directory=WEB / "vendor"), name="vendor")


@app.get("/{ruta:path}")
async def pantalla(ruta: str):
    # no-cache: el navegador revalida siempre. Sin esto, después de actualizar el
    # asistente seguiría mostrando la pantalla vieja hasta un Ctrl+F5 que nadie conoce.
    sin_cache = {"Cache-Control": "no-cache"}
    archivo = (WEB / ruta).resolve()
    if ruta and archivo.is_file() and WEB.resolve() in archivo.parents:
        return FileResponse(archivo, headers=sin_cache)
    return FileResponse(WEB / "index.html", headers=sin_cache)


def _ya_corre(url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{url}/api/salud", timeout=1.5) as r:
            return r.status == 200
    except OSError:
        return False


def main() -> None:
    import uvicorn

    config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=config.LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    url = f"http://127.0.0.1:{config.PUERTO}"
    if _ya_corre(url):
        webbrowser.open(url)
        return

    servidor = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=config.PUERTO, log_level="warning", log_config=None)
    )

    async def correr():
        async def abrir_navegador():
            for _ in range(50):
                await asyncio.sleep(0.2)
                if servidor.started:
                    webbrowser.open(url)
                    return

        if "--sin-navegador" not in sys.argv:
            asyncio.create_task(abrir_navegador())
        await servidor.serve()

    # asyncio.run usa el loop Proactor en Windows, que es el que permite lanzar el
    # CLI de Claude como subproceso.
    asyncio.run(correr())


if __name__ == "__main__":
    main()
