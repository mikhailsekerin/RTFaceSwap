import sys
import os
import numpy as np
import cv2
import dlib
import time
from threading import Thread, Lock

# Global variables for threaded face detection
detector = dlib.get_frontal_face_detector()
predictor_path = "shape_predictor_68_face_landmarks.dat"

# Check if model file exists before loading
if not os.path.exists(predictor_path):
    print(f"ERROR: Model file '{predictor_path}' not found!", file=sys.stderr)
    print("Please download it from: http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2", file=sys.stderr)
    sys.exit(1)

try:
    predictor = dlib.shape_predictor(predictor_path)
except Exception as e:
    print(f"ERROR: Failed to load model: {e}", file=sys.stderr)
    sys.exit(1)

# Thread-safe variables
face_data_lock = Lock()
cached_points1 = None
cached_points2 = None
cached_face1 = False
cached_face2 = False


def get_landmarks(im):
    """Detect facial landmarks in an image."""
    rects = detector(im, 1)
    points = []
    if len(rects) >= 1:
        # Take first face if multiple detected
        for p in predictor(im, rects[0]).parts():
            points.append((p.x, p.y))
        return points, True
    return points, False


def readPoints(path):
    """Read landmark points from file."""
    points = []
    with open(path) as file:
        for line in file:
            x, y = line.split()
            points.append((int(x), int(y)))
    return points


def applyAffineTransform(src, srcTri, dstTri, size):
    """Apply affine transform to triangle."""
    warpMat = cv2.getAffineTransform(np.float32(srcTri), np.float32(dstTri))
    dst = cv2.warpAffine(
        src, warpMat, (size[0], size[1]),
        None,
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT_101
    )
    return dst


def rectContains(rect, point):
    """Check if point is inside rectangle."""
    return (rect[0] <= point[0] <= rect[0] + rect[2] and
            rect[1] <= point[1] <= rect[1] + rect[3])


def calculateDelaunayTriangles(rect, points):
    """Calculate Delaunay triangulation for given points."""
    subdiv = cv2.Subdiv2D(rect)

    for p in points:
        # Convert to float tuple and ensure within bounds with margin
        x, y = float(p[0]), float(p[1])
        # Add 1px margin from edges to avoid boundary issues
        if (rect[0] + 1 < x < rect[0] + rect[2] - 1 and
            rect[1] + 1 < y < rect[1] + rect[3] - 1):
            try:
                subdiv.insert((x, y))
            except cv2.error:
                # Skip points that cause issues
                continue

    try:
        triangleList = subdiv.getTriangleList()
    except cv2.error:
        return []

    delaunayTri = []

    for t in triangleList:
        pt = [(t[0], t[1]), (t[2], t[3]), (t[4], t[5])]

        if all(rectContains(rect, p) for p in pt):
            ind = []
            for j in range(3):
                for k in range(len(points)):
                    if abs(pt[j][0] - points[k][0]) < 1.0 and abs(pt[j][1] - points[k][1]) < 1.0:
                        ind.append(k)
                        break

            if len(ind) == 3:
                delaunayTri.append((ind[0], ind[1], ind[2]))

    return delaunayTri


