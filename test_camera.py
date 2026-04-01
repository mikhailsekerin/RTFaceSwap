#!/usr/bin/env python3
"""Simple camera test script"""
import cv2
import sys

print("Testing camera access...")
print("OpenCV version:", cv2.__version__)

# Try different backends
backends = [
    (cv2.CAP_AVFOUNDATION, "AVFoundation (macOS native)"),
    (cv2.CAP_ANY, "Any available backend"),
]

for backend_id, backend_name in backends:
    print(f"\nTrying {backend_name}...")
    cap = cv2.VideoCapture(0, backend_id)

    if cap.isOpened():
        ret, frame = cap.read()
        if ret:
            print(f"✓ SUCCESS with {backend_name}")
            print(f"  Frame size: {frame.shape}")
            cap.release()
            sys.exit(0)
        else:
            print(f"✗ Camera opened but failed to read frame")
            cap.release()
    else:
        print(f"✗ Failed to open camera with {backend_name}")

print("\n✗ All camera backends failed")
print("\nPlease check:")
print("1. System Settings > Privacy & Security > Camera")
print("2. Enable camera access for Terminal or your IDE")
print("3. Restart Terminal/IDE after granting permission")
sys.exit(1)
