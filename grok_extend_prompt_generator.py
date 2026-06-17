import json
import os
import argparse

def generate_prompt(scene_data):
    
    constraints = scene_data.get("grok_prompt_constraints", [])
    motion = scene_data.get("next_motion", {})
    
    lines = []
    lines.append(f"SCENE: {scene_data.get('project_name', 'Proxy')}")
    lines.append("-" * 40)
    lines.append("GROK IMAGINE EXTENSION PROMPT (6-SECONDS)")
    lines.append("-" * 40)
    
    # Core preservation commands
    lines.append("CORE INSTRUCTIONS:")
    for c in constraints:
        lines.append(f"- {c}")
    
    lines.append("")
    lines.append("CURRENT STATE (FRAME 0):")
    lines.append(f"{scene_data.get('current_frame_description', 'No description provided.')}")
    lines.append(f"Subject Orientation: {scene_data.get('subject_orientation', 'Neutral')}")
    lines.append(f"Pose: {scene_data.get('pose_notes', 'Neutral')}")
    lines.append(f"Surface Contact: {scene_data.get('surface_contact_points', 'None')}")
    
    lines.append("")
    lines.append("MOTION DIRECTIVE (SECONDS 1-6):")
    lines.append(f"Timing: {motion.get('timing', '6-second continuation')}")
    lines.append(f"Camera Action: {motion.get('camera_behavior', 'Static')}")
    lines.append(f"Body Action: {motion.get('body_behavior', 'Static')}")
    
    lines.append("")
    lines.append("-" * 40)
    lines.append("PROMPT FOR GROK (COPY/PASTE):")
    lines.append("-" * 40)
    
    # The actual prompt string
    prompt = (
        f"Continue this scene for 6 seconds. The first frame must exactly match the input image. "
        f"Preserve the exact identity, outfit state, room layout, lighting direction, camera angle, and anatomical proportions. "
        f"Do not reset the scene or change the context. "
        f"Action: {motion.get('body_behavior', 'Maintain pose')}. "
        f"Camera: {motion.get('camera_behavior', 'Maintain camera')}. "
        f"Keep the motion physically coherent, photorealistic, and continuous. "
        f"No new people, no new props, no outfit change."
    )
    
    lines.append(prompt)
    
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description="Generate Grok Extension Prompts from Scene JSON")
    parser.add_argument("--scene", type=str, default="scene_proxy.json", help="Path to scene JSON")
    parser.add_argument("--out", type=str, default=os.path.join("outputs", "grok_extend_prompt.txt"), help="Output path")
    args = parser.parse_args()

    if not os.path.exists(args.scene):
        print(f"Error: Scene JSON not found at {args.scene}")
        return

    with open(args.scene, 'r') as f:
        scene_data = json.load(f)

    prompt_text = generate_prompt(scene_data)
    
    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        
    with open(args.out, 'w') as f:
        f.write(prompt_text)
        
    print(f"Success! Grok extend prompt written to: {args.out}")

if __name__ == "__main__":
    main()
