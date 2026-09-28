"""
Alta de un campus nuevo, ejecutada con el Python de la skill del campus.

El asistente no lleva las dependencias del MCP (cliente Moodle, etc.), así que la
alta corre en un subproceso con el intérprete del `moodle-tutor`: importa su
`server.py` y llama a `agregar_campus`, que prueba el login ANTES de guardar nada y
después descubre materias y comisiones.

Las credenciales viajan por stdin (JSON), nunca por argumentos ni por variables de
entorno: no quedan en la lista de procesos. Salida: una línea JSON con el resultado.

    python alta_campus.py <ruta a server.py del MCP>   < {"tenant_id": ..., ...}
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path


async def _alta(server, d: dict) -> dict:
    return await server.agregar_campus(
        d["tenant_id"], d["nombre"], d["url"], d["moodle_user"], d["moodle_pass"],
        d.get("activeia_user", ""), d.get("activeia_pass", ""),
    )


def main() -> None:
    servidor = Path(sys.argv[1])
    datos = json.loads(sys.stdin.read())
    sys.path.insert(0, str(servidor.parent))
    try:
        import server  # type: ignore  # el server.py del MCP
        res = asyncio.run(_alta(server, datos))
    except Exception as e:  # noqa: BLE001 — cualquier falla vuelve como error legible
        res = {"ok": False, "error": f"No pude dar de alta el campus: {type(e).__name__}"}
    # Sin credenciales en la respuesta: sólo lo que la interfaz necesita mostrar.
    print(json.dumps({"ok": bool(res.get("ok")), "error": res.get("error"),
                      "detalle": {k: v for k, v in res.items() if k not in ("ok", "error")}},
                     ensure_ascii=True, default=str))  # ASCII puro: no depende de la consola


if __name__ == "__main__":
    main()
