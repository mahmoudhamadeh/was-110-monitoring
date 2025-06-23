import json
import time
from datetime import datetime, timedelta, timezone
import pytz
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import threading
import collections
import logging
import re
import paramiko
import os
import shutil # Import shutil for file operations

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__, static_folder='static')
CORS(app)

SFP_USER = "root"
SFP_HOST = "192.168.11.1"

SFP_PASSWORD = os.environ.get('SFP_ROOT_PASSWORD')
if SFP_PASSWORD is None:
    print("WARNING: SFP_ROOT_PASSWORD environment variable not set. SSH authentication may fail.", flush=True)
    SFP_PASSWORD = "dummy_password_not_set"

LOCAL_TIMEZONE = 'America/Toronto'

SFP_CORE_TEMP_COMMAND = r"""
TEMP1=$(awk '{printf "%.1f", $1/1000}' /sys/class/thermal/thermal_zone0/temp);
TEMP2=$(awk '{printf "%.1f", $1/1000}' /sys/class/thermal/thermal_zone1/temp);
EEP=$(xxd -s 96 -l 2 -p /sys/class/pon_mbox/pon_mbox0/device/eeprom51);
B1_HEX=${EEP:0:2};
B2_HEX=${EEP:2:2};
B1=$(printf "%d" 0x$B1_HEX);
B2=$(printf "%d" 0x$B2_HEX);
OPTICAL_TEMP=$(awk -v a="$B1" -v b="$B2" 'BEGIN {printf "%.1f", a + b/256}');
echo "{ \"temp1\": \"$TEMP1\", \"temp2\": \"$TEMP2\", \"optical_temp\": \"$OPTICAL_TEMP\" }"
"""
SFP_CORE_TEMP_COMMAND = SFP_CORE_TEMP_COMMAND.strip()

SFP_OPTICAL_STATUS_COMMAND = r"""pontop -b -g 'Optical Interface Status'"""
SFP_OPTICAL_STATUS_COMMAND = SFP_OPTICAL_STATUS_COMMAND.strip()

current_stats_data = {
    "temp1": None, "temp2": None, "optical_temp": None,
    "voltage": None, "current": None, "transmit_power": None, "receive_power": None,
    "timestamp": None 
}

HISTORY_MAX_SIZE = 60 * 24 
DATA_DIR = "/data" 
HISTORY_FILE = os.path.join(DATA_DIR, "sfp_history.json") 

temp1_history = collections.deque(maxlen=HISTORY_MAX_SIZE)
temp2_history = collections.deque(maxlen=HISTORY_MAX_SIZE)
optical_temp_history = collections.deque(maxlen=HISTORY_MAX_SIZE)
voltage_history = collections.deque(maxlen=HISTORY_MAX_SIZE)
current_history = collections.deque(maxlen=HISTORY_MAX_SIZE)
transmit_power_history = collections.deque(maxlen=HISTORY_MAX_SIZE)
receive_power_history = collections.deque(maxlen=HISTORY_MAX_SIZE)
timestamps_history = collections.deque(maxlen=HISTORY_MAX_SIZE)

last_fetch_completion_time_dt = datetime.now(timezone.utc) 
FETCH_INTERVAL_SECONDS = 300

def execute_remote_command(client, command_string):
    stdin, stdout, stderr = client.exec_command(command_string)
    output = stdout.read().decode('utf-8').strip()
    error = stderr.read().decode('utf-8').strip()
    return output, error

def parse_optical_status_output(output):
    parsed_data = {}
    
    patterns = {
        "voltage": r"Transceiver supply voltage\s*:\s*([\d.]+) V",
        "current": r"Transmit bias current\s*:\s*([\d.]+) mA",
        "transmit_power": r"Transmit power\s*:\s*([-\d.]+) dBm",
        "receive_power": r"Receive power\s*:\s*([-\d.]+) dBm"
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, output)
        if match:
            try:
                parsed_data[key] = float(match.group(1))
            except ValueError:
                print(f"[{datetime.now().isoformat()}] Could not convert {key} to float: {match.group(1)}", flush=True)
                parsed_data[key] = None
        else:
            print(f"[{datetime.now().isoformat()}] Pattern for {key} not found in pontop output.", flush=True)
            parsed_data[key] = None
            
    return parsed_data

