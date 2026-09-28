"""
Acciones propias: lo que cada tutor arma para sí mismo y queda como un botón más.

Una acción propia es una receta (`recetas.py`) guardada en `~/.asistente-tup/acciones.json`:
nombre, descripción, los datos que se piden cada vez (el formulario) y la instrucción que
recibe Claude. Sirven en cualquier campus: materias y comisiones que se ofrecen son las del
campus activo. Las crea Claude junto con la persona (herramienta `guardar_accion`, que la
persona confirma en pantalla) y se pueden renombrar o eliminar desde el inicio.

Todo lo que llega acá se valida: el contenido lo redacta un modelo (o se edita a mano el
archivo), y termina renderizado en el formulario y enviado como prompt.
"""

from __future__ import annotations

import json
import re
import unicodedata
import uuid

from . import config

ARCHIVO_NOMBRE = "acciones.json"

# Los mismos tipos de campo que entiende el formulario (`web/app.js`).
TIPOS = ("curso", "comision", "tarea", "texto", "parrafo", "archivo", "archivos", "opcion")
MAX_ACCIONES = 60
MAX_CAMPOS = 10

_ID_CAMPO = re.compile(r"^[a-z][a-z0-9_]{0,29}$")
_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _ruta():
    return config.CONFIG_DIR / ARCHIVO_NOMBRE


def _texto(valor, nombre: str, maximo: int, obligatorio: bool = False) -> str:
    if valor is None:
        valor = ""
    if not isinstance(valor, str):
        raise ValueError(f"«{nombre}» tiene que ser texto.")
    valor = valor.strip()
    if obligatorio and not valor:
        raise ValueError(f"Falta «{nombre}».")
    if len(valor) > maximo:
        raise ValueError(f"«{nombre}» es demasiado largo (máximo {maximo} caracteres).")
    return valor


def validar(defn: dict) -> dict:
    """Devuelve la acción normalizada (sin `id`) o levanta ValueError con un mensaje claro."""
    if not isinstance(defn, dict):
        raise ValueError("La acción tiene un formato inválido.")
    titulo = _texto(defn.get("titulo"), "nombre", 70, True)
    bajada = _texto(defn.get("bajada"), "descripción", 220, True)
    resultado = _texto(defn.get("resultado"), "qué vas a obtener", 220)
    pedido = _texto(defn.get("pedido"), "instrucción", 4000, True)
    if len(pedido) < 15:
        raise ValueError("La instrucción es demasiado corta para que Claude sepa qué hacer.")

    campos_in = defn.get("campos") or []
    if not isinstance(campos_in, list) or len(campos_in) > MAX_CAMPOS:
        raise ValueError(f"Los datos a pedir tienen que ser una lista de hasta {MAX_CAMPOS}.")
    campos: list[dict] = []
    ids: list[str] = []
    for c in campos_in:
        if not isinstance(c, dict):
            raise ValueError("Uno de los datos a pedir tiene un formato inválido.")
        cid = c.get("id")
        if not isinstance(cid, str) or not _ID_CAMPO.match(cid):
            raise ValueError("Cada dato necesita un identificador en minúsculas, sin espacios (por ejemplo «materia»).")
        if cid in ids:
            raise ValueError(f"El identificador «{cid}» está repetido.")
        tipo = c.get("tipo")
        if tipo not in TIPOS:
            raise ValueError(f"El tipo «{tipo}» no existe. Los válidos: {', '.join(TIPOS)}.")
        campo = {"id": cid, "tipo": tipo, "etiqueta": _texto(c.get("etiqueta"), "etiqueta", 90, True)}
        if c.get("opcional"):
            campo["opcional"] = True
        ayuda = _texto(c.get("ayuda"), "ayuda", 200)
        if ayuda:
            campo["ayuda"] = ayuda
        vacio = _texto(c.get("vacio"), "texto por defecto", 120)
        if vacio:
            campo["vacio"] = vacio
        if tipo == "opcion":
            ops = c.get("opciones")
            if (not isinstance(ops, list) or not 2 <= len(ops) <= 12
                    or not all(isinstance(o, str) and 0 < len(o.strip()) <= 80 for o in ops)):
                raise ValueError(f"«{campo['etiqueta']}» necesita entre 2 y 12 opciones (texto corto).")
            campo["opciones"] = [o.strip() for o in ops]
        if tipo in ("comision", "tarea") and "curso" not in [x["tipo"] for x in campos]:
            raise ValueError("Un dato de comisión o tarea tiene que ir después de uno de materia (tipo «curso»).")
        ids.append(cid)
        campos.append(campo)

    desconocidos = sorted({m for m in _PLACEHOLDER.findall(pedido) if m not in ids})
    if desconocidos:
        raise ValueError("La instrucción usa datos que el formulario no pide: " + ", ".join("{" + m + "}" for m in desconocidos) + ".")
    return {"titulo": titulo, "bajada": bajada, "resultado": resultado or "El resultado de la acción, con lo que Claude encontró o hizo.",
            "campos": campos, "pedido": pedido}


