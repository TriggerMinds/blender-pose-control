# Blender Pose Control Generator

This is a headless Blender Python automation tool that generates neutral pose-control reference images. These images are optimized for Grok Imagine image-to-video pose transfer.

## Installation Assumptions

1. **Blender**: Ensure Blender 3.0+ or 4.0+ is installed on your system.
2. **PATH Environment Variable**: Ensure the `blender` executable is added to your system's PATH.

## Overview

The generator runs completely headlessly. It procedurally constructs a basic mannequin from spheres and cylinders based on normalized 3D joint coordinates defined in `poses.json`. It also generates visual helpers (spine curve, shoulder/hip axes, contact points, and weight/camera arrows).

## Commands

Run these commands from the root directory of this project (`C:\AI\blender-pose-control`).

### Test Run
Render a quick test using the first pose in your JSON, outputting to the `front` camera at 1024x1024:
```powershell
blender -b -P .\create_pose_reference.py -- --test
```

### Render One Pose
Render a specific pose across all 5 camera angles:
```powershell
blender -b -P .\create_pose_reference.py -- --pose "Standing_Weight_Shift"
```

### Render All Poses
Render all poses across all camera angles, and generate a contact-sheet overview from the diagonal renders:
```powershell
blender -b -P .\create_pose_reference.py -- --all
```

### Custom Settings
You can combine arguments, specify a single camera, or change the resolution:
```powershell
blender -b -P .\create_pose_reference.py -- --pose "Seated_Side_Lean" --camera "diagonal" --resolution 2048
```

## How to Add New Poses

1. Open `poses.json`.
2. Add a new key under the `"poses"` object with your pose name (e.g., `"My_Custom_Pose"`).
3. Provide normalized 3D coordinates `[X, Y, Z]` for the required joints:
   `head, neck, chest, pelvis, shoulder_l, shoulder_r, elbow_l, elbow_r, wrist_l, wrist_r, hand_l, hand_r, hip_l, hip_r, knee_l, knee_r, ankle_l, ankle_r, foot_l, foot_r`
   
*(Note: X is roughly Left/Right, Y is Front/Back, Z is Up/Down. Assume Z=0 is floor level. A value of Z <= 0.06 automatically generates a surface contact point).*
