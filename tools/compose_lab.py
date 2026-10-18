"""Compose the whole-lab twin: scenes/lab_twin.usda = Cell 01 working overlay + AICOR Lab 1 (site layout proposal S1).

  * sublayers scenes/cell01_twin.usda (Cell 01 + P1 + station twins + fit-out), unmodified;
  * /World/AICOR_Lab/Building    the shell (assets/site/build_site.py): hall, storage room ST01, doors (storage
                                 sliding door articulated), windows, ceiling + 40 luminaires, markings, services;
  * /World/AICOR_Lab/<Zone>/<Id> equipment from assets/labequip/usd/ (project-owned proxies, generic class
                                 dimensions) with SDT ids, zones and storage locations;
  * /World/AICOR_Lab/StorageRoom/S1_DispatchDock: a second H2-type dock (assets/r03/h2_dock.usda) where staff load
                                 R03's carrier; R03's map frame stays the H2 docked pose;
  * /World/AICOR_Lab/Zones/*     semantic site zones (extents, role); the R03 site route is in the shell;
  * lighting: daylight sky + sun through the south windows; the Cell 01 dome becomes the sky;
  * R03's PlanarX / PlanarY limits are widened in this scene only (the site route leaves the cell; Cell 01 tests keep theirs);
  * the Cell 01 floor cube stays the cell's collider, the epoxy hall floor is its visual.

Writes scenes/lab_twin.usda and scenes/site_layout_s1.json. Run: env_cad/bin/python tools/compose_lab.py
"""

import json
import os
import sys

from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.environ.get("LAB_TWIN_OUT", os.path.join(ROOT, "scenes", "lab_twin.usda"))
SITE_LAYER = os.path.join(os.path.dirname(OUT), "lab_site.usda")
CELL = os.environ.get("CELL01_OVERLAY_OUT", os.path.join(ROOT, "scenes", "cell01_twin.usda"))
SITE = os.path.join(ROOT, "assets", "site", "usd", "site_shell.usda")
EQ = os.path.join(ROOT, "assets", "labequip", "usd")
H2 = os.path.join(ROOT, "assets", "r03", "h2_dock.usda")
LAB = "/World/AICOR_Lab"
STATUS = "proposal_S1 (site layout around Cell 01; not part of the Cell 01 v0.3 baseline)"

ZONES = {  # name: (x0, x1, y0, y1, role)
    "Cell01": (-3.05, 3.05, -2.30, 2.30, "robot cell (Cell 01 v0.3 envelope 6.0 x 4.5 x 2.5 m)"),
    "RearServiceCorridor": (-5.2, 3.3, 2.30, 4.2, "technician access to the rear instrument side (spec: >= 1.0 m)"),
    "FrontLogistics": (-5.2, 9.6, -4.2, -2.30, "AMR lane to the Cell 01 portal; pedestrian walkway at y -4.15"),
    "StorageRoom_ST01": (-9.6, -5.2, -1.2, 4.2, "consumables, cold storage, cryostorage, CO2 supply, AMR dispatch S1"),
    "EntranceGowning": (-9.6, -5.2, -7.0, -1.2, "entrance from the building corridor, coats, gloves, hand wash"),
    "OperatorArea": (-5.2, 3.3, -7.0, -4.2, "monitoring desks facing the cell, twin compute rack"),
    "CulturePrep": (3.3, 9.6, -4.2, 4.2, "manual culture work upstream of Cell 01: BSCs, incubators, benches"),
    "WashWaste": (5.5, 9.6, -7.0, -4.2, "autoclave and waste collection (Cell 01 waste handover)"),
}

