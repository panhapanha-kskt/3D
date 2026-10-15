"""Reference anatomy: unified body, sculpted face, layered eyes and shaped ears."""
import math, random
import bpy
from mathutils import Vector
from .geometry import ellipsoid, blend_parts, mesh_object, tube, path, empty

def smoothstep(a,b,x):
    t=max(0.,min(1.,(x-a)/(b-a)))
    return t*t*(3-2*t)

def face_color(p,cfg):
    x,y,z=p
    front=1-smoothstep(-.45,-.12,y)
    patches=[]
    for s in [-1,1]:
        patches.append(math.exp(-(((x-s*cfg.eye_spacing)/.40)**2+((z-.13)/.46)**2)*1.1))
    mask=max(patches)*front
    mask=max(mask, math.exp(-((x/.72)**4+((z+.37)/.38)**4))*front*.93)
    mask=smoothstep(.10,.47,mask)
    ivory=cfg.cream_color;dark=cfg.mask_color
    return tuple(ivory[i]*(1-mask)+dark[i]*mask for i in range(3))

def distance_segment(x,z,a,b):
    vx,vz=b[0]-a[0],b[1]-a[1]
    t=max(0,min(1,((x-a[0])*vx+(z-a[1])*vz)/(vx*vx+vz*vz)))
    return math.hypot(x-a[0]-t*vx,z-a[1]-t*vz)

def head_surface(cfg):
    # Broad folds carved as smooth displacement fields, rather than visible tubes.
    folds=[[(.04,.88),(.14,.76),(.10,.56)],[(.22,.88),(.33,.69),(.29,.51)],
           [(.12,.48),(.35,.59),(.58,.56),(.73,.39)],
           [(.76,.29),(.80,.05),(.78,-.21)]]
    def deform(p):
        x,y,z=p
        if y<0:
            front=smoothstep(0,.45,-y)
            for s in [-1,1]:
                # Recess eye sockets gently into a broad forehead/cheek shell.
                d=((x-s*cfg.eye_spacing)/.34)**2+((z-.15)/.36)**2
                y+=.11*math.exp(-d*2)*front
                for f in folds:
                    dist=min(distance_segment(s*x,z,a,b) for a,b in zip(f,f[1:]))
                    y-=.080*math.exp(-(dist/.060)**2)*front
                    y+=.030*math.exp(-((dist-.070)/.023)**2)*front
            # Sagging cheek/jowl mass smoothly widens the lower head.
            x*=1+.045*math.exp(-((z+.45)/.3)**2)
        return x,y,z
    return deform

