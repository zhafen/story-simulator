"""Minimal top-down frame: bodies + velocity arrows. Edit STATE per turn."""
import sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

t = 0.4
STATE = [  # name, x, y, vx, vy, color
    ("Player", 1.13, 0.00, 2.83, 0.00, "#2b6cb0"),
    ("TDTFB", 2.00, 0.15, 0.00, 1.55, "#c05621"),
]
HISTORY = [  # (x, y, color) at earlier turns, drawn as empty circles
    (0.57, 0.00, "#2b6cb0"), (0.85, 0.00, "#2b6cb0"),  # player t=0.2, 0.3
    (2.00, 0.00, "#c05621"), (2.00, 0.00, "#c05621"),  # TDTFB t=0.2, 0.3
]
fig, ax = plt.subplots(figsize=(6, 3), dpi=150)
for x, y, c in HISTORY:
    ax.add_patch(Circle((x, y), 0.225, fill=False, color=c, lw=1, alpha=.5))
for name, x, y, vx, vy, c in STATE:
    ax.add_patch(Circle((x, y), 0.225, color=c, alpha=.35))
    ax.annotate("", xy=(x + vx * .2, y + vy * .2), xytext=(x, y),
                arrowprops=dict(arrowstyle="->", color=c, lw=2))
    ax.text(x, -.45, name, ha="center", va="top", fontsize=9, color=c)
ax.set_aspect("equal"); ax.set_xlim(-.3, 2.7); ax.set_ylim(-.7, .8)
ax.set_xticks([0, 1, 2]); ax.set_yticks([])
ax.set_xlabel("m"); ax.set_title(f"t = {t} s", fontsize=10)
for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
# Reachable region for the player over the next step (DT): release up to
# STORED joules as a velocity change of magnitude sqrt(2E/m) in any direction.
import math
DT, STORED, M = 0.1, 240, 75
px, py, pvx, pvy = 1.13, 0.00, 2.83, 0.00
dv = math.sqrt(2 * STORED / M)
ax.add_patch(Circle((px + pvx * DT, py + pvy * DT), dv * DT,
                    color="#2b6cb0", alpha=.12, ls="--", lw=1))
ax.add_patch(Circle((px + pvx * DT, py + pvy * DT), dv * DT,
                    fill=False, color="#2b6cb0", ls="--", lw=1))
# Comparison: "adds exactly its energy" rule -> final speed sqrt(v0^2 + 2E/m)
# in any direction, measured from the current position.
v_e = math.sqrt(pvx**2 + pvy**2 + 2 * STORED / M)
ax.add_patch(Circle((px, py), v_e * DT, fill=False, color="#2f855a", ls=":", lw=1.5))
ax.text(.0, .7, "- - velocity rule (release adds 2.53 m/s)", fontsize=7, color="#2b6cb0")
ax.text(.0, .58, "···· energy rule (always 3.80 m/s)", fontsize=7, color="#2f855a")
fig.tight_layout(); fig.savefig(sys.argv[1] if len(sys.argv) > 1 else f"docs/combat/frames/t{t}.png")
