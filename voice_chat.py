import socket
import pyaudio
import threading
import time
from tkinter import StringVar

# Audio settings
CHUNK = 512
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 22050
VOICE_PORT = 8000

class VoiceChat:
    def __init__(self, host):
        self.host = host
        self.running = False
        self.connected = False
        self.stop_event = threading.Event()
        self.server_socket = None
        self.connection = None
        self.client_address = None

        self.audio = None
        self.input_stream = None
        self.output_stream = None

        self.status_var = StringVar()
        self.status_var.set("Voice Chat: Disconnected")
        self.audio_level = 0

    def initialize_audio(self):
        self.cleanup_audio()
        self.audio = pyaudio.PyAudio()
        self.input_stream = self.audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK
        )
        self.output_stream = self.audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            output=True,
            frames_per_buffer=CHUNK
        )

    def cleanup_audio(self):
        if self.input_stream:
            try:
                self.input_stream.stop_stream()
                self.input_stream.close()
            except:
                pass
            self.input_stream = None

        if self.output_stream:
            try:
                self.output_stream.stop_stream()
                self.output_stream.close()
            except:
                pass
            self.output_stream = None

        if self.audio:
            try:
                self.audio.terminate()
            except:
                pass
            self.audio = None

    def start_server(self):
        if self.running:
            return

        self.status_var.set("Voice Chat: Waiting for connection...")

        def server_thread():
            try:
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.server_socket.bind((self.host, VOICE_PORT))
                self.server_socket.settimeout(1.0)
                self.server_socket.listen(1)
                print(f"Voice server listening on {self.host}:{VOICE_PORT}")

                while not self.stop_event.is_set():
                    try:
                        connection, addr = self.server_socket.accept()
                        print(f"Voice connection from {addr[0]} accepted")

                        self.initialize_audio()

                        self.connection = connection
                        self.client_address = addr
                        self.running = True
                        self.connected = True
                        self.status_var.set(f"Voice Chat: Connected to {addr[0]}")

                        send_thread = threading.Thread(target=self.send_audio)
                        receive_thread = threading.Thread(target=self.receive_audio)

                        send_thread.start()
                        receive_thread.start()

                        send_thread.join()
                        receive_thread.join()

                        if self.connection:
                            self.connection.close()
                            self.connection = None

                        self.connected = False
                        self.running = False
                        self.status_var.set("Voice Chat: Waiting for connection...")

                        self.cleanup_audio()

                    except socket.timeout:
                        continue
                    except Exception as e:
                        print(f"Error in voice server loop: {e}")
                        break

            except Exception as e:
                print(f"Voice server error: {e}")
                self.status_var.set(f"Voice Chat: Error - {e}")
            finally:
                if self.server_socket:
                    self.server_socket.close()
                    self.server_socket = None

        server_thread_handle = threading.Thread(target=server_thread)
        server_thread_handle.daemon = True
        server_thread_handle.start()

    def send_audio(self):
        try:
            while self.running:
                if self.input_stream:
                    data = self.input_stream.read(CHUNK, exception_on_overflow=False)
                    if len(data) > 0:
                        signal = [int.from_bytes(data[i:i+2], byteorder='little', signed=True)
                                  for i in range(0, len(data), 2)]
                        rms = sum(x*x for x in signal) / len(signal) if signal else 0
                        self.audio_level = min(100, int(rms / 100))

                    if self.connection:
                        self.connection.sendall(data)
        except (ConnectionResetError, BrokenPipeError) as e:
            print(f"Error sending audio: {e}")
        except IOError as e:
            print(f"Audio stream error: {e}")
        except Exception as e:
            print(f"Send audio error: {e}")
        finally:
            self.running = False

    def receive_audio(self):
        try:
            while self.running:
                if self.connection and self.output_stream:
                    data = self.connection.recv(CHUNK)
                    if not data:
                        print("Peer disconnected.")
                        break
                    self.output_stream.write(data)
        except (ConnectionResetError, BrokenPipeError) as e:
            print(f"Error receiving audio: {e}")
        except IOError as e:
            print(f"Audio stream error: {e}")
        except Exception as e:
            print(f"Receive audio error: {e}")
        finally:
            self.running = False

    def cleanup(self):
        self.stop_event.set()
        if self.connection:
            try:
                self.connection.close()
            except:
                pass
            self.connection = None

        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            self.server_socket = None

        self.cleanup_audio()
        print("Voice chat resources cleaned up")
