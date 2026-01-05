"""
Test script to verify that syncing with 255 LEDs works correctly.
"""

import time
from lumisync import connection, utils


def test_max_leds():
    """Test syncing with maximum LED count."""
    try:
        # Connect to devices
        print("Searching for devices...")
        server, devices = connection.connect()

        if not devices:
            print("No devices found!")
            return

        print(f"Found {len(devices)} device(s)\n")

        device = devices[0]
        print(f"Testing with: {device.get('model', 'Unknown')} ({device.get('ip')})")

        # Enable Razer mode
        print("Enabling Razer mode...")
        connection.switch_razer(server, device, True)
        time.sleep(1)

        # Test with 255 LEDs
        print("Generating 255 LED colors...")
        colors = []
        for i in range(255):
            # Create a rainbow pattern
            hue = (i / 255.0) * 360
            # Simple HSV to RGB conversion
            if hue < 60:
                r, g, b = 255, int((hue / 60) * 255), 0
            elif hue < 120:
                r, g, b = int(255 * (2 - hue / 60)), 255, 0
            elif hue < 180:
                r, g, b = 0, 255, int((hue - 120) / 60 * 255)
            elif hue < 240:
                r, g, b = 0, int(255 * (4 - hue / 60)), 255
            elif hue < 300:
                r, g, b = int((hue - 240) / 60 * 255), 0, 255
            else:
                r, g, b = 255, 0, int(255 * (6 - hue / 60))

            colors.append((int(r), int(g), int(b)))

        print(f"Sending {len(colors)} colors...")
        encoded = utils.convert_colors(colors)
        print(f"Encoded data length: {len(encoded)} characters")
        connection.send_razer_data(server, device, encoded)

        print("✓ Successfully sent 255 LED colors!")
        print("  All LEDs should now light up with a rainbow pattern")

        time.sleep(5)

        # Disable Razer mode
        print("Disabling Razer mode...")
        connection.switch_razer(server, device, False)

        print("\nTest complete!")

    finally:
        try:
            server.close()
        except:
            pass


if __name__ == "__main__":
    test_max_leds()
