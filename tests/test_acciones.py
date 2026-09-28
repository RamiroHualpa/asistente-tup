"""
Acciones propias: validación, persistencia, API y ejecución como una receta más.
También el primer uso de todo (nadie configuró nada todavía).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import acciones, agente, config, recetas  # noqa: E402


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "HOME", tmp_path)
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path / ".asistente-tup")
    monkeypatch.setattr(config, "CAMPUS_DIR", tmp_path / ".asistente-tup" / "campus")
    monkeypatch.setattr(config, "CAMPUS_REGISTRO", tmp_path / ".asistente-tup" / "campus.json")
    monkeypatch.setattr(config, "mcp_campus", lambda: None)
    return tmp_path


def _accion(**kw):
    base = {
        "titulo": "Entregas viejas de mi comisión",
        "bajada": "Lista lo que espera hace más de una semana.",
        "resultado": "Una lista por tarea.",
        "campos": [
            {"id": "materia", "tipo": "curso", "etiqueta": "Materia"},
            {"id": "comision", "tipo": "comision", "etiqueta": "Comisión", "opcional": True},
            {"id": "nota", "tipo": "texto", "etiqueta": "Aclaración", "opcional": True},
        ],
        "pedido": "Usá la skill tup-campus-navigator. Listá las entregas sin corregir de {materia}[[, comisión {comision}]]. [[{nota}]]",
    }
    return {**base, **kw}


# --------------------------------------------------------------------------- #
# Validación
# --------------------------------------------------------------------------- #


def test_validar_normaliza_y_conserva_lo_que_corresponde():
    v = acciones.validar(_accion(titulo="  Mi acción  "))
    assert v["titulo"] == "Mi acción" and [c["id"] for c in v["campos"]] == ["materia", "comision", "nota"]
    assert v["campos"][1]["opcional"] is True and "opcional" not in v["campos"][0]


def test_validar_sin_campos_es_valido():
    assert acciones.validar(_accion(campos=[], pedido="Decime cuántas entregas sin corregir tengo hoy."))["campos"] == []


@pytest.mark.parametrize("cambio,texto", [
    ({"titulo": ""}, "nombre"),
    ({"titulo": "x" * 71}, "demasiado largo"),
    ({"bajada": ""}, "descripción"),
    ({"pedido": "corto"}, "demasiado corta"),
    ({"pedido": "Hacé {inexistente} con lo que sea que corresponda."}, "inexistente"),
    ({"campos": [{"id": "Materia", "tipo": "curso", "etiqueta": "M"}]}, "identificador"),
    ({"campos": [{"id": "a", "tipo": "curso", "etiqueta": "M"}, {"id": "a", "tipo": "texto", "etiqueta": "T"}]}, "repetido"),
    ({"campos": [{"id": "a", "tipo": "volar", "etiqueta": "M"}]}, "no existe"),
    ({"campos": [{"id": "a", "tipo": "comision", "etiqueta": "C"}]}, "después de uno de materia"),
    ({"campos": [{"id": "a", "tipo": "opcion", "etiqueta": "O", "opciones": ["una sola"]}]}, "opciones"),
    ({"campos": [{"id": "a", "tipo": "texto", "etiqueta": ""}]}, "etiqueta"),
    ({"campos": [{"id": f"c{i}", "tipo": "texto", "etiqueta": "x"} for i in range(11)]}, "hasta"),
    ({"campos": "no es lista"}, "lista"),
])
def test_validar_rechaza_con_mensaje_claro(cambio, texto):
    d = _accion(**cambio)
    if "pedido" not in cambio and "campos" in cambio:
        d["pedido"] = "Hacé lo que corresponda con estos datos, por favor."
    with pytest.raises(ValueError, match=texto):
        acciones.validar(d)


def test_validar_no_es_una_puerta_a_texto_arbitrario_en_los_campos():
    with pytest.raises(ValueError):
        acciones.validar(_accion(titulo=["lista"]))
    with pytest.raises(ValueError):
        acciones.validar("no es un dict")


# --------------------------------------------------------------------------- #
# Persistencia
# --------------------------------------------------------------------------- #


def test_guardar_listar_y_persistir_entre_sesiones(home):
    g = acciones.guardar(_accion())
    assert g["id"] == "mia-entregas-viejas-de-mi-comision" and g["skill"] == "propias" and g["propia"] is True
    # «otra sesión»: se vuelve a leer del archivo
    assert [a["id"] for a in acciones.listar()] == [g["id"]]
    assert (home / ".asistente-tup" / "acciones.json").is_file()
    assert acciones.por_id(g["id"])["pedido"].startswith("Usá la skill")


def test_no_permite_nombres_repetidos_ni_pasarse_del_limite(home, monkeypatch):
    acciones.guardar(_accion())
    with pytest.raises(ValueError, match="Ya tenés"):
        acciones.guardar(_accion(titulo="ENTREGAS VIEJAS DE MI COMISIÓN".lower()))
    monkeypatch.setattr(acciones, "MAX_ACCIONES", 1)
    with pytest.raises(ValueError, match="Ya hay"):
        acciones.guardar(_accion(titulo="Otra distinta"))


def test_renombrar_y_eliminar(home):
    aid = acciones.guardar(_accion())["id"]
    acciones.guardar(_accion(titulo="Segunda"))
    r = acciones.renombrar(aid, "Nuevo nombre", "Nueva descripción")
    assert r["titulo"] == "Nuevo nombre" and acciones.por_id(aid)["bajada"] == "Nueva descripción"
    assert acciones.por_id(aid)["campos"][0]["id"] == "materia"          # lo demás no se toca
    with pytest.raises(ValueError):
        acciones.renombrar(aid, "Segunda", "x")                            # nombre ya usado por otra
    with pytest.raises(KeyError):
        acciones.renombrar("mia-no-existe", "a", "b")
    assert acciones.eliminar(aid) is True and acciones.eliminar(aid) is False
    assert [a["titulo"] for a in acciones.listar()] == ["Segunda"]


@pytest.mark.parametrize("contenido", ["{", "[]", '{"acciones": "x"}', '{"acciones": [1, {"sin": "id"}]}'])
def test_archivo_roto_no_rompe_nada(home, contenido):
    (home / ".asistente-tup").mkdir()
    (home / ".asistente-tup" / "acciones.json").write_text(contenido, encoding="utf-8")
    assert acciones.listar() == []
    assert acciones.guardar(_accion())["id"]                                # y se puede seguir guardando


def test_una_accion_editada_a_mano_e_invalida_se_ignora(home):
    (home / ".asistente-tup").mkdir()
    (home / ".asistente-tup" / "acciones.json").write_text(json.dumps({"acciones": [
        {"id": "mia-rota", "titulo": "Rota", "bajada": "b", "pedido": "Hacé {noexiste} ahora mismo, por favor.", "campos": []},
        {**_accion(), "id": "mia-buena"}]}), encoding="utf-8")
    assert [a["id"] for a in acciones.listar()] == ["mia-buena"]


# --------------------------------------------------------------------------- #
# API y ejecución
# --------------------------------------------------------------------------- #


def _cliente():
    from fastapi.testclient import TestClient
    from backend import app as backend_app

    return TestClient(backend_app.app)


def test_el_catalogo_incluye_las_propias_y_la_seccion_mis_acciones(home):
    aid = acciones.guardar(_accion())["id"]
    client = _cliente()
    ids = [r["id"] for r in client.get("/api/catalogo").json()["recetas"]]
    assert "crear_accion" in ids and aid in ids
    skills = {s["id"]: s for s in client.get("/api/estado").json()["skills"]}
    assert skills["propias"]["instalada"] is True and skills["propias"]["bloqueada"] is False


def test_una_accion_propia_corre_como_una_receta_sin_prefijo_de_skill(home, monkeypatch):
    aid = acciones.guardar(_accion())["id"]
    visto = []

    async def fake_abrir(trabajo):
        return SimpleNamespace(id="s1", ocupada=False)

    async def fake_conversar(sesion, prompt):
        visto.append(prompt)
        yield {"tipo": "fin"}

    monkeypatch.setattr(agente, "abrir_sesion", fake_abrir)
    monkeypatch.setattr(agente, "conversar", fake_conversar)
    r = _cliente().post("/api/tarea", json={"receta": aid, "valores": {"materia": "Prog II (course_id 81)", "comision": "C2 (group_id 9)"}})
    assert r.status_code == 200
    assert visto == ["Usá la skill tup-campus-navigator. Listá las entregas sin corregir de Prog II (course_id 81), comisión C2 (group_id 9). "]


def test_una_accion_propia_pide_sus_datos_obligatorios(home):
    aid = acciones.guardar(_accion())["id"]
    r = _cliente().post("/api/tarea", json={"receta": aid, "valores": {}})
    assert r.status_code == 400 and "Materia" in r.json()["detail"]


def test_api_renombrar_y_eliminar(home):
    aid = acciones.guardar(_accion())["id"]
    client = _cliente()
    r = client.put(f"/api/acciones/{aid}", json={"titulo": "Otro nombre", "bajada": "Otra descripción"})
    assert r.status_code == 200 and r.json()["titulo"] == "Otro nombre"
    assert client.put(f"/api/acciones/{aid}", json={"titulo": "", "bajada": "x"}).status_code == 400
    assert client.put("/api/acciones/mia-no-existe", json={"titulo": "a", "bajada": "b"}).status_code == 404
    assert client.delete(f"/api/acciones/{aid}").status_code == 200
    assert client.delete(f"/api/acciones/{aid}").status_code == 404


def test_guardar_accion_pasa_siempre_por_la_confirmacion_de_la_persona():
    assert agente._es_escritura("mcp__asistente__guardar_accion", {}) is True


def test_la_receta_de_crear_accion_explica_como_guardar():
    r = recetas.por_id("crear_accion")
    pedido = recetas.armar_pedido(r, {"idea": ""})
    assert "guardar_accion" in pedido and "[[" not in pedido and "{idea}" not in pedido
    assert "La idea inicial es: reportes" in recetas.armar_pedido(r, {"idea": "reportes"})


# --------------------------------------------------------------------------- #
# Primer uso: nada configurado todavía
# --------------------------------------------------------------------------- #


def test_primer_uso_sin_ningun_archivo_todo_responde(home):
    client = _cliente()
    assert client.get("/api/estado").status_code == 200
    c = client.get("/api/campus").json()
    assert c["activo"] == "tup" and [k["id"] for k in c["campus"]] == ["tup"]
    cat = client.get("/api/catalogo").json()
    assert cat["cursos"] == [] and any(r["id"] == "crear_accion" for r in cat["recetas"])
    assert client.get("/api/guia").status_code == 200
