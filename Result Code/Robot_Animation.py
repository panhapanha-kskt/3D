"""Animation-only injection for the inspected 17-bone Khmer_Robot_Rig.
Blender 5.2 tested. Does not edit mesh/curve/rest-bone data, parenting, or materials.
Run: blender --background receptionist-khmer.blend --python inject_khmer_animations.py
Optional script arguments: -- --output PATH
Creates an animated copy by default; never overwrites the source.
"""
import bpy, math, json, hashlib, struct, os, sys, argparse
from mathutils import Vector, Matrix, Quaternion
from math import pi, sin
RIG='Khmer_Robot_Rig'
CLIPS=[('KHMER_Sua_Sdei',1,40),('KHMER_Chumreap_Sour',50,90),('KHMER_Orkun',100,140)]

def fingerprint():
    """Hash all base geometry, topology, attachment data, rest bones and materials."""
    h=hashlib.sha256()
    def put(v):h.update(repr(v).encode('utf8'))
    for o in sorted(bpy.data.objects,key=lambda o:o.name):
        put((o.name,o.type,o.parent.name if o.parent else None,o.parent_type,o.parent_bone))
        put(tuple(tuple(row) for row in o.matrix_basis));put(tuple(tuple(row) for row in o.matrix_parent_inverse))
        if o.type=='MESH':
            put(o.data.name)
            for v in o.data.vertices:h.update(struct.pack('<3f',*v.co))
            for e in o.data.edges:put(tuple(e.vertices))
            for p in o.data.polygons:put((tuple(p.vertices),p.material_index,p.use_smooth))
            for layer in o.data.uv_layers:
                for d in layer.data:put(tuple(d.uv))
            if o.data.shape_keys:
                for k in o.data.shape_keys.key_blocks:
                    for v in k.data:h.update(struct.pack('<3f',*v.co))
        if o.type=='CURVE':
            for s in o.data.splines:
                for p in s.points:put(tuple(p.co))
                for p in s.bezier_points:put((tuple(p.co),tuple(p.handle_left),tuple(p.handle_right)))
        if o.type in {'MESH','CURVE'}:put(tuple(m.name if m else None for m in o.data.materials))
        if o.type=='ARMATURE':
            for b in o.data.bones:put((b.name,b.parent.name if b.parent else None,tuple(tuple(row) for row in b.matrix_local)))
    return h.hexdigest()

def ease(t):
    t=max(0.,min(1.,t));return t*t*t*(t*(t*6-15)+10)

