#!/usr/bin/env python3
"""Cliente JSON-RPC mínimo para Odoo (solo stdlib).

CLI:  python3 odoo.py <modelo> <método> ['<args_json>' ['<kwargs_json>']]
Como módulo:  from odoo import connect; c = connect(); c.call("res.partner", "search_read", [[]], limit=5)

Credenciales, en orden de prioridad:
  1. Variables de entorno ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD
  2. Archivo JSON indicado en ODOO_CONFIG, o ./odoo_config.json / ./config.json
     {"url": "https://host/jsonrpc", "db": "...", "username": "...", "password": "..."}
  3. Perfil guardado (ODOO_PROFILE, o el único/"default"), ver abajo.

Almacenamiento seguro de perfiles:
  python3 odoo.py --save [perfil]    guarda url/db/usuario/password (de ODOO_* o por prompt)
  python3 odoo.py --profiles         lista perfiles (sin passwords)
  python3 odoo.py --forget <perfil>  borra un perfil
Backend: llavero del SO (Linux: secret-tool/libsecret; macOS: security). Si no hay llavero,
archivo ~/.config/odoo-jsonrpc/profiles.json con permisos 0600 (aviso al guardar).
"""
import getpass, json, os, shutil, subprocess, sys, urllib.request

SERVICE = "odoo-jsonrpc"
INDEX = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
                     "odoo-jsonrpc", "profiles.json")


def _backend():
    if sys.platform == "darwin" and shutil.which("security"):
        return "macos"
    if shutil.which("secret-tool"):
        return "libsecret"
    return "file"


def _read_index():
    try:
        with open(INDEX) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _write_index(idx):
    os.makedirs(os.path.dirname(INDEX), mode=0o700, exist_ok=True)
    fd = os.open(INDEX, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(idx, f, indent=2)
    os.chmod(INDEX, 0o600)


def save_profile(name, cfg):
    """El índice guarda solo datos no sensibles; el password va al llavero si existe."""
    be = _backend()
    entry = {k: cfg[k] for k in ("url", "db", "username")}
    if be == "libsecret":
        subprocess.run(["secret-tool", "store", "--label", f"Odoo {name}", "service", SERVICE,
                        "profile", name], input=cfg["password"].encode(), check=True)
    elif be == "macos":  # `security` no lee el secreto por stdin: queda un instante en argv
        subprocess.run(["security", "add-generic-password", "-U", "-s", SERVICE, "-a", name,
                        "-w", cfg["password"]], check=True, capture_output=True)
    else:
        entry["password"] = cfg["password"]
    idx = _read_index()
    idx[name] = entry
    _write_index(idx)
    return be


def _stored_password(name):
    be = _backend()
    cmd = {"libsecret": ["secret-tool", "lookup", "service", SERVICE, "profile", name],
           "macos": ["security", "find-generic-password", "-s", SERVICE, "-a", name, "-w"]}.get(be)
    if not cmd:
        return None
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout.rstrip("\n") if r.returncode == 0 and r.stdout else None


def load_profile(name=None):
    idx = _read_index()
    name = name or os.environ.get("ODOO_PROFILE") or (
        "default" if "default" in idx else next(iter(idx)) if len(idx) == 1 else None)
    if not name or name not in idx:
        return None
    cfg = dict(idx[name])
    cfg.setdefault("password", _stored_password(name))
    if not cfg["password"]:
        sys.exit(f"Perfil '{name}': no se encontró el password en el llavero; vuelve a guardarlo con --save")
    return cfg


def forget_profile(name):
    idx = _read_index()
    if idx.pop(name, None) is None:
        sys.exit(f"Perfil '{name}' no existe")
    be = _backend()
    if be == "libsecret":
        subprocess.run(["secret-tool", "clear", "service", SERVICE, "profile", name])
    elif be == "macos":
        subprocess.run(["security", "delete-generic-password", "-s", SERVICE, "-a", name],
                       capture_output=True)
    _write_index(idx)


def cli_save(name):
    cfg = {}
    for key, env, label in (("url", "ODOO_URL", "URL"), ("db", "ODOO_DB", "DB"),
                            ("username", "ODOO_USER", "Usuario")):
        cfg[key] = os.environ.get(env) or input(f"{label}: ")
    cfg["password"] = os.environ.get("ODOO_PASSWORD") or getpass.getpass("Password/API key: ")
    be = save_profile(name, cfg)
    print(f"Perfil '{name}' guardado ({be})." + (
        " AVISO: sin llavero del SO; el password queda en un archivo 0600 en " + INDEX
        if be == "file" else ""))


def load_config():
    env = {k: os.environ.get("ODOO_" + v) for k, v in
           (("url", "URL"), ("db", "DB"), ("username", "USER"), ("password", "PASSWORD"))}
    if all(env.values()):
        cfg = env
    else:
        paths = [os.environ.get("ODOO_CONFIG"), "odoo_config.json", "config.json"]
        path = next((p for p in paths if p and os.path.isfile(p)), None)
        if path:
            with open(path) as f:
                cfg = json.load(f)
        else:
            cfg = load_profile()
            if not cfg:
                sys.exit("Sin credenciales: define ODOO_URL/ODOO_DB/ODOO_USER/ODOO_PASSWORD, "
                         "crea odoo_config.json, o guarda un perfil con: odoo.py --save")
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
    if len(sys.argv) > 1 and sys.argv[1] == "--save":
        return cli_save(sys.argv[2] if len(sys.argv) > 2 else "default")
    if len(sys.argv) > 1 and sys.argv[1] == "--profiles":
        for n, e in _read_index().items():
            print(f"{n}: {e['username']}@{e['db']} {e['url']}")
        return
    if len(sys.argv) > 2 and sys.argv[1] == "--forget":
        return forget_profile(sys.argv[2])
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    model, method = sys.argv[1:3]
    args = json.loads(sys.argv[3]) if len(sys.argv) > 3 else []
    kwargs = json.loads(sys.argv[4]) if len(sys.argv) > 4 else {}
    print(json.dumps(connect().call(model, method, args, **kwargs), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
