"""
Audio Stream Desktop Application - PyQt6 Version
Modern GUI with Qt for sleek Apple/Material-inspired design.
"""

import asyncio
import socket
import sys
import threading
import webbrowser
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QFrame, QInputDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QObject
from PyQt6.QtGui import QPixmap, QFont, QPalette, QColor, QCursor, QImage

try:
    import qrcode
    from PIL import Image
    HAS_QR = True
except ImportError:
    HAS_QR = False
    print("Warning: qrcode or pillow not installed. Run: pip install qrcode[pil]")


# Modern dark theme stylesheet
DARK_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #0f0f1a;
    color: #ffffff;
}

QLabel {
    color: #ffffff;
    background: transparent;
}

QLabel#subtitle {
    color: #6b7280;
}

QLabel#url {
    color: #00d4ff;
    font-weight: bold;
}

QLabel#status {
    color: #6b7280;
}

QFrame#qr_card {
    background-color: #1a1a2e;
    border: 1px solid #2d2d44;
    border-radius: 20px;
}

QFrame#instructions {
    background-color: #1a1a2e;
    border-radius: 15px;
}

QComboBox {
    background-color: #1a1a2e;
    color: #ffffff;
    border: 1px solid #2d2d44;
    border-radius: 10px;
    padding: 10px 15px;
    font-size: 13px;
    min-height: 20px;
}

QComboBox::drop-down {
    border: none;
    width: 30px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 8px solid #3b82f6;
    margin-right: 10px;
}

QComboBox QAbstractItemView {
    background-color: #1a1a2e;
    color: #ffffff;
    selection-background-color: #2d2d44;
    border: 1px solid #2d2d44;
    border-radius: 5px;
}

QPushButton#start_btn {
    background-color: #3b82f6;
    color: #ffffff;
    border: none;
    border-radius: 15px;
    font-size: 16px;
    font-weight: bold;
    padding: 15px;
    min-height: 25px;
}

QPushButton#start_btn:hover {
    background-color: #2563eb;
}

QPushButton#stop_btn {
    background-color: #ef4444;
    color: #ffffff;
    border: none;
    border-radius: 15px;
    font-size: 16px;
    font-weight: bold;
    padding: 15px;
    min-height: 25px;
}

QPushButton#stop_btn:hover {
    background-color: #dc2626;
}

QLabel#step_num {
    color: #3b82f6;
    font-weight: bold;
}

