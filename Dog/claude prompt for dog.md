# MASTER PROMPT — Pug Character Reconstruction in Blender (Reference-Matched)

## 0. Role and Goal

You are a senior Blender technical artist and Python (bpy) engineer specializing in stylized-realistic characters (feature-animation quality: big expressive eyes, cartoon proportions, but realistic fur, skin and lighting).

Your job is to rebuild the pug in the reference image inside Blender as closely as possible, using maintainable Python, real Blender execution, and render-versus-reference iteration.

The reference image is the visual authority. Match it. Do not invent a different dog or substitute a generic pug.

Pixel-perfect identity from one image is not realistic. The target is: **same silhouette, same pose, same face, same expression, same colors, same scarf and ornament, same lighting mood**, verified by side-by-side and overlay comparison.

---

## 1. Project Files

| Item | Path |
|---|---|
| Project folder | `D:\3D\Dog\` |
| Blender project | `D:\3D\Dog\receptionist.blend` |
| Existing script | `D:\3D\Dog\pug_avatar_builder.py` |
| Reference image | `D:\3D\Dog\assets\reference.png` (place the pug image here) |
| Optional base mesh | `D:\3D\Dog\assets\base_mesh.glb` (only if provided, e.g. from an image-to-3D tool) |

Back up `receptionist.blend` and `pug_avatar_builder.py` into `D:\3D\Dog\backups\` with a timestamp **before** changing anything.

---

## 2. Phase 1 — Inspect Before Editing

1. Find the installed Blender executable and version (e.g. `C:\Program Files\Blender Foundation\Blender 4.x\blender.exe`). All code must target that version.
2. Read `pug_avatar_builder.py` fully: structure, mesh generation, materials, collections, camera and lights, render and save logic, error handling.
3. Inspect `receptionist.blend` headless (`blender -b receptionist.blend --python-expr ...`): collections, objects, materials, modifiers, world, color management, unit scale.
4. Write a short analysis (max ~15 lines): what exists, what to reuse, what to replace, and the plan.

Never claim you inspected or ran anything you did not actually access.

---

## 3. Reference Breakdown (What the Image Shows)

Use these observations as the spec. Directions are **viewer's left / viewer's right**.

### Composition and camera
- Front view, camera at the dog's chest-to-eye level, looking very slightly down.
- Portrait framing, roughly **5:6 aspect** (e.g. 1700 × 2040 final). Dog centered, full body visible, small margin above the ears and below the paws.
- Mild telephoto look: use about **70–85 mm** focal length, so there is no wide-angle distortion.
- Head tilted about **10–12° toward viewer's right** (the right ear is lower than the left).

### Proportions (as fractions of total dog height, top of ears to bottom of paws)
- Head including ears: about **42–45%** of height. Head width is almost as wide as the hips.
- Head width (cheek to cheek, excluding ears) is about **1.2×** head height.
- Neck/scarf band sits at about **47–55%** of height.
- Body is pear-shaped and widest at the hind legs and hips.

### Head and face
- Big round skull, cream/beige fur.
- **Forehead wrinkles:** a central diamond/teardrop fold between the brows, deep curved folds above each eye, and smaller folds running up the forehead. They are soft and rounded, not sharp creases.
- **Black mask:** charcoal-black muzzle, dark patches around both eyes, and black lips.
- Short, flat muzzle with two puffy cheek pads on either side of the mouth.
- **Nose:** broad, black, slightly upturned, with two clearly defined nostrils and a leathery texture.
- A few sparse whiskers on the cheeks, mainly viewer's left. Whisker dots are visible on the muzzle.

### Eyes (top priority)
- Very large, bulging, round eyes with visible **white sclera** all around the iris (cartoon style).
- **Iris:** saturated orange-amber with a darker red-brown outer ring and radial fibers.
- Large black pupil.
- One sharp specular highlight in the upper-left of each eye, plus a softer secondary reflection.
- Glossy wet cornea, dark eyelid rims, and a soft transition into the black eye patches.
- **Gaze:** looking up at the viewer. The eyes diverge slightly; the viewer-left eye looks a bit more up and right.
- The viewer-right eye sits slightly lower because of the head tilt.

### Mouth and tongue
- Wide open, happy smile stretching across the lower face.
- Black lips; dark inner mouth with a hint of pink palate.
- Pink tongue hanging out at the center, slightly toward viewer's left. It is rounded and broad, with a soft center groove, a wet sheen, and some thickness.

### Ears
- Dark brown-black, soft and floppy "button/rose" ears with real thickness.
- **Viewer-left ear:** lifted and flipped outward/upward, showing a pinkish-brown inner ear.
- **Viewer-right ear:** hangs lower, folded forward along the side of the head.

### Body, legs and paws
- Seated pose. Broad chest with a soft fur tuft or whorl on the upper chest. Rounded belly.
- **Front legs:** straight, short, chunky, slightly apart.
- **Front paws:** face forward with 4 rounded toes each and short dark-brown/black curved claws.
- **Hind legs:** folded at the sides. The hind paws stick out to the left and right, turned outward, with visible toes and claws.
- All paws must touch the ground with soft contact shadows.

### Tail
- Thick, fluffy, tightly curled into one loop, on the **viewer's right at hip height**, curling upward and inward.
- Cream fur, slightly longer than the body fur. Attach it to the rump with no visible seam.

### Scarf (essential)
- Red-and-cream **gingham**, woven, wrapped around the neck as a fairly snug, slightly thick band (about 1/10 of the dog's height).
- About **8–10 checks** are visible across the front band. Each check shows woven thread texture.
- One tail hangs down from the knot on the **viewer's right of center**, over the chest, ending around belly level.
- The end has about **10 twisted fringe tassels**, each a two-ply twist of red and cream, with uneven lengths.
- Soft folds where the band bunches at the knot.

### Gold lotus ornament
- A gold pin at the top of the hanging scarf tail, just below the neck band.
- Lotus shape with about **5 front petals plus 2 side leaves** and a small round base. The petals are slightly cupped, polished gold with softer recesses.

### Fur look
- Short, dense, soft cream fur on the body.
- Very short fine fur on the face.
- Slightly longer fur on the cheeks' outer edge, chest tuft and tail.
- Subtle fuzz visible on the silhouette edges (from the rim light).
- Color varies from pale cream to light tan; darker brown-black fur on the ears and mask.

### Lighting and background
- Seamless warm gray studio backdrop and floor (about `#A39B95` to `#8E8781`), slightly lighter behind the head.
- Large soft key light from front, upper left.
- Soft fill from the front right.
- Gentle back/rim light for fur edge glow.
- Very soft, short shadows and low contrast. Warm, friendly mood.

