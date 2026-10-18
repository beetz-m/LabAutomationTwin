"""Compose the Cell 01 working overlay: Cell 01 (read-only) + physics-schema fixes + layout P1 + station twins.

The authoritative Cell 01 USD in ResearchSpace is NOT modified (user decision 2026-10-15: land Cell 01
changes as a non-destructive overlay). This writes scenes/cell01_twin.usda, which sublayers the Cell 01
scene and adds overrides only:

  1. the 12 colliders whose PhysicsCollisionAPI was authored as a plain attribute (ignored by USD/PhysX)
     get the API applied properly (see tools/fix_cell01_api_schemas.py for the in-place fix);
  2. a time-code range, and a 240 Hz PhysX scene;
  3. layout P1 'R01 cluster' (tools/reachability_study.py; adopted by the user 2026-10-15), with the
     placements computed and checked by tools/layout_p1.py (scenes/layout_p1.json):
       * R01 moved to (-1.55, 0.35) at the west end of the central bench;
       * H4, L09 and L10 twins (assets/*/) referenced onto their Cell 01 prims, each with its transfer nest
         0.56-0.60 m from R01 and its robot side facing R01; the placeholder Housing cubes are deactivated;
       * provisional supports (side tables, an L10 plinth) put every transfer nest at 0.972 m;
       * R02's rail shifted west to x -0.85..1.75 at y 0.78 (2.6 m, D004);
       * layout frames for the AMR carrier dock and the R01/R02 handover nest on the bench;
       * the R02 tool magazine TCM01 with tools T01-T05 (assets/r02/tooling.usda) on the Cell 01 tool-changer prim;
       * the L17 imager twin (assets/l17/) on its Cell 01 prim at its Cell 01 location, on a provisional plinth,
         its load stage presenting toward R02's rail;
       * the L21 QC bench twin (assets/l21/) at (2.20, 1.07) on a side table, replacing the placeholder deck (which
         has no collider in Cell 01).
  4. the Cell 01 fit-out (assets/cell01_fitout/build_fitout.py, 2026-10-16): the safety enclosure E01 (frame, glass, interlocked
     doors as articulations, AMR portal with light curtain, E-stops, HMI, stack lights) replaces the three placeholder
     glass cubes; the machine bench F01 and the R02 rail cover dress the bench (the Cell 01 worktop cube stays the
     collider, render purpose -> guide); instrument cabinets / the isolated L17 sub-base dress the P1 supports (the P1
     boxes stay the colliders); the L12 hood is added under the L12 station.
  R02 itself (rail + UR5e, assets/r02/) is added at runtime by the scripts that use it (twin/r02_rig.py), like R01.

Run with the CAD venv:  env_cad/bin/python tools/compose_cell01_overlay.py   (after tools/layout_p1.py)
"""

import json
import math
import os

from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CELL01 = os.path.expanduser(
    "~/ResearchSpace/projects/robot-scientist/cell-01/AICOR_Cell01_Codex_Handoff/simulation/isaac_sim/"
    "biophysical_v2/AICOR_BioPhysical_Cell01_v2.usda")
OUT = os.environ.get("CELL01_OVERLAY_OUT", os.path.join(ROOT, "scenes", "cell01_twin.usda"))
LAYOUT = os.path.join(ROOT, "scenes", "layout_p1.json")
R01 = "/World/Cell01/Robots/R01_FR3"
ASSETS = {"H4": "assets/h4/h4.usda", "L09": "assets/l09/l09.usda", "L10": "assets/l10/l10.usda",
          "L12": "assets/l12/l12.usda", "L17": "assets/l17/l17.usda", "L21": "assets/l21/l21.usda", "TCM01": "assets/r02/tooling.usda", "HN": "assets/hn/hn.usda",
          "H2": "assets/r03/h2_dock.usda", "R03": "assets/r03/r03.usda"}
R03 = "/World/Cell01/Robots/R03_SampleAMR"
FITOUT = os.path.join(ROOT, "assets", "cell01_fitout", "usd")
NEST_FRAME = {"H4": "transfer_nest", "L09": "transfer_nest", "L10": "transfer_station", "L17": "plate_load_frame",
              "L12": "plate_nest",
              "L21": "reference_plate_frame"}
