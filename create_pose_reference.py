import json
import sys
import argparse
import os

GROK_EXTEND_TEMPLATE = """Use the final frame as the exact first frame of a 6-second continuation. Preserve the same subject, outfit state, room layout, lighting direction, camera angle, anatomy, fabric behavior and photorealistic continuity.

{camera_move} {body_move} Do not combine multiple actions. Do not reset the scene. Do not reinterpret the pose.

Increase visual tension through camera proximity, body-line geometry, subtle weight shift, breathing, hand pressure, fabric tension, surface compression, flash or light falloff and shadow depth.

Timing: first second stays locked to the current frame. Middle seconds introduce one controlled camera move and one controlled body move. Final second settles into the strongest composition.

Keep the motion physically coherent, photorealistic and continuous. No new people, no new props, no outfit change, no scene reset, no camera teleportation, no broken hands, no warped limbs, no changed identity."""

def generate_text_prompts(pose_name, pose_data, output_dir):
    desc_path = os.path.join(output_dir, f"{pose_name}_target_pose_description.txt")
    keyframe_path = os.path.join(output_dir, f"{pose_name}_grok_keyframe_prompt.txt")
    extend_path = os.path.join(output_dir, f"{pose_name}_grok_extend_prompt.txt")
    
    desc = pose_data.get("pose_description", "")
    cam_move = pose_data.get("camera_move", "")
    body_move = pose_data.get("body_move", "")
    
    with open(desc_path, "w") as f:
        f.write(desc)
        
    with open(keyframe_path, "w") as f:
        f.write(f"Photorealistic cinematic shot. {desc} High visual tension, detailed anatomy, hyper-realistic lighting, 8k resolution.")
        
    extend_prompt = GROK_EXTEND_TEMPLATE.format(camera_move=cam_move, body_move=body_move)
    with open(extend_path, "w") as f:
        f.write(extend_prompt)
        
    print(f"Generated text prompts for {pose_name}")

def render_preview(pose_name, pose_data, output_dir):
    try:
        import bpy
        import mathutils
        import math
    except ImportError:
        print("Blender (bpy) not available in this environment. Skipping 3D preview.")
        return
        
    print(f"Generating 3D preview for {pose_name}...")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    
    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.render.resolution_x = 1024
    bpy.context.scene.render.resolution_y = 1024
    
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get('Background')
    if bg:
        bg.inputs[0].default_value = (0.2, 0.2, 0.2, 1.0)
    
    mat_grey = bpy.data.materials.new(name="MatteGrey")
    mat_grey.use_nodes = True
    bsdf = mat_grey.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (0.5, 0.5, 0.5, 1.0)
        bsdf.inputs['Roughness'].default_value = 0.8
        
    # Joints
    for j_name, j_loc in pose_data.items():
        if not isinstance(j_loc, list) or len(j_loc) != 3:
            continue
        radius = 0.08 if 'head' in j_name or 'chest' in j_name or 'pelvis' in j_name else 0.05
        bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=j_loc)
        obj = bpy.context.active_object
        obj.data.materials.append(mat_grey)
        bpy.ops.object.shade_smooth()

    # Bones
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
        if b1 in pose_data and b2 in pose_data:
            loc1 = mathutils.Vector(pose_data[b1])
            loc2 = mathutils.Vector(pose_data[b2])
            direction = loc2 - loc1
            length = direction.length
            if length == 0: continue
            center = loc1 + direction / 2.0
            rot = direction.to_track_quat('Z', 'Y')
            bpy.ops.mesh.primitive_cylinder_add(radius=0.04, depth=length, location=center)
            obj = bpy.context.active_object
            obj.rotation_euler = rot.to_euler()
            obj.data.materials.append(mat_grey)
            bpy.ops.object.shade_smooth()
            
    c_x = sum(v[0] for k,v in pose_data.items() if isinstance(v, list)) / 20.0
    c_y = sum(v[1] for k,v in pose_data.items() if isinstance(v, list)) / 20.0
    c_z = sum(v[2] for k,v in pose_data.items() if isinstance(v, list)) / 20.0
    
    cam_data = bpy.data.cameras.new("PreviewCam")
    cam_obj = bpy.data.objects.new("PreviewCam", cam_data)
    bpy.context.collection.objects.link(cam_obj)
    cam_obj.location = (c_x + 3.0, c_y - 3.0, c_z + 1.0)
    
    ttc = cam_obj.constraints.new(type='TRACK_TO')
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(c_x, c_y, c_z))
    ttc.target = bpy.context.active_object
    ttc.track_axis = 'TRACK_NEGATIVE_Z'
    ttc.up_axis = 'UP_Y'
    
    bpy.context.scene.camera = cam_obj
    
    light_data = bpy.data.lights.new(name="Light", type='SUN')
    light_data.energy = 2.0
    light_ob = bpy.data.objects.new(name="Light", object_data=light_data)
    bpy.context.collection.objects.link(light_ob)
    light_ob.rotation_euler = (math.radians(45), 0, math.radians(45))
    
    out_path = os.path.join(output_dir, f"{pose_name}_preview.png")
    bpy.context.scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)
    print(f"Preview saved to {out_path}")

def main():
    # Detect if running via Blender or standard Python
    in_blender = False
    try:
        import bpy
        in_blender = True
    except ImportError:
        pass

    args_list = sys.argv[1:]
    if in_blender and "--" in sys.argv:
        args_list = sys.argv[sys.argv.index("--") + 1:]
    
    parser = argparse.ArgumentParser(description="Grok Keyframe & Prompt Generator")
    parser.add_argument("--pose", type=str, help="Specific pose to generate")
    parser.add_argument("--all", action="store_true", help="Generate all poses")
    parser.add_argument("--preview", action="store_true", help="Generate a simple 3D mannequin preview PNG (Requires Blender)")
    
    args = parser.parse_args(args_list)
    
    out_dir = os.path.abspath("renders/grok_prompts")
    os.makedirs(out_dir, exist_ok=True)
    
    poses_file = "poses.json"
    if not os.path.exists(poses_file):
        print(f"Error: {poses_file} not found.")
        return
        
    with open(poses_file, 'r') as f:
        poses_json = json.load(f)
        poses = poses_json.get("poses", {})
        
    poses_to_run = []
    if args.pose:
        if args.pose in poses:
            poses_to_run.append(args.pose)
        else:
            print(f"Pose '{args.pose}' not found in poses.json")
            return
    elif args.all:
        poses_to_run = list(poses.keys())
    else:
        print("Please specify --pose <name> or --all")
        return
        
    for p_name in poses_to_run:
        generate_text_prompts(p_name, poses[p_name], out_dir)
        if args.preview:
            render_preview(p_name, poses[p_name], out_dir)

if __name__ == "__main__":
    main()
