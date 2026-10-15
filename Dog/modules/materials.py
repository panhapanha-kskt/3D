"""PBR materials with spatial color, directional microdetail and real cornea."""
import bpy

def principled(name, color, rough=.5, metal=0.0, subsurface=0.0):
    m=bpy.data.materials.get('PUG2 | '+name)
    if m is None:
        m=bpy.data.materials.new('PUG2 | '+name)
    m.use_nodes=True
    n=m.node_tree.nodes;n.clear();l=m.node_tree.links
    out=n.new('ShaderNodeOutputMaterial');p=n.new('ShaderNodeBsdfPrincipled')
    p.inputs['Base Color'].default_value=(*color,1)
    p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal
    p.inputs['Subsurface Weight'].default_value=subsurface
    l.new(p.outputs[0],out.inputs[0]);m.diffuse_color=(*color,1)
    return m,p

def noise_bump(m,p,scale,strength,distance):
    n=m.node_tree.nodes;l=m.node_tree.links
    t=n.new('ShaderNodeTexNoise');t.inputs['Scale'].default_value=scale;t.inputs['Detail'].default_value=3
    b=n.new('ShaderNodeBump');b.inputs['Strength'].default_value=strength;b.inputs['Distance'].default_value=distance
    l.new(t.outputs['Fac'],b.inputs['Height']);l.new(b.outputs[0],p.inputs['Normal'])

def library(cfg):
    mats={}
    for key,color,rough,metal,sss in [
        ('cream',cfg.cream_color,.82,0,.025),('mask',cfg.mask_color,.79,0,.02),
        ('ears',(.025,.014,.010),.85,0,.01),('lid',(.024,.016,.013),.48,0,.02),
        ('nose',(.009,.006,.005),.38,0,.01),('mouth',(.013,.003,.004),.72,0,0),
        ('tongue',(.67,.17,.21),.42,0,.09),('gold',(.65,.33,.075),.28,.82,0),
        ('gold_dark',(.28,.11,.018),.36,.83,0),('pupil',(.001,.0006,.0003),.1,0,0),
        ('sclera',(.88,.84,.73),.19,0,.015),('claw',(.025,.017,.012),.38,0,0),
        ('fringe_red',(.38,.035,.021),.9,0,0),('fringe_cream',(.75,.64,.46),.9,0,0)]:
        m,p=principled(key,color,rough,metal,sss);mats[key]=m
        if key not in ['pupil','sclera','mouth']:
            noise_bump(m,p,170 if key!='nose' else 95,.3,.004 if key!='nose' else .009)
    # Vertex mask on the continuous organic head, preventing hard patch boundaries.
    m,p=principled('face_coat',cfg.cream_color,.86,0,.025)
    a=m.node_tree.nodes.new('ShaderNodeVertexColor');a.layer_name='FurColor'
    m.node_tree.links.new(a.outputs['Color'],p.inputs['Base Color']);noise_bump(m,p,240,.27,.003)
    mats['face']=m
    m,p=principled('cornea',(1,1,1),.035)
    p.inputs['Transmission Weight'].default_value=1;p.inputs['IOR'].default_value=1.376
    mats['cornea']=m
    # Iris color is authored per vertex to follow actual radial iris geometry.
    m,p=principled('iris',(.4,.12,.012),.34)
    a=m.node_tree.nodes.new('ShaderNodeVertexColor');a.layer_name='IrisColor'
    m.node_tree.links.new(a.outputs['Color'],p.inputs['Base Color']);noise_bump(m,p,300,.14,.001)
    mats['iris']=m
    # Native curves use per-strand color variation instead of thick bevel tubes.
    for key,col in [('fur_cream',cfg.cream_color),('fur_dark',(.032,.022,.017)),('fur_ear',(.025,.014,.010)),('fur_face',cfg.cream_color)]:
        m,p=principled(key,col,.66)
        n=m.node_tree.nodes;l=m.node_tree.links
        info=n.new('ShaderNodeHairInfo');r=n.new('ShaderNodeValToRGB')
        r.color_ramp.elements[0].color=(*(c*.65 for c in col),1)
        r.color_ramp.elements[1].color=(*(min(c*1.45,1) for c in col),1)
        l.new(info.outputs['Random'],r.inputs[0]);l.new(r.outputs[0],p.inputs['Base Color'])
        p.inputs['Sheen Weight'].default_value=.25
        if key=='fur_face':
            attr=n.new('ShaderNodeAttribute');attr.attribute_name='strand_color'
            l.new(attr.outputs['Color'],p.inputs['Base Color'])
        mats[key]=m
    mats['scarf']=gingham()
    return mats

def gingham():
    m,p=principled('woven_gingham',(.6,.2,.12),.88)
    n=m.node_tree.nodes;l=m.node_tree.links
    tc=n.new('ShaderNodeTexCoord');sep=n.new('ShaderNodeSeparateXYZ');l.new(tc.outputs['UV'],sep.inputs[0])
    square=[]
    for axis in ['X','Y']:
        mul=n.new('ShaderNodeMath');mul.operation='MULTIPLY';mul.inputs[1].default_value=3.14159265/.052
        l.new(sep.outputs[axis],mul.inputs[0]);s=n.new('ShaderNodeMath');s.operation='SINE';l.new(mul.outputs[0],s.inputs[0])
        step=n.new('ShaderNodeMath');step.operation='GREATER_THAN';l.new(s.outputs[0],step.inputs[0]);square.append(step)
    add=n.new('ShaderNodeMath');add.operation='ADD'
    for i,s in enumerate(square):l.new(s.outputs[0],add.inputs[i])
    scale=n.new('ShaderNodeMath');scale.operation='MULTIPLY';scale.inputs[1].default_value=.5;l.new(add.outputs[0],scale.inputs[0])
    ramp=n.new('ShaderNodeValToRGB');ramp.color_ramp.interpolation='CONSTANT'
    ramp.color_ramp.elements[0].color=(.27,.028,.018,1);ramp.color_ramp.elements[1].color=(.8,.69,.5,1)
    ramp.color_ramp.elements[1].position=.99;ramp.color_ramp.elements.new(.49).color=(.53,.18,.12,1)
    l.new(scale.outputs[0],ramp.inputs[0]);l.new(ramp.outputs[0],p.inputs['Base Color'])
    # Warp/weft microstructure, in consistent physical UV units on both scarf pieces.
    waves=[]
    for direction in ['X','Y']:
        w=n.new('ShaderNodeTexWave');w.bands_direction=direction;w.inputs['Scale'].default_value=180
        l.new(tc.outputs['UV'],w.inputs['Vector']);waves.append(w)
    mult=n.new('ShaderNodeMath');mult.operation='MULTIPLY'
    for i,w in enumerate(waves):l.new(w.outputs['Color'],mult.inputs[i])
    b=n.new('ShaderNodeBump');b.inputs['Strength'].default_value=.45;b.inputs['Distance'].default_value=.002
    l.new(mult.outputs[0],b.inputs['Height']);l.new(b.outputs[0],p.inputs['Normal']);p.inputs['Sheen Weight'].default_value=.35
    return m
