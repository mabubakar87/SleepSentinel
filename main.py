import time
import psutil
import ctypes
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import traceback
from pynput import mouse, keyboard
import ttkbootstrap as tb
import logging
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageTk
import math

# Configure logging
log_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(log_dir, "log.txt")
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Clear the log file at the start of the application
with open(log_file, 'w') as f:
    f.truncate(0)

# Log application start
logging.info("=" * 50)
logging.info("Application started")
logging.info("=" * 50)

# Windows API for sleep prevention
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
SetThreadExecutionState = ctypes.windll.kernel32.SetThreadExecutionState

# Constants
CHECK_INTERVAL = 1  # Interval to check network speed (in seconds)
TIMER_REFRESH_INTERVAL = 500  # GUI timer refresh interval (in milliseconds)
DEFAULT_SPEED_THRESHOLD = 10  # Default threshold in Mbps
DEFAULT_INACTIVITY_LIMIT = 60  # Default inactivity time in seconds (1 minutes)

# Global Variables
last_activity_time = time.time()
download_speed = 0  # Network speed in Mbps
upload_speed = 0  # Upload speed in Mbps
monitoring_active = False  # Flag to control monitoring
lock = threading.Lock()  # Thread lock to prevent race conditions
stop_event = threading.Event()  # Event to signal threads to stop

# Log configuration settings
logging.info(f"Configuration: CHECK_INTERVAL={CHECK_INTERVAL}s, DEFAULT_SPEED_THRESHOLD={DEFAULT_SPEED_THRESHOLD}Mbps, DEFAULT_INACTIVITY_LIMIT={DEFAULT_INACTIVITY_LIMIT}s")

def get_network_speed():
    """Measure download and upload speed in Mbps."""
    global download_speed, upload_speed
    logging.info("Network speed monitoring thread started")
    while not stop_event.is_set():
        try:
            old_bytes_down = psutil.net_io_counters().bytes_recv
            old_bytes_up = psutil.net_io_counters().bytes_sent
            time.sleep(CHECK_INTERVAL)
            new_bytes_down = psutil.net_io_counters().bytes_recv
            new_bytes_up = psutil.net_io_counters().bytes_sent
            with lock:
                download_speed = ((new_bytes_down - old_bytes_down) * 8) / (CHECK_INTERVAL * 1_000_000)  # Convert to Mbps
                upload_speed = ((new_bytes_up - old_bytes_up) * 8) / (CHECK_INTERVAL * 1_000_000)  # Convert to Mbps
                logging.debug(f"Current speeds - Download: {download_speed:.2f} Mbps, Upload: {upload_speed:.2f} Mbps")
        except Exception as e:
            error_msg = f"Error in get_network_speed: {e}"
            logging.error(error_msg)
            logging.error(traceback.format_exc())

def on_activity(event=None):
    """Reset inactivity timer on mouse/keyboard activity."""
    global last_activity_time
    with lock:
        last_activity_time = time.time()
        logging.debug(f"User activity detected, reset timer at {datetime.fromtimestamp(last_activity_time).strftime('%H:%M:%S')}")

def start_listeners():
    """Start mouse and keyboard listeners in a separate thread."""
    logging.info("Starting mouse and keyboard listeners")
    mouse_listener = mouse.Listener(on_move=on_activity, on_click=on_activity, on_scroll=on_activity)
    keyboard_listener = keyboard.Listener(on_press=on_activity)
    mouse_listener.start()
    keyboard_listener.start()
    while not stop_event.is_set():
        time.sleep(1)  # Keep the thread alive
    logging.info("Stopping mouse and keyboard listeners")
    mouse_listener.stop()
    keyboard_listener.stop()
    logging.info("Mouse and keyboard listeners stopped")

def force_system_sleep():
    """Force the system to go to sleep and stop the application."""
    global monitoring_active
    logging.info("Forcing system to sleep and stopping the application.")

    try:
        # Stop monitoring and cleanup resources
        monitoring_active = False
        stop_event.set()
        SetThreadExecutionState(ES_CONTINUOUS)  # Reset system execution state

        # Force the system to sleep
        if os.name == 'nt':  # Windows
            os.system('rundll32.exe powrprof.dll,SetSuspendState 0,1,0')
        else:  # Linux/Unix
            os.system('systemctl suspend')

        # Exit the application
        logging.info("Application is stopping.")
        os._exit(0)  # Forcefully exit the application
    except Exception as e:
        logging.error(f"Error forcing sleep: {e}")
        logging.error(traceback.format_exc())