def main():
    args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    p=argparse.ArgumentParser();p.add_argument('--output');opts=p.parse_args(args)
    source=bpy.data.filepath
    if not source:raise RuntimeError('Open the source .blend before running.')
    output=opts.output or os.path.join(os.path.dirname(source),'receptionist-khmer-animated.blend')
    if os.path.normcase(os.path.abspath(output))==os.path.normcase(os.path.abspath(source)):
        raise RuntimeError('Choose a separate output file; source overwrite is disabled.')
    rig=bpy.data.objects.get(RIG)
    if not rig or rig.type!='ARMATURE':raise RuntimeError('Expected Khmer_Robot_Rig; do not use generic AICA bone names.')
    names=['Chest','Neck','Head','UpperArm_R','Forearm_R','Hand_R','UpperArm_L','Forearm_L','Hand_L']
    for name in names:
        if name not in rig.pose.bones:raise RuntimeError('Missing bone '+name)
        if rig.pose.bones[name].constraints:raise RuntimeError('Unexpected constraints on '+name)
    ad=rig.animation_data_create()
    if ad.action or len(ad.nla_tracks):raise RuntimeError('Existing animation detected; injection aborted to preserve it. Use the unanimated source.')
    before=fingerprint();sc=bpy.context.scene
    base={b.name:b.matrix_basis.copy() for b in rig.pose.bones}
    rest={b.name:b.bone.matrix_local.copy() for b in rig.pose.bones}
    previous={};reach_errors=[]
    def reset():
        for b in rig.pose.bones:b.matrix_basis=base[b.name]
        bpy.context.view_layer.update()
    def set_matrix(name,m):
        b=rig.pose.bones[name]
        kw={}
        if b.parent:kw={'parent_matrix':b.parent.matrix,'parent_matrix_local':b.parent.bone.matrix_local}
        b.matrix_basis=b.bone.convert_local_to_pose(m,b.bone.matrix_local,invert=True,**kw)
        bpy.context.view_layer.update()
    def axial(name,angle):
        # X in armature space pitches toward the character's -Y front.
        b=rig.pose.bones[name];r=rest[name].to_quaternion();q=r.inverted()@Quaternion((1,0,0),angle)@r
        b.matrix_basis=base[name]@q.to_matrix().to_4x4();bpy.context.view_layer.update()
    def limb(side,wrist,hand_delta,blend=1.0):
        u=rig.pose.bones['UpperArm_'+side];f=rig.pose.bones['Forearm_'+side];hand=rig.pose.bones['Hand_'+side]
        # All targets use armature coordinates transformed by the bowed chest.
        chest_delta=rig.pose.bones['Chest'].matrix@rest['Chest'].inverted()
        A=u.head.copy();T=chest_delta@Vector(wrist);D=T-A;dist=D.length
        a=u.bone.length;b=f.bone.length
        if not abs(a-b)+.001<dist<a+b-.001:
            raise RuntimeError('Unreachable wrist target: '+side+' '+str(dist))
        direction=D.normalized();s=1 if side=='L' else -1
        hint=chest_delta.to_3x3()@Vector((s*.55,-.15,-1))
        neutral_elbow=chest_delta@rig.data.bones['Forearm_'+side].head_local
        neutral_pole=neutral_elbow-A-direction*(neutral_elbow-A).dot(direction)
        target_pole=hint-direction*hint.dot(direction)
        pole=neutral_pole.normalized().lerp(target_pole.normalized(),blend).normalized()
        along=(a*a-b*b+dist*dist)/(2*dist);height=math.sqrt(max(0,a*a-along*along));E=A+direction*along+pole*height
        # Minimal rotation from inherited rest directions preserves lengths and bone heads.
        for pb,start,end in [(u,A,E),(f,E,T)]:
            inherited=pb.parent.matrix@pb.parent.bone.matrix_local.inverted()@pb.bone.matrix_local
            current=inherited.to_3x3()@Vector((0,1,0));q=current.rotation_difference((end-start).normalized())
            rot=q.to_matrix()@inherited.to_3x3();m=rot.to_4x4();m.translation=start;set_matrix(pb.name,m)
        # The whole rigid hand rotates. Finger geometry and its current splay stay untouched.
        rot=chest_delta.to_3x3()@hand_delta.to_matrix()@rest[hand.name].to_3x3();m=rot.to_4x4();m.translation=T;set_matrix(hand.name,m)
        reach_errors.append((hand.head-T).length)
    actions=[]
    for label,start,end in CLIPS:
        reset();act=bpy.data.actions.new(label);act.use_fake_user=True;ad.action=act;previous={}
        for frame in range(start,end+1):
            sc.frame_set(frame);reset();t=(frame-start)/(end-start)
            # Short anticipation, gentle arrival, readable hold, then smooth release.
            strength=ease(t/.28) if t<.28 else (1 if t<.70 else 1-ease((t-.70)/.30))
            chest_deg=0;neck_deg=0;head_deg=0
            if label.endswith('Sua_Sdei'):
                # Right is the character's right: negative armature X.
                wave=sin((t-.22)*2*pi*2.5)*math.radians(13)*strength
                limb('R',(-1.40,-.30,3.30),Quaternion((0,1,0),wave))
                # Blend from the existing welcoming pose into the wave.
                for n in ('UpperArm_R','Forearm_R','Hand_R'):
                    b=rig.pose.bones[n];q=base[n].to_quaternion().slerp(b.matrix_basis.to_quaternion(),strength);b.matrix_basis=q.to_matrix().to_4x4()
                neck_deg=1.2*strength;head_deg=1.5*strength
            else:
                grateful=label.endswith('Orkun')
                # Palms are forward of scarf and chest; hand depth requires a small separation.
                wrist_z=3.03 if grateful else 2.69
                y=-.98 if grateful else -.91
                # Bow peaks after the palms have arrived and starts releasing before they part.
                bow=ease((t-.25)/.18)*(1-ease((t-.63)/.18))
                chest_deg=(5 if grateful else 2)*bow
                neck_deg=(5 if grateful else 2)*bow
                head_deg=(8 if grateful else 4)*bow
                axial('Chest',math.radians(chest_deg));axial('Neck',math.radians(neck_deg));axial('Head',math.radians(head_deg))
                for side,s in [('L',1),('R',-1)]:
                    # Wrist paths arc forward first to clear body and scarf.
                    neutral=Vector((s*1.57,-.10,3.20));target=Vector((s*.175,y,wrist_z))
                    wrist=neutral.lerp(target,strength);wrist.y-=.11*sin(pi*strength)
                    delta=Quaternion((0,0,1),-s*pi/2*strength)
                    limb(side,wrist,delta,strength)
            if label.endswith('Sua_Sdei'):
                axial('Neck',math.radians(neck_deg));axial('Head',math.radians(head_deg))
            if strength<1e-8:
                for n in names:rig.pose.bones[n].matrix_basis=base[n]
            # Key rotations only. No bone translations, scales, rest-pose or geometry edits.
            for n in names:
                b=rig.pose.bones[n];q=b.matrix_basis.to_quaternion().normalized()
                if n in previous and previous[n].dot(q)<0:q.negate()
                previous[n]=q.copy();b.rotation_mode='QUATERNION';b.rotation_quaternion=q
                b.keyframe_insert(data_path='rotation_quaternion',frame=frame,group=n)
        # Dense, smoothly eased quaternion samples avoid Bezier overshoot into the body.
        for layer in act.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for fc in bag.fcurves:
                        for k in fc.keyframe_points:k.interpolation='LINEAR'
        slot=ad.action_slot;ad.action=None
        tr=ad.nla_tracks.new();tr.name=label
        st=tr.strips.new(label,start,act);st.action_slot=slot;st.extrapolation='NOTHING';st.blend_type='REPLACE'
        actions.append({'action':label,'start':start,'end':end})
        # Mute while authoring later actions, so scene evaluation cannot contaminate them.
        tr.mute=True
    for tr in ad.nla_tracks:tr.mute=False
    sc.frame_start=1;sc.frame_end=140
    for label,start,end in CLIPS:sc.timeline_markers.new(label,frame=start)
    sc.frame_set(1);bpy.context.view_layer.update()
    after=fingerprint()
    if before!=after:raise RuntimeError('Geometry/attachment fingerprint mismatch; output NOT saved.')
    report={'source':source,'output':output,'rig':RIG,'actions':actions,'geometry_before':before,'geometry_after':after,'geometry_unchanged':before==after,'max_analytic_wrist_error':max(reach_errors),'limitations':['No finger bones: existing splayed fingers remain; exact straight-finger Sampeah impossible.','No facial shape keys: existing static smile retained.','Bow angles are animation choices, not cultural standards.','Visual collision review required; no blanket collision-free guarantee.']}
    bpy.ops.wm.save_as_mainfile(filepath=output)
    with open(os.path.join(os.path.dirname(output),'khmer-animation-validation.json'),'w',encoding='utf8') as f:json.dump(report,f,indent=2,ensure_ascii=False)
    print('ANIMATION_INJECTION_OK',json.dumps(report))
if __name__=='__main__':main()

