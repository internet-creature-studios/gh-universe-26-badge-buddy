"""Neon wireframe creature proposals for Repo Defender. Each creature is a
3D vertex/edge list in units where the body fits a radius-1 sphere (the
game's bot 'size' scales it), so it can be ported to MicroPython as-is."""
import math
def ring(cx,cy,cz,rx,ry,n,axis='y',rz=None):
    pts=[]
    for i in range(n):
        a=2*math.pi*i/n
        if axis=='y': pts.append((cx+rx*math.cos(a),cy,cz+(rz or rx)*math.sin(a)))
        elif axis=='z': pts.append((cx+rx*math.cos(a),cy+ry*math.sin(a),cz))
        else: pts.append((cx,cy+ry*math.sin(a),cz+rx*math.cos(a)))
    return pts
class M:
    def __init__(s): s.v=[]; s.e=[]; s.eyes=[]
    def add(s,pts,closed=True):
        b=len(s.v); s.v+=pts; n=len(pts)
        for i in range(n-1 if not closed else n): s.e.append((b+i,b+(i+1)%n))
        return b
    def link(s,a,b,n,step=1):
        for i in range(0,n,step): s.e.append((a+i,b+i))
    def line(s,p,q): s.add([p,q],False)

def skitter():  # replaces bug: fast spider-mite
    m=M()
    # body: two stacked octagon rings + nose
    a=m.add(ring(0,0.05,0,0.7,0,8,rz=0.8)); b=m.add(ring(0,0.45,0,0.45,0,8))
    m.link(a,b,8)
    top=len(m.v); m.v.append((0,0.65,0)); [m.e.append((b+i,top)) for i in range(8)]
    # head wedge forward (-z is toward camera)
    h=m.add([(-0.25,0.15,-0.55),(0.25,0.15,-0.55),(0,0.0,-0.85)])
    m.e+= [(a+6,h),(a+6,h+1),(a+5,h),(a+7,h+1)]
    # mandibles
    m.line((-0.1,0.0,-0.85),(-0.25,-0.15,-1.0)); m.line((0.1,0.0,-0.85),(0.25,-0.15,-1.0))
    # 6 jointed legs
    for k,z in enumerate((-0.35,0,0.35)):
        for sx in (-1,1):
            knee=(sx*0.95,0.45,z*1.4); foot=(sx*1.25,-0.5,z*1.8)
            m.line((sx*0.5,0.1,z),knee); m.line(knee,foot)
    m.eyes=[(-0.12,0.18,-0.6),(0.12,0.18,-0.6)]
    return m

def hoardshell():  # replaces node_modules: slow armoured pillbug/tortoise
    m=M()
    rows=[]
    for j,ph in enumerate((0,0.35,0.7,1.0)):
        rows.append(m.add(ring(0,-0.3+0.75*math.sin(ph*1.35),0,1.0*math.cos(ph*1.2),0,10)))
    for j in range(3): m.link(rows[j],rows[j+1],10)
    cap=len(m.v); m.v.append((0,0.55,0)); [m.e.append((rows[3]+i,cap)) for i in range(10)]
    # plated skirt segments
    sk=m.add(ring(0,-0.45,0,1.05,0,10)); m.link(rows[0],sk,10)
    # head block
    hb=m.add([(-0.3,-0.4,-0.95),(0.3,-0.4,-0.95),(0.3,0.0,-1.0),(-0.3,0.0,-1.0)])
    m.e+=[(hb,rows[0]+7),(hb+1,rows[0]+8),(hb+2,rows[0]+8),(hb+3,rows[0]+7)]
    # stubby legs
    for i in (1,3,6,8):
        x,y,z=m.v[sk+i]; m.line((x,y,z),(x*1.05,-0.8,z*1.05))
    m.eyes=[(-0.15,-0.2,-1.0),(0.15,-0.2,-1.0)]
    return m

def mirage():  # replaces hallucination: swaying jellyfish
    m=M()
    prev=None
    for j,(y,r) in enumerate(((0.0,0.85),(0.3,0.75),(0.55,0.5),(0.7,0.2))):
        c=m.add(ring(0,y,0,r,0,9))
        if prev is not None: m.link(prev,c,9)
        prev=c
    first=0
    # tentacles: wavy polylines
    for i in range(0,9,2):
        a=2*math.pi*i/9; x0,z0=0.8*math.cos(a),0.8*math.sin(a)
        pts=[(x0*(1-0.1*k)+0.15*math.sin(k*1.7+i),-0.25*k,z0*(1-0.1*k)) for k in range(5)]
        m.add(pts,False)
    m.eyes=[(-0.3,0.3,-0.68),(0.22,0.38,-0.62)]  # mismatched
    return m

