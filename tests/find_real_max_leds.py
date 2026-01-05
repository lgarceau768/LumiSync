"""
Interactive script to find the actual maximum LED count by testing visually.
This asks the user if they see the color pattern, helping identify the real limit.
"""

import time
from lumisync import connection, utils


def test_led_count_interactive(server, device, led_count):
    """
    Test if a device supports the given number of LEDs by sending a color pattern
    and asking the user if they see it.

    Args:
        server: Socket server
        device: Device to test
        led_count: Number of LEDs to test

    Returns:
        True if the user confirms seeing the pattern, False otherwise
    """
    try:
        # Create a distinct pattern: red, green, blue repeating
        colors = []
        for i in range(led_count):
            if i % 3 == 0:
                colors.append((255, 0, 0))  # Red
            elif i % 3 == 1:
                colors.append((0, 255, 0))  # Green
            else:
                colors.append((0, 0, 255))  # Blue

        # Convert to protocol format
        encoded = utils.convert_colors(colors)

        print(f"\nSending {led_count} colors (Red/Green/Blue pattern)...")
        print(f"Encoded data length: {len(encoded)} characters")

        # Send to device
        connection.send_razer_data(server, device, encoded)

        # Give the device time to update
        time.sleep(0.5)

        # Ask user if they see the pattern
        while True:
            response = input(f"Do you see the RGB color pattern on {device.get('model', 'Unknown')}? (yes/no): ").strip().lower()
            if response in ['yes', 'y']:
                return True
            elif response in ['no', 'n']:
                return False
            else:
                print("Please answer 'yes' or 'no'")

    except Exception as e:
        print(f"Error with {led_count} LEDs: {str(e)}")
        return False


def find_real_max_leds(server, device):
    """
    Find the actual maximum number of LEDs the device can display.
    Starts at a known working value and increments until it fails.
    """
    print(f"\n{'='*70}")
    print(f"Finding actual maximum LED count for {device.get('model', 'Unknown')} ({device.get('ip')})")
    print(f"{'='*70}")

    # Start from a known working value
    current = 20
    max_working = 20

    # Test incrementally
    test_values = [20, 40, 60, 80, 100, 120, 140, 160, 180, 200, 220, 240, 255]

    for count in test_values:
        print(f"\n--- Testing {count} LEDs ---")
        if test_led_count_interactive(server, device, count):
            print(f"✓ {count} LEDs works!")
            max_working = count
        else:
            print(f"✗ {count} LEDs does NOT work")
            break

    # If all tested values worked, do fine-grained search
    if max_working == test_values[-1]:
        print("\nAll test values worked! Your device supports at least 255 LEDs.")
    else:
        # Try values between last working and first failing
        print(f"\nFine-tuning between {max_working} and {count}...")
        for test_count in range(max_working + 10, count, 10):
            print(f"\n--- Testing {test_count} LEDs ---")
            if test_led_count_interactive(server, device, test_count):
                print(f"✓ {test_count} LEDs works!")
                max_working = test_count
            else:
                print(f"✗ {test_count} LEDs does NOT work")
                break

    return max_working


def main():
    """Main test function."""
    try:
        # Connect to devices
        print("Searching for devices...")
        server, devices = connection.connect()

        if not devices:
            print("No devices found!")
            return

        print(f"Found {len(devices)} device(s)")

        # Enable Razer mode on all devices
        print("\nEnabling Razer mode on all devices...")
        for device in devices:
            print(f"  - {device.get('model', 'Unknown')} ({device.get('ip')})")
            connection.switch_razer(server, device, True)

        print("\nWaiting 1 second for devices to initialize...")
        time.sleep(1)

        # Find max LED count for each device
        results = {}
        for device in devices:
            max_count = find_real_max_leds(server, device)
            results[device.get('model', 'Unknown')] = max_count

        # Summary
        print("\n" + "="*70)
        print("SUMMARY")
        print("="*70)
        for model, count in results.items():
            print(f"{model}: {count} LEDs")

        # Find minimum (for syncing all devices with same count)
        min_count = min(results.values())
        print(f"\nRecommended config value for nled: {min_count}")
        print("(Use this value to sync all devices with the same number of LEDs)")

        # Disable Razer mode
        print("\nDisabling Razer mode...")
        for device in devices:
            connection.switch_razer(server, device, False)

        print("\nDiscovery complete!")

    finally:
        try:
            server.close()
        except:
            pass


if __name__ == "__main__":
    main()
