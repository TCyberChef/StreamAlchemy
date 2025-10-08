import requests
import subprocess
import json
import time
import os

# Configuration
FLASK_APP_URL = os.environ.get("FLASK_APP_URL", "http://localhost:5000")
FFPROBE_PATH = os.environ.get("FFPROBE_PATH", "ffprobe")

# Test video setup
TEST_VIDEOS_DIR = os.path.join(os.path.dirname(__file__), "test_videos")
SAMPLE_VIDEO_FILE_NAME = "sample.mp4" 
SAMPLE_VIDEO_PATH = os.path.join(TEST_VIDEOS_DIR, SAMPLE_VIDEO_FILE_NAME)

# A public RTSP stream for testing
PUBLIC_RTSP_SOURCE = "rtsp://wowzaec2demo.streamlock.net/vod/mp4:BigBuckBunny_115k.mov"

# --- API Test Functions ---
def test_api_list_videos():
    print("--- Testing API: /list_videos ---")
    try:
        response = requests.get(f"{FLASK_APP_URL}/list_videos", timeout=5)
        response.raise_for_status()
        data = response.json()
        if data.get("success") and isinstance(data.get("videos"), list) and not data.get("videos"):
            print("  PASS: /list_videos returned success and an empty videos list.")
            return True
        else:
            print(f"  FAIL: /list_videos unexpected response: {data}")
            return False
    except Exception as e:
        print(f"  FAIL: /list_videos error: {e}")
        return False
    finally:
        print("---------------------------------------\n")

def test_api_mediamtx_status():
    print("--- Testing API: /mediamtx/status ---")
    try:
        response = requests.get(f"{FLASK_APP_URL}/mediamtx/status", timeout=5)
        response.raise_for_status()
        data = response.json()
        if data.get("success") and "running" in data and "pid" in data:
            print(f"  PASS: /mediamtx/status returned success. Running: {data.get('running')}, PID: {data.get('pid')}")
            return True
        else:
            print(f"  FAIL: /mediamtx/status unexpected response: {data}")
            return False
    except Exception as e:
        print(f"  FAIL: /mediamtx/status error: {e}")
        return False
    finally:
        print("---------------------------------------\n")

