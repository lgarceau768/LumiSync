import socket
import time
from functools import partial
from typing import Any, Dict, List, Tuple

import colour
import numpy as np
from PIL import Image

from .. import connection, utils
from ..config.options import BRIGHTNESS, GENERAL
from ..utils.logging import get_logger

logger = get_logger("monitor_sync")


class ScreenGrab:
    """Facilitates taking a screenshot while supporting
    different platforms and compositors (the latter for Unix).
    """

    def __init__(self) -> None:
        if GENERAL.platform == "Windows":
            import dxcam

            self.camera = dxcam.create()
            self.capture_method = self.camera.grab
        else:
            if GENERAL.compositor == "x11":
                import mss

                self.camera = mss.mss()
                self.capture_method = partial(self.camera.grab, self.camera.monitors[0])
            else:
                # TODO: Implement Wayland support
                raise NotImplementedError("Wayland support is not yet implemented in ScreenGrab.")

    def capture(self) -> Image.Image | None:
        """Captures a screenshot."""
        screen = self.capture_method()
        if screen is None:
            return screen

        if GENERAL.platform != "Windows" and GENERAL.compositor == "x11":
            screen = np.array(screen)[..., [2, 1, 0]]

        return Image.fromarray(screen)


def sample_screen_colors(
    screen: Image.Image, num_colors: int
) -> List[Tuple[int, int, int]]:
    """Sample colors from screen regions to fill the specified number of LEDs.

    For 4 or fewer colors, uses strategic corner/edge sampling for better monitor coverage.
    For more colors, divides the screen into a grid and samples from each region.

    Args:
        screen: PIL Image from screen capture
        num_colors: Number of colors to sample (should match number of LEDs)

    Returns:
        List of RGB color tuples
    """
    width, height = screen.size
    logger.debug(f"Screen: {width}x{height}, Colors to sample: {num_colors}")

    # Use strategic sampling for 4 or fewer LEDs (better edge coverage)
    if num_colors <= 4:
        return _sample_strategic(screen, num_colors)

    # Use grid-based sampling for more LEDs
    return _sample_grid(screen, num_colors)


