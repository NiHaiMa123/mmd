"""Static proxy asset: unsigned surface voxelization, closing and marching cubes.

No animation integration or collision response. Normals and bone groups cannot
split or fold this union: all original hair triangles enter the same volume.
"""
import argparse, json, time
from pathlib import Path
import numpy as np
import scipy
from scipy import ndimage
import skimage
from skimage.measure import marching_cubes
import trimesh

p = argparse.ArgumentParser()
p.add_argument('--out', required=True)
p.add_argument('--manifold-clean', action='store_true')
a = p.parse_args()
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
assert not (out/'geometric_volume.npz').exists(), 'Use a new asset directory'
base = Path(__file__).resolve().parents[2]/'work/headswap_xl_codex'
started = time.monotonic()
def progress(stage, **kw):
    d = dict(stage=stage, elapsed_s=time.monotonic()-started, **kw)
    (out/'volume_status.json').write_text(json.dumps(d, indent=2), 'utf8')
    print('GEOMETRIC_VOLUME', json.dumps(d), flush=True)

z = np.load(base/'standard_proxy_20261031/inspection/inputs.npz')
inv = np.linalg.inv(z['head_matrix'])
x = z['world']@inv[:3,:3].T+inv[:3,3]
pitch = .002
origin = np.floor((x.min(0)-.022)/pitch)*pitch
shape = np.ceil((x.max(0)+.022-origin)/pitch).astype(int)+1
def raster(vertices, faces):
    surface = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    samples = surface.voxelized(pitch, method='subdivide').points
    indices = np.rint((samples-origin)/pitch).astype(np.int32)
    valid = np.all((indices>=0)&(indices<shape), axis=1)
    indices = indices[valid]
    mask = np.zeros(tuple(shape), bool)
    mask[tuple(indices.T)] = True
    return mask
def ball(radius):
    q = np.arange(-radius, radius+1)
    u,v,w = np.meshgrid(q,q,q,indexing='ij')
    return u*u+v*v+w*w <= radius*radius

progress('RASTERIZING_ALL_ORIGINAL_HAIR', grid=shape.tolist())
hair = raster(x, z['faces'])
progress('UNSIGNED_UNION_AND_GAP_CLOSING', surface_voxels=int(hair.sum()))
volume = ndimage.binary_dilation(hair, structure=ball(2))
volume = ndimage.binary_closing(volume, structure=ball(3))
# This is a rest-asset CSG clearance, never a per-frame projection. Skin keeps
# all its real triangles, with no artificial closure caps or region exclusions.
exp = base/'fullhair_repro_20261030/input_body_aware'
bodyworld = np.load(exp/'body.npy', mmap_mode='r')[0]
body = bodyworld@inv[:3,:3].T+inv[:3,3]
faces = np.load(exp/'body_faces.npy')[np.load(exp/'real_body_faces.npy').astype(bool)]
t = body[faces]
keep = np.all(t.max(1)>=origin, axis=1)&np.all(t.min(1)<=origin+(shape-1)*pitch, axis=1)
progress('STATIC_SKIN_CLEARANCE_CSG', real_skin_triangles=int(keep.sum()))
skin = raster(body, faces[keep])
skin_distance = ndimage.distance_transform_edt(~skin, sampling=pitch)
wall_preparation={}
if a.manifold_clean:
    # Keep at least two coarse isosurface cells of material after skin CSG.
    # Merely cutting a 4mm band at 5mm clearance erases tightly laid braids.
    # Thicken only the simulation copy near skin, preserving every source face.
    coarse_cell=pitch*2
    minimum_wall=2*coarse_cell
    band_radius=np.ceil((.005+minimum_wall)/pitch)*pitch
    seeds=hair&(skin_distance<.009)
    progress('MINIMUM_PROXY_WALL_NEAR_SKIN',minimum_wall_m=minimum_wall,offset_radius_m=band_radius)
    near_seed_distance=ndimage.distance_transform_edt(~seeds,sampling=pitch)
    volume|=near_seed_distance<=band_radius
    del near_seed_distance
    wall_preparation=dict(minimum_wall_m=minimum_wall,near_skin_offset_radius_m=float(band_radius))
volume &= skin_distance > .005
if a.manifold_clean:
    # Unsigned clearance alone keeps voxels deep INSIDE skin too. Use the
    # established fast-winding classifier to keep the exterior material only.
    import igl
    progress('CLASSIFYING_STATIC_SKIN_EXTERIOR')
    occupied=np.argwhere(volume)
    queries=origin+occupied*pitch
    winding_skin=igl.fast_winding_number(body.astype(np.float64),faces.astype(np.int64),queries.astype(np.float64))
    remove=np.abs(winding_skin)>.5
    volume[tuple(occupied[remove].T)]=False
    wall_preparation['skin_interior_voxels_removed']=int(remove.sum())
    del occupied,queries,winding_skin,remove
