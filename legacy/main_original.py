import math
import os
import random
import sys
import time

import pygame


WINDOW_WIDTH, WINDOW_HEIGHT = 960, 640
FPS = 60

# ===== BACKGROUND SETTINGS (ADJUST HERE) =====
BACKGROUND_COLOR = (34, 89, 34)  # Fallback solid color (dark green)
BACKGROUND_TILE_SIZE = (256, 144)  # Size of tiled background (will scale to window)
BACKGROUND_DARKNESS = 0.5  # 0.0 = no darkening, 1.0 = completely black
USE_ENVIRONMENT_DECORATIONS = True  # Show grass/flower decorations
DECORATION_SIZE_MIN = 16  # Minimum size of decorations in pixels
DECORATION_SIZE_MAX = 48  # Maximum size of decorations in pixels
DECORATION_DENSITY = 0.15  # Percentage of grid filled (0.0 to 1.0)
DECORATION_GRID_SIZE = 56  # Grid cell size for decoration placement
PIGEON_SCALE = 0.7  # Scale factor for pigeon size (1.0 = normal, 0.5 = half size)
# ============================================


def ease_out_cubic(t: float) -> float:
    """Easing function for smooth deceleration"""
    return 1 - pow(1 - t, 3)


def ease_in_out_cubic(t: float) -> float:
    """Easing function for smooth acceleration and deceleration"""
    if t < 0.5:
        return 4 * t * t * t
    else:
        return 1 - pow(-2 * t + 2, 3) / 2


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation between a and b"""
    return a + (b - a) * t


def create_bush_composition_surface(
    bush1: pygame.Surface,
    bush2: pygame.Surface,
    bush3: pygame.Surface,
    seed: int | None = None,
) -> pygame.Surface:
    """
    Create a random bush composition surface.
    
    Args:
        bush1: Surface for bush1 (most leaves, core layer)
        bush2: Surface for bush2 (middle leaves, middle layer)
        bush3: Surface for bush3 (least leaves, outer layer)
        seed: Random seed for reproducibility (None for random)
    
    Returns:
        A pygame Surface with the bush composition (80x80 pixels)
    """
    if seed is not None:
        rng = random.Random(seed)
    else:
        rng = random
    
    # Each bush is 16x16, so 5x5 = 80x80
    canvas_size = 80
    canvas = pygame.Surface((canvas_size, canvas_size), pygame.SRCALPHA)
    
    # Layer 1: Core (bush1) - dense center, multiple instances
    # Place 3-5 bush1 instances in the center area
    num_core = rng.randint(3, 5)
    for _ in range(num_core):
        # Random position in center 60% of canvas
        center_x = canvas_size // 2
        center_y = canvas_size // 2
        offset_range = int(canvas_size * 0.3)
        x = center_x + rng.randint(-offset_range, offset_range)
        y = center_y + rng.randint(-offset_range, offset_range)
        
        # Random scale between 0.8 and 1.2
        scale = rng.uniform(0.8, 1.2)
        scaled = pygame.transform.scale_by(bush1, scale)
        
        # Random slight rotation for variety
        angle = rng.uniform(-15, 15)
        rotated = pygame.transform.rotate(scaled, angle)
        
        # Center the rotated image on the position
        rect = rotated.get_rect()
        rect.center = (x, y)
        canvas.blit(rotated, rect)
    
    # Layer 2: Middle (bush2) - medium density, around core
    # Place 4-7 bush2 instances extending outward from core
    num_middle = rng.randint(4, 7)
    for _ in range(num_middle):
        # Position in middle ring (30-70% from center)
        center_x = canvas_size // 2
        center_y = canvas_size // 2
        angle_rad = math.radians(rng.uniform(0, 360))
        distance = rng.uniform(canvas_size * 0.15, canvas_size * 0.35)
        x = center_x + int(distance * math.cos(angle_rad))
        y = center_y + int(distance * math.sin(angle_rad))
        
        # Random scale between 0.7 and 1.1
        scale = rng.uniform(0.7, 1.1)
        scaled = pygame.transform.scale_by(bush2, scale)
        
        # Random rotation
        angle_rot = rng.uniform(-20, 20)
        rotated = pygame.transform.rotate(scaled, angle_rot)
        
        rect = rotated.get_rect()
        rect.center = (x, y)
        canvas.blit(rotated, rect)
    
    # Layer 3: Outer (bush3) - sparse outer layer
    # Place 5-9 bush3 instances on the edges
    num_outer = rng.randint(5, 9)
    for _ in range(num_outer):
        # Position in outer ring (40-45% from center, near edges)
        center_x = canvas_size // 2
        center_y = canvas_size // 2
        angle_rad = math.radians(rng.uniform(0, 360))
        distance = rng.uniform(canvas_size * 0.25, canvas_size * 0.42)
        x = center_x + int(distance * math.cos(angle_rad))
        y = center_y + int(distance * math.sin(angle_rad))
        
        # Keep within bounds
        x = max(8, min(canvas_size - 8, x))
        y = max(8, min(canvas_size - 8, y))
        
        # Random scale between 0.6 and 1.0
        scale = rng.uniform(0.6, 1.0)
        scaled = pygame.transform.scale_by(bush3, scale)
        
        # Random rotation
        angle_rot = rng.uniform(-25, 25)
        rotated = pygame.transform.rotate(scaled, angle_rot)
        
        rect = rotated.get_rect()
        rect.center = (x, y)
        canvas.blit(rotated, rect)
    
    return canvas


class SpriteSet:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.cache: dict[str, list[pygame.Surface]] = {}
        self._folder_index_built = False

    def _natural_key(self, s: str) -> tuple:
        import re
        return tuple(int(text) if text.isdigit() else text for text in re.split(r"(\d+)", s))

    def _normalize_anim_name(self, name: str) -> str:
        # Convert variations like walk(down) -> walk_down, walk-down -> walk_down
        return (
            name.replace("(", "_")
            .replace(")", "")
            .replace("-", "_")
            .replace(" ", "_")
        )

    def _alt_folder_names(self, name: str) -> list[str]:
        # Given walk_down -> [walk_down, walk(down)] and vice versa
        # Also handle eat_food_stand_front -> eat_food(stand_front)
        name_norm = self._normalize_anim_name(name)
        candidates = [name_norm]
        if "_" in name_norm:
            # Try splitting at each underscore position
            parts = name_norm.split("_")
            # For eat_food_stand_front -> eat_food(stand_front)
            for i in range(1, len(parts)):
                prefix = "_".join(parts[:i])
                suffix = "_".join(parts[i:])
                candidates.append(f"{prefix}({suffix})")
        # If already like run(right)
        if "(" in name and ")" in name:
            inner = name.replace("(", "_").replace(")", "")
            candidates.append(inner)
        return candidates

    def _load_from_folder(self, folder_name: str) -> list[pygame.Surface]:
        folder_path = os.path.join(self.base_dir, folder_name)
        if not os.path.isdir(folder_path):
            return []
        files = [f for f in os.listdir(folder_path) if f.lower().endswith(".png")]
        if not files:
            return []
        files.sort(key=self._natural_key)
        frames: list[pygame.Surface] = []
        for f in files:
            path = os.path.join(folder_path, f)
            image = pygame.image.load(path).convert_alpha()
            frames.append(image)
        return frames

    def load_sequence(self, name: str) -> list[pygame.Surface]:
        name = self._normalize_anim_name(name)
        if name in self.cache:
            return self.cache[name]
        frames: list[pygame.Surface] = []
        # Load files like name_01.png ... name_99.png
        for i in range(1, 100):
            filename = f"{name}_{i:02d}.png"
            path = os.path.join(self.base_dir, filename)
            if not os.path.exists(path):
                if i == 1:
                    # Not found at all
                    frames = []
                    break
                else:
                    # End of sequence
                    break
            image = pygame.image.load(path).convert_alpha()
            frames.append(image)
        if not frames:
            # Try subfolder variations
            for alt in self._alt_folder_names(name):
                frames = self._load_from_folder(alt)
                if frames:
                    break
        if frames:
            self.cache[name] = frames
        return frames


class Cat:
    def __init__(self, start_pos: tuple[int, int]):
        self.position_x = float(start_pos[0])
        self.position_y = float(start_pos[1])
        self.direction_x, self.direction_y = self._random_unit_vector()
        self.target_direction_x = self.direction_x
        self.target_direction_y = self.direction_y
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.mode = "walk"  # movement speed mode: "walk" or "run"
        self.state = "move"  # behavior state: "move", "eat", "preparing_sleep", "sleep", "sitting", or "hissing"
        self.mode_ends_at = 0.0
        self.eat_started_at = 0.0
        self.eat_duration = 0.0  # Will be set randomly when eating starts
        self.sleep_started_at = 0.0
        self.sleep_duration = 0.0  # Will be set randomly when sleeping starts
        self.sleep_anim_name = ""  # Which sleep animation to use
        self.last_sleep_check = 0.0
        self.preparing_sleep_at = 0.0  # When cat started preparing to sleep
        self.last_eat_finished_at = 0.0  # When cat finished eating (to prevent immediate sleep)
        self.sit_started_at = 0.0  # When cat started sitting
        self.sit_duration = 0.0  # How long the sit lasts
        self.sit_anim_name = ""  # Which sit animation to use
        self.last_sit_check = 0.0  # Last time we checked if cat should sit
        self.hiss_started_at = 0.0  # When cat started hissing
        self.hiss_duration = 0.0  # How long the hiss lasts
        self.hiss_target_pigeon = False  # Whether currently hissing at pigeon
        self.last_hiss_check = 0.0  # Last time we checked if cat should hiss
        self.last_idle_time = 0.0
        self.idle_duration = 0.0
        self.body_width = 60
        self.body_height = 36
        self.color_body = (230, 180, 120)
        self.color_outline = (30, 30, 30)
        self._schedule_next_mode()
        self.sprites = SpriteSet(os.path.join(os.path.dirname(__file__), "assets", "cat"))
        self.render_scale = 2
        self.acceleration = 250.0  # Pixels per second squared
        self.deceleration = 350.0
        self.rotation_speed = 3.0  # How fast cat turns
        self.window_width = WINDOW_WIDTH
        self.window_height = WINDOW_HEIGHT
        self.ground_zone_ratio = 1.0 / 6.0  # Bottom 1/6 of screen
        self.current_anim_name = ""  # Track current animation
        self.anim_time = 0.0  # Time in current animation
        self.prev_anim_name = ""  # Previous animation for blending
        self.anim_blend_time = 0.0  # Time spent blending
        self.anim_blend_duration = 0.15  # Duration of blend in seconds
        self.display_position_x = float(start_pos[0])  # Smoothed display position
        self.display_position_y = float(start_pos[1])

    def _random_unit_vector(self) -> tuple[float, float]:
        angle = random.uniform(0.0, math.tau)
        return math.cos(angle), math.sin(angle)

    def _speed(self) -> float:
        return 60.0 if self.mode == "walk" else 150.0
    
    def _smooth_rotate_toward(self, target_x: float, target_y: float, dt: float) -> None:
        """Smoothly rotate direction toward target with easing"""
        # Calculate angular difference for smoother rotation
        current_angle = math.atan2(self.direction_y, self.direction_x)
        target_angle = math.atan2(target_y, target_x)
        
        # Find shortest rotation direction
        angle_diff = target_angle - current_angle
        # Normalize to -pi to pi
        while angle_diff > math.pi:
            angle_diff -= 2 * math.pi
        while angle_diff < -math.pi:
            angle_diff += 2 * math.pi
        
        # Apply easing to rotation speed
        max_rotation = self.rotation_speed * dt
        rotation_amount = max(-max_rotation, min(max_rotation, angle_diff))
        
        # Apply smooth rotation
        new_angle = current_angle + rotation_amount
        self.direction_x = math.cos(new_angle)
        self.direction_y = math.sin(new_angle)

    def _schedule_next_mode(self) -> None:
        now = time.monotonic()
        if self.mode == "walk":
            duration = random.uniform(1.5, 4.0)
        else:
            # Running lasts longer - at least a couple of seconds
            duration = random.uniform(2.5, 5.0)
        self.mode_ends_at = now + duration

    def _maybe_change_mode(self, food_available: bool) -> None:
        now = time.monotonic()
        if now >= self.mode_ends_at and self.state == "move":
            # Determine run probability based on food availability
            if food_available:
                # With food: normal behavior (70% chance to switch)
                if random.random() < 0.7:
                    self.mode = "run" if self.mode == "walk" else "walk"
                    # 50% chance to pick a new direction on mode change
                    if random.random() < 0.5:
                        self.direction_x, self.direction_y = self._random_unit_vector()
            else:
                # Without food: mostly walk, 5% chance to run
                if self.mode == "run":
                    # If currently running, switch back to walk
                    self.mode = "walk"
                else:
                    # If walking, small chance to start running
                    if random.random() < 0.05:
                        self.mode = "run"
                # Still change direction sometimes
                if random.random() < 0.3:
                    self.direction_x, self.direction_y = self._random_unit_vector()
            self._schedule_next_mode()

        # Small random jitter to direction for organic movement
        if self.state == "move" and random.random() < 0.02:
            jx, jy = self._random_unit_vector()
            mix = 0.2
            self.direction_x = (1 - mix) * self.direction_x + mix * jx
            self.direction_y = (1 - mix) * self.direction_y + mix * jy
            mag = math.hypot(self.direction_x, self.direction_y) or 1.0
            self.direction_x /= mag
            self.direction_y /= mag

    def update(self, dt: float, food_pos: tuple[int, int] | None, pigeon_pos: tuple[int, int] | None = None) -> None:
        # Only allow mode switching when not actively chasing food
        if self.state == "move":
            if food_pos is not None:
                dist_to_food = math.hypot(float(food_pos[0]) - self.position_x, float(food_pos[1]) - self.position_y)
                # If far from food, allow mode switching. If close, stay in current mode
                if dist_to_food > 50:
                    self._maybe_change_mode(True)
                # If close to food, force run mode to reach it quickly
                elif dist_to_food > 28:
                    self.mode = "run"
            else:
                self._maybe_change_mode(False)
        now = time.monotonic()
        
        # Update animation time and blend time
        self.anim_time += dt
        self.anim_blend_time += dt

        # Check if currently sleeping
        if self.state == "sleep":
            if now - self.sleep_started_at < self.sleep_duration:
                return  # Stay asleep, don't move
            else:
                # Finished sleeping, return to move state
                self.state = "move"
                return

        # Check if preparing to sleep (slowing down)
        if self.state == "preparing_sleep":
            # Force walk mode and decelerate
            self.mode = "walk"
            current_speed = math.hypot(self.velocity_x, self.velocity_y)
            
            # After 1.5 seconds of slowing down, or if nearly stopped, go to sleep
            if now - self.preparing_sleep_at > 1.5 or current_speed < 5.0:
                self.state = "sleep"
                self.sleep_started_at = now
                self.sleep_duration = random.uniform(3.0, 6.0)
                # Pick a random sleep animation from sleep1-5
                sleep_variants = [
                    "sleep1_left_front", "sleep1_left_back", "sleep1_right_front", "sleep1_right_back",
                    "sleep2_left_front", "sleep2_right_front",
                    "sleep3_left_front", "sleep3_right_front",
                    "sleep4_left_front", "sleep4_right_front",
                    "sleep5_left_front", "sleep5_right_back"
                ]
                self.sleep_anim_name = random.choice(sleep_variants)
                return
            # Continue slowing down but don't move toward targets
            # Fall through to movement code but with reduced speed

        # Check if currently eating
        if self.state == "eat":
            # Continue eating until duration expires
            if now - self.eat_started_at < self.eat_duration:
                return  # Stay in eat state, don't move
            else:
                # Finished eating, return to move state
                self.state = "move"
                self.last_eat_finished_at = now  # Record when eating finished
                return  # Exit update to prevent re-entering eat state this frame

        # Check if currently sitting
        if self.state == "sitting":
            # Continue sitting until duration expires
            if now - self.sit_started_at < self.sit_duration:
                return  # Stay in sitting state, don't move
            else:
                # Finished sitting, return to move state
                self.state = "move"
                return

        # Check if currently hissing
        if self.state == "hissing":
            # Continue hissing until duration expires
            if now - self.hiss_started_at < self.hiss_duration:
                return  # Stay in hissing state, don't move
            else:
                # Finished hissing, return to move state
                self.state = "move"
                self.hiss_target_pigeon = False
                return

        # Random chance to sleep (check every 3 seconds)
        # BUT only if there's no food or pigeon on the surface
        # AND at least 0.7 seconds have passed since finishing eating
        if now - self.last_sleep_check > 3.0:
            self.last_sleep_check = now
            # Don't go to sleep if there's food or pigeon to interact with
            # Also wait at least 0.7 seconds after eating before sleeping
            if food_pos is None and pigeon_pos is None and (now - self.last_eat_finished_at > 0.7):
                if random.random() < 0.15:  # 15% chance every 3 seconds
                    # Start preparing to sleep (slowing down phase)
                    self.state = "preparing_sleep"
                    self.preparing_sleep_at = now
                    return

        # Random chance to sit (check every 4 seconds)
        # Only sit when there's nothing interesting to do
        if now - self.last_sit_check > 4.0:
            self.last_sit_check = now
            # Don't sit if there's food or pigeon to interact with
            if food_pos is None and pigeon_pos is None:
                if random.random() < 0.20:  # 20% chance every 4 seconds
                    # Stop and sit
                    self.state = "sitting"
                    self.sit_started_at = now
                    self.sit_duration = random.uniform(2.5, 5.5)
                    
                    # Choose a random sitting animation based on direction facing
                    # Available: tail_wag, scratch, paw_swipe (left/right)
                    sit_type = random.choice(["tail_wag", "scratch", "left_paw_swipe", "right_paw_swipe"])
                    
                    # Determine facing direction
                    if abs(self.direction_x) >= abs(self.direction_y):
                        # Horizontal facing
                        facing = "right" if self.direction_x >= 0 else "left"
                    else:
                        # Vertical facing
                        facing = "front" if self.direction_y >= 0 else "back"
                    
                    self.sit_anim_name = f"{sit_type}_sit_{facing}"
                    self.velocity_x = 0.0
                    self.velocity_y = 0.0
                    return

        # Determine target direction based on priorities
        has_target = False
        target_speed = self._speed()
        
        # If preparing to sleep, just decelerate - don't seek new targets
        if self.state == "preparing_sleep":
            target_speed = 0.0
            has_target = False
        # Priority 1: Interact with pigeon if it's landed
        elif pigeon_pos is not None:
            pigeon_x, pigeon_y, pigeon_vx, pigeon_vy = pigeon_pos
            
            target_dx = pigeon_x - self.position_x
            target_dy = pigeon_y - self.position_y
            dist = math.hypot(target_dx, target_dy)
            
            # Check if cat is close enough to hiss (50-100 pixels away)
            if 50 < dist < 100 and now - self.last_hiss_check > 1.5:
                self.last_hiss_check = now
                if random.random() < 0.6:  # 60% chance to hiss when close
                    # Face the pigeon and hiss
                    if dist > 1e-3:
                        self.direction_x = target_dx / dist
                        self.direction_y = target_dy / dist
                    self.state = "hissing"
                    self.hiss_started_at = now
                    self.hiss_duration = random.uniform(0.8, 1.5)
                    self.hiss_target_pigeon = True
                    self.velocity_x = 0.0
                    self.velocity_y = 0.0
                    return
            
            # Chase the pigeon (run toward it with prediction)
            # Predict where the pigeon will be based on its velocity
            prediction_time = 0.5  # Look ahead 0.5 seconds
            predicted_x = pigeon_x + pigeon_vx * prediction_time
            predicted_y = pigeon_y + pigeon_vy * prediction_time
            
            target_dx = predicted_x - self.position_x
            target_dy = predicted_y - self.position_y
            dist = math.hypot(target_dx, target_dy)
            
            if dist > 1e-3:
                self.target_direction_x = target_dx / dist
                self.target_direction_y = target_dy / dist
                # Force run mode when chasing pigeon
                self.mode = "run"
                has_target = True
            
            self.state = "move"

        # Priority 2: Seek food if available (only if not chasing pigeon)
        elif food_pos is not None:
            target_dx = float(food_pos[0]) - self.position_x
            target_dy = float(food_pos[1]) - self.position_y
            dist = math.hypot(target_dx, target_dy)
            
            # If close enough, switch to eat state and move to exact position
            if dist < 28:  # proximity threshold
                # Adjust position based on eating direction to align mouth with food
                # Determine which direction cat will face when eating
                if abs(self.direction_x) >= abs(self.direction_y):
                    # Horizontal facing (left/right)
                    if self.direction_x >= 0:
                        # Facing right - offset cat slightly left so mouth is on food
                        self.position_x = float(food_pos[0]) - 8
                        self.position_y = float(food_pos[1]) - 5
                    else:
                        # Facing left - offset cat slightly right so mouth is on food
                        self.position_x = float(food_pos[0]) + 8
                        self.position_y = float(food_pos[1]) - 5
                else:
                    # Vertical facing (front/back)
                    if self.direction_y >= 0:
                        # Facing front (down) - offset cat up so mouth is on food
                        self.position_x = float(food_pos[0])
                        self.position_y = float(food_pos[1]) - 10
                    else:
                        # Facing back (up) - offset cat down so mouth is on food
                        self.position_x = float(food_pos[0])
                        self.position_y = float(food_pos[1]) + 5
                
                self.state = "eat"
                self.eat_started_at = now
                self.eat_duration = random.uniform(1.5, 4.0)
                # Stop all movement
                self.velocity_x = 0.0
                self.velocity_y = 0.0
                target_speed = 0.0
            else:
                # Move toward food
                if dist > 1e-3:
                    self.target_direction_x = target_dx / dist
                    self.target_direction_y = target_dy / dist
                    has_target = True
                self.state = "move"
        else:
            if self.state != "preparing_sleep":
                self.state = "move"
            has_target = True  # Keep current direction

        # Apply smooth rotation toward target direction
        if has_target and self.state == "move":
            self._smooth_rotate_toward(self.target_direction_x, self.target_direction_y, dt)

        # Apply acceleration/deceleration with smooth velocity changes
        if self.state == "move" or self.state == "preparing_sleep":
            current_speed = math.hypot(self.velocity_x, self.velocity_y)
            
            if current_speed < target_speed:
                # Accelerate
                speed_delta = self.acceleration * dt
                new_speed = min(target_speed, current_speed + speed_delta)
            else:
                # Decelerate
                speed_delta = self.deceleration * dt
                new_speed = max(target_speed, current_speed - speed_delta)
            
            # Update velocity based on direction and new speed
            self.velocity_x = self.direction_x * new_speed
            self.velocity_y = self.direction_y * new_speed
            
            # Update position
            self.position_x += self.velocity_x * dt
            self.position_y += self.velocity_y * dt
        else:
            # Not moving, decelerate to stop
            current_speed = math.hypot(self.velocity_x, self.velocity_y)
            if current_speed > 0.1:
                speed_delta = self.deceleration * dt
                new_speed = max(0.0, current_speed - speed_delta)
                if current_speed > 0:
                    self.velocity_x = (self.velocity_x / current_speed) * new_speed
                    self.velocity_y = (self.velocity_y / current_speed) * new_speed
            else:
                self.velocity_x = 0.0
                self.velocity_y = 0.0

        half_w = self.body_width / 2
        half_h = self.body_height / 2

        # Corner avoidance - steer away from edges when in "move" state
        if self.state == "move" and has_target:
            edge_margin = 100  # Distance from edge to start avoiding
            avoidance_strength = 0.3  # How strongly to push away from edges
            
            # Check distance to each edge
            dist_left = self.position_x
            dist_right = self.window_width - self.position_x
            dist_top = self.position_y
            dist_bottom = self.window_height - self.position_y
            
            # Add repulsion force if near edges
            if dist_left < edge_margin:
                # Push away from left edge
                push_strength = (1.0 - dist_left / edge_margin) * avoidance_strength
                self.target_direction_x += push_strength
            elif dist_right < edge_margin:
                # Push away from right edge
                push_strength = (1.0 - dist_right / edge_margin) * avoidance_strength
                self.target_direction_x -= push_strength
            
            if dist_top < edge_margin:
                # Push away from top edge
                push_strength = (1.0 - dist_top / edge_margin) * avoidance_strength
                self.target_direction_y += push_strength
            elif dist_bottom < edge_margin:
                # Push away from bottom edge
                push_strength = (1.0 - dist_bottom / edge_margin) * avoidance_strength
                self.target_direction_y -= push_strength
            
            # Renormalize target direction after applying avoidance
            mag = math.hypot(self.target_direction_x, self.target_direction_y)
            if mag > 0.01:
                self.target_direction_x /= mag
                self.target_direction_y /= mag

        # Bounce off edges with gentle reflection
        bounced = False
        if self.position_x - half_w < 0:
            self.position_x = half_w
            self.direction_x = abs(self.direction_x)
            bounced = True
        elif self.position_x + half_w > self.window_width:
            self.position_x = self.window_width - half_w
            self.direction_x = -abs(self.direction_x)
            bounced = True

        # Allow cat to roam entire screen
        if self.position_y - half_h < 0:
            self.position_y = half_h
            self.direction_y = abs(self.direction_y)
            bounced = True
        elif self.position_y + half_h > self.window_height:
            self.position_y = self.window_height - half_h
            self.direction_y = -abs(self.direction_y)
            bounced = True

        if bounced and random.random() < 0.8:
            # Usually pick a new heading after bouncing to avoid edges
            self.direction_x, self.direction_y = self._random_unit_vector()

    def _choose_anim(self) -> tuple[str, float]:
        # Map movement direction to facing set
        if self.state == "sleep":
            return self.sleep_anim_name, 2.5
        if self.state == "sitting":
            # Use the selected sitting animation
            # Speed varies by animation type
            if "tail_wag" in self.sit_anim_name:
                fps = 3.5
            elif "scratch" in self.sit_anim_name:
                fps = 4.0
            else:  # paw swipes
                fps = 4.5
            return self.sit_anim_name, fps
        if self.state == "hissing":
            # Choose hissing animation based on direction cat is facing
            # Available: hiss(front_left) and hiss(front_right)
            if abs(self.direction_x) >= abs(self.direction_y):
                # Horizontal facing
                facing = "right" if self.direction_x >= 0 else "left"
                return f"hiss_front_{facing}", 5.0
            else:
                # Vertical facing - use front_left or front_right based on last horizontal direction
                facing = "right" if self.direction_x >= 0 else "left"
                return f"hiss_front_{facing}", 5.0
        if self.state == "eat":
            # Choose eating animation based on direction cat is facing
            if abs(self.direction_x) >= abs(self.direction_y):
                # Horizontal facing
                facing = "right" if self.direction_x >= 0 else "left"
                return f"eat_food_stand_{facing}", 4.0
            else:
                # Vertical facing
                facing = "front" if self.direction_y >= 0 else "back"
                return f"eat_food_stand_{facing}", 4.0
        
        # Check current speed to determine walk vs run animation
        current_speed = math.hypot(self.velocity_x, self.velocity_y)
        
        # Use mode to determine animation, with speed-based transition
        # This prevents weird animation during acceleration
        if self.mode == "run" and current_speed > 70:
            # Use run animation when in run mode and moving fast enough
            base = "run"
            # Speed up animation based on velocity with smoother scaling
            speed_ratio = current_speed / 150.0
            fps = 4.5 + speed_ratio * 3.5
        elif current_speed > 8:
            # Use walk animation for slower speeds
            base = "walk"
            # Adaptive walk speed with smoother curve
            speed_ratio = min(1.0, current_speed / 60.0)
            fps = 2.5 + speed_ratio * 2.5
        else:
            # Nearly stopped, very slow animation
            base = "walk"
            fps = 1.8
        
        # Use direction for facing
        if abs(self.direction_x) >= abs(self.direction_y):
            facing = "right" if self.direction_x >= 0 else "left"
            name = f"{base}_{facing}"
            return name, fps
        else:
            # vertical movement
            name = f"{base}_up" if self.direction_y < 0 else f"{base}_down"
            return name, fps

    def draw(self, surface: pygame.Surface) -> None:
        # Smooth position interpolation for display (reduces jitter)
        self.display_position_x = lerp(self.display_position_x, self.position_x, 0.5)
        self.display_position_y = lerp(self.display_position_y, self.position_y, 0.5)
        
        cx, cy = int(self.display_position_x), int(self.display_position_y)
        name_fps = self._choose_anim()
        sprite_key, fps = name_fps
        flip = sprite_key.endswith("|flip")
        base_name = sprite_key.replace("|flip", "")
        
        # Handle animation change with blending
        if base_name != self.current_anim_name:
            self.prev_anim_name = self.current_anim_name
            self.current_anim_name = base_name
            self.anim_blend_time = 0.0
            self.anim_time = 0.0
        
        frames = self.sprites.load_sequence(base_name)

        if frames:
            frame_count = len(frames)
            # Use fractional frame index for smoother playback
            frame_float = (self.anim_time * fps) % frame_count
            frame_index = int(frame_float)
            
            # Get current frame
            frame = frames[frame_index]
            
            # Blend with previous animation if transitioning
            if self.anim_blend_time < self.anim_blend_duration and self.prev_anim_name:
                prev_frames = self.sprites.load_sequence(self.prev_anim_name)
                if prev_frames:
                    blend_alpha = self.anim_blend_time / self.anim_blend_duration
                    blend_alpha = ease_in_out_cubic(blend_alpha)
                    
                    # Get previous frame
                    prev_frame_index = min(len(prev_frames) - 1, frame_index)
                    prev_frame = prev_frames[prev_frame_index].copy()
                    
                    # Create blended frame
                    current_frame = frame.copy()
                    
                    # Set alpha for blending
                    prev_frame.set_alpha(int(255 * (1.0 - blend_alpha)))
                    current_frame.set_alpha(int(255 * blend_alpha))
                    
                    # Create composite
                    blended = pygame.Surface(frame.get_size(), pygame.SRCALPHA)
                    blended.blit(prev_frame, (0, 0))
                    blended.blit(current_frame, (0, 0))
                    frame = blended
            
            if flip:
                frame = pygame.transform.flip(frame, True, False)
            if self.render_scale != 1:
                frame = pygame.transform.scale_by(frame, self.render_scale)
            rect = frame.get_rect()
            rect.midbottom = (cx, cy + self.body_height // 2)
            surface.blit(frame, rect)
            return

        # Fallback vector cat if no sprites are present
        rect = pygame.Rect(0, 0, self.body_width, self.body_height)
        rect.center = (cx, cy)
        pygame.draw.ellipse(surface, self.color_body, rect)
        pygame.draw.ellipse(surface, self.color_outline, rect, 2)


class Pigeon:
    def __init__(self):
        self.position_x = 0.0
        self.position_y = 0.0
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.state = "inactive"  # "inactive", "flying_in", "hesitating", "landing", "landed", "pecking", "flying_out"
        self.direction_x = 1.0
        self.landed_time = 0.0
        self.roam_duration = 0.0
        self.roam_target_x = 0.0
        self.roam_target_y = 0.0
        self.entry_side = ""  # "left", "right"
        self.target_land_x = 0.0
        self.target_land_y = 0.0
        self.land_approach_y = 0.0  # Y position to start landing descent
        self.peck_started_at = 0.0
        self.peck_duration = 0.0
        self.last_peck_check = 0.0
        self.head_bob_offset = 0.0
        self.hesitate_started_at = 0.0
        self.hesitate_duration = 0.0
        self.hesitate_base_y = 0.0
        self.hesitate_decision = ""  # "land" or "flee"
        self.sprites = SpriteSet(os.path.join(os.path.dirname(__file__), "assets", "pigeon"))
        self.render_scale = 2 * PIGEON_SCALE
        self.anim_time = 0.0  # Track animation time for smooth playback
        self.current_anim_name = ""
        self.prev_anim_name = ""
        self.anim_blend_time = 0.0
        self.anim_blend_duration = 0.12
        self.display_position_x = 0.0
        self.display_position_y = 0.0
        self.fly_speed = 120.0
        self.walk_speed = 25.0
        self.landing_speed = 45.0
        self.acceleration = 200.0
        self.window_width = WINDOW_WIDTH
        self.window_height = WINDOW_HEIGHT
        self.ground_zone_ratio = 1.0 / 6.0  # Bottom 1/6 of screen

    def spawn(self) -> None:
        """Initialize a new pigeon visit"""
        now = time.monotonic()
        # Choose random entry side
        self.entry_side = random.choice(["left", "right"])
        
        # Start position off-screen at flying height
        if self.entry_side == "left":
            self.position_x = -50.0
            self.direction_x = 1.0
        else:
            self.position_x = self.window_width + 50.0
            self.direction_x = -1.0
        
        self.position_y = random.uniform(80.0, 180.0)  # Higher up for flying
        
        # Choose landing spot anywhere on screen
        self.target_land_x = random.uniform(120.0, self.window_width - 120.0)
        self.target_land_y = random.uniform(200.0, self.window_height - 80.0)
        
        # Set approach point for landing (above the target)
        self.land_approach_y = self.target_land_y - 60.0
        
        self.state = "flying_in"
        self.roam_duration = random.uniform(4.0, 8.0)
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.last_peck_check = now

    def update(self, dt: float, cat_pos: tuple[float, float] | None = None, cat_hissing: bool = False) -> None:
        now = time.monotonic()
        
        if self.state == "inactive":
            return
        
        # Update animation time and blend time
        self.anim_time += dt
        self.anim_blend_time += dt
        
        # Update head bob for walking animation
        if self.state == "landed" or self.state == "pecking":
            current_speed = math.hypot(self.velocity_x, self.velocity_y)
            if current_speed > 5:
                self.head_bob_offset = math.sin(now * 12.0) * 2.0
            else:
                self.head_bob_offset *= 0.9  # Dampen when stopped
        
        # Check if cat is hissing at pigeon - 50% chance to fly away
        if (self.state == "landed" or self.state == "pecking") and cat_hissing and cat_pos is not None:
            dx = cat_pos[0] - self.position_x
            dy = cat_pos[1] - self.position_y
            dist = math.hypot(dx, dy)
            if 50 < dist < 100 and random.random() < 0.5:  # 50% chance to flee from hiss
                self.state = "flying_out"
                self.velocity_x = 0.0
                self.velocity_y = 0.0
                return
        
        # Check if cat is too close while landed/pecking - fly away!
        if (self.state == "landed" or self.state == "pecking") and cat_pos is not None:
            dx = cat_pos[0] - self.position_x
            dy = cat_pos[1] - self.position_y
            dist = math.hypot(dx, dy)
            if dist < 80:  # Cat within 80 pixels, flee!
                self.state = "flying_out"
                self.velocity_x = 0.0
                self.velocity_y = 0.0
                return
        
        if self.state == "flying_in":
            # Fly toward approach point, then descend for landing
            target_x = self.target_land_x
            
            # Check if we should start landing descent
            dist_to_target_x = abs(self.target_land_x - self.position_x)
            
            if dist_to_target_x < 80 and self.position_y < self.land_approach_y + 10:
                # Check if cat is nearby before landing
                if cat_pos is not None:
                    cat_dx = cat_pos[0] - self.position_x
                    cat_dy = cat_pos[1] - self.position_y
                    cat_dist = math.hypot(cat_dx, cat_dy)
                    
                    # If cat is within 200 pixels, hesitate before landing
                    if cat_dist < 200:
                        self.state = "hesitating"
                        self.hesitate_started_at = now
                        self.hesitate_duration = random.uniform(1.5, 3.0)
                        self.hesitate_base_y = self.position_y
                        # Decide now what to do after hesitating
                        # If cat is very close, more likely to flee
                        flee_chance = 0.3 if cat_dist > 120 else 0.7
                        self.hesitate_decision = "flee" if random.random() < flee_chance else "land"
                        self.velocity_x = 0.0
                        self.velocity_y = 0.0
                        return
                
                # No cat nearby, proceed to landing
                self.state = "landing"
                return
            
            # Fly toward approach point
            target_y = self.land_approach_y
            dx = target_x - self.position_x
            dy = target_y - self.position_y
            dist = math.hypot(dx, dy)
            
            if dist > 1:
                # Smooth acceleration toward target
                target_vx = (dx / dist) * self.fly_speed
                target_vy = (dy / dist) * self.fly_speed
                
                accel = self.acceleration * dt
                self.velocity_x += (target_vx - self.velocity_x) * min(1.0, accel / self.fly_speed)
                self.velocity_y += (target_vy - self.velocity_y) * min(1.0, accel / self.fly_speed)
                
                self.position_x += self.velocity_x * dt
                self.position_y += self.velocity_y * dt
                self.direction_x = 1.0 if dx > 0 else -1.0
        
        elif self.state == "hesitating":
            # Bob up and down while deciding whether to land or flee
            hesitate_elapsed = now - self.hesitate_started_at
            
            if hesitate_elapsed >= self.hesitate_duration:
                # Time to make decision with smooth transition
                if self.hesitate_decision == "flee":
                    self.state = "flying_out"
                    self.velocity_x = 0.0
                    self.velocity_y = 0.0
                else:
                    # Proceed to landing with smooth transition
                    self.state = "landing"
                return
            
            # Bob up and down with a sine wave pattern
            # Frequency: 1.8 Hz (slightly slower for more natural look)
            bob_amplitude = 18.0
            bob_offset = math.sin(hesitate_elapsed * math.pi * 2.0 * 1.8) * bob_amplitude
            target_y = self.hesitate_base_y + bob_offset
            
            # Also drift slightly horizontally to show uncertainty
            # Use different frequency for more organic movement
            drift_offset = math.sin(hesitate_elapsed * math.pi * 1.3) * 12.0
            target_x = self.target_land_x + drift_offset
            
            # Smoothly move to bobbing position with easing
            smooth_factor_y = 1.0 - math.exp(-6.0 * dt)
            smooth_factor_x = 1.0 - math.exp(-4.0 * dt)
            self.position_y += (target_y - self.position_y) * smooth_factor_y
            self.position_x += (target_x - self.position_x) * smooth_factor_x
        
        elif self.state == "landing":
            # Gradual descent to landing spot with easing
            dx = self.target_land_x - self.position_x
            dy = self.target_land_y - self.position_y
            dist_y = abs(dy)
            
            if dist_y < 5:
                # Landed! Smooth transition to landed state
                self.state = "landed"
                self.landed_time = now
                self.roam_target_x = self.position_x
                self.roam_target_y = self.position_y
                # Gentle deceleration to zero
                self.velocity_x *= 0.3
                self.velocity_y = 0.0
                return
            
            # Calculate progress of landing (0 to 1)
            total_descent = 60.0  # Approximate distance from approach to land
            landing_progress = 1.0 - (dist_y / total_descent)
            landing_progress = max(0.0, min(1.0, landing_progress))
            
            # Apply easing to descent speed (slower as it approaches ground)
            eased_progress = ease_out_cubic(landing_progress)
            descent_speed_multiplier = 1.0 - (eased_progress * 0.6)
            
            # Slow horizontal movement, controlled descent
            target_vx = (dx / max(1, abs(dx))) * self.landing_speed * 0.25 if abs(dx) > 1 else 0
            target_vy = self.landing_speed * descent_speed_multiplier
            
            # Smooth velocity transitions with exponential decay
            smooth_x = 1.0 - math.exp(-4.0 * dt)
            smooth_y = 1.0 - math.exp(-3.0 * dt)
            self.velocity_x += (target_vx - self.velocity_x) * smooth_x
            self.velocity_y += (target_vy - self.velocity_y) * smooth_y
            
            self.position_x += self.velocity_x * dt
            self.position_y += self.velocity_y * dt
            self.direction_x = 1.0 if dx > 0 else -1.0
        
        elif self.state == "landed":
            # Roam a bit on the ground
            if now - self.landed_time > self.roam_duration:
                # Time to leave
                self.state = "flying_out"
                self.velocity_x = 0.0
                self.velocity_y = 0.0
                return
            
            # Random chance to peck at ground
            if now - self.last_peck_check > 2.0:
                self.last_peck_check = now
                if random.random() < 0.3:  # 30% chance to peck
                    self.state = "pecking"
                    self.peck_started_at = now
                    self.peck_duration = random.uniform(1.0, 2.5)
                    return
            
            # Pick new roam target occasionally
            if random.random() < 0.015:
                self.roam_target_x = self.position_x + random.uniform(-60, 60)
                self.roam_target_y = self.position_y + random.uniform(-30, 30)
                # Keep in bounds
                self.roam_target_x = max(60, min(self.window_width - 60, self.roam_target_x))
                self.roam_target_y = max(60, min(self.window_height - 60, self.roam_target_y))
            
            # Walk toward roam target with smooth movement
            dx = self.roam_target_x - self.position_x
            dy = self.roam_target_y - self.position_y
            dist = math.hypot(dx, dy)
            
            if dist > 8:
                target_vx = (dx / dist) * self.walk_speed
                target_vy = (dy / dist) * self.walk_speed
                
                # Smooth acceleration
                self.velocity_x += (target_vx - self.velocity_x) * 4.0 * dt
                self.velocity_y += (target_vy - self.velocity_y) * 4.0 * dt
                
                self.position_x += self.velocity_x * dt
                self.position_y += self.velocity_y * dt
                self.direction_x = 1.0 if dx > 0 else -1.0
            else:
                # Slow down when close to target
                self.velocity_x *= 0.85
                self.velocity_y *= 0.85
                self.position_x += self.velocity_x * dt
                self.position_y += self.velocity_y * dt
        
        elif self.state == "pecking":
            # Stay in place and peck at ground
            if now - self.peck_started_at > self.peck_duration:
                self.state = "landed"
                return
            
            # Decelerate to stop
            self.velocity_x *= 0.8
            self.velocity_y *= 0.8
            self.position_x += self.velocity_x * dt
            self.position_y += self.velocity_y * dt
        
        elif self.state == "flying_out":
            # Fly off-screen with acceleration
            if self.entry_side == "left":
                # Exit right, going up and away
                target_x = self.window_width + 120
            else:
                # Exit left, going up and away
                target_x = -120
            target_y = random.uniform(60, 140)  # Fly upward
            
            dx = target_x - self.position_x
            dy = target_y - self.position_y
            dist = math.hypot(dx, dy)
            
            if dist < 40 or abs(self.position_x) > self.window_width + 150:
                # Off screen, deactivate
                self.state = "inactive"
                self.velocity_x = 0.0
                self.velocity_y = 0.0
            else:
                # Accelerate away (faster than normal flight)
                target_vx = (dx / dist) * self.fly_speed * 1.4
                target_vy = (dy / dist) * self.fly_speed * 1.4
                
                self.velocity_x += (target_vx - self.velocity_x) * 6.0 * dt
                self.velocity_y += (target_vy - self.velocity_y) * 6.0 * dt
                
                self.position_x += self.velocity_x * dt
                self.position_y += self.velocity_y * dt
                self.direction_x = 1.0 if dx > 0 else -1.0

    def draw(self, surface: pygame.Surface) -> None:
        if self.state == "inactive":
            return
        
        # Smooth position interpolation for display
        self.display_position_x = lerp(self.display_position_x, self.position_x, 0.5)
        self.display_position_y = lerp(self.display_position_y, self.position_y, 0.5)
        
        cx = int(self.display_position_x)
        cy = int(self.display_position_y + self.head_bob_offset)  # Apply head bob
        
        # Choose animation based on state
        if self.state == "flying_in" or self.state == "flying_out" or self.state == "hesitating":
            anim_name = "fly"
            fps = 6.0
        elif self.state == "landing":
            anim_name = "fly"  # Use fly animation but slower
            fps = 4.0
        elif self.state == "pecking":
            anim_name = "eat"  # Use eat animation for pecking
            fps = 4.5
        else:  # landed, walking
            current_speed = math.hypot(self.velocity_x, self.velocity_y)
            if current_speed > 5:
                anim_name = "walk"
                # Slower walk animation
                fps = 1.5 + (current_speed / self.walk_speed) * 1.5
            else:
                anim_name = "walk"
                fps = 1.0  # Very slow idle bobbing
        
        # Handle animation transitions
        if anim_name != self.current_anim_name:
            self.prev_anim_name = self.current_anim_name
            self.current_anim_name = anim_name
            self.anim_blend_time = 0.0
            self.anim_time = 0.0
        
        frames = self.sprites.load_sequence(anim_name)
        if frames:
            frame_count = len(frames)
            # Use continuous animation time for smoother playback
            frame_float = (self.anim_time * fps) % frame_count
            frame_index = int(frame_float)
            frame = frames[frame_index]
            
            # Blend with previous animation if transitioning
            if self.anim_blend_time < self.anim_blend_duration and self.prev_anim_name:
                prev_frames = self.sprites.load_sequence(self.prev_anim_name)
                if prev_frames:
                    blend_alpha = self.anim_blend_time / self.anim_blend_duration
                    blend_alpha = ease_in_out_cubic(blend_alpha)
                    
                    prev_frame_index = min(len(prev_frames) - 1, frame_index)
                    prev_frame = prev_frames[prev_frame_index].copy()
                    current_frame = frame.copy()
                    
                    prev_frame.set_alpha(int(255 * (1.0 - blend_alpha)))
                    current_frame.set_alpha(int(255 * blend_alpha))
                    
                    blended = pygame.Surface(frame.get_size(), pygame.SRCALPHA)
                    blended.blit(prev_frame, (0, 0))
                    blended.blit(current_frame, (0, 0))
                    frame = blended
            
            # Flip based on direction
            if self.direction_x < 0:
                frame = pygame.transform.flip(frame, True, False)
            
            if self.render_scale != 1:
                frame = pygame.transform.scale_by(frame, self.render_scale)
            
            rect = frame.get_rect()
            rect.center = (cx, cy)
            surface.blit(frame, rect)


def main() -> None:
    pygame.init()
    try:
        screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.RESIZABLE)
    except pygame.error as err:
        print(f"Failed to create window: {err}")
        pygame.quit()
        sys.exit(1)

    pygame.display.set_caption("Cat Roaming - ADHD_trap")
    clock = pygame.time.Clock()
    
    # Track current window size
    current_width = WINDOW_WIDTH
    current_height = WINDOW_HEIGHT
    
    # Load tiled grass background
    background = None
    background_path = os.path.join(os.path.dirname(__file__), "assets", "background", "grassBackground.png")
    if os.path.exists(background_path):
        try:
            bg_original = pygame.image.load(background_path).convert()
            # Scale to initial window size
            background = pygame.transform.scale(bg_original, (current_width, current_height))
            # Darken the background if configured
            if BACKGROUND_DARKNESS > 0.0:
                dark_overlay = pygame.Surface((current_width, current_height))
                dark_overlay.fill((0, 0, 0))
                dark_overlay.set_alpha(int(255 * BACKGROUND_DARKNESS))
                background.blit(dark_overlay, (0, 0))
        except pygame.error as e:
            print(f"Failed to load background: {e}")
            background = None
    
    # Load environment decorations (grass and flowers) if enabled
    decoration_positions = []
    
    if USE_ENVIRONMENT_DECORATIONS:
        environment_decorations = []
        environment_dir = os.path.join(os.path.dirname(__file__), "assets", "environment")
        
        if os.path.exists(environment_dir):
            for filename in os.listdir(environment_dir):
                if filename.lower().endswith(".png"):
                    try:
                        deco_path = os.path.join(environment_dir, filename)
                        deco = pygame.image.load(deco_path).convert_alpha()
                        environment_decorations.append(deco)
                    except pygame.error:
                        pass
        
        # Place decorations randomly on the field with random sizes
        grid_cols = WINDOW_WIDTH // DECORATION_GRID_SIZE
        grid_rows = WINDOW_HEIGHT // DECORATION_GRID_SIZE
        occupied = set()
        
        # Place decorations based on configured density
        num_decorations = int(grid_cols * grid_rows * DECORATION_DENSITY)
        rng_deco = random.Random(42)  # Fixed seed for consistent decoration placement
        
        for _ in range(num_decorations):
            if not environment_decorations:
                break
            
            attempts = 0
            while attempts < 20:
                grid_x = rng_deco.randint(0, grid_cols - 1)
                grid_y = rng_deco.randint(0, grid_rows - 1)
                
                if (grid_x, grid_y) not in occupied:
                    occupied.add((grid_x, grid_y))
                    
                    # Pick random decoration (no bush logic)
                    deco_original = rng_deco.choice(environment_decorations)
                    
                    # Random size between configured min and max
                    size = rng_deco.randint(DECORATION_SIZE_MIN, DECORATION_SIZE_MAX)
                    deco_scaled = pygame.transform.scale(deco_original, (size, size))
                    
                    # Place decoration at grid position with random offset
                    offset_range = DECORATION_GRID_SIZE - size
                    pos_x = grid_x * DECORATION_GRID_SIZE + rng_deco.randint(0, max(0, offset_range))
                    pos_y = grid_y * DECORATION_GRID_SIZE + rng_deco.randint(0, max(0, offset_range))
                    
                    decoration_positions.append((deco_scaled, pos_x, pos_y))
                    break
                
                attempts += 1
    
    # Generate and place a random bush composition
    bush_composition = None
    bush_position = None
    bush_dir = os.path.join(os.path.dirname(__file__), "assets", "environment", "bush")
    bush1_path = os.path.join(bush_dir, "bush1.png")
    bush2_path = os.path.join(bush_dir, "bush2.png")
    bush3_path = os.path.join(bush_dir, "bush3.png")
    
    if all(os.path.exists(p) for p in [bush1_path, bush2_path, bush3_path]):
        try:
            bush1 = pygame.image.load(bush1_path).convert_alpha()
            bush2 = pygame.image.load(bush2_path).convert_alpha()
            bush3 = pygame.image.load(bush3_path).convert_alpha()
            
            # Generate a random bush composition
            bush_composition = create_bush_composition_surface(bush1, bush2, bush3)
            
            # Place it randomly on the screen (avoid edges)
            bush_margin = 80  # Keep bush away from edges
            bush_x = random.randint(bush_margin, WINDOW_WIDTH - bush_margin)
            bush_y = random.randint(bush_margin, WINDOW_HEIGHT - bush_margin)
            bush_position = (bush_x, bush_y)
        except pygame.error as e:
            print(f"Failed to load bush images: {e}")

    # Initialize cat in center of screen
    cat = Cat((WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2))
    
    # Pigeon spawning variables
    pigeon = Pigeon()
    last_pigeon_spawn_time = time.time()
    pigeon_spawn_interval = random.uniform(10.0, 20.0)  # Next pigeon in 10-20 seconds
    
    # Load food icons
    food_icons = []
    food_dir = os.path.join(os.path.dirname(__file__), "assets", "food")
    if os.path.exists(food_dir):
        for filename in os.listdir(food_dir):
            if filename.lower().endswith(".png"):
                try:
                    icon_path = os.path.join(food_dir, filename)
                    icon = pygame.image.load(icon_path).convert_alpha()
                    # Scale icon to reasonable size (e.g., 32x32)
                    icon = pygame.transform.scale(icon, (32, 32))
                    food_icons.append(icon)
                except pygame.error:
                    pass  # Skip if image fails to load
    
    # Food spawning variables
    rng = random.Random()
    food_pos = None  # Start with no food
    food_icon = None  # Current food icon
    food_radius = 16  # Collision radius
    last_food_spawn_time = time.time()
    food_spawn_interval = rng.uniform(5.0, 10.0)  # Next food appears in 5-10 seconds
    food_disappear_time = 0.0
    food_lifetime = 0.0  # How long food stays before disappearing

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                # Handle window resize
                current_width, current_height = event.w, event.h
                screen = pygame.display.set_mode((current_width, current_height), pygame.RESIZABLE)
                # Rescale background to new size
                if background is not None:
                    bg_original = pygame.image.load(background_path).convert()
                    background = pygame.transform.scale(bg_original, (current_width, current_height))
                    # Darken the background if configured
                    if BACKGROUND_DARKNESS > 0.0:
                        dark_overlay = pygame.Surface((current_width, current_height))
                        dark_overlay.fill((0, 0, 0))
                        dark_overlay.set_alpha(int(255 * BACKGROUND_DARKNESS))
                        background.blit(dark_overlay, (0, 0))
                # Update bush position to stay within new window bounds
                if bush_position is not None:
                    bush_margin = 80
                    bush_x, bush_y = bush_position
                    bush_x = max(bush_margin, min(current_width - bush_margin, bush_x))
                    bush_y = max(bush_margin, min(current_height - bush_margin, bush_y))
                    bush_position = (bush_x, bush_y)

        dt = clock.tick(FPS) / 1000.0
        current_time = time.time()

        # Pigeon spawning logic
        if pigeon.state == "inactive":
            if current_time - last_pigeon_spawn_time > pigeon_spawn_interval:
                pigeon.spawn()
                last_pigeon_spawn_time = current_time
                pigeon_spawn_interval = random.uniform(10.0, 20.0)
        
        # Update pigeon (pass cat position and hissing state so it can flee)
        cat_is_hissing = (cat.state == "hissing" and cat.hiss_target_pigeon)
        pigeon.update(dt, (cat.position_x, cat.position_y), cat_is_hissing)

        # Determine if cat should chase pigeon (only when pigeon is landed or pecking)
        pigeon_target = None
        if pigeon.state == "landed" or pigeon.state == "pecking":
            pigeon_target = (pigeon.position_x, pigeon.position_y, pigeon.velocity_x, pigeon.velocity_y)

        # Update window size for cat and pigeon
        cat.window_width = current_width
        cat.window_height = current_height
        pigeon.window_width = current_width
        pigeon.window_height = current_height
        
        # Food spawning logic
        if food_pos is None:
            # No food present, check if it's time to spawn
            if current_time - last_food_spawn_time > food_spawn_interval:
                # Spawn food anywhere on screen
                food_pos = (rng.randint(60, current_width - 60), rng.randint(60, current_height - 60))
                # Pick random food icon
                if food_icons:
                    food_icon = rng.choice(food_icons)
                food_lifetime = rng.uniform(8.0, 15.0)  # Food stays for 8-15 seconds
                food_disappear_time = current_time + food_lifetime
                last_food_spawn_time = current_time
                food_spawn_interval = rng.uniform(5.0, 10.0)  # Next spawn in 5-10 seconds
        else:
            # Food is present, check if it should disappear
            if current_time > food_disappear_time:
                food_pos = None  # Food disappears
                food_icon = None

        # Update cat (with pigeon target if landed)
        cat.update(dt, food_pos, pigeon_target)
        
        # Check if cat just finished eating (state changed from eat to move)
        if hasattr(cat, '_prev_state'):
            if cat._prev_state == "eat" and cat.state == "move":
                # Food was eaten, remove it
                food_pos = None
                food_icon = None
                last_food_spawn_time = current_time
        cat._prev_state = cat.state

        # Draw background (tiled grass or solid dark green fallback)
        if background is not None:
            screen.blit(background, (0, 0))
        else:
            screen.fill(BACKGROUND_COLOR)
        
        # Draw environment decorations (grass and flowers)
        for deco, x, y in decoration_positions:
            screen.blit(deco, (x, y))
        
        # Draw bush composition if generated
        if bush_composition is not None and bush_position is not None:
            # Center the bush at its position
            bush_rect = bush_composition.get_rect()
            bush_rect.center = bush_position
            screen.blit(bush_composition, bush_rect)
        
        # Draw food icon (or fallback to circle if no icons loaded)
        if food_pos is not None:
            if food_icon is not None:
                # Draw the food icon
                rect = food_icon.get_rect()
                rect.center = (int(food_pos[0]), int(food_pos[1]))
                screen.blit(food_icon, rect)
            else:
                # Fallback to red circle if no icons
                pygame.draw.circle(screen, (220, 40, 40), (int(food_pos[0]), int(food_pos[1])), food_radius)
                pygame.draw.circle(screen, (255, 255, 255), (int(food_pos[0]), int(food_pos[1])), food_radius, 1)

        cat.draw(screen)
        pigeon.draw(screen)

        # Subtle vignette
        overlay = pygame.Surface((current_width, current_height), pygame.SRCALPHA)
        pygame.draw.rect(overlay, (0, 0, 0, 40), overlay.get_rect(), border_radius=28)
        screen.blit(overlay, (0, 0))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()


