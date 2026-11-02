import bpy,json
group=bpy.data.node_groups.new('TEMP_Clump_API_Probe','GeometryNodeTree')
try:
    compare=group.nodes.new('FunctionNodeCompare');compare.data_type='INT';compare.operation='NOT_EQUAL'
    print(json.dumps(dict(version=bpy.app.version_string,inputs=[dict(name=s.name,identifier=s.identifier,type=s.type) for s in compare.inputs],outputs=[dict(name=s.name,identifier=s.identifier) for s in compare.outputs]),ensure_ascii=False))
finally:bpy.data.node_groups.remove(group)