def warpTriangle(img1, img2, t1, t2):
    """Warp triangle from img1 to img2."""
    r1 = cv2.boundingRect(np.float32([t1]))
    r2 = cv2.boundingRect(np.float32([t2]))

    # Check for invalid rectangles
    if r1[2] <= 0 or r1[3] <= 0 or r2[2] <= 0 or r2[3] <= 0:
        return

    # Check if rectangles are within image bounds
    if (r1[0] < 0 or r1[1] < 0 or r1[0] + r1[2] > img1.shape[1] or r1[1] + r1[3] > img1.shape[0]):
        return
    if (r2[0] < 0 or r2[1] < 0 or r2[0] + r2[2] > img2.shape[1] or r2[1] + r2[3] > img2.shape[0]):
        return

    t1Rect = []
    t2Rect = []
    t2RectInt = []

    for i in range(3):
        t1Rect.append(((t1[i][0] - r1[0]), (t1[i][1] - r1[1])))
        t2Rect.append(((t2[i][0] - r2[0]), (t2[i][1] - r2[1])))
        t2RectInt.append(((t2[i][0] - r2[0]), (t2[i][1] - r2[1])))

    mask = np.zeros((r2[3], r2[2], 3), dtype=np.float32)
    cv2.fillConvexPoly(mask, np.int32(t2RectInt), (1.0, 1.0, 1.0), 16, 0)

    img1Rect = img1[r1[1]:r1[1] + r1[3], r1[0]:r1[0] + r1[2]]

    # Check if extracted rectangle is valid
    if img1Rect.size == 0 or img1Rect.shape[0] == 0 or img1Rect.shape[1] == 0:
        return

    size = (r2[2], r2[3])
    img2Rect = applyAffineTransform(img1Rect, t1Rect, t2Rect, size)
    img2Rect = img2Rect * mask

    img2[r2[1]:r2[1] + r2[3], r2[0]:r2[0] + r2[2]] = \
        img2[r2[1]:r2[1] + r2[3], r2[0]:r2[0] + r2[2]] * ((1.0, 1.0, 1.0) - mask)

    img2[r2[1]:r2[1] + r2[3], r2[0]:r2[0] + r2[2]] = \
        img2[r2[1]:r2[1] + r2[3], r2[0]:r2[0] + r2[2]] + img2Rect


def swap(img1, img2, points1, points2):
    """Swap faces between two images."""
    if not points1 or not points2:
        return img2

    img1Warped = np.copy(img2)
    hull1 = []
    hull2 = []

    hullIndex = cv2.convexHull(np.array(points2), returnPoints=False)

    for i in range(len(hullIndex)):
        hull1.append(points1[int(hullIndex[i][0])])
        hull2.append(points2[int(hullIndex[i][0])])

    sizeImg2 = img2.shape
    rect = (0, 0, sizeImg2[1], sizeImg2[0])
    dt = calculateDelaunayTriangles(rect, hull2)

    if len(dt) == 0:
        return img2

    for i in range(len(dt)):
        t1 = [hull1[dt[i][j]] for j in range(3)]
        t2 = [hull2[dt[i][j]] for j in range(3)]
        warpTriangle(img1, img1Warped, t1, t2)

    hull8U = [(hull2[i][0], hull2[i][1]) for i in range(len(hull2))]

    mask = np.zeros(img2.shape, dtype=img2.dtype)
    cv2.fillConvexPoly(mask, np.int32(hull8U), (255, 255, 255))

    r = cv2.boundingRect(np.float32([hull2]))
    center = (r[0] + int(r[2] / 2), r[1] + int(r[3] / 2))

    try:
        output = cv2.seamlessClone(np.uint8(img1Warped), img2, mask, center, cv2.NORMAL_CLONE)
        return output
    except cv2.error:
        return img2


def detect_faces_thread(img1, img2):
    """Thread function to detect faces asynchronously."""
    global cached_points1, cached_points2, cached_face1, cached_face2

    # Downscale for faster detection
    scale_factor = 0.5
    small_img1 = cv2.resize(img1, None, fx=scale_factor, fy=scale_factor)
    small_img2 = cv2.resize(img2, None, fx=scale_factor, fy=scale_factor)

    points1, face1 = get_landmarks(small_img1)
    points2, face2 = get_landmarks(small_img2)

    # Scale points back up
    if points1:
        points1 = [(int(x/scale_factor), int(y/scale_factor)) for x, y in points1]
    if points2:
        points2 = [(int(x/scale_factor), int(y/scale_factor)) for x, y in points2]

    with face_data_lock:
        cached_points1 = points1
        cached_points2 = points2
        cached_face1 = face1
        cached_face2 = face2


