"""Same energy, constant force over a full pace vs over the first foot then coast."""
import numpy as np, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
m, E = 75.0, 300.0
cases = [("constant force over 1 pace (1.0 m)", 1.0, "#2b6cb0"),
         ("constant force over first foot (0.305 m), then coast", 0.3048, "#c05621")]
t = np.linspace(0, 0.8, 801)
fig, axs = plt.subplots(1, 3, figsize=(11, 3.2), dpi=150)
for lab, D, c in cases:
    F = E / D; a = F / m; tD = np.sqrt(2 * D / a); vf = a * tD
    x = np.where(t < tD, .5 * a * t**2, D + vf * (t - tD))
    v = np.where(t < tD, a * t, vf)
    for ax, y in zip(axs, (x, v, .5 * m * v**2)): ax.plot(t, y, color=c, label=lab)
    print(f"{lab}: F={F:.0f} N, a={a:.1f} m/s2, force ends {tD:.3f} s, vf={vf:.2f} m/s, "
          f"reaches 1 m at {(tD if D >= 1 else tD + (1 - D) / vf):.3f} s")
axs[0].axhline(1.0, color="#999", ls=":", lw=1); axs[0].text(.01, 1.02, "1 pace", fontsize=7, color="#666")
for ax, yl in zip(axs, ("position (m)", "speed (m/s)", "kinetic energy (J)")):
    ax.set_xlabel("t (s)"); ax.set_ylabel(yl); ax.set_xlim(0, .8); ax.set_ylim(bottom=0)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
axs[0].legend(fontsize=7, frameon=False, loc="upper left")
fig.suptitle(f"Same energy ({E:.0f} J, 75 kg body from rest)", fontsize=10)
fig.tight_layout(); fig.savefig("docs/combat/plots/force_distance_sensitivity.png")
