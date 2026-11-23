"""KYIV - vodka poured over ice into a rocks glass (Cycles). Plays once on the site, ends on the full glass.
Run: blender -b -P pour.py -- [w=720 h=900 samples=48 frames=84 only=0,40 out=DIR]"""
import bpy, math, os, sys, runpy, random
from mathutils import Vector
LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kyiv_quality_elements.py")   # shared studio, materials and helpers
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opt = dict(a.split("=", 1) for a in argv if "=" in a)
W = int(opt.get("w", 720)); H = int(opt.get("h", 900)); FR = int(opt.get("frames", 84))
OUT = opt.get("out", os.path.join(os.path.dirname(os.path.abspath(__file__)), "out"))
ONLY = [int(x) for x in opt["only"].split(",")] if "only" in opt else None
sys.argv = ["x", "--", "samples=" + opt.get("samples", "48")]
L = runpy.run_path(LIB, run_name="lib")
sc = L["reset"](); sc.render.resolution_x = W; sc.render.resolution_y = H
sc.cycles.max_bounces = 24; sc.cycles.transmission_bounces = 24; sc.cycles.transparent_max_bounces = 24
lathe, glass, smooth, principled, fade = L["lathe"], L["glass"], L["smooth"], L["principled"], L["fade_surface"]

# ---- scene (units: decimetres - glass is ~0.9 tall)
R, HB, HG = 0.42, 0.12, 0.92          # outer radius, base thickness, glass height
RI = R - 0.03                         # inner radius
L["camera"]((0, -2.75, 1.0), (0, 0, 0.6), lens=58)
for _o in bpy.data.objects:
    if _o.type == "LIGHT" and _o.name == "Top": _o.visible_glossy = False
L["studio"]((0, 0, 0.5))
bpy.data.objects["Top"].visible_glossy = False
L["softbox"]("Strip", (0, 1.4, 1.9), (0, 0, 0.6), 1.6, 0.1, 3.0, (1.0, 0.72, 0.42))   # gold highlight on the glass, out of the floor
L["area"]("Under", (0, -0.6, -1.2), (0, 0, 0.3), 60, (0.35, 0.5, 1.0), size=0.6)
floor = L["grid"]("Floor", 10, 2); floor.data.materials.append(fade("Floor", 1.05, rough=0.1, spec=0.5, coat=0.3))

# rocks glass: heavy base, straight walls, thin rim
prof = [(0.001, 0.0), (R - 0.02, 0.0), (R, 0.02), (R, HG), (RI, HG), (RI, HB + 0.01), (RI - 0.01, HB), (0.001, HB)]
gl = lathe("Glass", prof, seg=128); smooth(gl, 1)
gl.data.materials.append(glass("GlassM", (0.97, 0.985, 1.0), ior=1.5))

liq_m = glass("Vodka", (0.94, 0.97, 1.0), ior=1.36)
ice_m = principled("Ice", (0.92, 0.96, 1.0), rough=0.12, trans=1.0, ior=1.31)

# liquid: a cylinder whose top we move; a few rings so the surface can ripple
def make_liquid():
    prof = [(0.001, HB + 0.004)] + [(RI - 0.004, HB + 0.004)] + [(RI - 0.004, HB + 0.01)]
    o = lathe("Liquid", prof + [(RI - 0.004, HB + 0.02)], seg=96, cap_top=True, cap_bottom=True)
    smooth(o, 0); o.data.materials.append(liq_m); return o
liq = make_liquid()
lbase = [v.co.copy() for v in liq.data.vertices]

# ice: three rounded cubes
random.seed(3); ice = []
for k, (x, y, rz) in enumerate([(-0.13, 0.05, 0.3), (0.12, -0.06, 0.9), (0.02, 0.16, 1.7)]):
    bpy.ops.mesh.primitive_cube_add(size=0.22)
    c = bpy.context.object; c.name = "Ice%d" % k
    bv = c.modifiers.new("B", "BEVEL"); bv.width = 0.035; bv.segments = 4
    sd = c.modifiers.new("S", "SUBSURF"); sd.levels = sd.render_levels = 1
    for p in c.data.polygons: p.use_smooth = True
    c.data.materials.append(ice_m)
    ice.append((c, x, y, rz, k))

# stream: a thin column of vodka coming in from above the frame
bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.018, depth=1.0)
st = bpy.context.object; st.data.materials.append(liq_m)
for p in st.data.polygons: p.use_smooth = True

def ease(t): t = max(0.0, min(1.0, t)); return t * t * (3 - 2 * t)

T_IN, T_OUT = 6, 60                  # stream arrives / leaves (frames)
LV0, LV1 = HB + 0.004, HB + 0.40     # liquid top: empty / full
def frame(i):
    # pour level: rises while the stream runs, then settles
    u = ease((i - T_IN - 2) / (T_OUT - T_IN))
    lvl = LV0 + (LV1 - LV0) * u
    pouring = T_IN <= i <= T_OUT + 6
    # liquid top with ripples from the stream
    amp = 0.012 * (1 if T_IN < i < T_OUT else max(0, 1 - (i - T_OUT) / 18))
    for v, b in zip(liq.data.vertices, lbase):
        if b.z > HB + 0.015:
            r = math.hypot(b.x, b.y)
            v.co.z = lvl + amp * math.sin(r * 60 - i * 0.9) * math.exp(-r * 4)
        elif b.z > HB + 0.008:
            v.co.z = max(HB + 0.006, lvl - 0.006)
        else:
            v.co.z = b.z
    liq.data.update()
    liq.hide_render = lvl < HB + 0.012
    # ice: rests on the bottom, floats up with the vodka, bobs a little
    for c, x, y, rz, k in ice:
        rest = HB + 0.11 + k * 0.10
        flo = lvl - 0.035 + 0.008 * math.sin(i * 0.25 + k * 2)
        c.location = (x, y, max(rest, flo))
        c.rotation_euler = (0.18 * k + 0.05 * math.sin(i * 0.2 + k), 0.12 - 0.04 * k, rz + 0.02 * math.sin(i * 0.15 + k))
    # stream: top end comes down from above, bottom end follows at the end
    top = 2.4
    head = top - (top - lvl) * ease((i - T_IN + 4) / 6.0) if i >= T_IN - 4 else top + 1
    tail = top if i <= T_OUT else top - (top - lvl) * ease((i - T_OUT) / 6.0)
    lo, hi = max(lvl, head), tail
    st.hide_render = not (hi - lo > 0.02 and i >= T_IN - 4)
    st.location = (0.03, 0.0, (lo + hi) / 2); st.scale = (1, 1, max(0.001, hi - lo))

os.makedirs(OUT, exist_ok=True)
for i in (ONLY if ONLY is not None else range(FR)):
    frame(i)
    sc.render.filepath = os.path.join(OUT, "%04d.png" % i)
    if os.path.exists(sc.render.filepath) and ONLY is None: continue
    bpy.ops.render.render(write_still=True); print("frame", i, flush=True)
