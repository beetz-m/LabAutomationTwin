"""A pretty-printer for LDL and CRAM/RPL Lisp, following Common Lisp / Emacs indentation conventions.

  * forms with a body (`seq`, `par`, `with-policy`, `let*`, ...) put their distinguished arguments on the first line
    (or indented by 4) and their body indented by 2 (Emacs `lisp-indent-function` with &body);
  * designators `(an action (type ...) ...)` break with one slot per line, indented by 4 (CRAM style);
  * other calls align their arguments under the first argument;
  * a form that fits within the width stays on one line;
  * comments are kept: own-line comments where they were, trailing comments after their form;
  * LDL annotations (`:column validity`, `:establishable`, ...) and keyword arguments stay with the item they qualify.

    from rsa.sexp_pretty import pretty
    print(pretty(open("challenge_rescue.ldl").read(), mode="ldl"))
"""

from __future__ import annotations

from typing import Any, List

WIDTH = 100
DET = {"a", "an", "the", "some", "each"}
PREFIXES = {"'", "`", ",", ",@", "#'"}
#: body forms that keep their first distinguished argument on the head line when the whole does not fit
ATTACH = {"let*", "let", "with-retry-counters", "with-policy", "scope", "whenever", "do-retry", "when", "unless", "case"}

#: number of distinguished arguments before the body (Emacs lisp-indent-function)
BODY = {
    # RPL / CRAM
    "seq": 0, "par": 0, "pursue": 0, "try-in-order": 0, "try-all": 0, "partial-order": 1, "with-policy": 1,
    "whenever": 1, "wait-for": 1, "with-failure-handling": 1, "with-retry-counters": 1, "do-retry": 1,
    "unwind-protect": 1, "def-top-level-cram-function": 2, "def-cram-function": 2, "with-process-modules-running": 1,
    "scope": 1, ":tag": 1, "let*": 1, "let": 1, "case": 1, "when": 1, "unless": 1, "lambda": 1, "defmacro": 2,
    "define-condition": 2, "defparameter": 1, "defun": 2, "progn": 0, "def-action-plan": 2,
    # LDL
    "contract": 1, "process-model": 1, "meta-model": 1, "rule": 1, "treatment": 1, "on": 1, "requires": 0,
    "prevents": 0, "maintains": 0, "achieves": 0, "goal": 0, "given": 0, "entities": 0, "steps": 0, "quality": 0,
    "handles": 0, "signals": 0, "faults": 0, "roles": 0, "instrument": 0, "when-": 0,
}
#: LDL annotations and Lisp keyword arguments: how many following atoms belong to the keyword
ARITY = {"ldl": {":column": 1, ":tolerance": 2, ":establishable": 0, ":consequential": 0},
         "lisp": {":grade": 1, ":consequential": 1, ":description": 1, ":initarg": 1, ":reader": 1, ":initform": 1,
                  ":documentation": 1, ":name": 1, ":value": 1, ":cause": 1}}


class Cmt(str):
    """An own-line comment."""


class TC:
    """A form with a trailing comment."""
    def __init__(self, form, text):
        self.form, self.text = form, text


class Pre:
    """A prefixed form: 'x `x ,x ,@x #'x."""
    def __init__(self, prefix, form):
        self.prefix, self.form = prefix, form


class Blank:
    pass


# ------------------------------------------------------------------------------------------------- reading
def parse(text: str) -> List[Any]:
    out: List[Any] = []
    stack = [out]
    i, n = 0, len(text)
    line_has_code = False
    pending_prefix = None
    blank_run = 0
    while i < n:
        ch = text[i]
        if ch == "\n":
            if not line_has_code:
                blank_run += 1
                if blank_run == 1 and len(stack) == 1 and out and not isinstance(out[-1], Blank):
                    out.append(Blank())
            line_has_code = False
            i += 1
            continue
        if ch in " \t\r":
            i += 1
            continue
        blank_run = 0
        if ch == ";":
            j = text.find("\n", i)
            j = n if j < 0 else j
            c = text[i:j].rstrip()
            cur = stack[-1]
            if line_has_code and len(cur) == 1 and isinstance(cur[0], str) and len(stack) > 1:
                cur.append(Cmt(";; " + c.lstrip(";").strip()))   # a comment after the head describes the body
            elif line_has_code and cur and not isinstance(cur[-1], (Cmt, Blank)):
                prev = cur[-1]
                cur[-1] = TC(prev.form, prev.text + " " + c.lstrip(";").strip()) if isinstance(prev, TC) else TC(prev, c.lstrip(";").strip())
            elif line_has_code and len(stack) > 1 and not cur:
                cur.append(Cmt(c.lstrip(";").strip()))          # right after an opening paren
            else:
                cur.append(Cmt(c))
            i = j
            continue
        line_has_code = True
        if ch == '"':
            j = i + 1
            while text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            tok = text[i:j + 1]
            i = j + 1
            stack[-1].append(tok)
            continue
        if ch == "(":
            lst: List[Any] = []
            stack[-1].append(Pre(pending_prefix, lst) if pending_prefix else lst)
            pending_prefix = None
            stack.append(lst)
            i += 1
            continue
        if ch == ")":
            stack.pop()
            i += 1
            continue
        j = i
        while j < n and not text[j].isspace() and text[j] not in '();"':
            j += 1
        tok = text[i:j]
        i = j
        if tok in PREFIXES and i < n and text[i] == "(":
            pending_prefix = tok
            continue
        stack[-1].append(tok)
    return out