def test_api_get_active_streams_lifecycle(test_payload):
    print(f"--- Testing API: /get_active_streams lifecycle for {test_payload['stream_name']} ---")
    stream_name = test_payload['stream_name']
    abs_payload = test_payload.copy()
    if abs_payload.get("video_file_path") == SAMPLE_VIDEO_PATH:
            abs_payload["video_file_path"] = os.path.abspath(SAMPLE_VIDEO_PATH)

    def get_streams():
        try:
            r = requests.get(f"{FLASK_APP_URL}/get_active_streams", timeout=5)
            r.raise_for_status()
            return r.json()
        except Exception as e_req:
            print(f"    [API Sub-Test Error] /get_active_streams: {e_req}")
            return None

    # 1. Check initially (stream should not be there or be stopped)
    print("  Step 1: Checking active streams before start...")
    streams_before = get_streams()
    if streams_before and streams_before.get("success"):
        found_before = any(s['name'] == stream_name and s['status'] == 'running' for s in streams_before.get("streams", []))
        if found_before:
            print(f"  FAIL: Stream '{stream_name}' found running before start.")
            stop_stream(stream_name) # Cleanup attempt
            return False
        print("  PASS: Stream not found or not running initially.")
    else:
        print("  FAIL: Could not get initial active streams list.")
        return False

    # 2. Start stream
    print(f"  Step 2: Starting stream '{stream_name}'...")
    start_resp = start_stream(abs_payload)
    if not start_resp or not start_resp.get("success"):
        print(f"  FAIL: Could not start stream '{stream_name}' for active_streams test. Response: {start_resp}")
        return False
    time.sleep(5) # Give it a moment to appear

    # 3. Check if stream is active
    print("  Step 3: Checking if stream is active...")
    streams_after_start = get_streams()
    if streams_after_start and streams_after_start.get("success"):
        active_stream_data = next((s for s in streams_after_start.get("streams", []) if s['name'] == stream_name), None)
        if active_stream_data and active_stream_data.get('status') in ['running', 'starting']:
            print(f"  PASS: Stream '{stream_name}' found active. Status: {active_stream_data.get('status')}")
        else:
            print(f"  FAIL: Stream '{stream_name}' not found active after start. Data: {streams_after_start}")
            stop_stream(stream_name) # Cleanup attempt
            return False
    else:
        print("  FAIL: Could not get active streams list after start.")
        stop_stream(stream_name) # Cleanup attempt
        return False

    # 4. Stop stream
    print(f"  Step 4: Stopping stream '{stream_name}'...")
    stop_resp = stop_stream(stream_name)
    if not stop_resp or not stop_resp.get("success"):
        print(f"  WARN: Failed to stop stream '{stream_name}' cleanly during active_streams test. Response: {stop_resp}")
        # Not failing the test for this, but it's a warning
    time.sleep(3) # Give it a moment to be processed

    # 5. Check if stream is stopped/gone
    print("  Step 5: Checking if stream is stopped/removed...")
    streams_after_stop = get_streams()
    if streams_after_stop and streams_after_stop.get("success"):
        found_after_stop = any(s['name'] == stream_name and s['status'] == 'running' for s in streams_after_stop.get("streams", []))
        if not found_after_stop:
            print(f"  PASS: Stream '{stream_name}' is stopped or removed from active list.")
        else:
            print(f"  FAIL: Stream '{stream_name}' still found running after stop.")
            print("---------------------------------------\n")
            return False
    else:
        print("  FAIL: Could not get active streams list after stop.")
        print("---------------------------------------\n")
        return False
    
    print(f"  SUCCESS: /get_active_streams lifecycle test for '{stream_name}' passed.")
    print("---------------------------------------\n")
    return True

# --- Test Cases Definition ---
TEST_CASES = [
    {
        "description": "File Source (Custom Path) H.264 720p 25fps No Audio (Software)",
        "payload": {
            "stream_name": "test_file_h264_720p_noaudio",
            "stream_type": "file",
            "file_source_type": "custom", # Explicitly use custom path
            "video_file_path": SAMPLE_VIDEO_PATH, # Use absolute path placeholder
            # "video_file": SAMPLE_VIDEO_FILE_NAME, # Not needed for custom path
            "video_codec": "h264",
            "resolution": "720",
            "target_fps": "25",
            "audio_enabled": "no",
            "hardware_accel": "no",
            "duration_hours": "0"
        },
        "expected_ffprobe": {
            "video": {
                "codec_name": "h264",
                "width": 1280,
                "height": 720,
                "avg_frame_rate_num": 25,
                "avg_frame_rate_den": 1,
            },
            "audio": None
        },
        "requires_sample_video": True # New flag
    },
    {
        "description": "File Source (Custom Path) H.264 480p 20fps AAC Audio (Software) - Formerly RTSP",
        "payload": {
            "stream_name": "test_file_h264_480p_aac_audio",
            "stream_type": "file",
            "file_source_type": "custom",
            "video_file_path": SAMPLE_VIDEO_PATH,
            "video_codec": "h264",
            "resolution": "480",
            "target_fps": "20",
            "audio_enabled": "yes",
            "audio_codec": "aac",
            "hardware_accel": "no",
            "duration_hours": "0"
        },
        "expected_ffprobe": {
            "video": {
                "codec_name": "h264",
                "width": 854, 
                "height": 480,
                "avg_frame_rate_num": 20,
                "avg_frame_rate_den": 1,
            },
            "audio": {
                "codec_name": "aac",
            }
        },
        "requires_sample_video": True # Now requires the sample video
    },
    {
        "description": "File Source (Custom Path) H.265 1080p 30fps AAC Audio (Software)",
        "payload": {
            "stream_name": "test_file_h265_1080p_audio",
            "stream_type": "file",
            "file_source_type": "custom",
            "video_file_path": SAMPLE_VIDEO_PATH,
            "video_codec": "h265",
            "resolution": "1080",
            "target_fps": "30",
            "audio_enabled": "yes",
            "audio_codec": "aac",
            "hardware_accel": "no",
            "duration_hours": "0"
        },
        "expected_ffprobe": {
            "video": {
                "codec_name": "hevc",
                "width": 1920,
                "height": 1080,
                "avg_frame_rate_num": 30,
                "avg_frame_rate_den": 1,
            },
            "audio": {
                "codec_name": "aac"
            }
        },
        "requires_sample_video": True
    }
]

