import time
from tkinter import Frame, Label, Listbox, Button, MULTIPLE, StringVar, RIGHT, LEFT, BOTH, Y
from tkinter import ttk
from server import connection_requests, connected_clients, socketio

class ConnectionRequestPanel:
    def __init__(self, parent):
        """Initialize the connection request panel."""
        self.parent = parent
        self.frame = Frame(parent, bg="#f0f0f0")
        self.frame.pack(fill="both", expand=True, padx=5, pady=10)

        # Heading
        Label(self.frame, text="Connection Requests", font=("Arial", 12, "bold"), bg="#f0f0f0").pack(pady=5)

        # Status label
        self.status_var = StringVar()
        self.status_var.set("No pending requests")
        self.status_label = Label(self.frame, textvariable=self.status_var, bg="#f0f0f0")
        self.status_label.pack(pady=5)

        # Request list frame with scrollbar
        list_frame = Frame(self.frame)
        list_frame.pack(fill=BOTH, expand=True, pady=5)

        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=RIGHT, fill=Y)

        # Request listbox
        self.request_list = Listbox(list_frame, selectmode=MULTIPLE, height=8, width=25)
        self.request_list.pack(side=LEFT, fill=BOTH, expand=True)

        # Configure scrollbar
        self.request_list.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.request_list.yview)

        # Bind selection event to show question
        self.request_list.bind("<<ListboxSelect>>", self.display_selected_question)

        # Label to show selected question
        self.question_label = Label(self.frame, text="Question: ", font=("Arial", 10), bg="#f8f8f8", wraplength=500, justify="left")
        self.question_label.pack(fill="x", padx=5, pady=5)

        # Buttons
        button_frame = Frame(self.frame, bg="#f0f0f0")
        button_frame.pack(fill="x", pady=5)

        ttk.Button(button_frame, text="Approve Selected", command=self.approve_selected).pack(side="left", padx=2)
        ttk.Button(button_frame, text="Reject Selected", command=self.reject_selected).pack(side="left", padx=2)
        ttk.Button(button_frame, text="Refresh", command=self.refresh_requests).pack(side="left", padx=2)

        # Request storage
        self.pending_requests = {}  # {index: request_data}
        self.index_to_client_id = {}  # {listbox index: client_id}

        # Automatically refresh requests on creation
        self.refresh_requests()

    def refresh_requests(self):
        """Refresh the list of connection requests."""
        current_time = time.time()
        stale_indexes = []

        # Check for stale requests
        for index, request_data in self.pending_requests.items():
            if current_time - request_data["timestamp"] > 120:  # 2 minutes
                stale_indexes.append(index)

        # Disconnect and remove stale
        for index in stale_indexes:
            client_id = self.pending_requests[index]["client_id"]
            try:
                socketio.server.disconnect(client_id)
            except Exception as e:
                print(f"Error disconnecting stale client {client_id}: {e}")
            del self.pending_requests[index]

        # Get new requests from the queue
        while not connection_requests.empty():
            request = connection_requests.get()
            if request["client_id"] not in connected_clients:
                index = len(self.pending_requests)
                self.pending_requests[index] = request

        # Update Listbox
        self.request_list.delete(0, "end")
        self.index_to_client_id.clear()

        for idx, (index, request_data) in enumerate(self.pending_requests.items()):
            client_ip = request_data["client_ip"]
            timestamp = time.strftime("%H:%M:%S", time.localtime(request_data["timestamp"]))
            question = request_data.get("question", "").strip()
            preview = (question[:30] + "...") if len(question) > 30 else question
            self.request_list.insert(idx, f"{client_ip} ({timestamp}) - {preview}")
            self.index_to_client_id[idx] = request_data["client_id"]

        # Update status
        if self.pending_requests:
            self.status_var.set(f"{len(self.pending_requests)} pending request(s)")
        else:
            self.status_var.set("No pending requests")

    def approve_selected(self):
        """Approve selected connection requests."""
        selected_indexes = self.request_list.curselection()
        if not selected_indexes:
            return

        for idx in selected_indexes:
            client_id = self.index_to_client_id.get(idx)
            if client_id:
                request_data = self._find_request_by_client_id(client_id)
                if request_data:
                    client_ip = request_data["client_ip"]
                    connected_clients.add(client_id)
                    socketio.emit("allow_student", {"allowed_sid": client_id})
                    socketio.emit("connection_approved", room=client_id)
                    print(f"Approved connection from {client_ip} (ID: {client_id})")

                    self._remove_request_by_client_id(client_id)

        self.refresh_requests()

    def reject_selected(self):
        """Reject selected connection requests."""
        selected_indexes = self.request_list.curselection()
        if not selected_indexes:
            return

        for idx in selected_indexes:
            client_id = self.index_to_client_id.get(idx)
            if client_id:
                request_data = self._find_request_by_client_id(client_id)
                if request_data:
                    client_ip = request_data["client_ip"]
                    socketio.emit("connection_rejected", room=client_id)
                    try:
                        socketio.server.disconnect(client_id)
                    except Exception as e:
                        print(f"Error disconnecting client {client_id}: {e}")
                    print(f"Rejected connection from {client_ip} (ID: {client_id})")

                    self._remove_request_by_client_id(client_id)

        self.refresh_requests()

    def display_selected_question(self, event):
        """Show the full question of the selected request."""
        selection = self.request_list.curselection()
        if not selection:
            self.question_label.config(text="Question: ")
            return

        idx = selection[0]
        client_id = self.index_to_client_id.get(idx)
        if not client_id:
            self.question_label.config(text="Question: ")
            return

        request_data = self._find_request_by_client_id(client_id)
        if request_data:
            question = request_data.get("question", "").strip()
            self.question_label.config(text=f"Question: {question or 'N/A'}")
        else:
            self.question_label.config(text="Question: ")

    def _find_request_by_client_id(self, client_id):
        """Helper to find request_data by client_id."""
        for data in self.pending_requests.values():
            if data["client_id"] == client_id:
                return data
        return None

    def _remove_request_by_client_id(self, client_id):
        """Helper to remove request by client_id."""
        to_delete = [k for k, v in self.pending_requests.items() if v["client_id"] == client_id]
        for k in to_delete:
            del self.pending_requests[k]