# (zone, id, asset, x, y, z, yaw, extra semantics). Wall items: (x, y) on the wall face, z = mounting height.
# (zone, id, asset, x, y, z, yaw, snap). Floor items: snap = (wall side N/S/E/W, wall coordinate, gap): the item's
# measured back face is put against the wall (the given x or y on that axis is replaced). Wall items: (x, y) on the
# wall face, z = mounting height of the asset origin, snap None.
N_WALL, S_WALL, E_WALL, W_WALL = 4.2, -7.0, 9.6, -9.6
ST_E, ST_S = -5.26, -1.14            # storage-room partitions, inner faces
PLACEMENTS = [
    # storage room ST01
    ("StorageRoom", "ST01_R1", "shelving_rack_R1", -9.35, 3.30, 0.0, 90, ("W", W_WALL, 0.03)),
    ("StorageRoom", "ST01_R2", "shelving_rack_R2", -9.35, 2.00, 0.0, 90, ("W", W_WALL, 0.03)),
    ("StorageRoom", "ST01_R3", "shelving_rack_R3", -5.47, 2.30, 0.0, -90, ("E", ST_E, 0.03)),
    # cold storage along the north wall (ULT, two +4 C fridges, -20 C freezer), CO2 cabinet in the NE corner
    ("StorageRoom", "ST01_U1", "ult_freezer", -8.52, 3.735, 0.0, 0, ("N", N_WALL, 0.08)),
    ("StorageRoom", "ST01_F1", "lab_fridge", -7.73, 3.855, 0.0, 0, ("N", N_WALL, 0.05)),
    ("StorageRoom", "ST01_F2", "lab_fridge", -7.08, 3.855, 0.0, 0, ("N", N_WALL, 0.05)),
    ("StorageRoom", "ST01_Z1", "freezer_m20", -6.43, 3.855, 0.0, 0, ("N", N_WALL, 0.05)),
    ("StorageRoom", "ST01_G1", "gas_cabinet", -5.52, 3.55, 0.0, -90, ("E", ST_E, 0.03)),
    # cryostorage in the SW corner, next to the O2-depletion monitor
    ("StorageRoom", "ST01_N1", "ln2_dewar", -9.15, -0.60, 0.0, 0, ("W", W_WALL, 0.10)),
    ("StorageRoom", "S1_DispatchBench", "dispatch_bench", -7.95, 0.60, 0.0, 90, None),
    ("StorageRoom", "ST01_O2", "o2_monitor", W_WALL, -0.20, 1.60, 90, None),
    ("StorageRoom", "ST01_FireExt", "fire_extinguisher", -8.0, ST_S, 0.90, 180, None),
    ("StorageRoom", "ST01_Access", "access_reader", -5.50, -1.26, 1.10, 0, None),
    # entrance / gowning (west wall: coats north of the entrance door; extinguisher, hand-wash sink, first aid south)
    ("Entrance", "EN_Coats", "lab_coat_rack", W_WALL, -2.00, 1.75, 90, None),
    ("Entrance", "EN_Gloves", "glove_dispenser", -9.20, -1.26, 1.40, 0, None),
    ("Entrance", "EN_FireExt", "fire_extinguisher", W_WALL, -4.88, 0.90, 90, None),
    ("Entrance", "EN_Sink", "lab_sink_unit", -9.275, -5.85, 0.0, 90, ("W", W_WALL, 0.02)),
    ("Entrance", "EN_FirstAid", "first_aid_box", W_WALL, -6.70, 1.50, 90, None),
    ("Entrance", "EN_Plant", "potted_plant", -7.55, -6.30, 0.0, 30, None),
    # operator area
    ("OperatorArea", "OP1_MonitoringDesk", "operator_desk", -0.60, -5.00, 0.0, 0, None),
    ("OperatorArea", "OP2_EngineeringDesk", "operator_desk", 2.30, -5.00, 0.0, 0, None),
    ("OperatorArea", "OP_TwinRack", "server_rack", -4.55, -6.48, 0.0, 180, ("S", S_WALL, 0.05)),
    ("OperatorArea", "OP_Plant", "potted_plant", -2.45, -6.25, 0.0, 70, None),
    # culture prep
    ("CulturePrep", "PR_BSC1", "bsc_class2", 9.15, 2.60, 0.0, -90, ("E", E_WALL, 0.05)),
    ("CulturePrep", "PR_BSC2", "bsc_class2", 9.15, 0.80, 0.0, -90, ("E", E_WALL, 0.05)),
    ("CulturePrep", "PR_INC1", "co2_incubator_stack", 9.175, -0.85, 0.0, -90, ("E", E_WALL, 0.05)),
    ("CulturePrep", "PR_Island", "lab_bench_island", 6.00, 0.20, 0.0, 0, None),
    ("CulturePrep", "PR_WallBench", "wall_bench", 7.10, 3.805, 0.0, 0, ("N", N_WALL, 0.02)),
    ("CulturePrep", "PR_Microscope", "inverted_microscope", 6.20, 3.80, 0.90, 0, None),
    ("CulturePrep", "PR_Centrifuge", "centrifuge", 7.65, 3.80, 0.90, 0, None),
    ("CulturePrep", "PR_WaterBath", "water_bath", 8.35, 3.85, 0.90, 0, None),
    ("CulturePrep", "PR_Pipettes", "pipette_stand", 5.35, -0.25, 0.90, 0, None),
    ("CulturePrep", "PR_Sink", "lab_sink_unit", 3.90, 3.855, 0.0, 0, ("N", N_WALL, 0.02)),
    ("CulturePrep", "PR_Shower", "emergency_shower", 5.00, N_WALL, 0.0, 0, None),
    ("CulturePrep", "PR_Gloves", "glove_dispenser", E_WALL, -1.75, 1.40, -90, None),
    ("CulturePrep", "PR_FirstAid", "first_aid_box", 2.90, N_WALL, 1.50, 0, None),
    ("CulturePrep", "PR_FireExt", "fire_extinguisher", E_WALL, -3.10, 0.90, -90, None),
    ("CulturePrep", "PR_Stool1", "lab_stool", 5.40, -1.10, 0.0, 10, None),
    ("CulturePrep", "PR_Stool2", "lab_stool", 6.70, -1.10, 0.0, -20, None),
    ("CulturePrep", "PR_Stool3", "lab_stool", 8.10, 2.55, 0.0, 0, None),
    ("CulturePrep", "PR_Stool4", "lab_stool", 8.10, 0.85, 0.0, 40, None),
    ("CulturePrep", "PR_Whiteboard", "whiteboard", 4.50, S_WALL, 1.50, 180, None),
    # wash / waste
    ("WashWaste", "WW_Autoclave", "autoclave", 8.90, -6.45, 0.0, 180, ("S", S_WALL, 0.05)),
    ("WashWaste", "WW_Waste", "waste_station", 7.30, -6.50, 0.0, 180, ("S", S_WALL, 0.05)),
]
CEILING = [("hvac_diffuser", x, y) for x in (-3.3, 1.5, 6.3) for y in (-5.1, -0.3, 3.3)] + \
          [("hvac_diffuser", -7.8, 0.6), ("hvac_diffuser", -7.8, -5.1)] + \
          [("smoke_detector", x, y) for x in (-6.9, -0.9, 4.5, 8.1) for y in (-4.5, 2.1)] + \
          [("smoke_detector", -7.8, 2.4)] + \
          [("sprinkler_head", x, y) for x in (-8.1, -5.7, -2.1, 0.3, 2.7, 5.1, 7.5) for y in (-5.7, -2.1, 1.5)]
