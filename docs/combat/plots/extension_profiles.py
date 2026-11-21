"""Final punch energy vs time to full arm extension for three motion profiles."""
import numpy as np, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
m, d, x0 = 3.75, 0.6, 0.01   # arm mass kg, extension m, exp-profile start offset m
E = np.linspace(10, 400, 400)
vf = np.sqrt(2 * E / m)
fig, ax = plt.subplots(figsize=(6, 4), dpi=150)
ax.axhspan(0.13, 0.48, color="#999", alpha=.15, lw=0)
ax.text(395, .47, "measured punch times", ha="right", va="top", fontsize=7, color="#666")
ax.axvspan(96, 228, color="#999", alpha=.15, lw=0)  # IQR of 16 lab punch measurements
ax.text(162, .69, "measured punch\nenergies (IQR)", ha="center", va="top", fontsize=7, color="#666")
for k, lab, c in [(1, "x ~ t  (constant speed)", "#2f855a"),
                  (1.5, "x ~ t^1.5  (constant power)", "#2b6cb0"),
                  (np.log(d / x0), "x ~ e^t  (v ∝ x, start 1 cm)", "#c05621")]:
    ax.plot(E, k * d / vf, color=c, label=lab)
ax.axvline(300, color="#555", ls=":", lw=1); ax.text(302, .02, "cap", fontsize=7, color="#555")
ax.set_xlabel("final energy (J)"); ax.set_ylabel("time to extend 0.6 m (s)")
ax.set_ylim(0, 0.7); ax.legend(fontsize=7, frameon=False, loc="center right")
for s in ("top", "right"): ax.spines[s].set_visible(False)
fig.tight_layout(); fig.savefig("docs/combat/plots/extension_profiles.png")
