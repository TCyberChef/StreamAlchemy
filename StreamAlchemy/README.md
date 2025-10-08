## Project: Python RTSP/File Streaming Interface

This application provides a web interface to start and manage video streams from RTSP URLs or local video files, re-encoding them to a specified format and serving them via an integrated MediaMTX RTSP server.

## Core Features (Python Interface)

*   **Input Sources:**
    *   RTSP streams
    *   YouTube live streams and videos (via yt-dlp)
    *   Local video files (MP4, M4V, etc.) via absolute custom paths.
*   **Customizable Output:**
    *   Adjust video codec (H.264, H.265, MPEG-4).
    *   Select resolution (480p, 720p, 1080p, 1440p, 2160p).
    *   Set target FPS.
    *   Enable/disable audio and select audio codec.
    *   Optional hardware acceleration (NVENC/VAAPI if available).
    *   Set stream duration or run indefinitely.
*   **Web Interface:**
    *   Start new streams with detailed configurations.
    *   View list of active streams with their status and parameters.
    *   Stop active streams.
    *   View logs for individual streams and the MediaMTX server.
*   **Backend:**
    *   Built with Python and Flask.
    *   Uses FFmpeg for video processing.
    *   Integrates MediaMTX for RTSP output.
*   **Automated Health Monitoring:** Monitors active streams and attempts to restart or clean up failed ones (configurable).

## Requirements

*   **Operating System:** Currently developed and tested on Linux (x64/amd64 architecture). Other OS compatibility is not guaranteed.
*   **Python:** Python 3.8+
*   **pip:** For installing Python packages.
*   **venv:** For creating isolated Python environments (recommended).
*   **FFmpeg:** Must be installed and accessible in the system's PATH. This is used for all video processing.
*   **yt-dlp:** Must be installed and accessible in the system's PATH if YouTube URL support is needed.
*   **MediaMTX:** The application includes a local MediaMTX binary (in the `mediamtx` directory relative to the project root) for serving RTSP streams. Ensure it has execute permissions.

## Setup and Running (Python Interface)

1.  **Clone the Repository:**
    ```bash
    git clone <repository_url>
    cd StreamAlchemy
    ```

2.  **Navigate to the Python Interface Directory:**
    ```bash
    cd python_interface
    ```

3.  **Install Dependencies & Run:**
    The `run.sh` script handles dependency installation and starting the application. It will:
    *   Activate the virtual environment (if `venv/bin/activate` exists).
    *   Attempt to kill any existing processes on port 5000 (the default Flask port).
    *   Install Python packages from `requirements.txt`.
    *   Start the Flask web application.

    To run (from the `python_interface` directory):
```bash
./run.sh
```
    *(Ensure `run.sh` has execute permissions: `chmod +x run.sh`)*

4.  **Access the Web Interface:**
    Open your web browser and go to `http://localhost:5000` (or the configured host/port if changed in `config.py` or via environment variables).

5.  **Using the Interface:**
    *   **Stream Type:** Choose "RTSP Stream" or "Video File".
    *   **RTSP Stream:** Provide the source RTSP URL.
    *   **Video File:** The interface now exclusively uses the "Custom Path" method. You will need to provide the full, absolute path to your video file on the server where the Python application is running (e.g., `/home/user/videos/myvideo.mp4`).
    *   Configure other parameters (stream name, codec, resolution, FPS, audio, duration, hardware acceleration) as needed.
    *   Click "Start Stream".
    *   Monitor active streams in the "Active Streams" section.

## Automated Testing

