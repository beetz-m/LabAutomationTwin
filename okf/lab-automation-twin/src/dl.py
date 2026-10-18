"""Description-logic expressions written once in Python and rendered three ways:

  .ofn()  OWL 2 functional syntax (full semantics: definitions, negation, data values) - for Konclude / HermiT
  .man()  Manchester syntax in AICOR's `-dl.md` style - read by AICOR's exporter (okf_owl.py)
  .dl()   DL notation for people (∃, ∀, ⊓, ⊔, ¬, ≥n, ≤n, =n)

AICOR convention (okf_owl.py): every class and property lives in one namespace, http://aicor.knowledge/l2-ontology.owl#,
and an upper-ontology token `dul:X` / `soma:X` denotes the stand-in class `dul_X` / `soma_X`. Names are written bare
(AICOR, robot-scientist, VRB and this module) or with dul: / soma: (upper level) or bio: / c01lab: / cell01: / sdtc:
(Cell 01's own namespaces, bridged in the full OWL export only).
"""

from __future__ import annotations

AICOR_NS = "http://aicor.knowledge/l2-ontology.owl#"
PREFIXES = {
    "": AICOR_NS,
    "bio": "https://aicor.example/okf/biology#",
    "c01lab": "https://aicor.example/okf/lab#",
    "sdtc": "https://aicor.example.org/ontology/sdt#",
    "cell01": "https://aicor.example.org/ontology/cell01#",
    "owl": "http://www.w3.org/2002/07/owl#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
}
UPPER = ("dul", "soma")


def q(name: str) -> str:
    """OFN name."""
    if ":" in name:
        pre, loc = name.split(":", 1)
        if pre in UPPER:
            return f":{pre}_{loc}"
        return name
    return f":{name}"


def iri(name: str) -> str:
    """Full IRI of a name."""
    if ":" in name:
        pre, loc = name.split(":", 1)
        if pre in UPPER:
            return f"{AICOR_NS}{pre}_{loc}"
        return PREFIXES[pre] + loc
    return AICOR_NS + name


def E(x):
    return x if isinstance(x, Expr) else Named(x)


class Expr:
    prec = 9

    def names(self):
        return set()

    def props(self):
        return set()

    def simple(self):
        """True if AICOR's tolerant exporter keeps this as an axiom (a named class, or a restriction whose filler is a
        named class or a flat union / intersection of named classes)."""
        return False


def _wrap(e, prec, f):
    s = getattr(e, f)()
    return f"({s})" if e.prec < prec else s


class Named(Expr):
    def __init__(self, n):
        self.n = n

    def ofn(self):
        return "owl:Thing" if self.n == "⊤" else q(self.n)

    def man(self):
        return "owl:Thing" if self.n == "⊤" else self.n

    def dl(self):
        return "⊤" if self.n == "⊤" else self.n

    def names(self):
        return {self.n} if self.n != "⊤" else set()

    def simple(self):
        return self.n != "⊤"


class Inv:
    def __init__(self, p):
        self.p = p

    def ofn(self):
        return f"ObjectInverseOf({q(self.p)})"

    def man(self):
        return f"inverse ({self.p})"

    def dl(self):
        return f"{self.p}⁻"


def _p(p, f):
    return getattr(p, f)() if isinstance(p, Inv) else (q(p) if f == "ofn" else p)


def _pn(p):
    return p.p if isinstance(p, Inv) else p


class Some(Expr):
    kw, sym = "some", "∃"

    def __init__(self, p, c="⊤"):
        self.p, self.c = p, E(c)

    def ofn(self):
        return f"Object{'Some' if self.kw == 'some' else 'All'}ValuesFrom({_p(self.p, 'ofn')} {self.c.ofn()})"

    def man(self):
        return f"{_p(self.p, 'man')} {self.kw} {_wrap(self.c, 9, 'man')}"

    def dl(self):
        return f"{self.sym}{_p(self.p, 'dl')}.{_wrap(self.c, 9, 'dl')}"

    def names(self):
        return self.c.names()

    def props(self):
        return {_pn(self.p)} | self.c.props()

    def simple(self):
        flat = isinstance(self.c, (And, Or)) and all(isinstance(x, Named) for x in self.c.xs)
        return not isinstance(self.p, Inv) and (isinstance(self.c, Named) and self.c.n != "⊤" or flat)