def _leer() -> list[dict]:
    try:
        d = json.loads(_ruta().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    lista = d.get("acciones") if isinstance(d, dict) else None
    return [a for a in (lista or []) if isinstance(a, dict) and isinstance(a.get("id"), str)]


def _escribir(lista: list[dict]) -> None:
    config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _ruta().write_text(json.dumps({"acciones": lista}, ensure_ascii=False, indent=2), encoding="utf-8")


def listar() -> list[dict]:
    """Las acciones guardadas, ya como recetas (`skill: propias`). Las que no pasan la validación se ignoran."""
    salida = []
    for a in _leer():
        try:
            salida.append({**validar(a), "id": a["id"], "skill": "propias", "propia": True})
        except ValueError:
            continue
    return salida


def por_id(aid: str) -> dict | None:
    return next((a for a in listar() if a["id"] == aid), None)


def _slug(titulo: str) -> str:
    plano = unicodedata.normalize("NFD", titulo.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plano).strip("-")[:30].strip("-") or "accion"


def guardar(defn: dict) -> dict:
    """Valida y guarda una acción nueva. Devuelve la receta guardada."""
    nueva = validar(defn)
    lista = _leer()
    if len(lista) >= MAX_ACCIONES:
        raise ValueError(f"Ya hay {MAX_ACCIONES} acciones propias: eliminá alguna antes de sumar otra.")
    if any(a.get("titulo", "").strip().lower() == nueva["titulo"].lower() for a in lista):
        raise ValueError(f"Ya tenés una acción llamada «{nueva['titulo']}». Elegí otro nombre.")
    ocupados = {a["id"] for a in lista}
    aid = f"mia-{_slug(nueva['titulo'])}"
    if aid in ocupados:
        aid = f"{aid}-{uuid.uuid4().hex[:4]}"
    lista.append({**nueva, "id": aid})
    _escribir(lista)
    return {**nueva, "id": aid, "skill": "propias", "propia": True}


def renombrar(aid: str, titulo: str, bajada: str) -> dict:
    lista = _leer()
    actual = next((a for a in lista if a["id"] == aid), None)
    if actual is None:
        raise KeyError(aid)
    nuevo = validar({**actual, "titulo": titulo, "bajada": bajada})
    if any(a["id"] != aid and a.get("titulo", "").strip().lower() == nuevo["titulo"].lower() for a in lista):
        raise ValueError(f"Ya tenés una acción llamada «{nuevo['titulo']}». Elegí otro nombre.")
    actual.update({"titulo": nuevo["titulo"], "bajada": nuevo["bajada"]})
    _escribir(lista)
    return {**nuevo, "id": aid, "skill": "propias", "propia": True}


def eliminar(aid: str) -> bool:
    lista = _leer()
    resto = [a for a in lista if a["id"] != aid]
    if len(resto) == len(lista):
        return False
    _escribir(resto)
    return True
