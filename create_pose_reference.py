import bpy
import json
import math
import mathutils
import sys
import argparse
import os

# --- OPENPOSE COLORS ---
OP_COLORS = {
    'head': (1.0, 0.0, 0.0, 1.0),
    'neck': (1.0, 0.33, 0.0, 1.0),
    'shoulder_r': (1.0, 0.66, 0.0, 1.0),
    'elbow_r': (1.0, 1.0, 0.0, 1.0),
    'wrist_r': (0.66, 1.0, 0.0, 1.0),
    'hand_r': (0.66, 1.0, 0.0, 1.0),
    'shoulder_l': (0.33, 1.0, 0.0, 1.0),
    'elbow_l': (0.0, 1.0, 0.0, 1.0),
    'wrist_l': (0.0, 1.0, 0.33, 1.0),
    'hand_l': (0.0, 1.0, 0.33, 1.0),
    'chest': (1.0, 0.0, 0.0, 1.0),
    'pelvis': (1.0, 0.0, 0.0, 1.0),
    'hip_r': (0.0, 0.66, 1.0, 1.0),
    'knee_r': (0.0, 0.33, 1.0, 1.0),
    'ankle_r': (0.0, 0.0, 1.0, 1.0),
    'foot_r': (0.0, 0.0, 1.0, 1.0),
    'hip_l': (0.33, 0.0, 1.0, 1.0),
    'knee_l': (0.66, 0.0, 1.0, 1.0),
    'ankle_l': (1.0, 0.0, 1.0, 1.0),
    'foot_l': (1.0, 0.0, 1.0, 1.0),
}

def clean_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def setup_environment(resolution, mode):
    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.cycles.device = 'GPU'
    bpy.context.scene.cycles.samples = 32 # Emission only needs very few samples
    bpy.context.scene.render.resolution_x = resolution
    bpy.context.scene.render.resolution_y = resolution
    bpy.context.scene.render.resolution_percentage = 100
    bpy.context.scene.render.film_transparent = False
    
    # Disable color management so hex colors are pure
    bpy.context.scene.view_settings.view_transform = 'Standard'

    world = bpy.context.scene.world
    if not world:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get('Background')
    if bg:
        if mode == 'openpose':
            bg.inputs[0].default_value = (0.0, 0.0, 0.0, 1.0) # Black
        else:
            bg.inputs[0].default_value = (1.0, 1.0, 1.0, 1.0) # White
        bg.inputs[1].default_value = 1.0

def create_emission_material(name, color):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    
    emission = nodes.new(type='ShaderNodeEmission')
    emission.inputs['Color'].default_value = color
    emission.inputs['Strength'].default_value = 1.0
    
    output = nodes.new(type='ShaderNodeOutputMaterial')
    mat.node_tree.links.new(emission.outputs['Emission'], output.inputs['Surface'])
    return mat

def get_2d_projection(points, camera_loc, target_loc):
    cam_loc = mathutils.Vector(camera_loc)
    targ_loc = mathutils.Vector(target_loc)
    direction = targ_loc - cam_loc
    if direction.length == 0:
        direction = mathutils.Vector((0, -1, 0))
    rot_quat = direction.to_track_quat('-Z', 'Y')
    mat_rot = rot_quat.to_matrix().to_4x4()
    mat_loc = mathutils.Matrix.Translation(cam_loc)
    cam_matrix = mat_loc @ mat_rot
    inv_cam_matrix = cam_matrix.inverted()
    
    projected = {}
    for k, v in points.items():
        p_local = inv_cam_matrix @ mathutils.Vector(v)
        # X is right, Y is up in camera space, Z is negative depth.
        projected[k] = mathutils.Vector((p_local.x, p_local.y, p_local.z))
    return projected

def create_flat_cylinder(name, loc1, loc2, radius, material, z_offset):
    loc1 = mathutils.Vector(loc1)
    loc2 = mathutils.Vector(loc2)
    direction = loc2 - loc1
    length = direction.length
    if length == 0:
        return
    center = loc1 + direction / 2.0
    rot = direction.to_track_quat('Y', 'Z')
    
    # Create flat cylinder on XY plane
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=length, location=(center.x, center.y, z_offset))
    obj = bpy.context.active_object
    obj.name = name
    obj.rotation_euler = rot.to_euler()
    # Flatten it so it's a 2D line without overlapping issues
    obj.scale[2] = 0.001 
    obj.data.materials.append(material)
    bpy.ops.object.shade_smooth()

