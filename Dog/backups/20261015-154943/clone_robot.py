"""
clone_robot.py
==============
Clones a rigged robot inside a .blend file:
  * duplicates the armature, skinned meshes, shape keys, modifiers,
    constraints, drivers, NLA tracks and actions
  * duplicates every material so the clone can be recolored independently
  * recolors the clone (Principled BSDF Base Color, or Multiply over a texture)
  * speeds up the cloned animation by a given factor
  * optionally exports ONLY the clone to .glb

Compatible with Blender 4.x AND 5.x (handles the new slotted-Action API).

Background usage
----------------
blender --background path/to/robot.blend --python clone_robot.py -- ^
    --gltf-json path/to/structure.json ^
    --clone-name RedBot ^
    --color "#FF5500" ^
    --speed 2.0 ^
    --export C:/path/RedBot.glb
"""

import bpy
import sys
import os
import json
import argparse
import math


# ================================================================== #
# CLI
# ================================================================== #
def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser(
        description="Clone robot with recolored materials + sped-up animation")
    p.add_argument("--blend",      type=str, default=None, help="Optional .blend path")
    p.add_argument("--gltf-json",  type=str, default=None, help="Optional glTF JSON")
    p.add_argument("--clone-name", type=str, default="RobotClone")
    p.add_argument("--color",      type=str, default=None,
                   help="'#RRGGBB', '#RRGGBBAA' or 'r,g,b[,a]'")
    p.add_argument("--speed",      type=float, default=1.0,
                   help="Animation speed factor (>1 = faster)")
    p.add_argument("--export",     type=str, default=None, help="Path for .glb export")
    p.add_argument("--root",       type=str, default=None, help="Explicit root object")
    p.add_argument("--collection", type=str, default=None, help="Explicit source collection")
    return p.parse_args(argv)


def log(*a):
    print("[clone_robot]", *a, flush=True)


def parse_color(s):
    if s is None:
        return None
    s = s.strip()
    if s.startswith("#"):
        h = s[1:]
        if len(h) == 6:
            return (int(h[0:2], 16) / 255.0,
                    int(h[2:4], 16) / 255.0,
                    int(h[4:6], 16) / 255.0, 1.0)
        if len(h) == 8:
            return (int(h[0:2], 16) / 255.0,
                    int(h[2:4], 16) / 255.0,
                    int(h[4:6], 16) / 255.0,
                    int(h[6:8], 16) / 255.0)
        raise ValueError(f"Bad hex color: {s}")
    vals = [float(x.strip()) for x in s.split(",")]
    if len(vals) == 3:
        return (vals[0], vals[1], vals[2], 1.0)
    if len(vals) == 4:
        return tuple(vals)
    raise ValueError(f"Bad color: {s}")


# ================================================================== #
# Blender 4.4+ / 5.x action compatibility helpers
# ================================================================== #
def action_fcurves(action):
    """
    Return a flat list of every F-Curve in an Action.

    Works across:
      * Legacy API (< Blender 4.4):  action.fcurves
      * Slotted API (4.4+ / 5.x):    action.layers[*].strips[*]
                                       .channelbags[*].fcurves
                                       (or .channelbag)
    """
    if action is None:
        return []

    curves = []

    # ---- Legacy path ------------------------------------------------
    legacy = getattr(action, "fcurves", None)
    if legacy is not None:
        try:
            curves.extend(list(legacy))
        except Exception as e:
            log(f"  (legacy fcurves read failed on '{action.name}': {e})")

    # ---- Slotted path ----------------------------------------------
    layers = getattr(action, "layers", None)
    if not layers:
        return curves

    for layer in layers:
        strips = getattr(layer, "strips", None)
        if not strips:
            continue
        for strip in strips:
            # 4.4+: collection of channelbags (one per slot)
            bags = getattr(strip, "channelbags", None)
            if bags:
                try:
                    for cb in bags:
                        f = getattr(cb, "fcurves", None)
                        if f:
                            curves.extend(list(f))
                except Exception as e:
                    log(f"  (channelbags read failed on '{action.name}': {e})")

            # Some 4.4/5.x builds expose a singular channelbag per strip
            singular = getattr(strip, "channelbag", None)
            if singular is not None:
                f = getattr(singular, "fcurves", None)
                if f:
                    curves.extend(list(f))

    return curves


def action_frame_range(action):
    """Robust frame range that works whether or not action.frame_range is populated."""
    if action is None:
        return (0.0, 0.0)

    # Try the native range first (works fine when populated)
    try:
        fr = action.frame_range
        if fr is not None and len(fr) == 2:
            lo, hi = float(fr[0]), float(fr[1])
            # Sometimes returns (0,0) for slotted actions with no assigned slot — ignore those
            if lo != 0.0 or hi != 0.0:
                return (lo, hi)
    except Exception:
        pass

    # Fallback: scan keyframes ourselves
    lo, hi = None, None
    for fc in action_fcurves(action):
        for kp in fc.keyframe_points:
            x = float(kp.co[0])
            if lo is None or x < lo:
                lo = x
            if hi is None or x > hi:
                hi = x
    if lo is None:
        return (0.0, 0.0)
    return (lo, hi)


