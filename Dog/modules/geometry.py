"""Geometry utilities: explicit parametric meshes, remesh blending, swept sections."""
import math
import bpy
import bmesh
from mathutils import Vector

OWNER = 'pug_reconstruction_v2'

def collection(name, parent=None):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    return c

def link_object(o, coll, parent=None):
    for c in list(o.users_collection):
        c.objects.unlink(o)
    coll.objects.link(o)
    o['generator'] = OWNER
    if parent:
        o.parent = parent
    return o

def mesh_object(name, vertices, faces, coll, mat=None, parent=None, uvs=None):
    m = bpy.data.meshes.new(name + ' mesh')
    m.from_pydata(vertices, [], faces)
    m.update()
    bm = bmesh.new()
    bm.from_mesh(m)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(m)
    bm.free()
    o = bpy.data.objects.new(name, m)
    coll.objects.link(o)
    o['generator'] = OWNER
    if mat:
        m.materials.append(mat)
    if parent:
        o.parent = parent
    for p in m.polygons:
        p.use_smooth = True
    if uvs:
        layer = m.uv_layers.new(name='SurfaceUV')
        for polygon in m.polygons:
            for li in polygon.loop_indices:
                layer.data[li].uv = uvs[m.loops[li].vertex_index]
    return o

def ellipsoid(name, loc, scale, coll, mat=None, parent=None, deform=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=48)
    o = bpy.context.object
    o.name = name
    for v in o.data.vertices:
        p = Vector((v.co.x * scale[0], v.co.y * scale[1], v.co.z * scale[2]))
        if deform:
            p = Vector(deform(p))
        v.co = p + Vector(loc)
    o.data.update()
    for p in o.data.polygons:
        p.use_smooth = True
    if mat:
        o.data.materials.append(mat)
    return link_object(o, coll, parent)

def active(o):
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True)
    bpy.context.view_layer.objects.active = o

def blend_parts(name, parts, voxel=.025, smooth=5):
    """Voxel-union connected volumes, then relax without erasing broad anatomy."""
    bpy.ops.object.select_all(action='DESELECT')
    for o in parts:
        o.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    o = bpy.context.object
    o.name = name
    r = o.modifiers.new('Organic volume union', 'REMESH')
    r.mode = 'VOXEL'
    r.voxel_size = voxel
    r.use_smooth_shade = True
    bpy.ops.object.modifier_apply(modifier=r.name)
    s = o.modifiers.new('Surface relaxation', 'SMOOTH')
    s.factor = .65
    s.iterations = smooth
    bpy.ops.object.modifier_apply(modifier=s.name)
    sub = o.modifiers.new('Sculpt surface subdivision', 'SUBSURF')
    sub.levels = 1
    sub.render_levels = 1
    bpy.ops.object.modifier_apply(modifier=sub.name)
    for f in o.data.polygons:
        f.use_smooth = True
    o.data.update()
    return o

def path(name, points, radius, coll, mat, parent=None, cyclic=False, radii=None):
    c = bpy.data.curves.new(name, 'CURVE')
    c.dimensions = '3D'
    c.resolution_u = 16
    c.bevel_depth = radius
    c.bevel_resolution = 3
    s = c.splines.new('BEZIER')
    s.bezier_points.add(len(points) - 1)
    for i, (b, p) in enumerate(zip(s.bezier_points, points)):
        b.co = p
        b.handle_left_type = 'AUTO'
        b.handle_right_type = 'AUTO'
        if radii:
            b.radius = radii[i]
    s.use_cyclic_u = cyclic
    o = bpy.data.objects.new(name, c)
    coll.objects.link(o)
    c.materials.append(mat)
    o['generator'] = OWNER
    if parent:
        o.parent = parent
    return o

def tube(name, centers, radii, coll, mat, parent=None, sides=20):
    """Continuous capped polygon tube with varying circular section."""
    verts, faces, uvs = [], [], []
    centers = [Vector(p) for p in centers]
    for i, p in enumerate(centers):
        tangent = (centers[min(i+1,len(centers)-1)]-centers[max(0,i-1)]).normalized()
        axis = tangent.cross(Vector((0,1,0))).normalized()
        if axis.length < .1:
            axis = tangent.cross(Vector((1,0,0))).normalized()
        second = tangent.cross(axis).normalized()
        for j in range(sides):
            a = j*2*math.pi/sides
            verts.append(p+radii[i]*(math.cos(a)*axis+math.sin(a)*second))
            uvs.append((j/sides, i/(len(centers)-1)))
    for i in range(len(centers)-1):
        for j in range(sides):
            a=i*sides+j; b=i*sides+(j+1)%sides
            faces.append((a,b,b+sides,a+sides))
    faces.append(tuple(range(sides-1,-1,-1)))
    faces.append(tuple((len(centers)-1)*sides+j for j in range(sides)))
    return mesh_object(name, verts, faces, coll, mat, parent, uvs)

def empty(name, coll, parent=None, location=(0,0,0)):
    o=bpy.data.objects.new(name,None);coll.objects.link(o);o['generator']=OWNER
    o.location=location
    o.parent=parent
    return o
