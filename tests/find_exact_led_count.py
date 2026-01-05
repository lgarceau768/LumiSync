"""
Fine-grained LED count finder for narrowing down exact LED count.
Tests between known working and failing counts.
"""

import time
from lumisync import connection, utils


def main():
    """Test LED counts between 40 and 60 to find exact maximum."""
    try:
        print("Searching for devices...")
        server, devices = connection.connect()

        if not devices:
            print("No devices found!")
            return

        # Use H61D5 (the rope light)
        device = None
        for d in devices:
            if d.get('model') == 'H61D5':
                device = d
                break

        if not device:
            print("H61D5 not found! Using first device...")
            device = devices[0]

        print(f"Testing {device.get('model', 'Unknown')} at {device.get('ip')}")
        print("=" * 70)

        # Enable Razer mode
        connection.switch_razer(server, device, True)
        time.sleep(0.5)

        # We know 40 works and 60 fails, so test everything between
        # Start at 41 and go up to 59
        results = {}

        for count in range(41, 60):
            colors = []
            for i in range(count):
                if i % 3 == 0:
                    colors.append((255, 0, 0))
                elif i % 3 == 1:
                    colors.append((0, 255, 0))
                else:
                    colors.append((0, 0, 255))

            encoded = utils.convert_colors(colors)

            print(f"Testing {count} LEDs ({len(encoded)} encoded chars)...", end=" ", flush=True)
            try:
                connection.send_razer_data(server, device, encoded)
                time.sleep(0.2)

                response = input("Works? (y/n): ").strip().lower()
                if response == 'y':
                    print("✓")
                    results[count] = True
                else:
                    print("✗")
                    results[count] = False
                    # Once we find one that fails, stop testing higher
                    if not results[count]:
                        break
            except Exception as e:
                print(f"ERROR: {e}")
                results[count] = False

        # Summary
        print("\n" + "=" * 70)
        working = [c for c, w in results.items() if w]
        if working:
            max_count = max(working)
            print(f"Results: {working}")
            print(f"Maximum working LED count: {max_count}")
            print(f"\nUpdate your config with: \"nled\": {max_count}")
        else:
            print("No working counts found in range 41-59")

        # Disable Razer mode
        connection.switch_razer(server, device, False)

    finally:
        try:
            server.close()
        except:
            pass


if __name__ == "__main__":
    main()