# --- Helper Functions ---
def start_stream(payload):
    try:
        response = requests.post(f"{FLASK_APP_URL}/start_stream", json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"  [API ERROR] Failed to start stream {payload.get('stream_name')}: {e}")
        return None

def stop_stream(stream_name):
    try:
        response = requests.post(f"{FLASK_APP_URL}/stop_stream", json={"stream_name": stream_name}, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"  [API ERROR] Failed to stop stream {stream_name}: {e}")
        return None

def get_stream_info_ffprobe(stream_name, retries=3, delay=5):
    rtsp_url = f"rtsp://localhost:8554/{stream_name}"
    for attempt in range(retries):
        try:
            print(f"  Probing {rtsp_url} (attempt {attempt + 1}/{retries})...")
            time.sleep(delay) # Wait for stream to be fully up
            command = [
                FFPROBE_PATH,
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                "-timeout", "15000000", # 15 seconds timeout for ffprobe connection
                rtsp_url
            ]
            process = subprocess.run(command, capture_output=True, text=True, timeout=20)
            if process.returncode != 0:
                print(f"  [FFPROBE ERROR] ffprobe failed for {stream_name}. STDERR: {process.stderr}")
                continue # Retry
            
            return json.loads(process.stdout)
        except subprocess.TimeoutExpired:
            print(f"  [FFPROBE TIMEOUT] ffprobe timed out for {stream_name}.")
        except json.JSONDecodeError:
            print(f"  [FFPROBE ERROR] Failed to decode ffprobe JSON for {stream_name}.")
        except Exception as e:
            print(f"  [FFPROBE ERROR] An unexpected error occurred with ffprobe for {stream_name}: {e}")
    return None
    
