"""Small helpers to read KiCad .kicad_sym libraries (S-expressions) without KiCad itself."""
import os
import re

KICAD = os.path.expanduser("~/Applications/KiCad/KiCad.app/Contents/SharedSupport")


def parse_sexpr(text):
    """Parses an S-expression into nested lists of strings (quoted strings keep no quotes)."""
    tokens = re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+', text)
    stack = [[]]
    for tok in tokens:
        if tok == "(":
            stack.append([])
        elif tok == ")":
            done = stack.pop()
            stack[-1].append(done)
        elif tok.startswith('"'):
            stack[-1].append(Str(tok[1:-1].replace('\\"', '"').replace("\\\\", "\\")))
        else:
            stack[-1].append(tok)
    return stack[0]


class Str(str):
    """A token that was quoted in the source, so it is written back quoted."""


def dump(node, indent=0):
    if isinstance(node, list):
        if not node:
            return "()"
        inner = " ".join(dump(n, indent + 1) for n in node)
        if len(inner) < 100 and not any(isinstance(n, list) and len(n) > 3 for n in node):
            return "(" + inner + ")"
        pad = "\n" + "  " * (indent + 1)
        return "(" + dump(node[0], indent + 1) + "".join(pad + dump(n, indent + 1) for n in node[1:]) + ")"
    if isinstance(node, Str):
        return '"' + node.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return node


def find(node, key):
    return [n for n in node if isinstance(n, list) and n and n[0] == key]


def first(node, key):
    found = find(node, key)
    return found[0] if found else None


_lib_cache = {}


def load_library(path):
    if path not in _lib_cache:
        _lib_cache[path] = parse_sexpr(open(path, encoding="utf-8").read())[0]
    return _lib_cache[path]


def symbol_lib_path(lib):
    local = os.path.join(os.path.dirname(__file__), "..", "lib", lib + ".kicad_sym")
    if os.path.exists(local):
        return os.path.abspath(local)
    return os.path.join(KICAD, "symbols", lib + ".kicad_sym")


def get_symbol(lib_id):
    """Returns the symbol definition with `extends` resolved, renamed to the full lib_id."""
    lib, name = lib_id.split(":")
    library = load_library(symbol_lib_path(lib))
    symbols = {s[1]: s for s in find(library, "symbol")}
    sym = symbols[name]
    ext = first(sym, "extends")
    if ext:
        parent = symbols[ext[1]]
        # Child keeps its own properties; graphics/pins come from the parent (renamed units).
        merged = [n for n in sym if not (isinstance(n, list) and n and n[0] == "extends")]
        props = {p[1] for p in find(sym, "property")}
        for n in parent[2:]:
            if isinstance(n, list) and n and n[0] == "property" and n[1] in props:
                continue
            if isinstance(n, list) and n and n[0] == "symbol":
                n = [n[0], Str(n[1].replace(ext[1], name, 1))] + n[2:]
            merged.append(n)
        sym = merged
    out = [sym[0], Str(lib_id)] + sym[2:]
    return out


def symbol_pins(sym):
    """[(number, name, electrical_type, x, y, angle)] across all units."""
    pins = []
    for unit in find(sym, "symbol"):
        for pin in find(unit, "pin"):
            at = first(pin, "at")
            name = first(pin, "name")[1]
            number = first(pin, "number")[1]
            pins.append((str(number), str(name), pin[1], float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0))
    return pins
