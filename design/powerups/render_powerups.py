import math,sys
sys.path.insert(0,'../enemies')
from PIL import Image,ImageDraw
from render import bg,W,H,FOCAL,HOR,EYE
from powerups import MODELS,MATERIALS
L=(-0.4,0.75,-0.5); n=math.sqrt(sum(v*v for v in L)); L=tuple(v/n for v in L)
def shade(rgb,k): return tuple(int(c*k) for c in rgb)
def flat_faces(m,yaw,pitch=-0.45):
    cy,sy,cp,sp=math.cos(yaw),math.sin(yaw),math.cos(pitch),math.sin(pitch)
    P=[]
    for x,y,z in m.points:
        x,z=x*cy-z*sy,x*sy+z*cy; y,z=y*cp-z*sp,y*sp+z*cp; P.append((x,y,z))
    out=[]
    for a,b,c,mat in m.faces:
        A,B,C=P[a],P[b],P[c]
        u=[B[i]-A[i] for i in range(3)]; v=[C[i]-A[i] for i in range(3)]
        nx,ny,nz=u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]
        ln=math.sqrt(nx*nx+ny*ny+nz*nz) or 1; nx,ny,nz=nx/ln,ny/ln,nz/ln
        if nz>0: nx,ny,nz=-nx,-ny,-nz  # two-sided: face the viewer
        d=nx*L[0]+ny*L[1]+nz*L[2]
        tone=1.0 if d>0.45 else (0.72 if d>0.0 else 0.48)  # 3 tones
        depth=(A[2]+B[2]+C[2])/3-(0.5 if mat in ('pepperoni','coffee') else 0)
        pts=[]
        for X,Y,Z in (A,B,C):
            k=4/(4+Z); pts.append((X*k,-Y*k))
        out.append((depth,pts,shade(MATERIALS[mat],tone)))
    out.sort(key=lambda f:-f[0])
    return out
def draw(img,m,cx,cy,r,yaw,outline=False):
    d=ImageDraw.Draw(img)
    for _,pts,col in flat_faces(m,yaw):
        d.polygon([(cx+x*r,cy+y*r) for x,y in pts],fill=col)
    return img
