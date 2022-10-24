import argparse
import logging
import os
import time

from cvzone.HandTrackingModule import HandDetector
from imutils import opencv2matplotlib
from PIL import Image

from helpers import (
    get_player_from_ip_camera,
    get_player_from_webcam,
    pil_image_to_byte_array,
)
from mqtt import connect_to_mqtt_broker

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def stream_video(ip: str, frame_rate: int = 2) -> None:
    logger.info("Selecting device...")
    if ip == "localhost":
        player = get_player_from_webcam()
    else:
        player = get_player_from_ip_camera(ip)

    # logger.info("Loading face detector...")
    # detector = cv2.CascadeClassifier("haarcascade_frontalface_default.xml")
    prev: float = 0
    detector = HandDetector(detectionCon=0.8, maxHands=2)
    client = connect_to_mqtt_broker(os.environ["MQTT_USER"], os.environ["MQTT_PW"])
    client.connect(os.environ["MQTT_BROKER_IP"])
    while player.isOpened():
        time_elapsed = time.time() - prev
        _, img = player.read()
        if time_elapsed > 1.0 / frame_rate:
            # img = rescale_frame(img, percent=50)
            prev = time.time()
            # faces = haar_find_faces(frame, detector)
            # if len(faces) > 0:
            #    print(faces)
            #    frame = plot_haar_faces(frame, faces)
            hands, img = detector.findHands(img, draw=True)  # with draw

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
            client.publish(os.environ["MQTT_TOPIC"], msg)

            np_array_RGB = opencv2matplotlib(img)
            image = Image.fromarray(np_array_RGB)
            byte_array = pil_image_to_byte_array(image)
            client.publish("home/camera/capture", byte_array, qos=1)

    player.release()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true", help="print debug messages to stderr")
    parser.add_argument("--prod", action="store_true", help="Run in production mode")
    args = parser.parse_args()
    DEBUG = args.debug
    stream_video(os.environ["CAMERA_IP"])
