import cv2
import os
import time
import numpy as np

# Source - https://stackoverflow.com/q/59371075
# Posted by Nabeel Ayub, modified by community. See post 'Timeline' for change history
# Retrieved 2026-05-23, License - CC BY-SA 4.0

# Source 2: 
# https://medium.com/@siromermer/detecting-and-tracking-moving-objects-with-background-subtractors-using-opencv-f2ff7f94586f


camera = cv2.VideoCapture(0)  # here it throws an error

MOG2_subtractor = cv2.createBackgroundSubtractorMOG2(detectShadows = True) 
# exclude shadow areas from the objects you detected
KNN_subtractor = cv2.createBackgroundSubtractorKNN(detectShadows = True) 
# detectShadows=True : exclude shadow areas from the objects you detected

bg_subtractor=MOG2_subtractor



import json
while(True):
    # Capture frame-by-frame
    ret, frame = camera.read()

    retval, buffer_img = cv2.imencode('.jpg', frame)
    # Every frame is used both for calculating the foreground mask and for updating the background. 
    foreground_mask = bg_subtractor.apply(frame)

    # threshold if it is bigger than 240 pixel is equal to 255 if smaller pixel is equal to 0
    # create binary image , it contains only white and black pixels
    ret , treshold = cv2.threshold(foreground_mask.copy(), 120, 255,cv2.THRESH_BINARY)
    
    # dilation expands or thickens regions of interest in an image.
    dilated = cv2.dilate(treshold,cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3,3)),iterations = 2)
    
    # find contours 
    contours, hier = cv2.findContours(dilated,cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # check every contour if are exceed certain value draw bounding boxes
    for contour in contours:
        # if area exceed certain value then draw bounding boxes
        if cv2.contourArea(contour) > 50:
            (x,y,w,h) = cv2.boundingRect(contour)
            cv2.rectangle(frame, (x,y), (x+w, y+h), (255, 255, 0), 2)

    cv2.imshow("Subtractor", foreground_mask)
    cv2.imshow("threshold", treshold)
    cv2.imshow("detection", frame)

    # Display the resulting frame
    # cv2.imshow('frame',frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# When everything done, release the capture
camera.release()
cv2.destroyAllWindows()
