"""
Sync controller for the LumiSync GUI.
This module handles synchronization functionality (monitor sync and music sync).
"""

import platform
import socket
import threading
import time
from typing import Any, Callable, Dict, Optional

if platform.system() == "Windows":
    from pythoncom import CoInitializeEx, CoUninitialize

from ... import connection, devices, utils
from ...config.options import AUDIO, BRIGHTNESS, COLORS, GENERAL
from ...sync import monitor, music
from ...utils import get_logger

logger = get_logger("sync_controller")


class SyncController:
    """Controller for managing synchronization."""

    def __init__(self, status_callback: Callable[[str], None] | None = None):
        """
        Initialize the sync controller.

        Args:
            status_callback: Callback function to update status messages
        """
        self.status_callback = status_callback
        self.sync_thread = None
        self.stop_event = threading.Event()
        self.current_sync_mode = None
        self.server = None
        self.selected_device = None
        self.all_devices = []  # List of all devices for syncing

        # Initialize brightness settings from config
        self.monitor_brightness = BRIGHTNESS.monitor
        self.music_brightness = BRIGHTNESS.music

        # Initialize with available device if any
        self._init_device()

    def _init_device(self):
        """Initialize with available devices."""
        try:
            settings = devices.get_data()
            if settings["devices"] and len(settings["devices"]) > 0:
                self.all_devices = settings["devices"]
                self.selected_device = settings["devices"][settings["selectedDevice"]]
                device_names = ", ".join([d.get('model', 'Unknown') for d in self.all_devices])
                self.set_status(
                    f"Loaded {len(self.all_devices)} device(s): {device_names}"
                )
        except Exception as e:
            self.set_status(f"Error initializing devices: {str(e)}")

    def set_status(self, message: str) -> None:
        """Set the status message."""
        if self.status_callback:
            # Don't log brightness updates to avoid recursion
            if "brightness set to" not in message:
                self.status_callback(message)
            # For brightness updates, handle without callback to avoid recursion
            else:
                # Directly set the status without logging
                pass

    def set_monitor_brightness(self, value: float) -> None:
        """Set brightness for monitor sync mode.

        Args:
            value: Brightness value between 0.0 and 1.0
        """
        self.monitor_brightness = float(value)
        BRIGHTNESS.monitor = self.monitor_brightness
        # Don't call set_status to avoid recursion
        # self.set_status(f"Monitor sync brightness set to {int(self.monitor_brightness * 100)}%")

    def set_music_brightness(self, value: float) -> None:
        """Set brightness for music sync mode.

        Args:
            value: Brightness value between 0.0 and 1.0
        """
        self.music_brightness = float(value)
        BRIGHTNESS.music = self.music_brightness
        # Don't call set_status to avoid recursion
        # self.set_status(f"Music sync brightness set to {int(self.music_brightness * 100)}%")

    def get_monitor_brightness(self) -> float:
        """Get brightness for monitor sync mode."""
        return self.monitor_brightness

    def get_music_brightness(self) -> float:
        """Get brightness for music sync mode."""
        return self.music_brightness

    def set_color_rotation(self, rotation: int) -> None:
        """Set color rotation for LED positioning.

        Args:
            rotation: Rotation angle in degrees (0, 90, 180, 270)
        """
        if rotation not in (0, 90, 180, 270):
            logger.warning(f"Invalid rotation angle {rotation}°, using 0°")
            rotation = 0

        from lumisync.config.options import GENERAL

        GENERAL.color_rotation = rotation

        # Update settings.json
        try:
            import json
            import time

            with open("settings.json", "r") as f:
                settings = json.load(f)

            settings["color_rotation"] = rotation
            settings["time"] = time.time()

            with open("settings.json", "w") as f:
                json.dump(settings, f, indent=2)

            logger.info(f"Color rotation set to {rotation}°")
        except Exception as e:
            logger.error(f"Error saving color rotation: {e}")

    def get_color_rotation(self) -> int:
        """Get current color rotation setting."""
        from lumisync.config.options import GENERAL

        return GENERAL.color_rotation

    def _ensure_server(self):
        """Ensure we have an active server connection."""
        if self.server is None:
            self.server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.server.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.server.setsockopt(
                socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
            )  # Add reuse flag
            self.server.bind(("", connection.CONNECTION.default.listen_port))
            self.server.settimeout(connection.CONNECTION.default.timeout)

    def set_device(self, device: Dict[str, Any]) -> None:
        """Set the device to use for synchronization."""
        self.selected_device = device
        if device:
            self.set_status(f"Ready to sync with {device.get('model', 'Unknown')}")

    def get_selected_device(self) -> Dict[str, Any]:
        """Get the currently selected device.

        If no device is explicitly selected, try to get one from settings.
        """
        if self.selected_device is None:
            self._init_device()
        return self.selected_device

    def start_monitor_sync(self) -> None:
        """Start monitor synchronization to all devices."""
        # Reload devices to ensure we have the latest list
        try:
            settings = devices.get_data()
            self.all_devices = settings["devices"]
        except Exception as e:
            self.set_status(f"Error loading devices: {str(e)}")
            return

        if not self.all_devices:
            self.set_status("No devices available. Please discover devices first.")
            return

        if self.sync_thread and self.sync_thread.is_alive():
            self.stop_sync()

        # Set the brightness in the config before starting sync
        BRIGHTNESS.monitor = self.monitor_brightness

        self._ensure_server()
        self.stop_event.clear()
        self.current_sync_mode = "monitor"
        self.set_status("Starting monitor sync...")

        def sync_task():
            try:
                print("[GUI Monitor Sync] Starting sync task...")
                # Enable Razer mode on all devices
                for device in self.all_devices:
                    try:
                        print(f"[GUI Monitor Sync] Enabling Razer mode on {device.get('model', 'Unknown')}")
                        connection.switch_razer(self.server, device, True)
                        print(f"[GUI Monitor Sync] Razer mode enabled on {device.get('model', 'Unknown')}")
                    except Exception as e:
                        self.set_status(f"Error enabling Razer mode on {device.get('model', 'Unknown')}: {str(e)}")
                        print(f"[GUI Monitor Sync] ERROR enabling Razer mode: {e}")

                # Initialize with placeholder (will be set on first frame)
                num_leds = GENERAL.nled
                previous_colors = None

                # Initialize screen grabber
                print(f"[GUI Monitor Sync] Initializing screen grabber for {num_leds} LEDs...")
                screen_grab = monitor.ScreenGrab()
                print("[GUI Monitor Sync] Screen grabber initialized")
                device_names = ", ".join([d.get('model', 'Unknown') for d in self.all_devices])
                self.set_status(f"Monitor sync running on {len(self.all_devices)} device(s) ({device_names}) with {num_leds} LEDs")

                frame_count = 0
                while not self.stop_event.is_set():
                    frame_count += 1
                    try:
                        # Capture screen and sample colors
                        screen = screen_grab.capture()
                        if screen is None:
                            if frame_count == 1:
                                print("[GUI Monitor Sync] ERROR: Screen capture returned None!")
                            continue

                        if frame_count == 1:
                            print(f"[GUI Monitor Sync] Screen captured successfully")

                        # Sample colors from screen regions to fill all LEDs
                        colors = monitor.sample_screen_colors(screen, num_leds)

                        # Apply brightness to colors
                        colors = monitor.apply_brightness(colors, BRIGHTNESS.monitor)

                        if frame_count == 1:
                            print(f"[GUI Monitor Sync] After brightness: {colors[:5]}...")

                        # On first frame, send colors directly without interpolation
                        if previous_colors is None:
                            print("[GUI Monitor Sync] First frame - sending colors directly (no interpolation)")
                            previous_colors = colors
                            # Send directly to all devices
                            for device in self.all_devices:
                                try:
                                    encoded_data = utils.convert_colors(colors)
                                    connection.send_razer_data(self.server, device, encoded_data)
                                    print(f"[GUI Monitor Sync] Direct send to {device.get('model', 'Unknown')}: {colors[:3]}...")
                                except Exception as e:
                                    self.set_status(f"Error syncing {device.get('model', 'Unknown')}: {str(e)}")
                                    print(f"[GUI Monitor Sync] ERROR syncing {device.get('model', 'Unknown')}: {e}")
                        else:
                            # Send to all devices with smooth transition
                            for device in self.all_devices:
                                try:
                                    # Apply smooth transition with faster settings for responsive UI
                                    monitor.smooth_transition(
                                        self.server, device, previous_colors, colors, steps=3, delay=0.002
                                    )
                                except Exception as e:
                                    self.set_status(f"Error syncing {device.get('model', 'Unknown')}: {str(e)}")
                                    print(f"[GUI Monitor Sync] ERROR syncing {device.get('model', 'Unknown')}: {e}")

                            # Update previous colors
                            previous_colors = colors
                    except Exception as e:
                        self.set_status(f"Error in monitor sync: {str(e)}")
                        print(f"[GUI Monitor Sync] Frame {frame_count} ERROR: {e}")
                        time.sleep(1)  # Avoid tight loop on error
            except Exception as e:
                self.set_status(f"Monitor sync error: {str(e)}")
                print(f"[GUI Monitor Sync] Critical error: {e}")
            finally:
                self.current_sync_mode = None
                self.set_status("Monitor sync stopped")
                print("[GUI Monitor Sync] Sync task stopped")

        self.sync_thread = threading.Thread(target=sync_task)
        self.sync_thread.daemon = True
        self.sync_thread.start()
        device_names = ", ".join([d.get('model', 'Unknown') for d in self.all_devices])
        self.set_status(
            f"Monitor sync started with {len(self.all_devices)} device(s) ({device_names}) at {int(self.monitor_brightness * 100)}% brightness"
        )

    def start_music_sync(self) -> None:
        """Start music synchronization to all devices."""
        # Reload devices to ensure we have the latest list
        try:
            settings = devices.get_data()
            self.all_devices = settings["devices"]
        except Exception as e:
            self.set_status(f"Error loading devices: {str(e)}")
            return

        if not self.all_devices:
            self.set_status("No devices available. Please discover devices first.")
            return

        if self.sync_thread and self.sync_thread.is_alive():
            self.stop_sync()

        # Set the brightness in the config before starting sync
        BRIGHTNESS.music = self.music_brightness

        self._ensure_server()
        self.stop_event.clear()
        self.current_sync_mode = "music"
        self.set_status("Starting music sync...")

        def sync_task():
            try:
                # Initialize COM for this thread
                if platform.system() == "Windows":
                    CoInitializeEx(0)

                # Enable Razer mode on all devices
                for device in self.all_devices:
                    try:
                        connection.switch_razer(self.server, device, True)
                    except Exception as e:
                        self.set_status(f"Error enabling Razer mode on {device.get('model', 'Unknown')}: {str(e)}")

                # Initialize current colors
                COLORS.current = [(0, 0, 0)] * GENERAL.nled
                device_names = ", ".join([d.get('model', 'Unknown') for d in self.all_devices])
                self.set_status(f"Music sync running on {len(self.all_devices)} device(s) ({device_names})")

                while not self.stop_event.is_set():
                    try:
                        # This code is adapted from music.py's start() function
                        with music.sc.get_microphone(
                            id=str(music.sc.default_speaker().name),
                            include_loopback=True,
                        ).recorder(samplerate=AUDIO.sample_rate) as mic:
                            # Try and except due to a soundcard error when no audio is playing
                            try:
                                data = mic.record(
                                    numframes=int(AUDIO.duration * AUDIO.sample_rate)
                                )
                            except TypeError:
                                data = None
                            amp = music.get_amplitude(data)

                            # Custom wave_color implementation since we need to pass server and device
                            match amp:
                                case amp if amp < 0.04:
                                    COLORS.current.append([int(amp * 255), 0, 0])
                                case amp if 0.04 <= amp < 0.08:
                                    COLORS.current.append([0, int(amp * 255), 0])
                                case _:
                                    COLORS.current.append([0, 0, int(amp * 255)])

                            COLORS.current.pop(0)

                            # Apply brightness to colors
                            adjusted_colors = music.apply_brightness(
                                COLORS.current, BRIGHTNESS.music
                            )

                            # Convert colors and send to all devices
                            from ...utils import convert_colors
                            encoded_colors = convert_colors(adjusted_colors)

                            for device in self.all_devices:
                                try:
                                    connection.send_razer_data(
                                        self.server, device, encoded_colors
                                    )
                                except Exception as e:
                                    self.set_status(f"Error syncing {device.get('model', 'Unknown')}: {str(e)}")

                    except Exception as e:
                        self.set_status(f"Error in music sync: {str(e)}")
                        time.sleep(1)  # Avoid tight loop on error
            except Exception as e:
                self.set_status(f"Music sync error: {str(e)}")
            finally:
                # Ensure COM is uninitialized even if an exception occurs
                try:
                    if platform.system() == "Windows":
                        CoUninitialize()
                except:
                    pass
                self.current_sync_mode = None
                self.set_status("Music sync stopped")

        self.sync_thread = threading.Thread(target=sync_task)
        self.sync_thread.daemon = True
        self.sync_thread.start()
        device_names = ", ".join([d.get('model', 'Unknown') for d in self.all_devices])
        self.set_status(
            f"Music sync started with {len(self.all_devices)} device(s) ({device_names}) at {int(self.music_brightness * 100)}% brightness"
        )

    def start_edge_sync(self) -> None:
        """Start edge lighting synchronization to all devices."""
        # Reload devices to ensure we have the latest list
        try:
            settings = devices.get_data()
            self.all_devices = settings["devices"]
        except Exception as e:
            self.set_status(f"Error loading devices: {str(e)}")
            return

        if not self.all_devices:
            self.set_status("No devices available. Please discover devices first.")
            return

        if self.sync_thread and self.sync_thread.is_alive():
            self.stop_sync()

        self._ensure_server()
        self.stop_event.clear()
        self.current_sync_mode = "edge"
        self.set_status("Starting edge lighting sync...")

        def sync_task():
            try:
                from ...sync.edge import EdgeSyncMode

                # Enable Razer mode on all devices
                for device in self.all_devices:
                    try:
                        connection.switch_razer(self.server, device, True)
                    except Exception as e:
                        self.set_status(f"Error enabling Razer mode on {device.get('model', 'Unknown')}: {str(e)}")

                device_names = ", ".join([d.get('model', 'Unknown') for d in self.all_devices])
                self.set_status(f"Edge lighting sync running on {len(self.all_devices)} device(s) ({device_names})")

                # Create edge sync mode instance with first device
                device = self.all_devices[0]
                position = device.get("position", "center")
                edge_mode = EdgeSyncMode(self.server, device, position)

                while not self.stop_event.is_set():
                    try:
                        data = edge_mode.capture_data()
                        colors = edge_mode.generate_colors(data)

                        # Send to all devices
                        for device in self.all_devices:
                            try:
                                encoded_data = utils.convert_colors(colors)
                                connection.send_razer_data(self.server, device, encoded_data)
                            except Exception as e:
                                self.set_status(f"Error syncing {device.get('model', 'Unknown')}: {str(e)}")

                    except Exception as e:
                        self.set_status(f"Error in edge sync: {str(e)}")
                        time.sleep(0.1)

            except Exception as e:
                self.set_status(f"Edge sync error: {str(e)}")
            finally:
                self.current_sync_mode = None
                self.set_status("Edge lighting sync stopped")

        self.sync_thread = threading.Thread(target=sync_task)
        self.sync_thread.daemon = True
        self.sync_thread.start()
        device_names = ", ".join([d.get('model', 'Unknown') for d in self.all_devices])
        self.set_status(f"Edge lighting sync started with {len(self.all_devices)} device(s) ({device_names})")

    def start_zone_sync(self) -> None:
        """Start zone lighting synchronization to all devices."""
        # Reload devices to ensure we have the latest list
        try:
            settings = devices.get_data()
            self.all_devices = settings["devices"]
        except Exception as e:
            self.set_status(f"Error loading devices: {str(e)}")
            return

        if not self.all_devices:
            self.set_status("No devices available. Please discover devices first.")
            return

        if self.sync_thread and self.sync_thread.is_alive():
            self.stop_sync()

        self._ensure_server()
        self.stop_event.clear()
        self.current_sync_mode = "zone"
        self.set_status("Starting zone lighting sync...")

        def sync_task():
            try:
                from ...sync.zone import ZoneSyncMode

                # Enable Razer mode on all devices
                for device in self.all_devices:
                    try:
                        connection.switch_razer(self.server, device, True)
                    except Exception as e:
                        self.set_status(f"Error enabling Razer mode on {device.get('model', 'Unknown')}: {str(e)}")

                device_names = ", ".join([d.get('model', 'Unknown') for d in self.all_devices])
                self.set_status(f"Zone lighting sync running on {len(self.all_devices)} device(s) ({device_names})")

                # Create zone sync mode instance with first device
                device = self.all_devices[0]
                position = device.get("position", "center")
                zone_mode = ZoneSyncMode(self.server, device, position)

                while not self.stop_event.is_set():
                    try:
                        data = zone_mode.capture_data()
                        colors = zone_mode.generate_colors(data)

                        # Send to all devices
                        for device in self.all_devices:
                            try:
                                encoded_data = utils.convert_colors(colors)
                                connection.send_razer_data(self.server, device, encoded_data)
                            except Exception as e:
                                self.set_status(f"Error syncing {device.get('model', 'Unknown')}: {str(e)}")

                    except Exception as e:
                        self.set_status(f"Error in zone sync: {str(e)}")
                        time.sleep(0.1)

            except Exception as e:
                self.set_status(f"Zone sync error: {str(e)}")
            finally:
                self.current_sync_mode = None
                self.set_status("Zone lighting sync stopped")

        self.sync_thread = threading.Thread(target=sync_task)
        self.sync_thread.daemon = True
        self.sync_thread.start()
        device_names = ", ".join([d.get('model', 'Unknown') for d in self.all_devices])
        self.set_status(f"Zone lighting sync started with {len(self.all_devices)} device(s) ({device_names})")

    def start_action_sync(self) -> None:
        """Start action/effect detection synchronization to all devices."""
        # Reload devices to ensure we have the latest list
        try:
            settings = devices.get_data()
            self.all_devices = settings["devices"]
        except Exception as e:
            self.set_status(f"Error loading devices: {str(e)}")
            return

        if not self.all_devices:
            self.set_status("No devices available. Please discover devices first.")
            return

        if self.sync_thread and self.sync_thread.is_alive():
            self.stop_sync()

        self._ensure_server()
        self.stop_event.clear()
        self.current_sync_mode = "action"
        self.set_status("Starting action detection sync...")

        def sync_task():
            try:
                from ...sync.action import ActionSyncMode

                # Enable Razer mode on all devices
                for device in self.all_devices:
                    try:
                        connection.switch_razer(self.server, device, True)
                    except Exception as e:
                        self.set_status(f"Error enabling Razer mode on {device.get('model', 'Unknown')}: {str(e)}")

                device_names = ", ".join([d.get('model', 'Unknown') for d in self.all_devices])
                self.set_status(f"Action detection sync running on {len(self.all_devices)} device(s) ({device_names})")

                # Create action sync mode instance with first device
                device = self.all_devices[0]
                position = device.get("position", "center")
                action_mode = ActionSyncMode(self.server, device, position)

                while not self.stop_event.is_set():
                    try:
                        data = action_mode.capture_data()
                        colors = action_mode.generate_colors(data)

                        # Send to all devices
                        for device in self.all_devices:
                            try:
                                encoded_data = utils.convert_colors(colors)
                                connection.send_razer_data(self.server, device, encoded_data)
                            except Exception as e:
                                self.set_status(f"Error syncing {device.get('model', 'Unknown')}: {str(e)}")

                    except Exception as e:
                        self.set_status(f"Error in action sync: {str(e)}")
                        time.sleep(0.1)

            except Exception as e:
                self.set_status(f"Action sync error: {str(e)}")
            finally:
                self.current_sync_mode = None
                self.set_status("Action detection sync stopped")

        self.sync_thread = threading.Thread(target=sync_task)
        self.sync_thread.daemon = True
        self.sync_thread.start()
        device_names = ", ".join([d.get('model', 'Unknown') for d in self.all_devices])
        self.set_status(f"Action detection sync started with {len(self.all_devices)} device(s) ({device_names})")

    def stop_sync(self) -> None:
        """Stop any active synchronization."""
        if self.sync_thread and self.sync_thread.is_alive():
            self.stop_event.set()
            self.set_status(f"Stopping {self.current_sync_mode} sync...")
            self.sync_thread.join(timeout=2)  # Wait for thread to finish

            # If thread is still alive after timeout, we can't do much more in Python
            if self.sync_thread.is_alive():
                self.set_status(
                    f"Warning: {self.current_sync_mode} sync thread did not stop cleanly"
                )

            self.current_sync_mode = None
            self.set_status("Sync stopped")

    def get_current_sync_mode(self) -> Optional[str]:
        """Get the current synchronization mode."""
        return self.current_sync_mode

    def is_syncing(self) -> bool:
        """Check if synchronization is active."""
        return self.sync_thread is not None and self.sync_thread.is_alive()

    def __del__(self):
        """Clean up resources when the controller is deleted."""
        self.stop_sync()
        if self.server:
            try:
                self.server.close()
            except:
                pass
