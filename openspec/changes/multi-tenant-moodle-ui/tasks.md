## 1. `backend/config.py` — tenant-aware paths

- [x] 1.1 Add `tenant_activo() -> str`: tolerant read of `~/.moodle-skill/estado.json` (same try/except pattern as `leer()`), returns `tenant_activo` field or `"tup"` on missing file/key/parse error. Verify: importing `backend.config` with a monkeypatched `HOME` pointing at an empty temp dir returns `"tup"`.
- [x] 1.2 Replace `MOODLE_SKILL_DIR`, `SALIDAS_CAMPUS`, `MIS_DATOS` module constants with `moodle_skill_dir()`, `salidas_campus()`, `mis_datos_path()` functions that compute from `HOME / ".moodle-skill"` (unchanged flat root — tenant subdirectories are the sibling repo's concern, not resolved here) each call. Verify: no remaining references to the old constant names anywhere in `backend/`.
- [x] 1.3 Add `listar_campus() -> list[dict]`: tolerant direct read of `~/.moodle-skill/tenants.json`, returns `[]` on missing/unreadable/malformed file. Verify: with no `tenants.json`, returns `[]`; with a fixture file containing a list, returns that list.

## 2. `backend/app.py` — call-site updates and `/api/campus`

- [x] 2.1 Update `_mis_datos()` to call `config.mis_datos_path()` instead of `config.MIS_DATOS`. Verify: `grep -n "config.MIS_DATOS"` in `backend/app.py` returns nothing.
- [x] 2.2 Update `_copiar_informes()` to call `config.salidas_campus()` instead of `config.SALIDAS_CAMPUS`. Verify: same grep check for `config.SALIDAS_CAMPUS` in that function.
- [x] 2.3 Update `_permitida()`'s `bases` list and `_es_de_salidas()` to call `config.salidas_campus()` instead of `config.SALIDAS_CAMPUS`. Verify: `grep -n "config.SALIDAS_CAMPUS"` in `backend/app.py` returns nothing anywhere in the file.
- [x] 2.4 Update `tarea()`'s `bases = [cfg["carpeta_trabajo"], config.SALIDAS_CAMPUS]` to use `config.salidas_campus()`. Verify: same grep check.
- [x] 2.5 Add `GET /api/campus` returning `{"campus": config.listar_campus(), "activo": config.tenant_activo()}`. Verify: with the venv's `python.exe -c` importing `backend.app` and calling the route function directly (or a short script hitting the FastAPI `TestClient`), confirm the response shape with no `tenants.json`/`estado.json` present is `{"campus": [], "activo": "tup"}`.

## 3. `backend/recetas.py` — `campus` field type and receta wiring

- [x] 3.1 Update the module docstring's `campos` type list to include `campus`. Verify: docstring text includes the word `campus` in the types enumeration.
- [x] 3.2 Add a shared `_CAMPUS_OPC` field definition (`tipo: "campus"`, optional, sensible `etiqueta`/`ayuda`) near the existing `_CURSO`/`_COMISION_OPC` helpers. Verify: defined once, reused across recetas (no duplicated literal dicts).
- [x] 3.3 Add `_CAMPUS_OPC` to the `campos` list and append a `[[...]]` optional prompt block referencing `usar_campus` to the `pedido` text, for each of the 8 `campus`-category recetas: `pendientes`, `inactivos`, `mensajes`, `informe`, `panorama`, `corregir`, `auditar_aula`, `campus_libre`. Verify: `grep -c "_CAMPUS_OPC" backend/recetas.py` reports 8 usages in `campos` lists, and each of those 8 recetas' `pedido` string contains a `[[...{campus}...]]` block.
- [x] 3.4 Verify `armar_pedido`/`faltantes` need no code changes for the new field type (it behaves as a plain optional field for substitution purposes) — confirm by running a short script importing `backend.recetas`, calling `armar_pedido` on one updated receta with and without a `campus` value, and checking the `[[...]]` block is included/omitted correctly.

## 4. `web/app.js` — campus selector

- [x] 4.1 In `cargar()`, add a third parallel fetch `api('/api/campus')` into `E.campus` alongside `/api/estado` and `/api/catalogo`. Verify: read the updated `Promise.all` call and confirm `E.campus` is assigned from it.
- [x] 4.2 In `campo()`, add a branch for `c.tipo === 'campus'`: render a `<select>` listing `E.campus.campus` (id/nombre), pre-select the option matching `E.campus.activo`, and wire `set()` on change — modeled directly on the existing `curso` branch's structure (plain select, no `bus` dependency needed). Verify: the new branch mirrors the `curso` branch's shape (options built from a list, `set()` called on change, first option handling when the list is empty).
- [x] 4.3 Confirm no other part of `app.js` needs to change (recetas rendering, `verReceta`, `empezar` already pass `c` generically to `campo()`). Verify: read through `verReceta`/`empezar` and confirm the `campus` field id flows through `valores` like any other field with no special-casing needed.

## 5. Verification and documentation

- [x] 5.1 Run `openspec validate multi-tenant-moodle-ui --strict` and confirm it passes.
- [x] 5.2 Standalone script (in the repo's `.venv`) importing `backend.config` with monkeypatched `HOME`/`config.HOME` pointing at a temp directory: confirm `tenant_activo()` returns `"tup"` with no `estado.json`, `listar_campus()` returns `[]` with no `tenants.json`, and both correctly reflect fixture files written to that temp directory when present. Must not touch the real `~/.moodle-skill/`.
- [x] 5.3 Confirm `backend/app.py` and `backend/recetas.py` import cleanly and the FastAPI app object constructs without error (e.g. `python -c "from backend import app"`), catching any syntax/reference errors from the refactor.