def validate_stream(ffprobe_data, expected):
    if not ffprobe_data or "streams" not in ffprobe_data:
        return False, "No ffprobe data or streams array."

    results = {"video": "NOT_CHECKED", "audio": "NOT_CHECKED"}
    messages = []

    # Video validation
    video_stream = next((s for s in ffprobe_data["streams"] if s.get("codec_type") == "video"), None)
    if expected["video"]:
        if not video_stream:
            messages.append("FAIL: Expected video stream, none found.")
            results["video"] = "FAIL"
        else:
            v_expected = expected["video"]
            v_actual = video_stream
            mismatches = []
            for key, val_expected in v_expected.items():
                if key == "avg_frame_rate_den": # Skip explicit check for den, handled by avg_frame_rate_num
                    continue
                
                val_actual = v_actual.get(key)

                if key == "avg_frame_rate_num" and "avg_frame_rate" in v_actual:
                    try:
                        num_actual_str, den_actual_str = v_actual["avg_frame_rate"].split('/')
                        num_actual = int(num_actual_str)
                        den_actual = int(den_actual_str)
                        expected_den = v_expected.get("avg_frame_rate_den", 1)
                        
                        if val_expected != num_actual or expected_den != den_actual:
                             mismatches.append(f"FPS: expected {val_expected}/{expected_den}, got {v_actual['avg_frame_rate']}")
                    except ValueError:
                         mismatches.append(f"FPS: expected {val_expected}/{v_expected.get('avg_frame_rate_den',1)}, got unparsable {v_actual['avg_frame_rate']}")
                elif val_actual != val_expected:
                    mismatches.append(f"{key}: expected {val_expected}, got {val_actual}")
            
            if not mismatches:
                results["video"] = "PASS"
                messages.append("Video: PASS")
            else:
                results["video"] = "FAIL"
                messages.append(f"Video: FAIL ({', '.join(mismatches)})")
    elif video_stream:
        messages.append("FAIL: No video stream expected, but one was found.")
        results["video"] = "FAIL"
    else:
        results["video"] = "PASS" # Expected no video, and none found
        messages.append("Video: PASS (No video stream expected and none found)")


    # Audio validation
    audio_stream = next((s for s in ffprobe_data["streams"] if s.get("codec_type") == "audio"), None)
    if expected["audio"]:
        if not audio_stream:
            messages.append("FAIL: Expected audio stream, none found.")
            results["audio"] = "FAIL"
        else:
            a_expected = expected["audio"]
            a_actual = audio_stream
            mismatches = []
            for key, val_expected in a_expected.items():
                val_actual = a_actual.get(key)
                if val_actual != val_expected:
                    mismatches.append(f"{key}: expected {val_expected}, got {val_actual}")
            
            if not mismatches:
                results["audio"] = "PASS"
                messages.append("Audio: PASS")
            else:
                results["audio"] = "FAIL"
                messages.append(f"Audio: FAIL ({', '.join(mismatches)})")
    elif audio_stream:
        messages.append("FAIL: No audio stream expected, but one was found.")
        results["audio"] = "FAIL"
    else:
        results["audio"] = "PASS" # Expected no audio, and none found
        messages.append("Audio: PASS (No audio stream expected and none found)")

    overall_pass = all(r == "PASS" or r == "NOT_CHECKED" for r in results.values())
    return overall_pass, " | ".join(messages)

