#!/usr/bin/env python3
"""Cliente JSON-RPC mínimo para Odoo (solo stdlib).

CLI:  python3 odoo.py <modelo> <método> ['<args_json>' ['<kwargs_json>']]
Como módulo:  from odoo import connect; c = connect(); c.call("res.partner", "search_read", [[]], limit=5)

Credenciales (nunca se guardan en el plugin), en orden de prioridad:
  1. Variables de entorno ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD
  2. Archivo JSON indicado en ODOO_CONFIG
  3. ./odoo_config.json o ./config.json en el directorio actual
     {"url": "https://host/jsonrpc", "db": "...", "username": "...", "password": "..."}
"""
import json, os, sys, urllib.request


def load_config():
    env = {k: os.environ.get("ODOO_" + v) for k, v in
           (("url", "URL"), ("db", "DB"), ("username", "USER"), ("password", "PASSWORD"))}
    if all(env.values()):
        cfg = env
    else:
        paths = [os.environ.get("ODOO_CONFIG"), "odoo_config.json", "config.json"]
        path = next((p for p in paths if p and os.path.isfile(p)), None)
        if not path:
            sys.exit("Sin credenciales: define ODOO_URL/ODOO_DB/ODOO_USER/ODOO_PASSWORD "
                     "o crea odoo_config.json en el directorio actual.")
        with open(path) as f:
            cfg = json.load(f)
    url = cfg["url"].rstrip("/")
    if not url.endswith("/jsonrpc"):
        url += "/jsonrpc"
    cfg["url"] = url
    return cfg


def jsonrpc(url, service, method, args, timeout=60):
    payload = {"jsonrpc": "2.0", "method": "call", "id": 1,
               "params": {"service": service, "method": method, "args": args}}
    req = urllib.request.Request(url, json.dumps(payload).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode())
    if "error" in body:
        raise RuntimeError(json.dumps(body["error"], indent=2, ensure_ascii=False))
    return body["result"]


class Odoo:
    def __init__(self, cfg):
        self.cfg = cfg
        self.uid = jsonrpc(cfg["url"], "common", "authenticate",
                           [cfg["db"], cfg["username"], cfg["password"], {}])
        if not self.uid:
            raise RuntimeError("Autenticación fallida (revisa db, usuario y password/API key)")

    def call(self, model, method, args=None, **kwargs):
        c = self.cfg
        return jsonrpc(c["url"], "object", "execute_kw",
                       [c["db"], self.uid, c["password"], model, method, args or [], kwargs])

    def search_read(self, model, domain=None, fields=None, **kw):
        return self.call(model, "search_read", [domain or []], fields=fields or [], **kw)


def connect(cfg=None):
    return Odoo(cfg or load_config())


def main():
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    model, method = sys.argv[1:3]
    args = json.loads(sys.argv[3]) if len(sys.argv) > 3 else []
    kwargs = json.loads(sys.argv[4]) if len(sys.argv) > 4 else {}
    print(json.dumps(connect().call(model, method, args, **kwargs), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
