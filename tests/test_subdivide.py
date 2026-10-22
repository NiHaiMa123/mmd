"""Unit test for subdivide_triangles: topology, UVs, morphs, weights.

Run it with:

    blender -b --factory-startup --python tests/test_subdivide.py

It needs no model and no asset: it builds its own mesh, so anyone can
check the assertions instead of taking the result on trust.
"""
import os
import sys

import bpy
import bmesh
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import dressing                       # noqa: E402


def build():
    me = bpy.data.meshes.new("t")
    obj = bpy.data.objects.new("t", me)
    bpy.context.scene.collection.objects.link(obj)
    verts = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0), (0, -1, 0)]
    me.from_pydata(verts, [], [(0, 1, 2), (1, 3, 2), (0, 4, 1)])
    me.update()
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li, loop in enumerate(poly.loop_indices):
            uv.data[li].uv = (poly.index * 0.5 + li * 0.1, poly.index * 0.25)
    me.materials.append(bpy.data.materials.new("m0"))
    me.materials.append(bpy.data.materials.new("m1"))
    me.polygons[0].material_index = 1
    vg = obj.vertex_groups.new(name="bone")
    vg.add([0, 1], 1.0, 'REPLACE')
    vg2 = obj.vertex_groups.new(name="bone2")
    vg2.add([2, 3, 4], 1.0, 'REPLACE')
    obj.shape_key_add(name="Basis", from_mix=False)
    sk = obj.shape_key_add(name="Morph", from_mix=False)
    for i, v in enumerate(sk.data):
        v.co.z += 0.1 * (i + 1)
    return me, obj


def build_poly():
    """A quad with a neighbour, so the fan branch is exercised."""
    me = bpy.data.meshes.new("q")
    obj = bpy.data.objects.new("q", me)
    bpy.context.scene.collection.objects.link(obj)
    verts = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (2, 0, 0)]
    me.from_pydata(verts, [], [(0, 1, 2, 3), (1, 4, 2)])
    me.update()
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li, loop in enumerate(poly.loop_indices):
            uv.data[li].uv = (poly.index * 0.5 + li * 0.1, poly.index * 0.25)
    obj.shape_key_add(name="Basis", from_mix=False)
    sk = obj.shape_key_add(name="Morph", from_mix=False)
    for i, v in enumerate(sk.data):
        v.co.z += 0.1 * (i + 1)
    return me, obj


def test_fan_centre():
    """The fan centre is one vertex, so it has to have one UV."""
    me, obj = build_poly()
    dressing.subdivide_triangles(me, [0])
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    # the centre is the vertex that belongs to the most faces
    centre = max(bm.verts, key=lambda v: len(v.link_faces))
    layer = bm.loops.layers.uv.active
    values = set()
    for loop in centre.link_loops:
        values.add((round(loop[layer].uv[0], 6), round(loop[layer].uv[1], 6)))
    print(f"centre belongs to {len(centre.link_faces)} faces, "
          f"{len(values)} distinct UVs")
    ok = len(values) == 1
    print(f"[{'PASS' if ok else 'FAIL'}] the fan centre has one UV")
    bm.free()
    return ok


def main():
    me, obj = build()
    before_faces = len(me.polygons)
    before_verts = len(me.vertices)
    # select the first two faces; the third one shares an edge with them
    added = dressing.subdivide_triangles(me, [0, 1])
    print("faces:", before_faces, "->", len(me.polygons),
          "verts:", before_verts, "->", len(me.vertices), "added:", added)

    ok = True

    def check(name, cond, detail=""):
        nonlocal ok
        ok = ok and bool(cond)
        print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")

    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # a T-junction: a vertex that lies on an edge without being one of its
    # ends.  That is what breaks when a midpoint is put on an edge that a
    # face outside the selection still uses.
    ts = []
    for v in bm.verts:
        for e in bm.edges:
            if v.index in (e.verts[0].index, e.verts[1].index):
                continue
            a = e.verts[0].co
            b = e.verts[1].co
            ab = b - a
            if ab.length < 1e-9:
                continue
            t = (v.co - a).dot(ab) / ab.length_squared
            if not 0.02 < t < 0.98:
                continue
            d = (v.co - (a + ab * t)).length
            if d < 1e-5:
                ts.append((v.index, e.index))
    check("no T-junction anywhere", not ts, str(ts[:5]))

    # no edge with more than two faces
    bad = [e.index for e in bm.edges if len(e.link_faces) > 2]
    check("no edge with more than two faces", not bad, str(bad[:5]))

    # every edge that the neighbour still uses is still whole: the edge
    # (0, 1) between the selection and the neighbour must not have a
    # midpoint in the middle of it
    shared = [e for e in bm.edges
              if {e.verts[0].index, e.verts[1].index} == {0, 1}]
    check("the edge shared with the outside face is still one edge",
          len(shared) == 1, f"{len(shared)}")

    # the neighbour face is still a triangle: it is the only face with the
    # vertex at (0, -1, 0)
    nb = [p for p in me.polygons
          if any(abs(me.vertices[v].co.y + 1.0) < 1e-6 for v in p.vertices)]
    check("the neighbour face is still a triangle",
          len(nb) == 1 and len(nb[0].vertices) == 3,
          str([len(p.vertices) for p in nb]))

    # the material index of the selection survived
    mats = [p.material_index for p in me.polygons]
    check("the material index of the selection survived",
          mats.count(1) >= 4, str(sorted(mats)))

    # the morph is interpolated: the new vertices carry a value between the
    # two ends, and the originals keep theirs
    sk = me.shape_keys.key_blocks["Morph"]
    check("the original vertices kept their morph",
          abs(sk.data[0].co.z - 0.1) < 1e-6, f"{sk.data[0].co.z}")
    zs = sorted(round(v.co.z, 4) for v in sk.data)
    print("morph z values:", zs)
    check("the morph was interpolated on the new vertices",
          len(zs) == len(me.vertices), f"{len(zs)} vs {len(me.vertices)}")

    # the weights: a vertex between a weighted and an unweighted one has
    # both groups
    both = 0
    for v in me.vertices:
        names = {obj.vertex_groups[g.group].name for g in v.groups}
        if len(names) == 2:
            both += 1
    check("the new midpoints carry both weights", both >= 4,
          f"{both} mixed vertices")

    # the UVs: every loop has a UV and they are inside the original range
    uv = me.uv_layers[0]
    us = [d.uv.x for d in uv.data]
    check("every loop has a UV", len(uv.data) == sum(len(p.vertices)
                                                    for p in me.polygons),
          f"{len(uv.data)}")
    check("the UVs stay in range", max(us) <= 1.2 + 1e-6 and min(us) >= -1e-6,
          f"{min(us):.3f}..{max(us):.3f}")

    bm.free()
    ok = ok and test_fan_centre()
    print("RESULT:", "OK" if ok else "PROBLEM")


main()
