"""
Find the true maximum LED count by testing downward.
Since higher LED counts light LESS of the rope, we need to find the optimal count.
"""

import time
from lumisync import connection, utils


def test_rope_coverage(server, device, led_count):
    """
    Test if a specific LED count lights up the rope.

    Returns:
        True if more rope lights up, False if less/same
    """
    try:
        # Create full white for easy visibility of rope coverage
        colors = [(255, 255, 255)] * led_count

        encoded = utils.convert_colors(colors)
        connection.send_razer_data(server, device, encoded)
        time.sleep(0.3)

        response = input(f"{led_count:3d} LEDs - Does this light up MORE of the rope than before? (y/n): ").strip().lower()
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
        print("Finding optimal LED count")
        print("(Testing DOWNWARD since higher counts light less)")
        print("-" * 70)

        # Enable Razer mode
        connection.switch_razer(server, device, True)
        time.sleep(0.5)

        results = {}

        # Test downward from 10 to 1
        test_values = [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]

        for count in test_values:
            works = test_rope_coverage(server, device, count)
            results[count] = works
            if works:
                print(f"✓ {count} LEDs lights MORE")
            else:
                print(f"✗ {count} LEDs lights LESS or SAME")

        # Summary
        print("\n" + "=" * 70)
        print("Results:")
        for count in sorted(results.keys(), reverse=True):
            status = "✓ Lights MORE" if results[count] else "✗ Lights LESS"
            print(f"  {count:2d} LEDs: {status}")

        # Disable Razer mode
        connection.switch_razer(server, device, False)

    finally:
        try:
            server.close()
        except:
            pass


if __name__ == "__main__":
    main()
