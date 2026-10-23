# odoo-tools — plugin `odoo-jsonrpc`

Skill de Claude Code + cliente Python (solo stdlib) para consultar y escribir en cualquier base Odoo vía JSON-RPC.

## Instalar

Desde GitHub (dentro de Claude Code):
```
/plugin marketplace add AugeTec/odoo-jsonrpc-plugin
/plugin install odoo-jsonrpc@odoo-tools
```
También con la URL completa: `/plugin marketplace add git@github.com:AugeTec/odoo-jsonrpc-plugin.git` (SSH) o `https://github.com/AugeTec/odoo-jsonrpc-plugin.git` (HTTPS).

Desde una copia local:
```
git clone git@github.com:AugeTec/odoo-jsonrpc-plugin.git
/plugin marketplace add ./odoo-jsonrpc-plugin
/plugin install odoo-jsonrpc@odoo-tools
```

Actualizar: `/plugin marketplace update odoo-tools`.

Skills incluidas: `odoo-jsonrpc` (conexión y consultas) y `odoo-workflow-design` (diseño y prueba de flujos de trabajo).

## Credenciales

Guárdalas una vez en el llavero del SO: `python3 plugins/odoo-jsonrpc/scripts/odoo.py --save [perfil]` (sin llavero usa `~/.config/odoo-jsonrpc/profiles.json` con permisos 0600). También sirven `ODOO_URL`, `ODOO_DB`, `ODOO_USER`, `ODOO_PASSWORD` u `odoo_config.json` (ver `plugins/odoo-jsonrpc/skills/odoo-jsonrpc/SKILL.md`). Nunca se incluyen en el repositorio.

## Uso directo

```
python3 plugins/odoo-jsonrpc/scripts/odoo.py res.partner search_read '[[]]' '{"fields":["name"],"limit":5}'
```

## Licencia

Apache License 2.0 — ver [LICENSE](LICENSE).
