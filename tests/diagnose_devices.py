"""
Diagnostic script to test both devices and find the correct LED count.
"""

import time
from lumisync import connection, utils


def test_device_connection(server, device):
    """Test basic connection to a device."""
    print(f"\n{'='*70}")
    print(f"Testing device: {device.get('model', 'Unknown')} ({device.get('ip')}:{device.get('port', 4001)})")
    print(f"{'='*70}")

    try:
        # Enable Razer mode
        print("Enabling Razer mode...", end=" ")
        connection.switch_razer(server, device, True)
        print("✓")
        time.sleep(0.5)

        # Send a simple test pattern (10 LEDs in RGB pattern)
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)] * 3 + [(255, 255, 255)]
        encoded = utils.convert_colors(colors)

        print(f"Sending 10 LEDs (Red/Green/Blue pattern)...", end=" ")
        connection.send_razer_data(server, device, encoded)
        print("✓")
        print(f"  Encoded length: {len(encoded)} chars")

        time.sleep(0.5)

        # Ask user if they see it
        response = input(f"Do you see RGB colors on {device.get('model', 'Unknown')}? (yes/no): ").strip().lower()
        if response in ['yes', 'y']:
            print("✓ Device is responsive!")
            return True
        else:
            print("✗ Device did not respond visually")
            return False

    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    finally:
        # Disable Razer mode
        try:
            connection.switch_razer(server, device, False)
        except:
            pass


def find_led_count_for_device(server, device):
    """Find the actual LED count by binary search."""
    print(f"\n{'='*70}")
    print(f"Finding LED count for {device.get('model', 'Unknown')}")
    print(f"{'='*70}")

    # Enable Razer mode
    connection.switch_razer(server, device, True)
    time.sleep(0.5)

    # Test exponential values
    test_values = [20, 40, 60, 80, 100, 120, 140, 160, 180, 200, 220, 240, 255]
    results = {}

    for count in test_values:
        colors = []
        for i in range(count):
            if i % 3 == 0:
                colors.append((255, 0, 0))  # Red
            elif i % 3 == 1:
                colors.append((0, 255, 0))  # Green
            else:
                colors.append((0, 0, 255))  # Blue

        encoded = utils.convert_colors(colors)

        print(f"\nTesting {count} LEDs ({len(encoded)} encoded chars)...", end=" ")
        try:
            connection.send_razer_data(server, device, encoded)
            time.sleep(0.3)

            response = input("Do you see the RGB pattern? (yes/no): ").strip().lower()
            if response in ['yes', 'y']:
                print("✓ Works")
                results[count] = True
            else:
                print("✗ Failed")
                results[count] = False
        except Exception as e:
            print(f"✗ Error: {e}")
            results[count] = False

    # Analyze results
    working_counts = [c for c, w in results.items() if w]
    if working_counts:
        max_working = max(working_counts)
        print(f"\n{'='*70}")
        print(f"Results for {device.get('model', 'Unknown')}:")
        print(f"  Working LED counts: {working_counts}")
        print(f"  Maximum working: {max_working} LEDs")
        print(f"  Recommended config: {max_working}")
        return max_working
    else:
        print(f"\n✗ No LED counts worked! Check device connection.")
        return None


def main():
    """Main diagnostic function."""
    try:
        # Connect to devices
        print("Searching for devices...")
        server, devices = connection.connect()

        if not devices:
            print("No devices found!")
            return

        print(f"Found {len(devices)} device(s)")
        for device in devices:
            print(f"  - {device.get('model', 'Unknown')} at {device.get('ip')}:{device.get('port', 4001)}")

        # Test each device
        responsive_devices = []
        for device in devices:
            if test_device_connection(server, device):
                responsive_devices.append(device)

        if not responsive_devices:
            print("\n✗ No devices responded! Check your network connection and device IPs.")
            return

        # Find LED count for each responsive device
        print(f"\n{'='*70}")
        print("PHASE 2: FINDING LED COUNTS")
        print(f"{'='*70}")

        results = {}
        for device in responsive_devices:
            max_count = find_led_count_for_device(server, device)
            if max_count:
                results[device.get('model', 'Unknown')] = max_count

        # Summary
        print(f"\n{'='*70}")
        print("DIAGNOSTIC SUMMARY")
        print(f"{'='*70}")
        print(f"Responsive devices: {len(responsive_devices)}")
        for model, count in results.items():
            print(f"  {model}: {count} LEDs recommended")

        if results:
            min_count = min(results.values())
            print(f"\nUpdate settings.json with: \"nled\": {min_count}")
            print("(This value works for all your devices)")

        # Disable Razer mode on all devices
        print("\nDisabling Razer mode...")
        for device in devices:
            try:
                connection.switch_razer(server, device, False)
            except:
                pass

        print("\nDiagnostic complete!")

    finally:
        try:
            server.close()
        except:
            pass


if __name__ == "__main__":
    main()
