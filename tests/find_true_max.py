"""
Find the true maximum LED count by testing if the ENTIRE rope lights up.
"""

import time
from lumisync import connection, utils


def test_full_rope_coverage(server, device, led_count):
    """
    Test if a specific LED count lights up the ENTIRE rope.

    Returns:
        True if the entire rope lights up, False otherwise
    """
    try:
        # Create full white for easy visibility of rope coverage
        colors = [(255, 255, 255)] * led_count

        encoded = utils.convert_colors(colors)
        connection.send_razer_data(server, device, encoded)
        time.sleep(0.3)

        response = input(f"{led_count:3d} LEDs - Does ENTIRE rope light up white? (y/n): ").strip().lower()
        return response in ['y', 'yes']

    except Exception as e:
        print(f"Error: {e}")
        return False


def main():
    """Main test function."""
    try:
        print("Searching for devices...")
        server, devices = connection.connect()

        if not devices:
            print("No devices found!")
            return

        device = None
        for d in devices:
            if d.get('model') == 'H61D5':
                device = d
                break

        if not device:
            print("H61D5 not found!")
            return

        print(f"\nTesting {device.get('model')} at {device.get('ip')}")
        print("=" * 70)
        print("Finding exact LED count for FULL rope coverage")
        print("(Testing with WHITE color for easy visibility)")
        print("-" * 70)

        # Enable Razer mode
        connection.switch_razer(server, device, True)
        time.sleep(0.5)

        results = {}

        # Start lower and work up
        test_values = [20, 24, 30, 40, 50, 60, 80, 100, 120, 140, 160, 200, 255]

        for count in test_values:
            works = test_full_rope_coverage(server, device, count)
            results[count] = works
            if works:
                print(f"✓ {count} LEDs works")
            else:
                print(f"✗ {count} LEDs failed")

        # Summary
        print("\n" + "=" * 70)
        working = [c for c, w in results.items() if w]
        print(f"LED counts that light ENTIRE rope: {working}")

        if working:
            max_working = max(working)
            print(f"\n✓ RECOMMENDED: nled = {max_working}")
        else:
            print("\n✗ None of the tested counts lit the entire rope!")

        # Disable Razer mode
        connection.switch_razer(server, device, False)

    finally:
        try:
            server.close()
        except:
            pass


if __name__ == "__main__":
    main()
