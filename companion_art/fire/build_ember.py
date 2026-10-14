"""Build the URI fire companion ("Ember") in Blender from source.

    blender -b --factory-startup -P companion_art/fire/build_ember.py -- \
        --out companion_art/fire/ember.blend

Everything in the .blend is produced here, so the asset is reviewable as code
and can be rebuilt on any machine with Blender 4.2+ (developed on 5.2.2).

Structure
---------
* EMBER_CTRL   - an empty carrying every expression control as a custom
                 property (see states.json). Nothing else is keyed by hand:
                 drivers read these properties and the scene frame, and every
                 periodic driver divides the clip length ``loop``, so any clip
                 rendered over ``loop`` frames repeats seamlessly.
* EMBER_RIG    - armature: root, body, head, arms and legs.
* Head, eyes, lids, brows, mouth, blush - parented to the head bone.
* Robe, limbs  - skinned (limbs are skin-modifier tubes on a vertex chain).
* Flames       - Curves objects whose strand roots, directions and seeds are
                 attributes; one geometry-nodes group ("EmberFlame") grows,
                 sweeps, swirls and shakes them from the controls.
* Embers       - Points object driven by the "EmberSparks" node group.
* Actions      - one action per clip ("EMBER_<clip>") keying the controls,
                 so the clips are also available inside Blender.

No external assets, textures or add-ons are used.
"""

from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

HERE = Path(__file__).resolve().parent
STATES = json.loads((HERE / "states.json").read_text(encoding="utf-8"))
CTRL_NAME = "EMBER_CTRL"

# Proportions (Blender units; feet on z=0, camera looks along +Y).
HEAD_C = Vector((0.0, 0.0, 1.30))
HEAD_R = (0.44, 0.35, 0.33)  # x (width), y (depth), z (height) semi-axes
NECK_Z = 1.02
HEM_Z = 0.50


# ------------------------------------------------------------------ utils


def args() -> dict:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    out = {"out": str(HERE / "ember.blend")}
    for i, a in enumerate(argv):
        if a == "--out":
            out["out"] = argv[i + 1]
    return out


def reset_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def link(obj: bpy.types.Object) -> bpy.types.Object:
    bpy.context.scene.collection.objects.link(obj)
    return obj


def ctrl_driver(owner, path: str, expr: str, props: list[str], index: int = -1):
    """Add a scripted driver on ``owner.path`` reading EMBER_CTRL props.

    Expressions use only what Blender's simple-expression evaluator accepts
    (arithmetic, sin/cos/pi/min/max, ``frame``), so files open and render
    without enabling Python auto-run."""
    fc = owner.driver_add(path, index) if index >= 0 else owner.driver_add(path)
    drv = fc.driver
    drv.type = "SCRIPTED"
    ctrl = bpy.data.objects[CTRL_NAME]
    for p in props:
        v = drv.variables.new()
        v.name = p
        v.type = "SINGLE_PROP"
        v.targets[0].id_type = "OBJECT"
        v.targets[0].id = ctrl
        v.targets[0].data_path = f'["{p}"]'
    drv.expression = expr
    return fc


def mod_input(mod, ng, name):
    """The value holder of a geometry-nodes modifier input (Blender 5.x
    exposes them as structs under ``properties.inputs``; 4.x as ID
    properties). Returns (owner, path) for driver_add."""
    ident = next(it.identifier for it in ng.interface.items_tree
                 if getattr(it, "in_out", "") == "INPUT" and it.name == name)
    props = getattr(mod, "properties", None)
    if props is not None and hasattr(props, "inputs"):
        return getattr(props.inputs, ident), "value"
    return mod, f'["{ident}"]'


