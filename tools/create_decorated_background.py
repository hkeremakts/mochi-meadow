#!/usr/bin/env python3
"""Create a decorated grass background with random grass and flower sprites"""

import os
import random
from PIL import Image

# Paths
script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
base_tile_path = os.path.join(project_dir, "assets", "background", "grass_alt.png")
environment_dir = os.path.join(project_dir, "assets", "environment")
output_path = os.path.join(project_dir, "assets", "background", "grassBackground.png")

# Output dimensions
output_width = 1920
output_height = 1080

# Load the base grass tile
base_tile = Image.open(base_tile_path).convert("RGBA")
tile_width, tile_height = base_tile.size

print(f"Base tile size: {tile_width}x{tile_height}")

# Create the background by tiling
tiles_x = (output_width + tile_width - 1) // tile_width
tiles_y = (output_height + tile_height - 1) // tile_height

print(f"Creating {output_width}x{output_height} background using {tiles_x}x{tiles_y} tiles")

background = Image.new("RGBA", (output_width, output_height))

# Tile the base grass
for y in range(tiles_y):
    for x in range(tiles_x):
        pos_x = x * tile_width
        pos_y = y * tile_height
        background.paste(base_tile, (pos_x, pos_y))

# Crop to exact size
background = background.crop((0, 0, output_width, output_height))

# Load all grass and flower decorations
decorations = []
if os.path.exists(environment_dir):
    for filename in os.listdir(environment_dir):
        if filename.lower().endswith(".png"):
            try:
                deco_path = os.path.join(environment_dir, filename)
                deco = Image.open(deco_path).convert("RGBA")
                decorations.append(deco)
            except Exception as e:
                print(f"Failed to load {filename}: {e}")

print(f"Loaded {len(decorations)} decoration sprites")

# Scatter decorations randomly across the background
# Use a grid system to prevent overlapping
decoration_size = 64  # Scale decorations to 64x64
grid_size = 64  # Size of each grid cell to prevent overlap
grid_cols = output_width // grid_size
grid_rows = output_height // grid_size
occupied = set()

# Place decorations with ~10% density
num_decorations = int(grid_cols * grid_rows * 0.10)

for _ in range(num_decorations):
    if not decorations:
        break
    
    # Try to find an unoccupied grid cell
    attempts = 0
    while attempts < 20:
        grid_x = random.randint(0, grid_cols - 1)
        grid_y = random.randint(0, grid_rows - 1)
        
        if (grid_x, grid_y) not in occupied:
            occupied.add((grid_x, grid_y))
            
            # Place decoration at this grid cell with some random offset
            offset_range = grid_size - decoration_size
            pos_x = grid_x * grid_size + random.randint(0, max(0, offset_range))
            pos_y = grid_y * grid_size + random.randint(0, max(0, offset_range))
            
            # Make sure it stays in bounds
            pos_x = max(0, min(output_width - decoration_size, pos_x))
            pos_y = max(0, min(output_height - decoration_size, pos_y))
            
            # Pick random decoration and scale to 64x64
            deco = random.choice(decorations)
            deco_scaled = deco.resize((decoration_size, decoration_size), Image.NEAREST)
            
            # Paste decoration
            background.paste(deco_scaled, (pos_x, pos_y), deco_scaled)
            break
        
        attempts += 1

print(f"Placed {len(occupied)} decorations")

# Save
background.save(output_path)
print(f"Saved decorated background to: {output_path}")