def retime_action(action, frame_scale):
    """Multiply every keyframe time and handle X-position by frame_scale."""
    n_curves = 0
    n_keys = 0
    for fc in action_fcurves(action):
        n_curves += 1
        for kp in fc.keyframe_points:
            kp.co[0]           *= frame_scale
            kp.handle_left[0]  *= frame_scale
            kp.handle_right[0] *= frame_scale
            n_keys += 1
        try:
            fc.update()
        except Exception:
            pass
    return n_curves, n_keys


# ================================================================== #
# Discovery
# ================================================================== #
def collect_descendants(roots):
    seen, stack = set(), list(roots)
    while stack:
        o = stack.pop()
        if o in seen:
            continue
        seen.add(o)
        stack.extend(o.children)
    return list(seen)


def find_source(args):
    """Return (collection, objects, armature)."""
    coll = None
    if args.collection:
        coll = bpy.data.collections.get(args.collection)
    if coll is None:
        coll = bpy.data.collections.get("Collection")
    if coll is None:
        for c in bpy.data.collections:
            for o in c.objects:
                if o.type == 'ARMATURE':
                    coll = c
                    break
            if coll:
                break
    if coll is None:
        coll = bpy.context.scene.collection

    arm = None
    if args.root:
        r = bpy.data.objects.get(args.root)
        if r:
            if r.type == 'ARMATURE':
                arm = r
            else:
                for o in collect_descendants([r]):
                    if o.type == 'ARMATURE':
                        arm = o
                        break
    if arm is None:
        arm = bpy.data.objects.get("AICA_RIG")
    if arm is None:
        for o in bpy.data.objects:
            if o.type == 'ARMATURE':
                arm = o
                break

    if args.root and bpy.data.objects.get(args.root):
        objs = collect_descendants([bpy.data.objects[args.root]])
    else:
        objs = list(coll.objects)
        if arm is not None:
            objs = list({*objs, *collect_descendants([arm])})
    return coll, objs, arm


