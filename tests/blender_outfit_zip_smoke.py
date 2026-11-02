"""Verify the distributed package uses its bundled engine, not the checkout."""
from pathlib import Path
import sys
import zipfile
import uuid
import argparse

import bpy

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / "outputs" / ("outfit_zip_smoke_" + uuid.uuid4().hex[:8])
target.mkdir(parents=True, exist_ok=True)
parser=argparse.ArgumentParser();parser.add_argument('--zip',default=str(ROOT/'dist/mmd_outfit_bridge-0.9.0.zip'));args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
with zipfile.ZipFile(args.zip) as archive:
    names = archive.namelist()
    assert not any(name.endswith((".pmx", ".vmd", ".blend")) for name in names)
    archive.extractall(target)
sys.path.insert(0, str(target))
import mmd_outfit
from mmd_outfit.service import engine

sentinel = bpy.data.objects.new("ExistingScene", None)
bpy.context.scene.collection.objects.link(sentinel)
mmd_outfit.register()
if 'mmd_outfit/native_guard.py' in names:
    from mmd_outfit.native_guard import add_skin_guard
    from mmd_outfit.nylon_shell import install as install_nylon_shell
    assert callable(add_skin_guard) and callable(install_nylon_shell)
if 'mmd_outfit/mesh_cloth.py' in names:
    from mmd_outfit.mesh_cloth import configure
    from mmd_outfit.hosiery_cleanup import clean
    assert callable(configure) and callable(clean)
if 'mmd_outfit/structured_cloth.py' in names:
    from mmd_outfit.structured_cloth import install
    assert callable(install)
if 'mmd_outfit/chest_panel.py' in names:
    from mmd_outfit.chest_panel import restore
    assert callable(restore)
if 'mmd_outfit/sleeve_shape_constraints.py' in names:
    from mmd_outfit.sleeve_shape_constraints import rotation_blend, project_strain
    from mmd_outfit.stable_sleeve_cloth import bind_clamped_frames
    assert callable(rotation_blend) and callable(project_strain) and callable(bind_clamped_frames)
if 'mmd_outfit/motion_contact.py' in names:
    from mmd_outfit.motion_contact import audit_current_pose
    from mmd_outfit.contact_broadphase import scoped_box_pairs
    from mmd_outfit.contact_timeline import reference_at_time
    assert callable(audit_current_pose) and callable(scoped_box_pairs) and callable(reference_at_time)
assert hasattr(bpy.context.scene, "mmd_outfit")
assert bpy.context.scene.mmd_outfit.cuff_physics is False
from mmd_outfit.skin_patch import face_domain
from types import SimpleNamespace
assert face_domain(SimpleNamespace(vertices=(0,1,2)),('thumb','index','palm')) is None
assert "outfit_zip_smoke" in str(Path(engine("dressing").__file__))
assert "src.dressing" not in sys.modules
mmd_outfit.unregister()
assert "ExistingScene" in bpy.data.objects
print("ZIP_SMOKE_OK: bundled engine, UI registration, scene preserved")
