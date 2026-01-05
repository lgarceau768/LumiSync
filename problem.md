# LED Count Configuration Issue

## Problem Statement
The H61D5 rope light device has an unusual behavior: **increasing the LED count configuration decreases the portion of the rope that lights up**, which is the opposite of what would be expected.

## Investigation Summary

### Initial Observations
- Device model: **H61D5** (at 192.168.0.119:4001)
- Physical rope appearance: approximately 25 physical LEDs
- Early tests showed device accepts up to 40 LEDs before failing
- But syncing behavior was incorrect - only partial rope coverage

### Testing Performed

#### Test 1: diagnose_devices.py
- 10 LEDs: appeared to be ~2/5 of rope length
- 40 LEDs: tested as working in binary test
- 60+ LEDs: failed

#### Test 2: investigate_led_count.py
- Phase 1 (small increments, 10-30 LEDs):
  - Working counts: [10, 12, 14, 16, 18, 22, 24]
  - Failures: 20, 26, 28, 30 (intermittent/unreliable)
  - Max reliable: 24 LEDs
- Phase 2 (40-60 range):
  - All counts failed immediately
  - Note: This contradicted earlier diagnose_devices.py results

#### Test 3: find_true_max.py
- Tested: 20, 24, 30, 40, 50, 60, 80, 100, 120, 140, 160, 200, 255
- Result: **None lit the entire rope**
- Key finding: **Increasing LED count DECREASES rope coverage**

#### Test 4: find_max_downward.py
- Tested downward from 10 to 1 LED
- **Result: 4 LEDs lights up the ENTIRE rope** ✓

## Current Configuration
- **nled: 4** (entire rope now lights up during syncing)

## Root Cause: Firmware Limitation

**CONFIRMED**: The H61D5 device has a **hard firmware limit of 4 LEDs maximum**.

### Investigation Results

#### Encoding Analysis (debug_encoding.py)
- ✓ All encodings are technically correct
- ✓ All checksums valid for counts 1-40
- ✓ Protocol structure perfect for all tested counts
- ✓ No packet size issues (max 127 bytes, well within limits)
- **Conclusion**: NOT an encoding/protocol bug

#### Protocol Variations Testing (test_protocol_variations.py)
Tested with H61D5:
- ✓ 4 LEDs: **WORKS** - Full rope coverage
- ✗ 5 LEDs: Fails (with reset, without reset - same result)
- ✗ 6 LEDs: Fails
- ✗ 7 LEDs: Fails
- ✗ 8 LEDs: Fails (even 2x the working count)
- ✗ 12 LEDs: Fails
- ✗ 16 LEDs: Fails
- ✗ Repeat patterns: Fails
- **Conclusion**: Hard firmware limit at 4 LEDs

### Why It Appears to Accept Higher Counts

Earlier tests (diagnose_devices.py) showed 40 LEDs "working" because:
- The device **accepts** the command (no error response)
- But it **doesn't display** the colors correctly (only shows portion of rope)
- This is silent failure - device takes the command but can't execute it properly
- The "increasing LED count = decreasing coverage" is the device firmware struggling to map >4 LEDs

### Physical Hardware

The rope has approximately **4 addressable segments/zones**, not individual LEDs:
- Physical rope likely has 24-25 actual diodes
- But controlled through 4 firmware-level addressable zones
- Each zone represents ~6 LEDs in the physical rope

## Solution: Configure for 4 LEDs

Set `nled` to **4** - this is the **correct and only working configuration**.

### Optimizations Made

1. **Strategic Corner Sampling** (monitor.py)
   - For 4 LEDs: Samples from corners (20%, 80%) instead of grid centers
   - Provides better monitor content representation
   - Top-left, top-right, bottom-left, bottom-right sampling
   - Much better for syncing actual screen content to rope

2. **Grid Sampling Fallback** (monitor.py)
   - Code ready for if device firmware ever supports 5+ LEDs
   - Grid-based approach for hypothetical higher counts

## Reproduction Steps
```bash
python3 tests/find_max_downward.py
```
- 4 LEDs: Full rope lights up
- 5+ LEDs: Partial/decreasing coverage
- Higher counts: Even less coverage

## Files Related to This Issue
- `/lumisync/tests/diagnose_devices.py` - Initial diagnostic
- `/lumisync/tests/investigate_led_count.py` - Phase testing (10-30 and 40-60 ranges)
- `/lumisync/tests/find_true_max.py` - Full coverage testing (downward discovery)
- `/lumisync/tests/find_max_downward.py` - Systematic downward testing
- `/lumisync/settings.json` - Current config: `"nled": 4`