def build_head(cfg,cols,mats,root):
    pivot=empty('CTRL | head tilt',cols['HEAD'],root,(0,-.10,2.74))
    head=ellipsoid('Head | continuous sculpt', (0,0,0),(1.0,.73,.96),cols['HEAD'],mats['face'],pivot,head_surface(cfg))
    orbital_parts=[head]
    for side in [-1,1]:
        orbital_parts.append(ellipsoid('Orbital transition',(side*cfg.eye_spacing,-.43,.15),(.445,.31,.46),cols['HEAD'],mats['face'],pivot))
        orbital_parts.append(ellipsoid('Upper expressive brow',(side*.40,-.40,.53),(.38,.25,.22),cols['HEAD'],mats['face'],pivot))
    head=blend_parts('Head | continuous sculpt',orbital_parts,.018,5)
    for side in [-1,1]:
        cutter=ellipsoid('Eye socket cutter',(side*cfg.eye_spacing,-.605,.145),(.345,.345,.345),cols['HEAD'],None,pivot)
        bpy.context.view_layer.objects.active=head
        mod=head.modifiers.new('Anatomical eye socket','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter
        bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(cutter,do_unlink=True)
    # Subdivision increases fold resolution while retaining editability.
    head.data.materials.clear();head.data.materials.append(mats['face'])
    for polygon in head.data.polygons:polygon.material_index=0
    # Volume union already includes one subdivision pass; keep that density.
    attr=head.data.color_attributes.new(name='FurColor',type='FLOAT_COLOR',domain='POINT')
    for v,d in zip(head.data.vertices,attr.data):d.color=(*face_color(v.co,cfg),1)
    # Wide U-shaped smile cavity, with a volumetric lower lip and cream chin.
    cavity=ellipsoid('Mouth | deep smiling cavity',(0,-.60,-.40),(.66,.25,.38),cols['MOUTH'],mats['mouth'],pivot)
    lower=[]
    for i in range(33):
        a=math.pi+i*math.pi/32
        lower.append((.61*math.cos(a),-.72-.08*math.sin(a),-.35+.34*math.sin(a)))
    lip=tube('Lower lip | smiling U',lower,[.065]*33,cols['MOUTH'],mats['mask'],pivot)
    chin=ellipsoid('Chin | soft cream transition',(0,-.37,-.67),(.62,.30,.22),cols['HEAD'],mats['cream'],pivot)
    pads=[]
    for s in [-1,1]:
        def pad_shape(p):
            x,y,z=p
            # Fuller inner lobe with a soft raised outer smile corner.
            z+=.13*(s*x/.4)**2
            return x,y,z
        pads.append(ellipsoid('Muzzle pad '+str(s),(s*.275,-.72,-.23),(cfg.muzzle_width,.31,.27),cols['MUZZLE'],mats['mask'],pivot,pad_shape))
    muzzle=blend_parts('Muzzle | blended bilateral pads',pads,.012,4)
    # Nose is sculpted by tapering the lower half and cutting nostril volumes.
    def nose_shape(p):
        x,y,z=p
        x*=.72+.28*smoothstep(-.11,.10,z)
        y-=.018*math.cos(x*12)
        return x,y,z
    nose=ellipsoid('Nose | leather and carved nostrils',(0,-.997,-.035),(.225,.135,.15),cols['NOSE'],mats['nose'],pivot,nose_shape)
    for s in [-1,1]:
        cutter=ellipsoid('temporary nostril cutter',(s*.108,-1.106,-.012),(.036,.067,.057),cols['NOSE'],None,pivot)
        # Rotation needs local mesh transform because primitive vertices use head space.
        bpy.context.view_layer.objects.active=nose
        mod=nose.modifiers.new('Nostril cavity','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter
        bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(cutter,do_unlink=True)
    path('Nose | philtrum',[(0,-1.123,-.105),(0,-1.052,-.24),(0,-.998,-.31)],.004,cols['NOSE'],mats['lid'],pivot)
    def tongue_shape(p):
        x,y,z=p
        y-=.12*(1-(z/.25)**2)
        y+=.012*math.exp(-(x/.025)**2)*max(0,-y/.07)
        x*=1+.13*(-z/.25)
        return x,y,z
    tongue=ellipsoid('Tongue | soft rounded curved tip',(-.045,-.85,-.53),(.185,.055,.235),cols['TONGUE'],mats['tongue'],pivot,tongue_shape)
    eyes=[]
    for s in [-1,1]:eyes.append(build_eye(s,cfg,cols,mats,pivot))
    ears=[build_ear(s,cfg,cols,mats,pivot) for s in [-1,1]]
    pivot.scale=(cfg.head_scale,)*3;pivot.rotation_euler[1]=math.radians(cfg.head_tilt_degrees)
    return pivot,head,muzzle,chin,ears,lip

def build_eye(side,cfg,cols,mats,parent):
    x=side*cfg.eye_spacing;z=.145+(0.008 if side<0 else -.008);cy=-.605;r=cfg.eye_radius
    gaze=empty('CTRL | eye gaze '+str(side),cols['EYES'],parent,(x,cy,z))
    eye=ellipsoid('Eyeball '+str(side),(0,0,0),(r,r,r),cols['EYES'],mats['sclera'],gaze)
    # Iris radial mesh follows the globe; dark limbal ring, amber radial fibers.
    verts=[];faces=[];colors=[];rng=random.Random(141+side);nr=30;nt=192;outer=r*.69;inner=r*.43
    fibers=[rng.uniform(.45,1.1) for _ in range(nt)]
    for i in range(nr+1):
        t=i/nr;rr=inner+(outer-inner)*t
        for j in range(nt):
            a=j*2*math.pi/nt;xx=rr*math.cos(a);zz=rr*math.sin(a)
            yy=-math.sqrt(max(.001,r*r-rr*rr))-.006+.002*math.sin(a*67+t*13)
            verts.append((xx,yy,zz))
            intensity=fibers[j]*(.64+.36*math.sin(t*math.pi))
            edge=(.15+.85*smoothstep(0,.12,t))*(1-.91*smoothstep(.85,1,t))
            colors.append((.64*intensity*edge,.24*intensity*edge,.024*intensity*edge,1))
    for i in range(nr):
        for j in range(nt):
            a=i*nt+j;b=i*nt+(j+1)%nt;faces.append((a,a+nt,b+nt,b))
    iris=mesh_object('Iris | radial amber fibers '+str(side),verts,faces,cols['EYES'],mats['iris'],gaze)
    attr=iris.data.color_attributes.new(name='IrisColor',type='FLOAT_COLOR',domain='POINT')
    for d,c in zip(attr.data,colors):d.color=c
    ellipsoid('Pupil | recessed '+str(side),(0,-r-.005,0),(inner,.008,inner),cols['EYES'],mats['pupil'],gaze)
    verts=[];faces=[];nr=24;nt=96
    for i in range(nr+1):
        rr=outer*1.09*i/nr
        for j in range(nt):
            a=j*2*math.pi/nt
            verts.append((rr*math.cos(a),-math.sqrt((r+.026)**2-rr*rr)-.004,rr*math.sin(a)))
    for i in range(nr):
        for j in range(nt):
            a=i*nt+j;b=i*nt+(j+1)%nt;faces.append((a,b,b+nt,a+nt))
    cornea=mesh_object('Cornea | optical shell '+str(side),verts,faces,cols['EYES'],mats['cornea'],gaze)
    sol=cornea.modifiers.new('Corneal thickness','SOLIDIFY');sol.thickness=.002
    # Dark fleshy eyelid margin hugs the globe, with a thicker expressive top arc.
    pts=[];radii=[]
    for i in range(97):
        a=i*2*math.pi/96;rx=r*.98;rz=r*1.05
        xx=x+rx*math.cos(a);zz=z+rz*math.sin(a)
        yy=cy-.107-.045*math.sin(a)
        pts.append((xx,yy,zz));radii.append(.014+.009*max(0,math.sin(a)))
    lid=tube('Eyelid | continuous fleshy border '+str(side),pts,radii,cols['EYELIDS'],mats['lid'],parent)
    # A broad anatomical lid surface occludes the edge of the globe and joins
    # the orbit; a thin tube alone produces a mechanical goggle appearance.
    verts=[];faces=[];nt=128;nr=10
    for j in range(nr+1):
        t=j/nr
        for i in range(nt):
            a=i*2*math.pi/nt
            rx=.302+(.432-.302)*t;rz=.293+(.445-.293)*t
            dx=rx*math.cos(a);dz=rz*math.sin(a)
            inner_rr=math.hypot(.302*math.cos(a),.293*math.sin(a))
            yin=cy-math.sqrt(max(.001,r*r-inner_rr*inner_rr))-.010
            yout=-.54-.09*math.sin(a)
            yy=yin*(1-t)+yout*t-.035*math.sin(math.pi*t)
            verts.append((x+dx,yy,z+dz))
    for j in range(nr):
        for i in range(nt):
            a=j*nt+i;b=j*nt+(i+1)%nt;faces.append((a,b,b+nt,a+nt))
    orbit=mesh_object('Orbit | soft sculpted eyelid '+str(side),verts,faces,cols['EYELIDS'],mats['face'],parent)
    ca=orbit.data.color_attributes.new(name='FurColor',type='FLOAT_COLOR',domain='POINT')
    for v,d in zip(orbit.data.vertices,ca.data):
        t=(v.index//nt)/nr
        shade=smoothstep(.5,1,t)
        color=face_color(v.co,cfg)
        d.color=(*(cfg.mask_color[k]*(1-shade)+color[k]*shade for k in range(3)),1)
    solid=orbit.modifiers.new('Eyelid skin thickness','SOLIDIFY');solid.thickness=.008
    # Thin wet line on lower inside edge; direct reflected lights supply catchlights.
    pts=[]
    for i in range(28):
        a=math.pi+i*math.pi/27
        pts.append((x+r*.94*math.cos(a),cy-.141,z+r*1.015*math.sin(a)))
    path('Tear line '+str(side),pts,.006,cols['EYELIDS'],mats['cornea'],parent)
    return eye

def build_ear(side,cfg,cols,mats,parent):
    """Closed tapered folded flap; width and curl are controlled along its length."""
    verts=[];faces=[];nv=40;nu=40
    for i in range(nv+1):
        t=i/nv
        cx=side*(.70+.30*math.sin(t*math.pi*.8));cz=.73-.91*t
        cy=.01-.20*t-.13*math.sin(t*math.pi)
        width=(.13+.23*math.sin(math.pi*t)**.7)*(1-.94*t**7)
        for j in range(nu):
            a=j*2*math.pi/nu
            x=cx+side*width*math.cos(a)
            z=cz+.08*math.cos(a)*math.sin(t*math.pi)
            y=cy+.065*math.sin(a)+.09*math.cos(a)**2*math.sin(t*math.pi)
            verts.append((x,y,z))
    for i in range(nv):
        for j in range(nu):
            a=i*nu+j;b=i*nu+(j+1)%nu;faces.append((a,b,b+nu,a+nu))
    faces.extend([tuple(range(nu-1,-1,-1)),tuple(nv*nu+j for j in range(nu))])
    o=mesh_object('Ear | folded triangular '+str(side),verts,faces,cols['EARS'],mats['ears'],parent)
    sub=o.modifiers.new('Soft flap subdivision','SUBSURF');sub.levels=1
    return o

def build_body(cfg,cols,mats,root):
    parts=[ellipsoid('Body base',(0,.20,1.18),(cfg.body_width,.65,1.03),cols['BODY'],mats['cream'],root),
           ellipsoid('Chest base',(0,-.03,1.77),(.69,.55,.62),cols['BODY'],mats['cream'],root)]
    for side in [-1,1]:
        parts.append(ellipsoid('Haunch base',(side*.69,.29,.58),(.45,.54,.58),cols['BODY'],mats['cream'],root))
        # Legs connect directly to chest with a tapered softly curved loft.
        centers=[];radii=[]
        for i in range(25):
            t=i/24;centers.append((side*(.53+.055*t),-.29-.26*t,1.78-1.5*t));radii.append(.20+.025*math.cos(t*math.pi*2)+.025*t)
        parts.append(tube('Leg base',centers,radii,cols['BODY'],mats['cream'],root))
        for front in [True,False]:
            px=side*(.59 if front else .89);py=-.63 if front else -.06
            parts.append(ellipsoid('Paw base',(px,py,.18),(.29,.36,.19),cols['BODY'],mats['cream'],root))
            for j in range(4):
                tx=px+(j-1.5)*.125
                parts.append(ellipsoid('Toe base',(tx,py-.25,.16),(.09,.16,.125),cols['BODY'],mats['cream'],root))
                claw=tube('Claw | curved '+str(side)+' '+str(front)+' '+str(j),[(tx,py-.34,.14),(tx,py-.40,.13),(tx,py-.43,.08)],[.035,.027,.002],cols['PAWS'],mats['claw'],root,12)
    # Connected base of tail sits inside the rump; outer curl remains clearly visible.
    centers=[];radii=[]
    for i in range(90):
        t=i/89;a=-1.3+t*math.pi*2*cfg.tail_curl
        rad=.30*(1-.53*t)
        centers.append((.82+rad*math.cos(a),.49+.10*t,1.42+rad*math.sin(a)+.28*t))
        radii.append(.13*(1-.78*t**3))
    tail=tube('Tail | continuous tapered curl',centers,radii,cols['TAIL'],mats['cream'],root,24)
    # Body is blended for continuous shoulders, legs, haunches and toes.
    body=blend_parts('Body | unified organic seated anatomy',parts,.018,5)
    return body,tail