def principled(name: str, color, rough=0.5, emission=None, strength=0.0, alpha=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    if emission is not None:
        b.inputs["Emission Color"].default_value = (*emission, 1)
        b.inputs["Emission Strength"].default_value = strength
    if alpha < 1:
        b.inputs["Alpha"].default_value = alpha
    return m


def set_blend(m: bpy.types.Material) -> None:
    for attr, val in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND")):
        if hasattr(m, attr):
            try:
                setattr(m, attr, val)
            except Exception:
                pass
    if hasattr(m, "use_transparency_overlap"):
        m.use_transparency_overlap = True


# --------------------------------------------------------------- controls


def build_controls() -> bpy.types.Object:
    ctrl = bpy.data.objects.new(CTRL_NAME, None)
    link(ctrl)
    ctrl.empty_display_type = "SPHERE"
    ctrl.location = (1.2, 0, 1.3)
    for k, v in STATES["defaults"].items():
        ctrl[k] = float(v)
        ui = ctrl.id_properties_ui(k)
        ui.update(min=-4.0, max=200.0, soft_min=-1.0, soft_max=2.0, description=f"Ember control: {k}")
    return ctrl


# ------------------------------------------------------------------- rig


def build_rig() -> bpy.types.Object:
    arm = bpy.data.armatures.new("EMBER_RIG")
    rig = link(bpy.data.objects.new("EMBER_RIG", arm))
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.edit_bones

    def bone(name, head, tail, parent=None):
        b = eb.new(name)
        b.head, b.tail = Vector(head), Vector(tail)
        if parent:
            b.parent = eb[parent]
        return b

    bone("root", (0, 0, 0), (0, 0.25, 0))
    bone("body", (0, 0, 0.42), (0, 0, NECK_Z), "root")
    bone("head", (0, 0, NECK_Z), (0, 0, NECK_Z + 0.5), "body")
    for s, x in (("L", 1), ("R", -1)):
        bone(f"arm_up.{s}", (0.06 * x, 0, 0.92), (0.20 * x, 0, 0.76), "body")
        bone(f"arm_lo.{s}", (0.20 * x, 0, 0.76), (0.33 * x, -0.02, 0.64), f"arm_up.{s}")
        bone(f"leg.{s}", (0.05 * x, 0, 0.52), (0.07 * x, 0, 0.02), "root")
    # Every bone's local Z faces the camera axis (-Y), so rotation about Z
    # is always a turn in the picture plane: raise/lower arms, spread legs,
    # tilt the head. Local X stays the "nod" axis.
    for b in eb:
        b.align_roll(Vector((0, -1, 0)))
    bpy.ops.object.mode_set(mode="POSE")
    for pb in rig.pose.bones:
        pb.rotation_mode = "XYZ"
    bpy.ops.object.mode_set(mode="OBJECT")
    return rig


def drive_rig(rig: bpy.types.Object) -> None:
    pb = rig.pose.bones
    two_pi = "2*pi*frame/loop"
    # Whole-body bob, hop and sway. The hop is a bounce (|sin|), so the feet
    # leave the ground twice per loop and land softly.
    ctrl_driver(pb["root"], "location", f"bob*sin({two_pi}) + hop*abs(sin({two_pi})) - 0.04*slump", ["bob", "hop", "loop", "slump"], 2)
    ctrl_driver(pb["root"], "rotation_euler", f"sway*sin({two_pi}) ", ["sway", "loop"], 1)
    # Bones point along +Z, so X rotation tips forward/back.
    ctrl_driver(pb["body"], "rotation_euler", "0.30*slump - 0.10*lean", ["slump", "lean"], 0)
    ctrl_driver(pb["head"], "rotation_euler", f"0.10*slump - 0.25*lean + 0.02*sin({two_pi}+1)", ["slump", "lean", "loop"], 0)
    ctrl_driver(pb["head"], "rotation_euler", "head_tilt", ["head_tilt"], 2)
    # Head size relative to the body: scales the head and everything on it
    # (face, flame, aura) about the neck.
    for i in range(3):
        ctrl_driver(pb["head"], "scale", "head_size", ["head_size"], i)
    for s, sgn in (("L", 1), ("R", -1)):
        # Arms: out (abduction), up (cheer), small swing.
        ctrl_driver(
            pb[f"arm_up.{s}"], "rotation_euler",
            f"{sgn}*(-0.15 + 0.55*arms_out + 0.85*arms_up - 0.35*slump + 0.05*sin({two_pi}+{sgn}))",
            ["arms_out", "arms_up", "slump", "loop"], 2,
        )
        ctrl_driver(
            pb[f"arm_lo.{s}"], "rotation_euler",
            f"{sgn}*(0.2*arms_out + 0.45*arms_up - 0.2*slump + 0.08*sin({two_pi}*2+{sgn}))",
            ["arms_out", "arms_up", "slump", "loop"], 2,
        )
        ctrl_driver(pb[f"leg.{s}"], "rotation_euler", f"{sgn}*(0.32*stance) + {sgn}*0.25*hop*abs(sin({two_pi}))", ["stance", "hop", "loop"], 2)


# ------------------------------------------------------------------- body


def make_mesh(name: str, bm: bmesh.types.BMesh) -> bpy.types.Object:
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return link(bpy.data.objects.new(name, me))


def parent_bone(obj, rig, bone):
    """Bone-parent ``obj`` without moving it.

    The world matrix of a bone child is rig @ bone @ T(0, length, 0) @
    parent_inverse @ basis. At rest pose the bone matrix is matrix_local, so
    the parent inverse is computed from data rather than from evaluated
    matrices (which are stale in background mode)."""
    from mathutils import Matrix
    # Unparented: basis == world, and unlike matrix_world it is valid before
    # the depsgraph has evaluated the new object.
    mw = obj.matrix_basis.copy()
    b = rig.data.bones[bone]
    obj.parent = rig
    obj.parent_type = "BONE"
    obj.parent_bone = bone
    obj.matrix_parent_inverse = (rig.matrix_world @ b.matrix_local @ Matrix.Translation((0, b.length, 0))).inverted()
    obj.matrix_basis = mw


def build_head(rig) -> None:
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=32, radius=1.0)
    for v in bm.verts:
        x, y, z = v.co
        # Slightly flatter on the face, fuller at the cheeks, a soft chin.
        z = z * (1.0 if z > 0 else 0.92)
        v.co = Vector((x * HEAD_R[0], y * HEAD_R[1], z * HEAD_R[2])) + HEAD_C
    head = make_mesh("Head", bm)
    for p in head.data.polygons:
        p.use_smooth = True

    m = bpy.data.materials.new("M_Head")
    m.use_nodes = True
    nt = m.node_tree
    n = nt.nodes
    bsdf = n["Principled BSDF"]
    cream = (1.0, 0.90, 0.76, 1)
    ash = (0.42, 0.40, 0.38, 1)
    mix_c = n.new("ShaderNodeMix")
    mix_c.data_type = "RGBA"
    mix_c.inputs[6].default_value = cream
    mix_c.inputs[7].default_value = ash
    ctrl_driver(mix_c.inputs[0], "default_value", "head_ash", ["head_ash"])
    nt.links.new(mix_c.outputs[2], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.55
    if "Subsurface Weight" in bsdf.inputs:
        bsdf.inputs["Subsurface Weight"].default_value = 0.25
    # The head is lit from within: a warm-white core that turns orange at the
    # silhouette (layer weight facing), which is the reference's signature.
    lw = n.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.35
    ramp = n.new("ShaderNodeValToRGB")
    el = ramp.color_ramp.elements
    el[0].position, el[0].color = 0.0, (1.0, 0.86, 0.66, 1)
    el[1].position, el[1].color = 0.9, (1.0, 0.42, 0.06, 1)
    nt.links.new(lw.outputs["Facing"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Emission Color"])
    ctrl_driver(bsdf.inputs["Emission Strength"], "default_value", "0.22*head_glow", ["head_glow"])
    head.data.materials.append(m)
    parent_bone(head, rig, "head")

    # Eyes: glossy, near-black, with an optional warm brown iris and a
    # catchlight sphere. Large and set low and wide like the reference.
    eye_mat = bpy.data.materials.new("M_Eye")
    eye_mat.use_nodes = True
    en = eye_mat.node_tree.nodes
    eb = en["Principled BSDF"]
    eb.inputs["Roughness"].default_value = 0.06
    if "Coat Weight" in eb.inputs:
        eb.inputs["Coat Weight"].default_value = 1.0
    # Iris: radial gradient around the eye's own front (object coords -Y).
    tc = en.new("ShaderNodeTexCoord")
    sep = en.new("ShaderNodeSeparateXYZ")
    eye_mat.node_tree.links.new(tc.outputs["Object"], sep.inputs[0])
    vm = en.new("ShaderNodeVectorMath")
    vm.operation = "LENGTH"
    comb = en.new("ShaderNodeCombineXYZ")
    eye_mat.node_tree.links.new(sep.outputs[0], comb.inputs[0])
    eye_mat.node_tree.links.new(sep.outputs[2], comb.inputs[1])
    eye_mat.node_tree.links.new(comb.outputs[0], vm.inputs[0])
    ir = en.new("ShaderNodeValToRGB")
    e = ir.color_ramp.elements
    e[0].position, e[0].color = 0.30, (0.012, 0.008, 0.006, 1)
    e[1].position, e[1].color = 0.62, (0.30, 0.13, 0.05, 1)
    e3 = ir.color_ramp.elements.new(0.80)
    e3.color = (0.02, 0.012, 0.01, 1)
    eye_mat.node_tree.links.new(vm.outputs["Value"], ir.inputs["Fac"])
    mixe = en.new("ShaderNodeMix")
    mixe.data_type = "RGBA"
    mixe.inputs[6].default_value = (0.012, 0.009, 0.008, 1)
    eye_mat.node_tree.links.new(ir.outputs["Color"], mixe.inputs[7])
    ctrl_driver(mixe.inputs[0], "default_value", "iris", ["iris"])
    eye_mat.node_tree.links.new(mixe.outputs[2], eb.inputs["Base Color"])

    shine = principled("M_Catchlight", (1, 1, 1), emission=(1, 0.97, 0.92), strength=6.0)
    lid_mat = m  # lids are skin of the head

    for side, sx in (("L", 1), ("R", -1)):
        piv = bpy.data.objects.new(f"EyePivot.{side}", None)
        link(piv)
        piv.location = HEAD_C + Vector((0.16 * sx, -0.262, -0.045))
        parent_bone(piv, rig, "head")
        ctrl_driver(piv, "scale", "eye_scale", ["eye_scale"], 0)
        ctrl_driver(piv, "scale", "eye_scale", ["eye_scale"], 1)
        ctrl_driver(piv, "scale", "eye_scale", ["eye_scale"], 2)

        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=24, radius=0.122)
        for v in bm.verts:
            v.co.y *= 0.70
        eye = make_mesh(f"Eye.{side}", bm)
        for p in eye.data.polygons:
            p.use_smooth = True
        eye.data.materials.append(eye_mat)
        eye.parent = piv
        # Gaze: the eyeball turns; the catchlight stays (it is a reflection).
        ctrl_driver(eye, "rotation_euler", "-0.5*look_x", ["look_x"], 2)
        ctrl_driver(eye, "rotation_euler", "0.4*look_y", ["look_y"], 0)

        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.016)
        cl = make_mesh(f"Catchlight.{side}", bm)
        cl.data.materials.append(shine)
        cl.parent = piv
        cl.location = (-0.04 * sx + 0.012, -0.082, 0.048)

        # Lids: flat plates of face colour just in front of the eye (the
        # usual way stylised characters close their eyes). The upper plate's
        # lower edge is the lid line: it slides down as eye_open falls and
        # slants with lid_tilt (inner corner down = angry, outer down = sad).
        # Two blinks per loop at blink_at / blink_at2 (frames; <0 = none).
        for lid_name, lower in (("LidUp", False), ("LidLo", True)):
            bm = bmesh.new()
            ring = []
            n = 24
            for i in range(n + 1):
                a = math.pi * i / n
                ring.append(bm.verts.new((0.132 * math.cos(a), 0, 0.132 * math.sin(a) * (-1 if lower else 1))))
            bm.faces.new(ring)
            lid = make_mesh(f"{lid_name}.{side}", bm)
            lid.data.materials.append(lid_mat)
            lid.parent = piv
            lid.rotation_mode = "XYZ"
            lid.location = (0, -0.095, 0)
            if not lower:
                blink = (
                    "max(0, 1 - abs(frame - blink_at)/2.2)*(blink_at >= 0)"
                    " + max(0, 1 - abs(frame - blink_at2)/2.2)*(blink_at2 >= 0)"
                )
                ctrl_driver(lid, "location", f"-0.128 + 0.256*eye_open*(1 - min(1, {blink}))",
                            ["eye_open", "blink_at", "blink_at2"], 2)
                ctrl_driver(lid, "rotation_euler", f"{-sx}*0.55*lid_tilt", ["lid_tilt"], 1)
                # Present only while it shows: an open eye has no plate in
                # front of it at all.
                for i in range(3):
                    ctrl_driver(lid, "scale", f"(eye_open < 0.97 or ({blink}) > 0.01)*1.0",
                                ["eye_open", "blink_at", "blink_at2"], i)
            else:
                ctrl_driver(lid, "location", "-0.128 + 0.10*eye_lower", ["eye_lower"], 2)
                for i in range(3):
                    ctrl_driver(lid, "scale", "(eye_lower > 0.01)*1.0", ["eye_lower"], i)

    # Brows: short tapered strokes, only visible when angry or sad.
    brow_mat = principled("M_Brow", (0.10, 0.05, 0.03), rough=0.8)
    for side, sx in (("L", 1), ("R", -1)):
        cu = bpy.data.curves.new(f"Brow.{side}", "CURVE")
        cu.dimensions = "3D"
        cu.bevel_depth = 0.014
        cu.bevel_resolution = 2
        sp = cu.splines.new("BEZIER")
        sp.bezier_points.add(1)
        pts = [(-0.07, 0, 0), (0.07, 0, 0)]
        for bp, co in zip(sp.bezier_points, pts):
            bp.co = co
            bp.handle_left_type = bp.handle_right_type = "AUTO"
        sp.bezier_points[0].radius = 0.5
        sp.bezier_points[1].radius = 1.2
        brow = link(bpy.data.objects.new(f"Brow.{side}", cu))
        brow.data.materials.append(brow_mat)
        brow.location = HEAD_C + Vector((0.15 * sx, -0.305, 0.115))
        brow.scale.x = -sx
        parent_bone(brow, rig, "head")
        # Angry: inner end down; sad: inner end up. Hidden (scale 0) otherwise.
        ctrl_driver(brow, "rotation_euler", f"{sx}*(-0.55*brow_angry + 0.45*brow_sad)", ["brow_angry", "brow_sad"], 1)
        for i in range(3):
            ctrl_driver(brow, "scale", f"{(-sx if i == 0 else 1)}*min(1, 2*(brow_angry + brow_sad))", ["brow_angry", "brow_sad"], i)

    build_mouth(rig)

    # Blush: soft warm discs on the cheeks.
    blush = bpy.data.materials.new("M_Blush")
    blush.use_nodes = True
    bn = blush.node_tree.nodes
    bn.remove(bn["Principled BSDF"])
    out = bn["Material Output"]
    em = bn.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (1.0, 0.32, 0.12, 1)
    em.inputs["Strength"].default_value = 1.5
    tr = bn.new("ShaderNodeBsdfTransparent")
    mx = bn.new("ShaderNodeMixShader")
    tc = bn.new("ShaderNodeTexCoord")
    grad = bn.new("ShaderNodeTexGradient")
    grad.gradient_type = "SPHERICAL"
    blush.node_tree.links.new(tc.outputs["Object"], grad.inputs["Vector"])
    mul = bn.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    blush.node_tree.links.new(grad.outputs["Fac"], mul.inputs[0])
    ctrl_driver(mul.inputs[1], "default_value", "0.8*blush", ["blush"])
    blush.node_tree.links.new(mul.outputs[0], mx.inputs["Fac"])
    blush.node_tree.links.new(tr.outputs[0], mx.inputs[1])
    blush.node_tree.links.new(em.outputs[0], mx.inputs[2])
    blush.node_tree.links.new(mx.outputs[0], out.inputs["Surface"])
    set_blend(blush)
    for side, sx in (("L", 1), ("R", -1)):
        bpy.ops.mesh.primitive_circle_add(vertices=24, radius=1.0, fill_type="NGON")
        b = bpy.context.active_object
        b.name = f"Blush.{side}"
        b.data.materials.append(blush)
        b.location = HEAD_C + Vector((0.27 * sx, -0.275, -0.12))
        b.rotation_euler = (math.pi / 2, 0, -0.55 * sx)
        b.scale = (0.075, 0.05, 1)
        parent_bone(b, rig, "head")


def build_mouth(rig) -> None:
    """A small mouth whose shape keys cover smile, frown and open/talk."""
    bm = bmesh.new()
    n = 16
    ring = []
    for i in range(n):
        a = 2 * math.pi * i / n
        ring.append(bm.verts.new((0.05 * math.cos(a), 0, 0.012 * math.sin(a))))
    bm.faces.new(ring)
    mouth = make_mesh("Mouth", bm)
    mouth.shape_key_add(name="Basis")
    keys = {}
    for name in ("smile", "open", "frown"):
        keys[name] = mouth.shape_key_add(name=name, from_mix=False)
    for i in range(n):
        a = 2 * math.pi * i / n
        x, z = math.cos(a), math.sin(a)
        # smile: corners up, centre down (a curved slit)
        keys["smile"].data[i].co = Vector((0.06 * x, 0, 0.012 * z + 0.03 * x * x - 0.012))
        # open: a D-shaped open mouth (flat top, round bottom)
        keys["open"].data[i].co = Vector((0.055 * x, 0, (0.004 if z > 0 else 0.07) * z))
        # frown: corners down
        keys["frown"].data[i].co = Vector((0.045 * x, 0, 0.008 * z - 0.022 * x * x + 0.008))
    mouth.location = HEAD_C + Vector((0.0, -0.318, -0.17))
    mouth.scale = (1.5, 1.5, 1.5)
    mouth.rotation_euler = (0.18, 0, 0)
    mat = principled("M_Mouth", (0.18, 0.03, 0.02), rough=0.6, emission=(0.6, 0.12, 0.04), strength=0.3)
    mouth.data.materials.append(mat)
    parent_bone(mouth, rig, "head")
    sk = mouth.data.shape_keys.key_blocks
    ctrl_driver(sk["smile"], "value", "mouth_smile", ["mouth_smile"])
    # Talking opens and closes at roughly syllable rate (4 per loop second).
    ctrl_driver(
        sk["open"], "value",
        "max(mouth_open, mouth_talk*(0.5 + 0.5*sin(2*pi*frame*4/24)) )",
        ["mouth_open", "mouth_talk"],
    )
    ctrl_driver(sk["frown"], "value", "mouth_frown", ["mouth_frown"])
    # Hidden entirely when every key is at rest: the idle face has no mouth.
    for i in range(3):
        ctrl_driver(
            mouth, "scale",
            "1.5*min(1, 4*(mouth_smile + mouth_open + mouth_frown + mouth_talk))",
            ["mouth_smile", "mouth_open", "mouth_frown", "mouth_talk"], i,
        )


def build_body(rig) -> None:
    """A small dark tattered robe from the neck to the knees."""
    rnd = random.Random(7)
    bm = bmesh.new()
    rings, seg = 9, 28
    verts = []
    for r in range(rings):
        t = r / (rings - 1)
        z = NECK_Z - (NECK_Z - HEM_Z) * t
        rad = 0.045 + 0.16 * (t**1.35)
        row = []
        for s in range(seg):
            a = 2 * math.pi * s / seg
            rr = rad * (1 + 0.06 * math.sin(a * 3 + r))
            zz = z
            if r == rings - 1:
                # Tatters: alternate long and short points along the hem.
                zz -= (0.16 if s % 2 == 0 else 0.03) * (0.6 + 0.8 * rnd.random())
                rr *= 1.0 + 0.15 * rnd.random()
            row.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a) * 0.8, zz)))
        verts.append(row)
    for r in range(rings - 1):
        for s in range(seg):
            a, b = verts[r][s], verts[r][(s + 1) % seg]
            c, d = verts[r + 1][(s + 1) % seg], verts[r + 1][s]
            bm.faces.new((a, b, c, d))
    robe = make_mesh("Robe", bm)
    for p in robe.data.polygons:
        p.use_smooth = True
    m = bpy.data.materials.new("M_Robe")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.055, 0.035, 0.025, 1)
    b.inputs["Roughness"].default_value = 0.9
    # Streaky fibres (the video's shaggy body) via stretched noise in Z.
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (40, 40, 3)
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 2.0
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], noise.inputs["Vector"])
    rmp = nt.nodes.new("ShaderNodeValToRGB")
    rmp.color_ramp.elements[0].color = (0.02, 0.014, 0.01, 1)
    rmp.color_ramp.elements[1].color = (0.06, 0.04, 0.028, 1)
    nt.links.new(noise.outputs["Fac"], rmp.inputs["Fac"])
    ash = nt.nodes.new("ShaderNodeMix")
    ash.data_type = "RGBA"
    nt.links.new(rmp.outputs["Color"], ash.inputs[6])
    ash.inputs[7].default_value = (0.13, 0.125, 0.12, 1)
    ctrl_driver(ash.inputs[0], "default_value", "0.8*head_ash", ["head_ash"])
    nt.links.new(ash.outputs[2], b.inputs["Base Color"])
    robe.data.materials.append(m)
    sol = robe.modifiers.new("Solidify", "SOLIDIFY")
    sol.thickness = 0.01
    parent_bone(robe, rig, "body")

    limb = principled("M_Limb", (0.06, 0.04, 0.03), rough=0.85)
    build_limb("Arm.L", rig, [(0.06, 0, 0.92), (0.20, 0, 0.76), (0.33, -0.02, 0.64)], ["arm_up.L", "arm_up.L", "arm_lo.L"], limb, fingers=True, side=1)
    build_limb("Arm.R", rig, [(-0.06, 0, 0.92), (-0.20, 0, 0.76), (-0.33, -0.02, 0.64)], ["arm_up.R", "arm_up.R", "arm_lo.R"], limb, fingers=True, side=-1)
    build_limb("Leg.L", rig, [(0.05, 0, 0.52), (0.06, 0, 0.26), (0.07, 0, 0.02), (0.11, -0.04, 0.0)], ["leg.L"] * 4, limb)
    build_limb("Leg.R", rig, [(-0.05, 0, 0.52), (-0.06, 0, 0.26), (-0.07, 0, 0.02), (-0.11, -0.04, 0.0)], ["leg.R"] * 4, limb)