def fetch_and_update_sfp_temperatures():
    global last_fetch_completion_time_dt 
    if SFP_PASSWORD is None or SFP_PASSWORD == "dummy_password_not_set":
        print(f"[{datetime.now().isoformat()}] ERROR: SFP password environment variable (SFP_ROOT_PASSWORD) not set or is dummy. Skipping fetch.", flush=True)
        return

    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        print(f"[{datetime.now().isoformat()}] Attempting to fetch SFP data via Paramiko SSH...", flush=True)
        
        client.connect(hostname=SFP_HOST, username=SFP_USER, password=SFP_PASSWORD, timeout=15)
        
        temp_output, temp_error = execute_remote_command(client, SFP_CORE_TEMP_COMMAND) 
        if temp_error:
            print(f"[{datetime.now().isoformat()}] Core Temp SSH command error: {temp_error}", flush=True)
            print(f"[{datetime.now().isoformat()}] Raw Core Temp output (stdout): {temp_output}", flush=True)
            core_data = {}
        else:
            try:
                core_data = json.loads(temp_output)
            except json.JSONDecodeError as e:
                print(f"[{datetime.now().isoformat()}] Error decoding JSON from Core Temp SFP: {e}", flush=True)
                print(f"[{datetime.now().isoformat()}] Raw Core Temp output that caused error: {temp_output}", flush=True)
                core_data = {}

        optical_output, optical_error = execute_remote_command(client, SFP_OPTICAL_STATUS_COMMAND) 
        if optical_error:
            print(f"[{datetime.now().isoformat()}] Optical Status SSH command error: {optical_error}", flush=True)
            print(f"[{datetime.now().isoformat()}] Raw Optical Status output (stdout): {optical_output}", flush=True)
            optical_data = {}
        else:
            optical_data = parse_optical_status_output(optical_output) 

        local_tz = pytz.timezone(LOCAL_TIMEZONE)
        now_utc = datetime.utcnow().replace(tzinfo=timezone.utc) 
        now_local = now_utc.astimezone(local_tz)

        current_stats_data.update({
            "temp1": float(core_data.get("temp1", 0)) if core_data.get("temp1") else None,
            "temp2": float(core_data.get("temp2", 0)) if core_data.get("temp2") else None,
            "optical_temp": float(core_data.get("optical_temp", 0)) if core_data.get("optical_temp") else None,
            "voltage": optical_data.get("voltage"),
            "current": optical_data.get("current"),
            "transmit_power": optical_data.get("transmit_power"),
            "receive_power": optical_data.get("receive_power"),
            "timestamp": now_local.isoformat() 
        })
        
        last_fetch_completion_time_dt = datetime.now(timezone.utc) 

        timestamps_history.append(now_local.strftime('%H:%M:%S'))
        temp1_history.append(current_stats_data["temp1"])
        temp2_history.append(current_stats_data["temp2"])
        optical_temp_history.append(current_stats_data["optical_temp"])
        voltage_history.append(current_stats_data["voltage"])
        current_history.append(current_stats_data["current"])
        transmit_power_history.append(current_stats_data["transmit_power"])
        receive_power_history.append(current_stats_data["receive_power"])

        print(f"[{datetime.now().isoformat()}] Successfully fetched: {current_stats_data}", flush=True)
        save_history_to_file() 

    except paramiko.AuthenticationException:
        print(f"[{datetime.now().isoformat()}] Authentication failed. Check username and password in .env file.", flush=True)
        last_fetch_completion_time_dt = None 
    except paramiko.SSHException as e:
        print(f"[{datetime.now().isoformat()}] SSH error: {e}", flush=True)
        last_fetch_completion_time_dt = None
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] An unexpected error occurred during fetch: {e}", flush=True)
        last_fetch_completion_time_dt = None
    finally:
        client.close()

def periodic_fetch():
    while True:
        fetch_and_update_sfp_temperatures()
        time.sleep(FETCH_INTERVAL_SECONDS) 

fetch_thread = threading.Thread(target=periodic_fetch, daemon=True)
fetch_thread.start()


# --- DATA PERSISTENCE FUNCTIONS ---
def save_history_to_file(): 
    history_data = {
        "timestamps": list(timestamps_history),
        "temp1": list(temp1_history),
        "temp2": list(temp2_history),
        "optical_temp": list(optical_temp_history),
        "voltage": list(voltage_history),
        "current": list(current_history),
        "transmit_power": list(transmit_power_history),
        "receive_power": list(receive_power_history),
        "last_fetch_completion_time_iso": last_fetch_completion_time_dt.isoformat() if last_fetch_completion_time_dt else None
    }
    try:
        os.makedirs(DATA_DIR, exist_ok=True) 
        temp_file_path = os.path.join(DATA_DIR, "sfp_history.json.tmp")
        final_file_path = os.path.join(DATA_DIR, "sfp_history.json")
        
        with open(temp_file_path, 'w') as f:
            json.dump(history_data, f)
        
        # --- FIX: Use shutil.move for atomic move instead of os.replace ---
        # os.replace can sometimes fail if the destination does not exist yet (first save)
        # shutil.move is generally more robust for moving/replacing files.
        shutil.move(temp_file_path, final_file_path)
        # --- End FIX ---

        print(f"[{datetime.now().isoformat()}] History saved to {final_file_path}. Points: {len(timestamps_history)}", flush=True)
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERROR: Failed to save history to file: {e}", flush=True)

