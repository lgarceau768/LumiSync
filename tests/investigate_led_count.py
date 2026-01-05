"""
Detailed investigation to find actual physical LED count and device maximum.
Tests small increments with visual confirmation to understand rope behavior.
"""

import time
from lumisync import connection, utils


def test_led_count_detailed(server, device, led_count):
    """
    Test a specific LED count with visual feedback.

    Args:
        server: Socket server
        device: Device to test
        led_count: Number of LEDs to test

    Returns:
        True if pattern is visible, False otherwise
    """
    try:
        # Create distinct RGB pattern for easy visibility
        colors = []
        for i in range(led_count):
            if i % 3 == 0:
                colors.append((255, 0, 0))    # Red
            elif i % 3 == 1:
                colors.append((0, 255, 0))    # Green
            else:
                colors.append((0, 0, 255))    # Blue

        encoded = utils.convert_colors(colors)
        connection.send_razer_data(server, device, encoded)
        time.sleep(0.3)

        response = input(f"{led_count:3d} LEDs ({len(encoded):4d} chars) - See pattern? (y/n): ").strip().lower()
        return response in ['y', 'yes']

    except Exception as e:
        print(f"Error testing {led_count} LEDs: {e}")
        return False


def main():
    """Main investigation function."""
    try:
        print("Searching for devices...")
        server, devices = connection.connect()

        if not devices:
            print("No devices found!")
            return

        # Find H61D5
        device = None
        for d in devices:
            if d.get('model') == 'H61D5':
                device = d
                break

        if not device:
            print("H61D5 not found! Using first device...")
            device = devices[0]

        print(f"\nTesting {device.get('model', 'Unknown')} at {device.get('ip')}")
        print("=" * 70)
        print("\nPhase 1: Finding physical LED rope length")
        print("(Testing small increments from 10 to 30)")
        print("-" * 70)

        # Enable Razer mode
        connection.switch_razer(server, device, True)
        time.sleep(0.5)

        results_phase1 = {}

        # Test 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30
        for count in range(10, 31, 2):
            results_phase1[count] = test_led_count_detailed(server, device, count)

        working_phase1 = [c for c, w in results_phase1.items() if w]
        print(f"\nPhase 1 Results: {working_phase1}")
        if working_phase1:
            max_phase1 = max(working_phase1)
            min_phase1 = min(working_phase1)
            print(f"Pattern visible from {min_phase1} to {max_phase1} LEDs")

        # Phase 2: Test between 40-60 to find device maximum
        print("\n" + "=" * 70)
        print("Phase 2: Finding device maximum (between 40-60)")
        print("-" * 70)

        results_phase2 = {}

        # Binary search approach: test 40, 50, 45, 47, etc. to narrow down
        test_points = [40, 45, 50, 55, 58, 59, 60]

        for count in test_points:
            if count not in results_phase2:  # Skip if already tested
                if test_led_count_detailed(server, device, count):
                    results_phase2[count] = True
                else:
                    results_phase2[count] = False
                    # If a count fails, we can skip higher counts
                    break

        working_phase2 = [c for c, w in results_phase2.items() if w]
        failing_phase2 = [c for c, w in results_phase2.items() if not w]

        print(f"\nPhase 2 Results:")
        print(f"  Working: {working_phase2}")
        print(f"  Failing: {failing_phase2}")

        # Summary
        print("\n" + "=" * 70)
        print("INVESTIGATION SUMMARY")
        print("=" * 70)

        if working_phase1:
            print(f"\n✓ Physical rope appears to support up to {max(working_phase1)} LEDs")

        if working_phase2:
            max_working = max(working_phase2)
            print(f"✓ Device accepts up to {max_working} LEDs")
            print(f"\nRECOMMENDATION:")
            print(f"  Set nled to: {max_working}")

        # Disable Razer mode
        connection.switch_razer(server, device, False)
        print("\nInvestigation complete!")

    finally:
        try:
            server.close()
        except:
            pass


if __name__ == "__main__":
    main()
