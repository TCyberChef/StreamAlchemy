from flask import Flask, render_template, jsonify, request, flash, redirect, url_for, send_file, Response
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import re # For stream name validation
import subprocess
import shutil # For checking ffmpeg command
import threading
import time
import json # For crash report data
import platform # For system info in crash reports
import signal # For process group killing
import logging
import sys
import cv2
# Add new imports for logging handlers and sched
from logging.handlers import RotatingFileHandler
import atexit
import glob # For cleanup
import stat # For cleanup, to get file mode

# Import configuration
try:
    import config
except ImportError:
    # Fallback to default config if not available
    class config:
        VIDEO_DIR = "" # No longer using web-interface for default video dir
        BROWSEABLE_VIDEO_DIR = os.path.join(os.path.dirname(__file__), "browseable_videos") # Fallback browseable path
        BASE_TMP_DIR = "/tmp/stream_alchemy"
        LOG_DIR = os.path.join(BASE_TMP_DIR, "ffmpeg_logs")
        CRASH_LOG_DIR = os.path.join(BASE_TMP_DIR, "ffmpeg_crash_logs")
        PID_DIR = os.path.join(BASE_TMP_DIR, "pids")
        STATUS_DIR = os.path.join(BASE_TMP_DIR, "status")
        MAX_CPU_USAGE = 90.0
        MAX_MEMORY_USAGE = 2048
        MAX_STREAM_DURATION = 48 * 3600
        HEALTH_CHECK_INTERVAL = 60
        ENABLE_HEALTH_MONITORING = True
        ENABLE_YOUTUBE_SUPPORT = True
        HOST = '0.0.0.0'
        PORT = 5000
        DEBUG = True
        LOG_LEVEL = 'INFO'
        LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        MAX_UPLOAD_SIZE = 2 * 1024 * 1024 * 1024 # Updated to 2GB
        ALLOWED_VIDEO_EXTENSIONS = ['mp4', 'mkv', 'avi', 'mov', 'webm', 'flv', 'm4v'] # Removed leading dots
        UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "browseable_videos") # Changed to browseable_videos
        SECRET_KEY = 'a_fallback_secret_key_if_config_fails' # Fallback secret key

# Determine the correct static folder path, which is one level up from app.py directory
STATIC_FOLDER_PATH = os.path.join(os.path.dirname(__file__), '..', 'static')

app = Flask(__name__)
app.secret_key = config.SECRET_KEY # Set secret key for session management
CORS(app)  # Enable CORS for HLS streaming

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format=config.LOG_FORMAT
)

root_logger = logging.getLogger()

# Setup Flask app logger with RotatingFileHandler if APP_LOG_FILE is specified
if hasattr(config, 'APP_LOG_FILE') and config.APP_LOG_FILE:
    # Ensure the directory for the app log file exists
    app_log_dir = os.path.dirname(config.APP_LOG_FILE)
    if not os.path.exists(app_log_dir):
        os.makedirs(app_log_dir, exist_ok=True)
        print(f"Created application log directory: {app_log_dir}") # Optional: inform that dir was created

    app_log_handler = RotatingFileHandler(
        config.APP_LOG_FILE,
        maxBytes=getattr(config, 'APP_LOG_MAX_BYTES', 10*1024*1024), # Default 10MB
        backupCount=getattr(config, 'APP_LOG_BACKUP_COUNT', 5)      # Default 5 backups
    )
    app_log_handler.setFormatter(logging.Formatter(config.LOG_FORMAT))
    app.logger.addHandler(app_log_handler)
    # Also configure the root logger if desired, or rely on Flask's propagation
    # logging.getLogger().addHandler(app_log_handler) # This might duplicate logs if basicConfig also adds handlers
    # For simplicity, we'll let Flask's app.logger handle its own logging to the file.
    # If other modules use logging.getLogger(), they might not log to this file unless the root logger is also configured.
    # Let's add it to the root logger but remove basicConfig's default handler (if any) to avoid duplication.
    
    # Remove default handlers from root logger (if any, typically StreamHandler from basicConfig)
    if root_logger.hasHandlers():
        for handler in root_logger.handlers[:]: # Iterate over a copy
            if isinstance(handler, logging.StreamHandler) and handler.stream in [sys.stdout, sys.stderr]:
                 root_logger.removeHandler(handler) # remove console handler if we are logging to file.
    
    root_logger.addHandler(app_log_handler)
    root_logger.setLevel(getattr(logging, config.LOG_LEVEL)) # ensure root logger level is also set

    # If Flask is in debug mode, it might add its own StreamHandler.
    # We'll assume for production, DEBUG is False and this setup is sufficient.
    # If DEBUG is True, console logs from Flask itself might still appear.
    app.logger.info(f"Application logging configured. Main application logs will be written to: {config.APP_LOG_FILE}")
elif not root_logger.handlers: # if no file handler, and root still has no handlers (e.g. basicConfig did not add one)
    # This case might happen if basicConfig was called but for some reason didn't add a default (e.g. in some specific envs or Python versions)
    # Or if basicConfig itself wasn't effective and we don't have a file log, ensure console output for app.logger.
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(config.LOG_FORMAT))
    app.logger.addHandler(console_handler)
    app.logger.info("Application logging to console.")

# Startup message for runtime file locations
startup_message = (
    f"\n"
    f"****************************************************\n"
    f"* StreamAlchemy Runtime Files Location:\n"
    f"****************************************************\n"
    f"  Base Temporary Directory: {config.BASE_TMP_DIR}\n"
    f"  FFmpeg Logs Directory:    {config.LOG_DIR}\n"
    f"  Crash Logs Directory:     {config.CRASH_LOG_DIR}\n"
    f"  PID Files Directory:      {config.PID_DIR}\n"
    f"  Status Files Directory:   {config.STATUS_DIR}"
)
print(startup_message) # Print to console directly
app.logger.info("For detailed locations, see startup message on console.")

# Configure max upload size
app.config['MAX_CONTENT_LENGTH'] = config.MAX_UPLOAD_SIZE
app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER # Added UPLOAD_FOLDER to app config
app.config['ALLOWED_VIDEO_EXTENSIONS'] = config.ALLOWED_VIDEO_EXTENSIONS # Added ALLOWED_VIDEO_EXTENSIONS to app config

# --- Configuration & Global Variables ---
VIDEO_DIR = config.VIDEO_DIR
BASE_TMP_DIR = config.BASE_TMP_DIR

LOG_DIR = config.LOG_DIR
CRASH_LOG_DIR = config.CRASH_LOG_DIR
PID_DIR = config.PID_DIR
STATUS_DIR = config.STATUS_DIR

# Health monitoring limits
MAX_CPU_USAGE = config.MAX_CPU_USAGE
MAX_MEMORY_USAGE = config.MAX_MEMORY_USAGE
MAX_STREAM_DURATION = config.MAX_STREAM_DURATION
HEALTH_CHECK_INTERVAL = config.HEALTH_CHECK_INTERVAL

# Ensure directories exist
# Make sure BROWSEABLE_VIDEO_DIR is also created if it doesn't exist
PROJ_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BROWSEABLE_DIR = os.path.join(PROJ_BASE_DIR, "browseable_videos")
UPLOAD_DIR_TO_CREATE = getattr(config, 'UPLOAD_FOLDER', os.path.join(PROJ_BASE_DIR, "uploads")) # Prepare UPLOAD_FOLDER for creation

# Explicitly create BROWSEABLE_VIDEO_DIR and UPLOAD_FOLDER (often the same)
if hasattr(config, 'BROWSEABLE_VIDEO_DIR') and config.BROWSEABLE_VIDEO_DIR:
    os.makedirs(config.BROWSEABLE_VIDEO_DIR, exist_ok=True)
    app.logger.info(f"Ensured browseable video directory exists: {config.BROWSEABLE_VIDEO_DIR}")

# UPLOAD_FOLDER is typically the same as BROWSEABLE_VIDEO_DIR as per config.py
# If it could be different and needs separate creation, ensure it here too.
# Given UPLOAD_FOLDER = BROWSEABLE_VIDEO_DIR in config, the above create is sufficient.
# However, UPLOAD_DIR_TO_CREATE is used in the loop below, which handles the effective upload folder path.

for d_path in [config.LOG_DIR, config.CRASH_LOG_DIR, config.PID_DIR, config.STATUS_DIR, getattr(config, 'BROWSEABLE_VIDEO_DIR', DEFAULT_BROWSEABLE_DIR), UPLOAD_DIR_TO_CREATE, getattr(config, 'STREAM_PERSISTENCE_DIR', os.path.join(config.BASE_DIR, 'data')), getattr(config, 'HLS_DIR', os.path.join(config.BASE_TMP_DIR, 'hls_streams'))]: # Added UPLOAD_DIR_TO_CREATE, STREAM_PERSISTENCE_DIR, and HLS_DIR
    os.makedirs(d_path, exist_ok=True)

active_streams = {}
_shutdown_in_progress = False  # Flag to track if we're shutting down

# --- Stream Persistence Functions ---
def save_stream_state(stream_name, stream_config):
    """Save a stream's configuration to persistent storage"""
    if not config.ENABLE_STREAM_PERSISTENCE:
        return
    
    try:
        # Load existing streams
        persistent_streams = load_persistent_streams()
        
        # Add/update this stream
        persistent_streams[stream_name] = {
            'config': stream_config,
            'saved_at': time.time(),
            'status': 'active'
        }
        
        # Create backup of current file if it exists
        if os.path.exists(config.STREAM_PERSISTENCE_FILE):
            backup_file = f"{config.STREAM_PERSISTENCE_FILE}.backup"
            shutil.copy2(config.STREAM_PERSISTENCE_FILE, backup_file)
        
        # Save to file
        os.makedirs(os.path.dirname(config.STREAM_PERSISTENCE_FILE), exist_ok=True)
        with open(config.STREAM_PERSISTENCE_FILE, 'w') as f:
            json.dump(persistent_streams, f, indent=2)
        
        app.logger.info(f"Saved stream state for {stream_name}")
        
    except Exception as e:
        app.logger.error(f"Failed to save stream state for {stream_name}: {e}")

def remove_stream_state(stream_name):
    """Remove a stream's configuration from persistent storage"""
    if not config.ENABLE_STREAM_PERSISTENCE:
        return
    
    try:
        persistent_streams = load_persistent_streams()
        if stream_name in persistent_streams:
            del persistent_streams[stream_name]
            
            # Save updated file
            with open(config.STREAM_PERSISTENCE_FILE, 'w') as f:
                json.dump(persistent_streams, f, indent=2)
            
            app.logger.info(f"Removed stream state for {stream_name}")
        
    except Exception as e:
        app.logger.error(f"Failed to remove stream state for {stream_name}: {e}")

