"""
Prueba de login y descubrimiento de un campus nuevo, con el Python de la skill del campus.

El asistente no lleva el cliente de Moodle: usa el de la skill instalada (sin modificarla),
importando sus módulos (`moodle.cliente`, `moodle.ws_api`) desde una carpeta aparte. Este
script NO guarda nada: prueba el login y devuelve, por materia, todas las comisiones
candidatas (marcando cuáles son del tutor) y las tareas; elegir y guardar lo hace el
asistente.

Las credenciales viajan por stdin (JSON), nunca por argumentos ni por variables de
entorno. Salida: una línea JSON.

    python alta_campus.py <ruta a server.py del MCP>   < {"url", "moodle_user", "moodle_pass"}
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

# Comisión = grupo con el nombre de TUP («M25 C4-01», lo decide la skill) o, en otros campus,
# «Comision_6», «Comisión 3», «C2», «1pro1», «1Prog5». Regionales (R-*) y auxiliares no cuentan.
_COMISION_GENERICA = re.compile(r"comisi[oó]n|^com[\s_.-]*\d|\bC\d{1,2}\b|^\d+pro(?:g)?\d+$", re.IGNORECASE)


def _es_comision(ws_api, nombre: str) -> bool:
    tipo = ws_api.clasificar_grupo(nombre or "")
    return tipo == "comision" or (tipo == "otro" and bool(_COMISION_GENERICA.search(nombre or "")))


async def _descubrir(d: dict) -> dict:
    from moodle.cliente import MobileWSClient
    from moodle import ws_api

    cli = MobileWSClient(d["url"], d["moodle_user"], d["moodle_pass"])
    # Si esto falla es casi siempre usuario/contraseña (el usuario no siempre es el DNI).
    cursos = await ws_api.descubrir_cursos(cli)
    if not cursos:
        return {"ok": False, "error": "El login funcionó pero no veo ningún curso en tu cuenta."}
    if isinstance(cursos[0], dict) and cursos[0].get("error"):
        return {"ok": False, "error": cursos[0]["error"]}

    uid = await cli.api.userid()
    try:
        nombre = ((await cli.ws("core_webservice_get_site_info")) or {}).get("fullname") or ""
    except Exception:  # noqa: BLE001
        nombre = ""

    armados: list[dict] = []
    detectadas = False
    for c in cursos:
        cid = c.get("course_id")
        try:
            r = await cli.ws("core_group_get_course_user_groups", {"courseid": cid, "userid": uid})
            mios = {g.get("id") for g in ((r or {}).get("groups", []) if isinstance(r, dict) else [])}
        except Exception:  # noqa: BLE001
            mios = set()
        try:
            todos = await cli.ws("core_group_get_course_groups", {"courseid": cid}) or []
        except Exception:  # noqa: BLE001
            todos = []
        # Todas las comisiones candidatas del curso; `mia` = el tutor es miembro del grupo.
        # Sin membresía en ninguno (docente o manager con acceso a todo el curso) no se puede
        # saber cuáles son las suyas: nada queda marcado y lo elige la persona.
        comisiones = [{"group_id": g.get("id"), "comision": g.get("name"), "mia": g.get("id") in mios}
                      for g in todos if _es_comision(ws_api, g.get("name") or "")]
        detectadas = detectadas or any(x["mia"] for x in comisiones)
        try:
            tareas = [{"assign_id": str(t["id"]), "titulo": t.get("titulo", "")}
                      for t in await ws_api.listar_tareas(cli, cid)]
        except Exception:  # noqa: BLE001
            tareas = []
        armados.append({"course_id": cid, "nombre": c.get("nombre"), "tareas": tareas, "comisiones": comisiones})

    salida = {"ok": True, "tutor": nombre, "cursos": armados, "detectadas": detectadas}
    if not detectadas:
        salida["nota"] = ("No figurás como miembro de ninguna comisión (por ejemplo, tenés acceso docente a todo "
                          "el curso): elegí cuáles son las tuyas.")
    return salida


def main() -> None:
    servidor = Path(sys.argv[1])
    datos = json.loads(sys.stdin.read())
    sys.path.insert(0, str(servidor.parent))
    try:  # detrás de proxies que interceptan TLS: el almacén de certificados del sistema
        import truststore  # type: ignore
        truststore.inject_into_ssl()
    except Exception:  # noqa: BLE001 — opcional
        pass
    try:
        res = asyncio.run(_descubrir(datos))
    except Exception as e:  # noqa: BLE001 — cualquier falla vuelve como error legible
        res = {"ok": False, "error": f"El login falló ({type(e).__name__}). Revisá usuario y contraseña "
                                     f"(el usuario de Moodle no siempre es el DNI). No guardé nada. "
                                     f"Detalle: {str(e)[:150]}"}
    print(json.dumps(res, ensure_ascii=True, default=str))  # ASCII puro: no depende de la consola


if __name__ == "__main__":
    main()