class All(Some):
    kw, sym = "only", "∀"


class _Card(Expr):
    kind, kw, sym = "", "", ""

    def __init__(self, n, p, c="⊤"):
        self.n, self.p, self.c = n, p, E(c)

    def ofn(self):
        return f"Object{self.kind}Cardinality({self.n} {_p(self.p, 'ofn')} {self.c.ofn()})"

    def man(self):
        if self.n > 12 and self.kw in ("exactly", "min"):
            # a large qualified cardinality makes HermiT classification intractable over the AICOR export (measured:
            # =96 wells, >25 min vs 7 s); the AICOR export keeps the existential, the full OWL export the number
            return f"{_p(self.p, 'man')} some {_wrap(self.c, 9, 'man')}   -- {self.kw} {self.n} in the full OWL export"
        return f"{_p(self.p, 'man')} {self.kw} {self.n} {_wrap(self.c, 9, 'man')}"

    def dl(self):
        return f"{self.sym}{self.n} {_p(self.p, 'dl')}.{_wrap(self.c, 9, 'dl')}"

    def names(self):
        return self.c.names()

    def props(self):
        return {_pn(self.p)} | self.c.props()

    def simple(self):
        return not isinstance(self.p, Inv) and isinstance(self.c, Named) and self.c.n != "⊤"


class Min(_Card):
    kind, kw, sym = "Min", "min", "≥"


class Max(_Card):
    kind, kw, sym = "Max", "max", "≤"


class Exact(_Card):
    kind, kw, sym = "Exact", "exactly", "="


class And(Expr):
    prec, op, kw, sym = 5, "Intersection", "and", " ⊓ "

    def __init__(self, *xs):
        self.xs = [E(x) for x in xs]

    def ofn(self):
        return f"Object{self.op}Of({' '.join(x.ofn() for x in self.xs)})"

    def man(self):
        return f" {self.kw} ".join(_wrap(x, 6, "man") for x in self.xs)

    def dl(self):
        return self.sym.join(_wrap(x, 6, "dl") for x in self.xs)

    def names(self):
        return set().union(*(x.names() for x in self.xs))

    def props(self):
        return set().union(*(x.props() for x in self.xs))


class Or(And):
    prec, op, kw, sym = 4, "Union", "or", " ⊔ "


class Not(Expr):
    def __init__(self, c):
        self.c = E(c)

    def ofn(self):
        return f"ObjectComplementOf({self.c.ofn()})"

    def man(self):
        return f"not ({self.c.man()})"

    def dl(self):
        return f"¬{_wrap(self.c, 9, 'dl')}"

    def names(self):
        return self.c.names()

    def props(self):
        return self.c.props()


class Value(Expr):
    def __init__(self, p, ind):
        self.p, self.ind = p, ind

    def ofn(self):
        return f"ObjectHasValue({q(self.p)} {q(self.ind)})"

    def man(self):
        return f"{self.p} value {self.ind}"

    def dl(self):
        return f"∃{self.p}.{{{self.ind}}}"

    def props(self):
        return {self.p}


class DSome(Expr):
    def __init__(self, p, dt):
        self.p, self.dt = p, dt

    def ofn(self):
        return f"DataSomeValuesFrom({q(self.p)} {self.dt})"

    def man(self):
        return f"{self.p} some {self.dt}"

    def dl(self):
        return f"∃{self.p}.{self.dt}"

    def props(self):
        return {self.p}

    def simple(self):
        return True


class DValue(Expr):
    def __init__(self, p, lit, dt="xsd:string"):
        self.p, self.lit, self.dt = p, lit, dt

    def ofn(self):
        return f'DataHasValue({q(self.p)} "{self.lit}"^^{self.dt})'

    def man(self):
        return f"{self.p} value {self.lit if self.dt == 'xsd:boolean' else chr(34) + str(self.lit) + chr(34)}"

    def dl(self):
        return f'∃{self.p}.{{{self.lit}}}'

    def props(self):
        return {self.p}

    def simple(self):
        return True
