import bpy,numpy as np,sys
sys.path.insert(0,'E:/project/mmd/mmd_repo/tools/contact_stack/venv/Lib/site-packages')
import warp as wp
wp.init();print('BLENDER_WARP_OK',wp.get_devices(),np.__version__,flush=True)
