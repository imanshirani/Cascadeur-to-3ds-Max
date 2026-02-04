# File: max_receiver.py
import sys
import os
import socket
import json
import pymxs
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl

# --- Defult Values ---
DEFAULT_PORT = 5555
DEFAULT_SCALE = 1.0

# ---------------------------------------------------------
# 1. WORKER THREAD (Server Logic)
# ---------------------------------------------------------
class ServerWorker(QtCore.QThread):
    data_received = QtCore.Signal(dict)
    
    def __init__(self, port, scale_factor, parent=None):
        super().__init__(parent)
        self.port = port
        self.scale_factor = scale_factor 
        self.running = True

    def run(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        host = '127.0.0.1'
        try:
            server_socket.bind((host, self.port))
            server_socket.listen(1)
        except Exception as e:
            print(f"Bind Error on port {self.port}: {e}")
            return
        
        while self.running:
            try:
                server_socket.settimeout(1.0)
                try:
                    client, addr = server_socket.accept()
                except socket.timeout:
                    continue
                
                with client:
                    buffer = b""
                    while self.running:
                        try:
                            client.settimeout(2.0)
                            chunk = client.recv(8192 * 4) 
                            if not chunk: break
                            buffer += chunk
                            
                            try:
                                json_str = buffer.decode('utf-8')
                                if "}{" in json_str:
                                    json_str = json_str.split("}{")[0] + "}"

                                data_dict = json.loads(json_str)
                                data_dict["_runtime_scale"] = self.scale_factor
                                self.data_received.emit(data_dict)
                                buffer = b""
                            except json.JSONDecodeError:
                                continue
                            
                        except socket.timeout:
                            continue
                        except Exception:
                            break
            except Exception as e:
                if self.running:
                    print(f"Network Loop Error: {e}")

        server_socket.close()

    def stop(self):
        self.running = False
        self.wait()

# ---------------------------------------------------------
# 2. SETTINGS DIALOG (Original UI)
# ---------------------------------------------------------
class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, current_port, current_scale, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(400, 300)
        self.new_port = current_port
        self.new_scale = current_scale
        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout()
        self.tabs = QtWidgets.QTabWidget()
        self.tab_general = QtWidgets.QWidget()
        self.tab_about = QtWidgets.QWidget()
        
        self.tabs.addTab(self.tab_general, "General")
        self.tabs.addTab(self.tab_about, "About")
        
        # General
        gen_layout = QtWidgets.QFormLayout()
        gen_layout.setContentsMargins(20, 20, 20, 20)
        self.input_port = QtWidgets.QSpinBox()
        self.input_port.setRange(1024, 65535)
        self.input_port.setValue(self.new_port)
        gen_layout.addRow("Network Port:", self.input_port)
        self.input_scale = QtWidgets.QDoubleSpinBox()
        self.input_scale.setRange(0.001, 1000.0)
        self.input_scale.setSingleStep(0.1)
        self.input_scale.setValue(self.new_scale)
        gen_layout.addRow("Global Scale:", self.input_scale)
        self.tab_general.setLayout(gen_layout)
        
        # About
        abt_layout = QtWidgets.QVBoxLayout()
        abt_layout.setAlignment(QtCore.Qt.AlignCenter)
        abt_layout.setSpacing(15)
        lbl_title = QtWidgets.QLabel("Cascadeur Live Link")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #4fc3f7;")
        lbl_ver = QtWidgets.QLabel("Version 0.0.1")
        lbl_desc = QtWidgets.QLabel("Real-time bridge between Cascadeur & 3ds Max")
        abt_layout.addWidget(lbl_title)
        abt_layout.addWidget(lbl_ver)
        abt_layout.addWidget(lbl_desc)
        
        btn_box = QtWidgets.QHBoxLayout()
        self.btn_github = QtWidgets.QPushButton("GitHub Repo")
        self.btn_github.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/")))
        btn_box.addWidget(self.btn_github)
        self.btn_donate = QtWidgets.QPushButton("Donate")
        self.btn_donate.setStyleSheet("background-color: #0070ba; color: white; font-weight: bold;")
        self.btn_donate.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://paypal.me/")))
        btn_box.addWidget(self.btn_donate)
        abt_layout.addLayout(btn_box)
        
        self.tab_about.setLayout(abt_layout)
        layout.addWidget(self.tabs)
        
        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_save = QtWidgets.QPushButton("Save && Close")
        self.btn_save.clicked.connect(self.save_settings)
        self.btn_cancel = QtWidgets.QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        
    def save_settings(self):
        self.new_port = self.input_port.value()
        self.new_scale = self.input_scale.value()
        self.accept()

# ---------------------------------------------------------
# 3. MAIN WINDOW (Full Logic)
# ---------------------------------------------------------
class CasLiveDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cascadeur Live Link")
        self.resize(320, 220)
        self.current_port = DEFAULT_PORT
        self.current_scale = DEFAULT_SCALE
        self.worker = None 
        self.init_ui()
        

    def init_ui(self):
        self.setStyleSheet("""
            QDialog { background-color: #2b2b2b; color: #ffffff; }
            QLabel { color: #dddddd; }
            QPushButton { border-radius: 4px; padding: 6px; }
            QTabWidget::pane { border: 1px solid #444; }
        """)

        layout = QtWidgets.QVBoxLayout()
        layout.setSpacing(10)
        
        self.lbl_info = QtWidgets.QLabel(f"Port: {self.current_port} | Scale: {self.current_scale}")
        self.lbl_info.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_info.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self.lbl_info)

        self.lbl_status = QtWidgets.QLabel("OFFLINE")
        self.lbl_status.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_status.setStyleSheet("background-color: #1a1a1a; color: #555; font-size: 26px; font-weight: bold; border-radius: 8px; padding: 15px; border: 1px solid #333;")
        layout.addWidget(self.lbl_status)
        
        self.btn_toggle = QtWidgets.QPushButton("Start Connection")
        self.btn_toggle.setMinimumHeight(45)
        self.btn_toggle.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold; font-size: 14px;")
        self.btn_toggle.clicked.connect(self.toggle_connection)
        layout.addWidget(self.btn_toggle)

        self.btn_settings = QtWidgets.QPushButton("Settings")
        self.btn_settings.setStyleSheet("background-color: #444; color: white;")
        self.btn_settings.clicked.connect(self.open_settings)
        layout.addWidget(self.btn_settings)

        #self.btn_convert = QtWidgets.QPushButton("Convert Selection to Biped")
        #self.btn_convert.clicked.connect(self.convert_selection_to_biped)
        #layout.addWidget(self.btn_convert)

        self.setLayout(layout)

    def open_settings(self):
        dialog = SettingsDialog(self.current_port, self.current_scale, self)
        if dialog.exec():
            self.current_port = dialog.new_port
            self.current_scale = dialog.new_scale
            self.lbl_info.setText(f"Port: {self.current_port} | Scale: {self.current_scale}")
            if self.worker:
                pymxs.runtime.messageBox("Please Restart Connection to apply changes.")

    def toggle_connection(self):
        if self.worker is not None:
            self.stop_server()
        else:
            self.start_server()

    def start_server(self):
        self.worker = ServerWorker(self.current_port, self.current_scale)        
        self.worker.data_received.connect(self.process_caslive_data)
        self.worker.start()
        
        self.lbl_status.setText("LISTENING")
        self.lbl_status.setStyleSheet("background-color: #111; color: orange; font-size: 26px; font-weight: bold; border: 2px solid orange; border-radius: 8px; padding: 15px;")
        self.btn_toggle.setText("Stop Connection")
        self.btn_toggle.setStyleSheet("background-color: #c62828; color: white; font-weight: bold; font-size: 14px;")
        self.btn_settings.setEnabled(False)

    def stop_server(self):
        if self.worker:
            self.worker.stop()
            self.worker = None
        self.lbl_status.setText("OFFLINE")
        self.lbl_status.setStyleSheet("background-color: #1a1a1a; color: #555; font-size: 26px; font-weight: bold; border-radius: 8px; padding: 15px; border: 1px solid #333;")
        self.btn_toggle.setText("Start Connection")
        self.btn_toggle.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold; font-size: 14px;")
        self.btn_settings.setEnabled(True)

    # --- PROCESS DATA (This was missing!) ---
    def process_caslive_data(self, packet):
        cmd = packet.get("command")
        if packet.get("header", {}).get("signature") == "CLIVE": cmd = "LIVE_DATA"
        scale = packet.get("_runtime_scale", 1.0)
        
        if cmd == "SYNC_MODEL":
            fbx_path = packet.get("path")
            self.lbl_status.setText("SYNCING...")
            
            QtCore.QThread.msleep(100)
            self.import_full_scene(fbx_path)
            
            self.lbl_status.setText("MODEL SYNCED")
            self.lbl_status.setStyleSheet("background-color: #000; color: #00aaff; font-size: 26px; font-weight: bold; border: 2px solid #00aaff; border-radius: 8px; padding: 15px;")
            

        elif cmd == "LIVE_DATA":
            if "SYNC" in self.lbl_status.text() or "LISTENING" in self.lbl_status.text():
                 self.lbl_status.setText("LINKED")
                 self.lbl_status.setStyleSheet("background-color: #000; color: #00ff00; border: 2px solid #00ff00; padding: 15px;")

            frame = packet.get("frame", 0)
            data = packet.get("data", [])
            self.update_scene_live(data, scale, frame)

    # --- CLEANUP & IMPORT LOGIC ---
    def delete_previous_sync(self):
        
        rt = pymxs.runtime
        to_delete = []
        for obj in rt.objects:
            if rt.getUserProp(obj, "cas_bridge_tag") == True:
                to_delete.append(obj)
        
        if len(to_delete) > 0:
            rt.delete(to_delete)
            print(f"Deleted {len(to_delete)} old bridge objects.")

    def import_full_scene(self, path):
        if not os.path.exists(path): return
        rt = pymxs.runtime
        
        try:
            rt.FBXImporterSetParam("Mode", rt.name("create"))
            rt.FBXImporterSetParam("Geometries", True)
            rt.FBXImporterSetParam("Skin Modifier", True)
            rt.FBXImporterSetParam("Animation", False)
            rt.FBXImporterSetParam("Cameras", False)
            rt.FBXImporterSetParam("Lights", False)
            rt.FBXImporterSetParam("ScaleConversion", True)
        except: pass

        with pymxs.redraw(False):
            with pymxs.undo(True):
                
                self.delete_previous_sync()

                
                rt.importFile(path, rt.name("noPrompt"))
                
                
                for obj in rt.selection:
                    rt.setUserProp(obj, "cas_bridge_tag", True)
                    if ":" in obj.name:
                        try: obj.name = obj.name.split(":")[-1]
                        except: pass
        rt.redrawViews()

    def update_scene_live(self, bones_data, scale, frame_number):
        rt = pymxs.runtime
        with pymxs.undo(False):
            with pymxs.redraw(False):
                if rt.sliderTime != frame_number:
                    rt.sliderTime = frame_number

                for bone in bones_data:
                    name = bone.get("n")
                    if ":" in name: name = name.split(":")[-1]

                    node = rt.getNodeByName(name)
                    if not node: continue
                    
                    raw_pos = bone.get("p")
                    raw_rot = bone.get("r")
                    
                    node.pos = rt.Point3(raw_pos[0], raw_pos[2], raw_pos[1]) * scale
                    node.rotation = rt.Quat(raw_rot[0], raw_rot[2], -raw_rot[1], raw_rot[3])
            rt.redrawViews()

    def closeEvent(self, event):
        self.stop_server()
        event.accept()





    

def show_caslive():
    if not hasattr(sys, "caslive_win"):
        sys.caslive_win = None
    if sys.caslive_win:
        try: sys.caslive_win.close()
        except: pass
        
    main_window = QtWidgets.QWidget.find(pymxs.runtime.windows.getMAXHWND())
    sys.caslive_win = CasLiveDialog(main_window)
    sys.caslive_win.show()

if __name__ == "__main__":
    show_caslive()