del skin_distance
label, count = ndimage.label(volume)
sizes = np.bincount(label.ravel())
source_indices=np.rint((x-origin)/pitch).astype(int)
source_labels=label[tuple(source_indices.T)]
# Skin subtraction can leave isolated single voxels. Remove only <=8-voxel
# fragments containing no original hair vertex; record every removed fragment.
# No display geometry or substantial unrooted surface is discarded.
dust=[i for i in range(1,count+1) if sizes[i]<=8 and not np.any(source_labels==i)]
dust_voxels=int(sizes[dust].sum())
if dust:volume[np.isin(label,dust)]=False
cleanup=dict(wall_preparation)
if a.manifold_clean:
    # Fill enclosed air pockets, but retain any cavity containing real skin.
    # A connected solid can have many disconnected inner boundary surfaces.
    progress('FILLING_NON_SKIN_INTERNAL_CAVITIES')
    enclosed=ndimage.binary_fill_holes(volume,structure=np.ones((3,3,3),bool))&~volume
    hole_labels,hole_count=ndimage.label(enclosed)
    blocked=set(map(int,np.unique(hole_labels[skin])))
    fill_ids=[i for i in range(1,hole_count+1) if i not in blocked]
    fill_mask=np.isin(hole_labels,fill_ids)
    cleanup.update(internal_cavities_filled=len(fill_ids),internal_voxels_filled=int(fill_mask.sum()),
        skin_cavities_retained=sum(i in blocked for i in range(1,hole_count+1)))
    volume|=fill_mask
    del hole_labels,enclosed,fill_mask,label
    # Continuous scalar values remove the binary saddle/edge-touch ambiguity.
    # The coarser sampling is done before meshing, not by collapsing thin walls.
    progress('CONTINUOUS_FIELD_REMESHING',**cleanup)
    field=ndimage.gaussian_filter(volume.astype(np.float32),.85)
    stride=2
    vertices,triangles,_,_=marching_cubes(field[::stride,::stride,::stride],.5001,
        spacing=(pitch*stride,)*3,method='lewiner',allow_degenerate=False)
    vertices+=origin
    np.savez_compressed(out/'continuous_surface_before_remesh.npz',vertices=vertices,triangles=triangles)
    progress('STANDARD_ISOTROPIC_REMESHING',vertices=len(vertices),triangles=len(triangles))
    import pymeshlab
    ms=pymeshlab.MeshSet();ms.add_mesh(pymeshlab.Mesh(vertices.astype(float),triangles.astype(np.int32)))
    ms.meshing_isotropic_explicit_remeshing(iterations=5,adaptive=False,
        targetlen=pymeshlab.PureValue(.007),featuredeg=170.,checksurfdist=True,
        maxsurfdist=pymeshlab.PureValue(.0006),splitflag=True,collapseflag=True,
        swapflag=True,smoothflag=True,reprojectflag=True)
    vertices=ms.current_mesh().vertex_matrix().copy();triangles=ms.current_mesh().face_matrix().copy()
    cleanup.update(gaussian_sigma_voxels=.85,mc_sampling_stride=stride,mc_level=.5001,
        isotropic_target_edge_m=.007,isotropic_max_surface_deviation_m=.0006,
        native_decimate_after_import=False)
else:
    vertices=None
progress('MARCHING_CUBES', occupied_voxels=int(volume.sum()))
if vertices is None:
    vertices, triangles, _, _ = marching_cubes(volume.astype(np.float32), .5,
        spacing=(pitch,)*3, method='lewiner', allow_degenerate=False)
    vertices += origin
mesh=trimesh.Trimesh(vertices=vertices,faces=triangles,process=False)
if mesh.volume<0:triangles=triangles[:,::-1].copy()
edges=np.sort(np.concatenate([triangles[:,[0,1]],triangles[:,[1,2]],triangles[:,[2,0]]]),axis=1)
_,edge_counts=np.unique(edges,axis=0,return_counts=True)
cleanup.update(boundary_edges=int((edge_counts==1).sum()),nonmanifold_edges=int((edge_counts>2).sum()))
if a.manifold_clean:
    assert np.all(edge_counts==2),('Static cage must be closed and manifold',cleanup)
    import igl
    winding=igl.fast_winding_number(vertices.astype(np.float64),triangles.astype(np.int64),x.astype(np.float64))
    squared,_,_=igl.point_mesh_squared_distance(x.astype(np.float64),vertices.astype(np.float64),triangles.astype(np.int64))
    np.savez_compressed(out/'source_cage_coverage.npz',inside=winding>.5,distances=np.sqrt(squared),winding=winding,source_vertex_ids=z['ids'])
label, count = ndimage.label(volume)
sizes = np.bincount(label.ravel())[1:]
np.savez_compressed(out/'geometric_volume.npz', vertices=vertices,
    triangles=triangles, source_vertex_ids=z['ids'], source_clump_labels=z['chain_labels'])
report = dict(method='Unsigned triangle voxelization + binary dilation/closing + static skin-band CSG + Lewiner marching cubes',
    not_an_animation_solver=True, pitch_m=pitch, surface_dilation_voxels=2,
    closing_ball_radius_voxels=3, skin_band_exclusion_m=.005,
    source_hair_vertices=len(x), source_hair_triangles=len(z['faces']),
    vertices=len(vertices), triangles=len(triangles), volume_components=int(count),
    component_voxel_counts=sorted(map(int,sizes),reverse=True),
    removed_display_vertices=0, removed_unrooted_components=0,
    static_csg_dust_components_removed=len(dust),static_csg_dust_voxels_removed=dust_voxels,
    manifold_cleanup=a.manifold_clean,cleanup=cleanup,
    versions=dict(numpy=np.__version__,scipy=scipy.__version__,skimage=skimage.__version__,trimesh=trimesh.__version__),
    physics_started=False)
(out/'volume_asset.json').write_text(json.dumps(report,indent=2),'utf8')
progress('STATIC_VOLUME_ASSET_READY', **report)
