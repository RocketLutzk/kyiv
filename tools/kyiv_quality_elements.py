"""
KYIV - 3D elements for the "Якість" block (Blender 4.2+ / 5.x, Cycles).

Builds four small scenes from scratch and renders each one as a seamless loop:
  1. spirit  - a drop of spirit hovering over rippling liquid   (Спирт класу «Люкс»)
  2. water   - Carpathian peaks and a moving water surface       (Карпатська вода)
  3. crystal - a turning rock-crystal over charcoal               (фільтрація вугіллям і кришталем)
  4. flask   - a lab flask with rising bubbles                    (контроль кожної партії)

How to use in Blender: Scripting tab -> Open this file -> set OUT_DIR below -> Run Script.
From a terminal:       blender -b -P kyiv_quality_elements.py -- [element ...]
Frames land in OUT_DIR/<element>/0000.png ... ; the loop is seamless (last frame flows into the first).
"""
import bpy, bmesh, math, os, sys, random
from mathutils import Vector

# ----------------------------------------------------------------- settings
OUT_DIR  = os.path.join(os.path.expanduser("~"), "kyiv_elements")
RES      = 720          # square frame size, px
SAMPLES  = 64           # Cycles samples (denoised); 128 for final quality on a GPU
FRAMES   = 96           # frames per loop (96 at 30 fps = 3.2 s)
ELEMENTS = ["spirit", "water", "crystal", "flask"]
BG_SRGB  = (2, 4, 16)   # site background #020410 - what the camera sees behind the object

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
for a in argv:
    if a.startswith("res="): RES = int(a[4:])
    elif a.startswith("samples="): SAMPLES = int(a[8:])
    elif a.startswith("frames="): FRAMES = int(a[7:])
    elif a.startswith("out="): OUT_DIR = a[4:]
    elif a.startswith("only="): pass
_sel = [a for a in argv if "=" not in a]
STEP = 1
for a in argv:
    if a.startswith("step="): STEP = int(a[5:])          # step=12 -> quick preview of every 12th frame
ONLY = [int(a[5:]) for a in argv if a.startswith("only=")]  # only=0 -> render just that frame
if _sel: ELEMENTS = _sel

def lin(c):  # sRGB 0..255 -> linear
    c = c / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

GOLD = (0.83, 0.55, 0.26)

# ----------------------------------------------------------------- scene basics
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    cy = sc.cycles
    cy.samples = SAMPLES
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = 0.02
    cy.use_denoising = True
    try: cy.denoiser = "OPENIMAGEDENOISE"
    except Exception: pass
    cy.max_bounces = 16; cy.transmission_bounces = 16; cy.glossy_bounces = 8
    cy.transparent_max_bounces = 16; cy.caustics_reflective = True; cy.caustics_refractive = True
    cy.blur_glossy = 0.6
    pick_device(sc)
    sc.render.resolution_x = sc.render.resolution_y = RES
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.view_settings.view_transform = "Standard"     # keeps the background exactly the site colour
    sc.view_settings.look = "None"
    sc.view_settings.exposure = 0
    world(sc)
    return sc

def pick_device(sc):
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for t in ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"):
            try:
                prefs.compute_device_type = t
                prefs.get_devices()
                devs = [d for d in prefs.devices if d.type == t]
                if devs:
                    for d in prefs.devices: d.use = d.type in (t, "CPU") and d.type == t
                    sc.cycles.device = "GPU"; print("render device:", t); return
            except Exception:
                continue
    except Exception:
        pass
    sc.cycles.device = "CPU"; print("render device: CPU")

def world(sc):
    """Camera rays see the exact site colour; reflections see a dark blue studio."""
    w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
    nt = w.node_tree; n = nt.nodes; n.clear()
    out = n.new("ShaderNodeOutputWorld")
    lp = n.new("ShaderNodeLightPath")
    cam = n.new("ShaderNodeBackground"); cam.inputs[0].default_value = (*[lin(c) for c in BG_SRGB], 1); cam.inputs[1].default_value = 1
    env = n.new("ShaderNodeBackground"); env.inputs[0].default_value = (0.0015, 0.0025, 0.009, 1); env.inputs[1].default_value = 1
    mix = n.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
    nt.links.new(env.outputs[0], mix.inputs[1]); nt.links.new(cam.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])

