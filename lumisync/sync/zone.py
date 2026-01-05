"""
Zone-based lighting mode for gaming.
Divides screen into zones and sends zone-specific colors to devices based on their position.
"""

from typing import Any, Dict, List, Tuple

from PIL import Image

from .base_sync import BaseSyncMode
from ..utils.logging import get_logger

logger = get_logger("zone_sync")


class ZoneSyncMode(BaseSyncMode):
    """
    Zone-based lighting sync mode.

    Divides screen into zones and maps device positions to zones:
    - Top device: samples top-left, top-center, top-right zones
    - Bottom device: samples bottom-left, bottom-center, bottom-right zones
    - Left device: samples left-top, left-center, left-bottom zones
    - Right device: samples right-top, right-center, right-bottom zones
    - Center device: averages all zones
    """

    def __init__(self, server: Any, device: Dict[str, Any], position: str = "center"):
        """
        Initialize zone lighting mode.

        Args:
            server: UDP socket server
            device: Device configuration
            position: Device position (top, bottom, left, right, center)
        """
        brightness = device.get("brightness", 0.75)
        super().__init__(server, device, position, brightness)
        self.num_leds = device.get("nled", 4)

    def capture_data(self) -> Image.Image | None:
        """Capture current screen."""
        return self._capture_screen()

    def _get_zone_bounds(self, screen_width: int, screen_height: int, zone: str) -> Tuple[int, int, int, int]:
        """
        Get pixel bounds for a specific zone.

        Args:
            screen_width: Screen width in pixels
            screen_height: Screen height in pixels
            zone: Zone identifier (top-left, top-right, bottom-left, bottom-right, etc)

        Returns:
            (x1, y1, x2, y2) bounds
        """
        # Divide screen into thirds for zones
        third_w = screen_width // 3
        third_h = screen_height // 3

        zone_map = {
            # Quadrants
            "top-left": (0, 0, third_w * 2, third_h * 2),
            "top-right": (third_w, 0, screen_width, third_h * 2),
            "bottom-left": (0, third_h, third_w * 2, screen_height),
            "bottom-right": (third_w, third_h, screen_width, screen_height),
            # Halves
            "top-half": (0, 0, screen_width, screen_height // 2),
            "bottom-half": (0, screen_height // 2, screen_width, screen_height),
            "left-half": (0, 0, screen_width // 2, screen_height),
            "right-half": (screen_width // 2, 0, screen_width, screen_height),
            # Full
            "center": (0, 0, screen_width, screen_height),
        }

        return zone_map.get(zone, (0, 0, screen_width, screen_height))

    def _sample_zone_colors(self, screen: Image.Image, position: str) -> List[Tuple[int, int, int]]:
        """
        Sample colors from zones appropriate for device position.

        Args:
            screen: Screen image
            position: Device position

        Returns:
            List of RGB colors
        """
        width, height = screen.size
        colors = []

        try:
            if position == "top":
                # Sample top zones
                zones = [
                    "top-left",
                    "top-left",  # Center-left
                    "top-right",
                    "top-right",  # Center-right
                ]

            elif position == "bottom":
                # Sample bottom zones
                zones = [
                    "bottom-left",
                    "bottom-left",
                    "bottom-right",
                    "bottom-right",
                ]

            elif position == "left":
                # Sample left zones (vertically oriented)
                zones = ["top-left", "left-half", "bottom-left", "left-half"]

            elif position == "right":
                # Sample right zones (vertically oriented)
                zones = ["top-right", "right-half", "bottom-right", "right-half"]

            elif position == "center":
                # Sample all zones evenly
                zones = [
                    "top-left",
                    "top-right",
                    "bottom-left",
                    "bottom-right",
                ]

            else:
                logger.warning(f"Unknown position: {position}, using center")
                zones = ["top-left", "top-right", "bottom-left", "bottom-right"]

            # Sample vibrant color from each zone
            for zone in zones[:self.num_leds]:
                x1, y1, x2, y2 = self._get_zone_bounds(width, height, zone)
                color = self.get_vibrant_color_from_region(screen, x1, y1, x2, y2)
                colors.append(color)

            # Pad with gray if needed
            while len(colors) < self.num_leds:
                colors.append((128, 128, 128))

        except Exception as e:
            logger.error(f"Error sampling zone colors for {position}: {e}")
            colors = [(128, 128, 128)] * self.num_leds

        return colors

    def generate_colors(self, data: Any) -> List[Tuple[int, int, int]]:
        """
        Generate zone lighting colors from screen capture.

        Args:
            data: Screen image from capture_data()

        Returns:
            List of RGB colors for LEDs
        """
        if data is None:
            return []

        try:
            screen: Image.Image = data
            colors = self._sample_zone_colors(screen, self.position)
            return colors

        except Exception as e:
            logger.error(f"Error generating zone colors: {e}")
            return []