def build_limb(name, rig, pts, bones, mat, fingers=False, side=1) -> None:
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in pts]
    groups = list(bones)
    for a, b in zip(vs, vs[1:]):
        bm.edges.new((a, b))
    if fingers:
        tip = Vector(pts[-1])
        for k, (dx, dz) in enumerate(((0.05, -0.03), (0.06, 0.0), (0.045, 0.03), (0.02, -0.05))):
            f = bm.verts.new(tip + Vector((dx * side, -0.01, dz)))
            bm.edges.new((vs[-1], f))
            groups.append(bones[-1])
    obj = make_mesh(name, bm)
    skin = obj.modifiers.new("Skin", "SKIN")
    sv = obj.data.skin_vertices[0].data
    for i, v in enumerate(sv):
        r = 0.018 if i < len(pts) else 0.007
        if not fingers and i == len(pts) - 1:
            r = 0.022  # foot
        v.radius = (r, r)
    sv[0].use_root = True
    for b in set(bones):
        obj.vertex_groups.new(name=b)
    for i, g in enumerate(groups):
        obj.vertex_groups[g].add([i], 1.0, "REPLACE")
    am = obj.modifiers.new("Armature", "ARMATURE")
    am.object = rig
    # Deform the chain first, then grow the tube around it.
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_move_to_index(modifier="Armature", index=0)
    obj.modifiers.new("Subsurf", "SUBSURF").levels = 1
    obj.data.materials.append(mat)
    obj.parent = rig


