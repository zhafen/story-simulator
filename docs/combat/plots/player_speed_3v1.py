"""Player speed vs time, 3v1 encounter (constant power from rest from t=0.02)."""
import numpy as np, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
m, P, E0, t0, t1 = 75, 6000, 0, 0.02, 0.06
t = np.linspace(t0, t1, 200)
v = np.sqrt(2 * (E0 + P * (t - t0)) / m)
fig, ax = plt.subplots(figsize=(5, 3), dpi=150)
ax.plot([0, t0], [0, 0], color="#2b6cb0")
ax.plot(t, v, color="#2b6cb0")
for tt in (0, .02, .04, .06): ax.axvline(tt, color="#ccc", lw=.8, zorder=0)
ax.set_xlabel("t (s)"); ax.set_ylabel("speed (m/s)"); ax.set_xlim(0, t1); ax.set_ylim(0, 3)
ax.set_xticks([0, .02, .04, .06]); ax.set_title("Player speed (turns every 0.02 s)", fontsize=9)
for s in ("top", "right"): ax.spines[s].set_visible(False)
fig.tight_layout(); fig.savefig("docs/combat/plots/player_speed_3v1.png")
