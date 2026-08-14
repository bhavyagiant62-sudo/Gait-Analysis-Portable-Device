import json
import socket
import threading

from PyQt5.QtCore import QThread, pyqtSignal

from config import UDP_BIND_ADDR, UDP_PORT, UDP_SOCKET_TIMEOUT_SEC, WIFI_CHECK_INTERVAL_SEC, WIFI_CHECK_TIMEOUT_SEC, WIFI_PROBE_HOST


class UDPReceiverThread(QThread):
    """Background thread that owns the UDP listener and forwards valid JSON packets."""

    packet_received = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    status_message = pyqtSignal(str)

    def __init__(self, port: int = UDP_PORT, parent=None):
        super().__init__(parent)
        self._port = port
        self._stop_event = threading.Event()
        self._sock = None

    def run(self):
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.settimeout(UDP_SOCKET_TIMEOUT_SEC)
            self._sock.bind((UDP_BIND_ADDR, self._port))
            self.status_message.emit(f"UDP listener bound on port {self._port}")
        except OSError as exc:
            self.error_occurred.emit(f"Failed to bind UDP socket: {exc}")
            return

        while not self._stop_event.is_set():
            try:
                raw_bytes, _addr = self._sock.recvfrom(1024)
            except socket.timeout:
                continue
            except OSError as exc:
                if not self._stop_event.is_set():
                    self.error_occurred.emit(f"UDP socket error: {exc}")
                break

            try:
                data = json.loads(raw_bytes.decode("utf-8"))
                if all(k in data for k in ("time", "roll", "pitch", "yaw")):
                    self.packet_received.emit(data)
                else:
                    self.error_occurred.emit("Packet missing required fields")
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                self.error_occurred.emit(f"Malformed packet ignored: {exc}")

        if self._sock:
            self._sock.close()

    def stop(self):
        self._stop_event.set()
        self.wait(2000)


class NetworkMonitorThread(QThread):
    """Background thread that checks Wi-Fi reachability without blocking the UI."""

    wifi_status_changed = pyqtSignal(bool)

    def __init__(self, interval_sec: float = WIFI_CHECK_INTERVAL_SEC, parent=None):
        super().__init__(parent)
        self._interval = interval_sec
        self._stop_event = threading.Event()

    def run(self):
        while not self._stop_event.is_set():
            connected = self._probe_connectivity()
            self.wifi_status_changed.emit(connected)
            self._stop_event.wait(self._interval)

    @staticmethod
    def _probe_connectivity() -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(WIFI_CHECK_TIMEOUT_SEC)
                s.connect(WIFI_PROBE_HOST)
            return True
        except OSError:
            return False

    def stop(self):
        self._stop_event.set()
        self.wait(2000)
