import sys
import numpy as np
import cv2
import dlib
import time

predictor_path = "shape_predictor_68_face_landmarks.dat"
detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor(predictor_path)

# Performance optimization settings
PROCESS_SCALE = 0.5  # Scale down frame for processing (0.5 = 50% size)
FACE_DETECT_INTERVAL = 3  # Only detect faces every N frames
ENABLE_FPS_COUNTER = True  # Show FPS on screen

def get_all_landmarks(im, scale=1.0):
    """Detect all faces in the image and return their landmarks"""
    # Downscale for faster detection if scale < 1.0
    if scale < 1.0:
        small = cv2.resize(im, (int(im.shape[1] * scale), int(im.shape[0] * scale)))
        rects = detector(small, 0)
    else:
        rects = detector(im, 0)
        small = im

    all_landmarks = []
    for rect in rects:
        points = []
        for p in predictor(small, rect).parts():
            # Scale points back to original size and convert to proper type
            points.append((float(p.x / scale), float(p.y / scale)))
        all_landmarks.append(points)

    return all_landmarks


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

def swap(img1, img2, points1, points2):
    img1Warped = np.copy(img2)
    hull1 = []
    hull2 = []
    hullIndex = cv2.convexHull(np.array(points2, dtype=np.float32), returnPoints=False)

    for i in range(0, len(hullIndex)):
        hull1.append(points1[int(hullIndex[i][0])])
        hull2.append(points2[int(hullIndex[i][0])])

    sizeImg2 = img2.shape
    rect = (0, 0, sizeImg2[1], sizeImg2[0])
    dt = calculateDelaunayTriangles(rect, hull2)

    if len(dt) == 0:
        quit()

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

# Cached landmarks for frame skipping
cached_landmarks = []  # List of all detected face landmarks

print("Camera ready! Press 1 to enable face swap, 2 for normal view, q to quit")
print(f"Performance settings: Scale={PROCESS_SCALE}, Detect interval={FACE_DETECT_INTERVAL}")

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
            cached_landmarks = get_all_landmarks(frame, PROCESS_SCALE)

        # Use cached landmarks
        landmarks = cached_landmarks

        # Only swap if exactly 2 faces are detected
        if len(landmarks) == 2:
            points1 = landmarks[0]
            points2 = landmarks[1]

            # Swap both faces - use original frame as source for both swaps
            frame_copy = frame.copy()

            # Create intermediate result with face1 swapped
            temp = swap(frame_copy, frame.copy(), points1, points2)
            # Now swap face2 onto the result (use original frame as source)
            output = swap(frame_copy, temp, points2, points1)

            if ENABLE_FPS_COUNTER:
                cv2.putText(output, f"FPS: {fps:.1f} | 2 faces detected", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

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