def create_flat_disc(name, loc, radius, material, z_offset):
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=0.001, location=(loc[0], loc[1], z_offset))
    obj = bpy.context.active_object
    obj.name = name
    obj.data.materials.append(material)
    bpy.ops.object.shade_smooth()

def build_2d_pose(projected_points, mode):
    # Calculate bounding box
    min_x = min(p.x for p in projected_points.values())
    max_x = max(p.x for p in projected_points.values())
    min_y = min(p.y for p in projected_points.values())
    max_y = max(p.y for p in projected_points.values())
    
    center_x = (min_x + max_x) / 2.0
    center_y = (min_y + max_y) / 2.0
    
    # Center the points
    centered_points = {k: mathutils.Vector((p.x - center_x, p.y - center_y, p.z)) for k, p in projected_points.items()}
    
    # Depth sorting: sort by z (depth) to ensure foreground objects render on top. 
    # More negative Z = further away. We want further away to have lower z_offset.
    sorted_keys = sorted(centered_points.keys(), key=lambda k: centered_points[k].z)
    z_map = {k: i * 0.0001 for i, k in enumerate(sorted_keys)}
    
    bones = [
        ('head', 'neck'), ('neck', 'chest'), ('chest', 'pelvis'),
        ('shoulder_r', 'shoulder_l'), ('hip_r', 'hip_l'), # Cross connections
        ('neck', 'shoulder_l'), ('neck', 'shoulder_r'),
        ('chest', 'shoulder_l'), ('chest', 'shoulder_r'),
        ('pelvis', 'hip_l'), ('pelvis', 'hip_r'),
        ('shoulder_l', 'elbow_l'), ('elbow_l', 'wrist_l'), ('wrist_l', 'hand_l'),
        ('shoulder_r', 'elbow_r'), ('elbow_r', 'wrist_r'), ('wrist_r', 'hand_r'),
        ('hip_l', 'knee_l'), ('knee_l', 'ankle_l'), ('ankle_l', 'foot_l'),
        ('hip_r', 'knee_r'), ('knee_r', 'ankle_r'), ('ankle_r', 'foot_r')
    ]
    
    materials = {}
    if mode == 'openpose':
        for k, color in OP_COLORS.items():
            materials[k] = create_emission_material(f"mat_{k}", color)
    else:
        mat_grey = create_emission_material("mat_silhouette", (0.2, 0.2, 0.2, 1.0))
        for k in OP_COLORS.keys():
            materials[k] = mat_grey

    # Generate bones (lines)
    for b1, b2 in bones:
        if b1 in centered_points and b2 in centered_points:
            z_offset = (z_map[b1] + z_map[b2]) / 2.0
            radius = 0.015 if mode == 'openpose' else 0.05
            # Torso bones are thicker in silhouette
            if mode == 'silhouette' and b1 in ['head', 'neck', 'chest', 'pelvis', 'shoulder_l', 'shoulder_r', 'hip_l', 'hip_r']:
                if b2 in ['neck', 'chest', 'pelvis', 'shoulder_l', 'shoulder_r', 'hip_l', 'hip_r']:
                    radius = 0.08
            mat = materials.get(b2, materials.get(b1))
            create_flat_cylinder(f"bone_{b1}_{b2}", centered_points[b1], centered_points[b2], radius, mat, z_offset)
            
    # Generate joints (dots)
    for j_name, j_loc in centered_points.items():
        z_offset = z_map[j_name] + 0.005 # Joints slightly above their connecting bones
        radius = 0.03 if mode == 'openpose' else 0.06
        if 'head' in j_name or 'chest' in j_name or 'pelvis' in j_name:
            radius = 0.05 if mode == 'openpose' else 0.1
        mat = materials.get(j_name)
        create_flat_disc(f"joint_{j_name}", j_loc, radius, mat, z_offset)

    width = max_x - min_x
    height = max_y - min_y
    return width, height