# ================================================================== #
# Main
# ================================================================== #
def main():
    if "--pug-build" in sys.argv:
        parser = argparse.ArgumentParser(description="Replace prototype with seated pug avatar")
        parser.add_argument("--pug-build", action="store_true")
        parser.add_argument("--output-blend", required=True)
        parser.add_argument("--render", default=None)
        options = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from pug_avatar_builder import build
        build(options.output_blend, options.render)
        return
    if "--khmer-build" in sys.argv:
        parser = argparse.ArgumentParser(description="Build reference-inspired Khmer receptionist robot")
        parser.add_argument("--khmer-build", action="store_true")
        parser.add_argument("--output-blend", required=True)
        parser.add_argument("--render", default=None)
        options = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from khmer_robot_builder import build
        build(options.output_blend, options.render)
        return
    args = parse_args()
    log("Args:", vars(args))

    if args.blend:
        log(f"Opening {args.blend}")
        bpy.ops.wm.open_mainfile(filepath=args.blend)

    if bpy.context.mode != 'OBJECT':
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except Exception:
            pass

    speed_factor = max(0.0001, float(args.speed))
    frame_scale  = 1.0 / speed_factor
    new_color    = parse_color(args.color)

    src_coll, src_objs, src_arm = find_source(args)
    log(f"Source collection : {src_coll.name if src_coll else None}")
    log(f"Source objects    : {len(src_objs)}")
    log(f"Source armature   : {src_arm.name if src_arm else None}")

    if not src_objs:
        log("ERROR: no source objects found — aborting.")
        return

    # ------------------------------------------------------------------
    # Idempotent cleanup
    # ------------------------------------------------------------------
    clone_coll_name = f"{args.clone_name}_Collection"
    existing = bpy.data.collections.get(clone_coll_name)
    if existing:
        log(f"Removing existing clone collection '{clone_coll_name}'")
        for o in list(existing.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(existing)
    for o in list(bpy.data.objects):
        if o.name.startswith(f"{args.clone_name}_"):
            log(f"Removing leftover object {o.name}")
            bpy.data.objects.remove(o, do_unlink=True)

    before = {
        "objects"  : len(bpy.data.objects),
        "meshes"   : sum(1 for o in bpy.data.objects if o.type == 'MESH'),
        "armatures": sum(1 for o in bpy.data.objects if o.type == 'ARMATURE'),
        "actions"  : len(bpy.data.actions),
        "materials": len(bpy.data.materials),
    }

    # ------------------------------------------------------------------
    # Duplicate source
    # ------------------------------------------------------------------
    for o in bpy.data.objects:
        try:
            o.select_set(False)
        except RuntimeError:
            pass
    for o in src_objs:
        try:
            o.select_set(True)
        except RuntimeError:
            pass
    if src_arm:
        bpy.context.view_layer.objects.active = src_arm
    elif src_objs:
        bpy.context.view_layer.objects.active = src_objs[0]

    log("Duplicating...")
    result = bpy.ops.object.duplicate(linked=False)
    if 'FINISHED' not in result:
        log("Duplicate op returned:", result)

    cloned_objs = list(bpy.context.selected_objects)
    log(f"Duplicated {len(cloned_objs)} objects")

    # ------------------------------------------------------------------
    # Move into new collection & rename
    # ------------------------------------------------------------------
    clone_coll = bpy.data.collections.new(clone_coll_name)
    bpy.context.scene.collection.children.link(clone_coll)
    for o in cloned_objs:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        clone_coll.objects.link(o)
        o.name = f"{args.clone_name}_{o.name}"

    cloned_arm = None
    if src_arm:
        cloned_arm = bpy.data.objects.get(f"{args.clone_name}_{src_arm.name}")
    if cloned_arm is None:
        for o in cloned_objs:
            if o.type == 'ARMATURE':
                cloned_arm = o
                break
    log(f"Cloned armature   : {cloned_arm.name if cloned_arm else None}")

    # ------------------------------------------------------------------
    # Remap Armature modifiers to the cloned rig
    # ------------------------------------------------------------------
    if cloned_arm:
        for o in cloned_objs:
            if o.type == 'MESH':
                for m in o.modifiers:
                    if m.type == 'ARMATURE':
                        m.object = cloned_arm

    # ------------------------------------------------------------------
    # Duplicate materials, assign to clone
    # ------------------------------------------------------------------
    mat_map = {}

    def clone_material(mat):
        if mat is None:
            return None
        if mat.name in mat_map:
            return mat_map[mat.name]
        new_mat = mat.copy()
        new_mat.name = f"{args.clone_name}_{mat.name}"
        mat_map[mat.name] = new_mat
        return new_mat

    for o in cloned_objs:
        if o.type == 'MESH':
            for slot in o.material_slots:
                if slot.material:
                    slot.material = clone_material(slot.material)

    log(f"Duplicated {len(mat_map)} materials")

    # ------------------------------------------------------------------
    # Recolor cloned materials
    # ------------------------------------------------------------------
    if new_color is not None:
        recolored = []
        for old_name, mat in mat_map.items():
            try:
                mat.diffuse_color = new_color
            except Exception:
                pass

            nt = mat.node_tree
            if nt is None:
                recolored.append(mat.name)
                continue

            for node in nt.nodes:
                if node.type != 'BSDF_PRINCIPLED':
                    continue
                bc = node.inputs.get("Base Color")
                if bc is None:
                    continue

                if bc.is_linked:
                    link = bc.links[0]
                    upstream = link.from_socket

                    mix = nt.nodes.new("ShaderNodeMixRGB")
                    mix.blend_type = 'MULTIPLY'
                    mix.inputs['Fac'].default_value = 1.0
                    mix.inputs['Color2'].default_value = new_color
                    mix.location = (node.location.x - 220, node.location.y - 220)

                    nt.links.remove(link)
                    nt.links.new(upstream, mix.inputs['Color1'])
                    nt.links.new(mix.outputs['Color'], bc)
                    recolored.append(mat.name)
                else:
                    bc.default_value = new_color
                    em = node.inputs.get("Emission Color") or node.inputs.get("Emission")
                    if em is not None:
                        try:
                            em.default_value = new_color
                        except Exception:
                            pass
                    recolored.append(mat.name)

        log(f"Recolored {len(recolored)} clone materials: {recolored}")

    # ------------------------------------------------------------------
    # Duplicate actions
    # ------------------------------------------------------------------
    act_map = {}

    def clone_action(act):
        if act is None:
            return None
        if act.name in act_map:
            return act_map[act.name]
        new_act = act.copy()
        new_act.name = f"{args.clone_name}_{act.name}"
        act_map[act.name] = new_act
        return new_act

    for o in cloned_objs:
        if o.animation_data:
            if o.animation_data.action:
                o.animation_data.action = clone_action(o.animation_data.action)
            for tr in o.animation_data.nla_tracks:
                for st in tr.strips:
                    if st.action:
                        st.action = clone_action(st.action)

        if o.type == 'MESH' and o.data.shape_keys:
            sk = o.data.shape_keys
            if sk.animation_data and sk.animation_data.action:
                sk.animation_data.action = clone_action(sk.animation_data.action)

    log(f"Duplicated {len(act_map)} actions: {list(act_map.keys())}")

    # ------------------------------------------------------------------
    # Retime cloned actions
    # ------------------------------------------------------------------
    used_actions = set()
    for o in cloned_objs:
        if o.animation_data:
            if o.animation_data.action:
                used_actions.add(o.animation_data.action)
            for tr in o.animation_data.nla_tracks:
                for st in tr.strips:
                    if st.action:
                        used_actions.add(st.action)
        if o.type == 'MESH' and o.data.shape_keys and o.data.shape_keys.animation_data:
            a = o.data.shape_keys.animation_data.action
            if a:
                used_actions.add(a)

    log(f"Retiming {len(used_actions)} cloned actions (speed={speed_factor}x)")
    for act in used_actions:
        old_r = action_frame_range(act)
        n_curves, n_keys = retime_action(act, frame_scale)
        new_r = action_frame_range(act)
        log(f"  action '{act.name}': {old_r} -> {new_r} "
            f"({n_curves} fcurves, {n_keys} keys)")

    # ------------------------------------------------------------------
    # NLA strips
    # ------------------------------------------------------------------
    for o in cloned_objs:
        if not o.animation_data:
            continue
        for tr in o.animation_data.nla_tracks:
            for st in tr.strips:
                old_fs, old_fe = st.frame_start, st.frame_end
                old_afs, old_afe = st.action_frame_start, st.action_frame_end
                dur = old_fe - old_fs
                st.action_frame_start = old_afs * frame_scale
                st.action_frame_end   = old_afe * frame_scale
                st.frame_end          = old_fs + dur * frame_scale
                log(f"  NLA '{st.name}' on '{o.name}': "
                    f"[{old_fs}, {old_fe}] -> [{st.frame_start}, {st.frame_end}]")

    # ------------------------------------------------------------------
    # Scene frame range
    # ------------------------------------------------------------------
    if used_actions:
        new_max = max(action_frame_range(a)[1] for a in used_actions)
        scene = bpy.context.scene
        if 0 < new_max < scene.frame_end:
            log(f"Scene frame_end {scene.frame_end} -> {int(math.ceil(new_max))}")
            scene.frame_end = int(math.ceil(new_max))

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------
    after = {
        "objects"  : len(bpy.data.objects),
        "meshes"   : sum(1 for o in bpy.data.objects if o.type == 'MESH'),
        "armatures": sum(1 for o in bpy.data.objects if o.type == 'ARMATURE'),
        "actions"  : len(bpy.data.actions),
        "materials": len(bpy.data.materials),
    }

    log("=" * 62)
    log("REPORT")
    log("=" * 62)
    for k in before:
        log(f"  {k:10s}  original={before[k]:4d}   after={after[k]:4d}   "
            f"(+{after[k] - before[k]})")

    # glTF JSON cross-check
    if args.gltf_json:
        try:
            with open(args.gltf_json, "r", encoding="utf-8") as f:
                g = json.load(f)
            gl_nodes = [n.get("name", "") for n in g.get("nodes", [])]
            gl_mats  = [m.get("name", "") for m in g.get("materials", [])]
            gl_anims = [a.get("name", "") for a in g.get("animations", [])]
            log(f"  glTF nodes={len(gl_nodes)} materials={len(gl_mats)} animations={gl_anims}")
            blender_names = {o.name for o in bpy.data.objects}
            missing = [n for n in gl_nodes if n and n not in blender_names]
            if missing:
                log(f"  glTF names missing from Blender: {missing[:12]}"
                    f"{' ...' if len(missing) > 12 else ''}")
        except Exception as e:
            log(f"  Could not read glTF JSON: {e}")

    # ------------------------------------------------------------------
    # Export clone only
    # ------------------------------------------------------------------
    if args.export:
        export_path = os.path.abspath(args.export)
        os.makedirs(os.path.dirname(export_path) or ".", exist_ok=True)

        for o in bpy.data.objects:
            try:
                o.select_set(False)
            except RuntimeError:
                pass
        for o in cloned_objs:
            try:
                o.select_set(True)
            except RuntimeError:
                pass
        if cloned_arm:
            bpy.context.view_layer.objects.active = cloned_arm

        log(f"Exporting clone -> {export_path}")

        export_kwargs = dict(
            filepath=export_path,
            export_format='GLB',
            use_selection=True,
            export_apply=False,
            export_animations=True,
            export_skins=True,
            export_morph=True,
            export_yup=True,
        )

        try:
            bpy.ops.export_scene.gltf(**export_kwargs)
        except TypeError:
            # Some 5.x builds renamed/removed a kwarg — retry minimal
            log("  (retrying export with minimal kwargs)")
            bpy.ops.export_scene.gltf(
                filepath=export_path,
                export_format='GLB',
                use_selection=True,
                export_animations=True,
            )

        log("Export done.")

    log("All operations completed.")


if __name__ == "__main__":
    main()

