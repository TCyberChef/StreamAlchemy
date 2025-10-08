# StreamAlchemy Stream Persistence

This document describes the stream persistence feature that allows StreamAlchemy to save active streams to disk and restore them after service restarts.

## Overview

The stream persistence feature automatically saves the configuration of active streams to a JSON file on disk. When the service restarts, it reads this file and attempts to restore all previously active streams that haven't expired.

## Features

- **Automatic Persistence**: Stream configurations are automatically saved when streams start
- **Automatic Restoration**: Streams are automatically restored on service startup
- **Duration Awareness**: Streams that have exceeded their configured duration are not restored
- **File Validation**: For file-based streams, the system checks if source files still exist before restoration
- **Backup Protection**: The persistence file is backed up before each write operation
- **Manual Management**: API endpoints for manual management of persistent streams

## Configuration

The persistence feature is controlled by several configuration options in `config.py`:

```python
# Enable/disable stream persistence
ENABLE_STREAM_PERSISTENCE = True

# Location of the persistence file
STREAM_PERSISTENCE_FILE = os.path.join(BASE_TMP_DIR, "active_streams.json")

# Number of backup files to keep
STREAM_PERSISTENCE_BACKUP_COUNT = 3
```

### Environment Variables

You can also configure these settings using environment variables:

- `ENABLE_STREAM_PERSISTENCE`: Set to `"true"` or `"false"`
- `STREAM_PERSISTENCE_BACKUP_COUNT`: Number of backup files to keep

## How It Works

### Stream Lifecycle

1. **Stream Start**: When a stream is started via `/start_stream`, its configuration is saved to the persistence file
2. **Stream Stop**: When a stream is stopped (manually or automatically), its configuration is removed from the persistence file
3. **Service Restart**: On startup, the service reads the persistence file and attempts to restore all saved streams

### Persistence File Format

The persistence file is a JSON file with the following structure:

```json
{
  "stream_name": {
    "config": {
      "video_codec": "h264",
      "resolution": "1080",
      "target_fps": "30",
      "audio_enabled": "yes",
      "audio_codec": "aac",
      "hardware_accel": "no",
      "duration_hours": "2",
      "stream_type": "file",
      "video_file_path": "/path/to/video.mp4",
      "file_source_type": "custom"
    },
    "saved_at": 1703123456.789,
    "status": "active"
  }
}
```

### Restoration Logic

When restoring streams, the system performs several checks:

1. **Duration Check**: If a stream has a configured duration, the system calculates how much time has elapsed since it was saved. If the elapsed time exceeds the duration, the stream is not restored.

2. **File Existence Check**: For file-based streams, the system verifies that the source video file still exists at the specified path.

3. **Encoder Availability**: The system checks that the required video encoder is still available.

4. **Remaining Duration**: For streams with time limits, the remaining duration is calculated and used for the restored stream.

## API Endpoints

### Get Persistent Streams
```
GET /persistent_streams
```

Returns all currently saved persistent streams and the persistence status.

**Response:**
```json
{
  "success": true,
  "streams": {
    "stream_name": {
      "config": {...},
      "saved_at": 1703123456.789,
      "status": "active"
    }
  },
  "enabled": true
}
```

### Clear Persistent Streams
```
POST /clear_persistent_streams
```

Removes all saved persistent streams. This does not affect currently running streams.

**Response:**
```json
{
  "success": true,
  "message": "All persistent streams cleared"
}
```

### Manual Stream Restoration
```
POST /restore_streams
```

Manually triggers the stream restoration process. This can be useful for testing or if you want to restore streams without restarting the service.

**Response:**
```json
{
  "success": true,
  "message": "Stream restoration triggered"
}
```

## Use Cases

### Server Maintenance
When you need to restart the server for maintenance, active streams will be automatically restored when the service comes back online.

### Service Updates
During service updates or deployments, streams will persist across restarts.

### Power Outages
In case of unexpected shutdowns, streams will be restored when the system comes back online (assuming source files are still available).

### Development
During development, you can restart the service without losing your test streams.

## Limitations and Considerations

### File-Based Streams
- Source video files must remain at the same path for restoration to work
- If a file is moved or deleted, the stream will not be restored

### RTSP Streams
- RTSP sources must still be available and accessible
- Network connectivity issues may prevent restoration

### Duration Limits
- Streams with expired durations will not be restored
- The remaining duration is calculated based on elapsed time

### Hardware Encoders
- Hardware encoders must still be available on the system
- If hardware acceleration was used but is no longer available, restoration may fail

## Troubleshooting

### Streams Not Restoring

1. **Check the logs**: Look for restoration messages in the application logs
2. **Verify file paths**: Ensure source video files still exist at their original locations
3. **Check duration**: Verify that streams haven't exceeded their configured duration
4. **Encoder availability**: Ensure required encoders are still available

### Persistence File Issues

1. **File permissions**: Ensure the service has read/write access to the persistence file location
2. **Disk space**: Verify sufficient disk space for the persistence file
3. **Backup files**: Check if backup files exist if the main file is corrupted

### Manual Recovery

If automatic restoration fails, you can:

1. Use the `/persistent_streams` endpoint to view saved configurations
2. Manually recreate streams using the saved configurations
3. Clear persistent streams with `/clear_persistent_streams` if needed

## Testing

A test script is provided to verify the persistence functionality:

```bash
cd python_interface
python test_persistence.py
```

This script tests:
- Saving and loading stream configurations
- Multiple stream management
- Stream removal
- Duration expiry logic
- JSON file structure validation

## Security Considerations

- The persistence file may contain sensitive information like file paths or RTSP URLs
- Ensure appropriate file permissions on the persistence file
- Consider the security implications of automatically restoring streams on startup
- The persistence file location should be in a secure directory

## Performance Impact

- Minimal performance impact during normal operation
- Small disk I/O overhead when starting/stopping streams
- Startup time may increase slightly when restoring many streams
- Memory usage increases slightly to store persistence data

## Future Enhancements

Potential future improvements to the persistence feature:

- Encryption of the persistence file
- Stream priority levels for restoration order
- Conditional restoration based on system resources
- Integration with external configuration management systems
- Stream dependency management
- Automatic cleanup of expired persistence entries 