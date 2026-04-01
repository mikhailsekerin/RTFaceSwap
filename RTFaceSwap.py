import sys
import numpy as np
import cv2
import time
import os
import urllib.request
from pathlib import Path

# MediaPipe imports
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import (
    FaceLandmarker,
    FaceLandmarkerOptions,
    RunningMode
)
import mediapipe as mp

MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
MODEL_PATH = "models/face_landmarker.task"

def ensure_model_downloaded():
    """Download MediaPipe model if not present"""
    if os.path.exists(MODEL_PATH):
        return MODEL_PATH

    print("Downloading MediaPipe face_landmarker model (~5.7MB)...")
    os.makedirs("models", exist_ok=True)

    try:
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print(f"Model downloaded to {MODEL_PATH}")
        return MODEL_PATH
    except Exception as e:
        print(f"Error downloading model: {e}")
        print(f"Download manually from: {MODEL_URL}")
        sys.exit(1)

# Download model and initialize MediaPipe
model_path = ensure_model_downloaded()
base_options = BaseOptions(model_asset_path=model_path)
options = FaceLandmarkerOptions(
    base_options=base_options,
    running_mode=RunningMode.VIDEO,
    num_faces=2,
    min_face_detection_confidence=0.5,
    min_face_presence_confidence=0.5,
    min_tracking_confidence=0.5,
    output_face_blendshapes=True,  # Enable 52 ARKit-compatible facial expressions
    output_facial_transformation_matrixes=True  # Enable head pose/rotation data
)
face_landmarker = FaceLandmarker.create_from_options(options)

# Performance optimization settings
FACE_DETECT_INTERVAL = 1      # Detect every frame (MediaPipe is fast enough)
PROCESS_SCALE = 1.0            # Full resolution (no need to downscale)
ENABLE_FPS_COUNTER = True      # Show FPS on screen

# Advanced features (blend shapes and transformation matrices)
ENABLE_EXPRESSION_DATA = True  # Capture 52 ARKit facial expression parameters
SHOW_EXPRESSION_INFO = True    # Display top expressions in debug mode
ENABLE_POSE_DATA = True        # Capture head pose/rotation matrices

# MediaPipe landmark indices for face swapping (~150 key points)
MEDIAPIPE_FACE_SWAP_INDICES = [
    # Face oval
    10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288,
    397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
    172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109,
    # Left eye
    33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246,
    # Right eye
    362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398,
    # Lips outer and inner
    61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 308, 324, 318, 402, 317,
    14, 87, 178, 88, 95, 78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308,
    # Nose
    1, 2, 98, 327, 4, 5, 6, 168, 197, 195,
    # Eyebrows
    70, 63, 105, 66, 107, 55, 65, 52, 53, 46,
    300, 293, 334, 296, 336, 285, 295, 282, 283, 276
]

class FaceSwapCache:
    """Cache for expensive computations (triangulation and convex hull)"""
    def __init__(self, max_size=100):
        self.triangulation_cache = {}
        self.hull_cache = {}
        self.max_size = max_size

    def _make_key(self, points):
        """Create hashable key from points"""
        return tuple(tuple(p) for p in points[:10])  # Use first 10 points as key

    def get_hull(self, points):
        """Get cached convex hull or compute"""
        key = self._make_key(points)
        if key not in self.hull_cache:
            hull_index = cv2.convexHull(np.array(points, dtype=np.float32), returnPoints=False)
            self.hull_cache[key] = hull_index
            if len(self.hull_cache) > self.max_size:
                self.hull_cache.pop(next(iter(self.hull_cache)))
        return self.hull_cache[key]

    def get_triangulation(self, points, rect):
        """Get cached triangulation or compute"""
        key = self._make_key(points)
        if key not in self.triangulation_cache:
            dt = calculateDelaunayTriangles(rect, points)
            self.triangulation_cache[key] = dt
            if len(self.triangulation_cache) > self.max_size:
                self.triangulation_cache.pop(next(iter(self.triangulation_cache)))
        return self.triangulation_cache[key]

