"""R02 (rail + UR5e + tool-changer robot half) as one 8-DOF URDF: assets/r02/r02.urdf.

Composition (Cell 01 sdt/components/R02_RailMounted_UR5e.yaml: 8-DOF articulated system, rail_joint prismatic X,
2.6 m travel; D004):
  rail_base (fixed root: beam + stand)  --rail_joint (prismatic X, 0..2.6 m)-->  rail_carriage
  rail_carriage --fixed--> UR5e (official ur_description xacro, tf_prefix r02_)
  r02_tool0 --fixed--> tc_robot_half (automatic tool changer, robot side; Zimmer WMR2063 class, proxy dimensions)

The UR5e comes from the Cell 01 kit's Universal_Robots_ROS2_Description (BSD-3-Clause), read in place; its yaml
parameters and meshes are resolved to absolute paths. The rail, stand, carriage and coupler are project-owned
parametric proxies for the igus drylin ZLW-1660 axis and the WMR2063 (no manufacturer CAD; Cell 01 option A).
The asset origin is the carriage home position at floor level: place it at (rail x0, rail y, 0).

Run with the CAD venv (has xacro):  env_cad/bin/python tools/make_r02_urdf.py
"""

import os

import xacro
import xacro.substitution_args as sa

UR_DESC = os.path.expanduser(
    "~/ResearchSpace/projects/robot-scientist/cell-01/AICOR_Cell01_Codex_Handoff/simulation/isaac_sim/"
    "manufacturer_grounded/02_source_assets/open_source/Universal_Robots_ROS2_Description")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "assets/r02/r02.urdf")
BUILD = os.path.join(ROOT, "assets/r02/build")

TRAVEL = 2.6              # m (D004)
BEAM = (0.11, 0.09)       # rail profile width, height (m); the Cell 01 placeholder rail's cross-section
RAIL_TOP = 0.965          # m above the floor (Cell 01 rail centre 0.92 + half height)
CARRIAGE = (0.30, 0.22, 0.03)
TC_ROBOT = (0.0315, 0.016)  # coupler robot half radius, length (WMR2063-class proxy; + 12 mm tool half = 28 mm)


def box(name, size, xyz, mass=None, rgba="0.75 0.77 0.80 1"):
    inertial = ""
    if mass:
        sx, sy, sz = size
        inertial = (f'<inertial><origin xyz="{xyz}"/><mass value="{mass}"/><inertia ixx="{mass * (sy * sy + sz * sz) / 12:.6f}" '
                    f'iyy="{mass * (sx * sx + sz * sz) / 12:.6f}" izz="{mass * (sx * sx + sy * sy) / 12:.6f}" ixy="0" ixz="0" iyz="0"/></inertial>')
    geo = f'<geometry><box size="{size[0]} {size[1]} {size[2]}"/></geometry>'
    return (f'<visual name="{name}"><origin xyz="{xyz}"/>{geo}<material name="{name}_m"><color rgba="{rgba}"/></material></visual>'
            f'<collision name="{name}_c"><origin xyz="{xyz}"/>{geo}</collision>', inertial)


def main():
    length = TRAVEL + CARRIAGE[0] + 0.10
    beam_v, _ = box("beam", (length, *BEAM), f"{TRAVEL / 2} 0 {RAIL_TOP - BEAM[1] / 2}", rgba="0.70 0.72 0.75 1")
    legs = "".join(box(f"leg{i}", (0.08, 0.08, RAIL_TOP - BEAM[1]), f"{x} 0 {(RAIL_TOP - BEAM[1]) / 2}",
                       rgba="0.45 0.47 0.50 1")[0] for i, x in enumerate((-0.10, TRAVEL / 2, TRAVEL + 0.10)))
    car_v, car_i = box("carriage", CARRIAGE, f"0 0 {CARRIAGE[2] / 2}", mass=3.0, rgba="0.30 0.32 0.35 1")
    r, h = TC_ROBOT
    m = 0.35
    tc_i = (f'<inertial><origin xyz="0 0 {h / 2}"/><mass value="{m}"/><inertia ixx="{m * (3 * r * r + h * h) / 12:.6f}" '
            f'iyy="{m * (3 * r * r + h * h) / 12:.6f}" izz="{m * r * r / 2:.6f}" ixy="0" ixz="0" iyz="0"/></inertial>')
    tc_g = f'<geometry><cylinder radius="{r}" length="{h}"/></geometry>'
    # collider 1 mm short of the coupling face: the coupler lock's probe ray starts on that face (twin/r02_rig.py)
    tc_gc = f'<geometry><cylinder radius="{r}" length="{h - 0.001}"/></geometry>'
    xml = f"""<?xml version="1.0"?>
<robot xmlns:xacro="http://www.ros.org/wiki/xacro" name="r02">
  <xacro:include filename="$(find ur_description)/urdf/ur_macro.xacro"/>
  <link name="rail_base">{beam_v}{legs}
    <inertial><origin xyz="{TRAVEL / 2} 0 0.5"/><mass value="60"/><inertia ixx="10" iyy="40" izz="40" ixy="0" ixz="0" iyz="0"/></inertial>
  </link>
  <joint name="rail_joint" type="prismatic">
    <parent link="rail_base"/><child link="rail_carriage"/>
    <origin xyz="0 0 {RAIL_TOP}"/><axis xyz="1 0 0"/>
    <limit lower="0" upper="{TRAVEL}" effort="1500" velocity="1.0"/>
  </joint>
  <link name="rail_carriage">{car_v}{car_i}</link>
  <xacro:ur_robot name="r02_ur5e" tf_prefix="r02_" parent="rail_carriage"
    joint_limits_parameters_file="$(find ur_description)/config/ur5e/joint_limits.yaml"
    kinematics_parameters_file="$(find ur_description)/config/ur5e/default_kinematics.yaml"
    physical_parameters_file="$(find ur_description)/config/ur5e/physical_parameters.yaml"
    visual_parameters_file="$(find ur_description)/config/ur5e/visual_parameters.yaml"
    safety_limits="false" force_abs_paths="true">
    <origin xyz="0 0 {CARRIAGE[2]}" rpy="0 0 0"/>
  </xacro:ur_robot>
  <joint name="tc_mount" type="fixed"><parent link="r02_tool0"/><child link="tc_robot_half"/><origin xyz="0 0 0"/></joint>
  <link name="tc_robot_half">
    <visual name="tc"><origin xyz="0 0 {h / 2}"/>{tc_g}<material name="tc_m"><color rgba="0.62 0.64 0.68 1"/></material></visual>
    <collision name="tc_c"><origin xyz="0 0 {(h - 0.001) / 2}"/>{tc_gc}</collision>{tc_i}
  </link>
</robot>
"""
    os.makedirs(BUILD, exist_ok=True)
    src = os.path.join(BUILD, "r02.urdf.xacro")
    with open(src, "w") as f:
        f.write(xml)
    orig = sa._eval_find
    sa._eval_find = lambda pkg: UR_DESC if pkg == "ur_description" else orig(pkg)
    doc = xacro.process_file(src)
    out = doc.toprettyxml(indent="  ").replace("package://ur_description", UR_DESC).replace("file://", "")
    with open(OUT, "w") as f:
        f.write(out)
    joints = [j for j in doc.getElementsByTagName("joint") if j.getAttribute("type") != "fixed"]
    print("wrote", OUT, "movable joints:", [j.getAttribute("name") for j in joints])


if __name__ == "__main__":
    main()
