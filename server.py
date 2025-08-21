from flask import Flask, request, jsonify
from flask_socketio import SocketIO
from PIL import Image
import base64
import io
import time
import queue
import os

# Flask App for Whiteboard
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Queue for coordinates
coordinates_queue = queue.Queue()

# Connection management
connection_requests = queue.Queue()
connected_clients = set()  # Clients with edit permission

# Client viewports information
client_viewports = {}

# Current PDF state
current_pdf = {
    "data": None,
    "total_pages": 0,
    "current_page": 0
}

@app.route("/")
def index():
    return "Server is running."

@app.route("/upload_pdf", methods=["POST"])
def upload_pdf():
    """Handle PDF upload."""
    file = request.files.get("pdf")
    if file:
        # Save PDF to file system
        file_path = "uploaded_document.pdf"
        file.save(file_path)
        
        # Read PDF into memory for broadcasting
        with open(file_path, "rb") as pdf_file:
            pdf_bytes = pdf_file.read()
            pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
        
        # Update current PDF state
        current_pdf["data"] = pdf_base64
        current_pdf["total_pages"] = request.form.get("total_pages", 0)
        current_pdf["current_page"] = 0
        
        # Broadcast to all clients
        socketio.emit("new_pdf", {
            "pdf_data": pdf_base64,
            "total_pages": current_pdf["total_pages"],
            "current_page": current_pdf["current_page"]
        })
        
        return jsonify({"message": "PDF uploaded successfully"}), 200
    return jsonify({"message": "No PDF uploaded"}), 400

@socketio.on("connect")
def handle_connect():
    """Handle client connection - now clients connect immediately."""
    client_id = request.sid
    client_ip = request.remote_addr
    print(f"Client connected: {client_ip} (ID: {client_id})")
    
    # Notify client they're connected in view-only mode
    socketio.emit("connection_status", {
        "status": "connected", 
        "can_edit": False,
        "message": "You are connected in view-only mode."
    }, room=client_id)
    
    # Send current PDF state if available
    if current_pdf["data"]:
        socketio.emit("new_pdf", {
            "pdf_data": current_pdf["data"],
            "total_pages": current_pdf["total_pages"],
            "current_page": current_pdf["current_page"]
        }, room=client_id)
    
    return True

@socketio.on("request_edit_permission")
def request_edit_permission(data):
    print(data)
    """Client requests edit permission with an optional question."""
    client_id = request.sid
    client_ip = request.remote_addr
    question = data.get("question", "")  # Default to empty string if not provided

    # Add to connection request queue with timestamp and question
    connection_requests.put({
        "client_id": client_id,
        "client_ip": client_ip,
        "timestamp": time.time(),
        "status": "pending",
        "question": question
    })

    print(f"Edit permission requested by {client_ip} (ID: {client_id}) | Question: {question}")

    # Notify admin about this request including the question
    socketio.emit("new_edit_request", {
        "client_id": client_id,
        "client_ip": client_ip,
        "timestamp": time.time(),
        "question": question
    })


@socketio.on("allow_student")
def allowStudent(client_id):
    """Grant edit permission to a client."""
    # Add to connected_clients set (clients with edit permission)
    connected_clients.add(client_id)
    
    # Notify the client they can now edit
    socketio.emit("connection_status", {
        "status": "edit_approved",
        "can_edit": True,
        "message": "You now have permission to edit the whiteboard."
    }, room=client_id)
    
    # For backward compatibility
    socketio.emit("allow_student", {"allowed_sid": client_id})
    
    print(f"Edit permission granted to client {client_id}")

@socketio.on("send_coordinates")
def handle_coordinates(data):
    """Handle incoming coordinates from clients."""
    client_id = request.sid
    
    # Only process if client is approved for editing
    if client_id in connected_clients:
        coordinates_queue.put(data)
        # Broadcast to all other clients
        socketio.emit("coordinate_update", data, skip_sid=request.sid)
    else:
        print(f"Rejected coordinates from client without edit permission: {client_id}")
        # Inform client they need permission
        socketio.emit("connection_status", {
            "status": "permission_denied",
            "can_edit": False,
            "message": "You don't have permission to edit. Please request access."
        }, room=client_id)

@socketio.on("register_viewport")
def handle_viewport_registration(data):
    """Handle client viewport registration."""
    client_id = request.sid  # Socket ID for this client
    
    # All connected clients can register viewport
    width = data.get("width", 0)
    height = data.get("height", 0)
    client_viewports[client_id] = {"width": width, "height": height}
    print(f"Client {client_id} registered viewport: {width}x{height}")

@socketio.on("new_pdf")
def handle_new_pdf(data):
    """Handle new PDF document being shared."""
    # Update the current PDF state
    current_pdf["data"] = data.get("pdf_data")
    current_pdf["total_pages"] = data.get("total_pages", 0)
    current_pdf["current_page"] = data.get("current_page", 0)
    
    # Broadcast to all clients except sender
    socketio.emit("new_pdf", data, skip_sid=request.sid)

@socketio.on("change_page")
def handle_page_change(data):
    """Handle PDF page change."""
    page_number = data.get("page_number", 0)
    
    # Update current page in state
    current_pdf["current_page"] = page_number
    
    # Broadcast to all clients except sender
    socketio.emit("change_page", data, skip_sid=request.sid)

@socketio.on("disconnect")
def handle_disconnect():
    """Clean up when client disconnects."""
    client_id = request.sid
    if client_id in client_viewports:
        del client_viewports[client_id]
    
    if client_id in connected_clients:
        connected_clients.remove(client_id)
        print(f"Client {client_id} disconnected, removed from approved clients")