def load_history_from_file(): 
    global last_fetch_completion_time_dt 
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r') as f:
                history_data = json.load(f)
            
            timestamps_history.extend(history_data.get("timestamps", []))
            temp1_history.extend(history_data.get("temp1", []))
            temp2_history.extend(history_data.get("temp2", []))
            optical_temp_history.extend(history_data.get("optical_temp", []))
            voltage_history.extend(history_data.get("voltage", []))
            current_history.extend(history_data.get("current", []))
            transmit_power_history.extend(history_data.get("transmit_power", []))
            receive_power_history.extend(history_data.get("receive_power", []))

            last_fetch_iso = history_data.get("last_fetch_completion_time_iso")
            if last_fetch_iso:
                try:
                    last_fetch_completion_time_dt = datetime.fromisoformat(last_fetch_iso).astimezone(timezone.utc)
                    print(f"[{datetime.now().isoformat()}] Loaded last fetch time: {last_fetch_completion_time_dt.isoformat()}", flush=True)
                except ValueError:
                    print(f"[{datetime.now().isoformat()}] WARNING: Could not parse saved timestamp {last_fetch_iso}, initializing to now.", flush=True)
                    last_fetch_completion_time_dt = datetime.now(timezone.utc)
            else:
                print(f"[{datetime.now().isoformat()}] No last fetch timestamp found in file, initializing to now.", flush=True)
                last_fetch_completion_time_dt = datetime.now(timezone.utc)

            print(f"[{datetime.now().isoformat()}] History loaded from {HISTORY_FILE}. Points: {len(timestamps_history)}", flush=True)
        else:
            print(f"[{datetime.now().isoformat()}] No history file found at {HISTORY_FILE}. Starting fresh.", flush=True)
            last_fetch_completion_time_dt = datetime.now(timezone.utc) 
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERROR: Failed to load history from file: {e}. Clearing history and starting fresh.", flush=True)
        timestamps_history.clear() 
        temp1_history.clear()
        temp2_history.clear()
        optical_temp_history.clear()
        voltage_history.clear()
        current_history.clear()
        transmit_power_history.clear()
        receive_power_history.clear()
        last_fetch_completion_time_dt = datetime.now(timezone.utc)

@app.route('/')
def index():
    print(f"Serving index.html from: {app.static_folder}/index.html", flush=True)
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/data')
def get_data():
    time_to_next_refresh_s = None
    last_fetch_timestamp_iso = None 

    current_utc_time = datetime.now(timezone.utc) 

    if last_fetch_completion_time_dt:
        next_scheduled_fetch_time = last_fetch_completion_time_dt + timedelta(seconds=FETCH_INTERVAL_SECONDS)
        
        time_until_next_fetch = next_scheduled_fetch_time - current_utc_time
        
        time_to_next_refresh_s = max(0, int(time_until_next_fetch.total_seconds()))
        
        last_fetch_timestamp_iso = last_fetch_completion_time_dt.isoformat(timespec='milliseconds').replace('+00:00', 'Z')

    response_data = {
        "current": {
            **current_stats_data, 
            "time_to_next_refresh_s": time_to_next_refresh_s,
            "last_fetch_timestamp_iso": last_fetch_timestamp_iso
        },
        "history": {
            "timestamps": list(timestamps_history),
            "temp1": list(temp1_history),
            "temp2": list(temp2_history),
            "optical_temp": list(optical_temp_history),
            "voltage": list(voltage_history),
            "current": list(current_history),
            "transmit_power": list(transmit_power_history),
            "receive_power": list(receive_power_history)
        }
    }

    print(f"[{datetime.now().isoformat()}] get_data() called. Sending last_fetch_completion_time_dt: {last_fetch_completion_time_dt} (UTC), time_to_next_refresh_s: {time_to_next_refresh_s}", flush=True)
    print(f"[{datetime.now().isoformat()}] get_data() sending history points: {len(timestamps_history)}", flush=True)

    return jsonify(response_data)

if __name__ == '__main__':
    load_history_from_file() 
    
    if not timestamps_history or \
       (datetime.now(timezone.utc) - last_fetch_completion_time_dt).total_seconds() > FETCH_INTERVAL_SECONDS:
        print(f"[{datetime.now().isoformat()}] Initial/Catch-up fetch needed (no history or old history).", flush=True)
        fetch_and_update_sfp_temperatures() 
    else:
        print(f"[{datetime.now().isoformat()}] Using loaded history, next fetch due in {FETCH_INTERVAL_SECONDS - (datetime.now(timezone.utc) - last_fetch_completion_time_dt).total_seconds():.0f}s.", flush=True)
    
    app.run(host='0.0.0.0', port=5050, debug=False)
