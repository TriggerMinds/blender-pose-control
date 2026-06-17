import json
import os
import sys
import argparse
import math

GROK_EXTEND_TEMPLATE = """Use the final frame as the exact first frame of a 6-second continuation. Preserve the same subject, outfit state, room layout, lighting direction, camera angle, anatomy, fabric behavior and photorealistic continuity.

{camera_move} {body_move} Do not combine multiple actions. Do not reset the scene. Do not reinterpret the pose.

Increase visual tension through camera proximity, body-line geometry, subtle weight shift, breathing, hand pressure, fabric tension, surface compression, flash or light falloff and shadow depth.

Timing: first second stays locked to the current frame. Middle seconds introduce one controlled camera move and one controlled body move. Final second settles into the strongest composition.

Keep the motion physically coherent, photorealistic and continuous. No new people, no new props, no outfit change, no scene reset, no camera teleportation, no broken hands, no warped limbs, no changed identity."""

def parse_args():
    in_blender = False
    try:
        import bpy
        in_blender = True
    except ImportError:
        pass

    args_list = sys.argv[1:]
    if in_blender and "--" in sys.argv:
        args_list = sys.argv[sys.argv.index("--") + 1:]
    
    parser = argparse.ArgumentParser(description="Professional 3D Body/Pose Proxy & Keyframe-Reference Generator")
    parser.add_argument("--input_image", type=str, help="Path to input reference image")
    parser.add_argument("--pose_json", type=str, default="scene_proxy.json", help="JSON defining the proxy scene")
    parser.add_argument("--camera_match", action="store_true", help="Match camera to json and render overlay")
    parser.add_argument("--render_preview", action="store_true", help="Render all 3D previews")
    parser.add_argument("--generate_prompt", action="store_true", help="Generate Grok text prompts")
    parser.add_argument("--all", action="store_true", help="Run full pipeline")
    return parser.parse_args(args_list)

def build_proxy_scene(scene_data):
    import bpy
    import mathutils
    
    # Clear scene
    bpy.ops.wm.read_factory_settings(use_empty=True)
    
    # Render settings
    bpy.context.scene.render.engine = 'CYCLES'
    if bpy.app.version >= (3, 0, 0):
        bpy.context.scene.cycles.device = 'GPU'
    bpy.context.scene.render.resolution_x = 1024
    bpy.context.scene.render.resolution_y = 1024
    
    # World
    world = bpy.data.worlds.new("ProxyWorld")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get('Background')
    if bg: bg.inputs[0].default_value = (0.05, 0.05, 0.05, 1.0)
    
    # Materials
    mat_proxy = bpy.data.materials.new(name="ProxySkin")
    mat_proxy.use_nodes = True
    bsdf = mat_proxy.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (0.6, 0.6, 0.6, 1.0)
        bsdf.inputs['Roughness'].default_value = 0.5

    mat_env = bpy.data.materials.new(name="EnvironmentBlock")
    mat_env.use_nodes = True
    bsdf_env = mat_env.node_tree.nodes.get("Principled BSDF")
    if bsdf_env:
        bsdf_env.inputs['Base Color'].default_value = (0.2, 0.2, 0.25, 1.0)
        bsdf_env.inputs['Roughness'].default_value = 0.9
        
    # Build Environment
    for env in scene_data.get("environment", []):
        loc = env.get("location", [0,0,0])
        dim = env.get("dimensions", [1,1,1])
        if env.get("type") == "box":
            bpy.ops.mesh.primitive_cube_add(location=loc)
            obj = bpy.context.active_object
            obj.scale = (dim[0]/2, dim[1]/2, dim[2]/2)
            obj.data.materials.append(mat_env)
        elif env.get("type") == "plane":
            bpy.ops.mesh.primitive_plane_add(size=1, location=loc)
            obj = bpy.context.active_object
            obj.scale = (dim[0], dim[1], 1)
            obj.data.materials.append(mat_env)
            
    # Build Pose Proxy
    pose = scene_data.get("pose", {})
    # Joints
    for j_name, j_loc in pose.items():
        radius = 0.08 if 'head' in j_name or 'chest' in j_name or 'pelvis' in j_name else 0.04
        if 'head' in j_name: radius = 0.12
        bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=j_loc)
        obj = bpy.context.active_object
        obj.data.materials.append(mat_proxy)
        bpy.ops.object.shade_smooth()

    # Capsules/Bones
    bones = [
        ('head', 'neck'), ('neck', 'chest'), ('chest', 'pelvis'),
        ('shoulder_r', 'shoulder_l'), ('hip_r', 'hip_l'),
        ('neck', 'shoulder_l'), ('neck', 'shoulder_r'),
        ('pelvis', 'hip_l'), ('pelvis', 'hip_r'),
        ('shoulder_l', 'elbow_l'), ('elbow_l', 'wrist_l'), ('wrist_l', 'hand_l'),
        ('shoulder_r', 'elbow_r'), ('elbow_r', 'wrist_r'), ('wrist_r', 'hand_r'),
        ('hip_l', 'knee_l'), ('knee_l', 'ankle_l'), ('ankle_l', 'foot_l'),
        ('hip_r', 'knee_r'), ('knee_r', 'ankle_r'), ('ankle_r', 'foot_r')
    ]
    for b1, b2 in bones:
        if b1 in pose and b2 in pose:
            loc1 = mathutils.Vector(pose[b1])
            loc2 = mathutils.Vector(pose[b2])
            direction = loc2 - loc1
            length = direction.length
            if length == 0: continue
            center = loc1 + direction / 2.0
            rot = direction.to_track_quat('Z', 'Y')
            
            thickness = 0.08 if 'chest' in b1 or 'pelvis' in b1 or 'neck' in b1 else 0.05
            if 'hip' in b1 and 'knee' in b2: thickness = 0.07
            
            bpy.ops.mesh.primitive_cylinder_add(radius=thickness, depth=length, location=center)
            obj = bpy.context.active_object
            obj.rotation_euler = rot.to_euler()
            obj.data.materials.append(mat_proxy)
            bpy.ops.object.shade_smooth()

    # Lighting
    light_data = bpy.data.lights.new(name="AreaLight", type='AREA')
    light_data.energy = 200.0
    light_data.size = 2.0
    light_ob = bpy.data.objects.new(name="AreaLight", object_data=light_data)
    bpy.context.collection.objects.link(light_ob)
    light_ob.location = (2, -2, 3)
    light_ob.rotation_euler = (math.radians(45), 0, math.radians(45))
    
    light2 = bpy.data.lights.new(name="FillLight", type='AREA')
    light2.energy = 50.0
    light2.size = 3.0
    light2_ob = bpy.data.objects.new(name="FillLight", object_data=light2)
    bpy.context.collection.objects.link(light2_ob)
    light2_ob.location = (-2, -1, 1)
    light2_ob.rotation_euler = (math.radians(60), 0, math.radians(-45))

