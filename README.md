# odoo-tools — plugin `odoo-jsonrpc`

Skill de Claude Code + cliente Python (solo stdlib) para consultar y escribir en cualquier base Odoo vía JSON-RPC.

## Instalar

Desde un repositorio git (publica esta carpeta):
```
/plugin marketplace add <usuario>/<repo>
/plugin install odoo-jsonrpc@odoo-tools
```
Desde una ruta local:
```
/plugin marketplace add /ruta/a/odoo-jsonrpc-plugin
/plugin install odoo-jsonrpc@odoo-tools
```

## Credenciales

No se incluyen ni se guardan. Define `ODOO_URL`, `ODOO_DB`, `ODOO_USER`, `ODOO_PASSWORD` o crea `odoo_config.json` en tu directorio de trabajo (ver `plugins/odoo-jsonrpc/skills/odoo-jsonrpc/SKILL.md`).

## Uso directo

```
python3 plugins/odoo-jsonrpc/skills/odoo-jsonrpc/scripts/odoo.py res.partner search_read '[[]]' '{"fields":["name"],"limit":5}'
```
