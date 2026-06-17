# Grok Imagine DAZ/Blender Proxy Pipeline

A professional tool that translates external 3D DAZ/Genesis meshes into neutral, non-identifying 3D proxy scenes in Blender, and generates highly specific text prompts for Grok Imagine's 6-second image-to-video extensions.

## Goal
To abandon "toy mannequins", blob maps, and OpenPose/ControlNet abstract maps. Grok Imagine requires human-readable keyframes and clear textual continuation prompts. This pipeline uses professional DAZ/Genesis topology imported into Blender to match real camera perspectives perfectly on an RTX 2060 SUPER 8GB.

## Features
- **DAZ/Genesis Import**: Natively supports importing high-quality `.obj` or `.fbx` external meshes.
- **Camera Matching**: Translates JSON spatial definitions into perfect Blender camera placements with reference image overlays.
- **Fast Rendering**: Uses Blender Eevee/Workbench to render lighting-fast, grey-shaded proxies on standard 8GB GPUs without photoreal rendering overhead.
- **Grok Prompt Engine**: Auto-generates deterministic text prompts forcing Grok to respect specific camera and body motion over a 6-second continuation.
- **Smoke-Test Mode**: Built-in `--use_placeholder` mode to verify the python pipeline works before acquiring heavy DAZ meshes.

## Usage

### 1. Configure the Scene
Edit `scene_proxy.json` to define your camera position, scene blockouts, and intended motion behaviors.

### 2. Run the Blender Camera Match
To import your DAZ mesh and render previews:
```powershell
blender -b -P .\blender_camera_match_template.py -- --mesh .\assets\posed_human.fbx --reference .\references\input.jpg --scene .\scene_proxy.json --all
```

*Don't have a DAZ mesh yet? Run a smoke-test:*
```powershell
blender -b -P .\blender_camera_match_template.py -- --use_placeholder --reference .\references\input.jpg --scene .\scene_proxy.json --all
```

### 3. Generate the Grok Prompt
```powershell
python .\grok_extend_prompt_generator.py --scene .\scene_proxy.json
```

## Hardware Profile
Optimized for: **Windows 11 | NVIDIA RTX 2060 SUPER (8GB VRAM)**.
Does not rely on heavy local PyTorch installations for mesh generation.