def _get_most_vibrant_color(
    screen: Image.Image, center_x: int, center_y: int, region_size: Tuple[int, int]
) -> Tuple[int, int, int]:
    """Extract the most vibrant (saturated + bright) color from a screen region.

    Samples a rectangular region around the center point and finds the pixel with
    the highest saturation * brightness score in HSV color space. This captures
    the most visually prominent colors (e.g., explosions, bright UI elements).

    Args:
        screen: PIL Image of screen capture
        center_x: X coordinate of region center
        center_y: Y coordinate of region center
        region_size: Tuple of (width, height) of region to sample

    Returns:
        RGB tuple of the most vibrant color found in the region
    """
    region_width, region_height = region_size

    # Calculate region bounds
    x1 = max(0, center_x - region_width // 2)
    y1 = max(0, center_y - region_height // 2)
    x2 = min(screen.width, center_x + region_width // 2)
    y2 = min(screen.height, center_y + region_height // 2)

    # Crop region
    region = screen.crop((x1, y1, x2, y2))
    region_array = np.array(region)

    # Handle RGBA -> RGB
    if region_array.shape[2] == 4:
        region_array = region_array[:, :, :3]

    # Convert RGB to HSV using numpy
    # Normalize RGB to 0-1
    rgb_normalized = region_array.astype(np.float32) / 255.0

    # Convert RGB to HSV manually for speed (avoid PIL/colour library overhead)
    # H (Hue): 0-1, S (Saturation): 0-1, V (Value/Brightness): 0-1
    max_c = np.max(rgb_normalized, axis=2)
    min_c = np.min(rgb_normalized, axis=2)
    delta = max_c - min_c

    # Saturation: ratio of color purity
    saturation = np.where(max_c != 0, delta / max_c, 0)

    # Value/Brightness: brightness of color
    value = max_c

    # Vibrance score: combination of saturation and brightness
    # Prioritizes colors that are both vivid AND bright
    vibrance = saturation * value

    # Find pixel with maximum vibrance
    vibrance_flat = vibrance.reshape(-1)
    max_idx = np.argmax(vibrance_flat)
    max_row = max_idx // vibrance.shape[1]
    max_col = max_idx % vibrance.shape[1]

    # Get the RGB color of the most vibrant pixel
    most_vibrant_rgb = region_array[max_row, max_col]

    logger.debug(
        f"Vibrant color search: center=({center_x},{center_y}), region_size={region_size}, "
        f"max_vibrance={vibrance_flat[max_idx]:.3f}, color=RGB{tuple(most_vibrant_rgb)}"
    )

    return tuple(most_vibrant_rgb)


def _apply_rotation(colors: List[Tuple[int, int, int]], rotation: int) -> List[Tuple[int, int, int]]:
    """Apply color rotation to reorder LED positions.

    Rotates the color mapping for 4 LEDs by the specified angle (0, 90, 180, 270).
    Useful when the physical rope orientation doesn't match screen positions.

    Args:
        colors: List of RGB colors in order [TL, TR, BL, BR]
        rotation: Rotation angle in degrees (0, 90, 180, 270)

    Returns:
        Rotated color list
    """
    if len(colors) != 4:
        # Only rotate 4-LED setup
        return colors

    # Rotation mappings: which original position goes to which new position
    rotation_map = {
        0: [0, 1, 2, 3],      # No rotation: TL-TR-BL-BR
        90: [2, 0, 3, 1],     # 90° CW: BL-TL-BR-TR
        180: [3, 2, 1, 0],    # 180°: BR-BL-TR-TL
        270: [1, 3, 0, 2],    # 270° CW: TR-BR-TL-BL
    }

    if rotation not in rotation_map:
        logger.warning(f"Invalid rotation angle {rotation}°, using 0°")
        return colors

    if rotation == 0:
        return colors  # No rotation needed

    mapping = rotation_map[rotation]
    rotated = [colors[i] for i in mapping]

    logger.debug(f"Applied {rotation}° color rotation: {mapping}")
    return rotated


def _sample_strategic(screen: Image.Image, num_colors: int) -> List[Tuple[int, int, int]]:
    """Sample from strategic positions and find most vibrant colors for optimal gaming response.

    For gaming syncing, strategic corner/edge sampling with vibrant color detection captures
    the most visually prominent effects (explosions, muzzle flashes, bright UI elements)
    rather than single-pixel sampling which might hit dark backgrounds.
    """
    width, height = screen.size
    colors = []

    # Define sampling positions as percentages from edges
    # These represent corners/edges where important UI content typically appears
    if num_colors == 1:
        positions = [(50, 50)]  # Center
    elif num_colors == 2:
        positions = [(25, 50), (75, 50)]  # Left and right halves
    elif num_colors == 3:
        positions = [(25, 25), (75, 25), (50, 75)]  # Triangle pattern
    else:  # 4 LEDs
        positions = [
            (20, 20),   # Top-left
            (80, 20),   # Top-right
            (20, 80),   # Bottom-left
            (80, 80),   # Bottom-right
        ]

    logger.debug(f"Using strategic vibrant color sampling with {len(positions)} positions")

    # Calculate region size: 10% of screen dimensions for sufficient sampling area
    region_width = int(width * 0.10)
    region_height = int(height * 0.10)
    region_size = (region_width, region_height)

    logger.debug(f"Region size: {region_size} pixels")

    for pos_num, (x_pct, y_pct) in enumerate(positions, 1):
        center_x = int((x_pct / 100) * width)
        center_y = int((y_pct / 100) * height)

        # Clamp center to valid range
        center_x = max(0, min(center_x, width - 1))
        center_y = max(0, min(center_y, height - 1))

        # Get the most vibrant color in the region
        color = _get_most_vibrant_color(screen, center_x, center_y, region_size)

        colors.append(color)
        logger.debug(f"Position {pos_num}: ({x_pct}%, {y_pct}%) -> vibrant color {color}")

    # Apply color rotation if configured
    colors = _apply_rotation(colors, GENERAL.color_rotation)

    return colors


def _sample_grid(screen: Image.Image, num_colors: int) -> List[Tuple[int, int, int]]:
    """Sample using grid-based approach: divides screen into grid cells and samples from each.

    Used for higher LED counts (5+) where edge/corner sampling alone isn't sufficient.
    """
    width, height = screen.size

    # Create a simple grid layout: try to make rows and cols roughly square
    cols = int(np.sqrt(num_colors))
    rows = (num_colors + cols - 1) // cols  # Ceiling division

    logger.debug(f"Grid: {cols}x{rows} cells")

    colors = []
    cell_width = width / cols
    cell_height = height / rows

    for row in range(rows):
        for col in range(cols):
            if len(colors) >= num_colors:
                break

            # Sample from the center of each grid cell
            x1 = int(col * cell_width)
            y1 = int(row * cell_height)
            x2 = int((col + 1) * cell_width)
            y2 = int((row + 1) * cell_height)

            img = screen.crop((x1, y1, x2, y2))
            # Get pixel from center of cell
            center_x = img.size[0] // 2
            center_y = img.size[1] // 2
            color = img.getpixel((center_x, center_y))

            # Handle both RGB and RGBA formats
            if isinstance(color, tuple) and len(color) == 4:
                color = color[:3]  # Drop alpha channel

            colors.append(color)

    logger.debug(f"Sampled {len(colors)} colors. First 10: {colors[:10]}")
    return colors


def start(server: socket.socket, device: Dict[str, Any]) -> None:
    """Starts the monitor-light synchronization."""
    logger.info("Enabling Razer mode...")
    connection.switch_razer(server, device, True)
    screen_grab = ScreenGrab()

    # Initialize with black colors for all LEDs
    num_leds = GENERAL.nled
    previous_colors = [(0, 0, 0)] * num_leds
    logger.info(f"Starting monitor sync with {num_leds} LEDs")

    frame_count = 0
    logger.info("Entering main sync loop...")
    logger.info(f"Brightness setting: {BRIGHTNESS.monitor * 100}%")

    while True:
        frame_count += 1
        try:
            screen = screen_grab.capture()
            if screen is None:
                if frame_count == 1:
                    logger.warning("Screenshot returned None on first frame")
                continue

            width, height = screen.size
            if frame_count == 1:
                logger.debug(f"Screen captured: {width}x{height}")
        except OSError as e:
            if frame_count == 1:
                logger.error(f"Screenshot failed on first frame: {e}")
            continue
        except Exception as e:
            if frame_count == 1:
                logger.error(f"Unexpected error capturing screen on first frame: {e}")
            continue

        try:
            # Sample colors from screen regions to fill all LEDs
            # Divide screen into a grid and sample from each region
            colors = sample_screen_colors(screen, num_leds)

            if frame_count == 1:
                logger.debug(f"Sampled colors (before brightness): {colors[:10]}...")

            # Apply brightness setting to colors
            colors = apply_brightness(colors, BRIGHTNESS.monitor)

            if frame_count == 1:
                logger.debug(f"Sampled colors (after brightness): {colors[:10]}...")
                # Check if all colors are black
                all_black = all(c == (0, 0, 0) for c in colors)
                if all_black:
                    logger.warning("All colors are black!")

            # Log every 30 frames to avoid log spam
            if frame_count % 30 == 0:
                sample_colors = colors[:5]  # Show first 5 colors
                logger.info(f"Frame {frame_count}: Sending {len(colors)} colors - Sample: {sample_colors}...")

            # Use faster transition for more responsive monitor sync (fewer steps, shorter delay)
            smooth_transition(server, device, previous_colors, colors, steps=3, delay=0.002)
            previous_colors = colors
        except Exception as e:
            logger.error(f"Error in frame {frame_count}: {e}", exc_info=True)
            time.sleep(0.1)  # Avoid tight loop on error


def apply_brightness(
    colors: List[Tuple[int, int, int]], brightness_factor: float
) -> List[Tuple[int, int, int]]:
    """Apply brightness factor to a list of colors.

    Args:
        colors: List of RGB color tuples
        brightness_factor: Brightness factor (0.0 to 1.0)

    Returns:
        List of adjusted RGB color tuples
    """
    return [
        (
            int(r * brightness_factor),
            int(g * brightness_factor),
            int(b * brightness_factor),
        )
        for r, g, b in colors
    ]


def smooth_transition(
    server: socket.socket,
    device: Dict[str, Any],
    previous_colors: List[Tuple[float, float, float]],
    colors: List[Tuple[float, float, float]],
    steps: int = 10,
    delay: float = 0.01,
) -> None:
    """Computes a smooth transition of the colors and sends it to a device."""
    try:
        prev_colors = [
            colour.Color(rgb=(c[0] / 255, c[1] / 255, c[2] / 255)) for c in previous_colors
        ]
        next_colors = [
            colour.Color(rgb=(c[0] / 255, c[1] / 255, c[2] / 255)) for c in colors
        ]
    except Exception as e:
        logger.error(f"Error converting colors in smooth_transition: {e}")
        return

    logger.debug(f"Starting {steps}-step transition for {len(colors)} colors to {device.get('model', 'Unknown')}")

    # TODO: There is probably a quicker way to do this with the numpy package or so -> Check
    for step in range(steps):
        try:
            interpolated_colors = []
            for i in range(len(colors)):
                r = utils.lerp(prev_colors[i].red, next_colors[i].red, step / steps)
                g = utils.lerp(prev_colors[i].green, next_colors[i].green, step / steps)
                b = utils.lerp(prev_colors[i].blue, next_colors[i].blue, step / steps)
                interpolated_colors.append((int(r * 255), int(g * 255), int(b * 255)))

            encoded_data = utils.convert_colors(interpolated_colors)

            if step == 0:  # Log first step details
                logger.debug(f"Step {step}: First 5 colors: {interpolated_colors[:5]}")
                logger.debug(f"Step {step}: Encoded data length: {len(encoded_data)}")

            connection.send_razer_data(server, device, encoded_data)

            if step == 0:
                logger.debug(f"Successfully sent data to {device.get('model', 'Unknown')}")
        except Exception as e:
            logger.error(f"Error sending colors in smooth_transition step {step}: {e}")
            raise

        time.sleep(delay)
