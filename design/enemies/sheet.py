import math
from PIL import Image,ImageDraw,ImageFont
from render import *
F="/usr/share/fonts/truetype/dejavu/DejaVuSans"
def font(s,b=False):
    try: return ImageFont.truetype(F+("-Bold" if b else "")+".ttf",s)
    except: return ImageFont.load_default()
def ingame(img,c,azim,dist,yaw=0.5):
    yaw=0.35 if c['key']=='overmind' else yaw
    m=c["fn"](); col=hx(c["hex"]); a=math.radians(azim)
    x,z=dist*math.sin(a),dist*math.cos(a)
    sx=W/2+FOCAL*x/z; sy=HOR+(EYE-c["height"])*FOCAL/z; r=c["size"]*FOCAL/z
    pts,eyes=proj(m,yaw,0.15,sx,sy,r)
    d=ImageDraw.Draw(img)
    halo=tuple(int(v*0.35) for v in col)
    for e1,e2 in m.e: d.line([pts[e1],pts[e2]],fill=halo,width=3)  # cheap glow: dim 3px under
    for e1,e2 in m.e: d.line([pts[e1],pts[e2]],fill=col,width=1)
    for e in eyes: d.point((round(e[0]),round(e[1])),fill=(255,255,255))
    return r
# per-creature big cards
CW,CH=560,520
cards=[]
for c in CREATURES:
    big=bg().resize((CW,int(CW*240/320)),Image.NEAREST).crop((0,0,CW,CH-120)) if False else Image.new("RGB",(CW,CH),(8,10,22))
    # backdrop: real background scaled
    b=bg().resize((CW,420),Image.NEAREST); big.paste(b,(0,0))
    big=draw(big,c["fn"](),hx(c["hex"]),CW//2,200 if c["key"]=="overmind" else 215,140 if c["key"]=="overmind" else 120,yaw=0.35 if c["key"]=="overmind" else 0.55,width=2)
    d=ImageDraw.Draw(big)
    d.rectangle([0,420,CW,CH],fill=(10,12,24))
    d.text((18,430),c["name"],font=font(28,True),fill=hx(c["hex"]))
    d.text((CW-18,436),c["hex"],font=font(18),fill=(200,230,255),anchor="ra")
    d.text((18,466),"replaces: "+c["replaces"],font=font(15),fill=(150,170,200))
    d.text((18,490),c["idea"],font=font(13),fill=(200,230,255))
    big.save(f"{c['key']}_large.png"); cards.append(big)
# in-game scene: all five at plausible distances, 1:1 then x3 nearest
scene=bg()
place=[("skitter",-14,7),("hoardshell",8,12),("mirage",-4,16),("overmind",15,22),("glitchwyrm",-20,26)]
byk={c["key"]:c for c in CREATURES}
for k,az,dist in sorted(place,key=lambda p:-p[2]): ingame(scene,byk[k],az,dist)
scene.save("ingame_1x.png"); scene3=scene.resize((960,720),Image.NEAREST); scene3.save("ingame_x3.png")
# close/far strip per creature at 1x (shown x2)
strip=bg()
for i,c in enumerate(CREATURES):
    ingame(strip,c,-20+i*10,6.5); 
near=strip.resize((640,480),Image.NEAREST)
# assemble sheet
pad=24; cols=3
Wsh=cols*CW+(cols+1)*pad; rows=2
top=90
sheet=Image.new("RGB",(Wsh,top+rows*(CH+pad)+760+pad),(4,6,14))
d=ImageDraw.Draw(sheet)
d.text((pad,24),"Repo Defender: neon wireframe creature proposals",font=font(36,True),fill=(230,240,255))
d.text((pad,66),"styled on the in-game floor grid and skyline: 1px neon line + dim 3px halo, perspective-projected 3D wireframes",font=font(16),fill=(140,160,190))
for i,cd in enumerate(cards):
    sheet.paste(cd,(pad+(i%cols)*(CW+pad),top+(i//cols)*(CH+pad)))
# 6th slot: legend
lx,ly=pad+2*(CW+pad),top+CH+pad
d.rectangle([lx,ly,lx+CW,ly+CH],fill=(10,12,24))
for j,t in enumerate(["How to read this sheet","","Cards: each creature large, over the real","background (scaled up).","","Below left: all five at true in-game size","(320x240 screen, shown x3, nearest-neighbour).","","Below right: each one up close (6.5 units),","shown x2: the biggest they get before reaching you.","","Eyes are white-hot on every creature, replacing","the shared red eyes, so they still read as enemies."]):
    d.text((lx+18,ly+18+j*28),t,font=font(20 if j==0 else 16,j==0),fill=(200,230,255))
y=top+rows*(CH+pad)
sheet.paste(scene3,(pad,y)); sheet.paste(near,(pad+960+pad,y))
d.text((pad+960+pad,y+490),"up close, x2 (L→R: Skitter, Hoardshell, Mirage, Overmind, Glitchwyrm)",font=font(14),fill=(150,170,200))
sheet=sheet.crop((0,0,Wsh,y+720+pad))
sheet.save("proposal_sheet.png"); print(sheet.size)
