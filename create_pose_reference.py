import bpy
import json
import math
import mathutils
import sys
import argparse
import os

def clean_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def setup_environment(resolution):
    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.cycles.device = 'GPU'
    bpy.context.scene.cycles.samples = 128
    bpy.context.scene.render.resolution_x = resolution
    bpy.context.scene.render.resolution_y = resolution
    bpy.context.scene.render.resolution_percentage = 100
    bpy.context.scene.render.film_transparent = False

    world = bpy.context.scene.world
    if not world:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get('Background')
    if bg:
        bg.inputs[0].default_value = (0.9, 0.9, 0.9, 1.0) # Plain neutral background
        bg.inputs[1].default_value = 1.0

    light_data = bpy.data.lights.new(name="KeyLight", type='SUN')
    light_data.energy = 3.0
    light_ob = bpy.data.objects.new(name="KeyLight", object_data=light_data)
    bpy.context.collection.objects.link(light_ob)
    light_ob.location = (5, -5, 10)
    light_ob.rotation_euler = (math.radians(45), 0, math.radians(45))
    
    light_data_fill = bpy.data.lights.new(name="FillLight", type='SUN')
    light_data_fill.energy = 1.0
    light_ob_fill = bpy.data.objects.new(name="FillLight", object_data=light_data_fill)
    bpy.context.collection.objects.link(light_ob_fill)
    light_ob_fill.location = (-5, 5, 5)
    light_ob_fill.rotation_euler = (math.radians(45), 0, math.radians(-135))

def create_material(name, color, roughness=0.8):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs['Base Color'].default_value = color
        bsdf.inputs['Roughness'].default_value = roughness
    return mat

def create_sphere(name, location, radius, material):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.data.materials.append(material)
    bpy.ops.object.shade_smooth()
    return obj

def create_cylinder(name, loc1, loc2, radius, material):
    loc1 = mathutils.Vector(loc1)
    loc2 = mathutils.Vector(loc2)
    direction = loc2 - loc1
    length = direction.length
    if length == 0:
        return None
    center = loc1 + direction / 2.0
    rot = direction.to_track_quat('Z', 'Y')
    
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=length, location=center)
    obj = bpy.context.active_object
    obj.name = name
    obj.rotation_euler = rot.to_euler()
    obj.data.materials.append(material)
    bpy.ops.object.shade_smooth()
    return obj

def create_arrow(name, loc, direction, length, material):
    # Base cylinder
    dir_vec = mathutils.Vector(direction).normalized()
    end_loc = mathutils.Vector(loc) + dir_vec * (length * 0.7)
    create_cylinder(name + "_base", loc, end_loc, 0.02, material)
    
    # Cone head
    cone_loc = end_loc + dir_vec * (length * 0.15)
    rot = dir_vec.to_track_quat('Z', 'Y')
    bpy.ops.mesh.primitive_cone_add(radius1=0.06, depth=length*0.3, location=cone_loc)
    obj = bpy.context.active_object
    obj.name = name + "_head"
    obj.rotation_euler = rot.to_euler()
    obj.data.materials.append(material)

