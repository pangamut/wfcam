#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verbessertes Vogelerkennungs-Alarmsystem
Optimiert für Docker/Synology DVA 1622
"""

import os
import sys
import json
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
import urllib.request
import urllib.error

import cv2
import torch
from ultralytics import YOLO


class BirdDetector:
    """Hauptklasse für Vogelerkennung und Alarmsteuerung"""
    
    def __init__(self, config_path: str = "config.json"):
        """Initialisierung mit Konfigurationsdatei"""
        self.config = self._load_config(config_path)
        self._setup_logging()
        self._setup_directories()
        
        # Zähler und Status
        self.frame_count = 0
        self.frames_with_intruder = 0
        self.alarm_active = False
        self.last_alarm_time = 0
        self.last_check_time = time.time()
        
        # YOLO Model
        self.model = None
        self.cap = None
        
    def _load_config(self, config_path: str) -> dict:
        """Konfiguration aus JSON-Datei laden"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logging.error(f"Config-Datei {config_path} nicht gefunden")
            self._create_default_config(config_path)
            sys.exit(1)
        except json.JSONDecodeError as e:
            logging.error(f"Fehler beim Laden der Config: {e}")
            sys.exit(1)
    
    def _create_default_config(self, config_path: str):
        """Standard-Konfigurationsdatei erstellen"""
        default_config = {
            "camera": {
                "video_source": "https://your-camera-url-here",
                "checks_per_second": 2,
                "confidence_threshold": 0.5
            },
            "alarm": {
                "ip_socket": "10.1.1.81",
                "wait_seconds": 2,
                "duration_seconds": 5,
                "cooldown_seconds": 30
            },
            "detection": {
                "model_path": "best.pt",
                "intruder_species": ["Nilgans", "Uhu"],
                "snapshot_dir": "snapshots"
            },
            "logging": {
                "level": "INFO",
                "file": "bird_detector.log"
            }
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)
        
        print(f"Standard-Config erstellt: {config_path}")
        print("Bitte Video-URL und andere Einstellungen anpassen!")
    
    def _setup_logging(self):
        """Logging konfigurieren"""
        log_level = getattr(logging, self.config['logging']['level'].upper())
        log_file = self.config['logging']['file']
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("Bird Detector gestartet")
    
    def _setup_directories(self):
        """Erforderliche Verzeichnisse erstellen"""
        snapshot_dir = Path(self.config['detection']['snapshot_dir'])
        snapshot_dir.mkdir(exist_ok=True)
        self.logger.info(f"Snapshot-Verzeichnis: {snapshot_dir.absolute()}")
    
    def initialize_camera(self) -> bool:
        """Kamera-Stream initialisieren"""
        video_source = self.config['camera']['video_source']
        self.logger.info(f"Verbinde mit Kamera: {video_source}")
        
        try:
            self.cap = cv2.VideoCapture(video_source)
            if not self.cap.isOpened():
                self.logger.error("Kamera-Stream konnte nicht geöffnet werden")
                return False
            
            # Test-Frame lesen
            ret, _ = self.cap.read()
            if not ret:
                self.logger.error("Kein Frame von Kamera erhalten")
                return False
            
            self.logger.info("Kamera erfolgreich initialisiert")
            return True
            
        except Exception as e:
            self.logger.error(f"Fehler beim Initialisieren der Kamera: {e}")
            return False
    
    def load_model(self) -> bool:
        """YOLO-Modell laden"""
        model_path = self.config['detection']['model_path']
        
        if not os.path.exists(model_path):
            self.logger.error(f"Modell-Datei nicht gefunden: {model_path}")
            return False
        
        try:
            self.model = YOLO(model_path)
            self.logger.info(f"Modell geladen: {model_path}")
            return True
        except Exception as e:
            self.logger.error(f"Fehler beim Laden des Modells: {e}")
            return False
    
    def check_frame(self, frame) -> bool:
        """Frame auf Eindringlinge prüfen"""
        if self.model is None:
            return False
        
        intruder_detected = False
        confidence_threshold = self.config['camera']['confidence_threshold']
        intruder_species = set(self.config['detection']['intruder_species'])
        
        try:
            # YOLO-Erkennung durchführen
            results = self.model(frame, verbose=False)
            
            for result in results:
                for box in result.boxes:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    confidence = box.conf[0].item()
                    class_id = int(box.cls[0].item())
                    species_name = self.model.names[class_id]
                    
                    if confidence > confidence_threshold:
                        self.logger.info(
                            f"Erkannt: {species_name} ({confidence:.2f}%) "
                            f"Frame: {self.frame_count}"
                        )
                        
                        # Snapshot speichern
                        self._save_snapshot(result, species_name, confidence)
                        
                        # Prüfen ob Eindringling
                        if species_name in intruder_species:
                            intruder_detected = True
                            self.logger.warning(
                                f"EINDRINGLING: {species_name} mit {confidence:.2f}%"
                            )
            
            return intruder_detected
            
        except Exception as e:
            self.logger.error(f"Fehler bei Frame-Analyse: {e}")
            return False
    
    def _save_snapshot(self, result, species_name: str, confidence: float):
        """Snapshot mit Erkennungsrahmen speichern"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = (
            f"{timestamp}_frame{self.frame_count}_{species_name}_"
            f"{confidence:.0f}percent.jpg"
        )
        
        snapshot_dir = Path(self.config['detection']['snapshot_dir'])
        filepath = snapshot_dir / filename
        
        try:
            result.save(str(filepath))
            self.logger.debug(f"Snapshot gespeichert: {filepath}")
        except Exception as e:
            self.logger.error(f"Fehler beim Speichern des Snapshots: {e}")
    
    def start_alarm(self):
        """Alarm aktivieren"""
        if self.alarm_active:
            return
        
        self.alarm_active = True
        self.last_alarm_time = time.time()
        
        ip_socket = self.config['alarm']['ip_socket']
        url = f"http://{ip_socket}/cm?cmnd=Power%20On"
        
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                self.logger.info("ALARM GESTARTET!")
        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            self.logger.error(f"Alarm-Aktivierung fehlgeschlagen: {e}")
        except Exception as e:
            self.logger.error(f"Unerwarteter Fehler beim Alarm: {e}")
    
    def stop_alarm(self):
        """Alarm deaktivieren"""
        if not self.alarm_active:
            return
        
        self.alarm_active = False
        
        ip_socket = self.config['alarm']['ip_socket']
        url = f"http://{ip_socket}/cm?cmnd=Power%20Off"
        
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                self.logger.info("Alarm gestoppt")
        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            self.logger.error(f"Alarm-Deaktivierung fehlgeschlagen: {e}")
        except Exception as e:
            self.logger.error(f"Unerwarteter Fehler beim Alarm-Stopp: {e}")
    
    def should_trigger_alarm(self) -> bool:
        """Prüfen ob Alarm ausgelöst werden soll"""
        wait_seconds = self.config['alarm']['wait_seconds']
        checks_per_second = self.config['camera']['checks_per_second']
        cooldown_seconds = self.config['alarm']['cooldown_seconds']
        
        # Genug aufeinanderfolgende Detektionen?
        min_detections = wait_seconds * checks_per_second
        if self.frames_with_intruder < min_detections:
            return False
        
        # Alarm bereits aktiv?
        if self.alarm_active:
            return False
        
        # Cooldown noch aktiv?
        time_since_alarm = time.time() - self.last_alarm_time
        if time_since_alarm < cooldown_seconds:
            return False
        
        return True
    
    def should_stop_alarm(self) -> bool:
        """Prüfen ob Alarm gestoppt werden soll"""
        if not self.alarm_active:
            return False
        
        duration_seconds = self.config['alarm']['duration_seconds']
        alarm_duration = time.time() - self.last_alarm_time
        
        return alarm_duration >= duration_seconds
    
    def reconnect_camera(self) -> bool:
        """Kamera-Verbindung wiederherstellen"""
        self.logger.warning("Versuche Kamera-Reconnect...")
        
        if self.cap:
            self.cap.release()
            time.sleep(2)  # Kurz warten
        
        return self.initialize_camera()
    
    def run(self):
        """Hauptschleife des Detektors"""
        if not self.initialize_camera():
            return False
        
        if not self.load_model():
            return False
        
        checks_per_second = self.config['camera']['checks_per_second']
        check_interval = 1.0 / checks_per_second
        
        self.logger.info("Überwachung gestartet - Drücke Ctrl+C zum Beenden")
        
        try:
            while True:
                loop_start = time.time()
                
                # Frame lesen
                try:
                    ret, frame = self.cap.read()
                    if not ret:
                        self.logger.warning("Kein Frame erhalten - Reconnect...")
                        if not self.reconnect_camera():
                            break
                        continue
                    
                    self.frame_count += 1
                    
                except Exception as e:
                    self.logger.error(f"Fehler beim Frame-Lesen: {e}")
                    if not self.reconnect_camera():
                        break
                    continue
                
                # Frame prüfen (nur in definierten Intervallen)
                current_time = time.time()
                if current_time - self.last_check_time >= check_interval:
                    intruder_detected = self.check_frame(frame)
                    
                    if intruder_detected:
                        self.frames_with_intruder += 1
                    else:
                        self.frames_with_intruder = 0
                    
                    self.last_check_time = current_time
                    
                    # Status-Log
                    fps = self.frame_count / (current_time - self.last_check_time + check_interval)
                    self.logger.debug(
                        f"Frame {self.frame_count}, FPS: {fps:.1f}, "
                        f"Eindringling-Frames: {self.frames_with_intruder}, "
                        f"Alarm: {self.alarm_active}"
                    )
                
                # Alarm-Logik
                if self.should_trigger_alarm():
                    self.start_alarm()
                    self.frames_with_intruder = 0  # Reset nach Alarm
                
                if self.should_stop_alarm():
                    self.stop_alarm()
                
                # Loop-Timing optimieren
                loop_duration = time.time() - loop_start
                if loop_duration < check_interval:
                    time.sleep(check_interval - loop_duration)
        
        except KeyboardInterrupt:
            self.logger.info("Beende auf Benutzeranfrage...")
        except Exception as e:
            self.logger.error(f"Unerwarteter Fehler: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Ressourcen freigeben"""
        self.logger.info("Räume auf...")
        
        if self.alarm_active:
            self.stop_alarm()
        
        if self.cap:
            self.cap.release()
        
        self.logger.info("Bird Detector beendet")


def main():
    """Hauptfunktion"""
    config_file = "config.json"
    
    # Config-Datei als Argument
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
    
    detector = BirdDetector(config_file)
    detector.run()


if __name__ == "__main__":
    main()