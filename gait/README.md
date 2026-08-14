# Wearable 3D Knee Gait Analysis System

This dashboard is a production-oriented upgrade for a Raspberry Pi 5-based gait analysis setup. It preserves the existing UDP-driven architecture while adding a medical-style interface, live digital readouts, a high-volume data table, real-time graphs, a 3D orientation viewer, diagnostics, and CSV recording.

## Features
- Live knee pitch, roll, and yaw readouts
- Real-time graphing for pitch/roll/yaw
- 3D OpenGL knee orientation viewer
- Continuous data table with newest-row-first behavior
- Diagnostic panel for packet, latency, jitter, and connection metrics
- Recording controls and CSV export
- Dark medical-themed UI tuned for large displays and touch use

## Requirements
- Raspberry Pi 5
- Python 3.10+
- PyQt5
- PyQtGraph
- NumPy

## Installation
```bash
sudo apt update
sudo apt install python3-pyqt5 python3-pyqt5.qtopengl python3-pyqtgraph python3-numpy -y
pip3 install --user pyqtgraph numpy PyQt5
```

## Running on Raspberry Pi
```bash
export QT_QPA_PLATFORM=eglfs
python3 dashboard.py
```

For the official Raspberry Pi Touch Display, the app now defaults to a fullscreen 800x480 layout and uses EGLFS-friendly startup settings.

## Notes
- UDP packets are still received on port 5005.
- CSV files are written to ~/GaitAnalysis/data/.
