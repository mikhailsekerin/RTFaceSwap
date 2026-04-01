#!/usr/bin/env python3
"""
Test script for face swapping using static images instead of camera.
This allows testing without camera access.
"""
import sys
import numpy as np
import cv2
import dlib

# Initialize detector and predictor
detector = dlib.get_frontal_face_detector()
predictor_path = "shape_predictor_68_face_landmarks.dat"
predictor = dlib.shape_predictor(predictor_path)


def get_landmarks(im):
    """Detect facial landmarks in an image."""
    rects = detector(im, 1)
    points = []
    if len(rects) >= 1:
        for p in predictor(im, rects[0]).parts():
            points.append((p.x, p.y))
        return points, True
    return points, False


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
        subdiv.insert(p)

    triangleList = subdiv.getTriangleList()
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

    if r1[2] <= 0 or r1[3] <= 0 or r2[2] <= 0 or r2[3] <= 0:
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
        hull1.append(points1[int(hullIndex[i])])
        hull2.append(points2[int(hullIndex[i])])

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
    except cv2.error as e:
        print(f"Warning: seamlessClone failed: {e}")
        return img2


def main():
    """Test face swap with example images."""
    print("Testing face swap with static images...")
    print("Looking for bild*.jpg images...")

    # Try to load two test images
    try:
        img1 = cv2.imread("bild1.jpg")
        img2 = cv2.imread("bild2.jpg")

        if img1 is None or img2 is None:
            print("ERROR: Could not load test images (bild1.jpg, bild2.jpg)")
            print("Please ensure image files are present in the current directory")
            sys.exit(1)

        print(f"✅ Loaded bild1.jpg: {img1.shape}")
        print(f"✅ Loaded bild2.jpg: {img2.shape}")

        # Resize images to same size if needed
        height = min(img1.shape[0], img2.shape[0])
        width = min(img1.shape[1], img2.shape[1])
        img1 = cv2.resize(img1, (width, height))
        img2 = cv2.resize(img2, (width, height))

        print("\n🔍 Detecting faces...")
        points1, face1 = get_landmarks(img1)
        points2, face2 = get_landmarks(img2)

        if not face1:
            print("❌ No face detected in bild1.jpg")
            sys.exit(1)
        if not face2:
            print("❌ No face detected in bild2.jpg")
            sys.exit(1)

        print(f"✅ Face 1: {len(points1)} landmarks detected")
        print(f"✅ Face 2: {len(points2)} landmarks detected")

        print("\n🔄 Performing face swap...")
        result1 = swap(img1, img2, points1, points2)  # img1 face -> img2
        result2 = swap(img2, img1, points2, points1)  # img2 face -> img1

        # Save results
        cv2.imwrite("output_face1_to_2.jpg", result1)
        cv2.imwrite("output_face2_to_1.jpg", result2)

        print("\n✅ Face swap complete!")
        print("📁 Saved results:")
        print("   - output_face1_to_2.jpg (face from bild1 on bild2)")
        print("   - output_face2_to_1.jpg (face from bild2 on bild1)")

        # Display results
        cv2.imshow("Original 1", img1)
        cv2.imshow("Original 2", img2)
        cv2.imshow("Result: Face 1->2", result1)
        cv2.imshow("Result: Face 2->1", result2)

        print("\n⌨️  Press any key to close windows...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
