import json
import os
import sys
import argparse
import math

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
    
    parser = argparse.ArgumentParser(description="Blender DAZ/Genesis Camera Match Proxy Generator")
    parser.add_argument("--mesh", type=str, help="Path to external .obj or .fbx DAZ mesh")
    parser.add_argument("--reference", type=str, help="Path to reference image overlay")
    parser.add_argument("--scene", type=str, default="scene_proxy.json", help="Path to scene JSON")
    parser.add_argument("--render_preview", action="store_true", help="Render camera matched preview")
    parser.add_argument("--target_preview", action="store_true", help="Render target keyframe preview")
    parser.add_argument("--all", action="store_true", help="Render everything")
    parser.add_argument("--use_placeholder", action="store_true", help="Use smoke-test primitive volume instead of DAZ mesh")
    return parser.parse_args(args_list)

def setup_blender_scene(scene_data):
    import bpy
    
    # Clear scene
    bpy.ops.wm.read_factory_settings(use_empty=True)
    
    # Render settings: Eevee by default for fast neutral proxies
    bpy.context.scene.render.engine = 'BLENDER_EEVEE_NEXT' if hasattr(bpy.types.Scene, 'eevee') else 'BLENDER_EEVEE'
    bpy.context.scene.render.resolution_x = 1024
    bpy.context.scene.render.resolution_y = 1024
    
    # World
    world = bpy.data.worlds.new("ProxyWorld")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get('Background')
    if bg: bg.inputs[0].default_value = (0.1, 0.1, 0.1, 1.0)
    
    # Environment Material
    mat_env = bpy.data.materials.new(name="EnvironmentBlock")
    mat_env.use_nodes = True
    bsdf_env = mat_env.node_tree.nodes.get("Principled BSDF")
    if bsdf_env:
        bsdf_env.inputs['Base Color'].default_value = (0.2, 0.2, 0.25, 1.0)
        bsdf_env.inputs['Roughness'].default_value = 0.9
        
    # Build Environment
    for env in scene_data.get("scene_blockout", []):
        loc = env.get("location", [0,0,0])
        dim = env.get("dimensions", [1,1,1])
        if env.get("type") == "box":
            bpy.ops.mesh.primitive_cube_add(location=loc)
            obj = bpy.context.active_object
            obj.scale = (dim[0]/2, dim[1]/2, dim[2]/2)
            obj.data.materials.append(mat_env)
            
    # Lighting
    light_data = bpy.data.lights.new(name="AreaLight", type='AREA')
    light_data.energy = 500.0
    light_data.size = 5.0
    light_ob = bpy.data.objects.new(name="AreaLight", object_data=light_data)
    bpy.context.collection.objects.link(light_ob)
    light_ob.location = (2, -2, 4)
    light_ob.rotation_euler = (math.radians(45), 0, math.radians(45))
    
    light2 = bpy.data.lights.new(name="FillLight", type='AREA')
    light2.energy = 100.0
    light2.size = 3.0
    light2_ob = bpy.data.objects.new(name="FillLight", object_data=light2)
    bpy.context.collection.objects.link(light2_ob)
    light2_ob.location = (-2, 2, 2)
    light2_ob.rotation_euler = (math.radians(60), 0, math.radians(-45))

def setup_camera(scene_data, ref_image=None):
    import bpy
    cam_data = scene_data.get("camera", {})
    cam_loc = cam_data.get("position", [0, -3, 1])
    cam_rot = cam_data.get("rotation", [math.radians(90), 0, 0])
    
    cam = bpy.data.cameras.new("ProxyCam")
    cam.lens = cam_data.get("focal_length", 50.0)
    cam.sensor_width = cam_data.get("sensor_width", 36.0)
    
    cam_obj = bpy.data.objects.new("ProxyCam", cam)
    bpy.context.collection.objects.link(cam_obj)
    cam_obj.location = cam_loc
    cam_obj.rotation_euler = cam_rot
    
    bpy.context.scene.camera = cam_obj
    
    if ref_image:
        abs_ref = os.path.abspath(ref_image)
        if os.path.exists(abs_ref):
            cam.show_background_images = True
            bg = cam.background_images.new()
            try:
                img = bpy.data.images.load(abs_ref)
                bg.image = img
                bg.alpha = 0.5
                bg.display_depth = 'FRONT'
            except Exception as e:
                print(f"Warning: Could not load background image {abs_ref}: {e}")
        else:
            print(f"Warning: Reference image not found at {abs_ref}")
            
    return cam_obj

