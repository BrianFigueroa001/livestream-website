#webstreaming.py
#Sources used: https://www.pyimagesearch.com/2019/09/02/opencv-stream-video-to-web-browser-html-page/
#Purpose:
#   This module uses OpenCV to access webcam, perform motion detection w/ SingleMotionDetector object,
#   and then serve output frames to web browser via Flask.
#
#IMPORTANT NOTE FOR LIVE STREAMING:
#   Capturing a live stream from the laptop's webcam is done in this module. 
#   It can be 'supplemented' with motion detection via implementing SingleMotionDetector.py. Refer to source.
#
#IMPORTANT NOTE FOR STATIC STREAMING:
#   Flask makes streaming a static video very easy. Steps:
#		1) Have the folder named 'static' and store the video file there.
#		2) Do the rest in HTML code. Refer to index.html.

from imutils.video import VideoStream # Allows VIDEO ACCESS to a webcam, raspberry PI camera module, or video file.
from flask import Response
from flask import Flask
from flask import render_template
import threading # support concurry. aka multiple clients, web browsers, and tabs at the same time
import imutils
import time
import cv2
import os

#The URL stream
#NOTE: Whenever yamcam is turned off or no-ip is restarted, need to get updated link to stream.
STREAM_URL = 'http://bfcamera.servehttp.com:8081/video.mjpg?q=30&fps=33&id=0.5794413727626593&r=1585174552210/video?type=some.mjpeg'

# initialize the live stream frame and a lock used to ensure thread-safe
# exchanges of the output frames (useful when multiple browsers/tabs
# are viewing the stream)
liveOutputFrame = None 

#used to ensure thread-safe behavior when updating output frame.
#i.e., ensuring that one thread isn't trying to read the frame as it's being updated.
liveLock = threading.Lock() 
         
# initialize a flask object
app = Flask(__name__)

# initialize the video stream and allow the camera sensor to warmup
liveVS = VideoStream(STREAM_URL).start() #Object that provides access to web camera.
time.sleep(2.0)

#Function is responsible for:
# 1. Looping over frames in video stream
# 2. Applying motion detection.
# 3. Drawing any results on the liveOutputFrame.
#
#   If we don't have at least frameCount frames, we'll continue to compute accumulated weighted average.
#   Once frameCunt is reached, we'll start performing background subtraction.
#
# @Param frameCount = min # of requires frames to build background 'bg' in SingleMotionDetector object.
def liveStreamVideo(frameCount):
    # grab global references pertaining to live streaming.
    global liveVS, liveOutputFrame, liveLock

    # initialize the motion detector and the total number of frames read thus far
    #motionDetector = SingleMotionDetector(accumWeight=0.1)
    #total = 0

    # loop over frames from the video stream
    while True:
        # read the next frame from the video stream, resize it,
        # convert the frame to grayscale, and blur it
        frame = liveVS.read()
        frame = imutils.resize(frame, width=400) #resizing frame input smaller = the less data there is to process (faster processing)

        # Ensures liveOutputFrame is not being read by client while it is being updated here.
        with liveLock:
            liveOutputFrame = frame.copy()

# Generator function
#
# Encode liveOutputFrame as JPEG data.
#
# GENERATOR FuNCTIONS: Yield are used in Python generators. 
#                      A generator function is defined like a normal function, but whenever it needs to generate a value, 
#                      it does so with the yield keyword rather than return. 
#                      If the body of a def contains yield, the function automatically becomes a generator function.
#
#                      The yield statement suspends function’s execution and sends a value back to the caller, 
#                      but retains enough state to enable function to resume where it is left off. When resumed, 
#                      the function continues execution immediately after the last yield run. 
#                      This allows its code to produce a series of values over time, rather than computing them at once and 
#                      sending them back like a list.
#
#                      Return sends a specified value back to its caller whereas Yield can produce a sequence of values. 
#                      We should use yield when we want to iterate over a sequence, but don’t want to store the entire sequence 
#                      in memory.
def liveGenerate():
    # grab global references to the output frame and lock variables
    global liveOutputFrame, liveLock
    # loop over frames from the output stream
    while True:
        # wait until the liveLock is acquired
        with liveLock:
            # check if the output frame is available, otherwise skip
            # the iteration of the loop
            if liveOutputFrame is None:
                continue

            # encode the frame in JPEG format
            (flag, encodedImage) = cv2.imencode(".jpg", liveOutputFrame)

            # ensure the frame was successfully encoded
            # aka flag == false -> encoding failed.
            if not flag:
                continue

        # yield the output frame in the byte format
        yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + 
            bytearray(encodedImage) + b'\r\n')

# The code below Handles parsing command line arguments and launching flask app.
# There are three command line arguments used.
# --ip : the IP address of the sytem you are launching webstream.py file from.
# --port: the port number that the flask app will run on (normally supplied value of 8000)
# --frame-count: the number of frames used to accumulate and build the background model
#                before motion detection is performed. By default, we use 32 frames to build
#                background model.

@app.route("/")
def index():
    # return the rendered template
    return render_template("index.html")

#@app.route("/live_video_feed") tells Flask that this function is a URL endpoint.
#Data is being served from https://your-ip-address/video_feed
#
# Output of video_feed is the live motion detection output, encoded as a byte array via the generate function.
#
# NOTE: Web browser is smart enough to take this byte array and display it in your browser as a live feed!
#
# Line 9 in index.html instructs flask to dynamically render the URL of /video_feed route.
@app.route("/live_video_feed")
def live_video_feed():
    # return the response generated along with the specific media type (mime type)
    return Response(liveGenerate(), mimetype = "multipart/x-mixed-replace; boundary=frame")

# check to see if this is the main thread of execution.
if __name__ == '__main__':
    # construct the argument parser and parse command line arguments
    PORT = port = int(os.environ.get("PORT", 8000))
    #IP_ADDRESS = "127.0.0.1"
    IP_ADDRESS = "0.0.0.0"
    FRAME_COUNT = [3] # Need to pass as an arbitrary iterable object for threading.Thread()

    # start a thread for live-streaming.
    # Recall that Thread() requires 2 arguments:
    #   1. target = function for thread to start execution.
    #   2. args = an iterable to pass as arguments for the target function (even if its only 1 arg)
    liveThread = threading.Thread(target=liveStreamVideo, args=FRAME_COUNT)
    liveThread.daemon = True # This thread will never ends (until server is terminated)
    liveThread.start()

    # start the flask app
    app.run(host=IP_ADDRESS, port=PORT, debug=True, threaded=True, use_reloader=False)

# release the video stream pointers
liveVS.stop()