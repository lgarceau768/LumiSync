"""
Test script to discover the maximum number of LEDs supported by Govee devices.
Tries sending color data with increasing LED counts to find the limit.
"""

import time
from lumisync import connection, utils


def test_led_count(server, device, led_count):
    """
    Test if a device supports the given number of LEDs.

    Args:
        server: Socket server
        device: Device to test
        led_count: Number of LEDs to test

    Returns:
        True if the device accepts the color data, False otherwise
    """
    try:
        # Create test colors (simple alternating pattern)
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

        # Send to device
        connection.send_razer_data(server, device, encoded)

        return True
    except Exception as e:
        print(f"  Error with {led_count} LEDs: {str(e)}")
        return False


def discover_max_leds(server, device):
    """
    Discover the maximum number of LEDs supported by a device.

    Uses an exponential search followed by binary search for efficiency.
    """
    print(f"\nDiscovering maximum LED count for {device.get('model', 'Unknown')} ({device.get('ip')})")
    print("=" * 70)

    # First, find an upper bound using exponential search
    print("\nPhase 1: Finding upper bound (exponential search)...")
    upper_bound = 20
    last_working = 20

    test_counts = [20, 40, 80, 160]
    for count in test_counts:
        print(f"Testing {count} LEDs...", end=" ")
        if test_led_count(server, device, count):
            print("✓ Works")
            last_working = count
            upper_bound = count * 2
        else:
            print("✗ Failed")
            upper_bound = count
            break

    # If all exponential tests passed, try higher counts
    if last_working == test_counts[-1]:
        print(f"Testing 320 LEDs...", end=" ")
        if test_led_count(server, device, 320):
            print("✓ Works")
            upper_bound = 640
            last_working = 320
        else:
            print("✗ Failed")
            upper_bound = 320

    # Binary search between last_working and upper_bound
    print(f"\nPhase 2: Binary search between {last_working} and {upper_bound}...")
    low = last_working
    high = upper_bound
    max_working = last_working

    while low <= high:
        mid = (low + high) // 2

        # Skip if we've already tested this value
        if mid == last_working:
            low = mid + 1
            continue

        print(f"Testing {mid} LEDs...", end=" ")
        if test_led_count(server, device, mid):
            print("✓ Works")
            max_working = mid
            low = mid + 1
        else:
            print("✗ Failed")
            high = mid - 1

    print("\n" + "=" * 70)
    print(f"✓ Maximum LED count: {max_working}")
    print(f"  Protocol supports up to 255 LEDs (single byte limit)")
    print(f"  Device appears to support: {max_working} LEDs")

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

        print(f"Found {len(devices)} device(s)\n")

        # Enable Razer mode on all devices
        print("Enabling Razer mode on all devices...")
        for device in devices:
            print(f"  - {device.get('model', 'Unknown')} ({device.get('ip')})")
            connection.switch_razer(server, device, True)

        print("\nWaiting 2 seconds for devices to initialize...")
        time.sleep(2)

        # Discover max LED count for each device
        results = {}
        for device in devices:
            max_count = discover_max_leds(server, device)
            results[device.get('model', 'Unknown')] = max_count

        # Summary
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        for model, count in results.items():
            print(f"{model}: {count} LEDs")

        # Find minimum (for syncing all devices with same count)
        min_count = min(results.values())
        print(f"\nRecommended config value: {min_count} LEDs")
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
