"""KYIV - the bottle opens, pours over ice into a rocks glass and stands back beside it (Cycles).
Plays once on the site and ends on the open bottle next to the full glass.
Run: blender -b -P kyiv_bottle_pour.py -- [w=540 h=675 samples=28 frames=120 only=0,60 out=DIR glb=PATH]"""
import bpy, bmesh, math, os, sys, runpy, random
from mathutils import Vector, Matrix
HERE = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opt = dict(a.split("=", 1) for a in argv if "=" in a)
W = int(opt.get("w", 540)); H = int(opt.get("h", 675)); FR = int(opt.get("frames", 120))
OUT = opt.get("out", os.path.join(HERE, "out")); GLB = opt.get("glb", os.path.join(HERE, "kyiv_bottle.glb"))
ONLY = [int(x) for x in opt["only"].split(",")] if "only" in opt else None
sys.argv = ["x", "--", "samples=" + opt.get("samples", "28")]
L = runpy.run_path(os.path.join(HERE, "kyiv_quality_elements.py"), run_name="lib")
sc = L["reset"](); sc.render.resolution_x = W; sc.render.resolution_y = H
sc.cycles.max_bounces = 24; sc.cycles.transmission_bounces = 24; sc.cycles.transparent_max_bounces = 32
lathe, glassmat, smooth, principled = L["lathe"], L["glass"], L["smooth"], L["principled"]

def ease(t): t = max(0.0, min(1.0, t)); return t * t * (3 - 2 * t)
def mix(a, b, t): return a + (b - a) * t
def seg(i, a, b): return ease((i - a) / float(b - a))

# ================================================================ the bottle (same model as the 3D film)
bpy.ops.import_scene.gltf(filepath=GLB)
root = bpy.data.objects["Bottle"]; root.rotation_mode = "XYZ"
gobj = bpy.data.objects["Glass"]
root.scale = (1, 1, 1); bpy.context.view_layer.update()
zs = [(gobj.matrix_world @ v.co).z for v in gobj.data.vertices]
HB_RAW = max(zs) - min(zs); S = 2.87 / HB_RAW            # bottle 2.87 tall: a rocks glass of 0.92 is a third of it
root.scale = (S, S, S); bpy.context.view_layer.update()
def nodes(m): m.use_nodes = True; return m.node_tree.nodes, m.node_tree.links
def tex_of(m, name):
    for n in m.node_tree.nodes:
        if n.type == "TEX_IMAGE" and n.image and n.image.name == name: return n
gm = bpy.data.materials["Glass"]; n, l = nodes(gm); n.clear()
g = n.new("ShaderNodeBsdfGlass"); g.inputs["Color"].default_value = (0.93, 0.96, 1.0, 1); g.inputs["IOR"].default_value = 1.5
l.new(g.outputs[0], n.new("ShaderNodeOutputMaterial").inputs[0])
fm = bpy.data.materials["BlueFoot"]; n, l = nodes(fm); n.clear()
g = n.new("ShaderNodeBsdfGlass"); g.inputs["Color"].default_value = (0.05, 0.28, 1.0, 1); g.inputs["IOR"].default_value = 1.5
l.new(g.outputs[0], n.new("ShaderNodeOutputMaterial").inputs[0])
for name, base, metal in (("Print", "wrap", "wrap_metal"), ("Crest", "crest", "crest_metal"), ("Capsule", "capsule", "capsule_metal")):
    m = bpy.data.materials[name]; n, l = nodes(m); b = n.get("Principled BSDF"); tb = tex_of(m, base); tm = tex_of(m, metal)
    try: m.blend_method = "HASHED"
    except Exception: pass
    if tm:
        for lk in list(b.inputs["Metallic"].links): l.remove(lk)
        sep = n.new("ShaderNodeSeparateColor"); l.new(tm.outputs["Color"], sep.inputs[0]); l.new(sep.outputs[2], b.inputs["Metallic"])
        b.inputs["Roughness"].default_value = 0.25
        for lk in list(b.inputs["Roughness"].links): l.remove(lk)
    if name != "Capsule" and tb and "Alpha" in tb.outputs and not b.inputs["Alpha"].links: l.new(tb.outputs["Alpha"], b.inputs["Alpha"])

