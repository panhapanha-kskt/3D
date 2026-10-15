"""Surface-sampled, directionally combed native Blender hair curves."""
import bisect, math, random
from array import array
import bpy
from mathutils import Vector
from .geometry import OWNER
from .character import face_color

def groom(surface,name,coll,mat,cfg,region='body',density_scale=1.0):
    """Area-weighted barycentric roots on evaluated mesh, five tapered points each."""
    deps=bpy.context.evaluated_depsgraph_get();ev=surface.evaluated_get(deps);mesh=ev.to_mesh()
    try:
        mesh.calc_loop_triangles()
        tris=[];cumulative=[];total=0
        for t in mesh.loop_triangles:
            if t.area<=1e-10:continue
            a,b,c=(mesh.vertices[i].co.copy() for i in t.vertices)
            total+=t.area;tris.append((a,b,c,t.normal.copy()));cumulative.append(total)
        count=int(total*cfg.fur_density*density_scale)
        rng=random.Random(cfg.seed+sum(ord(c) for c in name));positions=array('f');radii=array('f');colors=array('f');accepted=0
        for i in range(count):
            a,b,c,n=tris[bisect.bisect_left(cumulative,rng.random()*total)]
            u=math.sqrt(rng.random());v=rng.random();p=a*(1-u)+b*(u*(1-v))+c*(u*v)
            if region=='head':
                # Do not fill optical openings or the nose/mouth with cream fibers.
                eye=min(((p.x-s*cfg.eye_spacing)/.355)**2+((p.z-.145)/.37)**2 for s in [-1,1])
                if p.y<-.35 and (eye<1.12 or (abs(p.x)<.69 and -.71<p.z<.02)):continue
                direction=Vector((p.x*.3,-.12,-.85))
                length=cfg.fur_length*(.65 if p.z>.3 else 1.0)
                color=face_color(p,cfg)
            elif region=='muzzle':
                direction=Vector((p.x*.55,-.15,-.5));length=.009;color=cfg.mask_color
            elif region=='ear':
                direction=Vector((0,-.15,-1));length=.023;color=(.024,.014,.010)
            elif region=='tail':
                direction=Vector((-.25,0,.9));length=.060;color=cfg.cream_color
            elif region=='chin':
                direction=Vector((p.x*.3,-.1,-.8));length=.025;color=cfg.cream_color
            else:
                direction=Vector((p.x*.10,-.1,-1));length=cfg.fur_length;color=cfg.cream_color
            # Comb tangent to the actual surface while retaining a small soft lift.
            tangent=direction-n*direction.dot(n)
            if tangent.length<.001:tangent=Vector((.3,0,-.5))
            tangent.normalize();length*=rng.uniform(.68,1.22)
            jitter=Vector((rng.uniform(-1,1),rng.uniform(-1,1),rng.uniform(-1,1)))*.07
            for k in range(5):
                t=k/4
                q=p+n*(.0008+length*(.27*t+.10*math.sin(math.pi*t)))+(tangent+jitter)*length*.84*t
                positions.extend(q);radii.append(.00048*(1-t)**.75+.00004)
                colors.extend((*(max(.0,min(1,c*rng.uniform(.90,1.12))) for c in color),1))
            accepted+=1
        data=bpy.data.hair_curves.new(name+' groom');data.add_curves([5]*accepted)
        data.attributes['position'].data.foreach_set('vector',positions)
        rad=data.attributes.new('radius','FLOAT','POINT');rad.data.foreach_set('value',radii)
        col=data.attributes.new('strand_color','FLOAT_COLOR','POINT');col.data.foreach_set('color',colors)
        data.materials.append(mat);data.surface=surface
        o=bpy.data.objects.new(name,data);coll.objects.link(o);o['generator']=OWNER
        o.parent=surface.parent;o.matrix_world=surface.matrix_world.copy()
        o['strand_count']=accepted;o['groom_region']=region
        print('[fur]',name,accepted,'strands',flush=True)
        return o
    finally:ev.to_mesh_clear()