def get_all_landmarks(im, timestamp_ms):
    """Detect faces using MediaPipe and return landmarks, blend shapes, and pose data"""
    # Convert BGR to RGB for MediaPipe
    rgb_frame = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

    # Detect with timestamp for VIDEO mode
    detection_result = face_landmarker.detect_for_video(mp_image, timestamp_ms)

    all_landmarks = []
    all_blendshapes = []
    all_transforms = []

    if detection_result.face_landmarks:
        h, w = im.shape[:2]
        for i, face_landmarks in enumerate(detection_result.face_landmarks):
            # Extract subset of landmarks and convert to pixels
            points = []
            for idx in MEDIAPIPE_FACE_SWAP_INDICES:
                if idx < len(face_landmarks):
                    lm = face_landmarks[idx]
                    x = float(lm.x * w)
                    y = float(lm.y * h)
                    points.append((x, y))

            if len(points) > 0:
                all_landmarks.append(points)

                # Collect blend shapes if enabled (52 ARKit expressions)
                if ENABLE_EXPRESSION_DATA and detection_result.face_blendshapes:
                    if i < len(detection_result.face_blendshapes):
                        blendshapes = {}
                        for blendshape in detection_result.face_blendshapes[i]:
                            blendshapes[blendshape.category_name] = blendshape.score
                        all_blendshapes.append(blendshapes)

                # Collect transformation matrices if enabled (4x4 pose matrix)
                if ENABLE_POSE_DATA and detection_result.facial_transformation_matrixes:
                    if i < len(detection_result.facial_transformation_matrixes):
                        all_transforms.append(detection_result.facial_transformation_matrixes[i])

    return all_landmarks, all_blendshapes, all_transforms


def readPoints(path):
    points = []
    with open(path) as file:
        for line in file:
            x, y = line.split()
            points.append((int(x), int(y)))
    return points


