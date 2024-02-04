import tkinter as tk
from tkinter import messagebox
import json
import os
import time
import logging
from logging.handlers import RotatingFileHandler
import threading
import datetime
import configparser

config = configparser.ConfigParser()
config.read('events.ini')

# Placeholder for system tray integration
# (Actual implementation might require additional libraries or macOS-specific code)

# Setting up logging with timestamp
log_dir = config.get('Logging', 'log_dir')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, config.get('Logging', 'log_file'))

# Create a logging format that includes the timestamp
log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt=config.get('Format', 'datetime'))

logger = logging.getLogger('EventLogger')
logger.setLevel(logging.INFO)

handler = RotatingFileHandler(log_file, maxBytes=config.getint('Logging', 'max_bytes'), backupCount=config.getint('Logging', 'backup_count'))
handler.setFormatter(log_format)  # Apply the logging format to our handler
logger.addHandler(handler)

# Function to read events from JSON
def read_events():
    try:
        with open(config.get('Events', 'json_file'), "r") as file:
            return json.load(file)
    except Exception as e:
        logger.error(f"Error reading JSON file: {e}")
        return []

# Function to calulate time to next event
def calculate_time_to_next_event(current_time, events):
    # Convert current time to a datetime object for comparison
    now = datetime.datetime.now()
    current_time_dt = datetime.datetime.strptime(current_time, config.get('Format', 'time')).replace(year=now.year, month=now.month, day=now.day)
    next_event_dt = None  # This will store the datetime of the next event

    # Sort events by time and find the next event's datetime
    sorted_events = sorted(events, key=lambda x: datetime.datetime.strptime(x['time'], config.get('Format', 'time')))
    for event in sorted_events:
        event_time_str = event['time']
        event_time_dt = datetime.datetime.strptime(event_time_str, config.get('Format', 'time')).replace(year=now.year, month=now.month, day=now.day)
        if event_time_dt > current_time_dt:
            next_event_dt = event_time_dt
            break
    
    # If no event is found for today, consider the first event tomorrow
    if not next_event_dt and sorted_events:
        # Assume the first event of the next day is the "next" event
        event_time_str = sorted_events[0]['time']
        next_event_dt = datetime.datetime.strptime(event_time_str, config.get('Format', 'time')).replace(year=now.year, month=now.month, day=now.day) + datetime.timedelta(days=1)

    return next_event_dt

# Function to show event notification
def show_notification(event, events):
    def run_dialog():
        def update_message():
            nonlocal next_event_dt
            current_time_dt = datetime.datetime.now()
            if next_event_dt:
                # Calculate the time difference
                delta = next_event_dt - current_time_dt
                # Determine if time should be displayed as negative
                prefix = "-" if delta.total_seconds() < 0 else ""
                # Change font color based on the time remaining
                color = config.get('Notification', 'inactive_color') if delta.total_seconds() < 0 else config.get('Notification', 'active_color')
                # Calculate absolute delta to avoid negative in format
                abs_delta = abs(delta)
                hours, remainder = divmod(abs_delta.seconds, 3600)
                minutes = remainder // 60
                
                updated_message = f"{event['time']} - {event['description']} ({event['duration']})\n{prefix}{hours:02d}:{minutes:02d} until the next event."
                message_var.set(updated_message)
                message_label.config(fg=color)  # Update font color based on time remaining
            else:
                message_var.set(f"{event['description']} ({event['duration']})\nNo more events today.")
                message_label.config(fg="black")  # Default color if no next event
            
            # Schedule the next update in 60 seconds
            top.after(config.getint('Notification', 'check_interval'), update_message)

        top = tk.Toplevel()
        top.title(config.get('Notification', 'window_title'))
        
        screen_width = top.winfo_screenwidth()
        screen_height = top.winfo_screenheight()
        window_position = f"+{screen_width // 2 - 100}+{screen_height // 2 - 50}"
        top.geometry(window_position)
        top.attributes("-topmost", True)
        
        message_var = tk.StringVar()
        next_event_dt = calculate_time_to_next_event(time.strftime(config.get('Format', 'time')), events)
        
        # Initialize the message with an initial value
        message_var.set(f"{event['description']} ({event['duration']})\nCalculating time to the next event...")
        
        # Label with dynamic font color
        message_label = tk.Label(top, textvariable=message_var, padx=20, pady=20)
        message_label.pack()
        
        ok_button = tk.Button(top, text="OK", command=top.destroy, width=10)
        ok_button.pack(pady=10)
        
        # Play sound
        sound_path = os.path.join(os.path.dirname(__file__), config.get('Sound', 'file_path'))
        os.system(f'afplay "{sound_path}" &')
        
        top.focus_force()
        top.grab_set()
        update_message()  # Initial call to set and update the message and font color
        
        logger.info(f"Event displayed: {event['description']} ({event['duration']})")

    # Run the dialog in its own thread to avoid blocking
    dialog_thread = threading.Thread(target=run_dialog)
    dialog_thread.start()

# Check to see if the event time has been reached
def check_events():
    global events  # Ensure 'events' is accessible and modifiable globally
    current_time = time.strftime(config.get('Format', 'time'))  # Correct method to get time format
    
    # Reload events from JSON file
    events = read_events()
    
    event_found = False
    for event in events:
        if current_time == event["time"]:
            show_notification(event, events)
            event_found = True
            # Schedule the next check based on the standard check_interval
            next_check = config.getint('Notification', 'check_interval')
            root.after(next_check, check_events)
            return  # Exit the function once an event is found and shown
    
    if not event_found:
        # If no event was found, use the retry_interval for the next check
        next_check = config.getint('Notification', 'retry_interval')
        root.after(next_check, check_events)

def main():
    logger.info(f"Start main loop")
    global events, root
    events = read_events()
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    check_events()
    root.mainloop()

if __name__ == "__main__":
    main()
