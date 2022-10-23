import argparse
import logging
import os
import time

import cv2
import numpy as np
from cv2 import VideoCapture
from cvzone.HandTrackingModule import HandDetector
from mqtt import connect_to_mqtt_broker

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def get_player_from_ip_camera(rtsp_url: str) -> VideoCapture:
    """Generate player

    Args:
        rtsp_url (str): rtsp_url as "rtsp://user:pw@camera_ip"

    Returns:
        VideoCapture: opencv player
    """
    return cv2.VideoCapture(rtsp_url)


def get_player_from_webcam():
    logger.info("Connecting to webcam...")
    return cv2.VideoCapture(0)


def generate_rtsp_url(ip: str, hq: bool = False) -> str:
    """Generate correct ip format, i.e. "rtsp://user:pw@ip".
        Environment variables CAMERA_USER and CAMERA_PW is needed.

    Args:
        ip (str): camera ip

    Returns:
        str: rtsp_url as "rtsp://user:pw@camera_ip"
    """
    if "CAMERA_USER" not in os.environ:
        raise ValueError("CAMERA_USER needs to be set as env variables!")
    elif "CAMERA_PW" not in os.environ:
        raise ValueError("CAMERA_PW needs to be set as env variables!")
    logger.info(f"Connecting to rtsp stream on ip: {ip}")
    user = os.environ["CAMERA_USER"]
    pw = os.environ["CAMERA_PW"]
    if hq:
        stream = "stream1"
    else:
        stream = "stream2"
    return f"rtsp://{user}:{pw}@{ip}/{stream}"


def stream_video(ip: str, frame_rate: int = 2) -> None:
    logger.info("Selecting device...")
    if ip == "localhost":
        player = get_player_from_webcam()
    else:
        rtsp_url = generate_rtsp_url(ip)
        player = get_player_from_ip_camera(rtsp_url)

    #logger.info("Loading face detector...")
    #detector = cv2.CascadeClassifier("haarcascade_frontalface_default.xml")
    prev: float = 0
    detector = HandDetector(detectionCon=0.8, maxHands=2)
    if not DEBUG:
        client = connect_to_mqtt_broker(os.environ["MQTT_BROKER_IP"], os.environ["MQTT_USER"], os.environ["MQTT_PW"])
    else:
        client = None

    while player.isOpened():
        time_elapsed = time.time() - prev
        _, img = player.read()
        if time_elapsed > 1.0 / frame_rate:
            #img = rescale_frame(img, percent=50)
            prev = time.time()
            # faces = haar_find_faces(frame, detector)
            # if len(faces) > 0:
            #    print(faces)
            #    frame = plot_haar_faces(frame, faces)
            if DEBUG:
                hands, img = detector.findHands(img, draw=True)  # with draw
            else:
                hands = detector.findHands(img, draw=False)  # with draw

            if hands:
                fingers = list()
                for hand in hands:
                    # lmList1 = hand["lmList"]  # List of 21 Landmark points
                    # bbox1 = hand["bbox"]  # Bounding box info x,y,w,h
                    # centerPoint1 = hand["center"]  # center of the hand cx,cy
                    # handType1 = hand["type"]  # Handtype Left or Right
                    fingers += detector.fingersUp(hand)
                msg = sum(fingers)
            else:
                msg = "unavailable"
            if client:
                client.publish(os.environ["MQTT_TOPIC"], msg)

            if DEBUG:
                logger.debug(f"Message to be sent to broker {os.environ['MQTT_BROKER_IP']} on topic {os.environ['MQTT_TOPIC']}: {msg}")
                try:
                    cv2.imshow("RTSP hand tracking camera", img)
                except cv2.error as e:
                    logger.warning(e)

                # Quit when 'x' is pressed
                if cv2.waitKey(1) & 0xFF == ord("x"):
                    break
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    player.release()


def rescale_frame(frame, percent=75):
    width = int(frame.shape[1] * percent / 100)
    height = int(frame.shape[0] * percent / 100)
    dim = (width, height)
    return cv2.resize(frame, dim, interpolation=cv2.INTER_AREA)


def plot_haar_faces(frame, faces):
    for (x, y, w, h) in faces:
        # draw the face bounding box on the image
        frame = cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
    return frame


def haar_find_faces(frame, detector) -> np.ndarray:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    # perform face detection
    return detector.detectMultiScale(
        gray, scaleFactor=1.25, minNeighbors=5, minSize=(64, 64), flags=cv2.CASCADE_SCALE_IMAGE
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true", help="print debug messages to stderr")
    parser.add_argument("--prod", action="store_true", help="Run in production mode")
    args = parser.parse_args()
    DEBUG = args.debug
    stream_video(os.environ["CAMERA_IP"])