def applyAffineTransform(src, srcTri, dstTri, size):
    warpMat = cv2.getAffineTransform(np.float32(srcTri), np.float32(dstTri))
    dst = cv2.warpAffine(src, warpMat, (size[0], size[1]), None, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
    return dst



def rectContains(rect, point):
    if point[0] < rect[0]:
        return False
    elif point[1] < rect[1]:
        return False
    elif point[0] > rect[0] + rect[2]:
        return False
    elif point[1] > rect[1] + rect[3]:
        return False
    return True



def calculateDelaunayTriangles(rect, points):
    subdiv = cv2.Subdiv2D(rect)

    for p in points:
        # Validate point is within rect bounds
        if rectContains(rect, p):
            try:
                subdiv.insert((float(p[0]), float(p[1])))
            except:
                pass  # Skip invalid points
    triangleList = subdiv.getTriangleList();
    delaunayTri = []
    pt = []

    for t in triangleList:
        pt.append((t[0], t[1]))
        pt.append((t[2], t[3]))
        pt.append((t[4], t[5]))
        pt1 = (t[0], t[1])
        pt2 = (t[2], t[3])
        pt3 = (t[4], t[5])

        if rectContains(rect, pt1) and rectContains(rect, pt2) and rectContains(rect, pt3):
            ind = []
            for j in range(0, 3):
                for k in range(0, len(points)):
                    if (abs(pt[j][0] - points[k][0]) < 1.0 and abs(pt[j][1] - points[k][1]) < 1.0):
                        ind.append(k)
            if len(ind) == 3:
                delaunayTri.append((ind[0], ind[1], ind[2]))
        pt = []

    return delaunayTri

def warpTriangle(img1, img2, t1, t2):
    r1 = cv2.boundingRect(np.float32([t1]))
    r2 = cv2.boundingRect(np.float32([t2]))

    # Validate rectangle dimensions
    if r1[2] <= 0 or r1[3] <= 0 or r2[2] <= 0 or r2[3] <= 0:
        return

    # Validate rectangle bounds
    if (r1[0] < 0 or r1[1] < 0 or r1[0] + r1[2] > img1.shape[1] or r1[1] + r1[3] > img1.shape[0] or
        r2[0] < 0 or r2[1] < 0 or r2[0] + r2[2] > img2.shape[1] or r2[1] + r2[3] > img2.shape[0]):
        return

    t1Rect = []
    t2Rect = []
    t2RectInt = []

    for i in range(0, 3):
        t1Rect.append(((t1[i][0] - r1[0]), (t1[i][1] - r1[1])))
        t2Rect.append(((t2[i][0] - r2[0]), (t2[i][1] - r2[1])))
        t2RectInt.append(((t2[i][0] - r2[0]), (t2[i][1] - r2[1])))

    mask = np.zeros((r2[3], r2[2], 3), dtype=np.float32)
    cv2.fillConvexPoly(mask, np.int32(t2RectInt), (1.0, 1.0, 1.0), 16, 0);
    img1Rect = img1[r1[1]:r1[1] + r1[3], r1[0]:r1[0] + r1[2]]

    if img1Rect.shape[0] <= 0 or img1Rect.shape[1] <= 0:
        return

    size = (r2[2], r2[3])
    img2Rect = applyAffineTransform(img1Rect, t1Rect, t2Rect, size)
    img2Rect = img2Rect * mask

    img2[r2[1]:r2[1] + r2[3], r2[0]:r2[0] + r2[2]] = img2[r2[1]:r2[1] + r2[3], r2[0]:r2[0] + r2[2]] * (
    (1.0, 1.0, 1.0) - mask)

    img2[r2[1]:r2[1] + r2[3], r2[0]:r2[0] + r2[2]] = img2[r2[1]:r2[1] + r2[3], r2[0]:r2[0] + r2[2]] + img2Rect

def swap(img1, img2, points1, points2, cache=None):
    img1Warped = np.copy(img2)
    hull1 = []
    hull2 = []

    # Use cached hull if available
    if cache:
        hullIndex = cache.get_hull(points2)
    else:
        hullIndex = cv2.convexHull(np.array(points2, dtype=np.float32), returnPoints=False)

    for i in range(0, len(hullIndex)):
        hull1.append(points1[int(hullIndex[i][0])])
        hull2.append(points2[int(hullIndex[i][0])])

    sizeImg2 = img2.shape
    rect = (0, 0, sizeImg2[1], sizeImg2[0])

    # Use cached triangulation if available
    if cache:
        dt = cache.get_triangulation(hull2, rect)
    else:
        dt = calculateDelaunayTriangles(rect, hull2)

    if len(dt) == 0:
        return img2

    for i in range(0, len(dt)):
        t1 = []
        t2 = []

        for j in range(0, 3):
            t1.append(hull1[dt[i][j]])
            t2.append(hull2[dt[i][j]])

        warpTriangle(img1, img1Warped, t1, t2)

    hull8U = []
    for i in range(0, len(hull2)):
        hull8U.append((hull2[i][0], hull2[i][1]))

    mask = np.zeros(img2.shape, dtype=img2.dtype)
    cv2.fillConvexPoly(mask, np.int32(hull8U), (255, 255, 255))
    r = cv2.boundingRect(np.float32([hull2]))

    # Validate bounding rectangle
    if r[2] <= 0 or r[3] <= 0:
        return img2

    center = (r[0] + int(r[2] / 2), r[1] + int(r[3] / 2))

    # Validate center is within image bounds
    if center[0] < 0 or center[0] >= img2.shape[1] or center[1] < 0 or center[1] >= img2.shape[0]:
        return img2

    # Try seamless clone with error handling
    try:
        output = cv2.seamlessClone(np.uint8(img1Warped), img2, mask, center, cv2.NORMAL_CLONE)
        return output
    except:
        return img2


def find_camera():
    """Try to find a working camera"""
    # Try different backends
    backends = [cv2.CAP_ANY, cv2.CAP_AVFOUNDATION, 0]

    for backend in backends:
        for i in range(3):  # Try camera indices 0-2
            cap = cv2.VideoCapture(i, backend) if backend else cv2.VideoCapture(i)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    print(f"Successfully opened camera {i} with backend {backend}")
                    return cap
                cap.release()
    return None

print("Initializing camera...")
cap = find_camera()
mode = 0

if cap is None:
    print("\nError: Could not open any camera.")
    print("Please ensure:")
    print("1. Camera access is granted in System Settings > Privacy & Security > Camera")
    print("2. No other application is using the camera")
    print("3. Your camera is properly connected")
    sys.exit(1)

# Performance tracking
frame_count = 0
fps_start_time = time.time()
fps = 0

# Initialize cache and timestamp
cache = FaceSwapCache()
timestamp_ms = 0

# Cached detection data for frame skipping
cached_landmarks = []  # List of all detected face landmarks
cached_blendshapes = []  # List of blend shape dictionaries (52 ARKit expressions)
cached_transforms = []  # List of 4x4 transformation matrices (head pose/rotation)

print("Camera ready! Press 1 to enable face swap, 2 for normal view, q to quit")
print(f"Performance settings: MediaPipe, Detect interval={FACE_DETECT_INTERVAL}")

while(True):
    ret, frame = cap.read()
    if not ret:
        print("Error: Failed to capture frame from camera")
        break

    frame_count += 1

    # Calculate FPS
    if ENABLE_FPS_COUNTER and frame_count % 30 == 0:
        fps_end_time = time.time()
        fps = 30 / (fps_end_time - fps_start_time)
        fps_start_time = fps_end_time

    ch = cv2.waitKey(1) & 0xFF
    if ch == ord('1'):
        mode = 1
        frame_count = 0  # Reset for fresh detection

    if ch == ord('q'):
        break

    if ch == ord('2'):
        mode = 0

    if mode == 0:
        if ENABLE_FPS_COUNTER:
            cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.imshow("Face swap", frame)

    if mode == 1:
        (major_ver, minor_ver, subminor_ver) = (cv2.__version__).split('.')

        if int(major_ver) < 3:
            print("ERROR: Script needs OpenCV 3.0 or higher", file=sys.stderr)
            sys.exit(1)

        # Detect all faces in the full frame every N frames
        if frame_count % FACE_DETECT_INTERVAL == 0:
            cached_landmarks, cached_blendshapes, cached_transforms = get_all_landmarks(frame, timestamp_ms)

        # Increment timestamp for MediaPipe VIDEO mode
        timestamp_ms += int(1000 / 30)  # Increment by ~33ms per frame (30 FPS)

        # Use cached landmarks
        landmarks = cached_landmarks

        # Only swap if exactly 2 faces are detected
        if len(landmarks) == 2:
            points1 = landmarks[0]
            points2 = landmarks[1]

            # Swap both faces - use original frame as source for both swaps
            frame_copy = frame.copy()

            # Create intermediate result with face1 swapped
            temp = swap(frame_copy, frame.copy(), points1, points2, cache)
            # Now swap face2 onto the result (use original frame as source)
            output = swap(frame_copy, temp, points2, points1, cache)

            if ENABLE_FPS_COUNTER:
                cv2.putText(output, f"FPS: {fps:.1f} | 2 faces detected", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            # Display top expressions in debug mode
            if SHOW_EXPRESSION_INFO and len(cached_blendshapes) > 0:
                y_offset = 60
                for face_idx, blendshapes in enumerate(cached_blendshapes[:2]):
                    # Get top 3 expressions
                    top_expressions = sorted(blendshapes.items(), key=lambda x: x[1], reverse=True)[:3]
                    cv2.putText(output, f"Face {face_idx + 1}:", (10, y_offset),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
                    y_offset += 20
                    for exp_name, score in top_expressions:
                        cv2.putText(output, f"  {exp_name}: {score:.2f}", (10, y_offset),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)
                        y_offset += 18

            cv2.imshow("Face Swapped", output)
        else:
            # Show original frame with message if not exactly 2 faces
            display_frame = frame.copy()
            msg = f"Detected {len(landmarks)} face(s) - need exactly 2"
            cv2.putText(display_frame, msg, (50, 50),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            if ENABLE_FPS_COUNTER:
                cv2.putText(display_frame, f"FPS: {fps:.1f}", (10, frame.shape[0] - 20),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.imshow("Face Swapped", display_frame)

cap.release()
cv2.destroyAllWindows()