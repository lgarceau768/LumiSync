"""
Base class for all sync modes.
Provides common functionality for screen capture, color processing, and device communication.
"""

import threading
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple

import numpy as np
from PIL import Image

from .. import connection
from ..config.options import BRIGHTNESS
from ..sync.monitor import ScreenGrab, apply_brightness
from ..utils.logging import get_logger

logger = get_logger("base_sync")


class BaseSyncMode(ABC):
    """Abstract base class for all sync modes (monitor, music, edge, zone, action, etc)."""

    def __init__(
        self,
        server: Any,
        device: Dict[str, Any],
        position: str = "center",
        brightness: float = 0.75,
    ):
        """
        Initialize sync mode.

        Args:
            server: UDP socket server
            device: Device configuration dictionary
            position: Device position (top, bottom, left, right, center)
            brightness: Brightness multiplier (0.1-1.0)
        """
        self.server = server
        self.device = device
        self.position = position
        self.brightness = brightness
        self.running = False
        self.stop_event = threading.Event()

        # Screen capture for position-based modes
        self._screen_grab = None
        self._prev_frame = None

        logger.info(
            f"Initialized {self.__class__.__name__} for {device.get('model', 'Unknown')} "
            f"at position '{position}' with brightness {brightness:.0%}"
        )

    def _init_screen_grab(self):
        """Initialize screen grabber if needed."""
        if self._screen_grab is None:
            try:
                self._screen_grab = ScreenGrab()
                logger.debug(f"{self.__class__.__name__}: Screen grabber initialized")
            except Exception as e:
                logger.error(f"Failed to initialize screen grabber: {e}")
                raise

    def _capture_screen(self) -> Image.Image | None:
        """Capture current screen."""
        if self._screen_grab is None:
            self._init_screen_grab()

        try:
            return self._screen_grab.capture()
        except Exception as e:
            logger.error(f"Screen capture error: {e}")
            return None

    def enable_razer_mode(self):
        """Enable Razer sync mode on device."""
        try:
            connection.switch_razer(self.server, self.device, True)
            logger.info(f"Razer mode enabled for {self.device.get('model', 'Unknown')}")
        except Exception as e:
            logger.error(f"Failed to enable Razer mode: {e}")

    def disable_razer_mode(self):
        """Disable Razer sync mode on device."""
        try:
            connection.switch_razer(self.server, self.device, False)
            logger.info(f"Razer mode disabled for {self.device.get('model', 'Unknown')}")
        except Exception as e:
            logger.error(f"Failed to disable Razer mode: {e}")

    def send_colors(self, colors: List[Tuple[int, int, int]]):
        """
        Send colors to device.

        Args:
            colors: List of RGB color tuples
        """
        try:
            from ..utils.colors import convert_colors

            # Apply brightness
            adjusted_colors = apply_brightness(colors, self.brightness)

            # Encode and send
            encoded = convert_colors(adjusted_colors)
            connection.send_razer_data(self.server, self.device, encoded)

            logger.debug(
                f"Sent {len(colors)} colors to {self.device.get('model', 'Unknown')}"
            )
        except Exception as e:
            logger.error(f"Error sending colors: {e}")

    def calculate_screen_brightness(self, screen: Image.Image) -> float:
        """
        Calculate average brightness of screen (0.0-1.0).

        Args:
            screen: PIL Image of screen

        Returns:
            Average brightness value
        """
        try:
            screen_array = np.array(screen)

            # Handle RGBA -> RGB
            if screen_array.shape[2] == 4:
                screen_array = screen_array[:, :, :3]

            # Convert to grayscale and calculate average
            gray = np.mean(screen_array, axis=2)
            brightness = np.mean(gray) / 255.0

            return brightness
        except Exception as e:
            logger.error(f"Error calculating screen brightness: {e}")
            return 0.5

    def get_vibrant_color_from_region(
        self, screen: Image.Image, x1: int, y1: int, x2: int, y2: int
    ) -> Tuple[int, int, int]:
        """
        Get the most vibrant color from a screen region.

        Args:
            screen: PIL Image
            x1, y1, x2, y2: Region bounds

        Returns:
            RGB tuple of most vibrant color
        """
        try:
            from ..sync.monitor import _get_most_vibrant_color

            # Calculate center of region
            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2
            region_size = (x2 - x1, y2 - y1)

            return _get_most_vibrant_color(screen, center_x, center_y, region_size)
        except Exception as e:
            logger.error(f"Error getting vibrant color: {e}")
            return (128, 128, 128)  # Fallback gray

    @abstractmethod
    def capture_data(self) -> Any:
        """
        Capture input data (screen, audio, etc).

        Returns:
            Mode-specific data (screen, audio frame, etc)
        """
        pass

    @abstractmethod
    def generate_colors(self, data: Any) -> List[Tuple[int, int, int]]:
        """
        Generate LED colors from captured data.

        Args:
            data: Data from capture_data()

        Returns:
            List of RGB color tuples
        """
        pass

    def run(self):
        """Main sync loop. Runs until stop_event is set."""
        logger.info(f"Starting {self.__class__.__name__} sync loop")
        self.running = True
        self.enable_razer_mode()

        try:
            frame_count = 0
            while not self.stop_event.is_set():
                frame_count += 1
                try:
                    # Capture data
                    data = self.capture_data()

                    if data is None:
                        logger.debug(f"No data captured (frame {frame_count})")
                        time.sleep(0.01)
                        continue

                    # Generate colors
                    colors = self.generate_colors(data)

                    if colors and len(colors) > 0:
                        # Send to device
                        self.send_colors(colors)

                        # Log periodically
                        if frame_count % 60 == 0:
                            logger.debug(
                                f"{self.__class__.__name__} frame {frame_count}: "
                                f"sent {len(colors)} colors to {self.device.get('model', 'Unknown')}"
                            )

                except Exception as e:
                    logger.error(f"Error in sync loop (frame {frame_count}): {e}")
                    time.sleep(0.1)

        except KeyboardInterrupt:
            logger.info(f"{self.__class__.__name__} interrupted by user")
        except Exception as e:
            logger.error(f"Fatal error in {self.__class__.__name__} sync loop: {e}")
        finally:
            self.running = False
            self.disable_razer_mode()
            logger.info(f"Stopped {self.__class__.__name__} sync loop")

    def stop(self):
        """Stop the sync loop."""
        logger.info(f"Stopping {self.__class__.__name__}")
        self.stop_event.set()
