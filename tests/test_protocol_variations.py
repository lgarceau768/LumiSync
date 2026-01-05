"""
Test different protocol variations to see if there's a way to fix the 5+ LED issue.
Maybe the device expects something different for higher LED counts.
"""

import time
import base64
from lumisync import connection, utils


def test_direct_protocol(server, device):
    """Test sending raw protocol with different variations."""
    print(f"\nTesting {device.get('model')} at {device.get('ip')}")
    print("=" * 70)

    # Enable Razer mode
    connection.switch_razer(server, device, True)
    time.sleep(0.5)

    # Test 1: Standard protocol with 4 LEDs (known working)
    print("\nTest 1: Standard 4 LEDs (control - should work)")
    colors_4 = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
    encoded = utils.convert_colors(colors_4)
    connection.send_razer_data(server, device, encoded)
    time.sleep(0.3)
    response = input("See 4 different colors across full rope? (y/n): ").strip().lower()
    print(f"Result: {'✓ Works' if response == 'y' else '✗ Failed'}")

    # Test 2: Send 5 LEDs but with a reset first
    print("\nTest 2: Reset then send 5 LEDs")
    connection.switch_razer(server, device, False)
    time.sleep(0.5)
    connection.switch_razer(server, device, True)
    time.sleep(0.5)

    colors_5 = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255)]
    encoded = utils.convert_colors(colors_5)
    connection.send_razer_data(server, device, encoded)
    time.sleep(0.3)
    response = input("See 5 colors across full rope? (y/n): ").strip().lower()
    print(f"Result: {'✓ Works' if response == 'y' else '✗ Failed'}")

    # Test 3: Send 5 LEDs but pad to 6 (round to multiple of 4?)
    print("\nTest 3: Send 6 LEDs (maybe device wants multiples of 4?)")
    colors_6 = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255), (255, 255, 0)]
    encoded = utils.convert_colors(colors_6)
    connection.send_razer_data(server, device, encoded)
    time.sleep(0.3)
    response = input("See 6 colors across full rope? (y/n): ").strip().lower()
    print(f"Result: {'✓ Works' if response == 'y' else '✗ Failed'}")

    # Test 4: Send 8 LEDs (next multiple of 4)
    print("\nTest 4: Send 8 LEDs (2x the working count)")
    colors_8 = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0),
                (255, 0, 255), (0, 255, 255), (255, 255, 255), (128, 128, 128)]
    encoded = utils.convert_colors(colors_8)
    connection.send_razer_data(server, device, encoded)
    time.sleep(0.3)
    response = input("See 8 colors across full rope? (y/n): ").strip().lower()
    print(f"Result: {'✓ Works' if response == 'y' else '✗ Failed'}")

    # Test 5: Try sending duplicate colors (maybe it expects different colors per segment?)
    print("\nTest 5: Send 8 LEDs but with only 4 unique colors (repeat pattern)")
    colors_repeat = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)] * 2
    encoded = utils.convert_colors(colors_repeat)
    connection.send_razer_data(server, device, encoded)
    time.sleep(0.3)
    response = input("Does rope show repeated R/G/B/Y pattern? (y/n): ").strip().lower()
    print(f"Result: {'✓ Repeats' if response == 'y' else '✗ No repeat'}")

    # Test 6: Simple test - send different numbers to see if there's a sweet spot
    print("\nTest 6: Binary search for optimal LED count (7-8)")
    for test_count in [7, 8, 12, 16]:
        colors = [(255, 255, 255)] * test_count
        encoded = utils.convert_colors(colors)
        connection.send_razer_data(server, device, encoded)
        time.sleep(0.3)
        response = input(f"  {test_count} LEDs - Full rope white? (y/n): ").strip().lower()
        if response == 'y':
            print(f"    ✓ {test_count} LEDs works!")
            break
        else:
            print(f"    ✗ {test_count} LEDs failed")

    # Disable Razer mode
    connection.switch_razer(server, device, False)
    print("\nTest complete!")


def main():
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
            print("H61D5 not found!")
            return

        test_direct_protocol(server, device)

    finally:
        try:
            server.close()
        except:
            pass


if __name__ == "__main__":
    main()