### Inferred, not visible
The back of the body, the underside, the back of the tail, and the inside of the mouth beyond what's visible are not in the image. Build them plausibly and label them as inferred in the report.

---

## 4. Phase 2 — Clean the Scene

1. Remove only the old prototype objects. Keep anything reusable (world, render settings, useful materials).
2. Purge orphan data safely.
3. Organize collections:

```
DOG_CHARACTER
  BODY, HEAD, FACE (EYES, NOSE, MOUTH, TONGUE), EARS, LEGS_PAWS, TAIL, FUR
  ACCESSORIES (SCARF, LOTUS)
CHARACTER_RIG
ENVIRONMENT
LIGHTING
CAMERAS
RENDER_HELPERS (reference image, comparison helpers)
```

---

## 5. Phase 3 — Geometry Method (Organic, Not Primitive Soup)

Use this pipeline for the body and head:

1. **Blockout from overlapping forms.** Use metaballs, or a signed-distance blend of ellipsoids and capsules, to model the skull, cheeks, muzzle, chest, belly, hips, legs and paws, all driven by the parameters in the config.
2. **Fuse into one mesh.** Convert, then **voxel remesh** (fine voxel size), then **Quadriflow** or keep voxel topology and smooth. Result: one watertight body mesh with no intersections.
3. **Procedural sculpting in code.** Apply displacement passes with bmesh, using falloff brushes defined by position and radius, to carve:
   - the forehead wrinkles (diamond fold and brow folds),
   - eye sockets,
   - the mouth opening and lip line,
   - cheek pads,
   - toe separations,
   - the chest tuft bulge.
   Store each brush stroke as data in the config so artists can tweak them.
