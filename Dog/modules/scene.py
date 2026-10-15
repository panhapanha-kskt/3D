"""Scene lifecycle, studio, device selection, saving and structural validation."""
import json,logging,math,os
from pathlib import Path
import bpy
from mathutils import Vector
from .geometry import collection,link_object,OWNER

LOG=logging.getLogger('pug')

def clean_character():
    """Remove only the inspected prior prototype and this generator's owned assets."""
    old=bpy.data.collections.get('PUG_AVATAR')
    victims=set(old.all_objects) if old else set()
    victims.update(o for o in bpy.data.objects if o.get('generator')==OWNER)
    for o in victims:
        bpy.data.objects.remove(o,do_unlink=True)
    for c in list(bpy.data.collections):
        if c.name=='PUG_AVATAR' or c.get('generator')==OWNER:
            bpy.data.collections.remove(c)
    # Only unused prototype/generator datablocks are eligible for cleanup.
    for blocks in [bpy.data.meshes,bpy.data.curves,bpy.data.hair_curves,bpy.data.materials]:
        for d in list(blocks):
            if d.users==0 and (d.name.startswith('PUG2 | ') or 'mesh' in d.name or d.name.startswith(('Fur |','Badge |','Eyes |','Iris |','Mouth interior','Muzzle |','Nose and pupils','Scarf |','Tongue |','Fine ','Head coat'))):
                blocks.remove(d)

def hierarchy():
    cols={};dog=collection('DOG_CHARACTER');dog['generator']=OWNER;cols['DOG_CHARACTER']=dog
    for name in ['BODY','HEAD','FACE','EARS','LEGS','PAWS','TAIL','FUR','ACCESSORIES']:
        c=collection(name,dog);c['generator']=OWNER;cols[name]=c
    for name in ['EYES','EYELIDS','NOSE','MUZZLE','MOUTH','TONGUE','WRINKLES']:
        c=collection(name,cols['FACE']);c['generator']=OWNER;cols[name]=c
    for name in ['SCARF','LOTUS_ORNAMENT']:
        c=collection(name,cols['ACCESSORIES']);c['generator']=OWNER;cols[name]=c
    for name in ['CHARACTER_RIG','RENDER_HELPERS']:
        c=collection(name);c['generator']=OWNER;cols[name]=c
    for name in ['ENVIRONMENT','LIGHTING','CAMERAS']:cols[name]=collection(name)
    return cols

def aim(o,target):
    o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()

def studio(cols,stage):
    scene=bpy.context.scene
    previous_ground=bpy.data.objects.get('Studio ground')
    if previous_ground:
        previous_ground.hide_render=True
        previous_ground.hide_set(True)
    bpy.ops.mesh.primitive_plane_add(size=200)
    ground=bpy.context.object;ground.name='Pug | seamless studio floor'
    link_object(ground,cols['ENVIRONMENT']);ground.location.z=-.015
    from .materials import principled
    mat,p=principled('studio_background',(.29,.25,.22),.87)
    ground.data.materials.clear();ground.data.materials.append(mat)
    for name,pos,power,size,color in [
        ('Key',(-3.8,-4.5,6.0),650,3.0,(1,.90,.80)),
        ('Fill',(3.2,-3.0,3.8),300,3.2,(.86,.92,1)),
        ('Rim',(1.2,2.8,5.2),700,2.6,(1,.88,.75))]:
        o=bpy.data.objects.get(name)
        if o is None or o.type!='LIGHT':
            d=bpy.data.lights.new('Pug studio '+name,'AREA');o=bpy.data.objects.new('Pug studio '+name,d);cols['LIGHTING'].objects.link(o);o['generator']=OWNER
        else:
            for c in list(o.users_collection):c.objects.unlink(o)
            cols['LIGHTING'].objects.link(o)
        o.data.type='AREA';o.data.shape='DISK';o.data.energy=power;o.data.size=size;o.data.color=color;o.location=pos;aim(o,(0,0,2))
    cam=scene.camera
    if cam is None:
        data=bpy.data.cameras.new('Pug portrait camera');cam=bpy.data.objects.new('Pug portrait camera',data);cols['CAMERAS'].objects.link(cam)
    else:
        for c in list(cam.users_collection):c.objects.unlink(cam)
        cols['CAMERAS'].objects.link(cam)
    cam.name='Pug | portrait camera';cam.data.type='PERSP';cam.data.lens=75;cam.data.sensor_width=36
    if stage=='head':cam.location=(.12,-6.7,3.05);aim(cam,(0,-.1,2.76))
    else:cam.location=(.10,-9.0,3.10);aim(cam,(0,-.02,1.85))
    cam.data.dof.use_dof=False;scene.camera=cam
    scene.world.use_nodes=True
    scene.world.node_tree.nodes.get('Background').inputs[0].default_value=(.45,.40,.35,1)
    scene.world.node_tree.nodes.get('Background').inputs[1].default_value=.24
    scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast';scene.view_settings.exposure=.45
    scene.unit_settings.system='METRIC'

