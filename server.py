import socket
import threading
import json
import os


rooms = {}
clients = {}
history_file = "rozmowy.json"


def save_message(room, sender, message):

    data = {"room": room, "sender": sender, "message": message}
    if os.path.exists(history_file):
        with open(history_file, "r", encoding="utf-8") as f:
            history = json.load(f)
    else:
        history = []
    history.append(data)
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=4)


def broadcast_message(room, message, sender, is_image=False, file_data=None, file_name=None):

    for client in clients.values():
        if client['room'] == room:
            try:
                msg_data = {
                    "type": "message" if not is_image else "image",
                    "room": room,
                    "sender": sender,
                    "message": message if not is_image else "",
                    "image": message if is_image else "",
                    "file_name": file_name if file_data else "",
                    "file_data": file_data if file_data else "",
                }
                client['socket'].send(json.dumps(msg_data).encode('utf-8'))
            except Exception as e:
                print(f"Error broadcasting message: {e}")


def handle_client(client_socket, client_address):
    username = None
    try:

        data = json.loads(client_socket.recv(1024).decode('utf-8'))
        username = data.get("username")

        
        if not username or username in clients:
            client_socket.send(
                json.dumps({"type": "error", "message": "Nazwa użytkownika jest pusta lub zajęta."}).encode('utf-8'))
            client_socket.close()
            return


        clients[username] = {'socket': client_socket, 'address': client_address, 'room': None}
        print(f"[INFO] {username} połączono z {client_address}.")


        broadcast_rooms()


        while True:
            data = json.loads(client_socket.recv(4096).decode('utf-8'))
            command = data.get("command")

            if command == "message":
                room = data.get("room")
                message = data.get("message")
                if room and message:
                    save_message(room, username, message)
                    broadcast_message(room, message, username)

            elif command == "create":
                room_name = data.get("room")
                if room_name:
                    if room_name not in rooms:
                        rooms[room_name] = {'users': []}
                        broadcast_rooms()
                        client_socket.send(
                            json.dumps({"type": "success", "message": f"Pokój {room_name} został utworzony."}).encode(
                                'utf-8'))
                    else:
                        client_socket.send(
                            json.dumps({"type": "error", "message": "Pokój już istnieje."}).encode('utf-8'))

            elif command == "join":
                room_name = data.get("room")
                if room_name in rooms:
                    client_socket.send(
                        json.dumps({"type": "success", "message": f"Dołączono do pokoju {room_name}."}).encode('utf-8'))
                    clients[username]['room'] = room_name
                    rooms[room_name]['users'].append(username)
                    broadcast_message(room_name, f"{username} dołączył do pokoju.", "Server")
                else:
                    client_socket.send(json.dumps({"type": "error", "message": "Pokój nie istnieje."}).encode('utf-8'))

            elif command == "send_file":
                file_name = data.get("file_name")
                file_data = data.get("file_data")
                room = clients[username]['room']
                if room:
                    broadcast_message(room, f"[File] {file_name}", username, file_data=file_data, file_name=file_name)

            elif command == "exit_room":
                room_name = data.get("room")
                if room_name and username in rooms.get(room_name, {}).get("users", []):
                    rooms[room_name]["users"].remove(username)
                    clients[username]['room'] = None
                    broadcast_message(room_name, f"{username} opuścił pokój.", "Server")

    except Exception as e:
        print(f"Error handling client: {e}")
    finally:
        if username and username in clients:
            del clients[username]
        client_socket.close()


def broadcast_rooms():

    rooms_info = []
    for room_name, room in rooms.items():
        rooms_info.append({"room": room_name, "users": room["users"]})
    for client in clients.values():
        try:
            client['socket'].send(json.dumps({"type": "rooms", "rooms": rooms_info}).encode('utf-8'))
        except Exception as e:
            print(f"Error broadcasting rooms: {e}")


def start_server(host='127.0.0.1', port=22345):

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((host, port))
    server_socket.listen(5)
    print(f"Server running on {host}:{port}...")

    while True:
        client_socket, client_address = server_socket.accept()
        threading.Thread(target=handle_client, args=(client_socket, client_address), daemon=True).start()


start_server()