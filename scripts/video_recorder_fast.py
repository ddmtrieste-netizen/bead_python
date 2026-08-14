import cv2
# print(cv2.getBuildInformation())

# Change device=/dev/video0 to match your webcam's index if you have multiple cameras
gst_pipeline = (
    "v4l2src device=/dev/video0 ! "
    "video/x-raw, width=640, height=480 ! "
    "videoconvert ! "
    "video/x-raw, format=BGR ! "
    "appsink drop=true sync=false"
)

cap = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)

if not cap.isOpened():
    print("Failed to open webcam with GStreamer pipeline.")
    exit()

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # 'frame' arrives ready as a Grayscale image.
    # cv2.cvtColor is bypassed entirely.

    cv2.imshow("Webcam Native Grayscale", frame)
    if cv2.waitKey(1) & 0xFF == 27:  # ESC key to exit
        break

cap.release()
cv2.destroyAllWindows()