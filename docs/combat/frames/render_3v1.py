"""Top-down frame for the player vs 3xTDTFB encounter. Edit STATE per turn."""
import sys, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
t, STORE, CAP, P, DT = 0.04, 0, 3000, 0, 0.02  # P into movement, store not filling
STATE = [("Player", 0.04, 0, 2.53, 0, "#2b6cb0"), ("1", 3.0, 0, 0, 0, "#c05621"),
         ("2", 2.30, 1.93, 0, 0, "#c05621"), ("3", 2.30, -1.93, 0, 0, "#c05621")]
fig = plt.figure(figsize=(6.6, 4.4), dpi=150)
bx = fig.add_axes([0.08, 0.2, 0.04, 0.6]); ax = fig.add_axes([0.16, 0.08, 0.82, 0.84])
bx.bar(0, CAP, color="none", edgecolor="#2b6cb0"); bx.bar(0, min(CAP, STORE + P * DT), color="#2b6cb0", alpha=.2)
bx.bar(0, STORE, color="#2b6cb0", alpha=.7); bx.set_xlim(-.5, .5); bx.set_ylim(0, CAP)
bx.set_xticks([]); bx.set_yticks([0, STORE, CAP]); bx.tick_params(labelsize=7)
bx.set_title("Player\nstore (J)", fontsize=7)
for s in ("top", "right"): bx.spines[s].set_visible(False)
for name, x, y, vx, vy, c in STATE:
    ax.add_patch(Circle((x, y), .225, color=c, alpha=.35))
    if vx or vy: ax.annotate("", xy=(x + vx * .2, y + vy * .2), xytext=(x, y), arrowprops=dict(arrowstyle="->", color=c, lw=2))
    ax.text(x, y - .3, name, ha="center", va="top", fontsize=8, color=c)
ax.set_aspect("equal"); ax.set_xlim(-1, 4); ax.set_ylim(-2.7, 2.7)
ax.set_xticks([0, 1, 2, 3]); ax.set_yticks([-2, 0, 2]); ax.set_xlabel("m"); ax.set_title(f"t = {t} s", fontsize=10)
for s in ("top", "right"): ax.spines[s].set_visible(False)
fig.savefig(sys.argv[1] if len(sys.argv) > 1 else f"docs/combat/frames/3v1_t{t}.png")
