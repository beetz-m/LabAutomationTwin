# rsa: robot science assistant kernel (iteration 1)

A consolidated, coraplex-shaped kernel that executes the challenge–rescue experiment as action designators. Design:
[../docs/rsa/KERNEL.md](../docs/rsa/KERNEL.md); findings: [../docs/rsa/ITERATIONS.md](../docs/rsa/ITERATIONS.md).

```
env_cad/bin/python -m rsa.run_example            # 12 scenarios + cross-check + critic + tamper test + 27 CQs
env_cad/bin/python -m rsa.run_example nominal    # one scenario
```

| File | Role |
|---|---|
| `kb.py` | Knowledge base: the planner's facts (`build/e2m/facts_<tag>.lp`) + Cell 01 component records (read-only) + registries; resolution queries return grounds |
| `core.py` | Designators (action / motion / device-command), plan nodes, belief with provenance and freshness, executor (lifecycle, acceptance, understanding gate, failure handling, projection) |
| `library.py` | Generalized plans of the categories (experiment … picking-up / placing); no device names (linted) |
| `checks.py` | Constraint checks, policies (window, L12 airspace), understanding frame U(a) |
| `backend.py` | Symbolic Cell 01 world with fault injection (Isaac backend: iteration 2) |
| `audit.py` | Hash-chained commitment records, one per lifecycle transition; verifier |
| `critic.py` | Two-column verdict (realization / validity) from the trail alone |
| `cq.py` | Competency questions answered from trail + KB + dry runs, with grounds |
| `registry/` | categories, constraints, devices (twin extensions, reagents, measurement bindings), norms, scenarios, CQs |
| `out/` | trails, run records, `report.md` |

ILLUSTRATIVE (D016): the twin's parameters and regulation mapping are labelled, not lab facts.