def camera(loc, look, lens=55):
    cd = bpy.data.cameras.new("Cam"); cd.lens = lens
    c = bpy.data.objects.new("Cam", cd); bpy.context.scene.collection.objects.link(c)
    c.location = loc; aim(c, look); bpy.context.scene.camera = c
    return c

def aim(o, target):
    d = Vector(target) - o.location
    o.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()

def area(name, loc, look, power, color, size=1.0, shape="RECTANGLE", sx=None):
    ld = bpy.data.lights.new(name, "AREA"); ld.energy = power; ld.color = color
    ld.shape = shape; ld.size = size; ld.size_y = sx or size
    o = bpy.data.objects.new(name, ld); bpy.context.scene.collection.objects.link(o)
    o.location = loc; aim(o, look); return o

def softbox(name, loc, look, w, h, strength, color=(1, 1, 1)):
    """An emitting card out of view: gives glass its long studio highlights."""
    bpy.ops.mesh.primitive_plane_add(size=1, location=loc)
    o = bpy.context.object; o.name = name; o.scale = (w, h, 1); aim(o, look)
    m = bpy.data.materials.new(name); m.use_nodes = True
    n = m.node_tree.nodes; n.clear()
    e = n.new("ShaderNodeEmission"); e.inputs[0].default_value = (*color, 1); e.inputs[1].default_value = strength
    lp = n.new("ShaderNodeLightPath"); tr = n.new("ShaderNodeBsdfTransparent"); mx = n.new("ShaderNodeMixShader")
    out = n.new("ShaderNodeOutputMaterial")
    l = m.node_tree.links
    l.new(lp.outputs["Is Camera Ray"], mx.inputs[0]); l.new(e.outputs[0], mx.inputs[1]); l.new(tr.outputs[0], mx.inputs[2])
    l.new(mx.outputs[0], out.inputs[0])
    o.data.materials.append(m); o.visible_shadow = False
    return o

def studio(center=(0, 0, 0.6)):
    """Shared lighting: warm gold key, cold blue rims, long softboxes for glass highlights."""
    area("Key", (2.6, -2.2, 2.6), center, 260, (1.0, 0.78, 0.52), size=1.6)
    area("RimL", (-2.8, 1.6, 1.8), center, 340, (0.45, 0.6, 1.0), size=0.6, sx=3.0)
    area("RimR", (2.6, 2.2, 1.2), center, 220, (0.55, 0.7, 1.0), size=0.5, sx=2.4)
    area("Top", (0, 0, 4.0), center, 90, (0.8, 0.86, 1.0), size=2.0)
    softbox("SoftL", (-2.4, -0.6, 1.0), center, 0.35, 3.2, 6, (0.75, 0.85, 1.0))
    softbox("SoftR", (2.4, -0.4, 1.1), center, 0.25, 3.0, 5, (1.0, 0.88, 0.7))

# ----------------------------------------------------------------- materials
def principled(name, base=(1, 1, 1), rough=0.0, metal=0.0, trans=0.0, ior=1.45, coat=0.0, emit=None, emit_s=0.0, spec=0.5):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    def s(k, v):
        if k in b.inputs: b.inputs[k].default_value = v
    s("Base Color", (*base, 1)); s("Roughness", rough); s("Metallic", metal)
    s("Transmission Weight", trans); s("Transmission", trans); s("IOR", ior)
    s("Coat Weight", coat); s("Specular IOR Level", spec)
    if emit: s("Emission Color", (*emit, 1)); s("Emission Strength", emit_s)
    return m

