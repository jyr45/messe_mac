"""
Servidor v3 para macOS (Roles: Laptop y Teléfono)
Versión adaptada para macOS: Sin dependencias de ctypes (Windows) y sin PowerToys OCR.
"""

import socket
import threading
import time
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk, font as tkfont
import pytesseract
from PIL import Image, ImageTk
import io
import requests
import json
import os

# Configuración
TCP_PORT = 5000
UDP_PORT = 5001
TCP_PORT_IMAGE = 5005
BEACON_INTERVAL = 2
FIRESTORE_URL = "https://firestore.googleapis.com/v1/projects/messe-fcff9/databases/(default)/documents/auth/master"
CONFIG_FILE = "config_server.json"

# Configuración de Tesseract para Mac
# Si se instala con 'brew install tesseract', usualmente no requiere ruta manual si está en el PATH.
# De lo contrario, descomentar y ajustar:
# pytesseract.pytesseract.tesseract_cmd = '/opt/homebrew/bin/tesseract'

# ─── Paleta de colores ───────────────────────────────────────────────────────
BG        = "#1a1a2e"
BG2       = "#16213e"
BG3       = "#0f3460"
ACCENT    = "#e94560"
ACCENT2   = "#0f7ea8"
TEXT      = "#eaeaea"
TEXT_DIM  = "#888aaa"
BTN_BG    = "#0f3460"
BTN_HOV   = "#e94560"
GREEN     = "#2ecc71"
ORANGE    = "#f39c12"

class StyledButton(tk.Label):
    def __init__(self, master, text, command=None, bg=BTN_BG, fg=TEXT, font=("Arial", 10, "bold"), pady=6, padx=8, **kwargs):
        self.state = kwargs.get('state', tk.NORMAL)
        # Clean kwargs for Label
        label_kwargs = {k: v for k, v in kwargs.items() if k not in ['activebackground', 'activeforeground', 'command', 'relief', 'bd', 'cursor', 'pady', 'padx', 'state', 'wraplength', 'justify']}
        
        super().__init__(master, text=text, bg=bg, fg=fg, font=font, pady=pady, padx=padx, cursor="hand2", relief=tk.FLAT, **label_kwargs)
        
        self.command = command
        self.default_bg = bg
        self.active_bg = kwargs.get('activebackground', BTN_HOV)
        self.default_fg = fg
        self.wraplength = kwargs.get('wraplength', 0)
        self.justify = kwargs.get('justify', tk.CENTER)
        
        if self.wraplength:
            self.config(wraplength=self.wraplength, justify=self.justify)
            
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        
        if self.state == tk.DISABLED:
            self.config(state=tk.DISABLED)

    def _on_click(self, event=None):
        if self.state == tk.NORMAL and self.command:
            self.command()

    def _on_enter(self, event=None):
        if self.state == tk.NORMAL:
            super().config(bg=self.active_bg)

    def _on_leave(self, event=None):
        if self.state == tk.NORMAL:
            super().config(bg=self.default_bg)

    def config(self, **kwargs):
        if 'state' in kwargs:
            self.state = kwargs['state']
            if self.state == tk.DISABLED:
                super().config(fg=TEXT_DIM, cursor="arrow")
            else:
                super().config(fg=self.default_fg, cursor="hand2")
            del kwargs['state']
        
        if 'bg' in kwargs:
            self.default_bg = kwargs['bg']
        if 'fg' in kwargs:
            self.default_fg = kwargs['fg']
            
        super().config(**kwargs)

    def configure(self, **kwargs):
        self.config(**kwargs)

class QuickButton(StyledButton):
    def __init__(self, master, text, command, display_override=None, **kwargs):
        display = display_override if display_override else (
            text if len(text) <= 22 else text[:20] + "…"
        )
        super().__init__(
            master,
            text=display,
            command=command,
            bg=BTN_BG,
            fg=TEXT,
            activebackground=BTN_HOV,
            font=("Arial", 10, "bold"),
            padx=8,
            pady=6,
            wraplength=220,
            justify="left",
            **kwargs
        )