# bottle-local geometry (root at origin, upright)
inv = root.matrix_world.inverted()
def local_z(o): return [(inv @ (o.matrix_world @ v.co)).z for v in o.data.vertices]
gz = local_z(gobj); BZ0, BZ1 = min(gz), max(gz)                   # base / mouth, in root-local units
cap = bpy.data.objects["Capsule"]; cz = local_z(cap); CZ0, CZ1 = min(cz), max(cz)

# split the capsule: the screw cap (top ~38%) comes off, the neck sleeve stays
def split_cap():
    zc = CZ1 - (CZ1 - CZ0) * 0.38
    lid = cap.copy(); lid.data = cap.data.copy(); bpy.context.scene.collection.objects.link(lid); lid.name = "Lid"
    for ob, keep_top in ((cap, False), (lid, True)):
        bm = bmesh.new(); bm.from_mesh(ob.data)
        mw = inv @ ob.matrix_world
        dead = [f for f in bm.faces if ((mw @ f.calc_center_median()).z > zc) != keep_top]
        bmesh.ops.delete(bm, geom=dead, context="FACES"); bm.to_mesh(ob.data); bm.free()
    return lid
lid = split_cap()
captop = bpy.data.objects["CapTop"]
lid_base = lid.matrix_basis.copy(); top_base = captop.matrix_basis.copy()

# spirit inside the bottle: a slightly smaller copy of the glass, cut by a world-level plane (stays level when tilted)
liqb = gobj.copy(); liqb.data = gobj.data.copy(); bpy.context.scene.collection.objects.link(liqb); liqb.parent = root
liqb.matrix_parent_inverse = gobj.matrix_parent_inverse.copy(); liqb.matrix_basis = gobj.matrix_basis.copy()
liqb.scale = tuple(s * 0.955 for s in gobj.scale)
liqb.data.materials.clear(); liqb.data.materials.append(glassmat("SpiritB", (0.97, 0.985, 1.0), ior=1.36))
bpy.ops.mesh.primitive_cube_add(size=1); cutter = bpy.context.object; cutter.hide_render = True; cutter.display_type = "WIRE"
cutter.scale = (20, 20, 20)
bo = liqb.modifiers.new("Fill", "BOOLEAN"); bo.operation = "DIFFERENCE"; bo.object = cutter

# pivot at the mouth: the bottle swings about its neck when pouring
bpy.ops.object.empty_add(location=(0, 0, 0)); piv = bpy.context.object
root.parent = piv; root.location = (0, 0, -BZ1 * S)                # mouth sits on the pivot origin
MOUTH = (BZ1 - BZ0) * S                                                   # mouth height above the base, scene units

# ================================================================ rocks glass: heavy base, slight taper, rounded rim
GX, GH = 0.62, 0.92
def r_in(z): return 0.385 + (0.418 - 0.385) * (z - 0.17) / (0.905 - 0.17)
prof = [(0.001, 0.0), (0.33, 0.0), (0.372, 0.006), (0.392, 0.024), (0.398, 0.05),
        (0.437, GH - 0.012), (0.436, GH - 0.004), (0.431, GH), (0.424, GH - 0.002), (0.420, GH - 0.01),
        (r_in(0.30), 0.30), (r_in(0.19), 0.19), (0.378, 0.165), (0.33, 0.15), (0.18, 0.143), (0.001, 0.141)]
gl = lathe("Rocks", prof, seg=160); smooth(gl, 2); gl.location.x = GX
gl.data.materials.append(glassmat("RocksM", (0.975, 0.985, 1.0), ior=1.52))

ZB = 0.142                                                           # inside bottom
NR = 10
lv, lf = [], []
for k in range(NR):
    for j in range(96):
        a = 2 * math.pi * j / 96; lv.append((math.cos(a), math.sin(a), k))
for k in range(NR - 1):
    for j in range(96):
        jj = (j + 1) % 96; lf.append((k * 96 + j, k * 96 + jj, (k + 1) * 96 + jj, (k + 1) * 96 + j))
