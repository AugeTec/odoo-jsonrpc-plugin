---
name: odoo-jsonrpc
description: Usar para leer o escribir datos en cualquier base de datos Odoo vía JSON-RPC — autenticar, ejecutar search_read/execute_kw, descubrir campos, hacer barridos de detección e investigar incidencias de datos. Aplica a cualquier cliente/instancia Odoo.
---

# Comunicarse con una base Odoo (JSON-RPC)

El plugin incluye un cliente sin dependencias en `scripts/odoo.py` (junto a este SKILL.md; usa la ruta del directorio base de la skill).

## 0. Credenciales — nunca asumidas

Pedir al usuario, por cada base nueva: **URL** (`https://<host>` o `.../jsonrpc`), **db**, **usuario** y **password o API key**.

- Pasarlas por variables de entorno (`ODOO_URL`, `ODOO_DB`, `ODOO_USER`, `ODOO_PASSWORD`) o por un `odoo_config.json` en el directorio de trabajo:
  ```json
  {"url": "https://<host>/jsonrpc", "db": "<db>", "username": "<login>", "password": "<password_o_api_key>"}
  ```
- No incluirlas en el repositorio (el `.gitignore` del plugin ya excluye `odoo_config.json`). Sí se puede documentar lo no sensible: URL, nombre de db, IDs de modelos/tipos ya identificados.

## 1. Probar la conexión primero

```bash
python3 <skill_dir>/scripts/odoo.py res.users search_read '[[["login","=","<login>"]]]' '{"fields":["id","name","login"]}'
```
Si falla por red, verificar que el egress del entorno alcance el host.

## 2. Patrones CLI

`python3 odoo.py <modelo> <método> '<args_json>' '<kwargs_json>'`

- **Buscar + leer**: `search_read '[[["campo","op","valor"]]]' '{"fields":[...],"limit":50}'`
- **Leer ids**: `read '[[1,2]]' '{"fields":[...]}'`
- **Contar antes de traer todo**: `search_count '[[[...]]]'`
- **Relaciones en el dominio** con punto: `["partner_id.country_id.code","=","MX"]`
- **Crear**: `create '[{"campo": valor}]'` · **Escribir**: `write '[[ids], {"campo": valor}]'`
- **Descubrir campos** antes de adivinar: `fields_get '[]' '{"attributes":["string","type","relation"]}'`. Los nombres varían entre modelos (p. ej. `stock.move` no tiene `name`, usa `reference`).
- Los errores traen el traceback en `error.data.debug`; léelo, suele indicar el campo o modelo erróneo.

## 3. Investigaciones de varios pasos: script, no CLI encadenado

Escribir un script que haga `sys.path.insert(0, "<skill_dir>/scripts")`, `from odoo import connect` y cruce todo en memoria:

```python
c = connect()
sospechosos = c.search_read("stock.move", [["state","=","assigned"]], ["id","picking_id"])
ids = {m["picking_id"][0] for m in sospechosos if m["picking_id"]}
pickings = c.search_read("stock.picking", [["id","in",list(ids)]], ["name","state"])  # un solo batch
```
1. Dominio acotado para los sospechosos. 2. Extraer llaves en un `set`. 3. Un solo `read` batch de lo relacionado. 4. Aplicar la lógica de negocio en Python, no en el dominio.

## 4. Seguridad al escribir en producción

- No escribir `state` como atajo; usar el flujo real (`action_confirm`, `action_assign`, `button_validate`) salvo excepción documentada por el negocio.
- Antes de modificar datos, presentar el diagnóstico completo y esperar confirmación explícita del usuario.
- Documentar hallazgos relevantes (query, IDs, diagnóstico, si se corrigió) sin credenciales.