# ------------------------------------------------------------------ flames


def flame_material(name: str, smoke: bool = False) -> bpy.types.Material:
    """Emission along the strand: white-hot at the root, gold, then deep
    orange at the tip, fading to nothing. Smoke uses the same ramp in grey."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    n = nt.nodes
    n.remove(n["Principled BSDF"])
    out = n["Material Output"]
    attr = n.new("ShaderNodeAttribute")
    attr.attribute_name = "t"
    ramp = n.new("ShaderNodeValToRGB")
    el = ramp.color_ramp.elements
    if smoke:
        el[0].position, el[0].color = 0.0, (0.30, 0.28, 0.26, 1)
        el[1].position, el[1].color = 1.0, (0.22, 0.21, 0.20, 1)
    else:
        el[0].position, el[0].color = 0.0, (1.0, 0.80, 0.52, 1)
        e1 = ramp.color_ramp.elements.new(0.2)
        e1.color = (1.0, 0.48, 0.12, 1)
        e2 = ramp.color_ramp.elements.new(0.55)
        e2.color = (0.92, 0.30, 0.05, 1)
        el[-1].position, el[-1].color = 1.0, (0.55, 0.12, 0.02, 1)
    nt.links.new(attr.outputs["Fac"], ramp.inputs["Fac"])
    em = n.new("ShaderNodeEmission")
    nt.links.new(ramp.outputs["Color"], em.inputs["Color"])
    if smoke:
        em.inputs["Strength"].default_value = 0.35
    else:
        ctrl_driver(em.inputs["Strength"], "default_value", "0.95*flame_bright", ["flame_bright"])
    # Opacity: solid near the root, fading out towards the tip.
    a = n.new("ShaderNodeMapRange")
    a.inputs["From Min"].default_value = 0.0
    a.inputs["From Max"].default_value = 1.0
    a.inputs["To Min"].default_value = 0.7 if smoke else 0.85
    a.inputs["To Max"].default_value = 0.0
    nt.links.new(attr.outputs["Fac"], a.inputs["Value"])
    tr = n.new("ShaderNodeBsdfTransparent")
    mx = n.new("ShaderNodeMixShader")
    nt.links.new(a.outputs["Result"], mx.inputs["Fac"])
    nt.links.new(tr.outputs[0], mx.inputs[1])
    nt.links.new(em.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs["Surface"])
    set_blend(m)
    return m


def iface(ng, name, io, stype, default=None, lo=None, hi=None):
    s = ng.interface.new_socket(name=name, in_out=io, socket_type=stype)
    if default is not None:
        s.default_value = default
    if lo is not None:
        s.min_value = lo
    if hi is not None:
        s.max_value = hi
    return s


def build_flame_group() -> bpy.types.NodeTree:
    """EmberFlame: positions every strand point from its curve attributes.

    Per point:  P = root + dir*len*L*t                 (grow)
                  + up*U*t^2 + side*S*t^2              (rise, sweep)
                  + swirl(t) around the emitter axis   (swirl)
                  + noise(P0 + loop circle)*T*t^1.3    (flicker)
    The noise is sampled on a circle whose angle is 2*pi*frame/loop, so the
    flicker is exactly periodic over the clip. Radius tapers with t; strands
    whose seed exceeds Count are collapsed (so the count animates smoothly).
    """
    ng = bpy.data.node_groups.new("EmberFlame", "GeometryNodeTree")
    iface(ng, "Geometry", "INPUT", "NodeSocketGeometry")
    iface(ng, "Geometry", "OUTPUT", "NodeSocketGeometry")
    for name, d in (
        ("Length", 1.0), ("Up", 0.35), ("Sweep", 0.25), ("Turbulence", 0.35),
        ("Count", 1.0), ("Swirl", 0.0), ("Phase", 0.0), ("Width", 1.0), ("Wobble", 1.0),
    ):
        iface(ng, name, "INPUT", "NodeSocketFloat", d)
    N = ng.nodes
    L = ng.links

    def node(t, **kw):
        nd = N.new(t)
        for k, v in kw.items():
            setattr(nd, k, v)
        return nd

    gi = node("NodeGroupInput")
    go = node("NodeGroupOutput")

    def named(name, dtype="FLOAT_VECTOR"):
        nd = node("GeometryNodeInputNamedAttribute", data_type=dtype)
        nd.inputs["Name"].default_value = name
        return nd.outputs["Attribute"]

    def math(op, a, b=None, c=None):
        nd = node("ShaderNodeMath", operation=op)
        for i, v in enumerate((a, b, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                nd.inputs[i].default_value = v
            else:
                L.new(v, nd.inputs[i])
        return nd.outputs[0]

    def vmath(op, a, b=None, scale=None):
        nd = node("ShaderNodeVectorMath", operation=op)
        if a is not None:
            L.new(a, nd.inputs[0])
        if b is not None:
            if isinstance(b, (tuple, list)):
                nd.inputs[1].default_value = b
            else:
                L.new(b, nd.inputs[1])
        if scale is not None:
            if isinstance(scale, (int, float)):
                nd.inputs["Scale"].default_value = scale
            else:
                L.new(scale, nd.inputs["Scale"])
        out = nd.outputs["Vector"] if op != "LENGTH" else nd.outputs["Value"]
        return out

    def combine(x, y, z):
        nd = node("ShaderNodeCombineXYZ")
        for i, v in enumerate((x, y, z)):
            if isinstance(v, (int, float)):
                nd.inputs[i].default_value = v
            else:
                L.new(v, nd.inputs[i])
        return nd.outputs[0]

    t = node("GeometryNodeSplineParameter").outputs["Factor"]
    root = named("root")
    dirv = named("dir")
    seed = named("seed", "FLOAT")
    ln = named("len", "FLOAT")
    side = named("side")
    t2 = math("POWER", t, 2.0)

    grow = vmath("SCALE", dirv, scale=math("MULTIPLY", math("MULTIPLY", ln, gi.outputs["Length"]), t))
    rise = vmath("SCALE", None, scale=math("MULTIPLY", math("MULTIPLY", gi.outputs["Up"], ln), t2))
    L.new(combine(0, 0, 1), rise.node.inputs[0])
    sweep = vmath("SCALE", side, scale=math("MULTIPLY", math("MULTIPLY", gi.outputs["Sweep"], ln), t2))

    # Loop phase: angle on the noise circle.
    scene_t = node("GeometryNodeInputSceneTime").outputs["Frame"]
    ang = math("ADD", math("MULTIPLY", math("DIVIDE", scene_t, gi.outputs["Phase"]), 2 * 3.14159265), math("MULTIPLY", seed, 6.283))
    circ = combine(math("COSINE", ang), math("SINE", ang), math("MULTIPLY", seed, 7.0))
    p0 = vmath("ADD", vmath("SCALE", root, scale=2.5), vmath("SCALE", circ, scale=0.8))
    p0 = vmath("ADD", p0, vmath("SCALE", combine(0, 0, t), scale=gi.outputs["Wobble"]))
    noise = node("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 1.6
    noise.inputs["Detail"].default_value = 2.0
    L.new(p0, noise.inputs["Vector"])
    nvec = vmath("SUBTRACT", noise.outputs["Color"], (0.5, 0.5, 0.5))
    flick = vmath("SCALE", nvec, scale=math("MULTIPLY", math("MULTIPLY", gi.outputs["Turbulence"], math("POWER", t, 1.3)), math("MULTIPLY", ln, 5.0)))

    # Swirl: rotate the grown offset around Z by an angle growing with t.
    pos = vmath("ADD", vmath("ADD", vmath("ADD", root, grow), rise), sweep)
    rel = vmath("SUBTRACT", pos, named("center"))
    rot = node("ShaderNodeVectorRotate", rotation_type="Z_AXIS")
    L.new(rel, rot.inputs["Vector"])
    L.new(math("MULTIPLY", math("MULTIPLY", gi.outputs["Swirl"], t), math("ADD", 2.2, math("MULTIPLY", scene_t, 0))), rot.inputs["Angle"])
    pos = vmath("ADD", named("center"), rot.outputs["Vector"])
    pos = vmath("ADD", pos, flick)

    alive = math("LESS_THAN", seed, gi.outputs["Count"])
    sp = node("GeometryNodeSetPosition")
    L.new(gi.outputs["Geometry"], sp.inputs["Geometry"])
    L.new(pos, sp.inputs["Position"])

    rad = node("GeometryNodeSetCurveRadius")
    L.new(sp.outputs["Geometry"], rad.inputs["Curve"])
    taper = math("MULTIPLY", math("POWER", math("SUBTRACT", 1.0, t), 0.8), math("MULTIPLY", named("width", "FLOAT"), gi.outputs["Width"]))
    taper = math("MULTIPLY", taper, alive)
    L.new(taper, rad.inputs["Radius"])

    st = node("GeometryNodeStoreNamedAttribute", data_type="FLOAT", domain="POINT")
    st.inputs["Name"].default_value = "t"
    L.new(rad.outputs["Curve"], st.inputs["Geometry"])
    L.new(t, st.inputs["Value"])

    prof = node("GeometryNodeCurvePrimitiveCircle")
    prof.inputs["Resolution"].default_value = 6
    prof.inputs["Radius"].default_value = 1.0
    c2m = node("GeometryNodeCurveToMesh")
    L.new(st.outputs["Geometry"], c2m.inputs["Curve"])
    L.new(prof.outputs["Curve"], c2m.inputs["Profile Curve"])
    if "Scale" in c2m.inputs:
        # Blender 4.2+: the profile is scaled by this field; feed the radius.
        rr = node("GeometryNodeInputRadius")
        L.new(rr.outputs[0], c2m.inputs["Scale"])
    # The material comes from the object's own slot (index 0).
    shade = node("GeometryNodeSetShadeSmooth")
    L.new(c2m.outputs["Mesh"], shade.inputs["Geometry"])
    L.new(shade.outputs["Geometry"], go.inputs["Geometry"])
    return ng


def make_strands(name, specs, mat, ng, rig, bone, props: dict, phase_div: int = 1):
    """Create a Curves object with one strand per spec.

    spec: dict(root, dir, side, len, width, seed, center). The geometry stored
    is a placeholder line; the node group computes the real positions."""
    K = 14
    cv = bpy.data.hair_curves.new(name)
    cv.add_curves([K] * len(specs))
    for attr, dt in (("root", "FLOAT_VECTOR"), ("dir", "FLOAT_VECTOR"), ("side", "FLOAT_VECTOR"),
                     ("center", "FLOAT_VECTOR"), ("len", "FLOAT"), ("width", "FLOAT"), ("seed", "FLOAT")):
        cv.attributes.new(attr, dt, "POINT")
    pos = cv.position_data
    i = 0
    for s in specs:
        for k in range(K):
            t = k / (K - 1)
            p = Vector(s["root"]) + Vector(s["dir"]) * s["len"] * t
            pos[i].vector = p
            cv.attributes["root"].data[i].vector = s["root"]
            cv.attributes["dir"].data[i].vector = s["dir"]
            cv.attributes["side"].data[i].vector = s["side"]
            cv.attributes["center"].data[i].vector = s["center"]
            cv.attributes["len"].data[i].value = s["len"]
            cv.attributes["width"].data[i].value = s["width"]
            cv.attributes["seed"].data[i].value = s["seed"]
            i += 1
    cv.materials.append(mat)
    obj = link(bpy.data.objects.new(name, cv))
    mod = obj.modifiers.new("EmberFlame", "NODES")
    mod.node_group = ng
    ids = {it.name: it.identifier for it in ng.interface.items_tree if getattr(it, "in_out", "") == "INPUT"}
    for sock, (expr, vars_) in props.items():
        ctrl_driver(*mod_input(mod, ng, sock), expr, vars_)
    # Noise period = clip loop length (exact seamless loop).
    ctrl_driver(*mod_input(mod, ng, "Phase"), f"loop/{phase_div}", ["loop"])
    # Strands are authored in world space; keep them where they are while the
    # bone carries them.
    parent_bone(obj, rig, bone)
    return obj


def head_flame_specs(rnd: random.Random) -> list[dict]:
    """Strands rooted over the back and crown of the head, fanning out
    sideways like a mane (idle) - the node group lifts them upward for the
    other states. A few long plume strands carry the tall curl."""
    specs = []
    n = 110
    for i in range(n):
        # Roots just inside the head silhouette, behind the face, so every
        # wisp appears to leave the edge of the head.
        a = rnd.uniform(-math.pi * 0.92, math.pi * 0.92)  # 0 = top, +-pi = chin
        x = math.sin(a) * HEAD_R[0] * 0.9
        z = math.cos(a) * HEAD_R[2] * 0.9
        y = HEAD_R[1] * rnd.uniform(0.05, 0.5)
        root = HEAD_C + Vector((x, y, z))
        # Outward from the ellipse, tilted up; the lower sides spread
        # horizontally like the reference's mane.
        out = Vector((math.sin(a) * 1.3, 0.1, math.cos(a) + 0.35)).normalized()
        # Curl: perpendicular to the strand in the picture plane, random
        # sign and strength, plus a steady drift to the upper right.
        perp = Vector((-out.z, 0, out.x)) * rnd.choice((-1, 1)) * rnd.uniform(0.3, 1.0)
        side = perp + Vector((0.45, 0, 0.1))
        lower = abs(a) > 1.2
        # The mane: side wisps reach well past the head (about 2.3 head
        # widths across in the reference); crown wisps stay shorter.
        ln = rnd.uniform(0.12, 0.30) * (2.0 if lower else 1.0)
        specs.append(dict(root=root, dir=out, side=side, center=HEAD_C, len=ln,
                          width=rnd.uniform(0.016, 0.042), seed=rnd.random()))
    # The plume: a loose bundle of longer strokes from the crown that leans
    # and curls to one side.
    for i in range(18):
        root = HEAD_C + Vector((rnd.uniform(-0.18, 0.12), HEAD_R[1] * 0.4, HEAD_R[2] * 0.8))
        out = Vector((rnd.uniform(-0.1, 0.45), 0.1, 1.0)).normalized()
        specs.append(dict(root=root, dir=out, side=Vector((rnd.uniform(0.5, 1.3), 0, -0.35)), center=HEAD_C,
                          len=rnd.uniform(0.35, 0.65), width=rnd.uniform(0.01, 0.022), seed=rnd.random() * 0.7))
    return specs


def small_flame_specs(rnd, center: Vector, n: int, ln=(0.06, 0.14), up=0.7) -> list[dict]:
    specs = []
    for i in range(n):
        a = rnd.uniform(0, 2 * math.pi)
        d = Vector((math.cos(a) * 0.6, math.sin(a) * 0.3, up + rnd.uniform(0, 0.4))).normalized()
        specs.append(dict(root=center + d * 0.015, dir=d, side=Vector((0.3, 0, 0)), center=center,
                          len=rnd.uniform(*ln), width=rnd.uniform(0.012, 0.025), seed=rnd.random()))
    return specs


def build_flames(rig) -> None:
    rnd = random.Random(20261014)
    ng = build_flame_group()
    fire = flame_material("M_Flame")
    smoke = flame_material("M_Smoke", smoke=True)

    make_strands("Flames.Head", head_flame_specs(rnd), fire, ng, rig, "head", {
        "Length": ("flame_len", ["flame_len"]),
        "Up": ("0.3 + 1.1*flame_up", ["flame_up"]),
        "Sweep": ("0.35 + 1.4*flame_sweep", ["flame_sweep"]),
        "Turbulence": ("flame_turb", ["flame_turb"]),
        "Count": ("flame_count", ["flame_count"]),
        "Swirl": ("1.4*flame_swirl", ["flame_swirl"]),
        "Width": ("0.6 + 0.4*flame_bright", ["flame_bright"]),
    })
    # Smoke rises from the crown when the fire is low.
    smoke_specs = []
    for i in range(6):
        root = HEAD_C + Vector((rnd.uniform(-0.2, 0.2), 0.1, HEAD_R[2] * 0.8))
        smoke_specs.append(dict(root=root, dir=Vector((rnd.uniform(-0.3, 0.3), 0, 1)).normalized(),
                                side=Vector((0.2, 0, 0)), center=root, len=rnd.uniform(0.6, 1.0),
                                width=rnd.uniform(0.035, 0.06), seed=rnd.random()))
    make_strands("Smoke.Head", smoke_specs, smoke, ng, rig, "head", {
        "Length": ("smoke", ["smoke"]),
        "Turbulence": ("0.9", []),
        "Count": ("smoke*1.01", ["smoke"]),
        "Width": ("smoke", ["smoke"]),
        "Up": ("0.1", []),
        "Sweep": ("0", []),
    })
    for side, sx in (("L", 1), ("R", -1)):
        hand = Vector((0.36 * sx, -0.04, 0.63))
        make_strands(f"Flames.Hand.{side}", small_flame_specs(rnd, hand, 22), fire, ng, rig, f"arm_lo.{side}", {
            "Length": ("0.6*hand_fire + 2.4*hand_fire*hand_swirl", ["hand_fire", "hand_swirl"]),
            "Count": ("min(1, 3*hand_fire)", ["hand_fire"]),
            "Swirl": ("6*hand_swirl", ["hand_swirl"]),
            "Turbulence": ("0.5 + 0.5*hand_swirl", ["hand_swirl"]),
            "Width": ("0.8 + 1.6*hand_swirl", ["hand_swirl"]),
            "Up": ("0.2", []),
            "Sweep": ("0", []),
        }, phase_div=2)
    # Tail: a curl of flame that wraps beside the body, low on the left.
    tail = []
    base = Vector((-0.16, 0.05, 0.55))
    for i in range(10):
        a = 1.2 + i * 0.03
        d = Vector((-math.cos(a), 0.0, math.sin(a) * 0.4 - 0.2)).normalized()
        tail.append(dict(root=base + Vector((0, 0, i * 0.008)), dir=d, side=Vector((0, 0, 0)), center=base + Vector((-0.2, 0, 0.0)),
                         len=rnd.uniform(0.28, 0.42), width=rnd.uniform(0.015, 0.03), seed=rnd.random()))
    make_strands("Flames.Tail", tail, fire, ng, rig, "body", {
        "Length": ("tail_fire", ["tail_fire"]),
        "Count": ("tail_fire*1.01", ["tail_fire"]),
        "Swirl": ("2.6", []),
        "Up": ("0.35", []),
        "Sweep": ("0", []),
        "Turbulence": ("0.4", []),
        "Width": ("tail_fire", ["tail_fire"]),
    })


def build_embers() -> None:
    """Sparks drifting up through the frame on exactly periodic paths."""
    rnd = random.Random(99)
    n = 80
    me = bpy.data.meshes.new("Embers")
    me.from_pydata([(rnd.uniform(-0.9, 0.9), rnd.uniform(-0.3, 0.3), rnd.uniform(0.2, 2.6)) for _ in range(n)], [], [])
    sd = me.attributes.new("seed", "FLOAT", "POINT")
    for i in range(n):
        sd.data[i].value = rnd.random()
    obj = link(bpy.data.objects.new("Embers", me))
    ng = bpy.data.node_groups.new("EmberSparks", "GeometryNodeTree")
    iface(ng, "Geometry", "INPUT", "NodeSocketGeometry")
    iface(ng, "Geometry", "OUTPUT", "NodeSocketGeometry")
    iface(ng, "Amount", "INPUT", "NodeSocketFloat", 0.25)
    iface(ng, "Speed", "INPUT", "NodeSocketFloat", 1.0)
    iface(ng, "Loop", "INPUT", "NodeSocketFloat", 48.0)
    N, Lk = ng.nodes, ng.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")

    def m(op, a, b):
        nd = N.new("ShaderNodeMath")
        nd.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                nd.inputs[i].default_value = v
            else:
                Lk.new(v, nd.inputs[i])
        return nd.outputs[0]

    seed = N.new("GeometryNodeInputNamedAttribute")
    seed.data_type = "FLOAT"
    seed.inputs["Name"].default_value = "seed"
    s = seed.outputs["Attribute"]
    pos = N.new("GeometryNodeInputPosition").outputs[0]
    sep = N.new("ShaderNodeSeparateXYZ")
    Lk.new(pos, sep.inputs[0])
    frame = N.new("GeometryNodeInputSceneTime").outputs["Frame"]
    # Rise: z = 0.2 + ((z0 + cycles*frame/loop*H) mod H). An integer number of
    # cycles per loop keeps it periodic; Speed picks 1, 2 or 3 cycles.
    H = 2.4
    cycles = m("MAXIMUM", m("ROUND", gi.outputs["Speed"], 0), 1)
    prog = m("MULTIPLY", m("DIVIDE", frame, gi.outputs["Loop"]), m("MULTIPLY", cycles, H))
    z = m("ADD", 0.2, m("FLOORED_MODULO", m("ADD", sep.outputs["Z"], prog), H))
    ang = m("MULTIPLY", m("ADD", m("DIVIDE", frame, gi.outputs["Loop"]), s), 6.2832)
    x = m("ADD", sep.outputs["X"], m("MULTIPLY", m("SINE", ang, None), 0.06))
    comb = N.new("ShaderNodeCombineXYZ")
    Lk.new(x, comb.inputs[0])
    Lk.new(sep.outputs["Y"], comb.inputs[1])
    Lk.new(z, comb.inputs[2])
    sp = N.new("GeometryNodeSetPosition")
    Lk.new(gi.outputs["Geometry"], sp.inputs["Geometry"])
    Lk.new(comb.outputs[0], sp.inputs["Position"])
    # Only `Amount` of the sparks exist; they shrink as they rise.
    alive = m("LESS_THAN", s, gi.outputs["Amount"])
    size = m("MULTIPLY", m("MULTIPLY", alive, m("SUBTRACT", 1.0, m("DIVIDE", m("SUBTRACT", z, 0.2), H))), 0.012)
    ico = N.new("GeometryNodeMeshIcoSphere")
    ico.inputs["Radius"].default_value = 1.0
    ico.inputs["Subdivisions"].default_value = 1
    inst = N.new("GeometryNodeInstanceOnPoints")
    Lk.new(sp.outputs["Geometry"], inst.inputs["Points"])
    Lk.new(ico.outputs["Mesh"], inst.inputs["Instance"])
    Lk.new(size, inst.inputs["Scale"])
    real = N.new("GeometryNodeRealizeInstances")
    Lk.new(inst.outputs["Instances"], real.inputs["Geometry"])
    Lk.new(real.outputs["Geometry"], go.inputs["Geometry"])
    mod = obj.modifiers.new("EmberSparks", "NODES")
    mod.node_group = ng
    ids = {it.name: it.identifier for it in ng.interface.items_tree if getattr(it, "in_out", "") == "INPUT"}
    me.materials.append(principled("M_Spark", (1, 0.6, 0.2), emission=(1.0, 0.62, 0.22), strength=12.0))
    ctrl_driver(*mod_input(mod, ng, "Amount"), "embers", ["embers"])
    ctrl_driver(*mod_input(mod, ng, "Speed"), "ember_speed", ["ember_speed"])
    ctrl_driver(*mod_input(mod, ng, "Loop"), "loop", ["loop"])


# ------------------------------------------------------------- lighting


def build_lighting(rig) -> None:
    sc = bpy.context.scene
    # The head flame lights the body: a warm point light just above and
    # behind the head, following it.
    for name, loc, energy, color, size in (
        ("Light.Flame", HEAD_C + Vector((0, 0.3, 0.35)), 60.0, (1.0, 0.55, 0.2), 0.4),
        ("Light.FlameFront", HEAD_C + Vector((0, -0.9, 0.5)), 10.0, (1.0, 0.75, 0.5), 0.6),
        ("Light.HandL", Vector((0.34, -0.25, 0.64)), 1.5, (1.0, 0.5, 0.15), 0.1),
        ("Light.HandR", Vector((-0.34, -0.25, 0.64)), 1.5, (1.0, 0.5, 0.15), 0.1),
    ):
        ld = bpy.data.lights.new(name, "POINT")
        ld.energy = energy
        ld.color = color
        ld.shadow_soft_size = size
        lo = link(bpy.data.objects.new(name, ld))
        lo.location = loc
        if "Hand" in name:
            ctrl_driver(ld, "energy", f"{energy}*(0.3 + 3*hand_fire)", ["hand_fire"])
            parent_bone(lo, rig, f"arm_lo.{name[-1]}")
        else:
            ctrl_driver(ld, "energy", f"{energy}*(0.15 + head_glow*flame_bright)", ["head_glow", "flame_bright"])
            parent_bone(lo, rig, "head")
    # Ground: a soft pool of warm light under the feet (sprite includes it).
    gm = bpy.data.materials.new("M_GroundGlow")
    gm.use_nodes = True
    n = gm.node_tree.nodes
    n.remove(n["Principled BSDF"])
    tc = n.new("ShaderNodeTexCoord")
    gr = n.new("ShaderNodeTexGradient")
    gr.gradient_type = "SPHERICAL"
    gm.node_tree.links.new(tc.outputs["Object"], gr.inputs["Vector"])
    em = n.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (1.0, 0.55, 0.22, 1)
    ctrl_driver(em.inputs["Strength"], "default_value", "0.25 + 0.6*head_glow*flame_bright", ["head_glow", "flame_bright"])
    tr = n.new("ShaderNodeBsdfTransparent")
    mx = n.new("ShaderNodeMixShader")
    pw = n.new("ShaderNodeMath")
    pw.operation = "POWER"
    pw.inputs[1].default_value = 2.0
    gm.node_tree.links.new(gr.outputs["Fac"], pw.inputs[0])
    gm.node_tree.links.new(pw.outputs[0], mx.inputs["Fac"])
    gm.node_tree.links.new(tr.outputs[0], mx.inputs[1])
    gm.node_tree.links.new(em.outputs[0], mx.inputs[2])
    gm.node_tree.links.new(mx.outputs[0], n["Material Output"].inputs["Surface"])
    set_blend(gm)
    bpy.ops.mesh.primitive_circle_add(vertices=48, radius=1.0, fill_type="NGON", location=(0, 0, 0.002))
    g = bpy.context.active_object
    g.name = "GroundGlow"
    g.scale = (0.75, 0.35, 1)
    g.data.materials.append(gm)


def build_aura(rig) -> None:
    """The warm glow mass around the head that the reference paints: a
    camera-facing disc behind the head with a radial emission falloff."""
    m = bpy.data.materials.new("M_Aura")
    m.use_nodes = True
    n = m.node_tree.nodes
    n.remove(n["Principled BSDF"])
    tc = n.new("ShaderNodeTexCoord")
    gr = n.new("ShaderNodeTexGradient")
    gr.gradient_type = "SPHERICAL"
    m.node_tree.links.new(tc.outputs["Object"], gr.inputs["Vector"])
    ramp = n.new("ShaderNodeValToRGB")
    el = ramp.color_ramp.elements
    el[0].position, el[0].color = 0.0, (0.85, 0.30, 0.04, 1)
    el[1].position, el[1].color = 0.75, (1.0, 0.78, 0.45, 1)
    m.node_tree.links.new(gr.outputs["Fac"], ramp.inputs["Fac"])
    em = n.new("ShaderNodeEmission")
    m.node_tree.links.new(ramp.outputs["Color"], em.inputs["Color"])
    ctrl_driver(em.inputs["Strength"], "default_value", "0.8*head_glow*flame_bright", ["head_glow", "flame_bright"])
    pw = n.new("ShaderNodeMath")
    pw.operation = "POWER"
    pw.inputs[1].default_value = 1.6
    m.node_tree.links.new(gr.outputs["Fac"], pw.inputs[0])
    k = n.new("ShaderNodeMath")
    k.operation = "MULTIPLY"
    m.node_tree.links.new(pw.outputs[0], k.inputs[0])
    ctrl_driver(k.inputs[1], "default_value", "min(1, 0.9*flame_len*head_glow)", ["flame_len", "head_glow"])
    tr = n.new("ShaderNodeBsdfTransparent")
    mx = n.new("ShaderNodeMixShader")
    m.node_tree.links.new(k.outputs[0], mx.inputs["Fac"])
    m.node_tree.links.new(tr.outputs[0], mx.inputs[1])
    m.node_tree.links.new(em.outputs[0], mx.inputs[2])
    m.node_tree.links.new(mx.outputs[0], n["Material Output"].inputs["Surface"])
    set_blend(m)
    bpy.ops.mesh.primitive_circle_add(vertices=48, radius=1.0, fill_type="NGON")
    o = bpy.context.active_object
    o.name = "Aura"
    o.data.materials.append(m)
    o.location = HEAD_C + Vector((0, 0.45, 0.06))
    o.rotation_euler = (math.radians(83), 0, 0)
    o.scale = (0.95, 0.80, 1)
    parent_bone(o, rig, "head")


def build_camera() -> None:
    sc = bpy.context.scene
    cam = bpy.data.cameras.new("EmberCam")
    cam.type = "ORTHO"
    cam.ortho_scale = 2.9
    co = link(bpy.data.objects.new("EmberCam", cam))
    # A slight high angle, as in the reference: the ground pool reads as an
    # ellipse and the head sits a little over the body.
    co.location = (0, -8, 1.12 + 8 * math.tan(math.radians(7)))
    co.rotation_euler = (math.radians(83), 0, 0)
    sc.camera = co


def build_render_settings() -> None:
    sc = bpy.context.scene
    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            sc.render.engine = eng
            break
        except TypeError:
            continue
    sc.render.film_transparent = True
    sc.render.resolution_x = 448
    sc.render.resolution_y = 480
    sc.render.fps = STATES["fps"]
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    # Standard keeps flame orange saturated; AgX/Filmic roll bright orange
    # to white, which the reference never does.
    sc.view_settings.view_transform = "Standard"
    ee = sc.eevee
    if hasattr(ee, "taa_render_samples"):
        ee.taa_render_samples = 32
    w = bpy.data.worlds.new("EmberWorld")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.02, 0.015, 0.012, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.3
    # A dim neutral key from the front and above, independent of the fire, so
    # the figure is still readable when the flame is out (Depleted).
    kd = bpy.data.lights.new("Light.Key", "AREA")
    kd.energy = 45.0
    kd.size = 3.0
    kd.color = (0.85, 0.82, 0.8)
    ko = link(bpy.data.objects.new("Light.Key", kd))
    ko.location = (0.8, -4.0, 3.2)
    ko.rotation_euler = (math.radians(62), 0, math.radians(12))
    sc.world = w


def build_actions(ctrl) -> None:
    """One action per clip keying every control at frame 1 (constant), named
    EMBER_<clip>. The render script applies the same values directly; the
    actions exist so an artist can audition the clips inside Blender."""
    d = STATES["defaults"]
    for clip, vals in STATES["clips"].items():
        base = dict(d)
        if "base" in vals:
            base.update({k: v for k, v in STATES["clips"][vals["base"]].items() if k in d})
        base.update({k: v for k, v in vals.items() if k in d})
        act = bpy.data.actions.new(f"EMBER_{clip}")
        act.use_fake_user = True
        ctrl.animation_data_create()
        ctrl.animation_data.action = act
        for k, v in base.items():
            ctrl[k] = float(v)
            ctrl.keyframe_insert(data_path=f'["{k}"]', frame=1)
    ctrl.animation_data.action = None
    for k, v in d.items():
        ctrl[k] = float(v)


def main() -> None:
    a = args()
    reset_scene()
    ctrl = build_controls()
    rig = build_rig()
    drive_rig(rig)
    build_head(rig)
    build_body(rig)
    build_flames(rig)
    build_aura(rig)
    build_embers()
    build_lighting(rig)
    build_camera()
    build_render_settings()
    build_actions(ctrl)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, int(STATES["defaults"]["loop"])
    out = Path(a["out"])
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True)
    print(f"EMBER_BUILD_OK {out}")


if __name__ == "__main__":
    main()
