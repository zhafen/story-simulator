"""Final kick energy vs time for the foot to travel to the target, three profiles."""
import numpy as np, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
m, d, x0 = 12.0, 1.0, 0.01   # whole-leg mass kg, foot travel m, exp-profile start offset m
E = np.linspace(10, 600, 400)
vf = np.sqrt(2 * E / m)
fig, ax = plt.subplots(figsize=(6, 4), dpi=150)
ax.axhspan(0.26, 0.35, color="#999", alpha=.15, lw=0)   # roundhouse foot-off -> contact
ax.text(595, .345, "measured kick times", ha="right", va="top", fontsize=7, color="#666")
ax.axvspan(35, 339, color="#999", alpha=.15, lw=0)      # IQR of 14 kick measurements
ax.text(187, 1.19, "measured kick\nenergies (IQR)", ha="center", va="top", fontsize=7, color="#666")
for k, lab, c in [(1, "x ~ t  (constant speed)", "#2f855a"),
                  (1.5, "x ~ t^1.5  (constant power)", "#2b6cb0"),
                  (np.log(d / x0), "x ~ e^t  (v ∝ x, start 1 cm)", "#c05621")]:
    ax.plot(E, k * d / vf, color=c, label=lab)
ax.axvline(300, color="#555", ls=":", lw=1); ax.text(302, .02, "cap", fontsize=7, color="#555")
ax.set_xlabel("final energy (J)"); ax.set_ylabel("time for foot to travel 1.0 m (s)")
ax.set_ylim(0, 1.2); ax.legend(fontsize=7, frameon=False, loc="upper right", bbox_to_anchor=(1, .93))
ax.set_title("Kick: whole leg 12 kg", fontsize=9)
for s in ("top", "right"): ax.spines[s].set_visible(False)
fig.tight_layout(); fig.savefig("docs/combat/plots/extension_profiles_kick.png")
