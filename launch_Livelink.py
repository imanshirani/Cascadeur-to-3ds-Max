# ====================================================================
# ===                                                              ===
# ===      Cascadeur to 3ds Max Live Link                          ===                                                      
# ===      Author: Iman Shirani                                    ===                                                    
# ===      Version: 0.0.1                                          ===                                              
# ===                                                              ===
# ===                                                              ===           
# ====================================================================
import sys
import os
import importlib

def run():
    
    current_dir = os.path.dirname(__file__)
    
    
    if current_dir not in sys.path:
        sys.path.append(current_dir)

    
    try:
        import max_receiver
        
        
        importlib.reload(max_receiver)
        
        
        print(f"Launching CasLive from: {current_dir}")
        max_receiver.show_caslive()
        
    except ImportError as e:
        print(f"Error: Could not import receiver script. {e}")
    except Exception as e:
        print(f"Error launching LiveLink: {e}")

if __name__ == "__main__":
    run()