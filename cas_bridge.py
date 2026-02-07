import sys
import os
import socket
import json
import time
import datetime
import threading
import csc

# --- CONFIG ---
HOST = '127.0.0.1'
PORT = 5555
UPDATE_RATE = 0.02
SEND_MESH = True 
LOG_FILE = "C:/Temp3d/cas_log.txt"

def log(msg):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    formatted_msg = f"[{timestamp}] {msg}"
    print(formatted_msg)
    try:
        if not os.path.exists("C:/Temp3d"): os.makedirs("C:/Temp3d")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted_msg + "\n")
    except: pass

class CasBridgeCore:
    def __init__(self):
        self.running = False
        self.thread = None
        self.sock = None
        self.app = csc.app.get_application()
        self.manager = self.app.get_scene_manager()

    def connect_socket(self):
        try:
            if self.sock: return True
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(0.5)
            self.sock.connect((HOST, PORT))
            return True
        except:
            self.sock = None
            return False

    def export_and_sync_mesh(self):
        log("   >>> [STEP 1] Starting Mesh Export Process...")
        
        target_dir = "C:/Temp3d/Cascadeur"
        if not os.path.exists(target_dir): os.makedirs(target_dir)
        fbx_path = f"{target_dir}/cas_sync.fbx"

        try:
            scene = self.manager.current_scene()
            if not scene:
                log("   ❌ ERROR: No active scene found to export.")
                return False

            log("   ℹ️ Exporting FBX file to disk...")
            tools = self.app.get_tools_manager()
            loader = tools.get_tool("FbxSceneLoader").get_fbx_loader(scene)
            
            if hasattr(loader, "export_all_objects"):
                loader.export_all_objects(fbx_path)
            else:
                loader.export_selected(fbx_path)
            
            log(f"   ✅ FBX File created at: {fbx_path}")

            log("   ℹ️ Sending SYNC command to 3ds Max...")
            temp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            temp_sock.settimeout(2.0)
            temp_sock.connect((HOST, PORT))
            packet = {"command": "SYNC_MODEL", "path": fbx_path}
            temp_sock.sendall(json.dumps(packet).encode('utf-8'))
            temp_sock.close()
            
            log("   ✅ Command Sent. Waiting for Max to load mesh...")
            return True
        except Exception as e:
            log(f"   ❌ Export Failed: {e}")
            return False

    def start_live_link(self):
        if self.running:
            self.stop_live_link()

        log("="*40)
        log("🚀 SCRIPT STARTED (RESTART MODE)")
        log(f"📋 Configuration: SEND_MESH is set to [{SEND_MESH}]")
        
        if SEND_MESH:
            log("🤔 Reason: Because SEND_MESH = True, I will export the mesh now.")
            success = self.export_and_sync_mesh()
            if success:
                log("   ⏳ Pausing 1.0s to let Max process the file...")
                time.sleep(1.0) 
            else:
                log("   ⚠️ Export failed, but trying to continue connection...")
        else:
            log("🤔 Reason: Because SEND_MESH = False, I am SKIPPING export.")

        self.running = True
        self.thread = threading.Thread(target=self._live_loop)
        self.thread.daemon = True
        self.thread.start()
        log("✅ [STEP 2] Live Thread Started.")
        log("="*40)

    def stop_live_link(self):
        self.running = False
        if self.thread: 
            try: self.thread.join(timeout=1.0)
            except: pass
        if self.sock: 
            try: self.sock.close()
            except: pass
            self.sock = None
        log("🛑 STOPPED previous session.")

    def _live_loop(self):
        log(" Live Loop Running... (Waiting for scene data)")
        packet_count = 0
        
        while self.running:
            time.sleep(UPDATE_RATE)

            try:
                if not self.connect_socket(): continue

                scene = self.manager.current_scene()
                if not scene: continue

                # --- FIX: Safe Frame Getter ---
                try:
                    current_frame = scene.get_current_frame()
                except AttributeError:
                    
                    current_frame = 0 
                # ------------------------------

                objects = []
                if hasattr(scene, "get_selected_objects"):
                    objects = scene.get_selected_objects()
                
                if not objects: continue

                data_list = []
                for obj in objects:
                    if "Joint" in obj.name or "Center" in obj.name or "Point" in obj.name:
                        tf = obj.get_global_transform()
                        p = tf.translation
                        r = tf.rotation
                        data_list.append({
                            "n": obj.name,
                            "p": [p.x, p.y, p.z],
                            "r": [r.x, r.y, r.z, r.w]
                        })

                if not data_list: continue

                packet = {
                    "command": "LIVE_DATA",
                    "frame": current_frame,
                    "data": data_list
                }
                
                msg = json.dumps(packet).encode('utf-8')
                self.sock.sendall(msg)
                
                if packet_count == 0:
                    log(f"📡 First Packet Sent! (Frame: {current_frame}, Objects: {len(data_list)})")
                packet_count += 1

            except Exception as e:
                
                if packet_count % 50 == 0:
                    log(f"⚠️ Loop Error: {e}")
                self.sock = None
                time.sleep(1.0)


def main():
    
    if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 1024 * 1024:
        try: os.remove(LOG_FILE)
        except: pass

    
    if hasattr(sys, "cas_bridge_instance") and sys.cas_bridge_instance:
        sys.cas_bridge_instance.running = False
        sys.cas_bridge_instance.stop_live_link()
        time.sleep(0.2) 
        sys.cas_bridge_instance = None

    
    bridge = CasBridgeCore()
    sys.cas_bridge_instance = bridge
    bridge.start_live_link()

if __name__ == "__main__":
    main()