# GUI Class
class NetworkMonitorGUI:
    def __init__(self, root):
        logging.info("Initializing GUI")
        self.root = root
        self.root.title("Sleep Sentinel")
        self.root.geometry("800x620")
        self.root.style.theme_use("superhero")  # Use a modern theme

        # Create main container with padding
        self.main_container = tb.Frame(root, padding=20)
        self.main_container.pack(fill="both", expand=True)

        # Header Section
        self.header_frame = tb.Frame(self.main_container)
        self.header_frame.pack(fill="x", pady=(0, 10))

        self.title_label = tb.Label(
            self.header_frame,
            text="Sleep Sentinel",
            font=("Arial", 28, "bold"),
            bootstyle="primary"
        )
        self.title_label.pack(side="left")

        # Define a style for the buttons
        style = tb.Style()
        style.configure('Custom.TButton', font=('Arial', 13))

        # Ensure consistent button style across themes
        self.root.style.configure('TButton', font=('Arial', 13))

        # Help Button
        self.help_button = tb.Button(
            self.header_frame,
            text="Help",
            command=self.show_help,
            bootstyle="info",
            padding=(10, 5),
            style='Custom.TButton'  # Apply custom style
        )
        self.help_button.pack(side="right", padx=10)

        # View Logs Button
        self.logs_button = tb.Button(
            self.header_frame,
            text="View Logs",
            command=self.view_logs,
            bootstyle="info",
            padding=(10, 5),
            style='Custom.TButton'  # Apply custom style
        )
        self.logs_button.pack(side="right", padx=10)

        # Ensure consistent button style across themes
        self.root.style.configure('Custom.TButton', font=('Arial', 10))  # Set font size for both buttons

        # Dark/Light Mode Toggle
        self.mode_toggle_frame = tb.Frame(self.header_frame)
        self.mode_toggle_frame.pack(side="right", padx=10, pady=(10, 0))

        self.mode_label = tb.Label(
            self.mode_toggle_frame,
            text="🌙 Dark Mode",
            font=("Arial", 13)
        )
        self.mode_label.pack(side="left")

        self.mode_toggle = tb.Checkbutton(
            self.mode_toggle_frame,
            bootstyle="round-toggle",
            command=self.toggle_dark_mode
        )
        self.mode_toggle.pack(side="right")

        # Settings Section
        self.settings_frame = tb.LabelFrame(
            self.main_container,
            text="Settings",
            padding=15,
            bootstyle="primary"
        )
        self.settings_frame.pack(fill="x", pady=(0, 10))

        # Timer Input
        self.timer_frame = tb.Frame(self.settings_frame)
        self.timer_frame.pack(fill="x", pady=5)

        self.timer_input_label = tb.Label(
            self.timer_frame,
            text="Inactivity Timer (sec):",
            font=("Arial", 12, "bold")
        )
        self.timer_input_label.pack(side="left")

        self.timer_entry = tb.Entry(
            self.timer_frame,
            font=("Arial", 13),
            width=10
        )
        self.timer_entry.insert(0, str(DEFAULT_INACTIVITY_LIMIT))
        self.timer_entry.pack(side="right")

        # Download Threshold
        self.download_frame = tb.Frame(self.settings_frame)
        self.download_frame.pack(fill="x", pady=5)

        self.download_threshold_label = tb.Label(
            self.download_frame,
            text="Download Threshold (Mbps):",
            font=("Arial", 12, "bold")
        )
        self.download_threshold_label.pack(side="left")

        self.download_threshold_entry = tb.Entry(
            self.download_frame,
            font=("Arial", 13),
            width=10
        )
        self.download_threshold_entry.insert(0, str(DEFAULT_SPEED_THRESHOLD))
        self.download_threshold_entry.pack(side="right")

        # Upload Threshold
        self.upload_frame = tb.Frame(self.settings_frame)
        self.upload_frame.pack(fill="x", pady=5)

        self.upload_threshold_label = tb.Label(
            self.upload_frame,
            text="Upload Threshold (Mbps):",
            font=("Arial", 12, "bold")
        )
        self.upload_threshold_label.pack(side="left")

        self.upload_threshold_entry = tb.Entry(
            self.upload_frame,
            font=("Arial", 13),
            width=10
        )
        self.upload_threshold_entry.insert(0, str(DEFAULT_SPEED_THRESHOLD))
        self.upload_threshold_entry.pack(side="right")

        # Status Section
        self.status_frame = tb.LabelFrame(
            self.main_container,
            text="Monitoring Status",
            padding=10,
            bootstyle="primary"
        )
        self.status_frame.pack(fill="x", pady=(0, 5))

        # Network Speed Meters
        self.speed_frame = tb.Frame(self.status_frame)
        self.speed_frame.pack(fill="x", pady=(0, 10))

        # Download Speed Meter
        self.download_meter_frame = tb.Frame(self.speed_frame)
        self.download_meter_frame.pack(side="left", expand=True, fill="x", padx=5)

        self.download_label = tb.Label(
            self.download_meter_frame,
            text="Download Speed",
            font=("Arial", 12, "bold")
        )
        self.download_label.pack()

        self.download_speed_label = tb.Label(
            self.download_meter_frame,
            text="0 Mbps",
            font=("Arial", 16)
        )
        self.download_speed_label.pack()

        self.download_meter = ttk.Progressbar(
            self.download_meter_frame,
            length=200,
            mode="determinate",
            style="success.Horizontal.TProgressbar"
        )
        self.download_meter.pack(pady=5)

        # Upload Speed Meter
        self.upload_meter_frame = tb.Frame(self.speed_frame)
        self.upload_meter_frame.pack(side="right", expand=True, fill="x", padx=5)

        self.upload_label = tb.Label(
            self.upload_meter_frame,
            text="Upload Speed",
            font=("Arial", 12, "bold")
        )
        self.upload_label.pack()

        self.upload_speed_label = tb.Label(
            self.upload_meter_frame,
            text="0 Mbps",
            font=("Arial", 16)
        )
        self.upload_speed_label.pack()

        self.upload_meter = ttk.Progressbar(
            self.upload_meter_frame,
            length=200,
            mode="determinate",
            style="info.Horizontal.TProgressbar"
        )
        self.upload_meter.pack(pady=5)

        # Timer Section
        self.timer_display_frame = tb.Frame(self.status_frame)
        self.timer_display_frame.pack(fill="x", pady=10)

        self.timer_label = tb.Label(
            self.timer_display_frame,
            text="Time Until Sleep",
            font=("Arial", 12, "bold")
        )
        self.timer_label.pack()

        self.time_remaining_label = tb.Label(
            self.timer_display_frame,
            text="--",
            font=("Arial", 24, "bold")
        )
        self.time_remaining_label.pack()

        self.timer_progress = ttk.Progressbar(
            self.timer_display_frame,
            orient="horizontal",
            length=400,
            mode="determinate",
            style="primary.Horizontal.TProgressbar"
        )
        self.timer_progress.pack(pady=5)

        # Status Message
        self.status_label = tb.Label(
            self.status_frame,
            text="Status: Waiting to start...",
            font=("Arial", 13),
            bootstyle="info"
        )
        self.status_label.pack(pady=10)

        # Control Button
        self.toggle_button = tk.Button(
            self.main_container,
            text="Start",
            command=self.toggle_monitoring,
            font=("Arial", 16),  # Match text size with 'Upload Speed'
            bg="#28a745",  # Success color
            fg="white",
            relief="flat",
            highlightthickness=0,
            bd=0,
            padx=20,
            pady=10  # Add padding for rounded effect
        )
        self.toggle_button.pack(pady=10, side="bottom", anchor="center")
        self.toggle_button.config(highlightbackground="#28a745", highlightcolor="#28a745")

        # Set initial button color to green
        self.toggle_button.config(bg="#28a745")

        # Start background processes
        threading.Thread(target=get_network_speed, daemon=True).start()
        threading.Thread(target=start_listeners, daemon=True).start()
        self.update_timer()

    def show_help(self):
        """Display help information."""
        messagebox.showinfo(
            "Help",
            "Sleep Sentinel monitors network activity and prevents your system from sleeping.\n\n"
            "1. Set the inactivity timer (in seconds).\n"
            "2. Set download/upload speed thresholds (in Mbps).\n"
            "3. Start monitoring to keep your system awake during active network usage.\n\n"
            "Note: The system will sleep if both network speeds are below the thresholds and the timer expires."
        )

    def view_logs(self):
        """Open the log file in a new window."""
        try:
            with open(log_file, "r") as f:
                logs = f.read()
            log_window = tk.Toplevel(self.root)
            log_window.title("Logs")
            log_window.geometry("750x500")  # Set window size to 800x600
            log_text = tk.Text(log_window, wrap="word", font=("Arial", 10))
            log_text.insert("1.0", logs)
            log_text.config(state="disabled")
            log_text.pack(fill="both", expand=True, padx=10, pady=10)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open logs: {e}")

    def monitor_network(self):
        """Monitor network speed and inactivity, preventing sleep if conditions are met."""
        global monitoring_active, last_activity_time
        logging.info(f"Network monitoring thread started with thresholds - Download: {self.download_threshold} Mbps, Upload: {self.upload_threshold} Mbps")
        while monitoring_active and not stop_event.is_set():
            with lock:
                inactivity_duration = time.time() - last_activity_time
                # Reset timer if either download or upload speed exceeds threshold
                if download_speed >= self.download_threshold or upload_speed >= self.upload_threshold:
                    last_activity_time = time.time()
                    logging.info(f"Timer reset due to high network activity - Download: {download_speed:.2f} Mbps, Upload: {upload_speed:.2f} Mbps")
                
                # Check if timer has run out and both speeds are below thresholds
                if (inactivity_duration >= self.inactivity_limit and 
                    download_speed < self.download_threshold and 
                    upload_speed < self.upload_threshold):
                    logging.info(f"Timer expired - Inactivity: {inactivity_duration:.1f}s, Download: {download_speed:.2f} Mbps, Upload: {upload_speed:.2f} Mbps")
                    self.status_label.config(text="Status: Timer expired. System going to sleep...", bootstyle="warning")
                    self.root.update()
                    time.sleep(2)
                    force_system_sleep()
                    break
            
            time.sleep(1)
        logging.info("Network monitoring thread stopped")

    def validate_inputs(self):
        """Validate user inputs for inactivity timer and speed thresholds."""
        try:
            inactivity_limit = int(self.timer_entry.get())
            download_threshold = float(self.download_threshold_entry.get())
            upload_threshold = float(self.upload_threshold_entry.get())

            if inactivity_limit <= 0 or download_threshold < 0 or upload_threshold < 0:
                raise ValueError("Values must be positive.")

            return True
        except ValueError as e:
            error_msg = f"Invalid input: {str(e)}"
            logging.error(error_msg)
            messagebox.showerror("Invalid Input", "Please enter valid positive numbers.")
            return False








    def toggle_monitoring(self):
        """Toggle monitoring on and off."""
        global monitoring_active, last_activity_time
        try:
            if monitoring_active:
                monitoring_active = False
                SetThreadExecutionState(ES_CONTINUOUS)  # Reset execution state
                self.toggle_button.config(text="Start", bg="#28a745")
                self.status_label.config(text="Status: Stopped.", bootstyle="danger")
                logging.info("Monitoring stopped by user")
            else:
                if not self.validate_inputs():
                    return

                self.inactivity_limit = int(self.timer_entry.get())
                self.download_threshold = float(self.download_threshold_entry.get())
                self.upload_threshold = float(self.upload_threshold_entry.get())
                logging.info(f"Starting monitoring with settings - Inactivity: {self.inactivity_limit}s, "
                           f"Download threshold: {self.download_threshold} Mbps, "
                           f"Upload threshold: {self.upload_threshold} Mbps")
                monitoring_active = True
                with lock:
                    last_activity_time = time.time()
                    logging.info(f"Reset activity timer to {datetime.fromtimestamp(last_activity_time).strftime('%Y-%m-%d %H:%M:%S')}")
                self.toggle_button.config(text="Stop", bg="#dc3545")
                self.status_label.config(text="Status: Monitoring...", bootstyle="info")
                threading.Thread(target=self.monitor_network, daemon=True).start()
        except ValueError as e:
            error_msg = f"Invalid input values: {str(e)}"
            logging.error(error_msg)
            self.timer_entry.delete(0, tk.END)
            self.timer_entry.insert(0, str(DEFAULT_INACTIVITY_LIMIT))
            self.download_threshold_entry.delete(0, tk.END)
            self.download_threshold_entry.insert(0, str(DEFAULT_SPEED_THRESHOLD))
            self.upload_threshold_entry.delete(0, tk.END)
            self.upload_threshold_entry.insert(0, str(DEFAULT_SPEED_THRESHOLD))
            self.status_label.config(text="Invalid input! Using default values.", bootstyle="warning")
            logging.info(f"Reset to default values - Inactivity limit: {DEFAULT_INACTIVITY_LIMIT}s, Download threshold: {DEFAULT_SPEED_THRESHOLD} Mbps, Upload threshold: {DEFAULT_SPEED_THRESHOLD} Mbps")
        except Exception as e:
            error_msg = f"Error in toggle_monitoring: {str(e)}"
            logging.error(error_msg)
            logging.error(traceback.format_exc())
            self.status_label.config(text=f"Error: {str(e)}", bootstyle="danger")

    def update_timer(self):
        """Update the countdown timer and speed meters in real-time."""
        if monitoring_active:
            with lock:
                inactivity_duration = time.time() - last_activity_time
            time_remaining = max(0, self.inactivity_limit - inactivity_duration)
            minutes = int(time_remaining) // 60
            seconds = int(time_remaining) % 60
            self.time_remaining_label.config(text=f"{minutes:02d}:{seconds:02d}")
            self.timer_progress["value"] = (time_remaining / self.inactivity_limit) * 100

            # Dynamically scale progress bars based on observed speeds
            max_speed = max(download_speed, upload_speed, 100)  # Ensure minimum range of 100 Mbps
            self.download_speed_label.config(text=f"{download_speed:.1f} Mbps")
            self.upload_speed_label.config(text=f"{upload_speed:.1f} Mbps")
            self.download_meter["maximum"] = max_speed
            self.upload_meter["maximum"] = max_speed
            self.download_meter["value"] = download_speed
            self.upload_meter["value"] = upload_speed
        else:
            self.time_remaining_label.config(text="--:--")
            self.timer_progress["value"] = 0
            self.download_meter["value"] = 0
            self.upload_meter["value"] = 0
            self.download_speed_label.config(text="0 Mbps")
            self.upload_speed_label.config(text="0 Mbps")
        self.root.after(TIMER_REFRESH_INTERVAL, self.update_timer)

    def toggle_dark_mode(self):
        """Toggle between light and dark mode."""
        if self.root.style.theme_use() == "superhero":
            self.root.style.theme_use("flatly")
            self.root.configure(bg="#7D8B92")  # Set light mode to a slightly grey background
            self.mode_label.config(text="☀️ Light Mode")
            if monitoring_active:
                self.toggle_button.config(bg="#dc3545")  # Ensure Stop button remains red when active
            else:
                self.toggle_button.config(bg="#28a745")  # Ensure Start button remains green when inactive
        else:
            self.root.style.theme_use("superhero")
            self.root.configure(bg="#2b2b2b")  # Ensure dark mode has a dark background
            self.mode_label.config(text="🌙 Dark Mode")
            if monitoring_active:
                self.toggle_button.config(bg="#dc3545")  # Ensure Stop button remains red when active
            else:
                self.toggle_button.config(bg="#28a745")  # Ensure Start button remains green when inactive


    def cleanup(self):
        """Clean up resources and stop all threads."""
        global monitoring_active
        logging.info("Starting application cleanup.")
        monitoring_active = False  # Stop the monitoring thread
        stop_event.set()  # Signal all threads to stop
        SetThreadExecutionState(ES_CONTINUOUS)  # Reset system execution state
        logging.info("Application cleanup complete.")

# Start GUI
if __name__ == "__main__":
    root = tb.Window(themename="flatly")
    app = NetworkMonitorGUI(root)
    try:
        logging.info("Entering main event loop")
        root.mainloop()
    except Exception as e:
        error_msg = f"Unhandled exception in main thread: {str(e)}"
        logging.critical(error_msg)
        logging.critical(traceback.format_exc())
        messagebox.showerror("Critical Error", f"An unhandled error occurred: {str(e)}\nSee log.txt for details.")
    finally:
        logging.info("Application shutting down")
        app.cleanup()  # Call cleanup to stop threads and reset system state
        stop_event.set()
        SetThreadExecutionState(ES_CONTINUOUS)
        logging.info("Reset system execution state")
        logging.info("=" * 50)