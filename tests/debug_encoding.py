"""
Debug script to analyze the color encoding for different LED counts.
Tests if there's an issue with the protocol encoding that breaks at higher counts.
"""

import base64
from lumisync import utils


def analyze_encoding(led_count):
    """Analyze the encoding for a specific LED count."""
    print(f"\n{'='*70}")
    print(f"Analyzing encoding for {led_count} LEDs")
    print(f"{'='*70}")

    # Create simple white colors for easy analysis
    colors = [(255, 255, 255)] * led_count

    # Encode
    encoded = utils.convert_colors(colors)

    # Decode to analyze
    decoded = base64.b64decode(encoded)
    decoded_bytes = list(decoded)

    print(f"\nEncoded (Base64): {encoded}")
    print(f"Encoded length: {len(encoded)} characters")
    print(f"Decoded length: {len(decoded_bytes)} bytes")

    # Print hex representation
    print(f"\nHex representation:")
    hex_str = ' '.join(f'{b:02X}' for b in decoded_bytes)
    print(hex_str)

    # Parse the packet
    print(f"\nPacket structure:")
    print(f"  Header bytes [0-5]: {decoded_bytes[0:6]} = {' '.join(f'{b:02X}' for b in decoded_bytes[0:6])}")
    print(f"  LED count byte [5]: {decoded_bytes[5]} (decimal) = {decoded_bytes[5]:02X} (hex)")
    print(f"  Color bytes [6:-1]: {len(decoded_bytes) - 7} bytes")
    print(f"  Checksum byte [-1]: {decoded_bytes[-1]} = {decoded_bytes[-1]:02X} (hex)")

    # Verify structure
    num_leds_in_packet = decoded_bytes[5]
    color_bytes = len(decoded_bytes) - 7  # Subtract header (6) + checksum (1)
    expected_color_bytes = num_leds_in_packet * 3

    print(f"\nVerification:")
    print(f"  LED count in packet: {num_leds_in_packet}")
    print(f"  Color bytes present: {color_bytes}")
    print(f"  Expected color bytes: {expected_color_bytes}")
    print(f"  Match: {color_bytes == expected_color_bytes} ✓" if color_bytes == expected_color_bytes else f"  Match: False ✗")

    # Verify checksum
    checksum_calculated = 0
    for byte in decoded_bytes[:-1]:
        checksum_calculated ^= byte

    checksum_in_packet = decoded_bytes[-1]
    print(f"\nChecksum verification:")
    print(f"  Calculated: {checksum_calculated} ({checksum_calculated:02X} hex)")
    print(f"  In packet:  {checksum_in_packet} ({checksum_in_packet:02X} hex)")
    print(f"  Match: {checksum_calculated == checksum_in_packet} ✓" if checksum_calculated == checksum_in_packet else f"  Match: False ✗")

    return {
        'led_count': led_count,
        'encoded': encoded,
        'packet_bytes': decoded_bytes,
        'num_leds_in_packet': num_leds_in_packet,
        'color_bytes': color_bytes,
        'checksum_match': checksum_calculated == checksum_in_packet,
    }


def main():
    """Test encoding for different LED counts."""
    print("Analyzing color encoding for different LED counts\n")

    results = []

    # Test the LED counts we know about
    test_counts = [1, 2, 3, 4, 5, 6, 8, 10, 15, 20, 24, 30, 40]

    for count in test_counts:
        result = analyze_encoding(count)
        results.append(result)

    # Summary
    print(f"\n\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"\n{'LED':>4} | {'Encoded':>8} | {'Packet Bytes':>12} | {'Color Bytes':>12} | {'Checksum OK':>11}")
    print("-" * 70)

    for r in results:
        checksum_status = "✓" if r['checksum_match'] else "✗"
        print(
            f"{r['led_count']:>4} | {len(r['encoded']):>8} | {len(r['packet_bytes']):>12} | "
            f"{r['color_bytes']:>12} | {checksum_status:>11}"
        )

    # Look for patterns
    print("\n" + "="*70)
    print("ANALYSIS")
    print("="*70)

    # Check if all checksums are correct
    all_checksums_ok = all(r['checksum_match'] for r in results)
    print(f"\nAll checksums valid: {all_checksums_ok} ✓" if all_checksums_ok else f"\nAll checksums valid: False ✗")

    # Check packet size pattern
    print("\nPacket sizes:")
    for r in results:
        print(f"  {r['led_count']:3d} LEDs: {len(r['packet_bytes']):3d} bytes ({len(r['encoded']):3d} base64 chars)")

    # Check if there's a maximum packet size issue
    max_bytes = max(r[1] for r in [(r['led_count'], len(r['packet_bytes'])) for r in results])
    print(f"\nMaximum packet size: {max_bytes} bytes")
    print("(If device has a max packet size limit, packets larger than that would fail)")


if __name__ == "__main__":
    main()
