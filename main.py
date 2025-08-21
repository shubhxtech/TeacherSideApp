import threading
import socket
from server import app, socketio
from whiteboard import run_tkinter

def get_local_ip():
    """Get the local IP address"""
    try:
        # Create a socket to connect to an external address
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # Doesn't actually connect but gets the local IP used for external connections
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            return local_ip
    except:
        return "127.0.0.1"  # Fallback to localhost

def run_flask():
    """Start the Flask server."""
    socketio.run(app, host="0.0.0.0", port=5000, debug=False)

if __name__ == "__main__":
    host_ip = get_local_ip()
    print(f"Using IP address: {host_ip}")
    
    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Start Tkinter in the main thread
    run_tkinter(host_ip)