def glass(name, tint=(1, 1, 1), ior=1.5, rough=0.0, dispersion=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    n = m.node_tree.nodes; n.clear()
    g = n.new("ShaderNodeBsdfGlass"); g.inputs["Color"].default_value = (*tint, 1)
    g.inputs["IOR"].default_value = ior; g.inputs["Roughness"].default_value = rough
    if "Dispersion" in g.inputs: g.inputs["Dispersion"].default_value = dispersion
    out = n.new("ShaderNodeOutputMaterial"); m.node_tree.links.new(g.outputs[0], out.inputs[0])
    return m

def fade_surface(name, radius, base=(0.004, 0.008, 0.03), rough=0.06, spec=0.7, coat=0.5, center=(0, 0), metal=0.0):
    """Dark glossy surface that dissolves into the site background towards its edge - no visible horizon."""
    m = principled(name, base, rough=rough, spec=spec, coat=coat, metal=metal)
    nt = m.node_tree; n = nt.nodes; l = nt.links
    bsdf = n.get("Principled BSDF"); out = n.get("Material Output")
    tc = n.new("ShaderNodeTexCoord")
    sub = n.new("ShaderNodeVectorMath"); sub.operation = "SUBTRACT"; sub.inputs[1].default_value = (center[0], center[1], 0)
    sc = n.new("ShaderNodeVectorMath"); sc.operation = "SCALE"; sc.inputs["Scale"].default_value = 1 / radius
    gr = n.new("ShaderNodeTexGradient"); gr.gradient_type = "SPHERICAL"
    ramp = n.new("ShaderNodeValToRGB"); ramp.color_ramp.elements[0].position = 0.0; ramp.color_ramp.elements[1].position = 0.75
    ramp.color_ramp.interpolation = "EASE"
    bg = n.new("ShaderNodeEmission"); bg.inputs[0].default_value = (*[lin(c) for c in BG_SRGB], 1); bg.inputs[1].default_value = 1
    mx = n.new("ShaderNodeMixShader")
    l.new(tc.outputs["Object"], sub.inputs[0]); l.new(sub.outputs[0], sc.inputs[0]); l.new(sc.outputs[0], gr.inputs[0])
    l.new(gr.outputs["Fac"], ramp.inputs[0])
    l.new(ramp.outputs["Color"], mx.inputs[0]); l.new(bg.outputs[0], mx.inputs[1]); l.new(bsdf.outputs[0], mx.inputs[2])
    l.new(mx.outputs[0], out.inputs[0])
    return m

def gold():  return principled("Gold", GOLD, rough=0.22, metal=1.0)
def liquid(): return glass("Spirit", (0.96, 0.98, 1.0), ior=1.36)

def smooth(o, level=2):
    for p in o.data.polygons: p.use_smooth = True
    if level:
        md = o.modifiers.new("Sub", "SUBSURF"); md.levels = md.render_levels = level

def link(o): bpy.context.scene.collection.objects.link(o); return o

def mesh_obj(name, verts, faces):
    me = bpy.data.meshes.new(name); me.from_pydata(verts, [], faces); me.update()
    return link(bpy.data.objects.new(name, me))

def lathe(name, profile, seg=96, cap_top=False, cap_bottom=False):
    """Revolve a list of (radius, z) points around Z."""
    v, f = [], []
    P = len(profile)
    for i in range(seg):
        a = 2 * math.pi * i / seg
        for r, z in profile: v.append((r * math.cos(a), r * math.sin(a), z))
    for i in range(seg):
        j = (i + 1) % seg
        for k in range(P - 1):
            f.append((i * P + k, j * P + k, j * P + k + 1, i * P + k + 1))
    if cap_bottom:
        c = len(v); v.append((0, 0, profile[0][1]))
        for i in range(seg): f.append(((i + 1) % seg * P, i * P, c))
    if cap_top:
        c = len(v); v.append((0, 0, profile[-1][1]))
        for i in range(seg): f.append((i * P + P - 1, (i + 1) % seg * P + P - 1, c))
    return mesh_obj(name, v, f)

def grid(name, size, n):
    v = [(-size / 2 + size * i / n, -size / 2 + size * j / n, 0) for j in range(n + 1) for i in range(n + 1)]
    f = [(j * (n + 1) + i, j * (n + 1) + i + 1, (j + 1) * (n + 1) + i + 1, (j + 1) * (n + 1) + i) for j in range(n) for i in range(n)]
    o = mesh_obj(name, v, f)
    for p in o.data.polygons: p.use_smooth = True
    return o

# ----------------------------------------------------------------- 1. spirit drop
def build_spirit():
    camera((0, -3.4, 1.25), (0, 0, 0.55), lens=62)
    studio((0, 0, 0.7))
    softbox("GoldStrip", (0, 3.2, 0.35), (0, 0, 0.3), 5.0, 0.22, 2.2, (1.0, 0.7, 0.4))
    # drop: a sphere whose upper half narrows to a point
    prof = []
    for i in range(41):
        t = i / 40                      # 0 bottom .. 1 tip
        a = math.pi * t
        if t < 0.5: r = math.sin(a) * 0.30; z = (1 - math.cos(a)) * 0.30
        else:
            u = (t - 0.5) / 0.5         # 0..1 along the neck
            r = 0.30 * (1 - u) ** 1.6; z = 0.30 + u * 0.52
        prof.append((max(r, 0.0005), z))
    drop = lathe("Drop", prof, seg=64)
    smooth(drop, 1); drop.data.materials.append(liquid())
    # liquid surface
    pool = grid("Pool", 9, 220)
    pool.data.materials.append(fade_surface("Pool", 2.6, base=(0.001, 0.002, 0.007), rough=0.03))
    base = [v.co.copy() for v in pool.data.vertices]
    # a ring of gold light on the surface
    def frame(ph):
        drop.location = (0, 0, 0.62 + 0.06 * math.sin(ph))
        drop.rotation_euler = (0.04 * math.sin(ph), 0.03 * math.cos(ph), 0)
        for v, b in zip(pool.data.vertices, base):
            r = math.hypot(b.x, b.y)
            v.co.z = 0.035 * math.exp(-r * 0.55) * math.sin(r * 7.0 - 2 * ph) * min(1, r * 3)
        pool.data.update()
    return frame

# ----------------------------------------------------------------- 2. Carpathian water
def build_water():
    camera((0, -4.6, 0.55), (0, 2.0, 0.95), lens=50)
    area("Key", (3.5, 5.5, 2.6), (0, 3.0, 0.6), 260, (1.0, 0.76, 0.48), size=1.5)
    area("RimL", (-4.0, 4.5, 1.6), (0, 2.6, 0.8), 260, (0.45, 0.6, 1.0), size=1.0, sx=3)
    area("Back", (0.9, 7.0, 1.4), (0, 2.5, 0.6), 500, (1.0, 0.72, 0.42), size=1.2)
    # (no sky softbox here: it showed up as grey slabs in the water)
    # low gold sun behind the ridges
    bpy.ops.mesh.primitive_circle_add(vertices=96, radius=0.62, fill_type="NGON", location=(0.75, 5.6, 1.25))
    sun = bpy.context.object; sun.rotation_euler = (math.radians(90), 0, 0)
    sun.data.materials.append(principled("Sun", GOLD, emit=(1.0, 0.66, 0.36), emit_s=1.25))
    # three ridges of peaks, darker towards the viewer
    random.seed(4)
    for row, (y, h, col) in enumerate([(4.6, 1.55, (0.02, 0.035, 0.1)), (3.7, 1.15, (0.009, 0.016, 0.05)), (2.9, 0.75, (0.003, 0.006, 0.018))]):
        n = 44; xs = [-6 + 12 * i / n for i in range(n + 1)]
        top = []
        for i, x in enumerate(xs):
            z = h * (0.35 + 0.65 * (0.5 + 0.5 * math.cos(x * 1.15 + row * 2.3)) ** 2) + random.uniform(-0.04, 0.04)
            top.append((x, y + random.uniform(-0.05, 0.05), z))
        d = 0.9 + row * 0.25
        v = [(x, yy - d, -0.2) for x, yy, _ in top] + [(x, yy, z) for x, yy, z in top] + [(x, yy + d, -0.2) for x, yy, _ in top]
        f = []
        for i in range(n):
            f.append((i, i + 1, n + 2 + i, n + 1 + i))                       # front slope
            f.append((n + 1 + i, n + 2 + i, 2 * n + 3 + i, 2 * n + 2 + i))   # back slope
        o = mesh_obj("Ridge%d" % row, v, f)
        o.data.materials.append(principled("Rock%d" % row, col, rough=0.5, spec=0.5))
    # water: dark mirror with waves that fades out at the sides
    w = grid("Water", 16, 280); w.location = (0, 1.0, 0)
    w.data.materials.append(fade_surface("Water", 6.0, base=(0.25, 0.32, 0.5), rough=0.025, spec=0.5, coat=0.0, center=(0, 0.6), metal=1.0))
    for o in bpy.data.objects:          # lamps light the peaks but do not glare in the water
        if o.type == "LIGHT": o.visible_glossy = False
    base = [v.co.copy() for v in w.data.vertices]
    def frame(ph):
        for v, b in zip(w.data.vertices, base):
            x, y = b.x, b.y
            v.co.z = (0.012 * math.sin(x * 2.4 + y * 1.1 - ph) +
                      0.008 * math.sin(x * -1.6 + y * 3.1 - 2 * ph) +
                      0.007 * math.sin(x * 5.3 + y * 4.4 - 3 * ph))
        w.data.update()
    return frame

# ----------------------------------------------------------------- 3. rock crystal
def crystal_mesh(name, r, h, tip):
    v = []; f = []
    for i in range(6):
        a = math.pi / 3 * i
        v.append((r * math.cos(a), r * math.sin(a), 0))
        v.append((r * math.cos(a), r * math.sin(a), h))
    v.append((0, 0, h + tip)); v.append((0, 0, -0.02))
    for i in range(6):
        j = (i + 1) % 6
        f.append((2 * i, 2 * j, 2 * j + 1, 2 * i + 1))
        f.append((2 * i + 1, 2 * j + 1, 12))
        f.append((2 * j, 2 * i, 13))
    o = mesh_obj(name, v, f)
    bv = o.modifiers.new("B", "BEVEL"); bv.width = 0.012; bv.segments = 2
    return o

def build_crystal():
    camera((0, -4.4, 1.7), (0, 0, 0.78), lens=55)
    studio((0, 0, 0.9))
    area("Beam", (0, 0.4, 4.2), (0, 0, 0.6), 420, (1.0, 0.86, 0.66), size=0.25)
    cm = glass("Crystal", (0.97, 0.99, 1.0), ior=1.544, rough=0.01, dispersion=0.25)
    main = crystal_mesh("Main", 0.3, 1.1, 0.42); main.data.materials.append(cm)
    main.location = (0, 0, 0.12)
    small = []
    for (x, y, rz, ry, s) in [(-0.55, 0.15, 0.4, -0.45, 0.55), (0.5, 0.25, 1.1, 0.5, 0.5), (0.15, 0.55, 2.0, 0.25, 0.42), (-0.25, 0.6, 0.2, -0.2, 0.36)]:
        o = crystal_mesh("C", 0.3 * s, 1.1 * s, 0.42 * s); o.data.materials.append(cm)
        o.location = (x, y, 0.08); o.rotation_euler = (0, ry, rz); small.append(o)
    # charcoal: dark faceted lumps the crystals stand in
    coal = principled("Charcoal", (0.0012, 0.0013, 0.0018), rough=0.5, spec=0.12)
    random.seed(7)
    for i in range(22):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=random.uniform(0.09, 0.2),
            location=(random.uniform(-1.0, 1.0), random.uniform(-0.5, 0.9), random.uniform(-0.05, 0.05)))
        o = bpy.context.object
        for v in o.data.vertices: v.co *= random.uniform(0.75, 1.25)
        o.rotation_euler = (random.random() * 6, random.random() * 6, random.random() * 6)
        o.data.materials.append(coal)
    floor = grid("Floor", 12, 2); floor.location.z = -0.06
    floor.data.materials.append(fade_surface("Floor", 2.0, rough=0.18, spec=0.5, coat=0.2))
    def frame(ph):
        main.rotation_euler = (0, 0, ph / 6)          # 60 deg per loop: the hexagon repeats seamlessly
    return frame

