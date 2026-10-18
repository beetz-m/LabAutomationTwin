"""Figures of a culture run: belief vs (audit-only) truth trajectories, plate maps, 4x micrograph contact sheet."""

import os


DESIGN_LABEL = {"A03": "0.25 au", "A04": "0.25 au + rescue", "B03": "0.45 au", "B04": "0.45 au + rescue",
                "C03": "0.65 au", "C04": "0.65 au + rescue", "D03": "0.85 au", "D04": "0.85 au + rescue",
                "E03": "control", "E04": "control", "F03": "control", "F04": "control"}


KIND_COLOR = {"challenge": "tab:red", "rescue": "tab:green", "vehicle": "tab:gray"}


def dashboard(run, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    wells = list(run["belief"])
    labels = (run.get("design") or {}).get("labels") or DESIGN_LABEL
    rows = -(-len(wells) // 4)
    fig, axes = plt.subplots(rows, 4, figsize=(18, 3.7 * rows), sharex=True, sharey=True, squeeze=False)
    for ax in axes.ravel()[len(wells):]:
        ax.set_visible(False)
    for ax, w in zip(axes.ravel(), wells):
        b = run["belief"][w]
        t = [h["t_h"] for h in b]
        for k, col in (("V", "tab:blue"), ("I", "tab:red")):
            ax.fill_between(t, [h[k]["p05"] for h in b], [h[k]["p95"] for h in b], color=col, alpha=0.18, lw=0)
            ax.plot(t, [h[k]["mean"] for h in b], color=col, lw=2, label=f"SDT belief {k} (90 %)")
            tr = run["truth"][w]
            ax.plot([h["t_h"] for h in tr], [h[k] for h in tr], color=col, ls="--", lw=1, alpha=0.8,
                    label=f"simulator truth {k} (audit only)")
        for o in run["observations"][w]:
            ax.axvline(o["t_h"], color="tab:gray" if o["accepted"] else "tab:purple", lw=0.6 if o["accepted"] else 2,
                       alpha=0.35 if o["accepted"] else 0.9)
        for e in run["interventions"]:
            if e["well"] == w:
                ax.axvline(e["t_h"], color=KIND_COLOR.get(e["kind"], "tab:green") if e["committed"]
                           else "tab:orange", lw=3, alpha=0.6)
        title = f"{w}  {labels.get(w, '')}"
        if w in run["anomalies"]:
            title += f"  [{run['anomalies'][w]['state']} @ {run['anomalies'][w]['t_h']:.0f} h]"
        rej = [e for e in run["interventions"] if e["well"] == w and not e["committed"]]
        if rej:
            title += "  [dose not committed]"
        ax.set_title(title, fontsize=10)
        ax.set_ylim(0, 1.02)
        ax.grid(alpha=0.25)
    for ax in axes[-1]:
        ax.set_xlabel("culture time (h)")
    for ax in axes[:, 0]:
        ax.set_ylabel("normalised state")
    axes[0, 0].legend(fontsize=7, loc="lower left")
    fig.suptitle(f"Culture SDT run '{run['scenario']}': belief (bands) from robot records + 4x images vs the hidden "
                 f"simulated culture (dashed). V viability, I injury. Illustrative Cell 01 surrogate (D016). "
                 f"90 % coverage {run['audit']['coverage_V_90']:.2f}", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(path, dpi=100)
    plt.close(fig)


def plate_maps(run, path, times=(0.0, 6.0, 24.0, 72.0)):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle
    fig, axes = plt.subplots(2, len(times), figsize=(4.6 * len(times), 7.2))
    cmap = plt.get_cmap("RdYlGn")
    for j, t in enumerate(times):
        for i, (src, title) in enumerate((("belief", "SDT belief V (ring: 90 % width; orange: dose not verified)"), ("truth", "hidden truth V"))):
            ax = axes[i, j]
            for r in range(8):
                for c in range(12):
                    ax.add_patch(Circle((c, -r), 0.42, color="0.88"))
            for w in run["belief"]:
                r, c = "ABCDEFGH".index(w[0]), int(w[1:]) - 1
                if src == "belief":
                    h = min(run["belief"][w], key=lambda x: abs(x["t_h"] - t))
                    v, u = h["V"]["mean"], (h["V"]["p95"] - h["V"]["p05"])
                    ax.add_patch(Circle((c, -r), 0.42, color=cmap(v)))
                    ax.add_patch(Circle((c, -r), 0.42, fill=False, lw=1 + 25 * u, ec="k", alpha=0.6))
                else:
                    h = min(run["truth"][w], key=lambda x: abs(x["t_h"] - t))
                    ax.add_patch(Circle((c, -r), 0.42, color=cmap(h["V"])))
                if w in run["anomalies"] and t >= run["anomalies"][w]["t_h"]:
                    ax.text(c, -r, "!", ha="center", va="center", fontsize=14, color="purple", weight="bold")
                if src == "belief" and any(ev["well"] == w and not ev["committed"] and ev["t_h"] <= t
                                           for ev in run["interventions"]):
                    ax.add_patch(Circle((c, -r), 0.50, fill=False, lw=2.2, ec="tab:orange"))
            ax.set_xlim(-0.6, 11.6)
            ax.set_ylim(-7.6, 0.6)
            ax.set_aspect("equal")
            ax.set_xticks(range(12), [str(k + 1) for k in range(12)], fontsize=7)
            ax.set_yticks([-k for k in range(8)], list("ABCDEFGH"), fontsize=7)
            ax.set_title(f"{title}, t = {t:.0f} h", fontsize=9)
    fig.suptitle(f"Plate_P17 - run '{run['scenario']}'" + (f" (design plate {run['design']['design_plate']})"
                 if run.get("design", {}).get("design_plate") else ""), fontsize=12)
    fig.tight_layout()
    fig.savefig(path, dpi=100)
    plt.close(fig)


def contact_sheet(img_dir, wells, times, path, scale=0.6, labels=None):
    from PIL import Image, ImageDraw, ImageFont
    s = int(200 * scale)
    lw = 70 if not labels else 230
    W, H = lw + s * len(times), 30 + s * len(wells)
    sheet = Image.new("RGB", (W, H), (20, 22, 26))
    d = ImageDraw.Draw(sheet)
    try:
        f = ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-Medium.otf", 14)
    except OSError:
        f = ImageFont.load_default()
    for j, t in enumerate(times):
        d.text((lw + j * s + 4, 6), f"{t:.0f} h", font=f, fill=(220, 225, 235))
    for i, w in enumerate(wells):
        d.text((6, 30 + i * s + s // 2 - 8), w + (f"  {labels.get(w, '')}" if labels else ""), font=f, fill=(220, 225, 235))
        for j, t in enumerate(times):
            p = os.path.join(img_dir, f"{w}_{t:04.1f}h.png")
            if os.path.exists(p):
                sheet.paste(Image.open(p).convert("RGB").resize((s - 2, s - 2)), (lw + j * s, 30 + i * s))
    sheet.save(path)


def arm_panel(run, img_dir, path, thumbs=(0.0, 24.0, 48.0, 72.0)):
    """Per arm of a design: its schedule (what is given when), the belief about each unit's viability against the
    hidden simulated truth, and the first unit's 4x images at a few times. ILLUSTRATIVE surrogate (D016)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from PIL import Image
    D = run["design"]
    arms = D["arms"]
    n, k = len(arms), len(thumbs)
    fig = plt.figure(figsize=(4.2 + 3.2 + 1.55 * k, 2.25 * n + 0.9))
    gs = fig.add_gridspec(n, 2 + k, width_ratios=[1.35, 2.3] + [1] * k, hspace=0.35, wspace=0.18)
    for i, (arm, wells) in enumerate(arms.items()):
        ax0 = fig.add_subplot(gs[i, 0])
        evs = [p for p in D["plan"] if p[1] == wells[0]]
        ax0.axhline(0, color="0.7", lw=1)
        last = -99.0
        for t, w, kind, au in evs:
            ax0.plot([t], [0], marker="v" if kind != "vehicle" else "o", ms=13 if kind != "vehicle" else 8,
                     color=KIND_COLOR.get(kind, "k"))
            y = 0.3 if t - last > 14 else 1.05          # stagger labels of events close in time
            last = t if y == 0.3 else last
            ax0.text(t, y, (kind if kind == "vehicle" else f"{kind} {au:g} au") + f"\n{t:g} h", ha="center",
                     va="bottom", fontsize=7, color=KIND_COLOR.get(kind, "k"))
        for t in thumbs:
            ax0.plot([t], [-0.3], marker="s", ms=5, color="tab:blue")
        ax0.set_xlim(-6, 78)
        ax0.set_ylim(-0.8, 2.1)
        ax0.set_yticks([])
        ax0.set_xticks([0, 24, 48, 72])
        for sp in ("left", "right", "top"):
            ax0.spines[sp].set_visible(False)
        ax0.set_title(f"{arm.replace('_', ' ')}  ({len(wells)} unit{'s' if len(wells) > 1 else ''})", fontsize=10,
                      loc="left", weight="bold")
        if i == n - 1:
            ax0.set_xlabel("culture time (h); squares: images shown", fontsize=8)
        ax1 = fig.add_subplot(gs[i, 1])
        for j, w in enumerate(wells):
            b = run["belief"][w]
            t = [h["t_h"] for h in b]
            col = plt.get_cmap("tab10")(j)
            ax1.fill_between(t, [h["V"]["p05"] for h in b], [h["V"]["p95"] for h in b], color=col, alpha=0.15, lw=0)
            ax1.plot(t, [h["V"]["mean"] for h in b], color=col, lw=1.8, label=f"{w} belief")
            tr = run["truth"][w]
            ax1.plot([h["t_h"] for h in tr], [h["V"] for h in tr], color=col, lw=0.9, ls="--")
        for t, w, kind, au in evs:
            if kind != "vehicle":
                ax1.axvline(t, color=KIND_COLOR[kind], alpha=0.35, lw=2)
        ax1.set_ylim(0, 1.02)
        ax1.set_xlim(0, 72)
        ax1.set_xticks([0, 24, 48, 72])
        ax1.grid(alpha=0.25)
        ax1.set_ylabel("viability", fontsize=8)
        ax1.legend(fontsize=6.5, loc="lower left", frameon=False)
        if i == 0:
            ax1.set_title("belief (band: 90 %) vs hidden truth (dashed)", fontsize=9)
        if i == n - 1:
            ax1.set_xlabel("culture time (h)", fontsize=8)
        for j, t in enumerate(thumbs):
            ax = fig.add_subplot(gs[i, 2 + j])
            p = os.path.join(img_dir, f"{wells[0]}_{t:04.1f}h.png")
            if os.path.exists(p):
                ax.imshow(Image.open(p), cmap="gray", vmin=0, vmax=255)
            ax.set_xticks([])
            ax.set_yticks([])
            if i == 0:
                ax.set_title(f"{t:.0f} h", fontsize=9)
            if j == 0:
                ax.set_ylabel(wells[0], fontsize=8)
    fig.suptitle(f"{D['name']} design, arm by arm: schedule, belief and 4x images (Culture SDT; illustrative "
                 "Cell 01 surrogate, D016)", fontsize=11, x=0.01, ha="left")
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)
