"""Player reachable positions after 1 and 2 turns (velocity rule, constant-power releases)."""
import math, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
m, P, T, Er = 75, 6000, 0.02, 120          # kg, W, s per turn, J per turn's release
x0, v0 = 0.068, 2.53                        # player at t = 0.06
u = 2 * Er / m; dv = math.sqrt(u)           # 1.79 m/s per full release
d1 = m / (3 * P) * u ** 1.5                 # shift during one constant-power release (0.024 m)
r1 = d1                                     # turn 1: release over the whole turn
r2 = d1 + dv * T + d1                       # turn 2: first release coasts a turn, second adds d1
c1, c2 = x0 + v0 * T, x0 + v0 * 2 * T
fig, ax = plt.subplots(figsize=(6, 3), dpi=150)
for c, r, lab, a in [(c2, r2, "by t = 0.10 s (2 releases)", .12), (c1, r1, "by t = 0.08 s (1 release)", .3)]:
    ax.add_patch(Circle((c, 0), r, color="#2b6cb0", alpha=a, lw=0))
    ax.add_patch(Circle((c, 0), r, fill=False, color="#2b6cb0", lw=1))
    ax.text(c, r + .008, lab, ha="center", va="bottom", fontsize=7, color="#2b6cb0")
ax.plot(x0, 0, "o", color="#2b6cb0"); ax.text(x0, -.012, "player\nt = 0.06 s", ha="center", va="top", fontsize=7, color="#2b6cb0")
ax.annotate("", xy=(c2, 0), xytext=(x0, 0), arrowprops=dict(arrowstyle="->", color="#999", lw=1))
ax.set_aspect("equal"); ax.set_xlim(.03, .27); ax.set_ylim(-.1, .12)
ax.set_xlabel("x (m)"); ax.set_ylabel("y (m)"); ax.set_title("Where the player's centre can be (zoomed)", fontsize=9)
for s in ("top", "right"): ax.spines[s].set_visible(False)
fig.tight_layout(); fig.savefig("docs/combat/plots/player_reach_3v1.png")
print(c1, r1, c2, r2, dv)
