# StreamAlchemy Python Interface Configuration

import os
import platform
import tempfile

# Detect operating system
SYSTEM = platform.system().lower()
IS_WINDOWS = SYSTEM == 'windows'
IS_MACOS = SYSTEM == 'darwin'
IS_LINUX = SYSTEM == 'linux'

# Base paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_DIR = "" # Retained for fallback or other uses, but /list_videos will use BROWSEABLE_VIDEO_DIR
BROWSEABLE_VIDEO_DIR = os.path.join(BASE_DIR, "browseable_videos") # New directory for browsable files

# Runtime directories - OS-specific temp directories
if IS_WINDOWS:
    DEFAULT_TMP_DIR = os.path.join(tempfile.gettempdir(), 'stream_alchemy')
else:
    DEFAULT_TMP_DIR = '/tmp/stream_alchemy'

BASE_TMP_DIR = os.environ.get('STREAM_ALCHEMY_TMP_DIR', DEFAULT_TMP_DIR)
LOG_DIR = os.path.join(BASE_TMP_DIR, "ffmpeg_logs")
CRASH_LOG_DIR = os.path.join(BASE_TMP_DIR, "ffmpeg_crash_logs")
PID_DIR = os.path.join(BASE_TMP_DIR, "pids")
STATUS_DIR = os.path.join(BASE_TMP_DIR, "status")

# Server configuration
HOST = os.environ.get('STREAM_ALCHEMY_HOST', '0.0.0.0')
PORT = int(os.environ.get('STREAM_ALCHEMY_PORT', '5000'))
DEBUG = os.environ.get('STREAM_ALCHEMY_DEBUG', 'False').lower() == 'true'

# RTSP server configuration
RTSP_HOST = os.environ.get('RTSP_HOST', 'localhost')
RTSP_PORT = int(os.environ.get('RTSP_PORT', '8554'))

# Health monitoring limits
MAX_CPU_USAGE = float(os.environ.get('MAX_CPU_USAGE', '90.0'))  # Percentage
MAX_MEMORY_USAGE = int(os.environ.get('MAX_MEMORY_USAGE', '2048'))  # MB
MAX_STREAM_DURATION = int(os.environ.get('MAX_STREAM_DURATION', str(48 * 3600)))  # Seconds
HEALTH_CHECK_INTERVAL = int(os.environ.get('HEALTH_CHECK_INTERVAL', '60'))  # Seconds

# FFmpeg defaults
DEFAULT_VIDEO_CODEC = os.environ.get('DEFAULT_VIDEO_CODEC', 'h264')
DEFAULT_AUDIO_CODEC = os.environ.get('DEFAULT_AUDIO_CODEC', 'aac')
DEFAULT_RESOLUTION = os.environ.get('DEFAULT_RESOLUTION', '1080')
DEFAULT_FPS = os.environ.get('DEFAULT_FPS', '15')
DEFAULT_DURATION_HOURS = os.environ.get('DEFAULT_DURATION_HOURS', '6')

# Feature flags
ENABLE_HEALTH_MONITORING = os.environ.get('ENABLE_HEALTH_MONITORING', 'True').lower() == 'true'
ENABLE_YOUTUBE_SUPPORT = True  # Enable YouTube URL support with yt-dlp
ENABLE_HARDWARE_ACCEL = os.environ.get('ENABLE_HARDWARE_ACCEL', 'True').lower() == 'true'

# OS-specific hardware acceleration support
HARDWARE_ACCEL_SUPPORT = {
    'windows': ['nvenc', 'qsv', 'amf'],
    'darwin': ['videotoolbox', 'nvenc'],  # macOS supports VideoToolbox and NVENC (on supported hardware)
    'linux': ['nvenc', 'vaapi', 'qsv']
}

# Default hardware acceleration for each OS
DEFAULT_HW_ACCEL = {
    'windows': 'nvenc',
    'darwin': 'videotoolbox',  # VideoToolbox is the best choice for macOS
    'linux': 'nvenc'
}

# Get available hardware acceleration for current OS
AVAILABLE_HW_ACCEL = HARDWARE_ACCEL_SUPPORT.get(SYSTEM, [])
DEFAULT_HW_ACCEL_FOR_OS = DEFAULT_HW_ACCEL.get(SYSTEM, 'nvenc')

# Security and limits
MAX_UPLOAD_SIZE = 4 * 1024 * 1024 * 1024
ALLOWED_VIDEO_EXTENSIONS = ['mp4', 'mkv', 'avi', 'mov', 'webm', 'flv', 'm4v']