def apply_neutral_material(obj):
    import bpy
    mat = bpy.data.materials.new(name="NeutralProxy")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (0.5, 0.5, 0.5, 1.0)
        bsdf.inputs['Roughness'].default_value = 0.6
        bsdf.inputs['Specular IOR Level'].default_value = 0.2
        
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)

def import_mesh(mesh_path):
    import bpy
    abs_path = os.path.abspath(mesh_path)
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"Mesh file not found: {abs_path}")
        
    ext = os.path.splitext(abs_path)[1].lower()
    
    # Store current objects to find the newly imported ones
    old_objs = set(bpy.context.scene.objects)
    
    if ext == '.fbx':
        bpy.ops.import_scene.fbx(filepath=abs_path)
    elif ext == '.obj':
        bpy.ops.wm.obj_import(filepath=abs_path)
    else:
        raise ValueError(f"Unsupported mesh format: {ext}. Use .fbx or .obj")
        
    new_objs = set(bpy.context.scene.objects) - old_objs
    
    for obj in new_objs:
        if obj.type == 'MESH':
            apply_neutral_material(obj)

def create_smoke_test_placeholder():
    import bpy
    # Creates a minimal placeholder (not a toy mannequin, just a literal volume for pipeline testing)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.3, depth=1.6, location=(0, 0, 0.8))
    obj = bpy.context.active_object
    obj.name = "TEST_PLACEHOLDER_VOLUME"
    
    # Add floating text to make it obvious
    bpy.ops.object.text_add(location=(0, 0, 1.8))
    txt = bpy.context.active_object
    txt.data.body = "TEST PLACEHOLDER"
    txt.rotation_euler = (math.radians(90), 0, 0)
    
    apply_neutral_material(obj)

def render_scene(output_path):
    import bpy
    bpy.context.scene.render.filepath = output_path
    bpy.ops.render.render(write_still=True)
    print(f"Rendered: {output_path}")

def main():
    args = parse_args()
    
    try:
        import bpy
    except ImportError:
        print("Error: Must be run inside Blender context. Run via 'blender -b -P script.py'")
        sys.exit(1)
        
    if not os.path.exists(args.scene):
        print(f"Error: Scene JSON not found at {args.scene}")
        sys.exit(1)
        
    with open(args.scene, 'r') as f:
        scene_data = json.load(f)
        
    # Setup base scene
    setup_blender_scene(scene_data)
    
    # Handle Mesh
    if args.mesh:
        print(f"Importing DAZ/Genesis Mesh: {args.mesh}")
        try:
            import_mesh(args.mesh)
        except Exception as e:
            print(f"Import Error: {e}")
            sys.exit(1)
    elif args.use_placeholder:
        print("WARNING: Using minimal smoke-test placeholder. This is not a valid proxy for final use.")
        create_smoke_test_placeholder()
    else:
        print("ERROR: No DAZ/Genesis --mesh provided. If you want to run a pipeline smoke-test, pass --use_placeholder.")
        sys.exit(1)
        
    # Setup Camera
    setup_camera(scene_data, args.reference)
    
    # Render Out
    out_dir = os.path.abspath(os.path.join("renders", "proxy_preview"))
    os.makedirs(out_dir, exist_ok=True)
    
    if args.render_preview or args.all:
        if args.reference:
            bpy.context.scene.render.film_transparent = True
        render_scene(os.path.join(out_dir, "camera_matched_proxy.png"))
        bpy.context.scene.render.film_transparent = False
        
    if args.target_preview or args.all:
        # Hide background image for target preview
        cam = bpy.context.scene.camera
        if cam and cam.data.background_images:
            cam.data.show_background_images = False
        render_scene(os.path.join(out_dir, "target_keyframe_preview.png"))

if __name__ == "__main__":
    main()
