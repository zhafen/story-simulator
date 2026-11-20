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
    (0.00, 0.00, "#2b6cb0"),  # player start (t=0)
    (0.57, 0.00, "#2b6cb0"), (0.85, 0.00, "#2b6cb0"),  # player t=0.2, 0.3
    (2.00, 0.00, "#c05621"), (2.00, 0.00, "#c05621"),  # TDTFB t=0.2, 0.3
]
fig = plt.figure(figsize=(6.6, 4), dpi=150)
bx = fig.add_axes([0.08, 0.2, 0.04, 0.6])   # player's energy store bar
ax = fig.add_axes([0.15, 0.08, 0.83, 0.84])
CAP, P_W, STEP = 300, 600, 0.1
STORE_NOW = 240
store_next = min(CAP, STORE_NOW + P_W * STEP)
bx.bar(0, CAP, color="none", edgecolor="#2b6cb0", lw=1)
bx.bar(0, store_next, color="#2b6cb0", alpha=.2)
bx.bar(0, STORE_NOW, color="#2b6cb0", alpha=.7)
bx.set_xlim(-.5, .5); bx.set_ylim(0, CAP); bx.set_xticks([])
bx.set_yticks([0, STORE_NOW, CAP]); bx.tick_params(labelsize=7)
bx.set_title("Player\nstore (J)", fontsize=7)
for sp in ("top", "right"): bx.spines[sp].set_visible(False)
for x, y, c in HISTORY:
    ax.add_patch(Circle((x, y), 0.225, fill=False, color=c, lw=1, alpha=.5))
for name, x, y, vx, vy, c in STATE:
    ax.add_patch(Circle((x, y), 0.225, color=c, alpha=.35))
    ax.annotate("", xy=(x + vx * .2, y + vy * .2), xytext=(x, y),
                arrowprops=dict(arrowstyle="->", color=c, lw=2))
    for R, ls in ((0.8, "-"), (1.0, ":")):  # punch / kick reach from body centre
        ax.add_patch(Circle((x, y), R, fill=False, color=c, ls=ls, lw=.8, alpha=.6))
    ax.text(x, -.45, name, ha="center", va="top", fontsize=9, color=c)
ax.set_aspect("equal"); ax.set_xlim(-.4, 3.1); ax.set_ylim(-1.1, 1.3)
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
PACE = 1.0  # jogging step length, m (~2.8 m/s at ~165 steps/min)
ax.plot([0, PACE], [.3, .3], color="#2b6cb0", lw=2)
ax.plot([0, 0], [.27, .33], [PACE, PACE], [.27, .33], color="#2b6cb0", lw=1)
ax.text(PACE / 2, .34, "1 pace", ha="center", va="bottom", fontsize=7, color="#2b6cb0")
ax.text(-.25, 1.15, "— punch reach 0.8 m   ··· kick reach 1.0 m", fontsize=7, color="#555")
fig.savefig(sys.argv[1] if len(sys.argv) > 1 else f"docs/combat/frames/t{t}.png")