CEIL_Z = 3.20
# R03 map frame (= H2 docked pose): world (-1.415, -0.28), yaw 180; S1 docked pose: world (-6.4, 0.6), heading +Y
S1_DOCK = (-6.4, 0.6, 90.0)


def local_rect(asset, yaw):
    """Plan bbox (x0, x1, y0, y1) of an asset rotated by yaw about its origin (measured from its USD)."""
    import math
    a = Usd.Stage.Open(asset)
    r = UsdGeom.BBoxCache(0, ["default", "render"]).ComputeWorldBound(a.GetDefaultPrim()).ComputeAlignedRange()
    lo, hi = r.GetMin(), r.GetMax()
    c, s_ = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    pts = [(c * x - s_ * y, s_ * x + c * y) for x in (lo[0], hi[0]) for y in (lo[1], hi[1])]
    return min(p[0] for p in pts), max(p[0] for p in pts), min(p[1] for p in pts), max(p[1] for p in pts)


def snapped(asset, x, y, yaw, snap):
    if not snap:
        return x, y
    side, wall, gap = snap
    x0, x1, y0, y1 = local_rect(asset, yaw)
    if side == "N":
        return x, wall - gap - y1
    if side == "S":
        return x, wall + gap - y0
    if side == "E":
        return wall - gap - x1, y
    return wall + gap - x0, y


