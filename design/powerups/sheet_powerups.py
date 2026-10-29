import math,sys
sys.path.insert(0,'../enemies')
from PIL import Image,ImageDraw,ImageFont
from render import bg,W,H,FOCAL,HOR,EYE
from render_powerups import draw
from powerups import MODELS,coffee,pizza
F="/usr/share/fonts/truetype/dejavu/DejaVuSans"
f=lambda s,b=False: ImageFont.truetype(F+("-Bold" if b else "")+".ttf",s)
YAW={"coffee":-0.5,"pizza":0.5}
counts={}
for k,fn in MODELS.items():
    m=fn(); counts[k]=(len(m.points),len(m.faces))
    big=bg().resize((640,480),Image.NEAREST); draw(big,m,320,240,150,YAW[k]); big.save(f"{k}_large.png")
    # gif: slow rotation, 36 frames, rendered 2x supersampled
    frames=[]
    for i in range(36):
        im=bg().resize((640,480),Image.NEAREST)
        draw(im,fn(i%6),320,240,150,YAW[k]+2*math.pi*i/36); frames.append(im.convert("P",palette=Image.ADAPTIVE))
    frames[0].save(f"{k}_spin.gif",save_all=True,append_images=frames[1:],duration=90,loop=0)
# in-game: PICKUP_SIZE 0.4, height ~0.75, at several distances
scene=bg()
for k,az,dist in (("coffee",-12,8),("pizza",10,8),("coffee",-4,18),("pizza",5,24),("coffee",14,4.5),("pizza",-18,4.5)):
    a=math.radians(az); x,z=dist*math.sin(a),dist*math.cos(a)
    sx=W/2+FOCAL*x/z; sy=HOR+(EYE-0.75)*FOCAL/z; r=max(4,0.4*FOCAL/z)
    draw(scene,MODELS[k](),sx,sy,r,YAW[k])
scene.save("ingame_1x.png"); scene.resize((960,720),Image.NEAREST).save("ingame_x3.png")
# sheet
S=Image.new("RGB",(1360,1330),(4,6,14)); d=ImageDraw.Draw(S)
d.text((24,20),"Repo Defender: low-poly powerups (flat-shaded triangles, 3 tones)",font=f(30,True),fill=(230,240,255))
for i,(k,label,hexc,note) in enumerate((("coffee","COFFEE","#C88C5A","overdrive: tapered 8-sided cup, sleeve, handle, coffee top, 3 swaying steam wisps"),
                                        ("pizza","PIZZA","#FFC850","+25 health: thick wedge, crust lip, cheese, 3 pepperoni, cheese drip"))):
    x=24+i*668; S.paste(Image.open(f"{k}_large.png"),(x,70))
    d.text((x,560),label,font=f(26,True),fill=tuple(int(hexc[j:j+2],16) for j in (1,3,5)))
    d.text((x+640,566),f"{counts[k][0]} points / {counts[k][1]} triangles",font=f(16),fill=(200,230,255),anchor="ra")
    d.text((x,596),note,font=f(14),fill=(170,190,220))
S.paste(Image.open("ingame_x3.png"),(24,630)) if False else None
g=Image.open("ingame_x3.png").resize((880,660),Image.NEAREST); S.paste(g,(24,640))
d.text((924,650),"in-game size (320x240, x2.75)\nPICKUP_SIZE 0.4 at 4.5, 8, 18, 24 units\n\nsame yaw/pitch would be\npre-flattened like FLAT[] for bots",font=f(16),fill=(200,230,255))
S.save("proposal_sheet.png"); print(counts)
