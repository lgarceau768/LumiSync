"""
Action/Effect detection mode for gaming.
Detects bright flashes, explosions, and high-intensity events and triggers reactive lighting.
"""

import time
from typing import Any, Dict, List, Tuple

import numpy as np
from PIL import Image

from .base_sync import BaseSyncMode
from ..utils.logging import get_logger

logger = get_logger("action_sync")


class ActionSyncMode(BaseSyncMode):
    """
    Action/Effect detection sync mode.

    Monitors screen for sudden brightness changes (explosions, flashes, muzzle flashes)
    and triggers reactive lighting with detected colors. Falls back to ambient colors
    when no action is detected.
    """

    # Action detection thresholds
    FLASH_THRESHOLD = 0.3  # Brightness increase threshold to trigger flash (0-1.0)
    FLASH_DURATION = 0.5  # How long flash color stays (seconds)
    FLASH_FADE_TIME = 0.2  # Fade duration back to normal (seconds)

    def __init__(self, server: Any, device: Dict[str, Any], position: str = "center"):
        """
        Initialize action detection mode.

        Args:
            server: UDP socket server
            device: Device configuration
            position: Device position (top, bottom, left, right, center)
        """
        brightness = device.get("brightness", 0.75)
        super().__init__(server, device, position, brightness)
        self.num_leds = device.get("nled", 4)

        # State tracking
        self.last_brightness = 0.5
        self.flash_end_time = 0.0
        self.flash_color = None
        self.normal_colors = None

    def capture_data(self) -> Tuple[Image.Image | None, float] | None:
        """
        Capture current screen and calculate brightness.

        Returns:
            Tuple of (screen_image, brightness) or None
        """
        try:
            screen = self._capture_screen()
            if screen is None:
                return None

            brightness = self.calculate_screen_brightness(screen)
            return (screen, brightness)

        except Exception as e:
            logger.error(f"Error capturing data: {e}")
            return None

    def _detect_flash(self, current_brightness: float) -> bool:
        """
        Detect if a flash event occurred.

        Args:
            current_brightness: Current screen brightness

        Returns:
            True if flash detected, False otherwise
        """
        brightness_delta = current_brightness - self.last_brightness

        if brightness_delta > self.FLASH_THRESHOLD:
            logger.info(f"Flash detected! Brightness delta: {brightness_delta:.2f}")
            return True

        return False

    def _get_most_saturated_color(self, screen: Image.Image) -> Tuple[int, int, int]:
        """
        Get the most saturated/vibrant color from the entire screen.
        This is the color that will flash.

        Args:
            screen: Screen image

        Returns:
            RGB tuple of most saturated color
        """
        try:
            # Use the entire screen as region
            width, height = screen.size
            return self.get_vibrant_color_from_region(screen, 0, 0, width, height)

        except Exception as e:
            logger.error(f"Error finding saturated color: {e}")
            return (255, 255, 255)  # Default white

    def _get_ambient_colors(self, screen: Image.Image) -> List[Tuple[int, int, int]]:
        """
        Get ambient colors from screen (fallback when no action).

        Uses a simple version of edge sampling for ambient lighting.

        Args:
            screen: Screen image

        Returns:
            List of RGB colors
        """
        try:
            from .edge import EdgeSyncMode

            # Create temporary edge sync mode to get ambient colors
            edge_mode = EdgeSyncMode(self.server, self.device, self.position)
            return edge_mode.generate_colors(screen)

        except Exception as e:
            logger.error(f"Error generating ambient colors: {e}")
            return [(64, 64, 64)] * self.num_leds

    def _interpolate_colors(
        self,
        start_colors: List[Tuple[int, int, int]],
        end_colors: List[Tuple[int, int, int]],
        progress: float,  # 0.0 to 1.0
    ) -> List[Tuple[int, int, int]]:
        """
        Interpolate between two color lists.

        Args:
            start_colors: Starting colors
            end_colors: Ending colors
            progress: Interpolation progress (0.0-1.0)

        Returns:
            Interpolated color list
        """
        result = []
        for start, end in zip(start_colors, end_colors):
            r = int(start[0] + (end[0] - start[0]) * progress)
            g = int(start[1] + (end[1] - start[1]) * progress)
            b = int(start[2] + (end[2] - start[2]) * progress)
            result.append((r, g, b))
        return result

    def generate_colors(self, data: Any) -> List[Tuple[int, int, int]]:
        """
        Generate action/effect detection colors.

        Args:
            data: Tuple of (screen_image, brightness)

        Returns:
            List of RGB colors for LEDs
        """
        if data is None:
            return []

        try:
            screen, current_brightness = data

            # Check if we're still in a flash
            current_time = time.time()
            if current_time < self.flash_end_time:
                # Still flashing - return flash color with fade
                elapsed = current_time - (self.flash_end_time - self.FLASH_DURATION)
                fade_progress = 1.0 - (elapsed / self.FLASH_FADE_TIME)

                if fade_progress > 0:
                    # Fade from flash color to normal
                    fade_colors = self._interpolate_colors(
                        self.flash_color,
                        self.normal_colors,
                        1.0 - max(0, fade_progress),
                    )
                    return fade_colors
                else:
                    # Fade complete, return normal colors
                    return self.normal_colors

            # Not in flash - check for new flash
            if self._detect_flash(current_brightness):
                # Flash detected!
                self.flash_color = [self._get_most_saturated_color(screen)] * self.num_leds
                self.normal_colors = self._get_ambient_colors(screen)
                self.flash_end_time = current_time + self.FLASH_DURATION
                return self.flash_color

            # No flash - return ambient colors
            self.normal_colors = self._get_ambient_colors(screen)
            self.last_brightness = current_brightness
            return self.normal_colors

        except Exception as e:
            logger.error(f"Error generating action colors: {e}")
            return [(128, 128, 128)] * self.num_leds
