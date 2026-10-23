#!/usr/bin/env python3
"""Descubrimiento genérico de flujos de trabajo en Odoo, solo por introspección.

Uso:  discover.py <comando> <modelo> [opciones]
  profile  <modelo>            estados (con conteo), botones del form, automatizaciones
  graph    <modelo> [--depth N] documentos enlazados (solo enlaces con datos reales)
  trans    <modelo>            transiciones de estado reales (mail.tracking.value)
  trace    <modelo> <id> [--depth N]  sigue un registro real por todos sus enlaces
Credenciales: igual que odoo.py (ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD).
"""
import os, re, sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "odoo-jsonrpc", "scripts"))
from odoo import connect

# Modelos de infraestructura: no son "documentos" de negocio.
NOISE = ("ir.", "res.", "mail.", "base.", "bus.", "web.", "uom.", "product.",
         "digest.", "portal.", "rating.", "utm.", "iap.", "format.", "report.",
         "onboarding.", "spreadsheet.", "documents.", "snailmail.", "sms.")
EXTRA = ("res.partner", "product.product")  # se muestran como contexto, sin recorrer

c = connect()
_cache = {}


def fields(model):
    if model not in _cache:
        _cache[model] = c.call(model, "fields_get", [],
                               attributes=["string", "type", "relation", "selection", "store"])
    return _cache[model]


def state_fields(model):
    return [k for k, v in fields(model).items()
            if v["type"] == "selection" and v.get("store", True) and v.get("selection")
            and re.search(r"(^|_)(state|status|stage)$", k)]


def doc_like(model):
    """Modelo de negocio: no ruido, con campo de estado o al menos registros."""
    if model.startswith(NOISE) or model.endswith((".line", ".wizard")) or ".wizard" in model:
        return False
    try:
        return bool(state_fields(model)) and c.call(model, "search_count", [[]]) > 0
    except Exception:
        return False


def links(model):
    """Campos relacionales hacia otros documentos, con cuántos registros los usan."""
    out = []
    for k, v in fields(model).items():
        rel = v.get("relation")
        if v["type"] not in ("many2one", "one2many", "many2many") or not rel or not v.get("store", True):
            continue
        if not doc_like(rel):
            continue
        try:
            n = c.call(model, "search_count", [[[k, "!=", False]]])
        except Exception:
            continue
        if n:
            out.append((k, v["type"], rel, n))
    return out


def buttons(model):
    try:
        arch = c.call(model, "get_views", [[[False, "form"]]])["views"]["form"]["arch"]
    except Exception:
        return []
    res = {}
    for m in re.finditer(r"<button\b([^>]*)>", arch):
        a = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
        if a.get("type") in ("object", "action") and a.get("name"):
            res.setdefault(a["name"], (a.get("string", ""), a.get("invisible", ""), a.get("groups", "")))
    return [(n, *v) for n, v in res.items()]


def cmd_profile(model):
    print(f"## {model}  ({c.call(model, 'search_count', [[]])} registros)")
    for sf in state_fields(model):
        sel = dict(fields(model)[sf]["selection"])
        cnt = {r[sf]: r[sf + "_count"] if sf + "_count" in r else r["__count"]
               for r in c.call(model, "read_group", [[], [sf], [sf]])}
        print(f"estado `{sf}`: " + " → ".join(f"{k}({cnt.get(k, 0)})" for k in sel))
    print("botones (acciones de flujo):")
    for n, s, inv, g in buttons(model):
        print(f"  {n:32} {s!r:28} invisible={inv[:60]!r}")
    for m, dom in (("base.automation", [["model_id.model", "=", model]]),
                   ("ir.actions.server", [["model_id.model", "=", model], ["usage", "!=", "ir_actions_server"]]),
                   ("ir.cron", [["model_id.model", "=", model]]),
                   ("mail.template", [["model", "=", model]])):
        try:
            rows = c.search_read(m, dom, ["name"], limit=20)
        except Exception:
            continue
        if rows:
            print(f"{m}: " + "; ".join(r["name"] for r in rows))


def cmd_graph(model, depth=2):
    seen, queue = {model}, [(model, 0)]
    while queue:
        cur, d = queue.pop(0)
        if d >= depth:
            continue
        for k, t, rel, n in links(cur):
            print(f"{cur} --{k} ({t}, {n} regs)--> {rel}")
            if rel not in seen:
                seen.add(rel)
                queue.append((rel, d + 1))


def cmd_trans(model, limit=5000):
    rows = c.search_read("mail.tracking.value",
                         [["mail_message_id.model", "=", model], ["field_id.name", "in", state_fields(model)]],
                         ["old_value_char", "new_value_char"], limit=limit)
    if not rows:
        print("sin tracking de estado (el modelo no usa mail.thread con tracking en el estado)")
    for (a, b), n in Counter((r["old_value_char"], r["new_value_char"]) for r in rows).most_common():
        print(f"  {a or '∅'} → {b}: {n}")


def cmd_trace(model, rid, depth=2, seen=None, indent=0):
    seen = seen if seen is not None else set()
    if (model, rid) in seen:
        return
    seen.add((model, rid))
    sf = state_fields(model)
    rec = c.call(model, "read", [[rid]], fields=sf + ["display_name"])[0]
    print("  " * indent + f"{model}#{rid} {rec['display_name']} " + " ".join(f"[{rec[s]}]" for s in sf))
    if indent // 2 >= depth:
        return
    for k, t, rel, _n in links(model):
        val = c.call(model, "read", [[rid]], fields=[k])[0][k]
        ids = [val[0]] if t == "many2one" and val else (val if t != "many2one" else [])
        for i in ids[:5]:
            print("  " * indent + f"  ({k})")
            cmd_trace(rel, i, depth, seen, indent + 2)


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 2:
        sys.exit(__doc__)
    depth = int(a[a.index("--depth") + 1]) if "--depth" in a else 2
    {"profile": lambda: cmd_profile(a[1]), "graph": lambda: cmd_graph(a[1], depth),
     "trans": lambda: cmd_trans(a[1]), "trace": lambda: cmd_trace(a[1], int(a[2]), depth)}[a[0]]()
