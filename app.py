"""
Audio Stream Desktop Application
Modern GUI with CustomTkinter for sleek Apple/Material-inspired design.
"""

import asyncio
import socket
import sys
import threading
import webbrowser
from pathlib import Path

import customtkinter as ctk

try:
    import qrcode
    from PIL import Image, ImageTk
    HAS_QR = True
except ImportError:
    HAS_QR = False
    print("Warning: qrcode or pillow not installed. Run: pip install qrcode[pil]")

# Theme configuration
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class AudioStreamApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Audio Stream")
        self.geometry("450x780")
        self.resizable(False, False)
        
        # Modern dark gradient background
        self.configure(fg_color="#0f0f1a")
        
        self.server_thread = None
        self.server_running = False
        self.loop = None
        self.devices = []
        
        self._setup_ui()
        
    def _setup_ui(self):
        # Main container with padding
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=30, pady=30)
        
        # Header
        header_frame = ctk.CTkFrame(container, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 20))
        
        # App icon/emoji
        icon_label = ctk.CTkLabel(
            header_frame,
            text="🎵",
            font=ctk.CTkFont(size=48)
        )
        icon_label.pack()
        
        # Title with gradient effect (using multiple colors)
        title = ctk.CTkLabel(
            header_frame,
            text="Audio Stream",
            font=ctk.CTkFont(family="Segoe UI", size=32, weight="bold"),
            text_color="#00d4ff"
        )
        title.pack(pady=(10, 5))
        
        subtitle = ctk.CTkLabel(
            header_frame,
            text="Stream PC audio to your devices",
            font=ctk.CTkFont(size=14),
            text_color="#6b7280"
        )
        subtitle.pack()
        
        # QR Code Card
        self.qr_card = ctk.CTkFrame(
            container,
            fg_color="#1a1a2e",
            corner_radius=20,
            border_width=1,
            border_color="#2d2d44"
        )
        self.qr_card.pack(fill="x", pady=20)
        
        self.qr_label = ctk.CTkLabel(
            self.qr_card,
            text="Start server to generate QR code",
            font=ctk.CTkFont(size=13),
            text_color="#6b7280",
            height=200
        )
        self.qr_label.pack(pady=15, padx=20)
        
        # URL Display
        self.url_var = ctk.StringVar(value="")
        self.url_label = ctk.CTkLabel(
            container,
            textvariable=self.url_var,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#00d4ff",
            cursor="hand2"
        )
        self.url_label.pack(pady=(0, 10))
        self.url_label.bind("<Button-1>", self._open_url)
        
        # Status indicator
        self.status_frame = ctk.CTkFrame(container, fg_color="transparent")
        self.status_frame.pack(pady=5)
        
        self.status_dot = ctk.CTkLabel(
            self.status_frame,
            text="●",
            font=ctk.CTkFont(size=12),
            text_color="#6b7280"
        )
        self.status_dot.pack(side="left", padx=(0, 5))
        
        self.status_var = ctk.StringVar(value="Ready")
        self.status_label = ctk.CTkLabel(
            self.status_frame,
            textvariable=self.status_var,
            font=ctk.CTkFont(size=13),
            text_color="#6b7280"
        )
        self.status_label.pack(side="left")
        
        # Device selector
        device_frame = ctk.CTkFrame(container, fg_color="transparent")
        device_frame.pack(fill="x", pady=15)
        
        device_label = ctk.CTkLabel(
            device_frame,
            text="Audio Source",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#9ca3af"
        )
        device_label.pack(anchor="w", pady=(0, 8))
        
        self.device_var = ctk.StringVar()
        self.device_combo = ctk.CTkComboBox(
            device_frame,
            variable=self.device_var,
            values=["Loading devices..."],
            width=400,
            height=40,
            corner_radius=10,
            border_width=1,
            border_color="#2d2d44",
            button_color="#3b82f6",
            button_hover_color="#2563eb",
            dropdown_fg_color="#1a1a2e",
            dropdown_hover_color="#2d2d44",
            font=ctk.CTkFont(size=13)
        )
        self.device_combo.pack(fill="x")
        self._populate_devices()
        
        # Start/Stop button
        self.btn = ctk.CTkButton(
            container,
            text="▶  Start Server",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=55,
            corner_radius=15,
            fg_color="#3b82f6",
            hover_color="#2563eb",
            command=self._toggle_server
        )
        self.btn.pack(fill="x", pady=20)
        
        # Instructions
        instructions_frame = ctk.CTkFrame(
            container,
            fg_color="#1a1a2e",
            corner_radius=15
        )
        instructions_frame.pack(fill="x", pady=(10, 0))
        
        steps = [
            ("1", "Select your audio device"),
            ("2", "Click Start Server"),
            ("3", "Scan QR with your phone")
        ]
        
        for num, text in steps:
            step_frame = ctk.CTkFrame(instructions_frame, fg_color="transparent")
            step_frame.pack(fill="x", padx=20, pady=10)
            
            num_label = ctk.CTkLabel(
                step_frame,
                text=num,
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color="#3b82f6",
                width=25
            )
            num_label.pack(side="left")
            
            text_label = ctk.CTkLabel(
                step_frame,
                text=text,
                font=ctk.CTkFont(size=13),
                text_color="#9ca3af"
            )
            text_label.pack(side="left", padx=10)
    
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
            device_names = [d[1] for d in input_devices]
            self.device_combo.configure(values=device_names)
            if device_names:
                self.device_combo.set(device_names[default_idx])
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
    
    def _update_qr_display(self, url):
        img = self._generate_qr(url)
        if img:
            img = img.resize((180, 180), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self.qr_label.configure(image=photo, text="")
            self.qr_label.image = photo
        
        self.url_var.set(url)
        
    def _open_url(self, event=None):
        url = self.url_var.get()
        if url.startswith("http"):
            webbrowser.open(url)
    
    def _run_server(self):
        # Direct import works in both dev mode and bundled EXE
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
        self.after(0, self._update_running_state)
        
        try:
            self.loop.run_forever()
        except:
            pass
        finally:
            self.loop.run_until_complete(runner.cleanup())
    
    def _update_running_state(self):
        self.status_var.set("Server running")
        self.status_dot.configure(text_color="#22c55e")
        
    def _start_server(self):
        self.status_var.set("Starting...")
        self.status_dot.configure(text_color="#f59e0b")
        
        ip = self._get_local_ip()
        url = f"http://{ip}:8080"
        self._update_qr_display(url)
        
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        
        self.btn.configure(
            text="⬛  Stop Server",
            fg_color="#ef4444",
            hover_color="#dc2626"
        )
        
    def _stop_server(self):
        self.status_var.set("Stopping...")
        self.status_dot.configure(text_color="#f59e0b")
        
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)
            
        self.server_running = False
        self.btn.configure(
            text="▶  Start Server",
            fg_color="#3b82f6",
            hover_color="#2563eb"
        )
        self.status_var.set("Ready")
        self.status_dot.configure(text_color="#6b7280")
        self.url_var.set("")
        self.qr_label.configure(image="", text="Start server to generate QR code")
        
    def _toggle_server(self):
        if self.server_running:
            self._stop_server()
        else:
            self._start_server()


if __name__ == "__main__":
    app = AudioStreamApp()
    app.mainloop()