class ChatServerV3Mac:
    def __init__(self):
        self.running = True
        self.auth_pin = None
        self.hostname = socket.gethostname()
        self.ip_address = self.get_local_ip()
        self.discovered_clients = {}
        
        # Variables para roles
        self.laptop_target = None 
        self.phone_target = None  
        
        self.stay_on_top = True
        self.predefined_messages = self.load_config()

        self.root = tk.Tk()
        self.root.withdraw()

        if not self.validate_server_access():
            self.root.destroy()
            return

        self.root.deiconify()
        self.root.title(f"Servidor v3 (Mac) — {self.hostname}")
        self.root.geometry("350x750+10+10")
        self.root.configure(bg=BG)
        self.root.attributes('-topmost', True)
        self.root.resizable(False, True)
        
        self.laptop_target = tk.StringVar(value="")
        self.phone_target = tk.StringVar(value="")

        self.setup_ui()
        self.bind_hotkeys()

        threading.Thread(target=self.run_server_beacon, daemon=True).start()
        threading.Thread(target=self.discover_clients, daemon=True).start()
        threading.Thread(target=self.cleanup_clients, daemon=True).start()
        threading.Thread(target=self.listen_for_images, daemon=True).start()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except:
                return []
        return ["¡Hola!", "¿Cómo vas?", "Prueba de sistema"]

    def save_config(self):
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.predefined_messages, f)
        except:
            pass

    def validate_server_access(self):
        while True:
            pin = simpledialog.askstring("Seguridad", "Introduce tu PIN de acceso:", show='*')
            if pin is None: return False
            try:
                response = requests.get(FIRESTORE_URL, timeout=5)
                if response.status_code == 200:
                    stored_pin = response.json().get('fields', {}).get('pin', {}).get('stringValue')
                    if stored_pin == pin:
                        self.auth_pin = pin
                        return True
                    else:
                        messagebox.showerror("Error", "PIN Incorrecto.")
                else:
                    messagebox.showerror("Error", "Error Firebase.")
                    return False
            except:
                messagebox.showerror("Error", "Error conexión.")
                return False

    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except: return "127.0.0.1"

    def toggle_topmost(self):
        self.stay_on_top = not self.stay_on_top
        self.root.attributes('-topmost', self.stay_on_top)
        if self.stay_on_top:
            self.pin_btn.config(text="📌 Siempre al frente: ON", bg="#1a5c2e", fg=GREEN)
        else:
            self.pin_btn.config(text="📌 Siempre al frente: OFF", bg="#3a1a1a", fg=ACCENT)

    def setup_ui(self):
        hdr = tk.Frame(self.root, bg=BG3, height=42)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text="📡  SERVIDOR v3 (Mac)", bg=BG3, fg=ACCENT, font=("Arial", 11, "bold")).pack(side=tk.LEFT, padx=12, pady=8)
        tk.Label(hdr, text=self.hostname, bg=BG3, fg=TEXT_DIM, font=("Arial", 9)).pack(side=tk.RIGHT, padx=12)

        pin_bar = tk.Frame(self.root, bg="#1a5c2e")
        pin_bar.pack(fill=tk.X)
        self.pin_btn = StyledButton(pin_bar, text="📌 Siempre al frente: ON", command=self.toggle_topmost, bg="#1a5c2e", fg=GREEN, font=("Arial", 8, "bold"), relief=tk.FLAT, bd=0, cursor="hand2", pady=4)
        self.pin_btn.pack(fill=tk.X)

        # ── Clientes ─────────────────────────────────────────────────────
        sec1 = tk.LabelFrame(self.root, text="  Asignación de Roles  ", bg=BG, fg=TEXT_DIM, font=("Arial", 8), bd=1, relief=tk.FLAT, highlightbackground=BG3, highlightthickness=1)
        sec1.pack(fill=tk.X, padx=10, pady=(8, 4))

        self.clients_frame = tk.Frame(sec1, bg=BG)
        self.clients_frame.pack(fill=tk.X, padx=4, pady=4)
        tk.Label(self.clients_frame, text="Esperando clientes…", bg=BG, fg=TEXT_DIM, font=("Arial", 9)).pack()

        # ── Respuestas rápidas ────────────────────────────────────────────
        sec2 = tk.LabelFrame(self.root, text="  Respuestas rápidas  ", bg=BG, fg=TEXT_DIM, font=("Arial", 8), bd=1, relief=tk.FLAT, highlightbackground=BG3, highlightthickness=1)
        sec2.pack(fill=tk.X, padx=10, pady=4)

        self.quick_btns_frame = tk.Frame(sec2, bg=BG)
        self.quick_btns_frame.pack(fill=tk.X, padx=4, pady=4)
        self.rebuild_quick_buttons()

        row = tk.Frame(sec2, bg=BG)
        row.pack(fill=tk.X, padx=4, pady=(2, 6))
        self.new_quick_entry = tk.Entry(row, bg=BG2, fg=TEXT, insertbackground=TEXT, font=("Arial", 9), relief=tk.FLAT, highlightthickness=1, highlightbackground=BG3)
        self.new_quick_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        self.new_quick_entry.bind("<Return>", lambda e: self.add_predefined())
        StyledButton(row, text="+", command=self.add_predefined, bg=GREEN, fg="white", font=("Arial", 9, "bold"), relief=tk.FLAT, bd=0, cursor="hand2", padx=8).pack(side=tk.LEFT, padx=(4, 0))
        StyledButton(row, text="−", command=self.del_last_predefined, bg=ACCENT, fg="white", font=("Arial", 9, "bold"), relief=tk.FLAT, bd=0, cursor="hand2", padx=8).pack(side=tk.LEFT, padx=(2, 0))

        # ── Redactar ──────────────────────────────────────────────────────
        sec3 = tk.LabelFrame(self.root, text="  Enviar al Teléfono  ", bg=BG, fg=TEXT_DIM, font=("Arial", 8), bd=1, relief=tk.FLAT, highlightbackground=BG3, highlightthickness=1)
        sec3.pack(fill=tk.X, padx=10, pady=4)
        self.me = tk.Entry(sec3, bg=BG2, fg=TEXT, insertbackground=TEXT, font=("Arial", 11), relief=tk.FLAT, highlightthickness=1, highlightbackground=BG3)
        self.me.pack(fill=tk.X, padx=6, pady=(6, 4), ipady=5)
        self.me.bind("<Return>", lambda e: self.send_to_selected())
        send_btn = StyledButton(sec3, text="▶  ENVIAR AL TELÉFONO", command=self.send_to_selected, bg=GREEN, fg="white", font=("Arial", 10, "bold"), relief=tk.FLAT, bd=0, cursor="hand2", pady=7)
        send_btn.pack(fill=tk.X, padx=6, pady=(0, 8))

        # ── Herramientas ──────────────────────────────────────────────────
        sec4 = tk.LabelFrame(self.root, text="  Captura (Laptop)  ", bg=BG, fg=TEXT_DIM, font=("Arial", 8), bd=1, relief=tk.FLAT, highlightbackground=BG3, highlightthickness=1)
        sec4.pack(fill=tk.X, padx=10, pady=(4, 10))
        ocr_btn = StyledButton(sec4, text="📷  Capturar pantalla de Laptop", command=self.request_screenshot_and_ocr, bg=ACCENT2, fg="white", font=("Arial", 9, "bold"), relief=tk.FLAT, bd=0, cursor="hand2", pady=8)
        ocr_btn.pack(fill=tk.X, padx=6, pady=6)

    def bind_hotkeys(self):
        fkeys = ["<F1>", "<F2>", "<F3>", "<F4>"]
        for i, fkey in enumerate(fkeys):
            self.root.bind(fkey, lambda e, n=i: self._hotkey_send(n))

    def _hotkey_send(self, index):
        if index < len(self.predefined_messages):
            self.send_quick(self.predefined_messages[index])

    def rebuild_quick_buttons(self):
        for w in self.quick_btns_frame.winfo_children(): w.destroy()
        fkey_labels = ["F1", "F2", "F3", "F4"]
        for i, msg in enumerate(self.predefined_messages):
            fkey_tag = f"[{fkey_labels[i]}]  " if i < len(fkey_labels) else ""
            btn = QuickButton(self.quick_btns_frame, text=msg, display_override=fkey_tag + (msg if len(msg) <= 20 else msg[:18] + "…"), command=lambda txt=msg: self.send_quick(txt))
            btn.pack(fill=tk.X, pady=2)

    def send_quick(self, text):
        target_h = self.phone_target.get()
        if not target_h or target_h not in self.discovered_clients:
            messagebox.showwarning("Sin Teléfono", "Selecciona qué dispositivo es el 'Teléfono'.")
            return
        ip = self.discovered_clients[target_h][0]
        threading.Thread(target=self.send_tcp_message, args=(ip, text), daemon=True).start()

    def add_predefined(self):
        msg = self.new_quick_entry.get().strip()
        if msg and msg not in self.predefined_messages:
            self.predefined_messages.append(msg)
            self.save_config(); self.rebuild_quick_buttons()
            self.new_quick_entry.delete(0, tk.END)

    def del_last_predefined(self):
        if self.predefined_messages:
            self.predefined_messages.pop()
            self.save_config(); self.rebuild_quick_buttons()

    def run_server_beacon(self):
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        beacon = f"SERVER_ALIVE|{self.hostname}|{self.ip_address}".encode('utf-8')
        while self.running:
            try: udp.sendto(beacon, ('<broadcast>', UDP_PORT)); time.sleep(BEACON_INTERVAL)
            except: time.sleep(BEACON_INTERVAL)

    def discover_clients(self):
        u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        u.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try: u.bind(('', UDP_PORT))
        except: return
        while self.running:
            try:
                data, addr = u.recvfrom(1024)
                m = data.decode('utf-8')
                if m.startswith("CLIENT_ALIVE"):
                    p = m.split('|')
                    h, ip = p[1], p[2]
                    is_new = h not in self.discovered_clients
                    self.discovered_clients[h] = (ip, time.time())
                    if is_new: self.root.after(0, self.update_client_list)
                    else: self.discovered_clients[h] = (ip, time.time())
            except: pass

    def update_client_list(self):
        for w in self.clients_frame.winfo_children(): w.destroy()
        if not self.discovered_clients:
            tk.Label(self.clients_frame, text="Esperando clientes…", bg=BG, fg=TEXT_DIM, font=("Arial", 9)).pack()
            return
        
        header = tk.Frame(self.clients_frame, bg=BG)
        header.pack(fill=tk.X)
        tk.Label(header, text="Dispositivo", bg=BG, fg=TEXT_DIM, font=("Arial", 8, "bold"), width=12, anchor="w").pack(side=tk.LEFT, padx=2)
        tk.Label(header, text="💻 Lap", bg=BG, fg=TEXT_DIM, font=("Arial", 8, "bold"), width=6).pack(side=tk.LEFT)
        tk.Label(header, text="📱 Tel", bg=BG, fg=TEXT_DIM, font=("Arial", 8, "bold"), width=6).pack(side=tk.LEFT)

        for h in sorted(self.discovered_clients.keys()):
            row = tk.Frame(self.clients_frame, bg=BG2, pady=2)
            row.pack(fill=tk.X, pady=1)
            
            info_frame = tk.Frame(row, bg=BG2)
            info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
            tk.Label(info_frame, text=h, bg=BG2, fg=TEXT, font=("Arial", 9, "bold"), anchor="w").pack(fill=tk.X)
            tk.Label(info_frame, text=self.discovered_clients[h][0], bg=BG2, fg=TEXT_DIM, font=("Arial", 7), anchor="w").pack(fill=tk.X)
            
            tk.Radiobutton(row, variable=self.laptop_target, value=h, bg=BG2, activebackground=BG2, selectcolor=BG3).pack(side=tk.LEFT, padx=10)
            tk.Radiobutton(row, variable=self.phone_target, value=h, bg=BG2, activebackground=BG2, selectcolor=BG3).pack(side=tk.LEFT, padx=10)
            
            tk.Label(row, text="●", bg=BG2, fg=GREEN, font=("Arial", 8)).pack(side=tk.RIGHT, padx=4)

    def cleanup_clients(self):
        while self.running:
            n = time.time()
            tr = [h for h, (ip, last) in self.discovered_clients.items() if n - last > 12]
            if tr:
                for h in tr:
                    if self.laptop_target.get() == h: self.laptop_target.set("")
                    if self.phone_target.get() == h: self.phone_target.set("")
                    del self.discovered_clients[h]
                self.root.after(0, self.update_client_list)
            time.sleep(5)

    def send_to_selected(self):
        msg = self.me.get().strip()
        if not msg: return
        target_h = self.phone_target.get()
        if not target_h or target_h not in self.discovered_clients:
            messagebox.showwarning("Sin Teléfono", "Selecciona qué dispositivo es el 'Teléfono'.")
            return
        ip = self.discovered_clients[target_h][0]
        threading.Thread(target=self.send_tcp_message, args=(ip, msg), daemon=True).start()

    def send_tcp_message(self, ip, message):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3); s.connect((ip, TCP_PORT))
            s.sendall(f"PIN:{self.auth_pin}|{message}".encode('utf-8')); s.close()
        except: pass

    def request_screenshot_and_ocr(self):
        target_h = self.laptop_target.get()
        if not target_h or target_h not in self.discovered_clients:
            messagebox.showwarning("Sin Laptop", "Selecciona qué dispositivo es la 'Laptop'.")
            return
        ip = self.discovered_clients[target_h][0]
        threading.Thread(target=self.send_tcp_message, args=(ip, "CMD_REQUEST_SCREENSHOT"), daemon=True).start()

    def listen_for_images(self):
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server_sock.bind(('0.0.0.0', TCP_PORT_IMAGE)); server_sock.listen(5)
            while self.running:
                conn, addr = server_sock.accept()
                threading.Thread(target=self.handle_image, args=(conn,), daemon=True).start()
        except Exception as e: print(f"Error listener imagen: {e}")

    def handle_image(self, conn):
        try:
            raw_msglen = self.recvall(conn, 8)
            if not raw_msglen: return
            msglen = int.from_bytes(raw_msglen, byteorder='big')
            data = self.recvall(conn, msglen)
            if not data: return
            prefix = f"PIN:{self.auth_pin}|".encode('utf-8')
            if data.startswith(prefix):
                img_data = data[len(prefix):]
                img = Image.open(io.BytesIO(img_data))
                self.root.after(0, self.show_image_viewer, img)
        except: pass
        finally: conn.close()

    def show_image_viewer(self, pil_img):
        viewer = tk.Toplevel(self.root)
        viewer.title("Captura — selecciona área para OCR")
        viewer.configure(bg=BG); viewer.attributes('-topmost', True)
        sw, sh = viewer.winfo_screenwidth(), viewer.winfo_screenheight()
        display_img = pil_img.copy()
        max_w, max_h = int(sw * 0.88), int(sh * 0.82)
        if pil_img.width > max_w or pil_img.height > max_h: display_img.thumbnail((max_w, max_h), Image.LANCZOS)
        tk_img = ImageTk.PhotoImage(display_img)
        toolbar = tk.Frame(viewer, bg=BG3, height=40); toolbar.pack(fill=tk.X); toolbar.pack_propagate(False)
        tk.Label(toolbar, text="Arrastra para seleccionar área → OCR", bg=BG3, fg=TEXT_DIM, font=("Arial", 9)).pack(side=tk.LEFT, padx=10)
        
        canvas = tk.Canvas(viewer, width=display_img.width, height=display_img.height, bg=BG, highlightthickness=0, cursor="crosshair")
        canvas.pack(); canvas.create_image(0, 0, anchor=tk.NW, image=tk_img); canvas.image = tk_img
        bottom = tk.Frame(viewer, bg=BG2); bottom.pack(fill=tk.X)
        ocr_label = tk.Label(bottom, text="Selecciona un área para extraer texto…", bg=BG2, fg=TEXT_DIM, font=("Arial", 9), anchor="w", padx=10)
        ocr_label.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=6)
        copy_btn = StyledButton(bottom, text="📋 Copiar", bg=BTN_BG, fg=TEXT, font=("Arial", 9), relief=tk.FLAT, bd=0, cursor="hand2", padx=8, pady=4, state=tk.DISABLED)
        copy_btn.pack(side=tk.RIGHT, padx=6, pady=4)
        send_ocr_btn = StyledButton(bottom, text="▶ Enviar al Teléfono", bg=GREEN, fg="white", font=("Arial", 9, "bold"), relief=tk.FLAT, bd=0, cursor="hand2", padx=8, pady=4, state=tk.DISABLED)
        send_ocr_btn.pack(side=tk.RIGHT, padx=2, pady=4)
        viewer.rect = None; viewer.start_x = viewer.start_y = None; self._last_ocr_text = ""
        def on_press(e):
            viewer.start_x, viewer.start_y = e.x, e.y
            if viewer.rect: canvas.delete(viewer.rect)
            viewer.rect = canvas.create_rectangle(e.x, e.y, e.x, e.y, outline=ACCENT, width=2, dash=(4, 2))
        def on_move(e):
            if viewer.rect: canvas.coords(viewer.rect, viewer.start_x, viewer.start_y, e.x, e.y)
        def on_release(e):
            sx, sy = pil_img.width / display_img.width, pil_img.height / display_img.height
            x1, y1 = min(viewer.start_x, e.x) * sx, min(viewer.start_y, e.y) * sy
            x2, y2 = max(viewer.start_x, e.x) * sx, max(viewer.start_y, e.y) * sy
            if (x2 - x1) > 8 and (y2 - y1) > 8:
                crop = pil_img.crop((x1, y1, x2, y2)); ocr_label.config(text="Procesando OCR…", fg=ORANGE)
                threading.Thread(target=self.process_roi_ocr, args=(crop, ocr_label, copy_btn, send_ocr_btn), daemon=True).start()
        canvas.bind("<ButtonPress-1>", on_press); canvas.bind("<B1-Motion>", on_move); canvas.bind("<ButtonRelease-1>", on_release)
        def do_copy():
            if self._last_ocr_text: self.root.clipboard_clear(); self.root.clipboard_append(self._last_ocr_text); self.root.update()
            copy_btn.config(text="✓ Copiado!", bg=GREEN); self.root.after(1500, lambda: copy_btn.config(text="📋 Copiar", bg=BTN_BG))
        def do_send():
            if self._last_ocr_text: self.me.delete(0, tk.END); self.me.insert(0, self._last_ocr_text[:200]); viewer.destroy()
        copy_btn.config(command=do_copy); send_ocr_btn.config(command=do_send)

    def process_roi_ocr(self, crop_img, label_widget, copy_btn, send_btn):
        try:
            text = pytesseract.image_to_string(crop_img).strip()
            self._last_ocr_text = text
            if text:
                display_text = text if len(text) <= 80 else text[:77] + "…"
                label_widget.after(0, lambda: (label_widget.config(text=f'"{display_text}"', fg=TEXT), copy_btn.config(state=tk.NORMAL), send_btn.config(state=tk.NORMAL)))
            else: label_widget.after(0, lambda: label_widget.config(text="No se detectó texto en esa área.", fg=ACCENT))
        except Exception as e: label_widget.after(0, lambda: label_widget.config(text=f"Error OCR: {e}", fg=ACCENT))

    def recvall(self, sock, n):
        data = bytearray()
        while len(data) < n:
            packet = sock.recv(n - len(data))
            if not packet: return None
            data.extend(packet)
        return data

    def run(self):
        self.root.mainloop()
        self.running = False

if __name__ == "__main__":
    server = ChatServerV3Mac()
    if hasattr(server, 'root') and server.root.winfo_exists(): server.run()