# --- Main Test Execution ---
if __name__ == "__main__":
    print("Starting StreamAlchemy Automated Tests...\n")
    api_tests_passed = 0
    api_tests_failed = 0
    stream_tests_run = 0
    stream_tests_passed = 0
    stream_tests_failed = 0
    stream_tests_skipped = 0

    # --- Run API Only Tests ---
    print("=== Running API Endpoint Sanity Tests ===")
    if test_api_list_videos(): api_tests_passed += 1
    else: api_tests_failed += 1
    
    if test_api_mediamtx_status(): api_tests_passed += 1
    else: api_tests_failed += 1
    
    # Select one simple stream case for the /get_active_streams lifecycle test
    # to avoid running it for every single ffprobe test case.
    # Use the first file-based test if sample video exists, otherwise first RTSP test.
    lifecycle_test_payload = None
    sample_video_exists_for_lifecycle = os.path.exists(SAMPLE_VIDEO_PATH)
    first_file_case = next((c for c in TEST_CASES if c["payload"]["stream_type"] == "file"), None)
    first_rtsp_case = next((c for c in TEST_CASES if c["payload"]["stream_type"] == "rtsp"), None)

    if sample_video_exists_for_lifecycle and first_file_case:
        lifecycle_test_payload = first_file_case["payload"]
    elif first_rtsp_case:
        lifecycle_test_payload = first_rtsp_case["payload"]
    
    if lifecycle_test_payload:
        if test_api_get_active_streams_lifecycle(lifecycle_test_payload): api_tests_passed += 1
        else: api_tests_failed += 1
    else:
        print("SKIPPING /get_active_streams lifecycle test as no suitable test case found.")
        # Consider this a skip or a pass depending on strictness, for now, just note it.

    print("=== API Endpoint Sanity Tests Complete ===\n")

    # --- Run Stream Validation Test Cases ---
    print("=== Running Stream Validation Test Cases (with FFprobe) ===")
    # Ensure test_videos directory exists
    if not os.path.isdir(TEST_VIDEOS_DIR):
        os.makedirs(TEST_VIDEOS_DIR)
        print(f"INFO: Created directory {TEST_VIDEOS_DIR}")
        print(f"INFO: Please place '{SAMPLE_VIDEO_FILE_NAME}' in this directory for file-based tests.")

    sample_video_exists = os.path.exists(SAMPLE_VIDEO_PATH)
    if not sample_video_exists:
        print(f"WARNING: Sample video '{SAMPLE_VIDEO_FILE_NAME}' not found at: {SAMPLE_VIDEO_PATH}")
        print("File-based tests requiring it will be skipped.\n")

    for i, case in enumerate(TEST_CASES):
        stream_tests_run +=1 # count all attempts
        print(f"--- Stream Validation Test Case {i+1}: {case['description']} ---")
        
        # Resolve absolute path for video_file_path if it's a placeholder
        current_payload = case["payload"].copy()
        if current_payload.get("video_file_path") == SAMPLE_VIDEO_PATH: # Check if it needs resolving
            current_payload["video_file_path"] = os.path.abspath(SAMPLE_VIDEO_PATH)

        stream_name = current_payload["stream_name"]

        if case.get("requires_sample_video", False) and not sample_video_exists:
            print(f"  SKIPPING: Test requires '{SAMPLE_VIDEO_FILE_NAME}' which is missing.")
            stream_tests_skipped +=1
            print("---------------------------------------\n")
            continue

        start_response = start_stream(current_payload)
        if not start_response or not start_response.get("success"):
            print(f"  FAIL: Could not start stream. Response: {start_response}")
            if start_response and "ffmpeg_command" in start_response:
                print(f"  FFMPEG Command (from server): {start_response['ffmpeg_command']}")
            stream_tests_failed += 1
            stop_stream(stream_name) # Attempt cleanup
            print("---------------------------------------\n")
            continue

        print(f"  Stream '{stream_name}' started. Waiting for it to stabilize...")
        time.sleep(10) # Wait for FFmpeg to initialize fully and RTSP server to be ready

        ffprobe_info = get_stream_info_ffprobe(stream_name)

        if not ffprobe_info:
            print(f"  FAIL: Could not get ffprobe info for {stream_name}.")
            stream_tests_failed += 1
        else:
            is_valid, validation_messages = validate_stream(ffprobe_info, case["expected_ffprobe"])
            print(f"  Validation: {validation_messages}")
            if is_valid:
                print("  RESULT: PASS")
                stream_tests_passed += 1
            else:
                print("  RESULT: FAIL")
                stream_tests_failed += 1
        
        print(f"  Stopping stream '{stream_name}'...")
        stop_response = stop_stream(stream_name)
        if not stop_response or not stop_response.get("success"):
            print(f"  Warning: Could not cleanly stop stream {stream_name}. Response: {stop_response}")
        
        print("---------------------------------------\n")
        time.sleep(2) # Small delay between tests

    print("\n--- Test Summary ---")
    print("API Tests:")
    print(f"  Passed: {api_tests_passed}, Failed: {api_tests_failed}")
    print("Stream Validation Tests (FFprobe):")
    print(f"  Total Attempted: {stream_tests_run - stream_tests_skipped}") # From TEST_CASES excluding skipped
    print(f"  Passed: {stream_tests_passed}")
    print(f"  Failed: {stream_tests_failed}")
    print(f"  Skipped: {stream_tests_skipped}")
    print("--------------------")

    if api_tests_failed > 0 or stream_tests_failed > 0:
        print("\nSome tests FAILED. Please review logs.")
    elif api_tests_passed + stream_tests_passed > 0:
        print("\nAll runnable tests PASSED!")
    else:
        print("\nNo tests were run or passed. Check configuration and sample files.")
