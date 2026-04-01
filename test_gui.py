#!/usr/bin/env python3
"""
Simple GUI test to verify OpenCV window display works
"""
import cv2
import numpy as np
import sys

print("="*50)
print("  OpenCV GUI Display Test")
print("="*50)
print()

# Check display
print("1. Checking display environment...")
import os
display = os.environ.get('DISPLAY')
print(f"   DISPLAY variable: {display if display else 'Not set (normal for macOS)'}")

# Test camera
print("\n2. Testing camera access...")
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("   ❌ Cannot open camera!")
    sys.exit(1)
print("   ✅ Camera opened successfully")

# Read frame
print("\n3. Reading frame from camera...")
ret, frame = cap.read()
if not ret:
    print("   ❌ Cannot read frame!")
    cap.release()
    sys.exit(1)
print(f"   ✅ Frame captured: {frame.shape}")

# Create test image with text
print("\n4. Creating test window...")
test_frame = frame.copy()
cv2.putText(test_frame, "CAN YOU SEE THIS?", (50, 100),
            cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 0), 3)
cv2.putText(test_frame, "Press ANY KEY to continue", (50, 200),
            cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
cv2.putText(test_frame, "or wait 10 seconds", (50, 250),
            cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

# Create window with all possible flags
window_name = "GUI TEST - Look for this window!"
cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
cv2.setWindowProperty(window_name, cv2.WND_PROP_TOPMOST, 1)
cv2.resizeWindow(window_name, 800, 600)

print(f"   Window created: '{window_name}'")
print()
print("="*50)
print("  LOOK FOR THE WINDOW ON YOUR SCREEN NOW!")
print("  It should show:")
print("  - Your camera feed")
print("  - Green text saying 'CAN YOU SEE THIS?'")
print("="*50)
print()
print("Displaying for 10 seconds...")
print("Press ANY KEY in the window to close early")
print()

# Display
cv2.imshow(window_name, test_frame)
key = cv2.waitKey(10000)  # Wait 10 seconds or until key press

if key == -1:
    print("\n⏱️  Timeout - no key was pressed")
    print("   This means either:")
    print("   1. You didn't see the window, OR")
    print("   2. You saw it but didn't press a key")
else:
    print(f"\n✅ Key pressed! (code: {key})")
    print("   This confirms the window WAS visible!")

# Cleanup
cap.release()
cv2.destroyAllWindows()

print("\nTest complete.")
print()
print("DID YOU SEE THE WINDOW? (yes/no)")
