# RTFaceSwap - Real-Time Face Swapping

Real-time face swapping application using MediaPipe and OpenCV with GPU acceleration.

## Features

- **Real-time face detection and swapping** - Swap faces between two people in live video
- **MediaPipe FaceLandmarker** - High-performance face detection with 468 landmarks (150 strategic points used)
- **GPU Acceleration** - Metal (Apple Silicon) and XNNPACK delegate support
- **ARKit Blend Shapes** - Captures 52 facial expression parameters (eyeBrowInnerUp, mouthSmile, jawOpen, etc.)
- **Head Pose Tracking** - 4x4 transformation matrices for head rotation and position
- **Performance Optimizations**:
  - Delaunay triangulation caching (5-10ms saved per frame)
  - Convex hull caching with LRU eviction
  - Frame-by-frame detection (configurable interval)
  - 3-5x faster than previous dlib-based implementation

## Performance

- **Face Detection**: 10-20ms per frame (MediaPipe)
- **Target FPS**: 30+ fps on Apple M1 Pro
- **Detection Mode**: Every frame processing (FACE_DETECT_INTERVAL=1)

## Requirements

- Python 3.14+
- Webcam
- At least 2 faces in view for face swapping

## Installation

1. Clone the repository:
```bash
git clone https://github.com/mikhailsekerin/RTFaceSwap.git
cd RTFaceSwap
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install opencv-python mediapipe numpy
```

4. The MediaPipe face landmarker model (3.6MB) will be automatically downloaded on first run.

## Usage

Run the application:
```bash
python RTFaceSwap.py
```

**Controls:**
- Press **1** - Enable face swap mode (shows blend shapes if enabled)
- Press **2** - Normal camera view
- Press **q** - Quit application

## Configuration

Edit the configuration flags in `RTFaceSwap.py`:

```python
# Performance settings
FACE_DETECT_INTERVAL = 1  # Detect faces every N frames (1 = every frame)
ENABLE_FPS_COUNTER = True  # Show FPS counter

# Expression and pose data
ENABLE_EXPRESSION_DATA = True  # Capture 52 ARKit facial expressions
SHOW_EXPRESSION_INFO = True    # Display top 3 expressions on screen
ENABLE_POSE_DATA = True        # Capture head pose/rotation matrices
```

## Technical Details

### Face Detection
- **MediaPipe FaceLandmarker v0.10.33** in VIDEO mode with temporal tracking
- Detects up to 2 faces simultaneously
- 468 total landmarks (150 strategic points used for face swapping)
- Minimum detection confidence: 0.5

### Face Swapping Algorithm
1. **Landmark Detection** - Extract 150 facial landmarks from both faces
2. **Delaunay Triangulation** - Divide faces into triangular regions (cached)
3. **Affine Transformation** - Warp triangles from source to destination face
4. **Seamless Cloning** - Blend the swapped face naturally using OpenCV's seamlessClone

### Blend Shapes (ARKit Compatible)
52 facial expression categories captured per face:
- Eye movements (eyeBlinkLeft, eyeWideRight, etc.)
- Eyebrow movements (eyeBrowInnerUp, eyeBrowOuterUp, etc.)
- Mouth expressions (mouthSmile, mouthFrown, jawOpen, etc.)
- Cheek movements (cheekPuff, cheekSquint, etc.)

### GPU Acceleration
- Metal backend on Apple Silicon (M1/M2/M3)
- XNNPACK delegate for CPU inference
- OpenGL support for rendering

## Project History

Originally developed as a university project for Interactive Systems by Vladislav Chirkov, Mikhail Sekerin, and Anton Sorokin.

**Recent Updates:**
- Migrated from dlib (68 landmarks) to MediaPipe (468 landmarks)
- Added ARKit blend shapes and transformation matrices
- Implemented caching for triangulation and convex hulls
- GPU acceleration support
- 3-5x performance improvement

## References

- [MediaPipe Face Landmarker](https://developers.google.com/mediapipe/solutions/vision/face_landmarker)
- [OpenCV Seamless Cloning](https://docs.opencv.org/3.4/df/da0/group__photo__clone.html)
- [Face Swap using OpenCV](http://www.learnopencv.com/face-swap-using-opencv-c-python/)
- [Poisson Image Editing (PDF)](http://www.irisa.fr/vista/Papers/2003_siggraph_perez.pdf)

## License

This project is available for educational and research purposes.