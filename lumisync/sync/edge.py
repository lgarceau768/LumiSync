"""
Edge/Ambient lighting mode for gaming.
Samples colors from monitor edges based on device position and creates immersive ambient lighting.
"""

import time
from typing import Any, Dict, List, Tuple

from PIL import Image

from .base_sync import BaseSyncMode
from ..utils.logging import get_logger

logger = get_logger("edge_sync")


class EdgeSyncMode(BaseSyncMode):
    """
    Edge/Ambient lighting sync mode.

    Samples colors from screen edges corresponding to device position:
    - Top device: samples top edge
    - Bottom device: samples bottom edge
    - Left device: samples left edge
    - Right device: samples right edge
    - Center device: averages all edges
    """

    EDGE_STRIP_HEIGHT = 0.1  # Sample 10% of screen height/width from edge

    def __init__(self, server: Any, device: Dict[str, Any], position: str = "center"):
        """
        Initialize edge lighting mode.

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

    def _sample_edge_strip(
        self, screen: Image.Image, position: str
    ) -> List[Tuple[int, int, int]]:
        """
        Sample colors from a specific edge of the screen.

        Args:
            screen: Screen image
            position: Edge position (top, bottom, left, right, center)

        Returns:
            List of RGB colors sampled from the edge
        """
        width, height = screen.size
        colors = []

        try:
            if position == "top":
                # Sample top edge strip
                edge_height = int(height * self.EDGE_STRIP_HEIGHT)
                edge_region = screen.crop((0, 0, width, edge_height))

            elif position == "bottom":
                # Sample bottom edge strip
                edge_height = int(height * self.EDGE_STRIP_HEIGHT)
                edge_region = screen.crop(
                    (0, height - edge_height, width, height)
                )

            elif position == "left":
                # Sample left edge strip
                edge_width = int(width * self.EDGE_STRIP_HEIGHT)
                edge_region = screen.crop((0, 0, edge_width, height))

            elif position == "right":
                # Sample right edge strip
                edge_width = int(width * self.EDGE_STRIP_HEIGHT)
                edge_region = screen.crop((width - edge_width, 0, width, height))

            elif position == "center":
                # For center, sample all edges and average them
                # Sample 5% from each edge
                edge_thickness = int(min(width, height) * 0.05)
                colors = self._sample_all_edges(screen, edge_thickness)
                return colors

            else:
                logger.warning(f"Unknown position: {position}, using center")
                edge_thickness = int(min(width, height) * 0.05)
                colors = self._sample_all_edges(screen, edge_thickness)
                return colors

            # Divide edge region into num_leds segments and sample vibrant color from each
            colors = self._segment_and_sample(edge_region, position)

        except Exception as e:
            logger.error(f"Error sampling edge strip for {position}: {e}")
            # Return default neutral colors
            colors = [(128, 128, 128)] * self.num_leds

        return colors

    def _segment_and_sample(
        self, edge_region: Image.Image, position: str
    ) -> List[Tuple[int, int, int]]:
        """
        Divide edge region into segments and sample vibrant color from each.

        Args:
            edge_region: Cropped edge region of screen
            position: Edge position

        Returns:
            List of RGB colors
        """
        colors = []
        region_width, region_height = edge_region.size

        if position in ["top", "bottom"]:
            # Divide horizontally
            segment_width = region_width // self.num_leds

            for i in range(self.num_leds):
                x1 = i * segment_width
                x2 = x1 + segment_width if i < self.num_leds - 1 else region_width
                y1 = 0
                y2 = region_height

                # Get vibrant color from this segment
                color = self.get_vibrant_color_from_region(
                    edge_region, x1, y1, x2, y2
                )
                colors.append(color)

        else:  # left, right
            # Divide vertically
            segment_height = region_height // self.num_leds

            for i in range(self.num_leds):
                y1 = i * segment_height
                y2 = y1 + segment_height if i < self.num_leds - 1 else region_height
                x1 = 0
                x2 = region_width

                # Get vibrant color from this segment
                color = self.get_vibrant_color_from_region(
                    edge_region, x1, y1, x2, y2
                )
                colors.append(color)

        return colors

    def _sample_all_edges(self, screen: Image.Image, thickness: int) -> List[Tuple[int, int, int]]:
        """
        Sample from all edges and average them for center position.

        Args:
            screen: Screen image
            thickness: Edge thickness in pixels

        Returns:
            List of blended colors
        """
        width, height = screen.size
        colors = []

        try:
            # Sample from each edge
            top_colors = self._segment_and_sample(
                screen.crop((0, 0, width, thickness)), "top"
            )
            bottom_colors = self._segment_and_sample(
                screen.crop((0, height - thickness, width, height)), "bottom"
            )
            left_colors = self._segment_and_sample(
                screen.crop((0, 0, thickness, height)), "left"
            )
            right_colors = self._segment_and_sample(
                screen.crop((width - thickness, 0, width, height)), "right"
            )

            # Blend colors from each edge (simple average)
            for i in range(self.num_leds):
                r = (top_colors[i][0] + bottom_colors[i][0] + left_colors[i][0] + right_colors[i][0]) // 4
                g = (top_colors[i][1] + bottom_colors[i][1] + left_colors[i][1] + right_colors[i][1]) // 4
                b = (top_colors[i][2] + bottom_colors[i][2] + left_colors[i][2] + right_colors[i][2]) // 4
                colors.append((r, g, b))

        except Exception as e:
            logger.error(f"Error sampling all edges: {e}")
            colors = [(128, 128, 128)] * self.num_leds

        return colors

    def generate_colors(self, data: Any) -> List[Tuple[int, int, int]]:
        """
        Generate edge lighting colors from screen capture.

        Args:
            data: Screen image from capture_data()

        Returns:
            List of RGB colors for LEDs
        """
        if data is None:
            return []

        try:
            screen: Image.Image = data
            colors = self._sample_edge_strip(screen, self.position)
            return colors

        except Exception as e:
            logger.error(f"Error generating edge colors: {e}")
            return []
