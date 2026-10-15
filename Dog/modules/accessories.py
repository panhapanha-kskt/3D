"""UV-consistent draped scarf and layered solid relief lotus brooch."""
import math, random
from mathutils import Vector
from .geometry import mesh_object,path,ellipsoid

def scarf(cfg,cols,mats,root):
    verts=[];faces=[];uv=[];nu=144;nv=24
    # Noncircular cloth wrap with relaxed horizontal fold channels.
    for i in range(nu+1):
        a=2*math.pi*i/nu
        for j in range(nv+1):
            v=j/nv
            rad=.07*math.sin(v*math.pi)+.015*math.sin(v*math.pi*5+a*2)
            x=(.73+rad)*math.cos(a)
            y=(.69+rad)*math.sin(a)-.035
            z=1.83+(v-.5)*.29+.045*math.cos(a+.5)+.012*math.sin(a*4+v*4)
            verts.append((x,y,z));uv.append((i/nu*4.1,v*.30))
    for i in range(nu):
        for j in range(nv):
            a=i*(nv+1)+j;faces.append((a,a+nv+1,a+nv+2,a+1))
    wrap=mesh_object('Scarf | naturally folded neck wrap',verts,faces,cols['SCARF'],mats['scarf'],root,uv)
    sol=wrap.modifiers.new('Woven cloth thickness','SOLIDIFY');sol.thickness=.022
    sub=wrap.modifiers.new('Soft fabric subdivision','SUBSURF');sub.levels=1
    # Width and y-depth vary down the hanging cloth; UVs use the same physical scale.
    verts=[];faces=[];uv=[];nu=20;nv=70
    for i in range(nv+1):
        t=i/nv
        cx=.42+.13*t;cy=-.75-.08*math.sin(t*math.pi*.65);z=1.98-1.0*t
        for j in range(nu+1):
            u=j/nu
            x=cx+(u-.5)*cfg.scarf_width
            y=cy+.022*math.sin(u*math.pi*3+t*5)+.015*math.cos(t*10)
            zz=z+.025*math.sin(u*math.pi*2+t*2)
            verts.append((x,y,zz));uv.append((u*cfg.scarf_width,t*1.15))
    for i in range(nv):
        for j in range(nu):
            a=i*(nu+1)+j;faces.append((a,a+1,a+nu+2,a+nu+1))
    end=mesh_object('Scarf | hanging woven panel',verts,faces,cols['SCARF'],mats['scarf'],root,uv)
    sol=end.modifiers.new('Cloth panel thickness','SOLIDIFY');sol.thickness=.018
    sub=end.modifiers.new('Drape smoothing','SUBSURF');sub.levels=1
    rng=random.Random(cfg.seed)
    for i in range(36):
        x=.55+(i/35-.5)*cfg.scarf_width
        col=mats['fringe_red'] if i%7<4 else mats['fringe_cream']
        length=rng.uniform(.15,.23)
        for strand in range(3):
            dx=(strand-1)*.0026
            pts=[(x+dx,-.745,1.02),(x+dx+.012,-.77,.96),(x+dx-.01,-.76,1.02-length)]
            path('Scarf | twisted tassel',pts,.0028,cols['SCARF'],col,root,radii=[1,1,.3])
    lotus(cols,mats,root)
    return wrap,end

def lotus(cols,mats,root):
    # Each pointed petal is a closed convex relief with a raised central vein.
    base=Vector((.475,-.866,1.64))
    for layer,(size,spread,offset) in enumerate([(.255,.72,0),(.205,.6,-.018),(.155,.5,-.035)]):
        for k in [-1,0,1]:
            angle=k*spread
            axis=Vector((math.sin(angle),0,math.cos(angle)))
            side=Vector((math.cos(angle),0,-math.sin(angle)))
            origin=base+Vector((0,offset,.012*layer))
            verts=[];faces=[];nu=24;nv=18
            for i in range(nv+1):
                t=i/nv;width=size*.31*math.sin(math.pi*t)**.8
                for j in range(nu):
                    a=2*math.pi*j/nu
                    p=origin+axis*size*t+side*width*math.cos(a)+Vector((0,-.018*math.sin(math.pi*t)*math.sin(a),0))
                    verts.append(p)
            for i in range(nv):
                for j in range(nu):
                    a=i*nu+j;b=i*nu+(j+1)%nu;faces.append((a,b,b+nu,a+nu))
            o=mesh_object('Lotus | layered solid petal',verts,faces,cols['LOTUS_ORNAMENT'],mats['gold'],root)
            pts=[origin+axis*size*t+Vector((0,-.021,0)) for t in [.08,.45,.88]]
            path('Lotus | petal vein',pts,.004,cols['LOTUS_ORNAMENT'],mats['gold_dark'],root)
    for s in [-1,1]:
        verts=[(.475,-.90,1.65),(.475+s*.08,-.91,1.71),(.475+s*.17,-.90,1.69),(.475+s*.12,-.91,1.62)]
        leaf=mesh_object('Lotus | solid lower leaf',verts,[(0,1,2,3)],cols['LOTUS_ORNAMENT'],mats['gold'],root)
        sol=leaf.modifiers.new('Leaf relief thickness','SOLIDIFY');sol.thickness=.018
        bevel=leaf.modifiers.new('Soft gold leaf edge','BEVEL');bevel.width=.008;bevel.segments=3
    ellipsoid('Lotus | heart',(.475,-.91,1.67),(.035,.016,.045),cols['LOTUS_ORNAMENT'],mats['gold'],root)