RAIL = dict(x0=-0.85, x1=1.75, y=0.78, z=0.92)
DECISION = ("2026-10-15 (user): layout P1 'R01 cluster' adopted (tools/reachability_study.py, tools/layout_p1.py); "
            "deviates from floor plan v0.3. Pending a DECISIONS.md entry in Cell 01 (proposals/cell01/README.md).")


def set_pose(prim, xyz, yaw_deg=None):
    xf = UsdGeom.Xformable(prim)
    xf.ClearXformOpOrder()
    xf.AddTranslateOp().Set(Gf.Vec3d(*map(float, xyz)))
    if yaw_deg is not None:
        xf.AddRotateZOp().Set(float(yaw_deg))


def ref(st, path, asset, xyz=(0, 0, 0), yaw_deg=None):
    prim = UsdGeom.Xform.Define(st, path).GetPrim()
    prim.GetReferences().AddReference(os.path.relpath(asset, os.path.dirname(OUT)))
    set_pose(prim, xyz, yaw_deg)
    return prim


def box(st, path, center, size, yaw_deg, color, collide=True):
    xf = UsdGeom.Xform.Define(st, path)
    set_pose(xf.GetPrim(), center, yaw_deg)
    c = UsdGeom.Cube.Define(st, path + "/Geom")
    c.CreateSizeAttr(1.0)
    c.AddScaleOp().Set(Gf.Vec3f(*map(float, size)))
    c.CreateDisplayColorAttr([Gf.Vec3f(*color)])
    if collide:
        UsdPhysics.CollisionAPI.Apply(c.GetPrim())
    return xf.GetPrim()


SEM_PLATE = "/World/ExperimentalWorld/Plates/Plate_P17"
SBS = (0.12776, 0.08548, 0.01435)        # m, ANSI/SLAS footprint and height (assets/common/twin_cad.py)
WELL_BOTTOM = 0.00345                    # m above the plate base (10.9 mm deep wells, twin plate model)


def semantic_plate(st, src):
    """5. The SDT plate P17 as a frame tree (user decision 2026-10-17, LDL report section 7).

    Cell 01 authors the 96 wells in world coordinates under an identity plate root, and a half-scale PlateBody 9 mm
    off the well grid, so a well's frame is only right while nothing moves and is off even then. Here the plate root
    sits on the L12 plate nest (the station Cell 01 places it at), every well is plate-relative (SBS: A1 at (-X,+Y),
    pitch 9 mm, frame at the well bottom) and the body has the SBS footprint. The well's interface frames stay as
    authored (pipette +10 mm, imaging +5 mm above the well frame). The runtime plate is /World/Episode/Plate_P17
    (twin/r01_rig.add_plate); this one is the SDT referent, so it neither collides nor renders (purpose guide).
    twin/culture/render_layer.py re-poses this root onto the physical plate from A01's local translate, which stays
    valid."""
    nest = UsdGeom.XformCache().GetLocalToWorldTransform(   # the composed stage: the L12 twin moves the nest
        st.GetPrimAtPath("/World/Cell01/Stations/L12_LiquidHandler/plate_nest")).ExtractTranslation()
    root = st.GetPrimAtPath(SEM_PLATE)
    root.GetAttribute("xformOp:translate").Set(type(root.GetAttribute("xformOp:translate").Get())(*nest))
    for w in st.GetPrimAtPath(SEM_PLATE + "/Wells").GetChildren():
        r, c = "ABCDEFGH".index(w.GetName()[0]), int(w.GetName()[1:]) - 1
        a = w.GetAttribute("xformOp:translate")
        a.Set(type(a.Get())(-0.0495 + 0.009 * c, 0.0315 - 0.009 * r, WELL_BOTTOM))
    body = st.GetPrimAtPath(SEM_PLATE + "/Physical/PlateBody")
    for name, val in (("xformOp:translate", (0.0, 0.0, SBS[2] / 2)), ("xformOp:scale", SBS)):
        a = body.GetAttribute(name)
        a.Set(type(a.Get())(*val))
    UsdPhysics.CollisionAPI(body).CreateCollisionEnabledAttr().Set(False)
    UsdGeom.Imageable(body).CreatePurposeAttr().Set(UsdGeom.Tokens.guide)
    root.CreateAttribute("sdt:note", Sdf.ValueTypeNames.String, custom=True).Set(
        "SDT referent of plate P17 as a frame tree: wells plate-relative (SBS), root on the L12 plate nest; "
        "the runtime plate is /World/Episode/Plate_P17 (compose_cell01_overlay.semantic_plate)")


