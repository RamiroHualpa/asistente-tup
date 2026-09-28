## Why

The sibling `moodle-tutor` MCP server (in a separate repo, `Skill-Moodle-dev`) is gaining multi-tenant support: a tutor will be able to register more than one Moodle campus (`tenants.json`) and switch which one is "active" (`estado.json` → `tenant_activo`), with per-tenant data isolation under `~/.moodle-skill/<tenant_id>/`. Today `asistente-tup-dev`'s backend and frontend assume a single, flat `~/.moodle-skill/` layout and have no way to show or select a campus. Without this change, the UI would keep reading/writing the old flat paths and the tutor would have no way to see which campus is active or pick a different one when building a receta prompt.

## What Changes

- `backend/config.py`: add a `tenant_activo()` helper that reads `~/.moodle-skill/estado.json` and defaults to `"tup"` when absent (same tolerant-read pattern already used by `leer()`). Convert `MOODLE_SKILL_DIR`, `SALIDAS_CAMPUS`, and `MIS_DATOS` from module-level constants into functions (`moodle_skill_dir()`, `salidas_campus()`, `mis_datos_path()`) so paths reflect the currently active tenant instead of being frozen at import time. Add `listar_campus()` reading `~/.moodle-skill/tenants.json`, tolerant of a missing file (returns `[]`).
- `backend/app.py`: update all call sites that referenced the old constants (`_mis_datos`, `_copiar_informes`, `_permitida`, `_es_de_salidas`, `tarea()`'s `bases` list) to call the new functions instead. Add `GET /api/campus` returning `{"campus": [...], "activo": "<tenant_id>"}`.
- `backend/recetas.py`: extend the `campos` type vocabulary with a `campus` field type (docstring + prompt-building support via the existing `[[...]]` optional-block substitution — no direct MCP calls). Wire an optional `campus` field into all 8 recetas under the `campus` skill category (`pendientes`, `inactivos`, `mensajes`, `informe`, `panorama`, `corregir`, `auditar_aula`, `campus_libre`).
- `web/app.js`: `cargar()` fetches `/api/campus` into `E.campus`; `campo()` gets a new `campus` branch (plain `<select>`, active tenant pre-selected), modeled on the existing `curso` branch.

## Capabilities

### New Capabilities
- `multi-tenant-moodle-ui`: tenant-aware config path resolution with a safe single-tenant default, a `GET /api/campus` listing endpoint, and a `campus` receta field type that lets the tutor pick which Moodle campus a prompt should target — without this repo ever calling Moodle-tenant MCP tools directly (it only builds prompts referencing `usar_campus`).

### Modified Capabilities
(none — no existing specs in this repo yet)

## Impact

- Affected files: `backend/config.py`, `backend/app.py`, `backend/recetas.py`, `web/app.js`.
- No new dependencies, no encryption, no changes to `main` branch.
- Backward compatible: an install with no `~/.moodle-skill/estado.json` or `tenants.json` behaves exactly as before (`tenant_activo()` → `"tup"`, `listar_campus()` → `[]`).
- Does not implement `agregar_campus`/`usar_campus` MCP tools themselves (those live in the sibling `Skill-Moodle-dev` repo); this repo only reads tenant state files and builds natural-language prompts that reference those tools.
