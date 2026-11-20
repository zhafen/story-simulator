import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
t=0.4
# history (t, x, y) from encounter log
P=[(0,0,0),(0.1,0.283,0),(0.2,0.566,0),(0.3,0.849,0),(0.4,1.131,0)]
D=[(0,2,0),(0.1,2,0),(0.2,2,0),(0.3,2,0),(0.4,2,0.155)]
pv=(2.83,0); dv=(0,1.55); r=0.225
fig,ax=plt.subplots(figsize=(8,4.6),dpi=150)
for hist,col,name,v in [(P,"#2b6cb0","Player",pv),(D,"#c05621","TDTFB",dv)]:
    xs=[h[1] for h in hist]; ys=[h[2] for h in hist]
    ax.plot(xs,ys,":",color=col,lw=1)
    for h in hist[:-1]: ax.plot(h[1],h[2],"o",color=col,ms=3,alpha=.5)
    x,y=xs[-1],ys[-1]
    ax.add_patch(Circle((x,y),r,color=col,alpha=.25)); ax.add_patch(Circle((x,y),r,fill=False,color=col,lw=1.5))
    ax.annotate("",xy=(x+v[0]*.2,y+v[1]*.2),xytext=(x,y),arrowprops=dict(arrowstyle="->",color=col,lw=2))
    ax.text(x,y-r-0.09,f"{name}\n{(v[0]**2+v[1]**2)**.5:.2f} m/s",ha="center",va="top",fontsize=8,color=col)
for h in P[:-1]: ax.text(h[1],h[2]+0.05,f"{h[0]:.1f}s",fontsize=6,ha="center",color="#2b6cb0",alpha=.7)
ax.text(2.0,0.05-0.25,"",fontsize=6)
ax.set_aspect("equal"); ax.set_xlim(-0.4,2.7); ax.set_ylim(-0.75,0.85)
ax.set_xlabel("x (m) — player's initial charge line"); ax.set_ylabel("y (m)")
ax.grid(alpha=.3); ax.set_title(f"Top-down, t = {t:.1f} s (player's turn) — arrows show 0.2 s of travel; circles = 0.45 m shoulder width",fontsize=8)
fig.tight_layout(); fig.savefig("/home/user/story-simulator/docs/combat/frames/t0.4.png")
