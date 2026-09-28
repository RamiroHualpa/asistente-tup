"""
Tests para los bugs del review de `multi-tenant-moodle-ui`:

1. Rutas por tenant (config.salidas_campus / mis_datos_path) con fallback a flat.
2. tenant_activo()/listar_campus() no explotan con estado.json malformado.
3. armar_pedido no inyecta el bloque de campus cuando el campo quedó vacío
   (equivalente server-side al "no se tocó el selector" del frontend).

Nunca tocan el `~/.moodle-skill` real: todo corre contra un `HOME` temporal
monkeypatcheado, y no se levanta ningún servidor (el 8790 real ya está en uso
por otra instancia -- confirmado con `netstat` antes de escribir este archivo).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import config, recetas  # noqa: E402


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "HOME", tmp_path)
    return tmp_path


def _moodle(home: Path) -> Path:
    d = home / ".moodle-skill"
    d.mkdir(parents=True, exist_ok=True)
    return d


# --------------------------------------------------------------------------- #
# Bug 1 — rutas por tenant con fallback
# --------------------------------------------------------------------------- #


def test_mis_datos_path_prefiere_tenant_cuando_existe(home):
    m = _moodle(home)
    (m / "mis_datos.json").write_text(json.dumps({"tutor": {"nombre": "Flat"}}), encoding="utf-8")
    tup = m / "tup"
    tup.mkdir()
    (tup / "mis_datos.json").write_text(json.dumps({"tutor": {"nombre": "PorTenant"}}), encoding="utf-8")
    # tenant_activo() sin estado.json => "tup", que sí tiene layout propio: debe ganar.
    assert config.tenant_activo() == "tup"
    ruta = config.mis_datos_path()
    assert ruta == tup / "mis_datos.json"
    assert json.loads(ruta.read_text(encoding="utf-8"))["tutor"]["nombre"] == "PorTenant"


def test_mis_datos_path_cae_a_flat_si_no_hay_tenant(home):
    m = _moodle(home)
    (m / "mis_datos.json").write_text(json.dumps({"tutor": {"nombre": "Flat"}}), encoding="utf-8")
    # Nada bajo m / "tup": debe caer a la ruta flat legacy.
    ruta = config.mis_datos_path()
    assert ruta == m / "mis_datos.json"
    assert json.loads(ruta.read_text(encoding="utf-8"))["tutor"]["nombre"] == "Flat"


def test_mis_datos_path_resuelve_bajo_tenant_no_tup(home):
    m = _moodle(home)
    (m / "estado.json").write_text(json.dumps({"tenant_activo": "otra-facu"}), encoding="utf-8")
    otra = m / "otra-facu"
    otra.mkdir()
    (otra / "mis_datos.json").write_text(json.dumps({"tutor": {"nombre": "OtraFacu"}}), encoding="utf-8")
    assert config.tenant_activo() == "otra-facu"
    assert config.mis_datos_path() == otra / "mis_datos.json"


def test_salidas_campus_prefiere_tenant_cuando_existe_el_directorio(home):
    m = _moodle(home)
    (m / "salidas").mkdir()
    tup_salidas = m / "tup" / "salidas"
    tup_salidas.mkdir(parents=True)
    assert config.salidas_campus() == tup_salidas


def test_salidas_campus_cae_a_flat_si_no_hay_carpeta_por_tenant(home):
    m = _moodle(home)
    (m / "salidas").mkdir()
    assert config.salidas_campus() == m / "salidas"


# --------------------------------------------------------------------------- #
# Bug 2 — tenant_activo()/listar_campus() no explotan con JSON malformado
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("contenido", ["[]", "null", '"x"', '{"tenant_activo": 5}', '{"tenant_activo": {}}'])
def test_tenant_activo_default_seguro_con_json_valido_pero_forma_incorrecta(home, contenido):
    m = _moodle(home)
    (m / "estado.json").write_text(contenido, encoding="utf-8")
    assert config.tenant_activo() == "tup"


def test_tenant_activo_default_seguro_con_bytes_no_utf8(home):
    m = _moodle(home)
    (m / "estado.json").write_bytes(b"\xff\xfe\x00\x01no-utf8")
    assert config.tenant_activo() == "tup"


def test_tenant_activo_ok_con_forma_correcta(home):
    m = _moodle(home)
    (m / "estado.json").write_text(json.dumps({"tenant_activo": "otra-facu"}), encoding="utf-8")
    assert config.tenant_activo() == "otra-facu"


@pytest.mark.parametrize("contenido", ["[]", "null", '"x"', '{"foo": "bar"}'])
def test_listar_campus_default_seguro_con_json_valido_pero_forma_incorrecta(home, contenido):
    m = _moodle(home)
    (m / "tenants.json").write_text(contenido, encoding="utf-8")
    assert config.listar_campus() == []


def test_listar_campus_default_seguro_con_bytes_no_utf8(home):
    m = _moodle(home)
    (m / "tenants.json").write_bytes(b"\xff\xfe\x00\x01no-utf8")
    assert config.listar_campus() == []


def test_listar_campus_filtra_entradas_malformadas(home):
    m = _moodle(home)
    datos = [
        {"id": "tup", "nombre": "TUP", "url": "https://tup.sied.utn.edu.ar"},
        None,
        "algo",
        {"nombre": "sin id"},
    ]
    (m / "tenants.json").write_text(json.dumps(datos), encoding="utf-8")
    campus = config.listar_campus()
    assert campus == [{"id": "tup", "nombre": "TUP", "url": "https://tup.sied.utn.edu.ar"}]


def test_listar_campus_ok_con_forma_correcta(home):
    m = _moodle(home)
    datos = [{"id": "tup", "nombre": "TUP", "url": "https://tup.sied.utn.edu.ar"}]
    (m / "tenants.json").write_text(json.dumps(datos), encoding="utf-8")
    assert config.listar_campus() == datos


# --------------------------------------------------------------------------- #
# Bug 2b — GET /api/campus no puede tirar abajo el resto de la app
# --------------------------------------------------------------------------- #


def test_api_campus_no_revienta_con_estado_corrupto(home):
    from fastapi.testclient import TestClient
    from backend import app as backend_app

    _moodle(home)
    (home / ".moodle-skill" / "estado.json").write_text("[]", encoding="utf-8")
    client = TestClient(backend_app.app)
    r = client.get("/api/campus")
    assert r.status_code == 200
    assert r.json() == {"campus": [], "activo": "tup"}


# --------------------------------------------------------------------------- #
# El campus se elige arriba (barra), no en cada receta
# --------------------------------------------------------------------------- #


def test_ninguna_receta_pide_campus_ni_lo_inyecta_en_el_pedido():
    for r in recetas.RECETAS:
        assert all(c["tipo"] != "campus" for c in r["campos"]), r["id"]
        assert "{campus}" not in r["pedido"] and "usar_campus" not in r["pedido"], r["id"]


def test_campus_que_no_es_tup_no_cae_a_la_carpeta_flat(home):
    m = _moodle(home)
    (m / "mis_datos.json").write_text(json.dumps({"tutor": {"nombre": "Flat de TUP"}}), encoding="utf-8")
    (m / "salidas").mkdir()
    (m / "tenants.json").write_text(json.dumps([{"id": "otra", "nombre": "Otra", "url": "https://x.edu"}]), encoding="utf-8")
    config.set_tenant_activo("otra")
    assert config.mis_datos_path() == m / "otra" / "mis_datos.json"
    assert config.salidas_campus() == m / "otra" / "salidas"


def test_set_tenant_activo_rechaza_id_no_registrado(home):
    m = _moodle(home)
    (m / "tenants.json").write_text(json.dumps([{"id": "tup", "nombre": "TUP", "url": "u"}]), encoding="utf-8")
    with pytest.raises(ValueError):
        config.set_tenant_activo("../etc")
    assert config.tenant_activo() == "tup"


def _campus_nuevo(home: Path) -> Path:
    m = _moodle(home)
    (m / "tenants.json").write_text(json.dumps([
        {"id": "tup", "nombre": "TUP (UTN)", "url": "https://tup.sied.utn.edu.ar"},
        {"id": "frm", "nombre": "FRM", "url": "https://campus.frm.edu"},
    ]), encoding="utf-8")
    d = m / "frm"
    d.mkdir()
    (d / "aulas.json").write_text(json.dumps({"materias": [
        {"materia": "Programación 1", "course_id": 3}, {"materia": "Programación II", "course_id": 6}]}), encoding="utf-8")
    (d / "comisiones.json").write_text(json.dumps({"materias": [
        {"materia": "Programación 1", "course_id": 3, "comisiones": []},
        {"materia": "Programación II", "course_id": 6, "comisiones": [
            {"comision": "C4-01", "nombre_campus": "C4-01", "group_id": 404}]}]}), encoding="utf-8")
    return m


def test_catalogo_de_campus_nuevo_sale_de_lo_descubierto(home):
    from fastapi.testclient import TestClient
    from backend import app as backend_app

    _campus_nuevo(home)
    config.set_tenant_activo("frm")
    cursos = TestClient(backend_app.app).get("/api/catalogo").json()["cursos"]
    assert [c["nombre"] for c in cursos] == ["Programación 1", "Programación II"]
    assert cursos[1]["comisiones"] == [{"id": 404, "nombre": "C4-01"}]


def test_api_cambiar_campus_activo(home):
    from fastapi.testclient import TestClient
    from backend import app as backend_app

    _campus_nuevo(home)
    client = TestClient(backend_app.app)
    r = client.post("/api/campus/activo", json={"id": "frm"})
    assert r.status_code == 200 and r.json()["activo"] == "frm"
    assert client.get("/api/campus").json()["activo"] == "frm"
    assert client.post("/api/campus/activo", json={"id": "no-existe"}).status_code == 404
    assert config.tenant_activo() == "frm"


def _alta_payload(**kw):
    base = {"nombre": "UTN Mendoza", "url": "https://campus.frm.edu", "moodle_user": "u", "moodle_pass": "p"}
    return {**base, **kw}


def test_api_alta_valida_datos_antes_de_probar_nada(home):
    from fastapi.testclient import TestClient
    from backend import app as backend_app

    client = TestClient(backend_app.app)
    assert client.post("/api/campus", json=_alta_payload(url="campus.sin.esquema")).status_code == 400
    assert client.post("/api/campus", json=_alta_payload(moodle_pass="")).status_code == 400
    # Active-IA a medias: usuario sin contraseña.
    assert client.post("/api/campus", json=_alta_payload(activeia_user="x")).status_code == 400


def test_api_alta_ok_pasa_credenciales_por_stdin_y_activa_el_campus(home, monkeypatch):
    import subprocess
    from fastapi.testclient import TestClient
    from backend import app as backend_app

    m = _moodle(home)
    (m / "tenants.json").write_text(json.dumps([{"id": "tup", "nombre": "TUP", "url": "u"}]), encoding="utf-8")
    monkeypatch.setattr(config, "mcp_campus", lambda: {"command": "py", "args": ["server.py"], "env": {"MOODLE_URL": "https://tup"}})
    visto = {}

    def fake_run(cmd, **kw):
        visto["cmd"], visto["input"], visto["env"] = cmd, json.loads(kw["input"]), kw["env"]
        # Lo que hace agregar_campus de la skill: registrar el tenant.
        (m / "tenants.json").write_text(json.dumps([
            {"id": "tup", "nombre": "TUP", "url": "u"},
            {"id": visto["input"]["tenant_id"], "nombre": "UTN Mendoza", "url": "https://campus.frm.edu"}]), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps({"ok": True, "error": None, "detalle": {}}) + "", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    r = TestClient(backend_app.app).post("/api/campus", json=_alta_payload(activeia_user="ia", activeia_pass="pw"))
    assert r.status_code == 200, r.text
    assert r.json()["activo"] == "utn-mendoza"
    assert visto["input"]["moodle_pass"] == "p" and visto["input"]["activeia_user"] == "ia"
    # Credenciales sólo por stdin: ni en argumentos ni en el entorno; y sin MOODLE_URL heredado.
    assert "p" not in visto["cmd"][1:] and not any(k.startswith("MOODLE_") for k in visto["env"])


def test_api_alta_con_login_invalido_no_cambia_de_campus(home, monkeypatch):
    import subprocess
    from fastapi.testclient import TestClient
    from backend import app as backend_app

    m = _moodle(home)
    (m / "tenants.json").write_text(json.dumps([{"id": "tup", "nombre": "TUP", "url": "u"}]), encoding="utf-8")
    monkeypatch.setattr(config, "mcp_campus", lambda: {"command": "py", "args": ["server.py"]})
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(
        cmd, 0, stdout=json.dumps({"ok": False, "error": "Acceso inválido", "detalle": {}}) + "", stderr=""))
    r = TestClient(backend_app.app).post("/api/campus", json=_alta_payload())
    assert r.status_code == 400 and "Acceso inválido" in r.json()["detail"]
    assert config.tenant_activo() == "tup"


def test_api_alta_tolera_salida_no_utf8_del_subproceso(home, monkeypatch):
    """Regresión: la consola de Windows imprime en cp1252; la alta no puede romperse por eso."""
    import subprocess
    from fastapi.testclient import TestClient
    from backend import app as backend_app

    m = _moodle(home)
    (m / "tenants.json").write_text(json.dumps([{"id": "tup", "nombre": "TUP", "url": "u"}]), encoding="utf-8")
    monkeypatch.setattr(config, "mcp_campus", lambda: {"command": "py", "args": ["server.py"]})
    visto = {}

    def fake_run(cmd, **kw):
        visto.update(kw)
        salida = json.dumps({"ok": False, "error": "Acceso inválido", "detalle": {}}, ensure_ascii=True)
        return subprocess.CompletedProcess(cmd, 0, stdout=salida, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    r = TestClient(backend_app.app).post("/api/campus", json=_alta_payload())
    assert r.status_code == 400 and "Acceso inválido" in r.json()["detail"]
    assert visto["env"]["PYTHONIOENCODING"] == "utf-8" and visto["errors"] == "replace"
