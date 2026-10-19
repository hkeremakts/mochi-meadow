#!/usr/bin/env python3
"""Create a tiled grass background from grass.png tile"""

import os
from PIL import Image

# Paths
script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
grass_tile_path = os.path.join(project_dir, "assets", "background", "grass_alt.png")
output_path = os.path.join(project_dir, "assets", "background", "grassBackground.png")

# Load the grass tile
grass_tile = Image.open(grass_tile_path).convert("RGBA")
tile_width, tile_height = grass_tile.size

print(f"Grass tile size: {tile_width}x{tile_height}")

# Create output dimensions
output_width = 1920
output_height = 1080

# Calculate how many tiles needed
tiles_x = (output_width + tile_width - 1) // tile_width
tiles_y = (output_height + tile_height - 1) // tile_height

print(f"Creating {output_width}x{output_height} background using {tiles_x}x{tiles_y} tiles")

# Create the background
background = Image.new("RGBA", (output_width, output_height))

# Tile the grass
for y in range(tiles_y):
    for x in range(tiles_x):
        pos_x = x * tile_width
        pos_y = y * tile_height
        background.paste(grass_tile, (pos_x, pos_y))

# Crop to exact size (in case tiles extended beyond)
background = background.crop((0, 0, output_width, output_height))

# Save
background.save(output_path)
print(f"Saved grass background to: {output_path}")

