"""Low-poly powerup models for Repo Defender. Each model: points (x,y,z; y up,
-z toward the player, fits radius ~1) and faces (i, j, k, material). Materials
map to a base colour; the renderer flat-shades each face into 3 tones.
Triangles only, so screen.triangle can draw them; draw back to front,
with pepperoni and the coffee surface drawn after the faces they sit on."""
import math
MATERIALS = {
    "cup": (235, 225, 210), "sleeve": (200, 140, 90), "coffee": (110, 65, 35),
    "steam": (220, 230, 240), "crust": (190, 110, 50), "cheese": (255, 200, 80),
    "pepperoni": (210, 50, 50),
}
class Model:
    def __init__(s): s.points=[]; s.faces=[]
    def p(s,*xyz): s.points.append(xyz); return len(s.points)-1
    def ring(s,cx,y,cz,r,n,start=0.0,ry=None):
        return [s.p(cx+r*math.cos(start+2*math.pi*i/n),y,cz+r*math.sin(start+2*math.pi*i/n)) for i in range(n)]
    def quad(s,a,b,c,d,m): s.faces+= [(a,b,c,m),(a,c,d,m)]
    def band(s,A,B,m,closed=True):
        n=len(A)
        for i in range(n if closed else n-1):
            j=(i+1)%n; s.quad(A[i],A[j],B[j],B[i],m)
    def fan(s,c,R,m):
        for i in range(len(R)): s.faces.append((c,R[i],R[(i+1)%len(R)],m))

def coffee(frame=0):
    m=Model(); N=8
    bot=m.ring(0,-0.75,0,0.42,N); s0=m.ring(0,-0.25,0,0.5,N); s1=m.ring(0,0.15,0,0.56,N); top=m.ring(0,0.55,0,0.62,N)
    m.fan(m.p(0,-0.75,0),bot[::-1],"cup")
    m.band(bot,s0,"cup"); m.band(s0,s1,"sleeve"); m.band(s1,top,"cup")
    # coffee surface just below the rim
    surf=m.ring(0,0.48,0,0.58,N); m.fan(m.p(0,0.48,0),surf,"coffee")
    # handle: square loop of boxes on the +x side
    hp=[(0.55,0.3),(0.9,0.3),(0.95,-0.15),(0.55,-0.3)]
    prev=None
    for x,y in hp:
        q=[m.p(x,y+0.07,-0.07),m.p(x,y+0.07,0.07),m.p(x,y-0.07,0.07),m.p(x,y-0.07,-0.07)]
        if prev: m.band(prev,q,"cup")
        prev=q
    # 3 steam wisps: thin zig-zag ribbons (2 tris each segment), sway with frame
    for k,x in enumerate((-0.25,0.05,0.3)):
        pts=[]
        for j in range(4):
            sw=0.1*math.sin(j*1.8+k+frame*1.2)
            pts.append((x+sw,0.65+0.22*j,-0.1))
        for j in range(3):
            (x0,y0,z0),(x1,y1,z1)=pts[j],pts[j+1]; w=0.045*(1-j/4)
            a=m.p(x0-w,y0,z0);b=m.p(x0+w,y0,z0);c=m.p(x1+w,y1,z1);d=m.p(x1-w,y1,z1)
            m.quad(a,b,c,d,"steam")
    return m

def pizza(frame=0):
    m=Model(); T=0.18  # thickness
    # wedge: tip toward the player-left, crust arc at the back
    arc=[(-0.75+1.5*i/4, 0.75-0.12*abs(i-2)) for i in range(5)]   # (x, z) back edge, slight curve
    tip=(0,-0.9)
    tt=m.p(tip[0],T/2,tip[1]); tb=m.p(tip[0],-T/2,tip[1])
    top=[m.p(x,T/2,z) for x,z in arc]; bot=[m.p(x,-T/2,z) for x,z in arc]
    for i in range(4):
        m.faces.append((tt,top[i+1],top[i],"cheese")); m.faces.append((tb,bot[i],bot[i+1],"crust"))
    m.quad(tt,top[0],bot[0],tb,"crust"); m.quad(tt,tb,bot[4],top[4],"crust")
    # crust lip: raised box along the arc
    lipF=[m.p(x,T/2+0.15,z-0.12) for x,z in arc]; lipB=[m.p(x,T/2+0.15,z+0.05) for x,z in arc]
    lipBb=[m.p(x,-T/2,z+0.05) for x,z in arc]
    for i in range(4):
        m.quad(top[i],top[i+1],lipF[i+1],lipF[i],"crust"); m.quad(lipF[i],lipF[i+1],lipB[i+1],lipB[i],"crust")
        m.quad(lipB[i],lipB[i+1],lipBb[i+1],lipBb[i],"crust")
    # 3 pepperoni hexagons sitting on the cheese
    for cx,cz in ((-0.28,0.35),(0.3,0.38),(0.0,-0.15)):
        R=m.ring(cx,T/2+0.03,cz,0.15,6); m.fan(m.p(cx,T/2+0.03,cz),R[::-1],"pepperoni")
    # cheese drip off the right edge
    a=m.p(-0.36,T/2+0.01,-0.1); b=m.p(-0.5,T/2+0.01,0.25); c=m.p(-0.5,-T/2-0.25,0.05)
    m.faces.append((a,b,c,"cheese"))
    return m
MODELS={"coffee":coffee,"pizza":pizza}
