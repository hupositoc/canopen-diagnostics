"""CANopen SDO poller and SSI serial logger (tkinter, Kvaser canlib, pyserial).

Reads identity objects once, polls communication objects in a loop and records
SSI encoder bytes from a serial bridge into the same session log.
"""
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox

try:
    import serial
    from serial.tools import list_ports
    from canlib import canlib, Frame
except ImportError:  # protocol helpers stay importable for tests without drivers
    serial = list_ports = canlib = Frame = None

SDO_ABORT_REASONS = {
    0x05040005: "Out of memory",
    0x06010000: "Unsupported access",
    0x06010001: "Attempt to read a write-only object",
    0x06010002: "Attempt to write a read-only object",
    0x06020000: "Object does not exist",
    0x06090011: "Sub-index not found",
    0x06090030: "Value range exceeded",
    0x060A0023: "Value too large",
    0x08000000: "General error",
    0x08000020: "Data cannot be transferred or stored",
}

# CiA 301 identity objects, read once per session
STATIC_OBJECTS = [
    (0x1000, 0x00, "Device Type"),
    (0x1001, 0x00, "Error Register"),
    (0x1003, 0x00, "Pre-defined Error Field Count"),
    (0x1018, 0x01, "Vendor ID"),
    (0x1018, 0x02, "Product Code"),
    (0x1018, 0x03, "Revision Number"),
    (0x1018, 0x04, "Serial Number"),
]

# CiA 301 communication objects, polled during the session
MONITOR_OBJECTS = [
    (0x1001, 0x00, "Error Register"),
    (0x1017, 0x00, "Producer Heartbeat Time"),
    (0x1002, 0x00, "Manufacturer Status Register"),
    (0x1005, 0x00, "SYNC COB-ID"),
    (0x100C, 0x00, "Guard Time"),
    (0x100D, 0x00, "Life Time Factor"),
    (0x1016, 0x01, "Consumer Heartbeat Time (1)"),
    (0x1029, 0x01, "Error Behavior - Communication Error"),
    (0x1F80, 0x00, "NMT Startup"),
]


def sdo_upload_request(node_id, index, subindex):
    """Return (COB-ID, 8 data bytes) for an expedited SDO upload request."""
    return 0x600 + node_id, [0x40, index & 0xFF, (index >> 8) & 0xFF, subindex, 0, 0, 0, 0]


def parse_sdo_response(data):
    """Classify an SDO server response as ('abort', code, reason) or ('data', value_bytes, '')."""
    data = list(data)
    if len(data) < 8:
        return ("invalid", data, "short frame")
    if data[0] == 0x80:
        code = int.from_bytes(bytes(data[4:8]), "little")
        return ("abort", code, SDO_ABORT_REASONS.get(code, "Unknown abort code"))
    return ("data", data[4:8], "")


def format_ssi_bytes(data):
    return " ".join(f"{b:02X}" for b in data)