cb = len(lv); lv.append((0, 0, 0)); ct = len(lv); lv.append((0, 0, NR - 1))
for j in range(96): lf.append(((j + 1) % 96, j, cb)); lf.append(((NR - 1) * 96 + j, (NR - 1) * 96 + (j + 1) % 96, ct))
lq = L["mesh_obj"]("Vodka", lv, lf); lq.location.x = GX
for p in lq.data.polygons: p.use_smooth = True
lq.data.materials.append(glassmat("VodkaM", (0.95, 0.975, 1.0), ior=1.36))
UNIT = [Vector(v) for v in lv]
def set_level(lvl, wob, i):
    for v, u in zip(lq.data.vertices, UNIT):
        k = u.z; z = ZB + 0.004 + (lvl - ZB - 0.004) * k / (NR - 1)
        r = r_in(max(z, 0.17)) - 0.004 if z > 0.17 else 0.30 + (0.378 - 0.30) * (z - ZB) / (0.17 - ZB)
        if k == NR - 1 and (u.x or u.y):
            z += wob * math.sin(math.atan2(u.y, u.x) * 3 + i * 0.7)
        v.co = (u.x * r, u.y * r, z)
    lq.data.update()

ice_m = principled("Ice", (0.93, 0.96, 1.0), rough=0.1, trans=1.0, ior=1.31)
ice = []
for k, (x, y, rz, s) in enumerate([(-0.11, 0.06, 0.3, 0.21), (0.12, -0.07, 0.95, 0.2), (0.02, 0.15, 1.7, 0.19), (-0.02, -0.12, 2.4, 0.17)]):
    bpy.ops.mesh.primitive_cube_add(size=s); c = bpy.context.object
    bv = c.modifiers.new("B", "BEVEL"); bv.width = s * 0.16; bv.segments = 4
    sd = c.modifiers.new("S", "SUBSURF"); sd.levels = sd.render_levels = 1
    for p in c.data.polygons: p.use_smooth = True
    c.data.materials.append(ice_m); ice.append((c, x, y, rz, s, k))

bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.022, depth=1.0); stream = bpy.context.object
stream.data.materials.append(bpy.data.materials["VodkaM"])
for p in stream.data.polygons: p.use_smooth = True

# ================================================================ studio
L["camera"]((-0.12, -5.0, 1.78), (-0.12, 0, 1.58), lens=50)
c = sc.camera.data; c.sensor_fit = "AUTO"
L["area"]("Key", (2.6, -2.6, 3.2), (0, 0, 1.0), 900, (1.0, 0.8, 0.56), size=1.8)
L["area"]("RimL", (-3.2, 1.6, 2.0), (0, 0, 1.2), 1600, (0.45, 0.6, 1.0), size=0.5, sx=3.5)
L["area"]("RimR", (3.2, 1.8, 1.6), (0, 0, 1.0), 1200, (0.55, 0.7, 1.0), size=0.5, sx=3.0)
top = L["area"]("Top", (0, 0, 5.0), (0, 0, 1.0), 300, (0.85, 0.9, 1.0), size=2.5); top.visible_glossy = False
L["softbox"]("TallL", (-3.0, -1.6, 1.5), (0, 0, 1.2), 0.18, 4.5, 4.0, (0.75, 0.85, 1.0))
L["softbox"]("TallR", (3.0, -1.2, 1.5), (0, 0, 1.2), 0.14, 4.5, 3.5, (1.0, 0.86, 0.66))
L["softbox"]("Back", (0, 3.5, 1.4), (0, 0, 1.2), 3.0, 3.0, 0.25, (0.2, 0.36, 1.0))
fl = L["grid"]("Floor", 14, 2)
fl.data.materials.append(L["fade_surface"]("Floor", 2.3, base=(0.001, 0.002, 0.006), rough=0.12, spec=0.45, coat=0.2))

# ================================================================ animation
BX = -0.66                                   # where the bottle stands
POUR = Vector((GX - 0.13, 0, GH + 0.34))     # mouth position while pouring
TILT = math.radians(122)
T = dict(unscrew=(8, 28), lidoff=(26, 40), lift=(34, 56), pour=(58, 90), back=(90, 112))
LV_FULL = 0.50

