"""MMD clothing-transfer toolkit.

Layout:
  src/blender_env.py   - locate Blender, run scripts inside it (outer process)
  src/import_export.py - PMX import/export/inventory (needs bpy, runs in Blender)
  src/extraction.py    - clothing segmentation + preview
  src/dressing.py      - rig mapping, body fit, re-weighting, body hiding
  src/qa.py            - static / motion validation
  src/cli.py           - command line front end
"""
__all__ = ["blender_env", "import_export", "extraction", "dressing", "qa", "cli"]