# Folder for uploaded videos - now points to BROWSEABLE_VIDEO_DIR
UPLOAD_FOLDER = BROWSEABLE_VIDEO_DIR

# Flask Secret Key for session management (flash messages)
SECRET_KEY = os.environ.get('SECRET_KEY', 'a_very_secret_dev_key_please_change_in_prod')

# Logging
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Application Log specific (if not logging to console)
APP_LOG_FILE = os.environ.get('APP_LOG_FILE', os.path.join(BASE_TMP_DIR, "app.log")) # Default to a file in BASE_TMP_DIR
APP_LOG_MAX_BYTES = int(os.environ.get('APP_LOG_MAX_BYTES', 10*1024*1024)) # 10 MB
APP_LOG_BACKUP_COUNT = int(os.environ.get('APP_LOG_BACKUP_COUNT', 5))

# Per-stream FFmpeg wrapper log settings (ffmpeg_*.log files from _log function)
STREAM_LOG_MAX_BYTES = int(os.environ.get('STREAM_LOG_MAX_BYTES', 5*1024*1024)) # 5 MB per stream log
STREAM_LOG_BACKUP_COUNT = int(os.environ.get('STREAM_LOG_BACKUP_COUNT', 2))     # 2 backups per stream log

# Log/File Retention and Cleanup
ENABLE_PERIODIC_CLEANUP = os.environ.get('ENABLE_PERIODIC_CLEANUP', 'True').lower() == 'true'
CLEANUP_INTERVAL_HOURS = int(os.environ.get('CLEANUP_INTERVAL_HOURS', 24)) # Run cleanup daily
LOG_RETENTION_DAYS = int(os.environ.get('LOG_RETENTION_DAYS', 7)) # Keep logs for 7 days
PID_STATUS_RETENTION_DAYS = int(os.environ.get('PID_STATUS_RETENTION_DAYS', 2)) # Keep PID/status files for 2 days
CRASH_LOG_RETENTION_DAYS = int(os.environ.get('CRASH_LOG_RETENTION_DAYS', 30)) # Keep crash reports for 30 days
MAX_LOG_DIR_SIZE_MB = int(os.environ.get('MAX_LOG_DIR_SIZE_MB', 512)) # Max size for LOG_DIR (ffmpeg .out, .err, .log, mediamtx.log)
MAX_CRASH_LOG_DIR_SIZE_MB = int(os.environ.get('MAX_CRASH_LOG_DIR_SIZE_MB', 256)) # Max size for CRASH_LOG_DIR

# Optional external services
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL', '')

# MediaMTX settings
RTSP_PORT = 8554  # Default RTSP port for MediaMTX

# Stream Persistence settings
ENABLE_STREAM_PERSISTENCE = os.environ.get('ENABLE_STREAM_PERSISTENCE', 'True').lower() == 'true'
# Store persistence file in application directory instead of tmp to survive reboots
STREAM_PERSISTENCE_DIR = os.environ.get('STREAM_PERSISTENCE_DIR', os.path.join(BASE_DIR, 'data'))
STREAM_PERSISTENCE_FILE = os.path.join(STREAM_PERSISTENCE_DIR, "active_streams.json")
STREAM_PERSISTENCE_BACKUP_COUNT = int(os.environ.get('STREAM_PERSISTENCE_BACKUP_COUNT', 3))

def validate_config():
    """Validate configuration values"""
    errors = []
    
    # if not os.path.exists(VIDEO_DIR): # Commenting out as VIDEO_DIR is no longer used for scanned files
    #     errors.append(f"Video directory does not exist: {VIDEO_DIR}")
    
    # It's good practice to ensure the browseable directory exists or can be created by the app.
    # However, for now, we'll just define it. App startup can create it.

    if MAX_CPU_USAGE <= 0 or MAX_CPU_USAGE > 100:
        errors.append(f"MAX_CPU_USAGE must be between 0 and 100, got {MAX_CPU_USAGE}")
    
    if MAX_MEMORY_USAGE <= 0:
        errors.append(f"MAX_MEMORY_USAGE must be positive, got {MAX_MEMORY_USAGE}")
    
    if PORT < 1 or PORT > 65535:
        errors.append(f"PORT must be between 1 and 65535, got {PORT}")
    
    return errors

# Load optional local config overrides
try:
    from config_local import *
except ImportError:
    pass 