A basic automated tester is available in `python_interface/automated_tester.py`.
1.  Ensure the Flask application (from `python_interface`) is running.
2.  The tester will attempt to create a `test_videos` directory inside `python_interface` if it doesn't exist.
3.  For file-based tests, the tester expects a video file named `sample.mp4` inside `python_interface/test_videos/`. If this file is missing, file-based tests will be skipped.
    *(You can manually place a suitable `sample.mp4` there, or the main application script `python_interface/app.py` can be modified to generate one if FFmpeg is available and the file is missing during its startup, though the tester currently doesn't trigger this generation).*
    Alternatively, the test script itself can be modified to generate a test video if FFmpeg is available. Currently, it uses `ffmpeg -y -f lavfi -i testsrc=duration=10:size=1280x720:rate=30 -c:v libx264 -pix_fmt yuv420p python_interface/test_videos/sample.mp4` command.
4.  Run the tester from the project root directory:
```bash
python python_interface/automated_tester.py
```
    Or from within the `python_interface` directory:
```bash
python automated_tester.py
```

## Directory Structure Notes

*   **`python_interface/`**: Contains the main Python Flask application.
    *   `app.py`: The main Flask application file.
    *   `config.py`: Configuration for the Flask application.
    *   `run.sh`: Script to set up the environment and run the Flask app.
    *   `requirements.txt`: Python dependencies.
    *   `static/`: CSS and JavaScript for the web interface.
    *   `templates/`: HTML templates for the web interface.
    *   `test_videos/`: (Create this for test media) Intended for sample video files used by `automated_tester.py`.
    *   `automated_tester.py`: Script for automated testing of the application.
*   **`mediamtx/`**: Contains the MediaMTX RTSP server binary and its configuration (`mediamtx.yml`). The Python application starts/stops this server.

*(Previous README content describing a PHP/GitHub Actions based system has been superseded by this description of the Python/Flask application.)*

## Running as a Systemd Service

To run the StreamAlchemy application persistently on a server, you can set it up as a `systemd` service. This will allow the application to start on boot and restart automatically if it crashes.

**1. Create a Service File:**

Create a file named `stream_alchemy.service` in `/etc/systemd/system/` with the following content. Adjust paths and user/group as necessary.

```ini
[Unit]
Description=StreamAlchemy Application
After=network.target

[Service]
# use what user&password that can run systemd
User=root
Group=root
# full path to python_interface
WorkingDirectory=/home/user/StreamAlchemy-local-streaming/python_interface
# full path to run.sh
ExecStart=/home/user/StreamAlchemy-local-streaming/python_interface/run.sh
Restart=always
RestartSec=10
StandardOutput=append:/var/log/stream_alchemy/stream_alchemy_stdout.log
StandardError=append:/var/log/stream_alchemy/stream_alchemy_stderr.log
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
```

**Important Considerations for the Service File:**

*   **`User` and `Group`**: Change `your_user` and `your_group` to the actual username and group that should run the application. It's recommended to run services under a non-root user.
*   **`WorkingDirectory`**: Update this to the absolute path of the `python_interface` directory within your StreamAlchemy project.
*   **`ExecStart`**:
    *   This should be the absolute path to the `run.sh` script in your project directory.
    *   The `run.sh` script handles setting up the virtual environment, installing dependencies, and running the application.
    *   Make sure the script has executable permissions (`chmod +x run.sh`).
    *   The script will automatically create and use a virtual environment named `venv` if it doesn't exist.
*   **Logging**: `StandardOutput` and `StandardError` are redirected to log files. Ensure the specified user has write permissions to `/var/log/` or choose a different log path.
*   **`Environment="PYTHONUNBUFFERED=1"`**: This is useful for ensuring Python's output is written directly to the logs without excessive buffering.


**2. Create Necessary Directories and Set Permissions:**

The user specified in the service file (e.g., `your_user`) needs write access to several directories:
    *   **Log Directory**: If you're logging to files in `/var/log/` as in the example, you might need to pre-create the log files and set their ownership, or create a subdirectory within `/var/log/` owned by `your_user`.
```bash
sudo mkdir -p /var/log/stream_alchemy
sudo chown your_user:your_group /var/log/stream_alchemy
sudo chmod 755 /var/log/stream_alchemy
# Then change StandardOutput/Error in the service file to:
# StandardOutput=append:/var/log/stream_alchemy/stdout.log
# StandardError=append:/var/log/stream_alchemy/stderr.log
```

        Alternatively, direct logs to a path the user already owns (e.g., inside the project directory or user's home).
    *   **Application Temporary Directories**: Based on a typical `config.py` structure for this app, ensure `your_user` owns and can write to `BASE_TMP_DIR` and its subdirectories (e.g., `/tmp/stream_alchemy` or a path you configure).
        If `BASE_TMP_DIR` is `/tmp/stream_alchemy`, you might run:

```bash
sudo mkdir -p /tmp/stream_alchemy
sudo chown -R your_user:your_group /tmp/stream_alchemy
sudo chmod -R u+rwX,g+rX,o+rX /tmp/stream_alchemy # User gets R/W, group/other get R
```
    *   **Browseable Video Directory (if app writes to it)**: If your application (running as `your_user`) needs to write to `BROWSEABLE_VIDEO_DIR` (e.g., for uploads via the web interface), ensure `your_user` has write permissions there too.
```bash
sudo chown your_user:your_group /path/to/your/browseable_videos
sudo chmod u+rwx,g+rwx,o+rx /path/to/your/browseable_videos # Example permissions
```
    *   **Working Directory**: The `WorkingDirectory` itself (`/home/your_user/StreamAlchemy/python_interface`) and its contents should be readable by `your_user`, and writable where necessary (e.g., if `app.py` tries to create files locally, though most dynamic data should go to `BASE_TMP_DIR`).

**4. Enable and Start the Service:**

After creating the service file, configuring `config.py`, and setting up directories/permissions:

*   **Reload systemd:**
```bash
sudo systemctl daemon-reload
```
*   **Enable the service to start on boot:**
```bash
sudo systemctl enable stream_alchemy.service
```
*   **Start the service immediately:**
```bash
sudo systemctl start stream_alchemy.service
```
*   **Check the status of the service:**
```bash
sudo systemctl status stream_alchemy.service
```
*   **View logs:**
```bash
sudo journalctl -u stream_alchemy.service -f
```
    Or, if you used file logging in the service unit:
```bash
tail -f /var/log/stream_alchemy_stdout.log
tail -f /var/log/stream_alchemy_stderr.log
```

This setup provides a basic way to run your application as a service. For more advanced production deployments, consider using a dedicated WSGI server like Gunicorn or uWSGI in front of your Flask application, and potentially a reverse proxy like Nginx.

