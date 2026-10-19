#!/usr/bin/env python3
"""
Creates random bush compositions by layering bush1 (core), bush2 (middle), and bush3 (outer).
The composition fits within a 5x5 bush image square (80x80 pixels).
"""

import math
import os
import random
import sys

import pygame


def create_bush_composition(
    bush1_path: str,
    bush2_path: str,
    bush3_path: str,
    output_path: str,
    seed: int | None = None,
) -> None:
    """
    Create a random bush composition.
    
    Args:
        bush1_path: Path to bush1.png (most leaves, core layer)
        bush2_path: Path to bush2.png (middle leaves, middle layer)
        bush3_path: Path to bush3.png (least leaves, outer layer)
        output_path: Where to save the composition
        seed: Random seed for reproducibility (None for random)
    """
    if seed is not None:
        random.seed(seed)
    
    # Load bush images
    bush1 = pygame.image.load(bush1_path).convert_alpha()
    bush2 = pygame.image.load(bush2_path).convert_alpha()
    bush3 = pygame.image.load(bush3_path).convert_alpha()
    
    # Each bush is 16x16, so 5x5 = 80x80
    canvas_size = 80
    canvas = pygame.Surface((canvas_size, canvas_size), pygame.SRCALPHA)
    
    # Layer 1: Core (bush1) - dense center, multiple instances
    # Place 3-5 bush1 instances in the center area
    num_core = random.randint(3, 5)
    for _ in range(num_core):
        # Random position in center 60% of canvas
        center_x = canvas_size // 2
        center_y = canvas_size // 2
        offset_range = int(canvas_size * 0.3)
        x = center_x + random.randint(-offset_range, offset_range)
        y = center_y + random.randint(-offset_range, offset_range)
        
        # Random scale between 0.8 and 1.2
        scale = random.uniform(0.8, 1.2)
        scaled = pygame.transform.scale_by(bush1, scale)
        
        # Random slight rotation for variety
        angle = random.uniform(-15, 15)
        rotated = pygame.transform.rotate(scaled, angle)
        
        # Center the rotated image on the position
        rect = rotated.get_rect()
        rect.center = (x, y)
        canvas.blit(rotated, rect)
    
    # Layer 2: Middle (bush2) - medium density, around core
    # Place 4-7 bush2 instances extending outward from core
    num_middle = random.randint(4, 7)
    for _ in range(num_middle):
        # Position in middle ring (30-70% from center)
        center_x = canvas_size // 2
        center_y = canvas_size // 2
        angle_rad = math.radians(random.uniform(0, 360))
        distance = random.uniform(canvas_size * 0.15, canvas_size * 0.35)
        x = center_x + int(distance * math.cos(angle_rad))
        y = center_y + int(distance * math.sin(angle_rad))
        
        # Random scale between 0.7 and 1.1
        scale = random.uniform(0.7, 1.1)
        scaled = pygame.transform.scale_by(bush2, scale)
        
        # Random rotation
        angle_rot = random.uniform(-20, 20)
        rotated = pygame.transform.rotate(scaled, angle_rot)
        
        rect = rotated.get_rect()
        rect.center = (x, y)
        canvas.blit(rotated, rect)
    
    # Layer 3: Outer (bush3) - sparse outer layer
    # Place 5-9 bush3 instances on the edges
    num_outer = random.randint(5, 9)
    for _ in range(num_outer):
        # Position in outer ring (40-45% from center, near edges)
        center_x = canvas_size // 2
        center_y = canvas_size // 2
        angle_rad = math.radians(random.uniform(0, 360))
        distance = random.uniform(canvas_size * 0.25, canvas_size * 0.42)
        x = center_x + int(distance * math.cos(angle_rad))
        y = center_y + int(distance * math.sin(angle_rad))
        
        # Keep within bounds
        x = max(8, min(canvas_size - 8, x))
        y = max(8, min(canvas_size - 8, y))
        
        # Random scale between 0.6 and 1.0
        scale = random.uniform(0.6, 1.0)
        scaled = pygame.transform.scale_by(bush3, scale)
        
        # Random rotation
        angle_rot = random.uniform(-25, 25)
        rotated = pygame.transform.rotate(scaled, angle_rot)
        
        rect = rotated.get_rect()
        rect.center = (x, y)
        canvas.blit(rotated, rect)
    
    # Save the composition
    pygame.image.save(canvas, output_path)
    print(f"Created bush composition: {output_path}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python create_bush_composition.py <output_path> [seed]")
        print("Example: python create_bush_composition.py output/bush_composite.png 42")
        sys.exit(1)
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    
    bush1_path = os.path.join(project_root, "assets", "environment", "bush", "bush1.png")
    bush2_path = os.path.join(project_root, "assets", "environment", "bush", "bush2.png")
    bush3_path = os.path.join(project_root, "assets", "environment", "bush", "bush3.png")
    
    output_path = sys.argv[1]
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else None
    
    pygame.init()
    # Initialize display (required for image loading)
    pygame.display.set_mode((1, 1))
    try:
        create_bush_composition(bush1_path, bush2_path, bush3_path, output_path, seed)
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()