# ------------------------------------------------------------------------------------------------- printing
def has_comment(x) -> bool:
    if isinstance(x, (Cmt, TC)):
        return True
    if isinstance(x, Pre):
        return has_comment(x.form)
    return isinstance(x, list) and any(has_comment(e) for e in x)


def flat(x) -> str:
    if isinstance(x, Pre):
        return x.prefix + flat(x.form)
    if isinstance(x, list):
        return "(" + " ".join(flat(e) for e in x) + ")"
    return str(x)


def groups(items, mode):
    """Group a keyword with the atoms that belong to it, and an LDL annotation with the item before it."""
    out = []
    ar = ARITY[mode]
    i = 0
    while i < len(items):
        e = items[i]
        if isinstance(e, str) and not isinstance(e, Cmt) and e in ar:
            k = ar[e]
            g = [e] + items[i + 1:i + 1 + k]
            i += 1 + k
            if mode == "ldl" and out and not isinstance(out[-1][-1], (Cmt, Blank)):
                out[-1] += g                   # annotation stays with the item it qualifies
            else:
                out.append(g)
            continue
        out.append([e])
        i += 1
    return out


def pp(x, col: int, mode: str, width: int = WIDTH) -> List[str]:
    """Lines for x; the first starts at `col` (no indentation in the string), the rest carry absolute indentation."""
    if isinstance(x, Cmt):
        return [str(x)]
    if isinstance(x, TC):
        lines = pp(x.form, col, mode, width)
        last_col = col if len(lines) == 1 else 0
        if last_col + len(lines[-1]) + 4 + len(x.text) <= width + 8:
            lines[-1] += f"  ; {x.text}"
            return lines
        return [f";; {x.text}", " " * col + lines[0]] + lines[1:]
    if isinstance(x, Pre):
        lines = pp(x.form, col + len(x.prefix), mode, width)
        lines[0] = x.prefix + lines[0]
        return lines
    if not isinstance(x, list):
        return str(x).split("\n")
    if not x:
        return ["()"]
    f = None if has_comment(x) else flat(x)
    if f is not None and col + len(f) <= width:
        return [f]
    head = x[0]
    hs = flat(head) if not isinstance(head, (list, Pre, TC, Cmt)) else None
    sp = lambda n: " " * n  # noqa: E731
    # designator: (an action \n    (slot ...) ...)
    if hs in DET and len(x) > 1 and isinstance(x[1], str):
        first = f"({hs} {x[1]}"
        rest = x[2:]
        if rest and isinstance(rest[0], str) and rest[0].startswith("?"):
            first += " " + rest[0]
            rest = rest[1:]
        return emit_body(first, rest, col, col + 4, mode, width)
    if hs is not None and hs in BODY:
        nd = BODY[hs]
        dist, body = x[1:1 + nd], x[1 + nd:]
        moved = [Cmt(";; " + d.text) for d in dist if isinstance(d, TC)]
        dist = [d.form if isinstance(d, TC) else d for d in dist]
        body = moved + list(body)
        first = "(" + hs
        if all(not has_comment(d) for d in dist):
            cand = first + "".join(" " + flat(d) for d in dist)
            if col + len(cand) <= width or not dist:
                return emit_body(cand, body, col, col + 2, mode, width)
        if hs in ATTACH and dist and not has_comment(dist[0]):
            # first distinguished argument stays on the head line, the others align under it
            ac = col + len(first) + 1
            dl = pp(dist[0], ac, mode, width)
            out = [first + " " + dl[0]] + dl[1:]
            for d in dist[1:]:
                dd = pp(d, ac, mode, width)
                out.append(sp(ac) + dd[0])
                out += dd[1:]
            for g in groups(body, mode):
                if len(g) == 1 and isinstance(g[0], Blank):
                    continue
                gl = pp_group(g, col + 2, mode, width)
                out.append(sp(col + 2) + gl[0])
                out += gl[1:]
            return close(out)
        # distinguished arguments on their own lines, indented by 4
        out = [first]
        for d in dist:
            dl = pp(d, col + 4, mode, width)
            out.append(sp(col + 4) + dl[0])
            out += dl[1:]
        for g in groups(body, mode):
            if len(g) == 1 and isinstance(g[0], Blank):
                continue
            gl = pp_group(g, col + 2, mode, width)
            out.append(sp(col + 2) + gl[0])
            out += gl[1:]
        return close(out)
    if hs is not None and len(x) > 2 and isinstance(x[1], list) and len(x[1]) == 1 and isinstance(x[1][0], str):
        # a handler clause (type (var) body...): the body indented by 2
        return emit_body(f"({hs} {flat(x[1])}", x[2:], col, col + 2, mode, width)
    if hs is not None:
        # function call: arguments aligned under the first argument
        args = x[1:]
        ac = col + 1 + len(hs) + 1
        if args and not has_comment(args[0]) and ac + 10 < width:
            gs = groups(args, mode)
            out = None
            for g in gs:
                text = None if any(has_comment(e) for e in g) else " ".join(flat(e) for e in g)
                if out is None:
                    first = pp(g[0], ac, mode, width) if text is None or ac + len(text) > width else [text]
                    out = [f"({hs} " + first[0]] + first[1:]
                    if len(g) > 1 and (text is None or ac + len(text) > width):
                        for e in g[1:]:
                            el = pp(e, ac, mode, width)
                            out.append(sp(ac) + el[0])
                            out += el[1:]
                    continue
                gl = pp_group(g, ac, mode, width)
                out.append(sp(ac) + gl[0])
                out += gl[1:]
            return close(out)
        return emit_body("(" + hs, args, col, col + 2, mode, width)
    # a list of forms (e.g. let* bindings, handler clauses): one per line under the first
    out = []
    for k, e in enumerate(x):
        el = pp(e, col + 1, mode, width)
        if k == 0:
            out = ["(" + el[0]] + el[1:]
        else:
            out.append(sp(col + 1) + el[0])
            out += el[1:]
    return close(out)


