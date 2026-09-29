"""
Multi-campus del asistente, sin tocar la skill del campus.

- El registro de campus, el campus activo y las carpetas de datos son del asistente
  (`~/.asistente-tup/campus.json`, `~/.asistente-tup/campus/<id>/`); TUP es el de siempre
  (`~/.moodle-skill`, URL de la config de Claude Code) y no se guarda en el registro.
- Cada tarea arranca el MCP `moodle-tutor` con el entorno del campus activo.
- El alta prueba el login en un subproceso y sólo guarda si salió bien.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import config, recetas  # noqa: E402

MCP_TUP = {
    "type": "stdio",
    "command": "py-skill",
    "args": ["C:/skill/mcp/server.py"],
    "env": {"MOODLE_URL": "https://tup.test", "SSL_CERT_FILE": "C:/certs.pem", "MOODLE_USER": "no-debe-pasar"},
}


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "HOME", tmp_path)
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path / ".asistente-tup")
    monkeypatch.setattr(config, "CAMPUS_DIR", tmp_path / ".asistente-tup" / "campus")
    monkeypatch.setattr(config, "CAMPUS_REGISTRO", tmp_path / ".asistente-tup" / "campus.json")
    monkeypatch.setattr(config, "mcp_campus", lambda: json.loads(json.dumps(MCP_TUP)))
    return tmp_path


# --------------------------------------------------------------------------- #
# Registro, campus activo y carpetas
# --------------------------------------------------------------------------- #


def test_sin_registro_solo_hay_tup_y_es_el_activo(home):
    assert config.listar_campus() == [{"id": "tup", "nombre": "TUP (UTN)", "url": "https://tup.test"}]
    assert config.tenant_activo() == "tup"
    assert config.datos_dir() == home / ".moodle-skill"
    assert config.mis_datos_path() == home / ".moodle-skill" / "mis_datos.json"
    assert config.salidas_campus() == home / ".moodle-skill" / "salidas"


def test_registrar_activar_y_carpeta_propia(home):
    config.registrar_campus("mendoza", "Mendoza", "https://m.test")
    assert [c["id"] for c in config.listar_campus()] == ["tup", "mendoza"]
    config.set_tenant_activo("mendoza")
    assert config.tenant_activo() == "mendoza"
    assert config.datos_dir() == home / ".asistente-tup" / "campus" / "mendoza"
    # nunca cae a la carpeta de TUP
    assert config.mis_datos_path() == home / ".asistente-tup" / "campus" / "mendoza" / "mis_datos.json"


def test_registrar_rechaza_tup_y_duplicados_sin_importar_mayusculas(home):
    with pytest.raises(ValueError):
        config.registrar_campus("TUP", "Otro", "https://x")
    config.registrar_campus("a", "A", "https://a")
    with pytest.raises(ValueError):
        config.registrar_campus("A", "A2", "https://a2")


def test_set_tenant_activo_rechaza_id_no_registrado(home):
    with pytest.raises(ValueError):
        config.set_tenant_activo("../etc")
    assert config.tenant_activo() == "tup"


def test_activo_guardado_que_ya_no_existe_vuelve_a_tup(home):
    config.registrar_campus("a", "A", "https://a")
    config.set_tenant_activo("a")
    config.CAMPUS_REGISTRO.write_text(json.dumps({"activo": "a"}), encoding="utf-8")  # sin la lista
    assert config.tenant_activo() == "tup"


@pytest.mark.parametrize("contenido", ["[]", '"x"', "null", "{", '{"activo": 3, "campus": "x"}'])
def test_registro_con_forma_incorrecta_no_rompe(home, contenido):
    config.CONFIG_DIR.mkdir(parents=True)
    config.CAMPUS_REGISTRO.write_text(contenido, encoding="utf-8")
    assert config.tenant_activo() == "tup"
    assert [c["id"] for c in config.listar_campus()] == ["tup"]


def test_registro_con_bytes_no_utf8_no_rompe(home):
    config.CONFIG_DIR.mkdir(parents=True)
    config.CAMPUS_REGISTRO.write_bytes(b"\xff\xfe\x00")
    assert config.tenant_activo() == "tup"


def test_listar_campus_filtra_entradas_malformadas(home):
    config.CONFIG_DIR.mkdir(parents=True)
    config.CAMPUS_REGISTRO.write_text(json.dumps({"campus": [
        {"id": "ok", "nombre": "Ok", "url": "u"}, {"nombre": "sin id"}, "texto", {"id": "tup", "nombre": "falso TUP"}]}),
        encoding="utf-8")
    assert [c["id"] for c in config.listar_campus()] == ["tup", "ok"]
    assert config.listar_campus()[0]["nombre"] == "TUP (UTN)"


# --------------------------------------------------------------------------- #
# El MCP arranca con el entorno del campus activo
# --------------------------------------------------------------------------- #


def test_mcp_de_tup_es_el_de_siempre_sin_tocar(home):
    assert config.mcp_campus_activo() == MCP_TUP


def test_mcp_de_otro_campus_lleva_su_carpeta_y_url_y_no_hereda_credenciales(home):
    config.registrar_campus("mendoza", "Mendoza", "https://m.test")
    config.set_tenant_activo("mendoza")
    mcp = config.mcp_campus_activo()
    assert mcp["command"] == MCP_TUP["command"] and mcp["args"] == MCP_TUP["args"]
    assert mcp["env"]["MOODLE_URL"] == "https://m.test"
    assert mcp["env"]["MOODLE_SKILL_HOME"] == str(home / ".asistente-tup" / "campus" / "mendoza")
    assert mcp["env"]["SSL_CERT_FILE"] == "C:/certs.pem"          # lo demás se conserva
    assert "MOODLE_USER" not in mcp["env"] and "MOODLE_PASS" not in mcp["env"]


def test_escribir_env_guarda_solo_lo_cargado(home):
    ruta = config.escribir_env("mendoza", {"MOODLE_USER": "u", "MOODLE_PASS": "p", "ACTIVEIA_USER": "", "ACTIVEIA_PASS": ""})
    assert ruta == home / ".asistente-tup" / "campus" / "mendoza" / ".env"
    lineas = [ln for ln in ruta.read_text(encoding="utf-8").splitlines() if not ln.startswith("#")]
    assert lineas == ["MOODLE_USER=u", "MOODLE_PASS=p"]


# --------------------------------------------------------------------------- #
# Recetas: el campus no se elige por receta
# --------------------------------------------------------------------------- #


def test_ninguna_receta_pide_campus_ni_lo_inyecta_en_el_pedido():
    for r in recetas.RECETAS:
        assert all(c["tipo"] != "campus" for c in r["campos"]), r["id"]
        assert "{campus}" not in r["pedido"] and "usar_campus" not in r["pedido"], r["id"]


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #


def _cliente():
    from fastapi.testclient import TestClient
    from backend import app as backend_app

    return TestClient(backend_app.app)


def test_api_campus_lista_y_activo(home):
    r = _cliente().get("/api/campus")
    assert r.status_code == 200 and r.json()["activo"] == "tup"


def test_api_cambiar_campus_activo(home):
    config.registrar_campus("mendoza", "Mendoza", "https://m.test")
    client = _cliente()
    r = client.post("/api/campus/activo", json={"id": "mendoza"})
    assert r.status_code == 200 and r.json()["activo"] == "mendoza"
    assert client.post("/api/campus/activo", json={"id": "no-existe"}).status_code == 404
    assert config.tenant_activo() == "mendoza"


def test_api_catalogo_sigue_al_campus_activo(home):
    (home / ".moodle-skill").mkdir()
    (home / ".moodle-skill" / "mis_datos.json").write_text(json.dumps({"cursos": [
        {"course_id": 1, "nombre": "Materia de TUP", "comisiones_del_tutor": [{"comision": "C1", "group_id": 10}], "tareas": []}]}), encoding="utf-8")
    config.registrar_campus("mendoza", "Mendoza", "https://m.test")
    carpeta = home / ".asistente-tup" / "campus" / "mendoza"
    carpeta.mkdir(parents=True)
    (carpeta / "mis_datos.json").write_text(json.dumps({"cursos": [
        {"course_id": 3, "nombre": "Prog 1", "comisiones_del_tutor": [{"comision": "1pro1", "group_id": 5}], "tareas": []}]}), encoding="utf-8")
    client = _cliente()
    assert [c["nombre"] for c in client.get("/api/catalogo").json()["cursos"]] == ["Materia de TUP"]
    config.set_tenant_activo("mendoza")
    cursos = client.get("/api/catalogo").json()["cursos"]
    assert [c["nombre"] for c in cursos] == ["Prog 1"] and cursos[0]["comisiones"] == [{"id": 5, "nombre": "1pro1"}]


def _alta_payload(**kw):
    return {"nombre": "UTN Mendoza", "url": "https://campus.frm.edu", "moodle_user": "u", "moodle_pass": "p", **kw}


def _resultado(ok=True, **extra):
    salida = {"ok": ok, **extra}
    return subprocess.CompletedProcess([], 0, stdout=json.dumps(salida, ensure_ascii=True) + "\n", stderr="")


# Lo que devuelve el subproceso: todas las comisiones candidatas; `mia` = es del tutor.
DESCUBIERTO = {"tutor": "Tutor", "detectadas": False, "nota": "elegí cuáles son las tuyas", "cursos": [
    {"course_id": 3, "nombre": "Prog 1", "tareas": [{"assign_id": "9", "titulo": "TP1"}],
     "comisiones": [{"group_id": 5, "comision": "1pro3", "mia": False}, {"group_id": 6, "comision": "1pro4", "mia": False},
                    {"group_id": 7, "comision": "1pro5", "mia": False}]},
    {"course_id": 6, "nombre": "Prog II", "tareas": [], "comisiones": [{"group_id": 8, "comision": "2pro5", "mia": False}]},
]}


def _con_membresia():
    d = json.loads(json.dumps(DESCUBIERTO))
    d["detectadas"], d["nota"] = True, None
    d["cursos"][0]["comisiones"][0]["mia"] = True
    return d


def _probar(client, monkeypatch, descubierto=DESCUBIERTO, **kw):
    monkeypatch.setattr(subprocess, "run", lambda cmd, **k: _resultado(**descubierto))
    return client.post("/api/campus/probar", json=_alta_payload(**kw))


def test_api_probar_valida_datos_antes_de_probar_nada(home):
    client = _cliente()
    assert client.post("/api/campus/probar", json=_alta_payload(url="campus.sin.esquema")).status_code == 400
    assert client.post("/api/campus/probar", json=_alta_payload(moodle_pass="")).status_code == 400
    assert client.post("/api/campus/probar", json=_alta_payload(activeia_user="x")).status_code == 400  # Active-IA a medias


def test_api_probar_no_guarda_nada_y_deja_todo_desmarcado_si_no_hay_membresia(home, monkeypatch):
    visto = {}

    def fake_run(cmd, **kw):
        visto.update(cmd=cmd, entrada=json.loads(kw["input"]), env=kw["env"])
        return _resultado(**DESCUBIERTO)

    monkeypatch.setattr(subprocess, "run", fake_run)
    r = _cliente().post("/api/campus/probar", json=_alta_payload(activeia_user="ia", activeia_pass="pw"))
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["detectadas"] is False and cuerpo["nota"] and cuerpo["token"]
    assert not any(g["elegida"] for c in cuerpo["cursos"] for g in c["comisiones"])
    assert not config.CAMPUS_DIR.exists() and [c["id"] for c in config.listar_campus()] == ["tup"]
    # Credenciales sólo por stdin: ni en argumentos ni en el entorno del subproceso.
    assert visto["entrada"]["moodle_pass"] == "p" and "p" not in visto["cmd"][1:]
    assert not any(k.startswith(("MOODLE_", "ACTIVEIA_")) for k in visto["env"])
    assert visto["env"]["PYTHONIOENCODING"] == "utf-8"


def test_api_probar_marca_las_del_tutor_si_hay_membresia(home, monkeypatch):
    cuerpo = _probar(_cliente(), monkeypatch, _con_membresia()).json()
    marcadas = [g["comision"] for c in cuerpo["cursos"] for g in c["comisiones"] if g["elegida"]]
    assert marcadas == ["1pro3"] and cuerpo["detectadas"] is True


def test_api_probar_con_login_invalido(home, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: _resultado(False, error="Acceso inválido"))
    r = _cliente().post("/api/campus/probar", json=_alta_payload())
    assert r.status_code == 400 and "Acceso inválido" in r.json()["detail"]
    assert not config.CAMPUS_DIR.exists()


def test_api_probar_sin_skill_instalada(home, monkeypatch):
    monkeypatch.setattr(config, "mcp_campus", lambda: None)
    assert _cliente().post("/api/campus/probar", json=_alta_payload()).status_code == 400


def _seleccion(*pares):
    return [{"course_id": c, "group_ids": g} for c, g in pares]


def test_api_confirmar_guarda_solo_lo_elegido_y_activa_el_campus(home, monkeypatch):
    client = _cliente()
    token = _probar(client, monkeypatch, activeia_user="ia", activeia_pass="pw").json()["token"]
    r = client.post("/api/campus", json={"token": token, "seleccion": _seleccion((3, [5, 6]), (6, []))})
    assert r.status_code == 200, r.text
    assert r.json()["activo"] == "utn-mendoza" and r.json()["detalle"]["cursos"] == 1
    carpeta = home / ".asistente-tup" / "campus" / "utn-mendoza"
    datos = json.loads((carpeta / "mis_datos.json").read_text(encoding="utf-8"))
    assert [c["nombre"] for c in datos["cursos"]] == ["Prog 1"]          # Prog II sin comisiones queda afuera
    assert [g["comision"] for g in datos["cursos"][0]["comisiones_del_tutor"]] == ["1pro3", "1pro4"]
    assert datos["cursos"][0]["tareas"] == [{"assign_id": "9", "titulo": "TP1"}]
    env = (carpeta / ".env").read_text(encoding="utf-8")
    assert "MOODLE_USER=u" in env and "MOODLE_URL=https://campus.frm.edu" in env and "ACTIVEIA_USER=ia" in env
    assert (carpeta / "catalogo.json").is_file()


def test_api_confirmar_exige_al_menos_una_comision_y_ids_reales(home, monkeypatch):
    client = _cliente()
    token = _probar(client, monkeypatch).json()["token"]
    assert client.post("/api/campus", json={"token": token, "seleccion": _seleccion((3, []))}).status_code == 400
    assert client.post("/api/campus", json={"token": token, "seleccion": _seleccion((3, [999]))}).status_code == 400
    assert client.post("/api/campus", json={"token": token, "seleccion": _seleccion((77, [1]))}).status_code == 400
    assert [c["id"] for c in config.listar_campus()] == ["tup"]           # nada se guardó


def test_api_confirmar_con_token_desconocido_o_vencido(home, monkeypatch):
    from backend import app as backend_app

    client = _cliente()
    assert client.post("/api/campus", json={"token": "nope", "seleccion": _seleccion((3, [5]))}).status_code == 410
    token = _probar(client, monkeypatch).json()["token"]
    backend_app._PENDIENTES[token]["hora"] -= backend_app._VIDA_PENDIENTE_S + 1
    assert client.post("/api/campus", json={"token": token, "seleccion": _seleccion((3, [5]))}).status_code == 410


def test_api_no_repite_un_id_existente_ni_pisa_tup(home, monkeypatch):
    client = _cliente()
    ids = []
    for nombre in ("UTN Mendoza", "UTN Mendoza", "TUP"):
        t = _probar(client, monkeypatch, nombre=nombre).json()["token"]
        ids.append(client.post("/api/campus", json={"token": t, "seleccion": _seleccion((3, [5]))}).json()["activo"])
    assert ids == ["utn-mendoza", "utn-mendoza-2", "tup-2"]


def _campus_con_catalogo(home, monkeypatch):
    client = _cliente()
    t = _probar(client, monkeypatch).json()["token"]
    client.post("/api/campus", json={"token": t, "seleccion": _seleccion((3, [5]))})
    return client


def test_editar_asignacion_lee_del_campus_y_marca_lo_elegido(home, monkeypatch):
    client = _campus_con_catalogo(home, monkeypatch)
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: _resultado(**DESCUBIERTO))
    r = client.post("/api/campus/utn-mendoza/asignacion/leer")
    assert r.status_code == 200, r.text
    elegidas = [g["comision"] for c in r.json()["cursos"] for g in c["comisiones"] if g["elegida"]]
    assert elegidas == ["1pro3"] and r.json()["tiene_seleccion"] is True


def test_editar_asignacion_guarda_conserva_otras_claves_y_deja_copia(home, monkeypatch):
    client = _campus_con_catalogo(home, monkeypatch)
    ruta = home / ".asistente-tup" / "campus" / "utn-mendoza" / "mis_datos.json"
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    datos["clickup"] = {"id": "77"}
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    r = client.put("/api/campus/utn-mendoza/asignacion", json={"seleccion": _seleccion((3, [6, 7]), (6, [8]))})
    assert r.status_code == 200, r.text
    nuevo = json.loads(ruta.read_text(encoding="utf-8"))
    assert nuevo["clickup"] == {"id": "77"}
    assert [(c["nombre"], [g["comision"] for g in c["comisiones_del_tutor"]]) for c in nuevo["cursos"]] == [
        ("Prog 1", ["1pro4", "1pro5"]), ("Prog II", ["2pro5"])]
    assert json.loads(ruta.with_name("mis_datos.json.bak").read_text(encoding="utf-8"))["clickup"] == {"id": "77"}
    # y lo que ve el resto de la app sigue al «Mis datos»
    config.set_tenant_activo("utn-mendoza")
    assert [c["nombre"] for c in client.get("/api/catalogo").json()["cursos"]] == ["Prog 1", "Prog II"]


def test_editar_asignacion_rechaza_vacio_y_campus_desconocido(home, monkeypatch):
    client = _campus_con_catalogo(home, monkeypatch)
    assert client.put("/api/campus/utn-mendoza/asignacion", json={"seleccion": _seleccion((3, []))}).status_code == 400
    assert client.put("/api/campus/no-existe/asignacion", json={"seleccion": _seleccion((3, [5]))}).status_code == 404
    assert client.post("/api/campus/no-existe/asignacion/leer").status_code == 404


def test_editar_asignacion_sin_catalogo_pide_leer_primero(home):
    config.registrar_campus("otro", "Otro", "https://o")
    r = _cliente().put("/api/campus/otro/asignacion", json={"seleccion": _seleccion((3, [5]))})
    assert r.status_code == 409


def test_leer_asignacion_sin_credenciales_guardadas(home):
    config.registrar_campus("otro", "Otro", "https://o")
    assert _cliente().post("/api/campus/otro/asignacion/leer").status_code == 400


def test_editar_tup_usa_su_env_y_conserva_sus_tareas_curadas(home, monkeypatch):
    (home / ".moodle-skill").mkdir()
    (home / ".moodle-skill" / ".env").write_text("MOODLE_USER=tutor\nMOODLE_PASS=clave\n", encoding="utf-8")
    (home / ".moodle-skill" / "mis_datos.json").write_text(json.dumps({"tutor": {"nombre": "Yo"}, "cursos": [
        {"course_id": 3, "nombre": "Prog 1", "comisiones_del_tutor": [{"comision": "1pro3", "group_id": 5}],
         "tareas": [{"assign_id": "9", "titulo": "TP curado"}]}]}), encoding="utf-8")
    visto = {}

    def fake_run(cmd, **kw):
        visto["e"] = json.loads(kw["input"])
        return _resultado(**DESCUBIERTO)

    monkeypatch.setattr(subprocess, "run", fake_run)
    client = _cliente()
    r = client.post("/api/campus/tup/asignacion/leer")
    assert r.status_code == 200 and visto["e"]["moodle_user"] == "tutor" and visto["e"]["url"] == "https://tup.test"
    assert client.put("/api/campus/tup/asignacion", json={"seleccion": _seleccion((3, [5, 6]))}).status_code == 200
    datos = json.loads((home / ".moodle-skill" / "mis_datos.json").read_text(encoding="utf-8"))
    assert datos["tutor"] == {"nombre": "Yo"} and datos["cursos"][0]["tareas"] == [{"assign_id": "9", "titulo": "TP curado"}]
    assert len(datos["cursos"][0]["comisiones_del_tutor"]) == 2 and (home / ".moodle-skill" / "mis_datos.json.bak").is_file()


# --------------------------------------------------------------------------- #
# Reconocimiento de comisiones del subproceso de alta
# --------------------------------------------------------------------------- #


class _WsFalso:
    @staticmethod
    def clasificar_grupo(nombre):
        if nombre.startswith("R-"):
            return "regional"
        return "comision" if nombre.startswith("M25 C") else "otro"


@pytest.mark.parametrize("nombre", ["M25 C4-01", "Comision_6", "Comisión 3", "C2", "1pro1", "2pro5", "1Prog5"])
def test_es_comision_reconoce_tup_y_otras_nomenclaturas(nombre):
    from backend import alta_campus

    assert alta_campus._es_comision(_WsFalso, nombre)


@pytest.mark.parametrize("nombre", ["R-Mendoza", "Grupo A", "INACTIVOS", "Rinde_Parcial2_Extra", "pro1x", ""])
def test_es_comision_descarta_regionales_y_auxiliares(nombre):
    from backend import alta_campus

    assert not alta_campus._es_comision(_WsFalso, nombre)


def test_el_subproceso_de_descubrimiento_no_abre_consola_en_windows(home, monkeypatch):
    """Regresión: bajo pythonw cada prueba de un campus hacía aparecer una ventana negra."""
    visto = {}

    def fake_run(cmd, **kw):
        visto.update(kw)
        return _resultado(**DESCUBIERTO)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(config, "es_windows", lambda: True)
    monkeypatch.setattr(subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)
    assert _cliente().post("/api/campus/probar", json=_alta_payload()).status_code == 200
    assert visto["creationflags"] == 0x08000000
    visto.clear()
    monkeypatch.setattr(config, "es_windows", lambda: False)
    assert _cliente().post("/api/campus/probar", json=_alta_payload()).status_code == 200
    assert "creationflags" not in visto


def test_consola_oculta_no_hace_nada_fuera_de_windows(monkeypatch):
    from backend import app as backend_app

    monkeypatch.setattr(config, "es_windows", lambda: False)
    assert backend_app._consola_oculta() is None  # no toca ctypes.windll (que ni existe en Linux/Mac)