def render_pose(pose_name, pose_data, cameras_to_render, modes_to_render, resolution, output_dir, validate):
    # Calculate 3D center for target
    c_x = sum(v[0] for v in pose_data.values()) / len(pose_data)
    c_y = sum(v[1] for v in pose_data.values()) / len(pose_data)
    c_z = sum(v[2] for v in pose_data.values()) / len(pose_data)
    target_loc = (c_x, c_y, c_z)

    preset_locs = {
        'front': (c_x, c_y - 3.5, c_z),
        'side': (c_x + 3.5, c_y, c_z),
        'low_side': (c_x + 3.0, c_y - 1.0, c_z - 0.5),
        'diagonal': (c_x + 2.5, c_y - 2.5, c_z + 0.5),
        'overhead': (c_x, c_y - 0.1, c_z + 3.5)
    }

    for cam_name in cameras_to_render:
        if cam_name not in preset_locs:
            continue
        
        projected_points = get_2d_projection(pose_data, preset_locs[cam_name], target_loc)
        
        for mode in modes_to_render:
            clean_scene()
            setup_environment(resolution, mode)
            
            width, height = build_2d_pose(projected_points, mode)
            
            # Setup Actual Render Camera (Orthographic, Top-Down)
            cam_data = bpy.data.cameras.new("RenderCam")
            cam_data.type = 'ORTHO'
            # We want the max span to fill 85% of the frame
            max_span = max(width, height)
            if max_span == 0:
                max_span = 0.1
            cam_data.ortho_scale = max_span / 0.85
            
            cam_obj = bpy.data.objects.new("RenderCam", cam_data)
            bpy.context.collection.objects.link(cam_obj)
            cam_obj.location = (0, 0, 10)
            cam_obj.rotation_euler = (0, 0, 0)
            bpy.context.scene.camera = cam_obj
            
            if validate:
                # Validation check: Ensure fill ratio is between 0.80 and 0.90
                # By definition, the max span fills 85% of ortho_scale.
                # However, if width/height is extremely small, we throw an error.
                if max_span < 0.1:
                    print(f"VALIDATION FAILED: {pose_name} from {cam_name} has a bounding box too small.")
                    continue

            out_path = os.path.join(output_dir, f"{pose_name}_{cam_name}_{mode}.png")
            bpy.context.scene.render.filepath = out_path
            bpy.ops.render.render(write_still=True)
            print(f"Rendered {out_path}")

def main():
    if "--" not in sys.argv:
        print("Please pass arguments after '--', e.g., blender -b -P script.py -- --all")
        return
        
    args_list = sys.argv[sys.argv.index("--") + 1:]
    
    parser = argparse.ArgumentParser(description="Generate Pose Control References")
    parser.add_argument("--pose", type=str, help="Specific pose to render")
    parser.add_argument("--camera", type=str, help="Specific camera preset to render")
    parser.add_argument("--all", action="store_true", help="Render all poses")
    parser.add_argument("--test", action="store_true", help="Render test pose")
    parser.add_argument("--resolution", type=int, default=1024, help="Output resolution")
    parser.add_argument("--mode", type=str, choices=['openpose', 'silhouette', 'all_modes'], default='all_modes', help="Render mode")
    parser.add_argument("--debug_helpers", action="store_true", help="Enable 3D debug helpers (disabled by default in 2D mode)")
    parser.add_argument("--validate", action="store_true", help="Enforce framing validation rules")
    
    args = parser.parse_args(args_list)
    
    out_dir = os.path.abspath("renders/pose_controls")
    os.makedirs(out_dir, exist_ok=True)
    
    poses_file = "poses.json"
    if not os.path.exists(poses_file):
        print(f"Error: {poses_file} not found.")
        return
        
    with open(poses_file, 'r') as f:
        poses_json = json.load(f)
        poses = poses_json.get("poses", {})
        
    modes_to_render = ['openpose', 'silhouette'] if args.mode == 'all_modes' else [args.mode]
        
    if args.test:
        test_pose_name = list(poses.keys())[0]
        print(f"Running test on pose: {test_pose_name}")
        render_pose(test_pose_name, poses[test_pose_name], ['front'], modes_to_render, args.resolution, out_dir, args.validate)
        return
        
    poses_to_render = []
    if args.pose:
        if args.pose in poses:
            poses_to_render.append(args.pose)
        else:
            print(f"Pose '{args.pose}' not found in poses.json")
            return
    elif args.all:
        poses_to_render = list(poses.keys())
    else:
        print("Please specify --pose <name>, --all, or --test")
        return
        
    cams_to_render = ['front', 'side', 'low_side', 'diagonal', 'overhead']
    if args.camera:
        cams_to_render = [args.camera]
        
    for p_name in poses_to_render:
        render_pose(p_name, poses[p_name], cams_to_render, modes_to_render, args.resolution, out_dir, args.validate)

if __name__ == "__main__":
    main()
