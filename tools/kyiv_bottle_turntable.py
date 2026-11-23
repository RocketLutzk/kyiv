"""KYIV bottle turntable for the hero: 360 deg seamless loop, Cycles.
Variants (v=1|2|3): 1 tilted, 2 straight, 3 big bottle at the right edge of a wide frame."""
import bpy, math, sys, os, runpy
argv = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
opt = dict(a.split("=") for a in argv if "=" in a)
V=opt.get("v","2"); W=int(opt.get("w",720)); Hh=int(opt.get("h",1080)); SAMPLES=int(opt.get("samples",48)); FR=int(opt.get("frames",120))
ONLY=[int(x) for x in opt["only"].split(",")] if "only" in opt else None
OUT=opt.get("out","/home/claude/kyiv-3d/turn/v/"+V)
_sv=sys.argv; sys.argv=['x']
L=runpy.run_path('/home/claude/kyiv-3d/blender/kyiv_quality_elements.py', run_name='lib')
sys.argv=_sv
sc=L['reset'](); sc.render.resolution_x=W; sc.render.resolution_y=Hh; sc.cycles.samples=SAMPLES
bpy.ops.import_scene.gltf(filepath='/home/claude/kyiv-3d/rt/fixed.glb')
root=bpy.data.objects['Bottle']; root.scale=(0.06,)*3; root.rotation_mode='XYZ'; root.rotation_euler=(0,0,0)
bpy.context.view_layer.update()
def nodes(m):
    m.use_nodes=True; return m.node_tree.nodes, m.node_tree.links
def tex_of(m, name):
    for n in m.node_tree.nodes:
        if n.type=='TEX_IMAGE' and n.image and n.image.name==name: return n
# glass body: clear glass with a faint blue
gm=bpy.data.materials['Glass']; n,l=nodes(gm); n.clear()
g=n.new('ShaderNodeBsdfGlass'); g.inputs['Color'].default_value=(0.93,0.96,1.0,1); g.inputs['IOR'].default_value=1.5; g.inputs['Roughness'].default_value=0.0
o=n.new('ShaderNodeOutputMaterial'); l.new(g.outputs[0],o.inputs[0])
# blue foot: deep cobalt glass
fm=bpy.data.materials['BlueFoot']; n,l=nodes(fm); n.clear()
g=n.new('ShaderNodeBsdfGlass'); g.inputs['Color'].default_value=(0.05,0.28,1.0,1); g.inputs['IOR'].default_value=1.5
o=n.new('ShaderNodeOutputMaterial'); l.new(g.outputs[0],o.inputs[0])
# printed / metal layers: keep the image textures, make the "metal" map drive gold metal, and alpha -> transparent
for name,base,metal in (('Print','wrap','wrap_metal'),('Crest','crest','crest_metal'),('Capsule','capsule','capsule_metal')):
    m=bpy.data.materials[name]; n,l=nodes(m)
    b=n.get('Principled BSDF'); tb=tex_of(m,base); tm=tex_of(m,metal)
    try: m.blend_method='HASHED'
    except Exception: pass
    if tm:
        # the metal mask: where it's bright, the surface is gold metal
        for lk in list(b.inputs['Metallic'].links): l.remove(lk)
        sep=n.new('ShaderNodeSeparateColor'); l.new(tm.outputs['Color'],sep.inputs[0]); l.new(sep.outputs[2],b.inputs['Metallic'])
        b.inputs['Roughness'].default_value=0.25
        for lk in list(b.inputs['Roughness'].links): l.remove(lk)
    if name!='Capsule' and tb and 'Alpha' in tb.outputs and not b.inputs['Alpha'].links: l.new(tb.outputs['Alpha'],b.inputs['Alpha'])
# liquid inside the body (scaled copy of the glass, clear spirit)
glass=bpy.data.objects['Glass']
liq=glass.copy(); liq.data=glass.data.copy(); bpy.context.scene.collection.objects.link(liq); liq.parent=root
liq.scale=(0.955,0.955,0.955); liq.location=(0,0,0.25)
liq.data.materials.clear(); liq.data.materials.append(L['glass']('Spirit',(0.97,0.985,1.0),ior=1.36))
# fill to the shoulder: cut with a boolean box
bpy.ops.mesh.primitive_cube_add(size=1); cut=bpy.context.object; cut.name='Cut'
dims=root.matrix_world
bpy.context.view_layer.update()
zs=[ (glass.matrix_world@v.co).z for v in glass.data.vertices]; z0,z1=min(zs),max(zs); H=z1-z0
cut.scale=(5,5,H); cut.location=(0,0,z0+H*0.70+H/2); cut.hide_render=True; cut.display_type='WIRE'
bo=liq.modifiers.new('Fill','BOOLEAN'); bo.operation='DIFFERENCE'; bo.object=cut
# stage ------------------------------------------------------------------
# pivot: the bottle spins about its own axis inside a holder that can be tilted (variant 1)
bpy.ops.object.empty_add(location=(0,0,0)); holder=bpy.context.object
cz=z0+H*0.5
root.parent=holder; root.location.z=-cz          # bottle centre sits on the holder origin
holder.location=(0,0,0)
if V=="1":
    holder.rotation_euler=(math.radians(-10),math.radians(16),0)   # leaning towards the viewer, to the right
    cam=L['camera']((-H*0.13,-H*2.2,H*0.10),(-H*0.13,0,0),lens=50)
elif V=="2":
    cam=L['camera']((0,-H*2.15,H*0.04),(0,0,0),lens=50)              # eye level, no floor
else:
    # close-up from the side of the page: big bottle, cut by the frame edge
    # bottle at the right edge of a wide frame, partly cut by it, full height in view
    cam=L['camera']((-H*0.80,-H*2.6,H*0.02),(-H*0.80,0,H*0.02),lens=50)
K=H
L['area']("Key",(K*1.1,-K*1.1,K*0.7),(0,0,0),360,(1.0,0.8,0.56),size=K*0.6)
L['area']("RimL",(-K*1.2,K*0.55,K*0.2),(0,0,0),1300,(0.45,0.6,1.0),size=K*0.15,sx=K*1.5)
L['area']("RimR",(K*1.2,K*0.6,0),(0,0,0),900,(0.55,0.7,1.0),size=K*0.15,sx=K*1.3)
L['area']("Top",(0,0,K*1.6),(0,0,0),120,(0.85,0.9,1.0),size=K*0.8)
L['area']("Bottom",(0,-K*0.3,-K*1.4),(0,0,0),180,(0.3,0.45,1.0),size=K*0.5)
L['softbox']("SoftL",(-K*0.9,-K*0.5,0),(0,0,0),K*0.12,K*1.5,7,(0.75,0.85,1.0))
L['softbox']("SoftR",(K*0.9,-K*0.4,0),(0,0,0),K*0.10,K*1.4,6,(1.0,0.88,0.7))
L['softbox']("Back",(0,K*1.3,0),(0,0,0),K*0.8,K*1.5,0.6,(0.2,0.38,1.0))
sc.cycles.max_bounces=24; sc.cycles.transmission_bounces=24; sc.cycles.transparent_max_bounces=32
os.makedirs(OUT,exist_ok=True)
for i in (ONLY if ONLY is not None else range(FR)):
    root.rotation_euler=(0,0,2*math.pi*i/FR)
    sc.render.filepath=os.path.join(OUT,'%04d.png'%i)
    if os.path.exists(sc.render.filepath) and ONLY is None: continue
    bpy.ops.render.render(write_still=True); print('frame',i,flush=True)