def configure_render(cfg,quality):
    scene=bpy.context.scene;scene.render.engine='CYCLES'
    prefs=bpy.context.preferences.addons['cycles'].preferences
    device='CPU'
    try:
        prefs.compute_device_type='OPTIX';prefs.refresh_devices()
        gpu=[d for d in prefs.devices if d.type=='OPTIX']
        if gpu:
            for d in prefs.devices:d.use=d in gpu
            scene.cycles.device='GPU';device='OPTIX: '+gpu[0].name
        else:scene.cycles.device='CPU'
    except (TypeError,RuntimeError) as exc:
        LOG.warning('GPU unavailable; CPU fallback: %s',exc);scene.cycles.device='CPU'
    scene['render_device']=device;LOG.info('Render device: %s',device)
    scene.cycles.samples=cfg.final_samples if quality=='final' else cfg.preview_samples
    scene.cycles.use_denoising=True;scene.cycles.max_bounces=8;scene.cycles.transmission_bounces=6
    scene.cycles.transparent_max_bounces=8;scene.cycles.diffuse_bounces=4
    scene.render.resolution_x=cfg.final_resolution if quality=='final' else 900
    scene.render.resolution_y=cfg.final_resolution if quality=='final' else 1080
    scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA';scene.render.image_settings.color_depth='8'
    return device

def validate(output):
    scene=bpy.context.scene;errors=[];meshes=[];hairs=[]
    for o in bpy.data.collections['DOG_CHARACTER'].all_objects:
        if o.type=='MESH':
            if not o.data.vertices:errors.append(o.name+': empty mesh')
            if any(not math.isfinite(x) for v in o.data.vertices for x in v.co):errors.append(o.name+': nonfinite coordinate')
            if not o.data.materials:errors.append(o.name+': missing material')
            if any(p.area<1e-12 for p in o.data.polygons):
                LOG.warning('Collapsed end-cap faces in %s (parametric pole)',o.name)
            meshes.append({'name':o.name,'vertices':len(o.data.vertices),'faces':len(o.data.polygons)})
        elif o.type=='CURVES':hairs.append({'name':o.name,'strands':len(o.data.curves),'points':len(o.data.points)})
    if not scene.camera:errors.append('Missing camera')
    if len([o for o in scene.objects if o.type=='LIGHT'])<3:errors.append('Missing studio lights')
    for m in bpy.data.materials:
        if m.name.startswith('PUG2 |') and m.node_tree and not any(n.type=='OUTPUT_MATERIAL' for n in m.node_tree.nodes):errors.append(m.name+': missing shader output')
    report={'blender':bpy.app.version_string,'errors':errors,'meshes':meshes,'hair_curves':hairs,'total_strands':sum(x['strands'] for x in hairs),'objects':len(bpy.data.objects),'materials':len(bpy.data.materials),'external_dependencies':list(bpy.utils.blend_paths()),'engine':scene.render.engine,'device':scene.get('render_device'),'resolution':[scene.render.resolution_x,scene.render.resolution_y],'samples':scene.cycles.samples,'limitations':['Inferred hidden anatomy from one view','No deformation rig; transform controls only','Voxel-union anatomy requires retopology for skeletal deformation']}
    Path(output).write_text(json.dumps(report,indent=2),encoding='utf-8')
    if errors:raise RuntimeError('Validation failed: '+str(errors))
    LOG.info('Validation passed: %d mesh objects, %d strands',len(meshes),report['total_strands'])
    return report