def main():
    """Main function."""
    global cached_points1, cached_points2, cached_face1, cached_face2

    # Check OpenCV version
    major_ver, minor_ver, _ = cv2.__version__.split('.')
    if int(major_ver) < 3:
        print('ERROR: Script needs OpenCV 3.0 or higher', file=sys.stderr)
        sys.exit(1)

    # Initialize camera
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("ERROR: Cannot open camera", file=sys.stderr)
        sys.exit(1)

    # Set camera properties for better performance
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)

    mode = 0
    detection_thread = None
    last_detection_time = 0
    detection_interval = 0.1  # Detect every 100ms

    # FPS tracking
    fps_start_time = time.time()
    fps_counter = 0
    fps = 0

    print("Controls:")
    print("  Press '1' to enable face swap mode")
    print("  Press '2' to disable face swap mode")
    print("  Press 'q' to quit")

    # Create windows with explicit flags and size for macOS
    cv2.namedWindow("Face Swap", cv2.WINDOW_NORMAL)
    cv2.namedWindow("Face Swapped", cv2.WINDOW_NORMAL)

    # Set proper window sizes
    cv2.resizeWindow("Face Swap", 1280, 720)
    cv2.resizeWindow("Face Swapped", 1280, 720)

    # Force window to front on macOS
    cv2.setWindowProperty("Face Swap", cv2.WND_PROP_TOPMOST, 1)
    cv2.setWindowProperty("Face Swapped", cv2.WND_PROP_TOPMOST, 1)

    try:
        while True:
            ret, frame = cap.read()

            if not ret:
                print("ERROR: Cannot read from camera", file=sys.stderr)
                break

            ch = cv2.waitKey(1) & 0xFF

            if ch == ord('1'):
                mode = 1
                print("Face swap mode: ENABLED")
            elif ch == ord('2'):
                mode = 0
                print("Face swap mode: DISABLED")
            elif ch == ord('q'):
                break

            # Calculate FPS
            fps_counter += 1
            if time.time() - fps_start_time > 1.0:
                fps = fps_counter
                fps_counter = 0
                fps_start_time = time.time()

            if mode == 0:
                # Display original frame with FPS
                display_frame = frame.copy()
                cv2.putText(display_frame, f"FPS: {fps}", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.imshow("Face Swap", display_frame)
            else:
                # Split frame into left and right halves
                img1 = frame[0:frame.shape[0], 0:int(frame.shape[1] / 2)]
                img2 = frame[0:frame.shape[0], int(frame.shape[1] / 2):frame.shape[1]]

                # Start face detection thread if not running
                current_time = time.time()
                if detection_thread is None or not detection_thread.is_alive():
                    if current_time - last_detection_time > detection_interval:
                        detection_thread = Thread(target=detect_faces_thread, args=(img1, img2))
                        detection_thread.start()
                        last_detection_time = current_time

                # Use cached face data
                with face_data_lock:
                    points1 = cached_points1
                    points2 = cached_points2
                    face1 = cached_face1
                    face2 = cached_face2

                # Perform face swap if both faces detected
                if face1 and face2 and points1 and points2:
                    leftframe = swap(img2, img1, points2, points1)
                    rightframe = swap(img1, img2, points1, points2)

                    output = frame.copy()
                    output[0:frame.shape[0], 0:int(frame.shape[1] / 2)] = leftframe
                    output[0:frame.shape[0], int(frame.shape[1] / 2):frame.shape[1]] = rightframe
                else:
                    output = frame.copy()
                    # Draw error message
                    cv2.putText(output, "Detecting faces...", (10, 30),
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

                # Display FPS
                cv2.putText(output, f"FPS: {fps}", (10, 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.imshow("Face Swapped", output)

    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        # Wait for detection thread to finish
        if detection_thread is not None and detection_thread.is_alive():
            detection_thread.join(timeout=1.0)

        cap.release()
        cv2.destroyAllWindows()
        print("Cleanup complete. Goodbye!")


if __name__ == "__main__":
    main()
