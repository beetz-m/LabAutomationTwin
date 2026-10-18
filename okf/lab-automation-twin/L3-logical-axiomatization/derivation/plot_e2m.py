"""Figures of the experiment-to-motion derivation: EIG landscape with the requirement, and the derived plan's timeline."""

import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.dirname(os.path.dirname(HERE))
DOCS = os.path.join(MOD, "docs")


def landscape(plan, cands, dst):
    doses = sorted({c["dose_au"] for c in cands["candidates"]})
    delays = sorted({c["delay_h"] for c in cands["candidates"]})
    reps = sorted({c["reps"] for c in cands["candidates"]})
    fig, axs = plt.subplots(1, len(reps), figsize=(13, 3.9), sharey=True)
    g, sel = plan["requirement_bits"], plan["selected"]
    for ax, n in zip(axs, reps):
        Z = np.array([[next(c["eig_bits"] for c in cands["candidates"] if c["dose_au"] == d and c["delay_h"] == t
                            and c["reps"] == n) for t in delays] for d in doses])
        im = ax.imshow(Z, origin="lower", cmap="viridis", vmin=0, vmax=0.7, aspect="auto")
        for i in range(len(doses)):
            for j in range(len(delays)):
                ok = Z[i, j] >= g
                ax.text(j, i, f"{Z[i, j]:.2f}", ha="center", va="center", fontsize=9,
                        color="black" if Z[i, j] > 0.45 else "white", weight="bold" if ok else "normal")
                if ok:
                    ax.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False, ec="white", lw=1.2, ls=":"))
        if n == sel["reps"]:
            i, j = doses.index(sel["dose_au"]), delays.index(sel["delay_h"])
            ax.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False, ec="#ff3b30", lw=3))
        ax.set_xticks(range(len(delays)), [f"{t} h" for t in delays])
        ax.set_yticks(range(len(doses)), [f"{d} au" for d in doses])
        ax.set_title(f"{n} replicate{'s' if n > 1 else ''} per arm  (cost {plan['candidate_optima'].get(next((c['id'] for c in cands['candidates'] if c['reps'] == n and c['eig_bits'] >= g), ''), '—')})",
                     fontsize=10)
        ax.set_xlabel("rescue delay")
    axs[0].set_ylabel("challenge dose")
    fig.colorbar(im, ax=axs, shrink=0.9, label="EIG (bits)  [max log2 3 = 1.585]")
    fig.suptitle(f"Expected information gain over M1-M3 (illustrative, D016). Required g = {g} bits: dotted = meets g, "
                 f"red = selected (least cost, then max EIG): {sel['id']}", fontsize=10)
    fig.savefig(dst, dpi=150, bbox_inches="tight")
    plt.close(fig)


def timeline(plan, dst, exe=None):
    lanes = ["safety", "l10", "r01", "r02", "l12", "l17", "l21"]
    colors = {"motion": "#4c78a8", "tool": "#9d755d", "device_command": "#59a14f", "safety_step": "#e15759"}
    trips = plan["sessions"]
    fig, axs = plt.subplots(len(trips), 1, figsize=(14, 1.9 * len(trips) + 0.6), squeeze=False)
    for ax, se in zip(axs[:, 0], trips):
        t = 0.0
        for st in se["steps"]:
            who = "safety" if st["level"] == "safety_step" else (st.get("robot") or st.get("device"))
            if who not in lanes:
                who = "safety"
            d = max(st["duration_s"], 0.6)
            ax.barh(lanes.index(who), d, left=t, color=colors[st["level"]], edgecolor="white", lw=0.4)
            if st["primitive"] in ("dispense", "image_well") or (st["duration_s"] >= 6 and st["primitive"] not in
                                                                  ("tip_pick", "aspirate", "tip_eject")):
                lab = (st["material"][1].upper() if st["primitive"] in ("dispense", "image_well") else st["primitive"])
                ax.text(t + d / 2, lanes.index(who), lab, ha="center", va="center", fontsize=6.5, color="white",
                        rotation=0, clip_on=True)
            t += st["duration_s"]
        title = (f"{se['session']} trip {se['trip']} at culture t = {se['t_h']} h — {se['device'].upper()}: "
                 f"{len(se['steps'])} steps, predicted {se['duration_s']:.0f} s (window {plan['window_s']:.0f} s)")
        if exe:
            tr = next((x for x in exe["trips"] if x["id"] == se["id"]), None)
            if tr:
                title += f"; twin execution {tr['steps_ok']}/{tr['steps_total']} steps ok, {tr['duration_s']:.0f} s"
                for x in tr["executed"]:
                    if x["ok"] and x["primitive"] in ("lift", "retract", "dispense", "store", "image_well"):
                        ax.plot([x["t"]], [lanes.index(x["who"]) + 0.42], marker="v", color="black", ms=3.5)
        ax.set_title(title, fontsize=9, loc="left")
        ax.set_yticks(range(len(lanes)), [x.upper() if x != "safety" else "safety" for x in lanes], fontsize=8)
        ax.set_xlim(0, max(plan["window_s"], max(s["duration_s"] for s in trips) * 1.05))
        ax.axvline(plan["window_s"] / 1.2, color="#e15759", ls="--", lw=0.8)
        ax.invert_yaxis()
    axs[-1, 0].set_xlabel("seconds outside the incubator (dashed: window / 1.2, the robust bound of S5)"
                          + ("; ▼ twin completion times" if exe else ""))
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in colors.values()]
    fig.legend(handles, ["motion designator", "tool change", "device command (L12: tip, aspirate, dispense <well>, "
                         "eject; L17: image <well>)", "safety step"], loc="lower center", ncol=4, fontsize=8,
               bbox_to_anchor=(0.5, 0.0))
    s = plan["selected"]
    fig.suptitle(f"Derived plan for g = {plan['requirement_bits']} bits: {s['dose_au']} au challenge, rescue "
                 f"{s['rescue_au']} au at {s['delay_h']} h, {s['reps']} replicate(s); wells "
                 + "; ".join(f"{k} {', '.join(v)}" for k, v in plan["wells"].items()), fontsize=10, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    fig.savefig(dst, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    tag = sys.argv[1] if len(sys.argv) > 1 else "g050"
    plan = json.load(open(os.path.join(HERE, "out", f"plan_{tag}.json")))
    cands = json.load(open(os.path.join(MOD, "build", "e2m", "eig_candidates.json")))
    exe_p = os.path.join(MOD, "..", "..", "test_reports", "e2m", f"plan_execution_{tag}.json")
    exe = json.load(open(exe_p)) if os.path.exists(exe_p) else None
    landscape(plan, cands, os.path.join(DOCS, f"e2m_eig_landscape_{tag}.png"))
    timeline(plan, os.path.join(DOCS, f"e2m_plan_{tag}.png"), exe)
    print(f"[plot] docs/e2m_eig_landscape_{tag}.png, docs/e2m_plan_{tag}.png" + (" (with twin execution)" if exe else ""))