def placed(st, path, asset, xyz, yaw, sem):
    prim = UsdGeom.Xform.Define(st, path).GetPrim()
    prim.GetReferences().AddReference(os.path.relpath(asset, os.path.dirname(OUT)))
    x = UsdGeom.Xformable(prim)
    x.AddTranslateOp().Set(Gf.Vec3d(*map(float, xyz)))
    x.AddRotateZOp().Set(float(yaw))
    for k, v in sem.items():
        prim.CreateAttribute(k, Sdf.ValueTypeNames.String, custom=True).Set(str(v))
    return prim


def main():
    # the lab content is its own layer (scenes/lab_site.usda) so other layers (e.g. a culture run) can stack on it;
    # lab_twin.usda = lab_site + the Cell 01 overlay
    for f in (OUT, SITE_LAYER):
        if os.path.exists(f):
            os.remove(f)
    st = Usd.Stage.CreateNew(SITE_LAYER)
    layer = st.GetRootLayer()
    UsdGeom.SetStageUpAxis(st, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(st, 1.0)
    st.SetStartTimeCode(0)
    st.SetEndTimeCode(1000000)
    st.SetTimeCodesPerSecond(60)
    st.SetDefaultPrim(st.OverridePrim("/World"))
    layer.comment = "AICOR Lab 1 site layer generated by tools/compose_lab.py; edit the scripts, not this file."
    lab = UsdGeom.Xform.Define(st, LAB).GetPrim()
    for k, v in (("sdt:siteId", "AICOR-LAB1"), ("sdt:status", STATUS),
                 ("sdt:contains", "Cell 01 (/World/Cell01) + storage room ST01 + culture prep + operator area"),
                 ("sdt:designBasis", "project-owned proxies with generic class dimensions; manufacturer CAD not acquired")):
        lab.CreateAttribute(k, Sdf.ValueTypeNames.String, custom=True).Set(v)
    placed(st, f"{LAB}/Building", SITE, (0, 0, 0), 0, {})
    # the Cell 01 floor cube stays the cell collider; the hall's epoxy floor is the visual
    UsdGeom.Imageable(st.OverridePrim("/World/Cell01/Architecture/Floor")).CreatePurposeAttr(UsdGeom.Tokens.guide)

    missing, eq = [], []
    for zone, pid, asset, x, y, z, yaw, snap in PLACEMENTS:
        path = os.path.join(EQ, f"{asset}.usda")
        if not os.path.exists(path):
            missing.append(asset)
            continue
        x, y = snapped(path, x, y, yaw, snap)
        prim = placed(st, f"{LAB}/{zone}/{pid}", path, (x, y, z), yaw, {"sdt:siteAssetId": pid, "sdt:zone": zone})
        eq.append(dict(id=pid, asset=asset, zone=zone, pose=[x, y, z, yaw], prim=str(prim.GetPath())))
    for i, (asset, x, y) in enumerate(CEILING):
        path = os.path.join(EQ, f"{asset}.usda")
        if not os.path.exists(path):
            missing.append(asset)
            continue
        placed(st, f"{LAB}/Ceiling/{asset}_{i:02d}", path, (x, y, CEIL_Z), 0, {})

    # S1 dispatch dock: a second H2-type dock in the storage room (R03 docks heading north)
    s1 = placed(st, f"{LAB}/StorageRoom/S1_DispatchDock", H2, (S1_DOCK[0], S1_DOCK[1], 0.0), S1_DOCK[2],
                {"sdt:siteAssetId": "S1_DispatchDock", "sdt:zone": "StorageRoom",
                 "sdt:role": "R03 dispatch / charging dock where staff load the clean-sample carrier"})
    s1.CreateAttribute("sdt:componentId", Sdf.ValueTypeNames.String, custom=True).Set("S1")

    # semantic zones
    for name, (x0, x1, y0, y1, role) in ZONES.items():
        z = UsdGeom.Xform.Define(st, f"{LAB}/Zones/{name}").GetPrim()
        z.CreateAttribute("sdt:extent_xy", Sdf.ValueTypeNames.Double4, custom=True).Set(Gf.Vec4d(x0, x1, y0, y1))
        z.CreateAttribute("sdt:role", Sdf.ValueTypeNames.String, custom=True).Set(role)

    # daylight: the Cell 01 dome becomes the sky seen through the windows, plus a low sun from the south-west
    dome = UsdLux.DomeLight(st.OverridePrim("/World/EnvironmentLight"))
    dome.CreateIntensityAttr(2200.0)
    dome.CreateColorAttr(Gf.Vec3f(0.80, 0.88, 1.0))
    sun = UsdLux.DistantLight.Define(st, f"{LAB}/Sun")
    sun.CreateIntensityAttr(2500.0)
    sun.CreateAngleAttr(0.53)
    sun.CreateColorTemperatureAttr(5600.0)
    sun.CreateEnableColorTemperatureAttr(True)
    xf = UsdGeom.Xformable(sun.GetPrim())
    xf.AddRotateZOp().Set(-25.0)
    xf.AddRotateXOp().Set(58.0)

    # R03 leaves the cell on the site route: widen its planar X travel (map frame) in this scene only
    jx = st.OverridePrim("/World/Cell01/Robots/R03_SampleAMR/Joints/PlanarXJoint")
    jx.CreateAttribute("physics:upperLimit", Sdf.ValueTypeNames.Float).Set(8.5)
    jx.CreateAttribute("physics:lowerLimit", Sdf.ValueTypeNames.Float).Set(-11.5)
    jx.CreateAttribute("sdt:note", Sdf.ValueTypeNames.String, custom=True).Set(
        "lab scene: map-frame X travel widened to the whole hall (Cell 01 scene keeps -4.0 .. 0.06 m)")
    jy = st.OverridePrim("/World/Cell01/Robots/R03_SampleAMR/Joints/PlanarYJoint")
    jy.CreateAttribute("physics:lowerLimit", Sdf.ValueTypeNames.Float).Set(-5.0)
    jy.CreateAttribute("physics:upperLimit", Sdf.ValueTypeNames.Float).Set(7.0)
    jy.CreateAttribute("sdt:note", Sdf.ValueTypeNames.String, custom=True).Set(
        "lab scene: map-frame Y travel widened to the whole hall; Cell 01's +-3.5 m stopped R03 0.48 m south of the "
        "AMR lane (found by the site route test)")
    layer.Save()
    top = Usd.Stage.CreateNew(OUT)
    top.GetRootLayer().subLayerPaths = [os.path.relpath(SITE_LAYER, os.path.dirname(OUT)),
                                        os.path.relpath(CELL, os.path.dirname(OUT))]
    UsdGeom.SetStageUpAxis(top, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(top, 1.0)
    top.SetStartTimeCode(0)
    top.SetEndTimeCode(1000000)
    top.SetTimeCodesPerSecond(60)
    top.SetDefaultPrim(top.OverridePrim("/World"))
    top.GetRootLayer().comment = "Whole-lab twin = scenes/lab_site.usda over the Cell 01 overlay (tools/compose_lab.py)."
    top.GetRootLayer().Save()

    site = {"status": STATUS, "frame": "Cell 01 frame (origin cell floor centre, +Y rear instrument wall)",
            "zones": {k: dict(extent_xy=v[:4], role=v[4]) for k, v in ZONES.items()},
            "equipment": eq, "s1_dock": dict(pose=list(S1_DOCK), asset="assets/r03/h2_dock.usda"),
            "missing_assets": sorted(set(missing))}
    sys.path.insert(0, os.path.join(ROOT, "assets", "site"))
    import build_site as bs  # noqa: E402
    site.update(hall=bs.HALL, storage=bs.STORE, storage_door=bs.STORE_DOOR, entrance=bs.ENTRANCE,
                amr_route=bs.AMR_ROUTE, ceiling_height=bs.H)
    json.dump(site, open(os.path.join(ROOT, "scenes", "site_layout_s1.json"), "w"), indent=1)
    print(f"wrote {OUT}: {len(eq)} equipment items placed; missing assets: {sorted(set(missing)) or 'none'}")


if __name__ == "__main__":
    main()