QLabel#step_text {
    color: #9ca3af;
}
"""


class SignalEmitter(QObject):
    """Helper class to emit signals from background threads."""
    update_status = pyqtSignal(str, str)  # status_text, dot_color
    server_started = pyqtSignal()
    server_error = pyqtSignal(str)  # error message


class AudioStreamApp(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Audio Stream")
        self.setFixedSize(450, 780)
        
        self.server_thread = None
        self.server_running = False
        self.loop = None
        self.devices = []
        
        self.signals = SignalEmitter()
        self.signals.update_status.connect(self._update_status_slot)
        self.signals.server_started.connect(self._on_server_started)
        self.signals.server_error.connect(self._on_server_error)
        
        self._starting_server = False  # Prevent double-click issues
        
        self._setup_ui()
        
    def _setup_ui(self):
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        
        # Main layout
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(0)
        
        # Header
        header_layout = QVBoxLayout()
        header_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # App icon emoji
        icon_label = QLabel("🎵")
        icon_label.setFont(QFont("Segoe UI Emoji", 36))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(icon_label)
        
        # Title
        title = QLabel("Audio Stream")
        title.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        title.setStyleSheet("color: #00d4ff;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(title)
        
        # Subtitle
        subtitle = QLabel("Stream PC audio to your devices")
        subtitle.setObjectName("subtitle")
        subtitle.setFont(QFont("Segoe UI", 12))
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(subtitle)
        
        main_layout.addLayout(header_layout)
        main_layout.addSpacing(20)
        
        # QR Code Card
        self.qr_card = QFrame()
        self.qr_card.setObjectName("qr_card")
        qr_layout = QVBoxLayout(self.qr_card)
        qr_layout.setContentsMargins(20, 15, 20, 15)
        
        self.qr_label = QLabel("Start server to generate QR code")
        self.qr_label.setObjectName("subtitle")
        self.qr_label.setFont(QFont("Segoe UI", 13))
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setMinimumHeight(200)
        qr_layout.addWidget(self.qr_label)
        
        main_layout.addWidget(self.qr_card)
        main_layout.addSpacing(10)
        
        # URL Display
        self.url_label = QLabel("")
        self.url_label.setObjectName("url")
        self.url_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.url_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.url_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.url_label.mousePressEvent = self._open_url
        main_layout.addWidget(self.url_label)
        main_layout.addSpacing(5)
        
        # Status indicator
        status_layout = QHBoxLayout()
        status_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.status_dot = QLabel("●")
        self.status_dot.setFont(QFont("Segoe UI", 12))
        self.status_dot.setStyleSheet("color: #6b7280;")
        status_layout.addWidget(self.status_dot)
        
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("status")
        self.status_label.setFont(QFont("Segoe UI", 13))
        status_layout.addWidget(self.status_label)
        
        main_layout.addLayout(status_layout)
        main_layout.addSpacing(15)
        
        # Device selector
        device_frame = QVBoxLayout()
        
        device_label = QLabel("Audio Source")
        device_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        device_label.setStyleSheet("color: #9ca3af;")
        device_frame.addWidget(device_label)
        device_frame.addSpacing(8)
        
        self.device_combo = QComboBox()
        self.device_combo.addItem("Loading devices...")
        device_frame.addWidget(self.device_combo)
        
        main_layout.addLayout(device_frame)
        self._populate_devices()
        main_layout.addSpacing(20)
        
        # Start/Stop button
        self.btn = QPushButton("▶  Start Server")
        self.btn.setObjectName("start_btn")
        self.btn.clicked.connect(self._toggle_server)
        main_layout.addWidget(self.btn)
        main_layout.addSpacing(20)
        
        # Instructions
        instructions_frame = QFrame()
        instructions_frame.setObjectName("instructions")
        instr_layout = QVBoxLayout(instructions_frame)
        instr_layout.setContentsMargins(20, 15, 20, 15)
        instr_layout.setSpacing(10)
        
        steps = [
            ("1", "Select your audio device"),
            ("2", "Click Start Server"),
            ("3", "Scan QR with your phone")
        ]
        
        for num, text in steps:
            step_layout = QHBoxLayout()
            
            num_label = QLabel(num)
            num_label.setObjectName("step_num")
            num_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
            num_label.setFixedWidth(25)
            step_layout.addWidget(num_label)
            
            text_label = QLabel(text)
            text_label.setObjectName("step_text")
            text_label.setFont(QFont("Segoe UI", 13))
            step_layout.addWidget(text_label)
            step_layout.addStretch()
            
            instr_layout.addLayout(step_layout)
        
        main_layout.addWidget(instructions_frame)
        main_layout.addStretch()
    
    def _populate_devices(self):
        """Populate device dropdown with available audio input devices."""
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            input_devices = []
            default_idx = 0
            
            for i, d in enumerate(devices):
                if d['max_input_channels'] > 0:
                    name = d['name']
                    if 'cable output' in name.lower():
                        name = f"⭐ {name}"
                        default_idx = len(input_devices)
                    elif 'stereo mix' in name.lower() or 'loopback' in name.lower():
                        name = f"⭐ {name}"
                        if default_idx == 0:
                            default_idx = len(input_devices)
                    input_devices.append((i, name))
            
            self.devices = input_devices
            self.device_combo.clear()
            for _, name in input_devices:
                self.device_combo.addItem(name)
            
            if input_devices:
                self.device_combo.setCurrentIndex(default_idx)
                
        except Exception as e:
            print(f"Error listing devices: {e}")
            self.devices = []
    
    def _get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    def _generate_qr(self, url):
        if not HAS_QR:
            return None
            
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=2
        )
        qr.add_data(url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="#00d4ff", back_color="#1a1a2e")
        return img
    
    def _pil_to_pixmap(self, pil_image):
        """Convert PIL Image to QPixmap."""
        pil_image = pil_image.convert("RGB")
        data = pil_image.tobytes("raw", "RGB")
        qimage = QImage(data, pil_image.width, pil_image.height, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(qimage)
    
    def _update_qr_display(self, url):
        img = self._generate_qr(url)
        if img:
            img = img.resize((180, 180), Image.Resampling.LANCZOS)
            pixmap = self._pil_to_pixmap(img)
            self.qr_label.setPixmap(pixmap)
            self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.url_label.setText(url)
    
    def _open_url(self, event=None):
        url = self.url_label.text()
        if url.startswith("http"):
            webbrowser.open(url)
    
    def _is_port_available(self, port=8080):
        """Check if port is available before attempting to start server."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('0.0.0.0', port))
                return True
        except OSError:
            return False
    
    def _run_server(self):
        try:
            import server
            
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            from aiohttp import web
            
            app = web.Application()
            app.on_startup.append(server.on_startup)
            app.on_shutdown.append(server.on_shutdown)
            app.router.add_get("/", server.index)
            app.router.add_post("/offer", server.offer)
            
            runner = web.AppRunner(app)
            self.loop.run_until_complete(runner.setup())
            
            site = web.TCPSite(runner, "0.0.0.0", 8080)
            self.loop.run_until_complete(site.start())
            
            self.server_running = True
            self.signals.server_started.emit()
            
            try:
                self.loop.run_forever()
            except:
                pass
            finally:
                self.loop.run_until_complete(runner.cleanup())
                
        except OSError as e:
            if e.errno == 10048:  # Port already in use on Windows
                self.signals.server_error.emit("Port 8080 is already in use. Close other instances first.")
            else:
                self.signals.server_error.emit(f"Server error: {e}")
        except Exception as e:
            self.signals.server_error.emit(f"Failed to start server: {e}")
    
    def _update_status_slot(self, text, color):
        """Thread-safe status update slot."""
        self.status_label.setText(text)
        self.status_dot.setStyleSheet(f"color: {color};")
    
    def _on_server_started(self):
        """Called when server has started."""
        self._starting_server = False
        self.status_label.setText("Server running")
        self.status_dot.setStyleSheet("color: #22c55e;")
    
    def _on_server_error(self, error_msg):
        """Called when server fails to start."""
        self._starting_server = False
        self.server_running = False
        self.status_label.setText("Error")
        self.status_dot.setStyleSheet("color: #ef4444;")
        self.btn.setText("▶  Start Server")
        self.btn.setObjectName("start_btn")
        self.btn.setStyle(self.btn.style())
        self.url_label.setText("")
        self.qr_label.setPixmap(QPixmap())
        self.qr_label.setText("Start server to generate QR code")
        QMessageBox.warning(self, "Server Error", error_msg)
    
    def _start_server(self):
        # Prevent double-click issues
        if self._starting_server or self.server_running:
            return
        
        # Check if port is available first
        if not self._is_port_available(8080):
            QMessageBox.warning(
                self, 
                "Port In Use", 
                "Port 8080 is already in use.\n\n"
                "Please close any other Audio Stream instances or \n"
                "applications using port 8080 and try again."
            )
            return
        
        self._starting_server = True
        self.status_label.setText("Starting...")
        self.status_dot.setStyleSheet("color: #f59e0b;")
        
        ip = self._get_local_ip()
        url = f"http://{ip}:8080"
        self._update_qr_display(url)
        
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        
        self.btn.setText("⬛  Stop Server")
        self.btn.setObjectName("stop_btn")
        self.btn.setStyle(self.btn.style())  # Force style refresh
        
    def _stop_server(self):
        self.status_label.setText("Stopping...")
        self.status_dot.setStyleSheet("color: #f59e0b;")
        
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)
            
        self.server_running = False
        self.btn.setText("▶  Start Server")
        self.btn.setObjectName("start_btn")
        self.btn.setStyle(self.btn.style())  # Force style refresh
        
        self.status_label.setText("Ready")
        self.status_dot.setStyleSheet("color: #6b7280;")
        self.url_label.setText("")
        self.qr_label.setPixmap(QPixmap())
        self.qr_label.setText("Start server to generate QR code")
        
    def _toggle_server(self):
        if self.server_running:
            self._stop_server()
        else:
            self._start_server()
    
    def closeEvent(self, event):
        """Clean up on window close."""
        if self.server_running:
            self._stop_server()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLESHEET)
    
    window = AudioStreamApp()
    window.show()
    
    sys.exit(app.exec())
