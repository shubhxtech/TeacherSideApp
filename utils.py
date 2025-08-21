import socket
import queue

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

def clear_queue(q):
    """Safely clear a queue."""
    try:
        while not q.empty():
            q.get_nowait()
    except queue.Empty:
        pass