def build_pose(pose_data, pose_name):
    mat_grey = create_material("MatteGrey", (0.5, 0.5, 0.5, 1.0))
    mat_helper_red = create_material("HelperRed", (0.8, 0.1, 0.1, 1.0))
    mat_helper_blue = create_material("HelperBlue", (0.1, 0.1, 0.8, 1.0))
    mat_helper_green = create_material("HelperGreen", (0.1, 0.8, 0.1, 1.0))
    mat_helper_yellow = create_material("HelperYellow", (0.8, 0.8, 0.1, 1.0))
    
    joints = pose_data
    spheres = {}
    
    # Create joints
    for j_name, j_loc in joints.items():
        radius = 0.06 if 'head' in j_name or 'chest' in j_name or 'pelvis' in j_name else 0.04
        # markers have distinct colors
        mat = mat_grey
        if j_name in ['elbow_l', 'elbow_r', 'wrist_l', 'wrist_r', 'knee_l', 'knee_r', 'ankle_l', 'ankle_r', 'hand_l', 'hand_r']:
            mat = mat_helper_blue
        obj = create_sphere(j_name, j_loc, radius, mat)
        spheres[j_name] = obj

    # Limbs connectivity
    bones = [
        ('head', 'neck'), ('neck', 'chest'), ('chest', 'pelvis'),
        ('neck', 'shoulder_l'), ('neck', 'shoulder_r'),
        ('shoulder_l', 'elbow_l'), ('elbow_l', 'wrist_l'), ('wrist_l', 'hand_l'),
        ('shoulder_r', 'elbow_r'), ('elbow_r', 'wrist_r'), ('wrist_r', 'hand_r'),
        ('pelvis', 'hip_l'), ('pelvis', 'hip_r'),
        ('hip_l', 'knee_l'), ('knee_l', 'ankle_l'), ('ankle_l', 'foot_l'),
        ('hip_r', 'knee_r'), ('knee_r', 'ankle_r'), ('ankle_r', 'foot_r')
    ]
    
    for b1, b2 in bones:
        if b1 in joints and b2 in joints:
            create_cylinder(f"bone_{b1}_{b2}", joints[b1], joints[b2], 0.03, mat_grey)
            
    # Geometry Helpers
    # Shoulder Axis
    if 'shoulder_l' in joints and 'shoulder_r' in joints:
        create_cylinder("helper_shoulder_axis", joints['shoulder_l'], joints['shoulder_r'], 0.015, mat_helper_red)
        
    # Hip Axis
    if 'hip_l' in joints and 'hip_r' in joints:
        create_cylinder("helper_hip_axis", joints['hip_l'], joints['hip_r'], 0.015, mat_helper_red)
        
    # Spine Curve (Bezier)
    curve_data = bpy.data.curves.new('spine_curve', type='CURVE')
    curve_data.dimensions = '3D'
    curve_data.bevel_depth = 0.01
    spline = curve_data.splines.new('BEZIER')
    spine_pts = ['pelvis', 'chest', 'neck', 'head']
    spline.bezier_points.add(len(spine_pts)-1)
    for i, pt in enumerate(spine_pts):
        if pt in joints:
            spline.bezier_points[i].co = joints[pt]
            spline.bezier_points[i].handle_left_type = 'AUTO'
            spline.bezier_points[i].handle_right_type = 'AUTO'
    curve_obj = bpy.data.objects.new('helper_spine', curve_data)
    bpy.context.collection.objects.link(curve_obj)
    curve_obj.data.materials.append(mat_helper_green)
    
    # Surface contact points and weight arrows
    for j_name, j_loc in joints.items():
        if j_loc[2] <= 0.06: # Close to floor
            # Contact disc
            bpy.ops.mesh.primitive_cylinder_add(radius=0.1, depth=0.01, location=(j_loc[0], j_loc[1], 0.0))
            disc = bpy.context.active_object
            disc.name = f"contact_{j_name}"
            disc.data.materials.append(mat_helper_yellow)
            
            # Weight arrow
            create_arrow(f"weight_{j_name}", (j_loc[0], j_loc[1], j_loc[2] + 0.3), (0, 0, -1), 0.3, mat_helper_yellow)
            
    # Target empty for cameras
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0.8))
    target = bpy.context.active_object
    target.name = "CameraTarget"
    return target

def setup_cameras(target_obj):
    cameras = {}
    preset_locs = {
        'front': (0.0, -3.5, 0.8),
        'side': (3.5, 0.0, 0.8),
        'low_side': (3.0, -1.0, 0.2),
        'diagonal': (2.5, -2.5, 1.2),
        'overhead': (0.0, -0.5, 4.0)
    }
    
    for name, loc in preset_locs.items():
        cam_data = bpy.data.cameras.new(name)
        cam_obj = bpy.data.objects.new(name, cam_data)
        bpy.context.collection.objects.link(cam_obj)
        cam_obj.location = loc
        
        # Track constraint
        ttc = cam_obj.constraints.new(type='TRACK_TO')
        ttc.target = target_obj
        ttc.track_axis = 'TRACK_NEGATIVE_Z'
        ttc.up_axis = 'UP_Y'
        
        cameras[name] = cam_obj
        
    return cameras

