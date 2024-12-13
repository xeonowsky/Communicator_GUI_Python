import wx
import socket
import threading
import json
import os
import base64
from PIL import Image
import io


class ChatClient(wx.Frame):
    def __init__(self, *args, **kwargs):
        super(ChatClient, self).__init__(*args, **kwargs)

        self.username = None
        self.current_room = None
        self.client_socket = None
        self.connected = False
        self.selected_color = wx.Colour(0, 0, 0)
        self.emoji_list = ["😊", "😂", "😍", "😎", "😢", "😡"]

        self.InitUI()

    def InitUI(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        self.chat_area = wx.BoxSizer(wx.VERTICAL)
        self.chat_display = wx.ScrolledWindow(panel, style=wx.VSCROLL)
        self.chat_display.SetScrollRate(5, 5)
        self.chat_display.SetSizer(self.chat_area)
        vbox.Add(self.chat_display, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)

        hbox = wx.BoxSizer(wx.HORIZONTAL)
        self.message_input = wx.TextCtrl(panel)
        send_button = wx.Button(panel, label="Send")
        send_emoji_button = wx.Button(panel, label="Send Emoji")
        send_file_button = wx.Button(panel, label="Send File")
        hbox.Add(self.message_input, proportion=1, flag=wx.EXPAND)
        hbox.Add(send_button, proportion=0, flag=wx.LEFT, border=5)
        hbox.Add(send_emoji_button, proportion=0, flag=wx.LEFT, border=5)
        hbox.Add(send_file_button, proportion=0, flag=wx.LEFT, border=5)
        vbox.Add(hbox, proportion=0, flag=wx.EXPAND | wx.ALL, border=5)

        room_box = wx.BoxSizer(wx.HORIZONTAL)
        self.room_list = wx.ListBox(panel)
        self.join_button = wx.Button(panel, label="Join Room")
        self.create_button = wx.Button(panel, label="Create Room")
        self.exit_button = wx.Button(panel, label="Exit")
        self.color_button = wx.Button(panel, label="Set Color", style=wx.BU_EXACTFIT)
        self.color_button.Disable()
        room_box.Add(self.room_list, proportion=1, flag=wx.EXPAND)
        room_box.Add(self.join_button, proportion=0, flag=wx.LEFT, border=5)
        room_box.Add(self.create_button, proportion=0, flag=wx.LEFT, border=5)
        room_box.Add(self.exit_button, proportion=0, flag=wx.LEFT, border=5)
        room_box.Add(self.color_button, proportion=0, flag=wx.LEFT, border=5)
        vbox.Add(room_box, proportion=0, flag=wx.EXPAND | wx.ALL, border=5)

        panel.SetSizer(vbox)

        send_button.Bind(wx.EVT_BUTTON, self.OnSend)
        send_emoji_button.Bind(wx.EVT_BUTTON, self.OnSendEmoji)
        send_file_button.Bind(wx.EVT_BUTTON, self.OnSendFile)
        self.join_button.Bind(wx.EVT_BUTTON, self.OnJoinRoom)
        self.create_button.Bind(wx.EVT_BUTTON, self.OnCreateRoom)
        self.exit_button.Bind(wx.EVT_BUTTON, self.OnExit)
        self.color_button.Bind(wx.EVT_BUTTON, self.OnSetColor)

        self.SetTitle("Chat Client")
        self.SetSize((600, 400))
        self.Centre()

    def ConnectToServer(self, host='127.0.0.1', port=22345):
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((host, port))
            self.connected = True
            threading.Thread(target=self.ReceiveMessages, daemon=True).start()

            username_dialog = wx.TextEntryDialog(self, "Enter your username:", "Username")
            if username_dialog.ShowModal() == wx.ID_OK:
                self.username = username_dialog.GetValue()
                self.client_socket.send(json.dumps({"username": self.username}).encode('utf-8'))
        except Exception as e:
            wx.MessageBox(f"Unable to connect: {e}", "Error", wx.OK | wx.ICON_ERROR)
            self.connected = False

    def ReceiveMessages(self):
        while True:
            try:
                data = self.client_socket.recv(1024 * 10).decode('utf-8')
                if not data:
                    break
                response = json.loads(data)
                wx.CallAfter(self.HandleResponse, response)
            except Exception as e:
                print(f"Error: {e}")
                break

    def HandleResponse(self, response):

        if response["type"] == "message":
            room = response["room"]
            sender = response["sender"]
            message = response["message"]
            self.DisplayText(f"[{room}] {sender}: {message}")
            self.SaveMessageToFile(room, sender, message)  # Save to file
        elif response["type"] == "rooms":
            self.UpdateRoomList(response["rooms"])
        elif response["type"] == "users":
            users = response["users"]
            self.DisplayText(f"[INFO] Users in the room: {', '.join(users)}")

    def OnJoinRoom(self, event):

        if self.connected:
            selected_room = self.room_list.GetStringSelection()
            if selected_room:
                room_name = selected_room.split(' ')[0]
                try:
                    self.client_socket.send(json.dumps({
                        "command": "join",
                        "room": room_name
                    }).encode('utf-8'))
                    self.current_room = room_name
                    self.DisplayText(f"[INFO] You joined room: {room_name}")
                    self.color_button.Enable()
                    self.join_button.Hide()
                    self.create_button.Hide()
                    self.exit_button.SetLabel("Exit Room")
                except Exception as e:
                    wx.MessageBox(f"Error joining room: {e}", "Error", wx.OK | wx.ICON_ERROR)
            else:
                wx.MessageBox("Please select a room to join.", "Info", wx.OK | wx.ICON_INFORMATION)

    def OnSend(self, event):
        if self.current_room and self.message_input.GetValue():
            message = self.message_input.GetValue()
            try:
                self.client_socket.send(json.dumps({
                    "command": "message",
                    "room": self.current_room,
                    "message": message
                }).encode('utf-8'))

                # self.DisplayText(f"[{self.current_room}] {self.username}: {message}")
                self.SaveMessageToFile(self.current_room, self.username, message)
                self.message_input.Clear()
            except Exception as e:
                wx.MessageBox(f"Error sending message: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def SaveMessageToFile(self, room, sender, message):

        message_data = {"room": room, "sender": sender, "message": message}
        file_path = "received_files/rozmowy.json"


        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                chat_history = json.load(f)
        else:
            chat_history = []


        chat_history.append(message_data)


        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(chat_history, f, ensure_ascii=False, indent=4)

    def OnSendEmoji(self, event):
        emoji_dialog = wx.SingleChoiceDialog(self, "Choose an emoji:", "Emoticons", self.emoji_list)
        if emoji_dialog.ShowModal() == wx.ID_OK:
            emoji = emoji_dialog.GetStringSelection()
            if emoji:
                self.message_input.AppendText(emoji)

    def OnSendFile(self, event):

        with wx.FileDialog(self, "Select a file", wildcard="All files (*.*)|*.*",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as file_dialog:
            if file_dialog.ShowModal() == wx.ID_OK:
                file_path = file_dialog.GetPath()
                try:
                    with open(file_path, "rb") as file:
                        file_data = base64.b64encode(file.read()).decode("utf-8")
                        file_name = os.path.basename(file_path)
                        self.client_socket.send(json.dumps({
                            "command": "send_file",
                            "file_name": file_name,
                            "file_data": file_data
                        }).encode('utf-8'))
                        self.DisplayText(f"[File] {file_name} (Click to download)")
                except Exception as e:
                    wx.MessageBox(f"Error sending file: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def HandleFileResponse(self, file_name, file_data):

        file_data = base64.b64decode(file_data)
        file_path = os.path.join(os.getcwd(), file_name)
        try:
            with open(file_path, "wb") as file:
                file.write(file_data)
            wx.MessageBox(f"File {file_name} has been saved.", "File Received", wx.OK | wx.ICON_INFORMATION)
        except Exception as e:
            wx.MessageBox(f"Error saving file: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def DisplayText(self, text):
        text_label = wx.StaticText(self.chat_display, label=text)
        text_label.SetForegroundColour(self.selected_color)
        self.chat_area.Add(text_label, flag=wx.LEFT | wx.TOP, border=5)
        self.chat_display.FitInside()
        self.chat_display.Layout()
        self.chat_display.Scroll(-1, -1)

    def UpdateRoomList(self, rooms_info):
        self.room_list.Clear()
        for room_info in rooms_info:
            room_name = room_info["room"]
            users = ", ".join(room_info["users"])
            self.room_list.Append(f"{room_name} ({users})")

    def OnCreateRoom(self, event):
        if self.connected:
            room_dialog = wx.TextEntryDialog(self, "Enter room name to create:", "Create Room")
            if room_dialog.ShowModal() == wx.ID_OK:
                room_name = room_dialog.GetValue()
                try:
                    self.client_socket.send(json.dumps({
                        "command": "create",
                        "room": room_name
                    }).encode('utf-8'))
                    self.current_room = room_name
                    self.DisplayText(f"[INFO] Created room: {room_name}")
                except Exception as e:
                    wx.MessageBox(f"Error creating room: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def OnExit(self, event):

        try:
            if self.current_room:
                self.client_socket.send(json.dumps({
                    "command": "exit_room",
                    "room": self.current_room
                }).encode('utf-8'))

            self.client_socket.shutdown(socket.SHUT_RDWR)
            self.client_socket.close()
        except (ConnectionAbortedError, ConnectionResetError, OSError):

            pass
        finally:

            self.Destroy()

    def OnSetColor(self, event):
        color_data = wx.ColourData()
        dialog = wx.ColourDialog(self, color_data)
        if dialog.ShowModal() == wx.ID_OK:
            color = dialog.GetColourData().GetColour()
            self.selected_color = color


def send_username_to_server(username):

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect(('127.0.0.1', 22345))

    username_data = json.dumps({"username": username}).encode('utf-8')
    client_socket.send(username_data)

    response = json.loads(client_socket.recv(1024).decode('utf-8'))
    print(response)
    client_socket.close()


send_username_to_server("TestUser")

if __name__ == "__main__":
    app = wx.App()
    client = ChatClient(None)
    client.ConnectToServer()
    client.Show()
    app.MainLoop()