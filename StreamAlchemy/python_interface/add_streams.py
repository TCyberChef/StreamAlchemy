#!/usr/bin/env python3
"""
StreamAlchemy - Bulk Video Stream Creator
This script loops over videos in a local folder and adds them as streams via API.

Features:
- Automatic stream name deduplication (appends 1, 2, etc. if name exists)
- Dry-run mode to preview actions
- Configurable stream settings
- Progress tracking and error handling
"""

import os
import sys
import json
import time
import requests
import argparse
from pathlib import Path
from typing import List, Dict, Optional

# Configuration
DEFAULT_API_URL = "http://localhost:5000"
DEFAULT_VIDEO_DIR = os.path.join(os.path.dirname(__file__), "browseable_videos")
ALLOWED_EXTENSIONS = ['mp4', 'mkv', 'avi', 'mov', 'webm', 'flv', 'm4v']

# Stream configuration defaults
DEFAULT_STREAM_CONFIG = {
    "video_codec": "h264",
    "resolution": "1080", 
    "target_fps": "15",
    "audio_enabled": "no",
    "hardware_accel": "no",
    "duration_hours": "0"  # 0 = unlimited
}

class StreamCreator:
    def __init__(self, api_url: str = DEFAULT_API_URL):
        self.api_url = api_url.rstrip('/')
        self.session = requests.Session()
        
    def test_connection(self) -> bool:
        """Test if the StreamAlchemy API is accessible"""
        try:
            response = self.session.get(f"{self.api_url}/get_active_streams", timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException as e:
            print(f"❌ API connection failed: {e}")
            return False
    
    def get_video_files(self, directory: str) -> List[Path]:
        """Get all video files from the specified directory"""
        video_dir = Path(directory)
        if not video_dir.exists():
            print(f"❌ Directory does not exist: {directory}")
            return []
        
        video_files = []
        for ext in ALLOWED_EXTENSIONS:
            # Case-insensitive search
            video_files.extend(video_dir.glob(f"*.{ext}"))
            video_files.extend(video_dir.glob(f"*.{ext.upper()}"))
        
        # Remove duplicates and sort
        unique_files = list(set(video_files))
        unique_files.sort()
        
        print(f"📁 Found {len(unique_files)} video files in {directory}")
        return unique_files
    
    def get_existing_streams(self) -> List[str]:
        """Get list of existing stream names"""
        try:
            response = self.session.get(f"{self.api_url}/get_active_streams", timeout=10)
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    return [stream['name'] for stream in result.get('streams', [])]
            return []
        except requests.exceptions.RequestException:
            # If we can't get the list, assume no existing streams to be safe
            return []
    
    def generate_stream_name(self, video_file: Path) -> str:
        """Generate a valid stream name from video filename"""
        # Remove extension and clean up the name
        name = video_file.stem
        # Replace invalid characters with underscores
        import re
        clean_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
        # Remove multiple consecutive underscores
        clean_name = re.sub(r'_+', '_', clean_name)
        # Remove leading/trailing underscores
        clean_name = clean_name.strip('_')
        
        # Ensure name is not empty
        if not clean_name:
            clean_name = f"stream_{int(time.time())}"
            
        return clean_name
    
    def get_unique_stream_name(self, base_name: str, existing_streams: Optional[List[str]] = None) -> str:
        """Ensure stream name is unique by appending numbers if needed"""
        if existing_streams is None:
            existing_streams = self.get_existing_streams()
        
        # If base name doesn't exist, use it
        if base_name not in existing_streams:
            return base_name
        
        # Try appending numbers until we find a unique name
        counter = 1
        while True:
            candidate_name = f"{base_name}{counter}"
            if candidate_name not in existing_streams:
                return candidate_name
            counter += 1
            
            # Safety check to prevent infinite loop
            if counter > 1000:
                # Fallback to timestamp-based name
                return f"{base_name}_{int(time.time())}"
    
    def create_stream(self, video_file: Path, stream_config: Dict) -> bool:
        """Create a single stream from a video file"""
        base_name = self.generate_stream_name(video_file)
        stream_name = self.get_unique_stream_name(base_name)
        
        # Show if name was modified for uniqueness
        if stream_name != base_name:
            print(f"⚠️  Stream name '{base_name}' already exists, using '{stream_name}' instead")
        
        # Build the request payload
        payload = {
            "stream_name": stream_name,
            "stream_type": "file",
            "file_source_type": "custom",
            "video_file_path": str(video_file.absolute()),
            **stream_config
        }
        
        try:
            print(f"🚀 Creating stream '{stream_name}' from {video_file.name}...")
            response = self.session.post(
                f"{self.api_url}/start_stream",
                json=payload,
                timeout=30
            )
            
            result = response.json()
            
            if response.status_code == 200 and result.get('success'):
                print(f"✅ Stream '{stream_name}' created successfully")
                print(f"   📺 RTSP URL: {result.get('stream_url', 'N/A')}")
                return True
            else:
                print(f"❌ Failed to create stream '{stream_name}': {result.get('message', 'Unknown error')}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Network error creating stream '{stream_name}': {e}")
            return False
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON response for stream '{stream_name}': {e}")
            return False
    
    def create_stream_with_existing_list(self, video_file: Path, stream_config: Dict, existing_streams: List[str]) -> bool:
        """Create a single stream from a video file, using provided existing streams list"""
        base_name = self.generate_stream_name(video_file)
        stream_name = self.get_unique_stream_name(base_name, existing_streams)
        
        # Show if name was modified for uniqueness
        if stream_name != base_name:
            print(f"⚠️  Stream name '{base_name}' already exists, using '{stream_name}' instead")
        
        # Build the request payload
        payload = {
            "stream_name": stream_name,
            "stream_type": "file",
            "file_source_type": "custom",
            "video_file_path": str(video_file.absolute()),
            **stream_config
        }
        
        try:
            print(f"🚀 Creating stream '{stream_name}' from {video_file.name}...")
            response = self.session.post(
                f"{self.api_url}/start_stream",
                json=payload,
                timeout=30
            )
            
            result = response.json()
            
            if response.status_code == 200 and result.get('success'):
                print(f"✅ Stream '{stream_name}' created successfully")
                print(f"   📺 RTSP URL: {result.get('stream_url', 'N/A')}")
                # Add the new stream name to the existing list to prevent future conflicts
                existing_streams.append(stream_name)
                return True
            else:
                print(f"❌ Failed to create stream '{stream_name}': {result.get('message', 'Unknown error')}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Network error creating stream '{stream_name}': {e}")
            return False
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON response for stream '{stream_name}': {e}")
            return False
    
    def create_streams_from_directory(self, 
                                    directory: str, 
                                    stream_config: Dict,
                                    delay_between_streams: float = 1.0,
                                    dry_run: bool = False) -> Dict[str, int]:
        """Create streams from all videos in a directory"""
        video_files = self.get_video_files(directory)
        
        if not video_files:
            print("❌ No video files found!")
            return {"total": 0, "success": 0, "failed": 0}
        
        # Get existing streams once at the beginning for efficiency
        existing_streams = self.get_existing_streams()
        
        if dry_run:
            print(f"\n🔍 DRY RUN MODE - Would create {len(video_files)} streams:")
            temp_existing = existing_streams.copy()  # Copy to simulate additions
            for video_file in video_files:
                base_name = self.generate_stream_name(video_file)
                unique_name = self.get_unique_stream_name(base_name, temp_existing)
                if unique_name != base_name:
                    print(f"   - {video_file.name} → stream '{unique_name}' ('{base_name}' already exists)")
                else:
                    print(f"   - {video_file.name} → stream '{unique_name}'")
                temp_existing.append(unique_name)  # Add to list to check future conflicts
            return {"total": len(video_files), "success": 0, "failed": 0}
        
        # Test connection before starting
        if not self.test_connection():
            print("❌ Cannot connect to StreamAlchemy API. Is the service running?")
            return {"total": len(video_files), "success": 0, "failed": len(video_files)}
        
        print(f"\n🎬 Creating {len(video_files)} streams...")
        print("=" * 60)
        
        stats = {"total": len(video_files), "success": 0, "failed": 0}
        
        for i, video_file in enumerate(video_files, 1):
            print(f"\n[{i}/{len(video_files)}] Processing: {video_file.name}")
            
            if self.create_stream_with_existing_list(video_file, stream_config, existing_streams):
                stats["success"] += 1
            else:
                stats["failed"] += 1
            
            # Delay between requests to avoid overwhelming the server
            if delay_between_streams > 0 and i < len(video_files):
                time.sleep(delay_between_streams)
        
        return stats

def main():
    parser = argparse.ArgumentParser(
        description="Create multiple streams from video files in a directory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python add_streams.py                                    # Use default directory
  python add_streams.py -d /path/to/videos                # Custom directory
  python add_streams.py -d /path/to/videos --dry-run      # Test without creating
  python add_streams.py --codec h265 --resolution 720    # Custom encoding
  python add_streams.py --duration 2 --fps 15            # Limited duration, lower FPS
        """
    )
    
    # Directory options
    parser.add_argument("-d", "--directory", 
                       default=DEFAULT_VIDEO_DIR,
                       help=f"Directory containing video files (default: {DEFAULT_VIDEO_DIR})")
    
    # API options
    parser.add_argument("--api-url", 
                       default=DEFAULT_API_URL,
                       help=f"StreamAlchemy API URL (default: {DEFAULT_API_URL})")
    
    # Stream configuration
    parser.add_argument("--codec", 
                       choices=["h264", "h265", "mpeg4"],
                       default="h264",
                       help="Video codec (default: h264)")
    
    parser.add_argument("--resolution", 
                       choices=["480", "720", "1080", "1440", "2160"],
                       default="1080",
                       help="Video resolution (default: 1080)")
    
    parser.add_argument("--fps", 
                       type=int,
                       default=30,
                       help="Target FPS (default: 30)")
    
    parser.add_argument("--duration", 
                       type=int,
                       default=0,
                       help="Stream duration in hours, 0 for unlimited (default: 0)")
    
    parser.add_argument("--no-audio", 
                       action="store_true",
                       help="Disable audio")
    
    parser.add_argument("--hardware-accel", 
                       action="store_true",
                       help="Enable hardware acceleration")
    
    # Execution options
    parser.add_argument("--dry-run", 
                       action="store_true",
                       help="Show what would be done without actually creating streams")
    
    parser.add_argument("--delay", 
                       type=float,
                       default=1.0,
                       help="Delay between stream creation requests in seconds (default: 1.0)")
    
    args = parser.parse_args()
    
    # Build stream configuration
    stream_config = {
        "video_codec": args.codec,
        "resolution": args.resolution,
        "target_fps": str(args.fps),
        "audio_enabled": "no" if args.no_audio else "yes",
        "audio_codec": "aac",
        "hardware_accel": "yes" if args.hardware_accel else "no",
        "duration_hours": str(args.duration)
    }
    
    print("🎥 StreamAlchemy Bulk Stream Creator")
    print("=" * 50)
    print(f"📁 Video directory: {args.directory}")
    print(f"🌐 API URL: {args.api_url}")
    print(f"⚙️  Stream config: {json.dumps(stream_config, indent=2)}")
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No streams will be created")
    
    # Create the stream creator and run
    creator = StreamCreator(args.api_url)
    stats = creator.create_streams_from_directory(
        args.directory, 
        stream_config,
        args.delay,
        args.dry_run
    )
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    print(f"Total videos processed: {stats['total']}")
    print(f"✅ Successful streams: {stats['success']}")
    print(f"❌ Failed streams: {stats['failed']}")
    
    if stats['success'] > 0:
        print(f"\n🎉 {stats['success']} streams are now available!")
        print(f"📺 View them at: {args.api_url}")
        
    # Exit with appropriate code
    sys.exit(0 if stats['failed'] == 0 else 1)

if __name__ == "__main__":
    main()
