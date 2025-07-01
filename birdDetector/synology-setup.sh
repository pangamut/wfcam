# synology-setup.sh (Setup-Script für Synology)
#!/bin/bash

echo "=== Bird Detector Setup für Synology DVA 1622 ==="

# Verzeichnisse erstellen
mkdir -p bird-detector/{snapshots,logs,models}
cd bird-detector

# Docker-Files erstellen
echo "Erstelle Docker-Files..."

# Dockerfile (siehe oben)
cat > Dockerfile << 'EOF'
# Dockerfile
FROM python:3.11-slim

# System-Pakete für OpenCV installieren
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgcc-s1 \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Arbeitsverzeichnis erstellen
WORKDIR /app

# Python-Abhängigkeiten kopieren und installieren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Anwendung kopieren
COPY bird_detector.py .
COPY config.json .

# Verzeichnisse für Daten erstellen
RUN mkdir -p snapshots logs

# Volumes für persistente Daten
VOLUME ["/app/snapshots", "/app/logs", "/app/models"]

# Standard-Benutzer (nicht root)
RUN groupadd -r birduser && useradd -r -g birduser birduser
RUN chown -R birduser:birduser /app
USER birduser

# Health Check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Container starten
CMD ["python", "bird_detector.py"]
EOF

# requirements.txt (siehe oben)
cat > requirements.txt << 'EOF'
opencv-python==4.8.1.78
torch==2.1.0
torchvision==0.16.0
ultralytics==8.0.196
numpy==1.24.3
EOF

# docker-compose.yml (siehe oben)
cat > docker-compose.yml << 'EOF'
version: '3.8'
# ... (docker-compose-Inhalt von oben)
EOF

# Beispiel-Config erstellen
cat > config.json << 'EOF'
{
  "camera": {
    "video_source": "HIER_DEINE_KAMERA_URL_EINFÜGEN",
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
    "model_path": "/app/models/best.pt",
    "intruder_species": ["Nilgans", "Uhu"],
    "snapshot_dir": "/app/snapshots"
  },
  "logging": {
    "level": "INFO",
    "file": "/app/logs/bird_detector.log"
  }
}
EOF

echo "Setup abgeschlossen!"
echo ""
echo "Nächste Schritte:"
echo "1. Kopiere dein best.pt Modell nach ./models/"
echo "2. Passe config.json an (Kamera-URL, IP-Adressen)"
echo "3. Starte mit: docker-compose up -d"
echo "4. Logs anzeigen: docker-compose logs -f"
echo ""
echo "Synology-spezifische Tipps:"
echo "- Container Station verwenden"
echo "- Port 80/443 für Kamera-Zugriff freigeben"
echo "- Snapshot-Ordner für File Station freigeben"