def frame(i):
    # --- cap: two turns while rising a little, then away up out of the frame
    u = seg(i, *T["unscrew"]); w = seg(i, *T["lidoff"])
    rise = 0.10 * u + 3.2 * w * w
    mv = Matrix.Translation((0.0, 0.0, rise / S)) @ Matrix.Rotation(-4 * math.pi * u - 1.5 * w, 4, "Z")
    lid.matrix_basis = mv @ lid_base; captop.matrix_basis = mv @ top_base
    lid.hide_render = captop.hide_render = w > 0.98
    # --- bottle: upright next to the glass -> over the glass, tilted -> back beside it
    up = Vector((BX, 0, MOUTH))
    a = seg(i, *T["lift"]); b = seg(i, *T["back"])
    if i < T["back"][0]:
        t = a; p = up.lerp(POUR, t) + Vector((0, 0, 0.7 * math.sin(math.pi * t)))
        ang = TILT * ease((i - T["lift"][0] - 4) / (T["lift"][1] - T["lift"][0] + 8))
        if i > T["pour"][0]: ang = TILT + math.radians(6) * seg(i, T["pour"][0], T["pour"][1])
    else:
        t = b; p = POUR.lerp(up, t) + Vector((0, 0, 0.7 * math.sin(math.pi * t)))
        ang = (TILT + math.radians(6)) * (1 - ease(t * 1.15))
    piv.location = p; piv.rotation_euler = (0, ang, 0)
    bpy.context.view_layer.update()
    # spirit in the bottle: a level surface; drops while pouring
    left = 1 - 0.35 * seg(i, T["pour"][0], T["pour"][1])
    mw = liqb.matrix_world; zs = [(mw @ liqb.data.vertices[j].co).z for j in range(0, len(liqb.data.vertices), 7)]
    lo, hi = min(zs), max(zs)
    depth = (hi - lo) * (0.62 if ang < 0.3 else 0.22) * left
    cutter.location = (0, 0, lo + depth + 10)
    # --- glass: level rises while the stream runs
    k = seg(i, T["pour"][0] + 2, T["pour"][1] + 4)
    lvl = ZB + 0.004 + (LV_FULL - ZB) * k
    pouring = T["pour"][0] - 2 <= i <= T["pour"][1] + 4
    wob = 0.010 * (1 if pouring else max(0.0, 1 - (i - T["pour"][1] - 4) / 14.0)) * (1 if k > 0.02 else 0)
    set_level(max(lvl, ZB + 0.008), wob, i); lq.hide_render = k < 0.01
    for c, x, y, rz, s, n in ice:
        rest = ZB + s * 0.5 + n * s * 0.75
        flo = lvl - s * 0.28 + 0.006 * math.sin(i * 0.22 + n * 2)
        c.location = (GX + x, y, max(rest, flo))
        c.rotation_euler = (0.2 * n + 0.04 * math.sin(i * 0.18 + n), 0.15 - 0.05 * n, rz + 0.03 * math.sin(i * 0.12 + n))
    # --- the stream from the mouth to the surface
    mouth = piv.location.copy()
    head = seg(i, T["pour"][0] - 4, T["pour"][0] + 2); tail = seg(i, T["pour"][1] - 2, T["pour"][1] + 4)
    z_top = mix(mouth.z, lvl, tail); z_bot = mix(mouth.z, lvl, head)
    stream.hide_render = not (z_top - z_bot > 0.02)
    stream.location = (mouth.x + 0.02, 0, (z_top + z_bot) / 2); stream.scale = (1, 1, max(0.001, z_top - z_bot))

os.makedirs(OUT, exist_ok=True)
for i in (ONLY if ONLY is not None else range(FR)):
    frame(i)
    sc.render.filepath = os.path.join(OUT, "%04d.png" % i)
    if os.path.exists(sc.render.filepath) and ONLY is None: continue
    bpy.ops.render.render(write_still=True); print("frame", i, flush=True)