def load_persistent_streams():
    """Load persistent stream configurations from disk"""
    if not config.ENABLE_STREAM_PERSISTENCE:
        return {}
    
    try:
        if os.path.exists(config.STREAM_PERSISTENCE_FILE):
            with open(config.STREAM_PERSISTENCE_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        app.logger.error(f"Failed to load persistent streams: {e}")
        
        # Try backup file
        backup_file = f"{config.STREAM_PERSISTENCE_FILE}.backup"
        if os.path.exists(backup_file):
            try:
                app.logger.info("Attempting to load from backup file")
                with open(backup_file, 'r') as f:
                    return json.load(f)
            except Exception as backup_e:
                app.logger.error(f"Failed to load from backup: {backup_e}")
    
    return {}

def restore_streams_on_startup():
    """Restore active streams from persistent storage on application startup"""
    if not config.ENABLE_STREAM_PERSISTENCE:
        app.logger.info("Stream persistence is disabled")
        return
    
    persistent_streams = load_persistent_streams()
    if not persistent_streams:
        app.logger.info("No persistent streams found")
        return
    
    app.logger.info(f"Found {len(persistent_streams)} persistent streams to restore")
    
    restored_count = 0
    failed_count = 0
    
    for stream_name, stream_data in persistent_streams.items():
        try:
            stream_config = stream_data.get('config', {})
            saved_at = stream_data.get('saved_at', 0)
            
            # Check if stream should still be running based on duration
            duration_hours = float(stream_config.get('duration_hours', '0'))
            if duration_hours > 0:
                elapsed_hours = (time.time() - saved_at) / 3600
                if elapsed_hours >= duration_hours:
                    app.logger.info(f"Stream {stream_name} duration expired ({elapsed_hours:.1f}h >= {duration_hours}h), skipping restore")
                    remove_stream_state(stream_name)
                    continue
            
            # Validate required fields
            if not stream_config.get('stream_type'):
                app.logger.warning(f"Stream {stream_name} missing stream_type, skipping")
                continue
            
            # Validate file existence for file streams
            if stream_config.get('stream_type') == 'file':
                video_file_path = stream_config.get('video_file_path')
                if video_file_path and not os.path.exists(video_file_path):
                    app.logger.warning(f"Stream {stream_name} source file not found: {video_file_path}, skipping")
                    continue
            
            app.logger.info(f"Restoring stream: {stream_name}")
            
            # Get encoder info
            vid_codec = stream_config.get('video_codec', 'h264')
            hw_accel = stream_config.get('hardware_accel') == 'yes'
            avail_encs = get_available_encoders()
            
            if not avail_encs or not avail_encs.get(vid_codec):
                app.logger.error(f"No encoders available for {vid_codec}, skipping {stream_name}")
                continue
            
            enc_info = get_best_encoder(vid_codec, avail_encs, hw_accel)
            
            # Add stream_name to config for construct_ffmpeg_command
            stream_config['stream_name'] = stream_name
            
            ff_cmd = construct_ffmpeg_command(stream_config, enc_info)
            
            # Calculate remaining duration
            remaining_duration = '0'
            if duration_hours > 0:
                elapsed_hours = (time.time() - saved_at) / 3600
                remaining_hours = max(0, duration_hours - elapsed_hours)
                remaining_duration = str(remaining_hours)
            
            # Start the stream
            ok, msg = exec_and_monitor_ffmpeg(stream_name, ff_cmd, remaining_duration, stream_config, enc_info)
            
            if ok:
                app.logger.info(f"Successfully restored stream: {stream_name}")
                restored_count += 1
            else:
                app.logger.error(f"Failed to restore stream {stream_name}: {msg}")
                failed_count += 1
                remove_stream_state(stream_name)
                
        except Exception as e:
            app.logger.error(f"Error restoring stream {stream_name}: {e}")
            failed_count += 1
    
    app.logger.info(f"Stream restoration complete: {restored_count} restored, {failed_count} failed")

# --- End Stream Persistence Functions ---

# --- End Configuration ---

# --- MediaMTX Management ---
# Check if MediaMTX is available via Homebrew (macOS) or use local binary
if shutil.which('mediamtx'):
    # Use system-installed MediaMTX (Homebrew on macOS)
    MEDIAMTX_BINARY = shutil.which('mediamtx')
    MEDIAMTX_DIR = os.path.dirname(MEDIAMTX_BINARY)
    # Use local config file if it exists, otherwise use system default
    local_config = os.path.join(os.path.dirname(__file__), '..', 'mediamtx', 'mediamtx.yml')
    if os.path.exists(local_config):
        MEDIAMTX_CONFIG = local_config
    else:
        MEDIAMTX_CONFIG = '/opt/homebrew/etc/mediamtx/mediamtx.yml'  # Homebrew default
else:
    # Fallback to local MediaMTX binary
    MEDIAMTX_DIR = os.path.join(os.path.dirname(__file__), '..', 'mediamtx')
    MEDIAMTX_BINARY = os.path.join(MEDIAMTX_DIR, 'mediamtx')
    MEDIAMTX_CONFIG = os.path.join(MEDIAMTX_DIR, 'mediamtx.yml')
MEDIAMTX_PID_FILE = os.path.join(PID_DIR, 'mediamtx.pid')
MEDIAMTX_LOG_FILE = os.path.join(LOG_DIR, 'mediamtx.log')

_stream_log_handlers = {} # Cache for RotatingFileHandlers for stream logs

def _get_stream_log_handler(log_file_path):
    if log_file_path not in _stream_log_handlers:
        # Use slightly smaller defaults for individual stream logs than main app log
        max_bytes = getattr(config, 'STREAM_LOG_MAX_BYTES', 5*1024*1024) # 5MB default per stream log file
        backup_count = getattr(config, 'STREAM_LOG_BACKUP_COUNT', 2)  # 2 backups per stream log file
        handler = RotatingFileHandler(
            log_file_path,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s')) # Simpler format for stream logs
        _stream_log_handlers[log_file_path] = handler
    return _stream_log_handlers[log_file_path]

def _run_command(command, timeout=None):
    try:
        process = subprocess.run(command, capture_output=True, text=True, shell=True, timeout=timeout, check=False)
        return process
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(command, returncode=-1, stdout="", stderr="Timeout")
    except Exception as e:
        return subprocess.CompletedProcess(command, returncode=-99, stdout="", stderr=str(e))

def _is_mediamtx_running():
    """Check if MediaMTX is already running"""
    # Check if PID file exists
    if os.path.exists(MEDIAMTX_PID_FILE):
        try:
            with open(MEDIAMTX_PID_FILE, 'r') as f:
                pid = int(f.read().strip())
            
            # Check if process is actually running
            result = _run_command(f"ps -p {pid} -o comm=")
            if result.returncode == 0 and 'mediamtx' in result.stdout.lower():
                return True, pid
            else:
                # PID file exists but process is not running, clean up
                os.remove(MEDIAMTX_PID_FILE)
        except Exception as e:
            app.logger.warning(f"Error checking MediaMTX PID: {e}")
    
    # Check if any mediamtx process is running
    result = _run_command("pgrep -x mediamtx")
    if result.returncode == 0 and result.stdout.strip():
        pids = result.stdout.strip().split('\n')
        return True, int(pids[0])
    
    # Check if something is listening on RTSP port
    rtsp_port = getattr(config, 'RTSP_PORT', 8554)
    result = _run_command(f"lsof -i :{rtsp_port} -t")
    if result.returncode == 0 and result.stdout.strip():
        app.logger.warning(f"Something is already listening on RTSP port {rtsp_port}")
        return True, None
    
    return False, None

def _start_mediamtx():
    """Start MediaMTX server if not already running"""
    running, pid = _is_mediamtx_running()
    
    if running:
        if pid:
            app.logger.info(f"MediaMTX is already running with PID {pid}")
        else:
            app.logger.info("MediaMTX or another service is already running on RTSP port")
        return True
    
    # Check if MediaMTX binary exists and is executable
    if not os.path.exists(MEDIAMTX_BINARY):
        app.logger.error(f"MediaMTX binary not found at {MEDIAMTX_BINARY}")
        return False
    
    if not os.access(MEDIAMTX_BINARY, os.X_OK):
        app.logger.warning("MediaMTX binary is not executable, attempting to make it executable")
        try:
            os.chmod(MEDIAMTX_BINARY, 0o755)
        except Exception as e:
            app.logger.error(f"Failed to make MediaMTX executable: {e}")
            return False
    
    # Check if config file exists
    if not os.path.exists(MEDIAMTX_CONFIG):
        app.logger.error(f"MediaMTX config not found at {MEDIAMTX_CONFIG}")
        return False
    
    # Start MediaMTX
    try:
        app.logger.info("Starting MediaMTX server...")
        
        # Open log file for MediaMTX output
        log_file = open(MEDIAMTX_LOG_FILE, 'a')
        
        # Start MediaMTX process
        process = subprocess.Popen(
            [MEDIAMTX_BINARY, MEDIAMTX_CONFIG],
            stdout=log_file,
            stderr=log_file,
            preexec_fn=os.setsid,  # Create new process group
            cwd=MEDIAMTX_DIR
        )
        
        # Wait a moment to ensure it starts successfully
        time.sleep(2)
        
        # Check if process is still running
        if process.poll() is None:
            # Save PID
            with open(MEDIAMTX_PID_FILE, 'w') as f:
                f.write(str(process.pid))
            
            app.logger.info(f"MediaMTX started successfully with PID {process.pid}")
            return True
        else:
            app.logger.error(f"MediaMTX failed to start, exit code: {process.poll()}")
            # Read last few lines of log for error info
            try:
                with open(MEDIAMTX_LOG_FILE, 'r') as f:
                    lines = f.readlines()
                    last_lines = lines[-10:] if len(lines) > 10 else lines
                    app.logger.error("MediaMTX error output:\n" + ''.join(last_lines))
            except:
                pass
            return False
            
    except Exception as e:
        app.logger.error(f"Failed to start MediaMTX: {e}")
        return False

def _stop_mediamtx():
    """Stop MediaMTX server"""
    running, pid = _is_mediamtx_running()
    
    if not running:
        app.logger.info("MediaMTX is not running")
        return True
    
    if not pid:
        app.logger.warning("MediaMTX is running but PID unknown, cannot stop")
        return False
    
    try:
        app.logger.info(f"Stopping MediaMTX with PID {pid}")
        
        # Try graceful shutdown first
        os.kill(pid, signal.SIGTERM)
        time.sleep(2)
        
        # Check if still running
        try:
            os.kill(pid, 0)  # Check if process exists
            # Still running, force kill
            os.kill(pid, signal.SIGKILL)
            app.logger.warning("MediaMTX required force kill")
        except ProcessLookupError:
            # Process is gone, good
            pass
        
        # Clean up PID file
        if os.path.exists(MEDIAMTX_PID_FILE):
            os.remove(MEDIAMTX_PID_FILE)
        
        app.logger.info("MediaMTX stopped successfully")
        return True
        
    except Exception as e:
        app.logger.error(f"Failed to stop MediaMTX: {e}")
        return False

# Start MediaMTX on app startup
if not _start_mediamtx():
    app.logger.error("Failed to start MediaMTX, streaming functionality will not work!")
    # You might want to exit here or show a warning in the UI

# --- End MediaMTX Management ---

_ffmpeg_encoders_cache = None

def _get_ffmpeg_encoders_info():
    global _ffmpeg_encoders_cache
    if _ffmpeg_encoders_cache is not None: return _ffmpeg_encoders_cache
    if not shutil.which("ffmpeg"): _ffmpeg_encoders_cache = ""; return ""
    process = _run_command("ffmpeg -hide_banner -encoders")
    if process.returncode == 0: _ffmpeg_encoders_cache = process.stdout; return process.stdout
    _ffmpeg_encoders_cache = ""; return ""

def _check_ffmpeg_encoder(encoder_name):
    ffmpeg_output = _get_ffmpeg_encoders_info()
    if not ffmpeg_output: return False
    for line in ffmpeg_output.splitlines():
        parts = line.strip().split()
        if len(parts) > 1 and parts[1] == encoder_name: return True
    return False

def _check_nvidia_gpu():
    if not shutil.which("nvidia-smi"): return False
    process = _run_command("nvidia-smi --query-gpu=gpu_name --format=csv,noheader")
    return process.returncode == 0 and process.stdout.strip() != ""

def _check_vaapi_device(): return os.path.exists("/dev/dri/renderD128")

def _test_vaapi_encoder(codec_name):
    if not _check_vaapi_device() or not shutil.which("ffmpeg"): return False
    vaapi_encoder_name = {'h264': 'h264_vaapi', 'h265': 'hevc_vaapi'}.get(codec_name)
    if not vaapi_encoder_name or not _check_ffmpeg_encoder(vaapi_encoder_name): return False
    # Use cross-platform timeout for VAAPI test
    timeout_cmd = "timeout 5" if not config.IS_MACOS else ("gtimeout 5" if shutil.which('gtimeout') else "")
    test_command = (
        f"{timeout_cmd} ffmpeg -loglevel error -vaapi_device /dev/dri/renderD128 -f lavfi "
        f"-i testsrc=duration=0.1:size=320x240:rate=10 -vf \"format=nv12,hwupload\" "
        f"-c:v {vaapi_encoder_name} -qp 23 -t 0.1 -f null -"
    ).strip()
    return _run_command(test_command, timeout=10).returncode == 0

def get_available_encoders():
    available = {c: {'software': None, 'hardware_nvidia': None, 'hardware_amd': None} for c in ['h264', 'h265']}
    available['mpeg4'] = {'software': None}
    if not shutil.which("ffmpeg"): return available
    if _check_ffmpeg_encoder('libx264'): available['h264']['software'] = 'libx264'
    if _check_ffmpeg_encoder('libx265'): available['h265']['software'] = 'libx265'
    if _check_ffmpeg_encoder('mpeg4'): available['mpeg4']['software'] = 'mpeg4'
    if _check_nvidia_gpu():
        if _check_ffmpeg_encoder('h264_nvenc'): available['h264']['hardware_nvidia'] = 'h264_nvenc'
        if _check_ffmpeg_encoder('hevc_nvenc'): available['h265']['hardware_nvidia'] = 'hevc_nvenc'
    if _check_vaapi_device():
        if _test_vaapi_encoder('h264'): available['h264']['hardware_amd'] = 'h264_vaapi'
        if _test_vaapi_encoder('h265'): available['h265']['hardware_amd'] = 'hevc_vaapi'
    return {c: e for c, e in available.items() if any(e.values())}

def get_best_encoder(codec, available_encoders, use_hardware_accel=True):
    if codec not in available_encoders: raise ValueError(f"No encoders for {codec}")
    options = available_encoders[codec]
    if use_hardware_accel:
        if options.get('hardware_nvidia'): return {'name': options['hardware_nvidia'], 'type': 'hardware_nvidia'}
        if options.get('hardware_amd'): return {'name': options['hardware_amd'], 'type': 'hardware_amd'}
    if options.get('software'): return {'name': options['software'], 'type': 'software'}
    raise ValueError(f"No suitable encoder for {codec} with preferences.")

def construct_ffmpeg_command(data, encoder_info):
    stream_name = data['stream_name']
    resolution_map = {
        '480': {'w': 854, 'h': 480, 'dim': '854x480'}, '720': {'w': 1280, 'h': 720, 'dim': '1280x720'},
        '1080': {'w': 1920, 'h': 1080, 'dim': '1920x1080'}, '1440': {'w': 2560, 'h': 1440, 'dim': '2560x1440'},
        '2160': {'w': 3840, 'h': 2160, 'dim': '3840x2160'}}
    res_details = resolution_map.get(data.get('resolution', '1080'), resolution_map['1080'])
    res_wh, res_dim = f"{res_details['w']}:{res_details['h']}", res_details['dim']
    
    audio_codec_val = data.get('audio_codec')
    if data.get('audio_enabled') == 'yes':
        if audio_codec_val == 'aac':
            audio_params = '-c:a aac -b:a 128k -ar 44100 -ac 2'
        elif audio_codec_val == 'pcm_alaw':
            audio_params = '-c:a pcm_alaw -ar 8000 -ac 1'
        else: # Default to AAC if audio is enabled but codec is unknown
            audio_params = '-c:a aac -b:a 128k -ar 44100 -ac 2' 
    else:
        audio_params = '-an'
        
    # --- Bitrate and GOP selection based on resolution and FPS ---
    # Determine target FPS (fallback to 15)
    try:
        target_fps_int = int(str(data.get('target_fps', '15')))
        if target_fps_int <= 0:
            target_fps_int = 15
    except Exception:
        target_fps_int = 15

    # Base bitrates (kbps) at 15 fps per resolution for each codec
    h264_base_kbps = {
        '480': 800,
        '720': 1500,
        '1080': 2500,
        '1440': 4500,
        '2160': 9000,
    }
    h265_base_kbps = {
        '480': 500,
        '720': 900,
        '1080': 1600,
        '1440': 3000,
        '2160': 6000,
    }
    mpeg4_base_kbps = {
        '480': 1000,
        '720': 2000,
        '1080': 4000,
        '1440': 7000,
        '2160': 12000,
    }

    # Scale bitrate approximately linearly with FPS relative to 15 fps
    fps_scale = max(0.5, min(2.0, target_fps_int / 15.0))

    def _select_bitrates_kbps(encoder_name: str, res_key: str):
        # Map encoder name to codec family
        if '265' in encoder_name or 'hevc' in encoder_name:
            base = h265_base_kbps
        elif 'mpeg4' in encoder_name:
            base = mpeg4_base_kbps
        else:
            base = h264_base_kbps
        base_kbps = base.get(res_key, base['1080'])
        target_kbps = int(base_kbps * fps_scale)
        maxrate_kbps = int(target_kbps * 1.2)
        bufsize_kbps = int(maxrate_kbps * 2)
        return target_kbps, maxrate_kbps, bufsize_kbps

    # Compute bitrate params and GOP
    b_kbps, max_kbps, buf_kbps = _select_bitrates_kbps(encoder_info['name'], data.get('resolution', '1080'))
    gop_val = max(2, target_fps_int * 2)

    # Build encoder-specific params
    enc_name, enc_type = encoder_info['name'], encoder_info['type']
    vid_params, hw_params = '', ''
    if enc_name == 'h264_nvenc':
        vid_params = f'-c:v h264_nvenc -preset llhq -rc:v vbr -cq:v 19 -b:v {b_kbps}k -maxrate {max_kbps}k -bufsize {buf_kbps}k -b_strategy 0 -bf 0 -g {gop_val} -keyint_min {gop_val}'
    elif enc_name == 'hevc_nvenc':
        vid_params = f'-c:v hevc_nvenc -preset llhq -rc:v vbr -cq:v 19 -b:v {b_kbps}k -maxrate {max_kbps}k -bufsize {buf_kbps}k -b_strategy 0 -bf 0 -g {gop_val} -keyint_min {gop_val}'
    elif enc_name == 'h264_vaapi':
        hw_params = '-hwaccel vaapi -hwaccel_device /dev/dri/renderD128 -hwaccel_output_format vaapi'
        vid_params = f'-vf "format=nv12,hwupload,scale_vaapi={res_wh}:force_original_aspect_ratio=decrease" -c:v h264_vaapi -qp 23 -b:v {b_kbps}k -maxrate {max_kbps}k -bufsize {buf_kbps}k -b_strategy 0 -bf 0 -g {gop_val} -keyint_min {gop_val}'
    elif enc_name == 'hevc_vaapi':
        hw_params = '-hwaccel vaapi -hwaccel_device /dev/dri/renderD128 -hwaccel_output_format vaapi'
        vid_params = f'-vf "format=nv12|vaapi,hwupload,scale_vaapi={res_wh}:force_original_aspect_ratio=decrease" -c:v hevc_vaapi -qp 23 -b:v {b_kbps}k -maxrate {max_kbps}k -bufsize {buf_kbps}k -b_strategy 0 -bf 0 -g {gop_val} -keyint_min {gop_val}'
    elif enc_name == 'libx264':
        vid_params = f'-c:v libx264 -preset veryfast -profile:v baseline -level 3.0 -s {res_dim} -b_strategy 0 -bf 0 -g {gop_val} -keyint_min {gop_val} -b:v {b_kbps}k -maxrate {max_kbps}k -bufsize {buf_kbps}k -pix_fmt yuv420p -movflags +faststart'
    elif enc_name == 'libx265':
        vid_params = f'-c:v libx265 -preset veryfast -tune zerolatency -profile:v main -level 4.0 -s {res_dim} -b_strategy 0 -bf 0 -g {gop_val} -keyint_min {gop_val} -b:v {b_kbps}k -maxrate {max_kbps}k -bufsize {buf_kbps}k -pix_fmt yuv420p'
    elif enc_name == 'mpeg4':
        vid_params = f'-c:v mpeg4 -s {res_dim} -b:v {b_kbps}k -b_strategy 0 -bf 0 -g {gop_val} -keyint_min {gop_val} -pix_fmt yuv420p'
    else: raise ValueError(f"Unsupported encoder: {enc_name}")
    
    source_url_val = data.get('source_url','') # ensure source_url_val is defined
    if data['stream_type'] == 'rtsp':
        # Check if it's a YouTube URL
        if config.ENABLE_YOUTUBE_SUPPORT and any(domain in source_url_val.lower() for domain in ['youtube.com', 'youtu.be', 'youtube-nocookie.com']):
            # Use yt-dlp to get the best stream URL
            input_cmd = f'-re -i "$(yt-dlp -f best -g \'{source_url_val}\')"'
        else:
            input_cmd = f"-re -i '{source_url_val}'"
    elif data['stream_type'] == 'file':
        input_cmd = f"-re -stream_loop -1 -i '{data['video_file_path']}'"
    else: # Should not happen due to prior validation
        input_cmd = ""
        
    # Create HLS directory for this stream
    hls_dir = os.path.join(config.HLS_DIR, stream_name)
    os.makedirs(hls_dir, exist_ok=True)
    
    cmd_parts = ["ffmpeg"]
    if hw_params: cmd_parts.append(hw_params)
    cmd_parts.extend([input_cmd, audio_params, vid_params, f"-r {target_fps_int}"])
    if enc_type != 'hardware_amd' and f'-s {res_dim}' not in vid_params: cmd_parts.append(f"-s {res_dim}")
    
    # For now, let's use RTSP only to avoid dual output issues
    # We'll implement HLS conversion separately for better stability
    rtsp_output = f"-f rtsp -rtsp_transport tcp -rtsp_flags prefer_tcp rtsp://localhost:8554/{stream_name}"
    
    cmd_parts.append(rtsp_output)
    cmd_str = " ".join(filter(None, cmd_parts))
    
    # Start HLS conversion in background after a short delay
    def start_hls_conversion():
        time.sleep(5)  # Wait for RTSP stream to start
        hls_cmd = f"ffmpeg -i rtsp://localhost:8554/{stream_name} -c:v copy -c:a copy -f hls -hls_time {config.HLS_SEGMENT_DURATION} -hls_list_size {config.HLS_PLAYLIST_SIZE} -hls_flags delete_segments+append_list+independent_segments -hls_segment_filename {hls_dir}/segment_%03d.ts -hls_allow_cache 0 {hls_dir}/playlist.m3u8"
        subprocess.Popen(hls_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Start HLS conversion in background thread
    hls_thread = threading.Thread(target=start_hls_conversion, daemon=True)
    hls_thread.start()
    dur_hr = data.get('duration_hours', '0'); 
    if dur_hr.isdigit() and int(dur_hr) > 0: 
        # Use cross-platform timeout approach
        if config.IS_WINDOWS:
            # Windows doesn't have timeout command, we'll handle duration in Python
            pass  # Duration will be handled by the monitoring thread
        elif config.IS_MACOS:
            # macOS doesn't have timeout command by default, use gtimeout if available or handle in Python
            if shutil.which('gtimeout'):
                cmd_str = f"gtimeout {int(dur_hr)*3600} {cmd_str}"
            # Otherwise, duration will be handled by the monitoring thread
        else:
            # Linux - use timeout command
            cmd_str = f"timeout {int(dur_hr)*3600} {cmd_str}"
    return cmd_str

def _get_stream_paths(name):
    return {k: os.path.join(d, f"ffmpeg_{name}{ext}") for k, d, ext in [
        ('log_file', LOG_DIR, ".log"), ('out_file', LOG_DIR, ".out"), ('err_file', LOG_DIR, ".err"),
        ('pid_file', PID_DIR, ".pid"), ('status_file', STATUS_DIR, ".status"), ('error_file', STATUS_DIR, ".error"),
        ('crash_report_file', CRASH_LOG_DIR, "_crash.log")]}

def _update_status(paths, status_msg, error_msg=None):
    try:
        with open(paths['status_file'], 'w') as f: f.write(status_msg)
        if error_msg: 
            with open(paths['error_file'], 'w') as f: f.write(error_msg)
        elif os.path.exists(paths['error_file']) and status_msg in ["running", "stopped"]:
            try: os.remove(paths['error_file'])
            except OSError: pass # Ignore if file is already gone or locked
    except Exception as e: app.logger.error(f"Error updating status files for {paths.get('status_file')}: {e}")

def _log(p, msg): 
    try: 
        # p is the paths dictionary, log_file is paths['log_file']
        log_file_path = p.get('log_file')
        stream_name = os.path.basename(log_file_path).replace("ffmpeg_", "").replace(".log", "") # Extract stream name

        if not log_file_path:
            app.logger.error(f"Log file path not found in paths dict for message: {msg}")
            return

        handler = _get_stream_log_handler(log_file_path)
        
        # Use a unique logger name for each stream to avoid handler conflicts or duplications
        logger_name = f"stream.{stream_name}"
        stream_logger = logging.getLogger(logger_name)
        
        # Check if this specific handler is already added to this specific logger
        # This is important if _log can be called multiple times for the same stream context
        already_has_handler = False
        for h in stream_logger.handlers:
            if isinstance(h, RotatingFileHandler) and h.baseFilename == handler.baseFilename:
                already_has_handler = True
                break
        
        if not already_has_handler:
            stream_logger.addHandler(handler)
            stream_logger.setLevel(logging.INFO) # Or configurable, e.g., from main app log level
            stream_logger.propagate = False # Do not propagate to the root logger

        stream_logger.info(msg)

    except Exception as e: 
        # Fallback to app.logger if stream-specific logging fails catastrophically
        app.logger.error(f"[Original Stream: {stream_name}] Error writing to stream log {p.get('log_file', 'N/A')}: {e}", exc_info=True)

def _read_log_tail(file_path, num_lines):
    try:
        if not os.path.exists(file_path): return [f"Log file {file_path} not found."]
        with open(file_path, 'r') as f: lines = f.readlines()
        return [l.strip() for l in lines[-num_lines:]]
    except Exception as e: return [f"Error reading {file_path}: {e}"]

def _save_crash_report(name, paths, cmd, code, reason="Unknown"):
    _update_status(paths, "error", f"{reason} (Code: {code}) Report: {paths['crash_report_file']}")
    report = [f"FFmpeg Crash: {name} @ {time.strftime('%Y-%m-%d %H:%M:%S')}", f"Code: {code}, Reason: {reason}", f"Cmd: {cmd}", ""]
    for desc, key, n_lines in [("Wrapper", 'log_file', 50), ("STDOUT", 'out_file', 50), ("STDERR", 'err_file', 100)]:
        report.append(f"--- {desc} (last {n_lines}) ---"); report.extend(_read_log_tail(paths.get(key, ''), n_lines)); report.append("")
    report.append("--- System Info ---")
    try:
        report.append(f"Kernel: {' '.join(platform.uname())}")
        ff_ver = _run_command("ffmpeg -version"); report.append(f"FFmpeg: {ff_ver.stdout.splitlines()[0] if ff_ver.returncode==0 and ff_ver.stdout else 'N/A'}")
        if shutil.which("nvidia-smi"): report.append(f"NVIDIA: {_run_command('nvidia-smi --query-gpu=name,driver_version,utilization.gpu,memory.used --format=csv,noheader').stdout.strip() or 'N/A'}")
        if os.path.exists("/proc/loadavg"): 
            with open("/proc/loadavg", 'r') as f_load: report.append(f"Load: {f_load.read().strip()}")
        mem_proc = _run_command("free -h")
        if mem_proc.stdout:
            mem_lines = mem_proc.stdout.splitlines()
            mem_l = next((l for l in mem_lines if "Mem:" in l), "")
            report.append(f"Memory: {mem_l.split()[6] if len(mem_l.split()) > 6 else 'N/A'}")
        else:
            report.append("Memory: N/A (free -h failed)")
    except Exception as e: report.append(f"Sys Info Error: {e}")
    try: 
        with open(paths['crash_report_file'], 'w') as f: f.write("\n".join(report))
        _log(paths, f"Crash report: {paths['crash_report_file']}")
    except Exception as e: _log(paths, f"Error saving crash report: {e}")

def _terminate_process_group(pid, log_paths, stream_name):
    _log(log_paths, f"Terminating process group {pid} for {stream_name}")
    try: 
        os.killpg(pid, signal.SIGTERM)
        _log(log_paths, f"Sent SIGTERM to PGID {pid} for {stream_name}")
    except ProcessLookupError: _log(log_paths, f"PGID {pid} not found for SIGTERM."); return
    except Exception as e: _log(log_paths, f"Error sending SIGTERM to PGID {pid}: {e}")
    time.sleep(2) # Grace period
    try: 
        os.killpg(pid, signal.SIGKILL)
        _log(log_paths, f"Sent SIGKILL to PGID {pid} for {stream_name}")
    except ProcessLookupError: _log(log_paths, f"PGID {pid} not found for SIGKILL.")
    except Exception as e: _log(log_paths, f"Error sending SIGKILL to PGID {pid}: {e}")

def _monitor_ffmpeg(name, cmd, proc, duration_s, paths, stop_event):
    _log(paths, f"Monitor started for {name} (PID {proc.pid}).")
    start_t = time.time(); normal_exit = False
    try:
        while not stop_event.is_set():
            rc = proc.poll()
            if rc is not None:
                elapsed = time.time() - start_t
                _log(paths, f"{name} (PID {proc.pid}) exited (code {rc}) after {elapsed:.1f}s.")
                is_timeout_kill = ("timeout " in cmd or "gtimeout " in cmd) and rc == 124 # timeout utility exit code for timeout
                was_stopped_by_event = stop_event.is_set()
                
                if rc == 0 or (duration_s and is_timeout_kill and abs(elapsed - duration_s) < 20) or was_stopped_by_event:
                    _update_status(paths, "stopped", "Stream stopped normally."); normal_exit = True
                else:
                    reason = "FFmpeg crashed"
                    if ("timeout " in cmd or "gtimeout " in cmd) and rc != 0 and rc != 124: # Error from timeout utility itself or ffmpeg called by it
                        reason += f" (via timeout utility, code {rc})"
                    elif is_timeout_kill: # Timeout happened but not near expected duration_s (premature)
                        reason += f" (killed by timeout utility prematurely or unexpectedly, code {rc})"
                    _save_crash_report(name, paths, cmd, rc, reason)
                break 
            if duration_s and (time.time() - start_t) > duration_s and not stop_event.is_set():
                _log(paths, f"Duration {duration_s}s up for {name}. Terminating PID {proc.pid}.")
                _terminate_process_group(proc.pid, paths, name)
                # _terminate_process_group will attempt to kill, poll should pick it up soon
            if stop_event.wait(timeout=10): break
    except Exception as e: 
        _log(paths, f"Monitor error for {name} (PID {proc.pid if proc else 'N/A'}): {e}")
        if proc and proc.poll() is None: _save_crash_report(name, paths, cmd, -99, f"Monitor exception: {e}")
    finally:
        if proc: 
            if proc.stdout: proc.stdout.close()
            if proc.stderr: proc.stderr.close()
            if proc.poll() is None and stop_event.is_set(): 
                _log(paths, f"Ensuring {name} (PID {proc.pid}) is stopped due to stop_event.")
                _terminate_process_group(proc.pid, paths, name)
        if os.path.exists(paths['pid_file']): 
            try: os.remove(paths['pid_file'])
            except OSError: pass 
        if not normal_exit and not stop_event.is_set() and proc and proc.poll() is None:
             _save_crash_report(name, paths, cmd, -1, "Monitor ended; process may be running or unpolled")
        
        # Always set final status to "stopped" for cleanup, regardless of how the stream ended
        # This ensures crashed/errored streams don't persist indefinitely in the UI
        if not normal_exit:
            _log(paths, f"Setting final status to 'stopped' for cleanup of {name}")
            _update_status(paths, "stopped", "Stream cleanup completed")
        
        _log(paths, f"Monitor stopped for {name}.")
        active_streams.pop(name, None)
        
        # Only remove stream state from persistence if we're not shutting down
        if not _shutdown_in_progress:
            remove_stream_state(name)
        else:
            _log(paths, f"Preserving stream state for {name} due to shutdown")

def exec_and_monitor_ffmpeg(name, cmd, duration_hrs_str, data, encoder_info):
    if name in active_streams: return False, "Stream name active."
    paths = _get_stream_paths(name)
    for f_key in paths: 
        if os.path.exists(paths[f_key]): 
            try: os.remove(paths[f_key])
            except OSError as e: _log(paths, f"Could not remove old file {paths[f_key]}: {e}")
    _log(paths, f"Starting {name}. Cmd: {cmd}"); _update_status(paths, "starting")
    proc, out_log, err_log = None, None, None
    try:
        out_log = open(paths['out_file'], 'wb'); err_log = open(paths['err_file'], 'wb')
        proc = subprocess.Popen(cmd, shell=True, stdout=out_log, stderr=err_log, 
                                stdin=subprocess.DEVNULL, preexec_fn=os.setsid)
        app.logger.info(f"[{name}] Popen successful, PID: {proc.pid}")
        with open(paths['pid_file'], 'w') as f: f.write(str(proc.pid))
    except Exception as e: 
        _log(paths, f"Popen fail for {name}: {e}"); _save_crash_report(name, paths, cmd, -1, f"Popen fail: {e}")
        if out_log: out_log.close(); 
        if err_log: err_log.close()
        app.logger.info(f"[{name}] Returning False: Popen exception.")
        return False, f"FFmpeg Popen failed: {e}"
    
    time.sleep(0.5) 
    
    poll_result = proc.poll()
    app.logger.info(f"[{name}] proc.poll() result after 0.5s: {poll_result}")
    
    if poll_result is not None:
        rc = poll_result
        app.logger.info(f"[{name}] FFmpeg died immediately (code {rc}). Saving crash report.")
        _save_crash_report(name, paths, cmd, rc, "FFmpeg died immediately")
        if out_log: out_log.close(); 
        if err_log: err_log.close()
        if os.path.exists(paths['pid_file']): 
            try: os.remove(paths['pid_file'])
            except OSError: pass
        app.logger.info(f"[{name}] Returning False: FFmpeg failed on start.")
        return False, "FFmpeg failed on start."
    
    app.logger.info(f"[{name}] FFmpeg process seems alive. Updating status to running.")
    _update_status(paths, "running"); _log(paths, f"{name} running post-check.")
    
    dur_s = int(duration_hrs_str) * 3600 if duration_hrs_str.isdigit() and int(duration_hrs_str) > 0 else 0
    stop_ev = threading.Event()
    
    app.logger.info(f"[{name}] Starting monitor thread.")
    mon_thread = threading.Thread(target=_monitor_ffmpeg, args=(name, cmd, proc, dur_s, paths, stop_ev), daemon=True)
    mon_thread.start()
    
    initial_config = {
        'video_codec': data.get('video_codec', 'h264'),
        'resolution': data.get('resolution', '1080'),
        'target_fps': data.get('target_fps', '15'),
        'audio_enabled': data.get('audio_enabled', 'no'),
        'audio_codec': data.get('audio_codec', 'aac'),
        'hardware_accel': data.get('hardware_accel', 'no'),
        'duration_hours': data.get('duration_hours', '0'),
        'encoder_details': encoder_info,
        'stream_type': data.get('stream_type'),
        'source_url': data.get('source_url') if data.get('stream_type') == 'rtsp' else None,
        'video_file': data.get('video_file') if data.get('stream_type') == 'file' and data.get('file_source_type') != 'custom' else None,
        'file_source_type': data.get('file_source_type') if data.get('stream_type') == 'file' else None,
        'video_file_path': data.get('video_file_path') if data.get('stream_type') == 'file' else None,
    }
    app.logger.info(f"[{name}] Storing stream details in active_streams.")
    active_streams[name] = {
        'process': proc, 
        'thread': mon_thread, 
        'stop_event': stop_ev, 
        'paths': paths,
        'config': initial_config,
        'start_time': time.time()
    }
    
    # Save stream state for persistence
    save_stream_state(name, initial_config)
    
    app.logger.info(f"[{name}] Returning True: Stream started.")
    return True, "Stream started."

def allowed_file(filename):
    app.logger.info(f"Checking file: {filename} (repr: {repr(filename)})")
    has_dot = '.' in filename
    if not has_dot:
        app.logger.info(f"File {filename} has no dot.")
        return False
    ext_parts = filename.rsplit('.', 1)
    if len(ext_parts) < 2 or not ext_parts[1]: # Handle cases like ".bashrc" or "filename."
        app.logger.info(f"File {filename} has no valid extension part after splitting.")
        return False
    ext = ext_parts[1].lower()
    app.logger.info(f"Raw extension part: '{ext_parts[1]}', Lowercased: '{ext}' (repr: {repr(ext)})")
    
    allowed_exts = app.config['ALLOWED_VIDEO_EXTENSIONS']
    app.logger.info(f"Allowed extensions list (repr): {repr(allowed_exts)}")
    for allowed_ext_item in allowed_exts:
        app.logger.info(f"Comparing '{ext}' (repr: {repr(ext)}) with allowed item '{allowed_ext_item}' (repr: {repr(allowed_ext_item)}). Match: {ext == allowed_ext_item}")

    is_allowed = ext in allowed_exts
    app.logger.info(f"Is file extension '{ext}' allowed by 'in' operator? {is_allowed}")
    return is_allowed

@app.route('/uploader', methods=['POST'])
def uploader():
    app.logger.info(f"Uploader route hit. Request files: {request.files}")
    if 'file' not in request.files:
        app.logger.warning("Uploader: No file part in request.files.")
        return jsonify(success=False, message='No file part'), 400
    file = request.files['file']
    app.logger.info(f"File from request: {file}")
    if file.filename == '':
        app.logger.warning("Uploader: No file selected (filename is empty).")
        return jsonify(success=False, message='No selected file'), 400
    
    app.logger.info(f"Processing file: {file.filename}")
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # UPLOAD_FOLDER is now browseable_videos thanks to config.py change
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        app.logger.info(f"Attempting to save file to: {upload_path}")
        try:
            file.save(upload_path)
            app.logger.info(f"File {filename} saved successfully.")
            return jsonify(success=True, message=f'File "{filename}" uploaded successfully to {app.config["UPLOAD_FOLDER"]}!', filename=filename)
        except Exception as e:
            app.logger.error(f"Error saving uploaded file {filename}: {e}", exc_info=True)
            return jsonify(success=False, message=f'Error uploading file: {str(e)}'), 500
    else:
        app.logger.warning(f"File type not allowed for {file.filename}.")
        return jsonify(success=False, message=f'File type not allowed for "{file.filename}". Allowed types: { ", ".join(app.config["ALLOWED_VIDEO_EXTENSIONS"]) }'), 400

@app.route('/check_file_exists/<path:filename>')
def check_file_exists(filename):
    # Sanitize filename to prevent directory traversal issues, though secure_filename should handle most of it.
    # However, here we receive it as a path param, so be extra careful.
    # For simplicity, we assume secure_filename will be applied by client before calling or server before saving.
    # The primary goal here is just a name check.
    
    # Normalize to prevent trivial bypasses like "file.mp4" vs "./file.mp4"
    safe_filename = secure_filename(os.path.basename(filename)) 
    if not safe_filename:
        # This case might happen if filename is empty or just dots, etc.
        return jsonify(exists=False, checked_name="", message="Invalid filename for check."), 400

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
    app.logger.info(f"Checking for file existence: {file_path} (original given: {filename})")
    if os.path.exists(file_path):
        app.logger.info(f"File {safe_filename} exists at {file_path}.")
        return jsonify(exists=True, checked_name=safe_filename)
    else:
        app.logger.info(f"File {safe_filename} does not exist at {file_path}.")
        return jsonify(exists=False, checked_name=safe_filename)

@app.route('/')
def index_route(): 
    # Pass the main config object to the template
    return render_template('index.html', config=config)

@app.route('/list_videos')
def list_videos_route():
    vids = []
    browse_dir = os.path.abspath(getattr(config, 'BROWSEABLE_VIDEO_DIR', DEFAULT_BROWSEABLE_DIR))
    allowed_extensions = getattr(config, 'ALLOWED_VIDEO_EXTENSIONS', ['.mp4', '.m4v'])
    if os.path.isdir(browse_dir):
        for f in os.listdir(browse_dir):
            if f.lower().endswith(tuple(allowed_extensions)): 
                vids.append({'name': f, 'path': f})
    return jsonify(success=True, videos=vids, browse_directory=browse_dir)

@app.route('/start_stream', methods=['POST'])
def start_stream_route():
    try:
        data = request.get_json()
        if not data:
            return jsonify(success=False, message='No JSON data'), 400
        
        name = data.get('stream_name')
        if not name or not re.match(r'^[a-zA-Z0-9_-]+$', name): return jsonify(success=False, message='Bad stream name'), 400
        s_type = data.get('stream_type')
        if s_type not in ['rtsp', 'file']: return jsonify(success=False, message='Bad stream type'), 400
        
        source_url = data.get('source_url') # Define source_url before using it in conditions
        if s_type == 'rtsp' and not source_url:
             return jsonify(success=False, message='No RTSP URL'), 400
        elif s_type == 'file':
            file_source_type = data.get('file_source_type', 'custom') # Default to custom if not specified
            data['file_source_type'] = file_source_type # Ensure it's in data for later use by ffmpeg command construction
            
            if file_source_type == 'custom':
                custom_path = data.get('video_file_path')
                if not custom_path: return jsonify(success=False, message='No file path provided for custom source'), 400
                if not os.path.exists(custom_path): return jsonify(success=False, message=f'Custom file not found: {custom_path}'), 400
                if not os.path.isfile(custom_path): return jsonify(success=False, message=f'Custom path is not a file: {custom_path}'), 400
                
                # Corrected extension checking logic:
                # os.path.splitext(...)[1] gives '.ext'
                # config.ALLOWED_VIDEO_EXTENSIONS stores extensions without a leading dot (e.g., 'mp4')
                file_ext_with_dot = os.path.splitext(custom_path)[1].lower()
                if not file_ext_with_dot or file_ext_with_dot.lstrip('.') not in config.ALLOWED_VIDEO_EXTENSIONS:
                    return jsonify(success=False, message=f'Invalid file type for custom path. Allowed: {config.ALLOWED_VIDEO_EXTENSIONS}'), 400
                
                data['video_file_path'] = custom_path # This is already the absolute path
            elif file_source_type == 'folder':
                vid_f = data.get('video_file') # This will be the filename from dropdown
                if not vid_f: return jsonify(success=False, message='No video file selected from folder'), 400
                
                browse_dir = getattr(config, 'BROWSEABLE_VIDEO_DIR', DEFAULT_BROWSEABLE_DIR)
                vid_p = os.path.join(browse_dir, os.path.basename(vid_f)) # Construct path
                
                if not os.path.exists(vid_p): return jsonify(success=False, message=f'File from folder not found: {vid_p}'), 400
                if not os.path.isfile(vid_p): return jsonify(success=False, message=f'Path from folder is not a file: {vid_p}'), 400
                data['video_file_path'] = vid_p # Set the absolute path for ffmpeg
            else:
                return jsonify(success=False, message='Invalid file_source_type'), 400
            
        if data.get('resolution', '1080') not in ['480', '720', '1080', '1440', '2160']: return jsonify(success=False, message='Bad resolution'), 400
        vid_codec = data.get('video_codec', 'h264')
        hw_accel = data.get('hardware_accel') == 'yes'
        avail_encs = get_available_encoders()
        if not avail_encs or not avail_encs.get(vid_codec): return jsonify(success=False, message=f"No encoders for {vid_codec}. Avail: {list(avail_encs.keys()) if avail_encs else 'None'}"), 400
        enc_info = get_best_encoder(vid_codec, avail_encs, hw_accel)
        ff_cmd = construct_ffmpeg_command(data, enc_info)
        ok, msg = exec_and_monitor_ffmpeg(name, ff_cmd, data.get('duration_hours', '0'), data, enc_info)
        if ok: return jsonify(success=True, message=msg, stream_url=f"rtsp://localhost:8554/{name}", ffmpeg_command=ff_cmd)
        else: 
            return jsonify(success=False, message=msg, ffmpeg_command=ff_cmd), 400
    except ValueError as e: return jsonify(success=False, message=str(e)), 400
    except Exception as e:
        app.logger.error(f"/start_stream error: {e}", exc_info=True)
        return jsonify(success=False, message=f"Server error: {str(e)}"), 500

def _get_server_ip():
    """Get the server's IP address"""
    try:
        # Try to get the IP from hostname first
        import socket
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        # If it's localhost, try to get external IP
        if ip.startswith('127.'):
            # Try to get the default route interface IP
            result = _run_command("ip route get 1 | awk '{print $7;exit}'")
            if result.returncode == 0 and result.stdout.strip():
                ip = result.stdout.strip()
        return ip
    except:
        return 'localhost'

@app.route('/get_active_streams', methods=['GET'])
def get_active_streams_route():
    output = []
    current_managed_streams = set(active_streams.keys())
    server_ip = _get_server_ip()
    
    for name, details in list(active_streams.items()): 
        status, error_msg = "unknown", ""
        try:
            if os.path.exists(details['paths']['status_file']):
                with open(details['paths']['status_file'], 'r') as f: status = f.read().strip()
            if os.path.exists(details['paths']['error_file']):
                with open(details['paths']['error_file'], 'r') as f: error_msg = f.read().strip()
        except Exception: pass
        
        # Calculate elapsed time
        elapsed_str = ""
        if 'start_time' in details:
            elapsed_seconds = int(time.time() - details['start_time'])
            days = elapsed_seconds // 86400
            hours = (elapsed_seconds % 86400) // 3600
            minutes = (elapsed_seconds % 3600) // 60
            if days > 0:
                elapsed_str = f"{days}d {hours:02d}h {minutes:02d}m"
            else:
                elapsed_str = f"{hours:02d}h {minutes:02d}m"
        
        # Calculate remaining time for streams with duration
        remaining_str = "Unlimited"
        config = details.get('config', {})
        duration_hours = config.get('duration_hours', '0')
        if duration_hours != '0' and 'start_time' in details:
            total_seconds = int(duration_hours) * 3600
            remaining_seconds = max(0, total_seconds - elapsed_seconds)
            if remaining_seconds > 0:
                r_days = remaining_seconds // 86400
                r_hours = (remaining_seconds % 86400) // 3600
                r_minutes = (remaining_seconds % 3600) // 60
                if r_days > 0:
                    remaining_str = f"{r_days}d {r_hours:02d}h {r_minutes:02d}m"
                else:
                    remaining_str = f"{r_hours:02d}h {r_minutes:02d}m"
            else:
                remaining_str = "Expired"
        
        # Get encoder details for display
        encoder_details = config.get('encoder_details', {})
        accel_type = 'cpu'
        if encoder_details:
            if encoder_details.get('type') == 'hardware_nvidia':
                accel_type = 'nvenc'
            elif encoder_details.get('type') == 'hardware_amd':
                accel_type = 'vaapi'
        
        # Get file info for display
        file_info = ''
        if config.get('stream_type') == 'file':
            if config.get('file_source_type') == 'custom':
                file_info = f"Custom: {os.path.basename(config.get('video_file_path', 'Unknown'))}"
            else:
                file_info = config.get('video_file', 'Unknown')
        
        output.append({
            'name': name, 
            'pid': details['process'].pid if details.get('process') else None, 
            'status': status, 
            'error': error_msg, 
            'managed': True,
            'config': config,
            'url': f"rtsp://{server_ip}:8554/{name}",  # Full RTSP URL
            'elapsed_time': elapsed_str,
            'remaining_time': remaining_str,
            'start_timestamp': details.get('start_time', 0),
            # Additional display fields from config
            'codec': config.get('video_codec', 'unknown'),
            'resolution': config.get('resolution', 'unknown'),
            'fps': config.get('target_fps', 'unknown'),
            'audio': 'none' if config.get('audio_enabled') == 'no' else config.get('audio_codec', 'unknown'),
            'accel_type': accel_type,
            'has_error': bool(error_msg),
            'crash_log_path': details['paths']['crash_report_file'] if error_msg and os.path.exists(details['paths']['crash_report_file']) else None,
            'file_info': file_info
        })
    
    # Handle orphaned streams
    try:
        for status_f_name in os.listdir(STATUS_DIR):
            if status_f_name.startswith("ffmpeg_") and status_f_name.endswith(".status"):
                stream_name_from_file = status_f_name.replace("ffmpeg_", "").replace(".status", "")
                if stream_name_from_file not in current_managed_streams:
                    paths = _get_stream_paths(stream_name_from_file)
                    s, e_msg = "unknown", ""
                    try:
                        with open(paths['status_file'], 'r') as sf: s = sf.read().strip()
                        if os.path.exists(paths['error_file']): 
                            with open(paths['error_file'], 'r') as ef: e_msg = ef.read().strip()
                    except Exception: pass
                    pid = None
                    try: 
                        if os.path.exists(paths['pid_file']): 
                            with open(paths['pid_file'],'r') as pf: pid_val = int(pf.read().strip())
                            # Check if process actually exists
                            if subprocess.run(["ps", "-p", str(pid_val)], capture_output=True, text=True).returncode == 0:
                                pid = pid_val
                            else: # Stale PID file
                                if s != 'stopped': s = 'error' # Mark as error if PID is gone but status wasn't stopped
                                e_msg = (e_msg + " (Stale PID)").strip()
                    except: pid = None
                    if s != "stopped": 
                         output.append({
                            'name': stream_name_from_file, 
                            'pid': pid, 
                            'status': s, 
                            'error': e_msg, 
                            'managed': False,
                            'config': {},
                            'url': f"rtsp://{server_ip}:8554/{stream_name_from_file}",  # Full RTSP URL
                            'elapsed_time': '',
                            'remaining_time': '',
                            'start_timestamp': 0,
                            'codec': 'unknown',
                            'resolution': 'unknown', 
                            'fps': 'unknown',
                            'audio': 'unknown',
                            'accel_type': 'unknown',
                            'has_error': bool(e_msg),
                            'crash_log_path': paths['crash_report_file'] if e_msg and os.path.exists(paths['crash_report_file']) else None
                        })
    except Exception as e:
        app.logger.error(f"Error listing orphaned streams: {e}")

    # Sort by start timestamp (newest first)
    output.sort(key=lambda x: x.get('start_timestamp', 0), reverse=True)
    
    return jsonify(success=True, streams=output)

@app.route('/stop_stream', methods=['POST'])
def stop_stream_route():
    data = request.get_json(); name = data.get('stream_name')
    if not name: return jsonify(success=False, message="No stream_name"), 400
    paths = _get_stream_paths(name)
    if name in active_streams:
        details = active_streams[name]
        _log(paths, f"Stop request for {name} (PID {details['process'].pid if details.get('process') and details['process'].pid else 'N/A'}).")
        details['stop_event'].set()
        proc = details.get('process')
        if proc and proc.pid:
            _terminate_process_group(proc.pid, paths, name)
        if details.get('thread') : details['thread'].join(timeout=7)
        _update_status(paths, "stopped", "Stream stopped by user.")
        active_streams.pop(name, None) # Ensure removal
        
        # Remove stream state from persistence
        remove_stream_state(name)
        
        if os.path.exists(paths['pid_file']): 
            try: os.remove(paths['pid_file'])
            except OSError: pass
        return jsonify(success=True, message=f"Stop sent to {name}.")
    else: 
        pid_to_kill = None
        if os.path.exists(paths['pid_file']):
            try:
                with open(paths['pid_file'], 'r') as f: pid_to_kill = int(f.read().strip())
            except Exception as e:
                 _log(paths, f"Could not read PID file for orphan {name}: {e}")
        if pid_to_kill:
            _log(paths, f"Stopping orphan {name} (PID {pid_to_kill}).")
            _terminate_process_group(pid_to_kill, paths, name)
            try: os.remove(paths['pid_file'])
            except OSError: pass
            _update_status(paths, "stopped", "Orphaned stream stopped.")
            
            # Remove stream state from persistence
            remove_stream_state(name)
            
            return jsonify(success=True, message=f"Stopped orphan {name} (PID {pid_to_kill}).")
        else: # No PID file, or couldn't read it.
            _update_status(paths, "stopped", "Orphaned stream (no PID) marked as stopped.") # Update status even if no PID
            return jsonify(success=False, message=f"{name} not actively managed and no PID file found. Marked as stopped."), 404

@app.route('/view_log/<log_type>/<stream_name>')
def view_log_route(log_type, stream_name):
    paths = _get_stream_paths(stream_name)
    log_key_map = {
        'main': 'log_file',
        'out': 'out_file',
        'err': 'err_file',
        'crash': 'crash_report_file'
    }
    if log_type not in log_key_map: return "Invalid log type.", 400
    file_path = paths.get(log_key_map[log_type])
    if not file_path or not os.path.exists(file_path):
        return f"Log for {stream_name} ({log_type}) not found.", 404
    
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        # Create HTML with line numbers
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Log Viewer - {stream_name} ({log_type})</title>
    <style>
        body {{
            font-family: monospace;
            background-color: #1e1e1e;
            color: #d4d4d4;
            margin: 0;
            padding: 20px;
        }}
        .log-header {{
            background-color: #2d2d30;
            border: 1px solid #3e3e42;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 5px;
        }}
        .log-header h1 {{
            margin: 0 0 10px 0;
            color: #4fc1ff;
            font-size: 20px;
        }}
        .log-info {{
            color: #9cdcfe;
            font-size: 14px;
        }}
        .log-content {{
            background-color: #1e1e1e;
            border: 1px solid #3e3e42;
            border-radius: 5px;
            overflow-x: auto;
        }}
        .log-line {{
            display: flex;
            border-bottom: 1px solid #2d2d30;
            transition: background-color 0.2s;
        }}
        .log-line:hover {{
            background-color: #2d2d30;
        }}
        .line-number {{
            background-color: #2d2d30;
            color: #858585;
            padding: 5px 15px;
            text-align: right;
            min-width: 60px;
            border-right: 1px solid #3e3e42;
            user-select: none;
        }}
        .line-content {{
            padding: 5px 15px;
            white-space: pre-wrap;
            word-wrap: break-word;
            flex: 1;
        }}
        /* Syntax highlighting for common log patterns */
        .log-error {{ color: #f48771; }}
        .log-warning {{ color: #dcdcaa; }}
        .log-info {{ color: #4fc1ff; }}
        .log-success {{ color: #4ec9b0; }}
        .log-timestamp {{ color: #9cdcfe; }}
        .search-box {{
            margin-bottom: 15px;
        }}
        .search-box input {{
            background-color: #3c3c3c;
            border: 1px solid #3e3e42;
            color: #cccccc;
            padding: 8px 12px;
            border-radius: 3px;
            width: 300px;
            font-family: monospace;
        }}
        .search-box button {{
            background-color: #0e639c;
            border: none;
            color: white;
            padding: 8px 15px;
            border-radius: 3px;
            cursor: pointer;
            margin-left: 10px;
        }}
        .search-box button:hover {{
            background-color: #1177bb;
        }}
        .highlight {{
            background-color: #ffd700;
            color: #000;
            padding: 0 2px;
        }}
        .stats {{
            color: #858585;
            font-size: 12px;
            margin-top: 10px;
        }}
    </style>
</head>
<body>
    <div class="log-header">
        <h1>Log Viewer: {stream_name}</h1>
        <div class="log-info">
            <strong>Log Type:</strong> {log_type.upper()} | 
            <strong>File:</strong> {os.path.basename(file_path)} | 
            <strong>Size:</strong> {os.path.getsize(file_path):,} bytes | 
            <strong>Lines:</strong> {len(lines):,}
        </div>
        <div class="search-box">
            <input type="text" id="searchInput" placeholder="Search in log..." onkeyup="searchLog(event)">
            <button onclick="searchLog()">Search</button>
            <button onclick="clearSearch()">Clear</button>
        </div>
    </div>
    
    <div class="log-content" id="logContent">
"""
        
        # Process each line
        for i, line in enumerate(lines, 1):
            # Escape HTML characters
            escaped_line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            
            # Apply syntax highlighting
            line_class = "line-content"
            if any(word in line.lower() for word in ['error', 'fail', 'exception', 'traceback']):
                line_class += " log-error"
            elif any(word in line.lower() for word in ['warning', 'warn']):
                line_class += " log-warning"
            elif any(word in line.lower() for word in ['info', 'starting', 'started']):
                line_class += " log-info"
            elif any(word in line.lower() for word in ['success', 'complete', 'done']):
                line_class += " log-success"
            
            # Highlight timestamps (common formats)
            import re
            escaped_line = re.sub(
                r'(\d{{4}}-\d{{2}}-\d{{2}}\s+\d{{2}}:\d{{2}}:\d{{2}})',
                r'<span class="log-timestamp">\1</span>',
                escaped_line
            )
            
            html_content += f"""
        <div class="log-line" data-line="{i}">
            <div class="line-number">{i}</div>
            <div class="{line_class}">{escaped_line}</div>
        </div>
"""
        
        html_content += """
    </div>
    
    <div class="stats">
        <p>End of log file</p>
    </div>
    
    <script>
        function searchLog(event) {
            if (event && event.key && event.key !== 'Enter') return;
            
            const searchTerm = document.getElementById('searchInput').value.toLowerCase();
            const lines = document.querySelectorAll('.log-line');
            
            // Clear previous highlights
            document.querySelectorAll('.highlight').forEach(el => {
                el.outerHTML = el.innerHTML;
            });
            
            if (!searchTerm) {
                lines.forEach(line => line.style.display = 'flex');
                return;
            }
            
            lines.forEach(line => {
                const content = line.querySelector('.line-content');
                const text = content.textContent.toLowerCase();
                
                if (text.includes(searchTerm)) {
                    line.style.display = 'flex';
                    // Highlight matching text
                    const regex = new RegExp(`(${searchTerm})`, 'gi');
                    content.innerHTML = content.innerHTML.replace(regex, '<span class="highlight">$1</span>');
                } else {
                    line.style.display = 'none';
                }
            });
        }
        
        function clearSearch() {
            document.getElementById('searchInput').value = '';
            const lines = document.querySelectorAll('.log-line');
            lines.forEach(line => line.style.display = 'flex');
            
            // Clear highlights
            document.querySelectorAll('.highlight').forEach(el => {
                el.outerHTML = el.innerHTML;
            });
        }
        
        // Auto-scroll to bottom on load
        window.onload = function() {
            window.scrollTo(0, document.body.scrollHeight);
        };
    </script>
</body>
</html>
"""
        return html_content
        
    except Exception as e:
        return f"Error reading log: {e}", 500

@app.route('/mediamtx/status', methods=['GET'])
def mediamtx_status_route():
    """Check MediaMTX status"""
    running, pid = _is_mediamtx_running()
    
    # Check if we can view the log
    log_exists = os.path.exists(MEDIAMTX_LOG_FILE)
    log_size = os.path.getsize(MEDIAMTX_LOG_FILE) if log_exists else 0
    
    return jsonify({
        'success': True,
        'running': running,
        'pid': pid,
        'log_exists': log_exists,
        'log_size': log_size,
        'binary_path': MEDIAMTX_BINARY,
        'config_path': MEDIAMTX_CONFIG,
        'rtsp_port': getattr(config, 'RTSP_PORT', 8554)
    })

@app.route('/mediamtx/restart', methods=['POST'])
def mediamtx_restart_route():
    """Restart MediaMTX server"""
    app.logger.info("MediaMTX restart requested")
    
    # Stop if running
    _stop_mediamtx()
    
    # Wait a moment
    time.sleep(1)
    
    # Start again
    success = _start_mediamtx()
    
    return jsonify({
        'success': success,
        'message': 'MediaMTX restarted successfully' if success else 'Failed to restart MediaMTX'
    })

@app.route('/mediamtx/log')
def mediamtx_log_route():
    """View MediaMTX log"""
    if not os.path.exists(MEDIAMTX_LOG_FILE):
        return "MediaMTX log not found", 404
    
    # Reuse the log viewer format
    try:
        with open(MEDIAMTX_LOG_FILE, 'r') as f:
            lines = f.readlines()
        
        # Create HTML with line numbers (similar to stream logs)
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MediaMTX Log</title>
    <style>
        body {{
            font-family: monospace;
            background-color: #1e1e1e;
            color: #d4d4d4;
            margin: 0;
            padding: 20px;
        }}
        .log-header {{
            background-color: #2d2d30;
            border: 1px solid #3e3e42;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 5px;
        }}
        .log-header h1 {{
            margin: 0 0 10px 0;
            color: #4fc1ff;
            font-size: 20px;
        }}
        .log-info {{
            color: #9cdcfe;
            font-size: 14px;
        }}
        .log-content {{
            background-color: #1e1e1e;
            border: 1px solid #3e3e42;
            border-radius: 5px;
            overflow-x: auto;
        }}
        .log-line {{
            display: flex;
            border-bottom: 1px solid #2d2d30;
            transition: background-color 0.2s;
        }}
        .log-line:hover {{
            background-color: #2d2d30;
        }}
        .line-number {{
            background-color: #2d2d30;
            color: #858585;
            padding: 5px 15px;
            text-align: right;
            min-width: 60px;
            border-right: 1px solid #3e3e42;
            user-select: none;
        }}
        .line-content {{
            padding: 5px 15px;
            white-space: pre-wrap;
            word-wrap: break-word;
            flex: 1;
        }}
        .log-error {{ color: #f48771; }}
        .log-warning {{ color: #dcdcaa; }}
        .log-info {{ color: #4fc1ff; }}
        .log-success {{ color: #4ec9b0; }}
    </style>
</head>
<body>
    <div class="log-header">
        <h1>MediaMTX Server Log</h1>
        <div class="log-info">
            <strong>File:</strong> {os.path.basename(MEDIAMTX_LOG_FILE)} | 
            <strong>Size:</strong> {os.path.getsize(MEDIAMTX_LOG_FILE):,} bytes | 
            <strong>Lines:</strong> {len(lines):,}
        </div>
    </div>
    
    <div class="log-content">
"""
        
        # Process each line
        for i, line in enumerate(lines, 1):
            # Escape HTML characters
            escaped_line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            
            # Apply syntax highlighting
            line_class = "line-content"
            if any(word in line.lower() for word in ['error', 'fail', 'exception']):
                line_class += " log-error"
            elif any(word in line.lower() for word in ['warning', 'warn']):
                line_class += " log-warning"
            elif any(word in line.lower() for word in ['info', 'stream ready']):
                line_class += " log-info"
            elif any(word in line.lower() for word in ['success', 'started']):
                line_class += " log-success"
            
            html_content += f"""
        <div class="log-line">
            <div class="line-number">{i}</div>
            <div class="{line_class}">{escaped_line}</div>
        </div>
"""
        
        html_content += """
    </div>
    
    <script>
        // Auto-scroll to bottom on load
        window.onload = function() {
            window.scrollTo(0, document.body.scrollHeight);
        };
    </script>
</body>
</html>
"""
        return html_content
        
    except Exception as e:
        return f"Error reading MediaMTX log: {e}", 500

@app.route('/get_video_info', methods=['POST'])
def get_video_info_route():
    data = request.get_json()
    original_file_path_req = data.get('file_path')

    if not original_file_path_req:
        return jsonify(success=False, error="File path is required."), 400

    resolved_file_path = None
    attempted_paths_log = []

    # 1. Check if original_file_path_req is an absolute path that exists and is a file
    if os.path.isabs(original_file_path_req):
        attempted_paths_log.append(f"Attempting absolute path: {original_file_path_req}")
        if os.path.exists(original_file_path_req) and os.path.isfile(original_file_path_req):
            resolved_file_path = original_file_path_req
            # TODO: Consider security validation for absolute paths if they can be arbitrary user input.
            # For now, if it's a valid file, we proceed. This is generally safe if paths from
            # custom input are expected to be trusted or further validated elsewhere.
        else:
            attempted_paths_log.append(f"Absolute path not found or not a file: {original_file_path_req}")
    
    # 2. If not resolved (either not absolute, or absolute but not found/not a file),
    #    treat as relative to UPLOAD_FOLDER. This handles dropdown values (filename only)
    #    and custom paths intended to be relative to UPLOAD_FOLDER.
    if not resolved_file_path:
        # Use os.path.basename to ensure we are only using the filename part if a relative path like 'folder/video.mp4' was given
        # and we intend it to be directly under UPLOAD_FOLDER.
        # If original_file_path_req is just 'video.mp4', basename doesn't change it.
        path_in_upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(original_file_path_req))
        attempted_paths_log.append(f"Attempting path in UPLOAD_FOLDER: {path_in_upload_folder}")
        if os.path.exists(path_in_upload_folder) and os.path.isfile(path_in_upload_folder):
            resolved_file_path = path_in_upload_folder
        else:
            attempted_paths_log.append(f"Path in UPLOAD_FOLDER not found or not a file: {path_in_upload_folder}")

    if not resolved_file_path:
        app.logger.warning(f"Video file not found. Original request: '{original_file_path_req}'. Attempted checks: {'; '.join(attempted_paths_log)}")
        # Return a more user-friendly message if possible, or distinguish between custom path and dropdown issues.
        return jsonify(success=False, error=f"File not found: {original_file_path_req}. Verified locations: UPLOAD_FOLDER, or if absolute path was provided."), 404

    # Proceed with cv2.VideoCapture(resolved_file_path)
    try:
        cap = cv2.VideoCapture(resolved_file_path)
        if not cap.isOpened():
            app.logger.error(f"Could not open video file with OpenCV: {resolved_file_path}")
            return jsonify(success=False, error=f"Could not open video file: {os.path.basename(original_file_path_req)}."), 500

        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
        
        codec_tag_string = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
        codec_long_name = codec_tag_string # Placeholder, as discussed.

        cap.release()

        details = {
            'fps': round(fps, 2) if fps and fps > 0 else 'N/A',
            'width': width,
            'height': height,
            'codec_tag_string': codec_tag_string.strip() if codec_tag_string.strip() else 'N/A',
            'codec_long_name': codec_long_name.strip() if codec_long_name.strip() else 'N/A'
        }
        return jsonify(success=True, details=details)

    except Exception as e:
        app.logger.error(f"Error processing video file {resolved_file_path}: {str(e)}", exc_info=True)
        return jsonify(success=False, error=f"Error processing video '{os.path.basename(original_file_path_req)}': {str(e)}"), 500

@app.errorhandler(Exception)
def handle_unhandled_exception(e):
    app.logger.error(f"Unhandled exception: {e}", exc_info=True)
    return jsonify(success=False, message="An unhandled server error occurred."), 500

def cleanup_all_streams():
    global _shutdown_in_progress
    _shutdown_in_progress = True
    app.logger.info("Attempting to clean up all active streams on shutdown...")
    for stream_name in list(active_streams.keys()):
        details = active_streams.get(stream_name)
        if details:
            paths = details['paths']
            _log(paths, f"Shutdown: Stopping stream {stream_name}.")
            details['stop_event'].set()
            proc = details.get('process')
            if proc and proc.pid:
                _terminate_process_group(proc.pid, paths, stream_name)
            if details.get('thread'): 
                details['thread'].join(timeout=5)
            _update_status(paths, "stopped", "Stream stopped due to server shutdown.")
            
            # Don't remove stream state from persistence during shutdown
            # This allows streams to be restored on restart
    
    app.logger.info("Cleanup complete.")
    
    # Stop MediaMTX
    app.logger.info("Stopping MediaMTX server...")
    _stop_mediamtx()

import atexit
import signal

def signal_handler(signum, frame):
    """Handle SIGINT (Ctrl+C) and SIGTERM signals"""
    global _shutdown_in_progress
    app.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    _shutdown_in_progress = True
    cleanup_all_streams()
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)  # Termination signal

# Also register atexit as a fallback
atexit.register(cleanup_all_streams)

# --- Periodic Cleanup Task ---
def _delete_old_files(directory, retention_days, pattern="*"):
    if not os.path.isdir(directory):
        app.logger.warning(f"Cleanup: Directory not found {directory}")
        return 0, 0 # deleted_count, deleted_size
    
    app.logger.info(f"Cleanup: Checking {directory} for files older than {retention_days} days (pattern: {pattern})")
    now = time.time()
    deleted_count = 0
    deleted_size = 0

    for filename_path in glob.glob(os.path.join(directory, pattern)):
        try:
            if os.path.isfile(filename_path) or os.path.islink(filename_path): # Check if it's a file or a symlink
                stat_info = os.stat(filename_path) # os.stat() follows symlinks by default
                file_mtime = stat_info.st_mtime
                if (now - file_mtime) > (retention_days * 86400):
                    file_size_bytes = stat_info.st_size
                    os.remove(filename_path)
                    app.logger.info(f"Cleanup: Deleted old file {filename_path} (age: {(now - file_mtime)/86400:.1f} days, size: {file_size_bytes / (1024*1024):.2f} MB)")
                    deleted_count += 1
                    deleted_size += file_size_bytes
        except Exception as e:
            app.logger.error(f"Cleanup: Error deleting file {filename_path}: {e}")
    if deleted_count > 0:
        app.logger.info(f"Cleanup: Deleted {deleted_count} files from {directory} (pattern: {pattern}), freeing {deleted_size / (1024*1024):.2f} MB by age.")
    return deleted_count, deleted_size

def _enforce_max_dir_size(directory, max_size_mb, pattern="*"):
    if not os.path.isdir(directory):
        app.logger.warning(f"Cleanup: Directory not found for size enforcement {directory}")
        return 0, 0 # deleted_count, deleted_size_freed

    max_size_bytes = max_size_mb * 1024 * 1024
    app.logger.info(f"Cleanup: Checking directory {directory} (pattern: {pattern}) against max size {max_size_mb} MB.")
    total_size_bytes = 0
    files_with_mtime = []

    for filename_path in glob.glob(os.path.join(directory, pattern)):
        try:
            if os.path.isfile(filename_path) or os.path.islink(filename_path):
                stat_info = os.stat(filename_path)
                files_with_mtime.append((filename_path, stat_info.st_mtime, stat_info.st_size))
                total_size_bytes += stat_info.st_size
        except Exception as e:
            app.logger.error(f"Cleanup: Error statting file {filename_path} for size enforcement: {e}")

    current_size_mb = total_size_bytes / (1024 * 1024)
    app.logger.info(f"Cleanup: Directory {directory} (pattern: {pattern}) current size: {current_size_mb:.2f} MB.")

    deleted_count = 0
    deleted_size_freed = 0

    if total_size_bytes > max_size_bytes:
        app.logger.info(f"Cleanup: Directory {directory} (pattern: {pattern}) size {current_size_mb:.2f} MB exceeds limit {max_size_mb} MB. Deleting oldest files...")
        files_with_mtime.sort(key=lambda x: x[1]) # Sort files by modification time (oldest first)
        
        amount_to_free = total_size_bytes - max_size_bytes
        freed_this_cycle = 0

        for f_path, f_mtime, f_size_bytes in files_with_mtime:
            if freed_this_cycle >= amount_to_free: # Stop if we've freed enough
                break
            try:
                os.remove(f_path)
                freed_this_cycle += f_size_bytes
                deleted_count +=1
                deleted_size_freed += f_size_bytes
                app.logger.info(f"Cleanup: Max size enforcement deleted {f_path} (size: {f_size_bytes / (1024*1024):.2f} MB). Freed {freed_this_cycle / (1024*1024):.2f} MB so far for this rule.")
            except Exception as e:
                app.logger.error(f"Cleanup: Error deleting file {f_path} for size enforcement: {e}")
        
        if deleted_count > 0:
             app.logger.info(f"Cleanup: Max size enforcement deleted {deleted_count} files from {directory} (pattern: {pattern}), freeing {deleted_size_freed / (1024*1024):.2f} MB.")
    else:
        app.logger.info(f"Cleanup: Directory {directory} (pattern: {pattern}) size {current_size_mb:.2f} MB is within limit {max_size_mb} MB.")
    return deleted_count, deleted_size_freed

def _is_unlimited_stream(stream_name):
    """Check if a stream is set to unlimited duration by checking persistent state or active streams"""
    # First check active streams
    if stream_name in active_streams:
        config = active_streams[stream_name].get('config', {})
        return config.get('duration_hours', '0') == '0'
    
    # Check persistent streams
    try:
        persistent_streams = load_persistent_streams()
        if stream_name in persistent_streams:
            config = persistent_streams[stream_name].get('config', {})
            return config.get('duration_hours', '0') == '0'
    except Exception:
        pass
    
    return False

def periodic_cleanup_task():
    app.logger.info("Periodic cleanup task starting its loop.")
    while True:
        interval_hours = getattr(config, 'CLEANUP_INTERVAL_HOURS', 24)
        try:
            app.logger.info(f"Periodic cleanup cycle started.")
            # Cleanup based on age
            log_ret_days = getattr(config, 'LOG_RETENTION_DAYS', 7)
            _delete_old_files(config.LOG_DIR, log_ret_days, pattern="ffmpeg_*.out")
            _delete_old_files(config.LOG_DIR, log_ret_days, pattern="ffmpeg_*.err")
            # ffmpeg_*.log are handled by RotatingFileHandler now, but mediamtx.log is not.
            _delete_old_files(config.LOG_DIR, log_ret_days, pattern="mediamtx.log*") # For mediamtx.log and its potential manual rotations/backups
            
            crash_log_ret_days = getattr(config, 'CRASH_LOG_RETENTION_DAYS', 30)
            _delete_old_files(config.CRASH_LOG_DIR, crash_log_ret_days, pattern="*.log")
            
            # SMART CLEANUP: Preserve PID and status files for unlimited streams
            pid_status_ret_days = getattr(config, 'PID_STATUS_RETENTION_DAYS', 2)
            
            # Clean up PID files - but preserve unlimited streams
            if os.path.exists(config.PID_DIR):
                for filename in os.listdir(config.PID_DIR):
                    if filename.endswith('.pid'):
                        stream_name = filename.replace('ffmpeg_', '').replace('.pid', '')
                        if not _is_unlimited_stream(stream_name):
                            file_path = os.path.join(config.PID_DIR, filename)
                            file_age_days = (time.time() - os.path.getmtime(file_path)) / 86400
                            if file_age_days > pid_status_ret_days:
                                try:
                                    os.remove(file_path)
                                    app.logger.info(f"Cleaned up old PID file: {filename}")
                                except Exception as e:
                                    app.logger.error(f"Error deleting {file_path}: {e}")
                        else:
                            app.logger.debug(f"Preserving PID file for unlimited stream: {filename}")
            
            # Clean up status files - but preserve unlimited streams
            if os.path.exists(config.STATUS_DIR):
                for filename in os.listdir(config.STATUS_DIR):
                    if filename.startswith('ffmpeg_'):
                        stream_name = filename.replace('ffmpeg_', '').replace('.status', '').replace('.error', '')
                        if not _is_unlimited_stream(stream_name):
                            file_path = os.path.join(config.STATUS_DIR, filename)
                            file_age_days = (time.time() - os.path.getmtime(file_path)) / 86400
                            if file_age_days > pid_status_ret_days:
                                try:
                                    os.remove(file_path)
                                    app.logger.info(f"Cleaned up old status file: {filename}")
                                except Exception as e:
                                    app.logger.error(f"Error deleting {file_path}: {e}")
                        else:
                            app.logger.debug(f"Preserving status file for unlimited stream: {filename}")

            # Cleanup based on total directory size (applied after age-based deletion)
            max_log_dir_mb = getattr(config, 'MAX_LOG_DIR_SIZE_MB', 512)
            if max_log_dir_mb > 0:
                # This will apply to remaining .out, .err, and mediamtx.log files. 
                # ffmpeg_*.log files are managed by RotatingFileHandler, but their sum might still be part of this check implicitly if not excluded by pattern.
                # Let's make the pattern more specific for .out and .err files if we want to primarily target them for size cap after age. Or apply to all *.* if that is the intent.
                _enforce_max_dir_size(config.LOG_DIR, max_log_dir_mb, pattern="ffmpeg_*.out")
                _enforce_max_dir_size(config.LOG_DIR, max_log_dir_mb, pattern="ffmpeg_*.err")
                _enforce_max_dir_size(config.LOG_DIR, max_log_dir_mb, pattern="mediamtx.log*")
                # Consider a global cap for LOG_DIR as well if individual caps above aren't enough: _enforce_max_dir_size(config.LOG_DIR, max_log_dir_mb, pattern="*.*")

            max_crash_dir_mb = getattr(config, 'MAX_CRASH_LOG_DIR_SIZE_MB', 256)
            if max_crash_dir_mb > 0:
                _enforce_max_dir_size(config.CRASH_LOG_DIR, max_crash_dir_mb, pattern="*.log")

            app.logger.info(f"Periodic cleanup cycle finished. Next run in {interval_hours} hours.")
        except Exception as e:
            app.logger.error(f"Error in periodic_cleanup_task: {e}", exc_info=True)
        
        time.sleep(interval_hours * 3600)

if getattr(config, 'ENABLE_PERIODIC_CLEANUP', False) and config.CLEANUP_INTERVAL_HOURS > 0: # Check if cleanup is enabled and interval is positive
    app.logger.info("Periodic cleanup is ENABLED. Starting cleanup thread.")
    cleanup_thread = threading.Thread(target=periodic_cleanup_task, daemon=True)
    cleanup_thread.start()
else:
    app.logger.info("Periodic cleanup is DISABLED either by ENABLE_PERIODIC_CLEANUP or CLEANUP_INTERVAL_HOURS <= 0.")

# --- End Periodic Cleanup Task ---


def _get_process_stats(pid):
    """Get CPU and memory usage for a process"""
    try:
        import psutil
        process = psutil.Process(pid)
        cpu_percent = process.cpu_percent(interval=1)  # Get CPU usage over 1 second
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / (1024 * 1024)  # Convert to MB
        return {
            'cpu_percent': cpu_percent,
            'memory_mb': memory_mb,
            'status': process.status()
        }
    except:
        # If psutil is not available or process doesn't exist
        try:
            # Fallback to ps command
            result = _run_command(f"ps -p {pid} -o %cpu,rss,stat --no-headers")
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split()
                if len(parts) >= 2:
                    cpu_percent = float(parts[0])
                    memory_kb = float(parts[1])
                    memory_mb = memory_kb / 1024
                    return {
                        'cpu_percent': cpu_percent,
                        'memory_mb': memory_mb,
                        'status': parts[2] if len(parts) > 2 else 'unknown'
                    }
        except:
            pass
    return None

def _check_stream_health(name, details):
    """Check if a stream is healthy and should continue running"""
    paths = details['paths']
    proc = details.get('process')
    
    if not proc or proc.poll() is not None:
        return True  # Process already stopped
    
    # Check duration limit - BUT ONLY FOR NON-UNLIMITED STREAMS
    if 'start_time' in details:
        # Get the stream's duration setting from config
        config = details.get('config', {})
        duration_hours = config.get('duration_hours', '0')
        
        # Only apply duration limit if stream is NOT unlimited (duration_hours != '0')
        if duration_hours != '0':
            elapsed = time.time() - details['start_time']
            if elapsed > MAX_STREAM_DURATION:
                _log(paths, f"Stream {name} exceeded maximum duration ({elapsed:.0f}s > {MAX_STREAM_DURATION}s)")
                return False
        else:
            # For unlimited streams, just log that they're unlimited
            elapsed = time.time() - details['start_time']
            if elapsed % 3600 < 60:  # Log once per hour (approximately)
                _log(paths, f"Stream {name} is unlimited, running for {elapsed/3600:.1f} hours")
    
    # Check process stats
    stats = _get_process_stats(proc.pid)
    if stats:
        # Check CPU usage
        if stats['cpu_percent'] > MAX_CPU_USAGE:
            _log(paths, f"Stream {name} exceeded CPU limit ({stats['cpu_percent']:.1f}% > {MAX_CPU_USAGE}%)")
            return False
        
        # Check memory usage
        if stats['memory_mb'] > MAX_MEMORY_USAGE:
            _log(paths, f"Stream {name} exceeded memory limit ({stats['memory_mb']:.1f}MB > {MAX_MEMORY_USAGE}MB)")
            return False
        
        # Log current stats for monitoring
        _log(paths, f"Health check: CPU={stats['cpu_percent']:.1f}%, Memory={stats['memory_mb']:.1f}MB")
    
    # Check for errors in log files
    try:
        # Check error file
        if os.path.exists(paths['err_file']):
            with open(paths['err_file'], 'r') as f:
                # Read last 1000 bytes to check for recent errors
                f.seek(0, 2)  # Go to end
                file_size = f.tell()
                f.seek(max(0, file_size - 1000))  # Go back 1000 bytes
                recent_content = f.read().lower()
                
                # Look for critical error patterns
                critical_errors = ['error', 'failed', 'invalid', 'cannot', 'unable']
                error_count = sum(1 for error in critical_errors if error in recent_content)
                
                if error_count > 5:  # Too many errors
                    _log(paths, f"Stream {name} has too many errors in log ({error_count} error keywords found)")
                    return False
    except Exception as e:
        _log(paths, f"Error checking log file health: {e}")
    
    return True

def _health_monitor_thread():
    """Background thread to monitor health of all active streams"""
    while True:
        try:
            # Create a copy of active streams to avoid modification during iteration
            streams_to_check = list(active_streams.items())
            
            for name, details in streams_to_check:
                if name not in active_streams:
                    continue  # Stream was removed while we were checking
                
                if not _check_stream_health(name, details):
                    # Stream is unhealthy, stop it
                    app.logger.warning(f"Stopping unhealthy stream: {name}")
                    
                    # Set stop event
                    details['stop_event'].set()
                    
                    # Log the reason
                    _update_status(details['paths'], "error", "Stream stopped due to health check failure")
                    
                    # Terminate the process
                    proc = details.get('process')
                    if proc and proc.pid:
                        _terminate_process_group(proc.pid, details['paths'], name)
        
        except Exception as e:
            app.logger.error(f"Error in health monitor thread: {e}")
        
        # Sleep before next check
        time.sleep(HEALTH_CHECK_INTERVAL)

# Start health monitor thread when app starts
if config.ENABLE_HEALTH_MONITORING:
    health_monitor = threading.Thread(target=_health_monitor_thread, daemon=True)
    health_monitor.start()
    app.logger.info("Health monitoring enabled")

# --- Stream Persistence Management Routes ---

@app.route('/persistent_streams', methods=['GET'])
def get_persistent_streams_route():
    """Get all persistent streams"""
    try:
        persistent_streams = load_persistent_streams()
        return jsonify(success=True, streams=persistent_streams, enabled=config.ENABLE_STREAM_PERSISTENCE)
    except Exception as e:
        app.logger.error(f"Error getting persistent streams: {e}")
        return jsonify(success=False, message=str(e)), 500

@app.route('/clear_persistent_streams', methods=['POST'])
def clear_persistent_streams_route():
    """Clear all persistent streams"""
    try:
        if os.path.exists(config.STREAM_PERSISTENCE_FILE):
            os.remove(config.STREAM_PERSISTENCE_FILE)
        app.logger.info("Cleared all persistent streams")
        return jsonify(success=True, message="All persistent streams cleared")
    except Exception as e:
        app.logger.error(f"Error clearing persistent streams: {e}")
        return jsonify(success=False, message=str(e)), 500

@app.route('/restore_streams', methods=['POST'])
def restore_streams_route():
    """Manually trigger stream restoration"""
    try:
        restore_streams_on_startup()
        return jsonify(success=True, message="Stream restoration triggered")
    except Exception as e:
        app.logger.error(f"Error during manual stream restoration: {e}")
        return jsonify(success=False, message=str(e)), 500

# --- End Stream Persistence Management Routes ---

# --- Routes ---

@app.route('/cleanup_stale_streams', methods=['POST'])
def cleanup_stale_streams_route():
    """Clean up stale error streams that are no longer actively managed"""
    try:
        cleaned_count = 0
        current_managed_streams = set(active_streams.keys())
        
        # Look for status files that represent streams not in active_streams
        for status_f_name in os.listdir(STATUS_DIR):
            if status_f_name.startswith("ffmpeg_") and status_f_name.endswith(".status"):
                stream_name_from_file = status_f_name.replace("ffmpeg_", "").replace(".status", "")
                if stream_name_from_file not in current_managed_streams:
                    paths = _get_stream_paths(stream_name_from_file)
                    
                    # Check if it's in error state
                    try:
                        with open(paths['status_file'], 'r') as sf: 
                            status = sf.read().strip()
                        
                        if status == "error":
                            # Clean up this stale error stream
                            _log(paths, f"Cleaning up stale error stream: {stream_name_from_file}")
                            _update_status(paths, "stopped", "Stream cleanup completed via manual cleanup")
                            
                            # Remove persistent state if any
                            remove_stream_state(stream_name_from_file)
                            
                            cleaned_count += 1
                            app.logger.info(f"Cleaned up stale error stream: {stream_name_from_file}")
                            
                    except Exception as e:
                        app.logger.error(f"Error cleaning up stream {stream_name_from_file}: {e}")
        
        return jsonify(success=True, message=f"Cleaned up {cleaned_count} stale error streams", cleaned_count=cleaned_count)
        
    except Exception as e:
        app.logger.error(f"Error during stale stream cleanup: {e}")
        return jsonify(success=False, message=str(e)), 500

# HLS Streaming Routes
@app.route('/hls/<stream_name>/playlist.m3u8')
def hls_playlist(stream_name):
    """Serve HLS playlist for a stream"""
    try:
        hls_dir = os.path.join(config.HLS_DIR, stream_name)
        playlist_path = os.path.join(hls_dir, 'playlist.m3u8')
        
        if not os.path.exists(playlist_path):
            return "Playlist not found", 404
            
        with open(playlist_path, 'r') as f:
            content = f.read()
        
        return Response(content, mimetype='application/vnd.apple.mpegurl')
    except Exception as e:
        app.logger.error(f"Error serving HLS playlist for {stream_name}: {e}")
        return "Error serving playlist", 500

@app.route('/hls/<stream_name>/<segment>')
def hls_segment(stream_name, segment):
    """Serve HLS segment files"""
    try:
        hls_dir = os.path.join(config.HLS_DIR, stream_name)
        segment_path = os.path.join(hls_dir, segment)
        
        if not os.path.exists(segment_path):
            return "Segment not found", 404
            
        return send_file(segment_path, mimetype='video/mp2t')
    except Exception as e:
        app.logger.error(f"Error serving HLS segment {segment} for {stream_name}: {e}")
        return "Error serving segment", 500

@app.route('/stream/<stream_name>/view')
def stream_viewer(stream_name):
    """Stream viewer page"""
    return render_template('stream_viewer.html', stream_name=stream_name)

if __name__ == '__main__':
    # Validate configuration
    if hasattr(config, 'validate_config'):
        errors = config.validate_config()
        if errors:
            for error in errors:
                app.logger.error(f"Configuration error: {error}")
            sys.exit(1)
    
    # Restore streams from previous session
    restore_streams_on_startup()
    
    app.run(debug=config.DEBUG, host=config.HOST, port=config.PORT) 