"""Read-only snapshot of this GUI's registered MMD background jobs."""
import bpy,json
rows=[]
for key,value in list(bpy.app.driver_namespace.items()):
 if key.startswith(('MMD_BACKGROUND_','HEADLESS_')) and hasattr(value,'poll'):
  rows.append(dict(key=key,pid=value.pid,exit_code=value.poll()))
print(json.dumps(dict(registered_jobs=rows,active_jobs=[r for r in rows if r['exit_code'] is None],scene=bpy.context.scene.name),ensure_ascii=False))