4. **Finishing modifiers.** Add Subdivision Surface (render level 2–3), weighted normals where useful, and keep modifiers non-destructive where possible.
5. **Separate meshes for parts that need them:**
   - eyes (sclera, iris disc/lens with parallax depth, cornea shell),
   - eyelid rims,
   - tongue,
   - inner mouth,
   - ears (thickened shells attached at the skull),
   - claws,
   - scarf, tassels, lotus.
6. **Tail:** a Bezier spiral curve, converted to a tapered mesh, blended into the rump.
7. **Scarf:** a ribbon mesh following a loop around the neck, plus a hanging strip.
   - Use Solidify for thickness and displacement for folds.
   - Optionally run a short cloth simulation pinned at the neck, then apply it.
   - Tassels are twisted curve pairs with a bevel.
8. **Lotus:** procedural petals (deformed, cupped planes), then Solidify, then a bevel. Arrange them radially and add a base.

If `assets\base_mesh.glb` exists, you may use it as the body base instead of step 1–2, then still apply steps 3–8 and proportion fixes.

---

## 6. Phase 4 — Fur

- Prefer Blender's **hair curves with Geometry Nodes** (Blender 3.5+; use the built-in Essentials hair node groups if available):
  - Distribute (density by vertex group),
  - Interpolate,
  - Clump,
  - Frizz (low),
  - Curl/noise,
  - Set profile.
- Fall back to particle hair if the version requires it.
- Use separate grooms:

| Groom | Length | Notes |
|---|---|---|
| Body | 3–5 mm (scaled) | Combed toward the back and down |
| Face | 1–2 mm | Very fine |
| Cheek edge and chest tuft | Slightly longer | Soft volume |
| Tail | Longest | Fluffy |
| Ears | Dark, very short | |
| Muzzle/mask | Very short, dark | Mostly skin visible |

- **Grooming direction:** guide curves or a vector field, so fur follows real dog flow: from the nose outward, from the forehead back, and down the body.
- **Fur material:** Principled Hair BSDF (melanin model).
  - Cream: melanin about 0.2–0.3, redness about 0.5–0.6, random color 0.1–0.15, roughness 0.3–0.4.
  - Dark: melanin about 0.85–0.95.
  - Blend by a vertex group or texture so the mask and ears are dark.
- The base skin under the fur gets matching colors, so thin areas don't look bald.

---

## 7. Phase 5 — Materials

| Material | Key settings |
|---|---|
| Skin under fur | Cream/tan base, subsurface on, roughness about 0.5 |
| Mask skin, lips, nose | Near-black (about `#151313`), roughness 0.35–0.5, bump from Voronoi plus noise for the leathery nose and the whisker-dot texture |
| Sclera | Off-white, slight subsurface, faint pink at the edges |
| Iris | Radial procedural pattern: orange-amber center, dark red-brown outer ring, darker limbal ring; black pupil |
| Cornea | Glass/clear coat, IOR about 1.376, roughness 0–0.02 |
| Inner mouth | Dark red-brown, subsurface |
| Tongue | Pink (about `#E8858E`), subsurface, coat 0.3–0.5 for wetness, subtle bump with a center-groove normal |
| Claws | Dark brown-black, roughness 0.3, slight translucency at the tips |
| Scarf | Procedural gingham (red about `#B3262B`, cream about `#EDE3D0`) where overlapping stripes produce a mid tone, plus a woven-thread bump; Sheen on, roughness 0.8 |
| Tassels | Same palette per strand, with a thread twist bump |
| Lotus | Metallic gold (about `#E2B566`), roughness 0.2–0.3, darker roughness in the recesses (use AO or pointiness) |
| Floor and background | Warm gray, matte, seamless cyclorama (curved backdrop) |

---

## 8. Phase 6 — Lighting, Camera, Render

- **Lights:**
  - Large area key light (front upper left, soft, warm white).
  - Area fill (front right, about 30–40% of the key).
  - Rim light from behind and above for fur glow.
  - Low world ambient in warm gray.
  - Add a small eye-light card if needed so the catchlights match the reference (upper left).
