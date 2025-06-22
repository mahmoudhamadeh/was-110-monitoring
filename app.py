import json
import time
from datetime import datetime, timedelta, timezone # Import timezone
import pytz
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import threading
import collections
import logging
import re
import paramiko
import os

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

current_data = {
    "temp1": None, "temp2": None, "optical_temp": None,
    "voltage": None, "current": None, "transmit_power": None, "receive_power": None,
    "timestamp": None,
    "time_to_next_refresh_s": None,
    "last_fetch_timestamp_iso": None # This will be ISO UTC
}

HISTORY_MAX_SIZE = 60 * 24
temp1_history = collections.deque(maxlen=HISTORY_MAX_SIZE)
temp2_history = collections.deque(maxlen=HISTORY_MAX_SIZE)
optical_temp_history = collections.deque(maxlen=HISTORY_MAX_SIZE)
voltage_history = collections.deque(maxlen=HISTORY_MAX_SIZE)
current_history = collections.deque(maxlen=HISTORY_MAX_SIZE)
transmit_power_history = collections.deque(maxlen=HISTORY_MAX_SIZE)
receive_power_history = collections.deque(maxlen=HISTORY_MAX_SIZE)
timestamps_history = collections.deque(maxlen=HISTORY_MAX_SIZE)

# Global variable to track the last successful fetch completion time (Python datetime object, UTC)
# Initialize to current UTC time. This ensures initial calculation from get_data is always reasonable.
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
        now_utc = datetime.utcnow().replace(tzinfo=pytz.utc) # Always use UTC for internal timestamps
        now_local = now_utc.astimezone(local_tz)

        current_data.update({
            "temp1": float(core_data.get("temp1", 0)) if core_data.get("temp1") else None,
            "temp2": float(core_data.get("temp2", 0)) if core_data.get("temp2") else None,
            "optical_temp": float(core_data.get("optical_temp", 0)) if core_data.get("optical_temp") else None,
            "voltage": optical_data.get("voltage"),
            "current": optical_data.get("current"),
            "transmit_power": optical_data.get("transmit_power"),
            "receive_power": optical_data.get("receive_power"),
            "timestamp": now_local.isoformat() # This timestamp is for display, localized
        })
        
        # --- FIX: Set last_fetch_completion_time_dt to current UTC time ---
        last_fetch_completion_time_dt = datetime.now(timezone.utc) 
        # --- End Fix ---

        timestamps_history.append(now_local.strftime('%H:%M:%S'))
        temp1_history.append(current_data["temp1"])
        temp2_history.append(current_data["temp2"])
        optical_temp_history.append(current_data["optical_temp"])
        voltage_history.append(current_data["voltage"])
        current_history.append(current_data["current"])
        transmit_power_history.append(current_data["transmit_power"])
        receive_power_history.append(current_data["receive_power"])

        print(f"[{datetime.now().isoformat()}] Successfully fetched: {current_data}", flush=True)

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

@app.route('/')
def index():
    print(f"Serving index.html from: {app.static_folder}/index.html", flush=True)
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/data')
def get_data():
    time_to_next_refresh_s = None
    last_fetch_timestamp_iso = None 

    # --- FIX: Ensure next_scheduled_fetch_time is correctly timezone-aware UTC ---
    # Python 3.9's datetime.now() without tzinfo is naive. 
    # Compare with datetime.utcnow() or make both timezone-aware.
    # We ensure last_fetch_completion_time_dt is always UTC-aware when set.
    # So, compare it to datetime.now(timezone.utc)
    current_utc_time = datetime.now(timezone.utc) 
    # --- End FIX ---

    if last_fetch_completion_time_dt:
        next_scheduled_fetch_time = last_fetch_completion_time_dt + timedelta(seconds=FETCH_INTERVAL_SECONDS)
        
        # Calculate remaining time from current UTC moment until next scheduled fetch
        time_until_next_fetch = next_scheduled_fetch_time - current_utc_time
        
        time_to_next_refresh_s = max(0, int(time_until_next_fetch.total_seconds()))
        
        # --- FIX: Ensure ISO format is consistently UTC ('Z' suffix) ---
        last_fetch_timestamp_iso = last_fetch_completion_time_dt.isoformat(timespec='milliseconds').replace('+00:00', 'Z')
        # --- End FIX ---

    print(f"[{datetime.now().isoformat()}] get_data() called. last_fetch_completion_time_dt: {last_fetch_completion_time_dt} (UTC), current_utc_time: {current_utc_time} (UTC), time_to_next_refresh_s: {time_to_next_refresh_s}", flush=True)

    response_data = {
        "current": current_data,
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
    response_data["current"]["time_to_next_refresh_s"] = time_to_next_refresh_s
    response_data["current"]["last_fetch_timestamp_iso"] = last_fetch_timestamp_iso

    return jsonify(response_data)

if __name__ == '__main__':
    # Initial fetch to populate data and set last_fetch_completion_time_dt
    # This also ensures last_fetch_completion_time_dt is immediately set to now(UTC)
    fetch_and_update_sfp_temperatures() 
    app.run(host='0.0.0.0', port=5050, debug=False)
