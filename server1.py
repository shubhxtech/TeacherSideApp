from flask import Flask, request, jsonify
from flask_socketio import SocketIO
from PIL import Image
import base64
import io
import time
import queue

# Flask App for Whiteboard
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Queue for coordinates
coordinates_queue = queue.Queue()

# Connection management
connection_requests = queue.Queue()
connected_clients = set()

# Client viewports information
client_viewports = {}

@app.route("/")
def index():
    return "Server is running."

@app.route("/upload_image", methods=["POST"])
def upload_image():
    """Handle image upload."""
    file = request.files.get("image")
    if file:
        file.save("uploaded_image.png")
        # Convert to base64 and emit
        with open("uploaded_image.png", "rb") as img_file:
            img_bytes = img_file.read()
            img_base64 = base64.b64encode(img_bytes).decode('utf-8')
            # Get image dimensions
            img = Image.open("uploaded_image.png")
            width, height = img.size
            socketio.emit("new_image", {
                "image_data": img_base64,
                "canvas_width": width,
                "canvas_height": height
            })
        return jsonify({"message": "Image uploaded successfully"}), 200
    return jsonify({"message": "No image uploaded"}), 400

@socketio.on("connect")
def handle_connect():
    """Handle client connection request."""
    client_id = request.sid
    client_ip = request.remote_addr
    print(f"Connection request from {client_ip} (ID: {client_id})")
    
    # Add to connection request queue with timestamp
    connection_requests.put({
        "client_id": client_id,
        "client_ip": client_ip,
        "timestamp": time.time(),
        "status": "pending"  # New status field for tracking
    })
    
    # Connection is pending until approved
    return True
@socketio.on("allow_student")
def allowStudent(client_id):
    socketio.emit("allow_student", {"allowed_sid": client_id})

@socketio.on("send_coordinates")
def handle_coordinates(data):
    """Handle incoming coordinates from clients."""
    client_id = request.sid
    
    # Only process if client is approved
    if client_id in connected_clients:
        coordinates_queue.put(data)
        # Broadcast to all other approved clients
        socketio.emit("coordinate_update", data, skip_sid=request.sid)
    else:
        print(f"Rejected coordinates from unapproved client {client_id}")

@socketio.on("register_viewport")
def handle_viewport_registration(data):
    """Handle client viewport registration."""
    client_id = request.sid  # Socket ID for this client
    
    # Only process if client is approved
    if client_id in connected_clients:
        width = data.get("width", 0)
        height = data.get("height", 0)
        client_viewports[client_id] = {"width": width, "height": height}
        # print(f"Client {client_id} registered viewport: {width}x{height}")

@socketio.on("disconnect")
def handle_disconnect():
    """Clean up when client disconnects."""
    client_id = request.sid
    if client_id in client_viewports:
        del client_viewports[client_id]
    
    if client_id in connected_clients:
        connected_clients.remove(client_id)
        print(f"Client {client_id} disconnected, removed from approved clients")