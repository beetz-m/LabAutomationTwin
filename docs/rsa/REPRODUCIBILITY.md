# Reproducible experimentation plan, audit trail and paper

## Commands

```
env_cad/bin/python -m rsa.reproduce            # run all stages; rsa/out/repro/manifest.json
env_cad/bin/python -m rsa.reproduce --verify   # run again; rsa/out/repro/reproduction.json; exit 1 unless the manifest hash is the same
env_cad/bin/python -m rsa.protocol             # (a stage of the above) protocol.json/.md and audit.json
env_cad/bin/python paper/build_paper.py        # paper/paper.tex, paper/paper.pdf (lualatex), paper/paper.html
```

## What each part is

### Manifest (`rsa/reproduce.py`)

For each stage, the manifest records:

- the command;
- the sha256 of the code the stage ran;
- the sha256 of every file the stage wrote. Writes are detected by mtime over `rsa/out`, `derivation/out` and `build/e2m`.

The following are recorded once:

- **Inputs:**
  - the LDL registry;
  - the kernel registry;
  - the ABox;
  - the ASP program;
  - the scene;
  - the culture surrogate;
  - the duration traces;
  - the recorded Isaac trails.
- **Tool versions.**

JSON files are hashed in canonical form, with `solve_s`, `ground_s` and `wall_s` dropped. These are wall-clock fields; nothing else is excluded.

The design stage runs with `--refresh`, so a reproduction recomputes the EIG Monte Carlo (seed 7).

### Protocol (`rsa/protocol.py` → `protocol.json` / `protocol.md`)

The protocol is generated from the outputs. It covers:

- question, goal and design, with the alternative designs;
- the culture plan and its order;
- the vessels;
- the refinement into lab actions and devices;
- the sessions;
- the constraints;
- the handlers;
- the KPIs and acceptance criteria;
- the records.

It is bound to the derivation by an input digest.

### Audit certificate (`audit.json`)

For every trail, the certificate records:

- whether the hash chain is intact;
- the tamper test (one changed value must be detected);
- the verdict;
- the registry the trail ran under.

Each symbolic scenario is also re-executed in a temporary directory, and the re-run trail must be identical to the recorded one, chain head included. The Isaac trails are verified, but they are not re-executed.

### Paper (`paper/build_paper.py`)

All numbers, tables, figures and listings are read from the outputs above.

## Not covered

- **Same machine:** reproduction was checked on the same machine with the same environment, not in a clean clone or container.
- **Isaac runs:** these are recorded inputs, not re-executed. GPU physics is not expected to be bit-reproducible.
- **References:** the paper's references were compiled without database access and must be checked before submission.
- **Placeholders:** the paper's authorship and AI-assistance statement are placeholders.