def pp_group(g, col, mode, width):
    text = None if any(has_comment(e) for e in g) else " ".join(flat(e) for e in g)
    if text is not None and col + len(text) <= width:
        return [text]
    lines = pp(g[0], col, mode, width)
    for e in g[1:]:
        el = pp(e, col, mode, width)
        if isinstance(e, str) and col + len(lines[-1].lstrip()) + 1 + len(el[0]) <= width and len(el) == 1:
            lines[-1] += " " + el[0]
        else:
            lines.append(" " * col + el[0])
            lines += el[1:]
    return lines


def close(out):
    """Append the closing paren: before a trailing comment, on its own line after an own-line comment."""
    last = out[-1]
    if last.lstrip().startswith(";"):
        out.append(" " * (len(last) - len(last.lstrip())) + ")")
    elif "  ; " in last:
        code, _, cmt = last.partition("  ; ")
        out[-1] = code + ")  ; " + cmt
    else:
        out[-1] = last + ")"
    return out


def emit_body(first, body, col, bcol, mode, width):
    out = [first]
    for g in groups(body, mode):
        if len(g) == 1 and isinstance(g[0], Blank):
            continue
        gl = pp_group(g, bcol, mode, width)
        out.append(" " * bcol + gl[0])
        out += gl[1:]
    return close(out)


def split_top(text):
    """Top-level items as raw text: ('form', text incl. a trailing comment) or ('line', a comment or blank line)."""
    items, i, n = [], 0, len(text)
    while i < n:
        j = text.find("\n", i)
        j = n if j < 0 else j
        line = text[i:j]
        s = line.strip()
        if not s or s.startswith(";"):
            items.append(("line", s))
            i = j + 1
            continue
        k = text.index("(", i)
        depth, m, instr = 0, k, False
        while True:
            ch = text[m]
            if instr:
                if ch == "\\":
                    m += 2
                    continue
                if ch == '"':
                    instr = False
            elif ch == '"':
                instr = True
            elif ch == ";":
                m = text.find("\n", m)
                continue
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    break
            m += 1
        e = text.find("\n", m)
        e = n if e < 0 else e
        items.append(("form", text[k:e]))
        i = e + 1
    return items


def pretty(text: str, mode: str = "lisp", width: int = WIDTH, verbatim=("defmacro",)) -> str:
    """Pretty-print every top-level form; forms whose head is in `verbatim` keep their original text."""
    out = []
    for kind, raw in split_top(text):
        if kind == "line":
            if raw or (out and out[-1] != ""):
                out.append(raw)
            continue
        items = [x for x in parse(raw) if not isinstance(x, Blank)]
        form = items[0].form if isinstance(items[0], TC) else items[0]
        if isinstance(form, list) and form and form[0] in verbatim:
            out += raw.rstrip().split("\n")
            continue
        for it in items:
            out += pp(it, 0, mode, width)
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"
