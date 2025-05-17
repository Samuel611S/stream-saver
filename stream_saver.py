from pytubefix import YouTube
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import threading
import os
import subprocess
import re
import sys

# --- Helper function for resource paths ---
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and PyInstaller """
    try:
        base_path = sys._MEIPASS  # PyInstaller temp folder
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- Throttle variable ---
last_update_percent = 0

def choose_folder():
    folder = filedialog.askdirectory()
    if folder:
        folder_path.set(folder)

def fetch_streams():
    url = url_entry.get()
    if not url:
        messagebox.showwarning("Missing URL", "Please enter a YouTube URL.")
        return
    try:
        yt = YouTube(url)
        video_streams = yt.streams.filter(adaptive=True, only_video=True, file_extension="mp4").order_by('resolution').desc()
        resolution_choices.clear()
        for stream in video_streams:
            res = stream.resolution
            if res and res not in resolution_choices:
                resolution_choices.append(res)
        resolution_dropdown['values'] = resolution_choices
        resolution_dropdown.current(0)
        status_label.config(text="Streams loaded.", bootstyle="success")
    except Exception as e:
        messagebox.showerror("Error", str(e))

def on_progress(stream, chunk, bytes_remaining):
    global last_update_percent
    total_size = stream.filesize
    bytes_downloaded = total_size - bytes_remaining
    percentage = int(bytes_downloaded / total_size * 100)

    if percentage > last_update_percent:
        last_update_percent = percentage
        progress_bar['value'] = percentage

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name)

def save_to_history(title, resolution, audio_only, path):
    history_file = resource_path("history.txt")
    with open(history_file, "a", encoding="utf-8") as f:
        f.write(f"{title} | {'Audio Only' if audio_only else resolution} | {path}\n")

def show_history():
    history_file = resource_path("history.txt")
    if os.path.exists(history_file):
        with open(history_file, "r", encoding="utf-8") as f:
            content = f.read()
        messagebox.showinfo("Download History", content)
    else:
        messagebox.showinfo("Download History", "No downloads yet.")

def download_video_thread():
    global last_update_percent
    url = url_entry.get()
    save_path = folder_path.get()
    selected_res = resolution_var.get()
    audio_only = audio_var.get()

    if not url or not save_path:
        messagebox.showwarning("Missing Input", "Please enter a URL and select a folder.")
        return

    try:
        yt = YouTube(url, on_progress_callback=on_progress)
        title = sanitize_filename(yt.title)
        status_label.config(text="Downloading...", bootstyle="info")

        if audio_only:
            audio_stream = yt.streams.filter(only_audio=True, mime_type="audio/mp4").first()
            if not audio_stream:
                status_label.config(text="No audio stream found.", bootstyle="danger")
                return
            audio_stream.download(output_path=save_path, filename=f"{title}_audio.mp4")
            status_label.config(text="Audio downloaded successfully!", bootstyle="success")
            save_to_history(title, "Audio", True, save_path)
        else:
            video_stream = yt.streams.filter(res=selected_res, mime_type="video/mp4", adaptive=True).first()
            audio_stream = yt.streams.filter(only_audio=True, mime_type="audio/mp4").first()
            if not video_stream or not audio_stream:
                status_label.config(text="Stream not found.", bootstyle="danger")
                return

            video_path = os.path.join(save_path, "temp_video.mp4")
            audio_path = os.path.join(save_path, "temp_audio.mp4")
            output_path = os.path.join(save_path, f"{title}.mp4")

            video_stream.download(output_path=save_path, filename="temp_video.mp4")
            audio_stream.download(output_path=save_path, filename="temp_audio.mp4")

            ffmpeg_path = resource_path("ffmpeg.exe")
            command = [ffmpeg_path, "-y", "-i", video_path, "-i", audio_path, "-c:v", "copy", "-c:a", "aac", "-strict", "experimental", output_path]
            result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if result.returncode == 0:
                os.remove(video_path)
                os.remove(audio_path)
                status_label.config(text="Download complete!", bootstyle="success")
                save_to_history(title, selected_res, False, save_path)
            else:
                status_label.config(text="FFmpeg failed to merge files.", bootstyle="danger")

        progress_bar['value'] = 0
        last_update_percent = 0

    except Exception as e:
        status_label.config(text=f"Error: {e}", bootstyle="danger")

def start_download():
    thread = threading.Thread(target=download_video_thread)
    thread.start()

# --- GUI Setup ---
root = tb.Window(themename="darkly")
root.title("Stream Saver")
root.geometry("520x520")
root.resizable(False, False)
root.iconbitmap(resource_path("icon.ico"))

folder_path = tb.StringVar()
resolution_var = tb.StringVar()
audio_var = tb.BooleanVar()
resolution_choices = []

main_frame = tb.Frame(root)
main_frame.pack(fill=BOTH, expand=True)

canvas = tb.Canvas(main_frame)
scrollbar = tb.Scrollbar(main_frame, orient=VERTICAL, command=canvas.yview)
scrollable_frame = tb.Frame(canvas)

scrollable_frame.bind(
    "<Configure>",
    lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
)

canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
canvas.configure(yscrollcommand=scrollbar.set)
canvas.pack(side=LEFT, fill=BOTH, expand=True)
scrollbar.pack(side=RIGHT, fill=Y)

logo_img = Image.open(resource_path("logo.png")).resize((60, 60))
logo_photo = ImageTk.PhotoImage(logo_img)
logo_label = tb.Label(scrollable_frame, image=logo_photo)
logo_label.image = logo_photo
logo_label.pack()

tb.Label(scrollable_frame, text="YouTube URL:").pack(anchor=W)
url_entry = tb.Entry(scrollable_frame, width=60)
url_entry.pack(pady=5)

tb.Button(scrollable_frame, text="Load Resolutions", command=fetch_streams, bootstyle="primary").pack(pady=5)

tb.Label(scrollable_frame, text="Select Resolution:").pack(anchor=W, pady=(10, 0))
resolution_dropdown = tb.Combobox(scrollable_frame, textvariable=resolution_var, state="readonly", width=30)
resolution_dropdown.pack()

tb.Checkbutton(scrollable_frame, text="Audio Only", variable=audio_var, bootstyle="secondary").pack(pady=(10, 10))

tb.Button(scrollable_frame, text="Choose Folder", command=choose_folder, bootstyle="info").pack()
tb.Label(scrollable_frame, textvariable=folder_path, bootstyle="secondary").pack()

progress_bar = tb.Progressbar(scrollable_frame, orient=HORIZONTAL, length=400, mode='determinate', bootstyle="success-striped")
progress_bar.pack(pady=15)

tb.Button(scrollable_frame, text="Download", command=start_download, bootstyle="success").pack(pady=5)
tb.Button(scrollable_frame, text="View History", command=show_history, bootstyle="info").pack(pady=(0, 10))

status_label = tb.Label(scrollable_frame, text="", font=("Segoe UI", 10))
status_label.pack(pady=(10, 0))

root.mainloop()
