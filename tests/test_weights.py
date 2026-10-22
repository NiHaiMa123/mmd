"""Unit test for the target weight transfer.

The bug this guards against: a helper bone of the base body that the vertex
already carried was scaled to nothing instead of being replaced by the base
body's own weight, so the base body's real influence disappeared silently.

Run it with:

    blender -b --factory-startup --python tests/test_weights.py
"""
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import dressing                       # noqa: E402

TARGET_BONE = "下半身"          # a bone both models have
HELPER_BONE = "足D++.L"         # a helper bone only the base body has
GARMENT_BONE = "スカート_0_0"   # a bone the garment owns


def build():
    """A base body with one triangle and a garment with three vertices."""
    for name in ("t_body", "t_garment"):
        if name in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects[name])

    body = bpy.data.meshes.new("t_body")
    body_obj = bpy.data.objects.new("t_body", body)
    bpy.context.scene.collection.objects.link(body_obj)
    body.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
    body.materials.append(bpy.data.materials.new("skin"))
    body.update()
    for i in range(3):
        body.vertices[i].groups  # the mesh has no groups yet
    body_groups = body_obj.vertex_groups
    g1 = body_groups.new(name=TARGET_BONE)
    g2 = body_groups.new(name=HELPER_BONE)
    for i in range(3):
        g1.add([i], 0.5, 'REPLACE')
        g2.add([i], 0.5, 'REPLACE')

    cloth = bpy.data.meshes.new("t_garment")
    cloth_obj = bpy.data.objects.new("t_garment", cloth)
    bpy.context.scene.collection.objects.link(cloth_obj)
    cloth.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
    cloth.materials.append(bpy.data.materials.new("cloth"))
    cloth.update()
    groups = cloth_obj.vertex_groups
    body_g = groups.new(name=TARGET_BONE)
    helper_g = groups.new(name=HELPER_BONE)
    skirt_g = groups.new(name=GARMENT_BONE)
    for i in range(3):
        body_g.add([i], 1.0, 'REPLACE')
    # the first vertex already carries the base body's helper bone
    helper_g.add([0], 0.2, 'REPLACE')
    # the third one carries a bone of its own
    skirt_g.add([2], 0.3, 'REPLACE')
    return body_obj, cloth_obj


def weights_of(obj, index):
    # the group list lives on the object; the mesh has none of its own
    groups = obj.vertex_groups
    names = {vg.index: vg.name for vg in groups}
    out = {}
    for g in obj.data.vertices[index].groups:
        out[names[g.group]] = round(g.weight, 6)
    return out


def main():
    body, garment = build()
    stats = dressing.transfer_target_weights(
        garment, body, {TARGET_BONE}, [1.0, 1.0, 1.0], blend=1.0,
        max_dist=0.5, domains=False,
        keep_bones={GARMENT_BONE}, target_bones={TARGET_BONE, HELPER_BONE})
    print("stats:", stats)

    ok = True

    def check(name, cond, detail=""):
        nonlocal ok
        ok = ok and bool(cond)
        print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")

    w0 = weights_of(garment, 0)
    w1 = weights_of(garment, 1)
    w2 = weights_of(garment, 2)
    print("vertex 0:", w0)
    print("vertex 1:", w1)
    print("vertex 2:", w2)

    # the vertex that already had the helper bone and the one that did not
    # have to end up with the same weight
    check("the helper bone is not lost when the vertex already had it",
          w0.get(HELPER_BONE, 0.0) > 0.4, f"{w0}")
    check("the helper bone is added when the vertex did not have it",
          w1.get(HELPER_BONE, 0.0) > 0.4, f"{w1}")
    check("both vertices end up with the same helper weight",
          abs(w0.get(HELPER_BONE, 0) - w1.get(HELPER_BONE, 0)) < 1e-5,
          f"{w0.get(HELPER_BONE)} vs {w1.get(HELPER_BONE)}")
    check("the old helper weight is not added on top",
          w0.get(HELPER_BONE, 0) < 0.6, f"{w0}")
    # a bone the garment owns keeps its weight
    check("the garment bone keeps its weight",
          abs(w2.get(GARMENT_BONE, 0) - 0.3) < 1e-4, f"{w2}")
    # and the weights still add up to one
    total = sum(w for n, w in w2.items() if n != GARMENT_BONE) + w2.get(GARMENT_BONE, 0)
    check("the weights still add up to one", abs(total - 1.0) < 1e-4, f"{total}")

    print("RESULT:", "OK" if ok else "PROBLEM")


main()