- **Camera:** 70–85 mm, matching the reference framing. Load `reference.png` as the camera background image for alignment.
- **Engine:** Cycles. Detect GPU (OptiX → CUDA → HIP → Metal), with CPU fallback.
- **Preview:** about 600 px, 64 samples, simplified fur density.
- **Final:** about 1700 × 2040 or higher, 256–512 samples, denoise on, AgX (Blender 4.x) or Filmic, curves fine, transparent bounces high enough for fur.

---

## 9. Phase 7 — Match Against the Reference (Mandatory)

After each stage below, render a preview and compare:

1. Blockout silhouette
2. Head, face, eyes
3. Ears, legs, tail
4. Scarf and lotus
5. Materials
6. Fur
7. Final lighting

For every comparison:
- Save `output\compare\stage_N_side_by_side.png` (reference left, render right) and `stage_N_overlay.png` (50% blend).
- Compute a **silhouette match score**: segment the dog from the reference background into a mask, render the dog as a mask (holdout/alpha) from the same camera, and calculate IoU. Target **IoU ≥ 0.90** before moving to detail work.
- List the top 3 visual differences and fix them before moving to the next stage. Pay special attention to:
  - eye size, spacing and gaze,
  - head tilt,
  - ear positions,
  - mouth width and tongue shape,
  - scarf placement,
  - tail position,
  - fur color.

Never report success because the script ran. Success means the comparison images look like the reference.

---

## 10. Phase 8 — Rig (Optional, Lower Priority)

If time allows, add a simple armature: spine, neck, head, jaw, tongue (2–3 bones), ears, tail chain, legs, and eye-target empties for gaze. Add a shape key for blinking.

Do not compromise the reconstruction quality for rigging.

---

## 11. Code Requirements

Adapt to the existing `pug_avatar_builder.py` structure where it makes sense. Suggested layout:

```
D:\3D\Dog\
  pug_avatar_builder.py          # entry point: runs the full pipeline
  config.py               # ALL tweakable parameters (proportions, sculpt strokes, colors, fur, render)
  modules\
    scene_manager.py      # backup, cleanup, collections, save
    body_builder.py       # blockout, remesh, procedural sculpt
    face_builder.py       # eyes, nose, mouth, tongue, ears
    accessories.py        # scarf, tassels, lotus
    fur_system.py
    materials.py
    lighting_camera.py
    render_manager.py     # preview/final, GPU detection
    compare.py            # side-by-side, overlay, IoU
  assets\  output\renders\  output\compare\  output\logs\  backups\
```

Requirements:
- Type hints, docstrings, and logging to `output\logs\generation.log`.
- **Idempotent:** rerunning replaces the character cleanly, with no duplicates.
- Fixed random seeds so results are reproducible.
- Clear errors for a missing reference image, unsupported API, failed save or failed render. Never fail silently.
- **CLI flags:**
  - `--stage N` builds up to stage N,
  - `--preview` or `--final`,
  - `--no-fur` for fast iteration.

**Run command:**

```
"C:\Program Files\Blender Foundation\Blender 4.x\blender.exe" -b D:\3D\Dog\receptionist.blend --python D:\3D\Dog\pug_avatar_builder.py -- --preview
```

---

## 12. Deliverables

1. Updated Python files and `config.py`.
2. Saved `receptionist.blend`, with backups preserved.
3. Renders:
   - `output\renders\dog_preview.png`
   - `output\renders\dog_final.png`
4. Comparison images for every stage and the final IoU score.
5. `output\implementation_report.md`, covering:
   - what was built,
   - final reference-match notes,
   - what is inferred versus visible,
   - known limitations,
   - how to rerun and tweak (which `config.py` values change what).

---

## 13. Rules

1. Inspect before editing; back up first.
2. The reference image is the authority. Match it; don't redesign it.
3. Build in stages, render, compare, fix, then continue.
4. Actually execute Blender. If you can't, say so plainly and give exact run steps instead of claiming results.
5. Never fabricate renders, scores or "it matches" claims.
6. Keep the code clean and configurable. Visual fixes go into `config.py` values, not hacks.

**Start now with Phase 1: inspect `pug_avatar_builder.py` and `receptionist.blend`, then report your analysis and plan.**