def setup_camera(cam_data, image_path=None):
    import bpy
    cam_loc = cam_data.get("location", [0, -3, 1])
    look_at = cam_data.get("look_at", [0, 0, 0])
    
    cam = bpy.data.cameras.new("MatchCam")
    cam.lens = cam_data.get("focal_length", 50.0)
    cam_obj = bpy.data.objects.new("MatchCam", cam)
    bpy.context.collection.objects.link(cam_obj)
    cam_obj.location = cam_loc
    
    ttc = cam_obj.constraints.new(type='TRACK_TO')
    target = bpy.data.objects.new("CamTarget", None)
    bpy.context.collection.objects.link(target)
    target.location = look_at
    ttc.target = target
    ttc.track_axis = 'TRACK_NEGATIVE_Z'
    ttc.up_axis = 'UP_Y'
    
    bpy.context.scene.camera = cam_obj
    
    if image_path:
        abs_image_path = os.path.abspath(image_path)
        if os.path.exists(abs_image_path):
            cam.show_background_images = True
            bg = cam.background_images.new()
            img = bpy.data.images.load(abs_image_path)
            bg.image = img
            bg.alpha = 0.5
            bg.display_depth = 'FRONT'
        else:
            print(f"Warning: Image not found at {abs_image_path}")
        
    return cam_obj

def render_scene(output_path):
    import bpy
    bpy.context.scene.render.filepath = output_path
    bpy.ops.render.render(write_still=True)
    print(f"Rendered: {output_path}")

def generate_prompts(scene_data, output_dir):
    meta = scene_data.get("metadata", {})
    desc = meta.get("pose_description", "")
    cam_move = meta.get("camera_move", "")
    body_move = meta.get("body_move", "")
    
    kf_path = os.path.join(output_dir, "grok_keyframe_prompt.txt")
    with open(kf_path, "w") as f:
        f.write(f"Photorealistic cinematic shot. {desc} High visual tension, detailed anatomy, hyper-realistic lighting, 8k resolution.")
        
    ext_path = os.path.join(output_dir, "grok_extend_prompt.txt")
    extend_prompt = GROK_EXTEND_TEMPLATE.format(camera_move=cam_move, body_move=body_move)
    with open(ext_path, "w") as f:
        f.write(extend_prompt)
        
    sum_path = os.path.join(output_dir, "scene_proxy_summary.json")
    with open(sum_path, "w") as f:
        json.dump({
            "status": "success",
            "proxy_type": "Neutral 3D Primitive Proxy",
            "metadata_used": meta,
            "environment_blocks": len(scene_data.get("environment", []))
        }, f, indent=4)
        
    print(f"Generated text prompts in {output_dir}")

def main():
    args = parse_args()
    
    if not os.path.exists(args.pose_json):
        print(f"Error: {args.pose_json} not found.")
        sys.exit(1)
        
    with open(args.pose_json, 'r') as f:
        scene_data = json.load(f)
        
    out_renders = os.path.abspath("renders/proxy_preview")
    out_prompts = os.path.abspath("outputs")
    os.makedirs(out_renders, exist_ok=True)
    os.makedirs(out_prompts, exist_ok=True)
    
    if args.generate_prompt or args.all:
        generate_prompts(scene_data, out_prompts)
        
    if args.render_preview or args.camera_match or args.all:
        try:
            import bpy
            build_proxy_scene(scene_data)
            cam = setup_camera(scene_data.get("camera", {}), args.input_image)
            
            # 1. Target Keyframe (Clean)
            render_scene(os.path.join(out_renders, "target_keyframe.png"))
            
            # 2. Camera Match (With background image)
            if args.input_image and os.path.exists(args.input_image):
                bpy.context.scene.render.film_transparent = True
                render_scene(os.path.join(out_renders, "camera_match.png"))
                bpy.context.scene.render.film_transparent = False
                
            # 3. Front Ortho
            cam.data.type = 'ORTHO'
            cam.data.ortho_scale = 3.0
            cam.location = (0, -4, 0)
            target = bpy.data.objects.get("CamTarget")
            if target: target.location = (0,0,0)
            render_scene(os.path.join(out_renders, "front.png"))
            
        except ImportError:
            print("Error: Blender environment not detected. Cannot render 3D previews. Run via 'blender -b -P'.")

if __name__ == "__main__":
    main()
