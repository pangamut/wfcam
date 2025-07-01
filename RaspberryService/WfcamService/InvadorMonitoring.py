#!/usr/bin/python3 -u
# -*- coding: utf-8 -*-

swversion = "0.0.0"

import sys
import time
from datetime import datetime
import urllib.request

import cv2
import torch
import sqlite3
from ultralytics import YOLO

# IP Steckdose (TASMOTA)
URL_IP_SOCKET = "10.1.2.21"

# Modell  (YOLOv8/YOLO11n)
#MODEL_PATH = "best.pt"  # Das trainierte Modell
MODEL_PATH = "yolo11n_ncnn_model"  # Das trainierte Modell

# Videostream 
VIDEO_SOURCE = "rtsp://stephan:stephan@10.1.2.25/stream2"  #  Kamera-URL

CHECKSPERSECOND = 2     # How often do we look into the Cam per second
WAITSECONDS = 2         # After how many seconds seeing an Intruder do we alarm?
ALARM_DURATION = 5      # duration of an alarm (seconds)
ALARM_WAIT = 30        # time to wait after an alarm before next alarm (seconds)

# Globals

DURATION_MS       = 1000/CHECKSPERSECOND
ALARM_DURATION_MS = ALARM_DURATION * 1000
ALARM_WAIT_MS     = ALARM_WAIT * 1000

cntFrames = 0
cntFramesWithIntruder = 0

lastAlarmStarted = datetime.now()
bAlarmActive = False


def checkFrame(frame, model):

    global cntFrames
    global cntFramesWithIntruder
    
    intruderInFrame = False
     
    # Bild durch das Modell laufen lassen
    results = model(frame, verbose=False)
 
    for result in results:  # Jedes Ergebnis durchgehen
        for box in result.boxes:  # Alle erkannten Objekte
            x1, y1, x2, y2 = box.xyxy[0].tolist()  # Bounding-Box-Koordinaten
            conf = box.conf[0].item()  # Wahrscheinlichkeit
            cls = int(box.cls[0].item())  # Klassen-ID
            vogelart = model.names[cls]  # Klassenname
            if conf > 0.5:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                bildpfad = f"snapshots/{timestamp.replace(' ', '_').replace(':', '-')}-{cntFrames}.jpg"
                #  Bild mit Rahmen speichern
                # result.save(bildpfad)
                frame=result.plot()    # Rahmen auf Ursprungs-Frame zeichnen
                print(f"Erkannt: {vogelart} mit {conf:.2f}% Wahrscheinlichkeit")  # Kontrollausgabe im Terminal/Log
                print(cntFrames, ": " + bildpfad) 
                if vogelart in ["Nilgans", "Uhu"]:
                    intruderInFrame = True
    if intruderInFrame:
        cntFramesWithIntruder += 1
    else:
        cntFramesWithIntruder = 0


def msSince(tStamp):
	elapsed = datetime.now()-tStamp
	elapsed_ms = elapsed.days*24*60*60*1000+elapsed.seconds*1000+elapsed.microseconds/1000
	return elapsed_ms
	
	

def startAlarm():
    global lastAlarmStarted
    global bAlarmActive
    lastAlarmStarted = datetime.now()
    bAlarmActive = True
    try:
        contents = urllib.request.urlopen("http://" + URL_IP_SOCKET + "/cm?cmnd=Power%20On").read()
    except:
        print("Switching Alarm on failed.")
    print("!!! ALARM !!!")
    

def stopAlarm():
    global bAlarmActive
    bAlarmActive = False
    try:
        contents = urllib.request.urlopen("http://" + URL_IP_SOCKET + "/cm?cmnd=Power%20Off").read()
    except:
        print("Switching Alarm off failed.")
    print("!!! ALARM stopped !!!")
    
    
def main(argv):
    global cntFrames
    frameChecked=0
    loopStart=datetime.now()
    bIntruderDetected = False
    
    run = True
    lastCheck = datetime.now()
    
    cap = cv2.VideoCapture(VIDEO_SOURCE)
    if(not cap.isOpened()):
        print("initCam failed.")
        return False
        
    model = YOLO(MODEL_PATH)

    
    while(run):     # Hauptschleife: alle Frames holen, in definierten Abständen checken
        try:
            # remember start of loop, get time since last checked frame and last alarm
            loop_ms = msSince(loopStart)
            loopStart = datetime.now()

            lastCheck_ms = msSince(lastCheck)
            lastAlarm_ms = msSince(lastAlarmStarted)
                    
            # A. read current frame of video stream. Don't miss a frame!
            try:
                ret, frame = cap.read()    # Aktuelles Bild holen
                cntFrames+=1
                if not ret:
                    run=False
                    break
            except:
                print("Reading Frame from Cam failed. retrying.")
                try:
                    cap = cv2.VideoCapture(VIDEO_SOURCE)
                    if(not cap.isOpened()):
                        print("initCam failed.")
                        return False
                except:
                    print("could not reopen Stream")
                    break
    
            # B. evaluate picture in defined frequency
            if(lastCheck_ms>DURATION_MS):
                framesPerSecond = int(0.5+(cntFrames-frameChecked)*1000/lastCheck_ms)
                #print("\n", loopStart, "checking frame ", cntFrames, "(", framesPerSecond, "FPS)")
                checkFrame(frame, model)
                frameChecked=cntFrames
                lastCheck=loopStart
                if(cntFramesWithIntruder > WAITSECONDS*CHECKSPERSECOND):
                    bIntruderDetected = True
     
            # C. stop Alarm, if running long enough
            if bAlarmActive and lastAlarm_ms>ALARM_DURATION_MS:
                stopAlarm()
                            
            # D. start Alarm, if intruder present, and alarm not running, and last alarm not too recent
            if bIntruderDetected:
                bIntruderDetected = False # this detection is now honored, forget about it
                if (not bAlarmActive) and lastAlarm_ms>ALARM_WAIT_MS:
                    startAlarm()
            
         
            # print("Loop ms: ", loop_ms, "last Check ms: ", lastCheck_ms, "last Alrm ms: ", lastAlarm_ms, "  cntFrames: ", cntFrames, "cntFramesWithIntruder: ", cntFramesWithIntruder, "bAlarmActive: ", bAlarmActive, end="\r")
        except:
            break
    
    # graceful exit
    stopAlarm()
    cap.release()

if __name__ == "__main__":
     main(sys.argv[1:])
     
     
     
     
     
     
     
     
     
     
