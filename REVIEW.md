# wfcam – Code Review

## 📦 Projektstruktur
- **Zweck:** Vogel-Erkennungssystem auf Raspberry Pi (Nilgans & Uhu als "Intruder")
- **Zwei Komponenten:**
  1. `birdDetector/` – Docker-Container für die Erkennung (Python + YOLO)
  2. `RaspberryService/` – systemd-Daemon + Audioplayer (IP-Steckdose als Alarm)

## ✅ Stärken
- saubere Trennung von Detection (Docker) und Service (systemd)
- Health-Check im Dockerfile integriert
- Logging und Snapshots strukturiert
- YOLO11n NCNN-Modell für effiziente Inferenz

## ⚠️ Optimierungsvorschläge

| Bereich | Problem | Empfehlung |
|--|---------|--|
| **Sicherheit** | hardcoded Credentials in `config.json` und `InvadorMonitoring.py` | `.env` Dateien / secrets management |
| **Fehlerbehandlung** | `except: break` ohne Details | Logs + Recovery-Logik |
| **Konfiguration** | `WAITSECONDS`, `CHECKSPERSECOND` als globale Variablen | `config.json` outsource |
| **Code-Qualität** | Kein `requirements.txt` in `RaspberryService` | Python dependencies dokumentieren |
| **Tests** | Keine Unit-Tests sichtbar | Minimal: Integrationstest mit Dummy-Frame |

## 🛠️ Nächste Schritte (wenn gewünscht)
1. `.env` Template für Credentials erstellen
2. `config.json` aufteilen: defaults + override-Datei
3. simple Integrationstest schreiben (`test_frame_processing.py`)
4. CI/CD mit GitHub Actions (Linter + Import-Check)

---

*Review erstellt am: 2026-03-15*
