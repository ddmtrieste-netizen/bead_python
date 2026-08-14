import cv2
import os
import time
import numpy as np

def record_frames(output_folder="output_frames", camera_index=0):
    # Create the output directory if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"Created folder: {output_folder}")

    # Initialize the USB camera (0 is usually the default built-in or first USB cam)
    cap = cv2.VideoCapture(camera_index)

    if not cap.isOpened():
        print(f"Error: Could not open video device at index {camera_index}")
        return

    print("Recording started. Press 'q' to quit.")
    frame_count = 0
    frame_count1 = frame_count
    frame_store = np.zeros((480, 640, 4000), dtype=np.uint8)

    t0 = time.time()
    t1 = t0
    try:
        while True:
            # Capture frame-by-frame
            ret, frame = cap.read()
            #print(frame.shape[0])
            #print(frame.shape[1])
            #print()
            if not ret:
                print("Error: Failed to grab frame.")
                break

            # Create a unique filename using a padded frame count
            # filename = os.path.join(output_folder, f"frame_{frame_count:05d}.jpg")
            frame_store[:,:, frame_count] = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            # Save the frame as a JPEG
            # cv2.imwrite(filename, frame)
            frame_count += 1
            frame_count1 += 1


            # Optional: Display the recording live stream
            # cv2.imshow('USB Camera Feed', frame)

            # Break the loop if 'q' key is pressed
            # The parameter inside waitKey is milliseconds to wait between frames

            t_now = time.time()
            # debug
            # if (int(t_now - t0) % 10 == 0 ): 
            #    t1 = time.time()
            #    frame_count1 = 0
            #    print(f"Time enlapsed: {t_now - t0}")
            # print(f"FPS: {frame_count1/(t_now - t1)}") 
            #if cv2.waitKey(1) & 0xFF == ord('q') or t_now - t0 >= 5:
            if frame_count % 100:
                print(f"Tempo impiegato: {t_now - t1}")
                print(f"frame number: {frame_count} / 4000")
            if frame_count > 4000:
                print(f"Tempo impiegato: {t_now - t1}")
                break

    finally:
        # Clean up everything when done
        for frame_count in range(0, 4000):
            filename = os.path.join(output_folder, f"frame_{frame_count:05d}.jpg")
            cv2.imwrite(filename, frame_store[:, :, frame_count])
        cap.release()
        cv2.destroyAllWindows()
        print(f"Recording stopped. Saved {frame_count} frames to '{output_folder}'.")

if __name__ == "__main__":
    output_folder = "./two_spheres_channels/test1"
    record_frames(output_folder)