def overmind():  # replaces rogue agent: simple wireframe dragon, facing the player
    m=M()
    # head: diamond-ish box, snout toward camera (-z)
    h=m.add([(-0.22,0.55,-0.35),(0.22,0.55,-0.35),(0.15,0.75,-0.25),(-0.15,0.75,-0.25)])
    sn=m.add([(-0.1,0.5,-0.7),(0.1,0.5,-0.7)]); m.e+=[(sn,sn+1),(h,sn),(h+1,sn+1),(h+3,sn),(h+2,sn+1)]
    jaw=len(m.v); m.v.append((0,0.32,-0.62)); m.e+=[(h,jaw),(h+1,jaw),(sn,jaw),(sn+1,jaw)]
    # horns
    m.line((-0.15,0.75,-0.25),(-0.4,1.1,0.0)); m.line((0.15,0.75,-0.25),(0.4,1.1,0.0))
    # neck + body: two rings
    n=m.add(ring(0,0.35,-0.1,0.18,0.15,4,'z')); m.e+=[(h,n+2),(h+1,n+0)]
    b=m.add(ring(0,0.1,0.25,0.32,0.26,4,'z')); m.link(n,b,4)
    # tail
    m.add([(0,-0.15,0.5),(0.3,-0.35,0.8),(0.55,-0.45,1.0),(0.75,-0.35,1.1)],False); m.e.append((b+3,len(m.v)-4))
    m.add([(0.75,-0.35,1.1),(0.9,-0.25,1.05),(0.85,-0.5,1.15)])  # tail spade
    # wings: shoulder -> elbow -> tip, with 2 finger struts and membrane edge
    for sx in (-1,1):
        sh=(sx*0.3,0.25,0.15); el=(sx*0.8,0.85,0.3); tip=(sx*1.45,1.0,0.4)
        f1=(sx*1.3,0.2,0.45); f2=(sx*0.85,-0.05,0.4)
        m.line(sh,el); m.line(el,tip); m.line(el,f1); m.line(el,f2)
        m.add([tip,f1,f2,(sx*0.3,0.0,0.3)],False)
    m.eyes=[(-0.13,0.65,-0.42),(0.13,0.65,-0.42)]
    return m

def glitchwyrm():  # optional 5th: spare type for a future enemy
    m=M(); prev=None
    for k in range(7):
        t=k/6; x=0.9*math.sin(t*5); z=-0.9+1.8*t; r=0.38*(1-0.6*t)
        c=m.add(ring(x,0.1+0.15*math.sin(t*9),z,r,r,5,'z'))
        if prev is not None: m.link(prev,c,5)
        prev=c
    m.line((m.v[0][0]-0.2,0.4,-0.95),(m.v[0][0]-0.35,0.75,-1.0)); m.line((m.v[0][0]+0.2,0.4,-0.95),(m.v[0][0]+0.35,0.75,-1.0))
    m.eyes=[(m.v[0][0]-0.15,0.2,-0.95),(m.v[0][0]+0.15,0.2,-0.95)]
    return m

CREATURES=[
 dict(key="skitter",name="Skitter",hex="#F4FF3A",replaces="Bug",fn=skitter,size=0.32,height=0.5,
      idea="a six-legged neon mite that scuttles straight at you; legs flicker as it runs"),
 dict(key="hoardshell",name="Hoardshell",hex="#2EF6FF",replaces="node_modules",fn=hoardshell,size=0.55,height=0.6,
      idea="a domed, plated pillbug; armour rings drop off as you dent it"),
 dict(key="mirage",name="Mirage",hex="#FF3DF2",replaces="Hallucination",fn=mirage,size=0.36,height=0.85,
      idea="a drifting jellyfish with mismatched eyes; swaying tentacles match its weave"),
 dict(key="overmind",name="Overmind",hex="#FF3355",replaces="Rogue agent (boss)",fn=overmind,size=0.85,height=0.95,
      idea="a horned wireframe dragon with wings spread wide; slow boss"),
 dict(key="glitchwyrm",name="Glitchwyrm",hex="#A45CFF",replaces="spare (future type)",fn=glitchwyrm,size=0.5,height=0.7,
      idea="a segmented serpent that S-curves in; a spare if a 5th enemy is added"),
]