# ----------------------------------------------------------------- 4. laboratory flask
def build_flask():
    camera((0, -4.6, 1.45), (0, 0, 0.78), lens=55)
    studio((0, 0, 0.8))
    outer = [(0.001, 0.0), (0.42, 0.0), (0.56, 0.05), (0.60, 0.16), (0.47, 0.55), (0.24, 1.02), (0.15, 1.24),
             (0.15, 1.62), (0.18, 1.66), (0.18, 1.70)]
    fl = lathe("Flask", outer, seg=96)
    sol = fl.modifiers.new("Wall", "SOLIDIFY"); sol.thickness = 0.022; sol.offset = 1
    smooth(fl, 1); fl.data.materials.append(glass("Glass", (0.97, 0.985, 1.0), ior=1.5))
    # liquid: slightly smaller than the inside wall
    fill = 0.62
    inner = []
    for r, z in outer:
        if z > fill: break
        inner.append((max(0.001, r - 0.03), z + 0.025))
    inner.append((inner[-1][0] - 0.02, fill))
    lq = lathe("Liquid", inner, seg=96, cap_top=True)
    smooth(lq, 0); lq.data.materials.append(glass("Liquid", (0.92, 0.96, 1.0), ior=1.36))
    # gold neck band and graduation marks
    bpy.ops.mesh.primitive_torus_add(major_radius=0.172, minor_radius=0.012, location=(0, 0, 1.40))
    ring = bpy.context.object; ring.data.materials.append(gold()); smooth(ring, 0)
    for k, z in enumerate([0.22, 0.30, 0.38]):
        r = 0.60 - (z - 0.16) * (0.13 / 0.39) + 0.004
        bpy.ops.mesh.primitive_torus_add(major_radius=r, minor_radius=0.004, location=(0, 0, z),
                                         major_segments=64, minor_segments=6)
        t = bpy.context.object; t.data.materials.append(gold())
        t.scale = (1, 1, 1)
    floor = grid("Floor", 12, 2); floor.location.z = -0.002
    floor.data.materials.append(fade_surface("Floor", 1.8, rough=0.12, spec=0.5, coat=0.3))
    # bubbles
    random.seed(11); bub = []
    bm = glass("Bubble", (1, 1, 1), ior=1 / 1.36)
    for i in range(14):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=random.uniform(0.018, 0.04), segments=16, ring_count=8)
        o = bpy.context.object; o.data.materials.append(bm); smooth(o, 0)
        bub.append((o, random.uniform(-0.28, 0.28), random.uniform(-0.28, 0.28), random.random(), random.choice([1, 2])))
    def frame(ph):
        f = ph / (2 * math.pi)
        for o, x, y, off, sp in bub:
            u = (off + f * sp) % 1.0
            z = 0.06 + u * (fill - 0.1)
            shrink = min(1, (1 - u) * 6, u * 10)
            o.location = (x * (1 - z * 0.5), y * (1 - z * 0.5), z)
            o.scale = (shrink,) * 3
            o.hide_render = shrink < 0.05
    return frame

BUILD = {"spirit": build_spirit, "water": build_water, "crystal": build_crystal, "flask": build_flask}

def render(name):
    sc = reset()
    frame = BUILD[name]()
    d = os.path.join(OUT_DIR, name); os.makedirs(d, exist_ok=True)
    idx = ONLY or range(0, FRAMES, STEP)
    for i in idx:
        frame(2 * math.pi * i / FRAMES)
        sc.render.filepath = os.path.join(d, "%04d.png" % i)
        if os.path.exists(sc.render.filepath) and not ONLY: continue
        bpy.ops.render.render(write_still=True)
        print(name, i, flush=True)

if __name__ != "lib":
    for e in ELEMENTS:
        render(e)
    print("done ->", OUT_DIR)