class SdoSsiLogger:
    BITRATES = ["125K", "250K", "500K", "1M"]

    def __init__(self, root):
        self.root = root
        self.root.title("CANopen SDO + SSI Logger")

        self.channel = tk.IntVar(value=0)
        self.bitrate = tk.StringVar(value="125K")
        self.node_id = tk.StringVar(value="0x01")
        self.timeout = tk.IntVar(value=1000)
        self.log_dir = tk.StringVar(value=os.getcwd())
        self.ssi_enable = tk.BooleanVar(value=True)
        self.ssi_port = tk.StringVar()
        self.ssi_baud = tk.StringVar(value="1000000")

        self.running = False
        self.log_file = None
        self.log_lock = threading.Lock()
        self.last_ssi_time = 0.0
        self.ui_queue = queue.Queue()  # worker threads never touch tkinter directly

        self.static_vars = [(tk.BooleanVar(value=True), *obj) for obj in STATIC_OBJECTS]
        self.monitor_vars = [(tk.BooleanVar(value=True), *obj) for obj in MONITOR_OBJECTS]

        self.build_gui()
        self.root.after(100, self.drain_ui_queue)

    # ---------- GUI ----------
    def build_gui(self):
        frm = ttk.Frame(self.root)
        frm.pack(padx=10, pady=10)
        ttk.Label(frm, text="Channel").grid(row=0, column=0)
        ttk.Entry(frm, textvariable=self.channel, width=5).grid(row=0, column=1)
        ttk.Label(frm, text="Bitrate").grid(row=0, column=2)
        ttk.Combobox(frm, textvariable=self.bitrate, values=self.BITRATES, width=7).grid(row=0, column=3)
        ttk.Label(frm, text="Node ID").grid(row=1, column=0)
        ttk.Entry(frm, textvariable=self.node_id, width=7).grid(row=1, column=1)
        ttk.Label(frm, text="Timeout (ms)").grid(row=1, column=2)
        ttk.Entry(frm, textvariable=self.timeout, width=7).grid(row=1, column=3)
        ttk.Button(frm, text="Select Log Dir", command=self.select_log_dir).grid(row=2, column=0, columnspan=2)
        ttk.Label(frm, textvariable=self.log_dir).grid(row=2, column=2, columnspan=2)

        ssi = ttk.LabelFrame(self.root, text="SSI Serial Settings")
        ssi.pack(padx=10, pady=5, fill="x")
        ttk.Checkbutton(ssi, text="Enable SSI", variable=self.ssi_enable).grid(row=0, column=0, sticky="w")
        ttk.Label(ssi, text="Port").grid(row=0, column=1)
        self.port_cb = ttk.Combobox(ssi, textvariable=self.ssi_port, width=10, values=self.ports())
        self.port_cb.grid(row=0, column=2)
        ttk.Label(ssi, text="Baudrate").grid(row=0, column=3)
        ttk.Combobox(ssi, textvariable=self.ssi_baud, values=["125000", "250000", "500000", "1000000"], width=10).grid(row=0, column=4)
        ttk.Button(ssi, text="Refresh", command=lambda: self.port_cb.configure(values=self.ports())).grid(row=0, column=5)

        for title, items in (("Static SDO Requests", self.static_vars), ("Monitor Items", self.monitor_vars)):
            box = ttk.LabelFrame(self.root, text=title)
            box.pack(padx=10, pady=5, fill="x")
            for i, (var, index, sub, desc) in enumerate(items):
                ttk.Checkbutton(box, text=f"{desc} (0x{index:04X}/{sub})", variable=var).grid(row=i // 2, column=i % 2, sticky="w")

        leds = ttk.Frame(self.root)
        leds.pack(padx=10, pady=5)
        ttk.Label(leds, text="CANopen").grid(row=0, column=0)
        self.can_led = tk.Label(leds, text="●", font=("Arial", 24), fg="gray")
        self.can_led.grid(row=0, column=1, padx=10)
        ttk.Label(leds, text="SSI").grid(row=0, column=2)
        self.ssi_led = tk.Label(leds, text="●", font=("Arial", 24), fg="gray")
        self.ssi_led.grid(row=0, column=3, padx=10)

        self.start_btn = ttk.Button(self.root, text="Start", command=self.start)
        self.stop_btn = ttk.Button(self.root, text="Stop", command=self.stop, state="disabled")
        self.start_btn.pack(pady=2)
        self.stop_btn.pack(pady=2)
        self.textbox = scrolledtext.ScrolledText(self.root, width=100, height=25, font=("Courier", 9))
        self.textbox.pack(padx=10, pady=5)

    def ports(self):
        return [p.device for p in list_ports.comports()] if list_ports else []

    def select_log_dir(self):
        directory = filedialog.askdirectory()
        if directory:
            self.log_dir.set(directory)

    def drain_ui_queue(self):
        while not self.ui_queue.empty():
            kind, value = self.ui_queue.get_nowait()
            if kind == "log":
                self.textbox.insert(tk.END, value + "\n")
                self.textbox.see(tk.END)
            elif kind == "can_led":
                self.can_led.config(fg=value)
            elif kind == "ssi_led":
                self.ssi_led.config(fg=value)
            elif kind == "error":
                self.set_stopped()
                messagebox.showerror("Error", value)
        self.root.after(100, self.drain_ui_queue)

    # ---------- session ----------
    def log(self, msg, to_file=True):
        self.ui_queue.put(("log", msg))
        if to_file:
            with self.log_lock:
                if self.log_file:
                    self.log_file.write(msg + "\n")

    def start(self):
        if canlib is None:
            messagebox.showerror("Error", "Kvaser canlib and pyserial are required.")
            return
        node_id = int(self.node_id.get(), 16)
        path = os.path.join(self.log_dir.get(), f"node_{node_id:02x}_{time.strftime('%Y%m%d_%H%M%S')}.txt")
        self.log_file = open(path, "w", encoding="utf-8")
        self.running = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.log(f"[INFO] Logging to {path}")
        threading.Thread(target=self.can_worker, args=(node_id,), daemon=True).start()
        if self.ssi_enable.get():
            threading.Thread(target=self.ssi_worker, daemon=True).start()

    def set_stopped(self):
        self.running = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        with self.log_lock:
            if self.log_file:
                self.log_file.close()
                self.log_file = None

    def stop(self):
        self.set_stopped()

    def fail(self, message):
        if self.running:
            self.running = False
            self.ui_queue.put(("error", message))

    def can_worker(self, node_id):
        rates = {"125K": canlib.canBITRATE_125K, "250K": canlib.canBITRATE_250K,
                 "500K": canlib.canBITRATE_500K, "1M": canlib.canBITRATE_1M}
        ch = None
        try:
            ch = canlib.openChannel(self.channel.get(), flags=0)
            ch.setBusParams(rates[self.bitrate.get()])
            ch.busOn()
            time.sleep(0.5)  # let the bus settle before the first request
            ch.write(Frame(id_=0x000, data=bytearray([0x01, node_id]), flags=canlib.canMSG_STD))  # NMT start
            self.log(f"[INFO] Bus on, NMT start sent to node 0x{node_id:02X}")
            for var, index, sub, desc in self.static_vars:
                if self.running and var.get():
                    self.request(ch, node_id, index, sub, desc)
                    time.sleep(0.1)
            while self.running:
                for var, index, sub, desc in self.monitor_vars:
                    if self.running and var.get():
                        self.request(ch, node_id, index, sub, desc)
                        time.sleep(0.5)
                time.sleep(5)
        except Exception as exc:
            self.fail(f"Unable to communicate with device: {exc}")
        finally:
            if ch is not None:
                try:
                    ch.busOff()
                    ch.close()
                except Exception:
                    pass

    def request(self, ch, node_id, index, sub, desc):
        tx_id, tx_data = sdo_upload_request(node_id, index, sub)
        rx_id = 0x580 + node_id
        ch.write(Frame(id_=tx_id, data=bytearray(tx_data), flags=canlib.canMSG_STD))
        self.log(f"{time.strftime('%H:%M:%S')} TX {desc}: {format_ssi_bytes(tx_data)}")
        deadline = time.time() + self.timeout.get() / 1000.0
        while time.time() < deadline and self.running:
            try:
                rx = ch.read(timeout=10)
            except canlib.CanNoMsg:
                continue
            if rx.id != rx_id:
                continue
            kind, value, reason = parse_sdo_response(rx.data)
            stamp = time.strftime("%H:%M:%S")
            if kind == "abort":
                self.log(f"{stamp} RX {desc}: abort 0x{value:08X} ({reason})")
            else:
                self.log(f"{stamp} RX {desc}: {format_ssi_bytes(value) if kind == 'data' else value}")
            self.ui_queue.put(("can_led", "green"))
            return
        if self.running:
            self.log(f"[TIMEOUT] No response for {desc}")
            self.ui_queue.put(("can_led", "red"))
            self.fail("No SDO response within the timeout")

    def ssi_worker(self):
        try:
            ser = serial.Serial(self.ssi_port.get(), baudrate=int(self.ssi_baud.get()), timeout=0.1)
        except Exception as exc:
            self.ui_queue.put(("ssi_led", "red"))
            self.fail(f"Cannot open SSI port: {exc}")
            return
        with ser:
            while self.running:
                try:
                    data = ser.read(16) if ser.in_waiting else b""
                except Exception as exc:
                    self.ui_queue.put(("ssi_led", "red"))
                    self.fail(f"SSI receive error: {exc}")
                    break
                if data:
                    self.last_ssi_time = time.time()
                    self.log(f"{time.strftime('%H:%M:%S')} SSI: {format_ssi_bytes(data)}")
                self.ui_queue.put(("ssi_led", "green" if time.time() - self.last_ssi_time < 2.0 else "gray"))
                time.sleep(0.2)


if __name__ == "__main__":
    root = tk.Tk()
    SdoSsiLogger(root)
    root.mainloop()
