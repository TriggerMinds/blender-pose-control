# Blender Pose Control Generator (2D OpenPose & Silhouette)

This headless Blender Python automation tool generates pure 2D pose-control reference images. These images are perfectly flat, shadowless, and optimized for Grok Imagine ControlNet pose transfer.

The tool strictly avoids 3D perspective occlusion by projecting the 3D joint coordinates from `poses.json` onto the chosen camera's local 2D view plane. It then procedurally draws standard OpenPose colored maps and dark grey silhouettes on a flat surface, ensuring maximum readability.

## Features
- **Auto-framing**: Dynamically computes the projected bounding box of all joints to tightly scale the orthographic camera. Guarantees 85% frame fill.
- **OpenPose Mode**: Pure emission bright colors on a black background. Maps standard RGB joint/limb combinations.
- **Silhouette Mode**: Flat, thick dark grey capsule limbs on a white background to guide mass positioning.
- **Validation Rules**: Ensures images are rendered natively at 1024x1024 without wasteful empty margins.

## Installation Assumptions
- Blender 3.0+ or 4.0+ is installed.
- `blender` is in your system's PATH.

## Commands

Run these commands from the root directory (`C:\AI\blender-pose-control`).

### Render All Modes and Angles
Renders every pose from all 5 angles (front, side, low_side, diagonal, overhead), outputting both OpenPose and Silhouette modes:
```powershell
blender -b -P .\create_pose_reference.py -- --all --mode all_modes
```

### Specific Pose & Mode
Render a specific pose in OpenPose mode only:
```powershell
blender -b -P .\create_pose_reference.py -- --pose "Standing_Weight_Shift" --mode openpose
```

### Enable Validation
Enforce strict bounding box checks to ensure the pose fills 80-90% of the screen. If it doesn't, the script will skip the render and throw a warning:
```powershell
blender -b -P .\create_pose_reference.py -- --all --validate
```

### Test Mode
Render the first pose in the JSON from the front view to quickly verify settings:
```powershell
blender -b -P .\create_pose_reference.py -- --test
```

## Adding Custom Poses
1. Open `poses.json`.
2. Add a new key under `"poses"`.
3. Provide normalized 3D coordinates `[X, Y, Z]` for the required joints.
   *(The script automatically centers these coordinates during projection).*
