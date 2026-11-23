# -*- coding: utf-8 -*-
"""لوحة مراجعة للبندين (الردم + العزل): خريطة اللبشة بمناطق وش اللبشة + القواعد + الأعمدة + الأكوار/الخزان/البادئ."""
import sys, os, math
import ezdxf, raft_footings as RF, concrete_columns_takeoff as cc, columns_takeoff as ct, column_exact as CX
import backfill_takeoff as BF, insulation_takeoff as INS

OUT=os.path.join(os.path.dirname(__file__), "..", "output")

def arabic(s):
    try:
        import arabic_reshaper; from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(s))
    except Exception: return s

def main():
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon as PPoly, Rectangle
    doc=ezdxf.readfile(cc.DEFAULT_DXF); msp=doc.modelspace()
    RX,RY=CX.PLAN_ORIGIN['RAFT']; CXo,CYo=CX.PLAN_ORIGIN['COL']
    # raft outline (biggest R.C. footing poly) + thickened footings
    def A(pts):
        a=0
        for i in range(len(pts)): x1,y1=pts[i]; x2,y2=pts[(i+1)%len(pts)]; a+=x1*y2-x2*y1
        return abs(a)/2/1e6
    big=None
    for e in msp.query('LWPOLYLINE'):
        if e.dxf.layer!='R.C. footing': continue
        try: pts=[(p[0]-RX,p[1]-RY) for p in e.get_points('xy')]
        except: continue
        if len(pts)>=4 and -15000<min(p[0] for p in pts)<60000:
            if big is None or A(pts)>A(big): big=pts
    fts=RF.assign_thickness(RF.collect_footings(msp), RF.collect_thickness_bubbles(msp))
    COL={-7.35:'#1b5e20',-7.55:'#388e3c',-7.75:'#66bb6a',-7.85:'#9ccc65',-8.15:'#c5e1a5'}
    fig,ax=plt.subplots(figsize=(20,16))
    if big: ax.add_patch(PPoly([(p[0]/1000,p[1]/1000) for p in big],closed=True,fc='#e3f2fd',ec='#0d47a1',lw=2,label='raft -8.45'))
    for f in fts:
        pts=[((x-RX)/1000,(y-RY)/1000) for x,y in f['pts']]
        ax.add_patch(PPoly(pts,closed=True,fc=COL.get(round(f['top'],2),'#ddd'),ec='#555',lw=1,alpha=0.85))
        cx=sum(p[0] for p in pts)/len(pts); cy=sum(p[1] for p in pts)/len(pts)
        ax.annotate(f"{f['top']}",(cx,cy),fontsize=7,ha='center',color='#111')
    # columns
    plan,_=ct.collect(msp)
    for sn,m,x,y in cc.columns_list(plan):
        xx,yy=(x-CXo)/1000,(y-CYo)/1000
        if m.startswith('CORE'):
            ax.add_patch(Rectangle((xx-1.8,yy-1.8),3.6,3.6,fc='#e2efda',ec='#2e7d32',lw=1.5,alpha=0.7))
            ax.annotate(m,(xx,yy),fontsize=8,ha='center',color='#1b5e20',weight='bold')
        else: ax.plot(xx,yy,'s',ms=4,color='#c62828')
    ax.set_aspect('equal'); ax.grid(True,ls=':',alpha=0.4)
    ax.autoscale_view()
    # totals
    raft,zones=BF.raft_zones(msp)
    ax.set_title(arabic("لوحة مراجعة أساسات البدروم السفلي — مناطق وش اللبشة (منسوب الردم ‑7.35)"),fontsize=15,weight='bold')
    ax.set_xlabel("X (m) [إطار 01/A]"); ax.set_ylabel("Y (m)")
    txt=arabic(f"اللبشة {raft:.0f}م² | مناطق الوش: ")+ " ".join(f"{k}:{round(v)}" for k,v in zones.items())
    ax.annotate(txt,(0.5,-0.06),xycoords='axes fraction',ha='center',fontsize=10)
    os.makedirs(OUT,exist_ok=True); p=os.path.join(OUT,"لوحة مراجعة الأساسات - الردم والعزل.png")
    fig.tight_layout(); fig.savefig(p,dpi=120,facecolor='white'); plt.close(fig); print("SAVED:",p)

if __name__=="__main__":
    sys.stdout.reconfigure(encoding="utf-8",errors="replace"); main()