def main():
    lay = json.load(open(LAYOUT))
    assert not lay["problems"], f"layout check failed, run tools/layout_p1.py: {lay['problems']}"
    src = Usd.Stage.Open(CELL01)
    broken = [p.GetPath() for p in src.Traverse() if p.GetAttribute("apiSchemas")
              and "PhysicsCollisionAPI" in (p.GetAttribute("apiSchemas").Get() or [])]

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    if os.path.exists(OUT):
        os.remove(OUT)
    st = Usd.Stage.CreateNew(OUT)
    layer = st.GetRootLayer()
    layer.subLayerPaths = [CELL01]
    st.SetDefaultPrim(st.GetPrimAtPath("/World"))
    UsdGeom.SetStageUpAxis(st, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(st, 1.0)
    st.SetStartTimeCode(0)
    st.SetEndTimeCode(1000000)
    st.SetTimeCodesPerSecond(60)
    layer.comment = ("Working overlay generated by tools/compose_cell01_overlay.py from scenes/layout_p1.json. "
                     "Cell 01 itself is unmodified; edit the scripts, not this file.")

    for path in broken:
        UsdPhysics.CollisionAPI.Apply(st.OverridePrim(path))
    scene = st.OverridePrim("/World/PhysicsScene")
    scene.AddAppliedSchema("PhysxSceneAPI")
    scene.CreateAttribute("physxScene:timeStepsPerSecond", Sdf.ValueTypeNames.UInt).Set(240)

    # R01: base_link stays 0.72 above the R01_FR3 origin (pedestal height)
    r01 = st.OverridePrim(R01)
    set_pose(r01, (lay["r01_base"][0], lay["r01_base"][1], 0.0))
    r01.CreateAttribute("sdt:placementDecision", Sdf.ValueTypeNames.String, custom=True).Set(DECISION)

    # stations: twin asset onto the Cell 01 prim, placeholder housing off, support underneath
    for name, s in lay["stations"].items():
        prim = st.OverridePrim(s["prim"])
        prim.GetReferences().AddReference(os.path.relpath(os.path.join(ROOT, ASSETS[name]), os.path.dirname(OUT)))
        set_pose(prim, s["origin"], s["yaw_deg"])
        prim.CreateAttribute("sdt:bindingStatus", Sdf.ValueTypeNames.String).Set("articulated_v1")
        prim.CreateAttribute("sdt:placementDecision", Sdf.ValueTypeNames.String, custom=True).Set(DECISION)
        for placeholder in ("Housing", "Deck"):
            if src.GetPrimAtPath(f"{s['prim']}/{placeholder}"):
                st.OverridePrim(f"{s['prim']}/{placeholder}").SetActive(False)
        if s["support"] == "bench":                 # stands on the central bench worktop: no support
            continue
        x0, x1, y0, y1 = s["footprint"]
        h = s["support_height"]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        c, sn = math.cos(math.radians(s["yaw_deg"])), math.sin(math.radians(s["yaw_deg"]))
        centre = (s["origin"][0] + c * cx - sn * cy, s["origin"][1] + sn * cx + c * cy, h / 2)
        sup = box(st, f"/World/Cell01/Furniture/P1_Supports/{name}_{s['support']}", centre,
                  (x1 - x0 + 0.04, y1 - y0 + 0.04, h), s["yaw_deg"], (0.62, 0.64, 0.66))
        # fit-out: the box stays the collider (guide purpose), the cabinet / sub-base asset is its visual
        UsdGeom.Imageable(st.GetPrimAtPath(sup.GetPath().AppendChild("Geom"))).CreatePurposeAttr(UsdGeom.Tokens.guide)
        ref(st, f"/World/Cell01/Furniture/FitOut/{name}_support", os.path.join(FITOUT, f"support_{name}.usda"),
            (centre[0], centre[1], 0.0), s["yaw_deg"])
        sup.CreateAttribute("sdt:note", Sdf.ValueTypeNames.String, custom=True).Set(
            f"provisional {s['support']} (layout P1), top at {h:.3f} m so the transfer nest is at {lay['nest_z']} m")

    # fixtures: the R02 tool magazine and the R01/R02 handover nest (not Cell 01 components: defined here)
    for name, fx in lay.get("fixtures", {}).items():
        prim = st.OverridePrim(fx["prim"]) if src.GetPrimAtPath(fx["prim"]) else UsdGeom.Xform.Define(st, fx["prim"]).GetPrim()
        prim.GetReferences().AddReference(os.path.relpath(os.path.join(ROOT, ASSETS[name]), os.path.dirname(OUT)))
        set_pose(prim, fx["origin"], fx["yaw_deg"])
        prim.CreateAttribute("sdt:bindingStatus", Sdf.ValueTypeNames.String).Set("static_v1" if name == "H2" else "proxy_v1")
        prim.CreateAttribute("sdt:placementDecision", Sdf.ValueTypeNames.String, custom=True).Set(
            DECISION + {"TCM01": " Tool magazine placed with R02 (layout P1 amendment, 2026-10-15).",
                        "HN": " Handover nest at the P1 handover site (2026-10-16).",
                        "H2": " H2 dock: AMR docks heading west, carrier seat at the AMR dock site (2026-10-16)."}[name])

    # R03 AMR: its map frame is the docked pose in H2 (shared with the dock); the placeholder body is deactivated
    h2 = lay["fixtures"]["H2"]
    r03 = st.OverridePrim(R03)
    r03.GetReferences().AddReference(os.path.relpath(os.path.join(ROOT, ASSETS["R03"]), os.path.dirname(OUT)))
    set_pose(r03, h2["origin"], h2["yaw_deg"])
    r03.CreateAttribute("sdt:bindingStatus", Sdf.ValueTypeNames.String).Set("articulated_v1")
    r03.CreateAttribute("sdt:placementDecision", Sdf.ValueTypeNames.String, custom=True).Set(
        DECISION + " R03 map frame = docked pose in H2 (2026-10-16).")
    if src.GetPrimAtPath(f"{R03}/Body"):
        st.OverridePrim(f"{R03}/Body").SetActive(False)

    # R02 rail (placeholder geometry, replaced at runtime when R02 is added)
    rail = st.OverridePrim("/World/Cell01/Robots/R02_RailSystem/LinearRail")
    set_pose(rail, ((RAIL["x0"] + RAIL["x1"]) / 2, RAIL["y"], RAIL["z"]))
    st.OverridePrim("/World/Cell01/Robots/R02_RailSystem/LinearRail/Rail").GetAttribute("xformOp:scale").Set(
        Gf.Vec3f(RAIL["x1"] - RAIL["x0"], 0.11, 0.09))

    # Cell 01 fit-out: enclosure E01 (replaces the placeholder glass cubes), bench F01 + rail cover (visual over the
    # Cell 01 worktop collider), L12 hood (static colliders, under the L12 station so its airspace monitor ignores it)
    for cube in ("RearGlass", "LeftGlass", "RightGlass"):
        if src.GetPrimAtPath(f"/World/Cell01/Architecture/SafetyEnclosure/{cube}"):
            st.OverridePrim(f"/World/Cell01/Architecture/SafetyEnclosure/{cube}").SetActive(False)
    ref(st, "/World/Cell01/Architecture/Enclosure_E01", os.path.join(FITOUT, "enclosure.usda"))
    UsdGeom.Imageable(st.OverridePrim("/World/Cell01/Furniture/AutomationBench/Worktop")).CreatePurposeAttr(
        UsdGeom.Tokens.guide)
    ref(st, "/World/Cell01/Furniture/FitOut/F01_Bench", os.path.join(FITOUT, "bench_f01.usda"))
    ref(st, "/World/Cell01/Furniture/FitOut/R02_RailCover", os.path.join(FITOUT, "rail_cover.usda"))
    ref(st, "/World/Cell01/Stations/L12_LiquidHandler/Enclosure", os.path.join(FITOUT, "l12_hood.usda"))
    UsdGeom.Xform.Define(st, "/World/Cell01/Furniture/FitOut").GetPrim().CreateAttribute(
        "sdt:note", Sdf.ValueTypeNames.String, custom=True).Set(
        "Cell 01 fit-out (assets/cell01_fitout/build_fitout.py): project-owned proxies of the spec's enclosure/furniture "
        "classes; manufacturer CAD not acquired")

    # layout frames (no device assets yet)
    for name, xyz in lay["extra_frames"].items():
        f = UsdGeom.Xform.Define(st, f"/World/Cell01/LayoutP1/{name}")
        set_pose(f.GetPrim(), xyz)
        UsdGeom.Xformable(f).CreateVisibilityAttr("invisible")
    UsdGeom.Xform.Define(st, "/World/Cell01/LayoutP1").GetPrim().CreateAttribute(
        "sdt:note", Sdf.ValueTypeNames.String, custom=True).Set(DECISION)
    semantic_plate(st, src)
    layer.Save()

    # report: composed nest poses against the layout
    out = Usd.Stage.Open(OUT)
    xc = UsdGeom.XformCache()
    base = xc.GetLocalToWorldTransform(out.GetPrimAtPath(R01 + "/base_link")).ExtractTranslation()
    colliders = sum(p.HasAPI(UsdPhysics.CollisionAPI) for p in out.Traverse())
    print(f"wrote {OUT}")
    print(f"  collider fixes: {len(broken)}; colliders in composed stage: {colliders}")
    print(f"  R01 base_link at ({base[0]:.3f}, {base[1]:.3f}, {base[2]:.3f})")
    worst = 0.0
    for name, s in lay["stations"].items():
        nest = xc.GetLocalToWorldTransform(out.GetPrimAtPath(f"{s['prim']}/{NEST_FRAME[name]}")).ExtractTranslation()
        err = (Gf.Vec3d(*s["nest"]) - nest).GetLength()
        worst = max(worst, err)
        who = "R02 (rail)" if s.get("served_by") == "R02" else (
            f"R01, {math.hypot(nest[0] - base[0], nest[1] - base[1]):.3f} m away, {nest[2] - base[2]:.3f} m above its base")
        print(f"  {name:4s} nest at ({nest[0]:.3f}, {nest[1]:.3f}, {nest[2]:.3f}); served by {who}; "
              f"layout error {err * 1000:.2f} mm")
    for name, fx in lay.get("fixtures", {}).items():
        if name == "H2":
            hf = xc.GetLocalToWorldTransform(out.GetPrimAtPath(f"{R03}/handover_carrier_frame")).ExtractTranslation()
            exp = Gf.Vec3d(*lay["extra_frames"]["AMR_dock_carrier"])
            worst = max(worst, (hf - exp).GetLength())
            print(f"  R03  carrier seat docked at ({hf[0]:.3f}, {hf[1]:.3f}, {hf[2]:.3f}); layout error "
                  f"{(hf - exp).GetLength() * 1e3:.2f} mm")
            continue
        if name == "HN":
            hf = xc.GetLocalToWorldTransform(out.GetPrimAtPath(f"{fx['prim']}/handover_frame")).ExtractTranslation()
            exp = Gf.Vec3d(*lay["extra_frames"]["handover_nest_R01_R02"])
            worst = max(worst, (hf - exp).GetLength())
            print(f"  HN   seat at ({hf[0]:.3f}, {hf[1]:.3f}, {hf[2]:.3f}); layout error {(hf - exp).GetLength() * 1e3:.2f} mm")
            continue
        for k in range(5):
            d = xc.GetLocalToWorldTransform(out.GetPrimAtPath(f"{fx['prim']}/dock_T0{k + 1}")).ExtractTranslation()
            exp = Gf.Vec3d(fx["origin"][0] + (k - 2) * 0.15, fx["origin"][1], 1.12)
            worst = max(worst, (d - exp).GetLength())
        print(f"  {name} docks at x {fx['origin'][0] - 0.30:.2f}..{fx['origin'][0] + 0.30:.2f}, y {fx['origin'][1]}, z 1.12")
    assert worst < 1e-3, worst


if __name__ == "__main__":
    main()
