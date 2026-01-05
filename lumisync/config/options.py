import os
import platform
from types import SimpleNamespace


def _detect_compositor() -> str:
    """Detects the display server for a Unix platform."""
    if (
        os.environ.get("WAYLAND_DISPLAY")
        or os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
        or "wayland" in os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    ):
        return "wayland"

    return "x11"


# TODO: Should the led option be moved under a different global?
GENERAL = SimpleNamespace(nled=4, platform=platform.system(), compositor=None, color_rotation=0)
if GENERAL.platform != "Windows":
    GENERAL.compositor = _detect_compositor()

# TODO: Replace the settings.json with this during runtime
# and only use the settings.json on restart?
CONNECTION = SimpleNamespace(
    default=SimpleNamespace(
        multicast="255.255.255.255",
        port=4001,
        listen_port=4002,
        timeout=1,
    ),
    devices=[],
)
# NOTE: Duration (seconds)
AUDIO = SimpleNamespace(sample_rate=48000, duration=0.01)

# TODO: This needs to change as soon as support for multiple devices
# is being implemented -> Similar with next as for the devices query?
COLORS = SimpleNamespace(previous=[], current=[])

# NOTE: Brightness settings for different sync modes (percent)
BRIGHTNESS = SimpleNamespace(monitor=0.75, music=0.85)

# Device configuration defaults
DEVICE_CONFIG = SimpleNamespace(
    position="center",  # top, bottom, left, right, center
    sync_mode="monitor",  # monitor, music, edge, zone, action
    brightness=0.75,  # 0.0-1.0
    nled=4,  # Number of LEDs
    color_rotation=0,  # 0, 90, 180, 270
)
