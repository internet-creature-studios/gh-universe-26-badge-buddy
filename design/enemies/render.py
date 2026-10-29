import math,random
from PIL import Image,ImageDraw,ImageFilter,ImageFont
from creatures import CREATURES
W,H=320,240; HFOV=50; FOCAL=(W/2)/math.tan(math.radians(HFOV/2)); HOR=92; EYE=1.0
def hx(h): return tuple(int(h[i:i+2],16) for i in (1,3,5))
def bg(yaw=0,scroll=1.3):
    im=Image.new("RGB",(W,H)); d=ImageDraw.Draw(im)
    for i,c in enumerate([(8,10,22),(12,16,36),(18,24,52)]): d.rectangle([0,i*30,W,i*30+31],fill=c)
    d.rectangle([0,HOR,W,H],fill=(6,10,14))
    random.seed(7); az=-70.0
    def sx(a): return W/2+FOCAL*math.tan(math.radians(a-yaw))
    while az<70:
        w=random.uniform(2,5.5); h=random.randint(6,26); l,r=sx(az),sx(az+w)
        d.rectangle([int(l),HOR-h,int(l)+max(1,int(r-l))-1,HOR-1],fill=(22,28,58))
        if r-l>=3:
            for wy in range(HOR-h+3,HOR-2,8): d.point((int(l)+1,wy),fill=(70,90,160))
        az+=w+random.uniform(0.5,3)
    def seg(x0,z0,x1,z1):
        near=1.0
        if z0<near: x0+=(x1-x0)*(near-z0)/(z1-z0); z0=near
        return (W/2+FOCAL*x0/z0,HOR+EYE*FOCAL/z0,W/2+FOCAL*x1/z1,HOR+EYE*FOCAL/z1)
    for k in range(-12,13): d.line(seg(k*1.5,1,k*1.5,60),fill=(18,52,44))
    z=2+(4-scroll)
    while z<40: d.line(seg(-25,z,25,z),fill=(30,90,70)); z*=1.35
    return im
def proj(m,yaw,pitch,cx,cy,r):
    cy_,sy_=math.cos(yaw),math.sin(yaw); cp,sp=math.cos(pitch),math.sin(pitch)
    def p(v):
        x,y,z=v; x,z=x*cy_-z*sy_, x*sy_+z*cy_
        y,z=y*cp-z*sp, y*sp+z*cp
        k=4.0/(4.0+z)  # mild perspective, like the floor
        return (cx+x*r*k, cy-y*r*k)
    return [p(v) for v in m.v],[p(v) for v in m.eyes]
def draw(img,m,col,cx,cy,r,yaw=0.55,pitch=0.18,width=1,glow=True,eye=(255,255,255)):
    pts,eyes=proj(m,yaw,pitch,cx,cy,r)
    if glow:
        g=Image.new("RGB",img.size); gd=ImageDraw.Draw(g)
        for a,b in m.e: gd.line([pts[a],pts[b]],fill=col,width=width*3)
        img.paste(Image.blend(img,Image.eval(Image.composite(g,img,g.convert("L").point(lambda v:255 if v else 0)),lambda v:v),0)) if False else None
        g=g.filter(ImageFilter.GaussianBlur(width*2.5))
        img=Image.fromarray(__import__("numpy").clip(__import__("numpy").asarray(img,dtype=int)+__import__("numpy").asarray(g,dtype=int)*0.9,0,255).astype("uint8"))
    d=ImageDraw.Draw(img)
    for a,b in m.e: d.line([pts[a],pts[b]],fill=col,width=width)
    er=max(2,width*2)
    for e in eyes: d.ellipse([e[0]-er,e[1]-er,e[0]+er,e[1]+er],fill=eye)
    return img
