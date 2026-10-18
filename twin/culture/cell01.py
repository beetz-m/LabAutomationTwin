"""Read-only access to Cell 01's Culture SDT code (sdt/culture_ledger.py, biophysical_v2/usd_event_bridge.py)."""

import importlib.util
import sys

from twin.episode_records import CELL01_ROOT


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, CELL01_ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    dont = sys.dont_write_bytecode
    sys.dont_write_bytecode = True          # Cell 01 is read-only from here
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = dont
    return mod


def culture_ledger():
    return _load("cell01_culture_ledger", "sdt/culture_ledger.py")


def usd_event_bridge():
    return _load("cell01_usd_event_bridge", "simulation/isaac_sim/biophysical_v2/usd_event_bridge.py")


def dose_monitor_names():
    import yaml
    s = yaml.safe_load((CELL01_ROOT / "sdt/schemas/cram_designator_schemas.yaml").read_text())
    for d in (s.get("designators") or s).values() if isinstance(s, dict) else []:
        if isinstance(d, dict) and d.get("action") == "dose":
            return list(d.get("monitors", []))
    return None