def create_camera_arrow(cam_obj, target_obj, name):
    mat_helper_cyan = create_material("HelperCyan", (0.1, 0.8, 0.8, 1.0))
    # Arrow near the character pointing along camera direction
    dir_vec = target_obj.location - cam_obj.location
    dir_vec.normalize()
    # Place arrow slightly away from target
    loc = target_obj.location - dir_vec * 1.5
    create_arrow(f"cam_arrow_{name}", loc, dir_vec, 0.4, mat_helper_cyan)

def generate_contact_sheet(image_paths, output_path):
    print("Generating contact sheet...")
    clean_scene()
    setup_environment(2048) # Higher res for contact sheet
    
    # Create grid of planes
    n = len(image_paths)
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    
    plane_size = 2.0
    margin = 0.2
    
    cam_z = max(cols, rows) * 2.5
    bpy.ops.object.camera_add(location=(0, 0, cam_z))
    cam = bpy.context.active_object
    cam.rotation_euler = (0, 0, 0)
    bpy.context.scene.camera = cam
    
    start_x = -((cols - 1) * (plane_size + margin)) / 2.0
    start_y = ((rows - 1) * (plane_size + margin)) / 2.0
    
    light_data = bpy.data.lights.new(name="ContactLight", type='SUN')
    light_data.energy = 5.0
    light_ob = bpy.data.objects.new(name="ContactLight", object_data=light_data)
    bpy.context.collection.objects.link(light_ob)
    
    for i, path in enumerate(image_paths):
        r = i // cols
        c = i % cols
        x = start_x + c * (plane_size + margin)
        y = start_y - r * (plane_size + margin)
        
        bpy.ops.mesh.primitive_plane_add(size=plane_size, location=(x, y, 0))
        plane = bpy.context.active_object
        
        mat = bpy.data.materials.new(name=f"Mat_{i}")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
        img = bpy.data.images.load(path)
        tex.image = img
        mat.node_tree.links.new(bsdf.inputs['Base Color'], tex.outputs['Color'])
        
        # Unlit look
        bsdf.inputs['Roughness'].default_value = 1.0
        bsdf.inputs['Specular IOR Level'].default_value = 0.0
        
        plane.data.materials.append(mat)
        
    bpy.context.scene.render.filepath = output_path
    bpy.ops.render.render(write_still=True)
    print(f"Contact sheet saved to {output_path}")

def render_pose(pose_name, pose_data, cameras_to_render, resolution, output_dir):
    clean_scene()
    setup_environment(resolution)
    target = build_pose(pose_data, pose_name)
    cameras = setup_cameras(target)
    
    rendered_paths = []
    for cam_name in cameras_to_render:
        if cam_name not in cameras:
            continue
        bpy.context.scene.camera = cameras[cam_name]
        
        # Optional: create a camera direction arrow. 
        # But this would change per camera. Let's delete old camera arrows first
        for obj in bpy.context.scene.objects:
            if obj.name.startswith("cam_arrow_"):
                bpy.data.objects.remove(obj)
        create_camera_arrow(cameras[cam_name], target, cam_name)
        
        out_path = os.path.join(output_dir, f"{pose_name}_{cam_name}.png")
        bpy.context.scene.render.filepath = out_path
        bpy.ops.render.render(write_still=True)
        rendered_paths.append(out_path)
        print(f"Rendered {out_path}")
        
    return rendered_paths

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
        
    if args.test:
        test_pose_name = list(poses.keys())[0]
        print(f"Running test on pose: {test_pose_name}")
        render_pose(test_pose_name, poses[test_pose_name], ['front'], args.resolution, out_dir)
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
        
    all_diagonal_renders = []
    for p_name in poses_to_render:
        paths = render_pose(p_name, poses[p_name], cams_to_render, args.resolution, out_dir)
        for path in paths:
            if "diagonal" in path:
                all_diagonal_renders.append(path)
                
    if args.all and not args.camera and all_diagonal_renders:
        contact_sheet_path = os.path.join(out_dir, "contact_sheet_overview.png")
        generate_contact_sheet(all_diagonal_renders, contact_sheet_path)

if __name__ == "__main__":
    main()
