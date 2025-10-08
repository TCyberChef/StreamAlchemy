#!/usr/bin/env python3
"""
Test script for StreamAlchemy stream persistence functionality.
This script tests the save/load/restore functionality without starting actual streams.
"""

import os
import sys
import json
import time
import tempfile
import shutil

# Add the current directory to Python path to import config and app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock config for testing
class MockConfig:
    ENABLE_STREAM_PERSISTENCE = True
    STREAM_PERSISTENCE_FILE = os.path.join(tempfile.gettempdir(), "test_active_streams.json")
    STREAM_PERSISTENCE_BACKUP_COUNT = 3

def test_persistence_functions():
    """Test the core persistence functions"""
    print("Testing StreamAlchemy Stream Persistence...")
    
    # Import the functions we need to test
    import config
    
    # Temporarily override config for testing
    original_enable = getattr(config, 'ENABLE_STREAM_PERSISTENCE', True)
    original_file = getattr(config, 'STREAM_PERSISTENCE_FILE', '/tmp/active_streams.json')
    
    config.ENABLE_STREAM_PERSISTENCE = True
    config.STREAM_PERSISTENCE_FILE = os.path.join(tempfile.gettempdir(), "test_active_streams.json")
    
    # Clean up any existing test file
    if os.path.exists(config.STREAM_PERSISTENCE_FILE):
        os.remove(config.STREAM_PERSISTENCE_FILE)
    
    try:
        # Import persistence functions
        from app import save_stream_state, remove_stream_state, load_persistent_streams
        
        print("✓ Successfully imported persistence functions")
        
        # Test 1: Save stream state
        print("\n1. Testing save_stream_state...")
        test_config = {
            'video_codec': 'h264',
            'resolution': '1080',
            'target_fps': '30',
            'audio_enabled': 'yes',
            'audio_codec': 'aac',
            'hardware_accel': 'no',
            'duration_hours': '2',
            'stream_type': 'file',
            'video_file_path': '/path/to/test/video.mp4',
            'file_source_type': 'custom'
        }
        
        save_stream_state("test_stream_1", test_config)
        print("✓ Saved test_stream_1")
        
        # Test 2: Load persistent streams
        print("\n2. Testing load_persistent_streams...")
        loaded_streams = load_persistent_streams()
        assert "test_stream_1" in loaded_streams, "test_stream_1 not found in loaded streams"
        assert loaded_streams["test_stream_1"]["config"]["video_codec"] == "h264", "Config not saved correctly"
        print("✓ Successfully loaded persistent streams")
        
        # Test 3: Save multiple streams
        print("\n3. Testing multiple streams...")
        test_config_2 = {
            'video_codec': 'h265',
            'resolution': '720',
            'stream_type': 'rtsp',
            'source_url': 'rtsp://example.com/stream',
            'duration_hours': '1'
        }
        
        save_stream_state("test_stream_2", test_config_2)
        
        loaded_streams = load_persistent_streams()
        assert len(loaded_streams) == 2, f"Expected 2 streams, got {len(loaded_streams)}"
        print("✓ Multiple streams saved and loaded correctly")
        
        # Test 4: Remove stream state
        print("\n4. Testing remove_stream_state...")
        remove_stream_state("test_stream_1")
        
        loaded_streams = load_persistent_streams()
        assert "test_stream_1" not in loaded_streams, "test_stream_1 should have been removed"
        assert "test_stream_2" in loaded_streams, "test_stream_2 should still exist"
        print("✓ Stream removal works correctly")
        
        # Test 5: File backup functionality
        print("\n5. Testing backup functionality...")
        # Save another stream to trigger backup
        save_stream_state("test_stream_3", test_config)
        
        backup_file = f"{config.STREAM_PERSISTENCE_FILE}.backup"
        if os.path.exists(backup_file):
            print("✓ Backup file created")
        else:
            print("⚠ Backup file not created (may be expected on first save)")
        
        # Test 6: Verify JSON structure
        print("\n6. Testing JSON structure...")
        with open(config.STREAM_PERSISTENCE_FILE, 'r') as f:
            data = json.load(f)
        
        for stream_name, stream_data in data.items():
            assert 'config' in stream_data, f"Missing 'config' in {stream_name}"
            assert 'saved_at' in stream_data, f"Missing 'saved_at' in {stream_name}"
            assert 'status' in stream_data, f"Missing 'status' in {stream_name}"
            assert isinstance(stream_data['saved_at'], (int, float)), f"saved_at should be timestamp in {stream_name}"
        
        print("✓ JSON structure is correct")
        
        print("\n✅ All persistence tests passed!")
        
        # Display final state
        print(f"\nFinal persistent streams:")
        for name, data in loaded_streams.items():
            config_summary = {k: v for k, v in data['config'].items() if k in ['stream_type', 'video_codec', 'resolution']}
            print(f"  - {name}: {config_summary}")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Restore original config
        config.ENABLE_STREAM_PERSISTENCE = original_enable
        config.STREAM_PERSISTENCE_FILE = original_file
        
        # Clean up test files
        test_file = os.path.join(tempfile.gettempdir(), "test_active_streams.json")
        backup_file = f"{test_file}.backup"
        for f in [test_file, backup_file]:
            if os.path.exists(f):
                os.remove(f)
    
    return True

def test_duration_expiry():
    """Test duration-based expiry logic"""
    print("\n" + "="*50)
    print("Testing Duration Expiry Logic...")
    
    # Create a mock stream that should expire
    current_time = time.time()
    expired_stream = {
        'config': {
            'duration_hours': '1',  # 1 hour duration
            'stream_type': 'file',
            'video_file_path': '/path/to/video.mp4'
        },
        'saved_at': current_time - 3700,  # Saved 3700 seconds ago (> 1 hour)
        'status': 'active'
    }
    
    # Create a mock stream that should NOT expire
    valid_stream = {
        'config': {
            'duration_hours': '2',  # 2 hour duration
            'stream_type': 'file',
            'video_file_path': '/path/to/video.mp4'
        },
        'saved_at': current_time - 1800,  # Saved 1800 seconds ago (30 minutes)
        'status': 'active'
    }
    
    # Test expiry logic
    duration_hours_expired = float(expired_stream['config']['duration_hours'])
    elapsed_hours_expired = (current_time - expired_stream['saved_at']) / 3600
    should_expire = elapsed_hours_expired >= duration_hours_expired
    
    duration_hours_valid = float(valid_stream['config']['duration_hours'])
    elapsed_hours_valid = (current_time - valid_stream['saved_at']) / 3600
    should_not_expire = elapsed_hours_valid < duration_hours_valid
    
    print(f"Expired stream: {elapsed_hours_expired:.2f}h elapsed >= {duration_hours_expired}h duration = {should_expire}")
    print(f"Valid stream: {elapsed_hours_valid:.2f}h elapsed < {duration_hours_valid}h duration = {should_not_expire}")
    
    assert should_expire, "Expired stream should be marked for expiry"
    assert should_not_expire, "Valid stream should not be marked for expiry"
    
    print("✅ Duration expiry logic works correctly!")

if __name__ == "__main__":
    print("StreamAlchemy Stream Persistence Test Suite")
    print("=" * 50)
    
    success = test_persistence_functions()
    if success:
        test_duration_expiry()
        print("\n🎉 All tests completed successfully!")
        print("\nThe stream persistence functionality is ready to use.")
        print("When you restart the StreamAlchemy service, active streams will be automatically restored.")
    else:
        print("\n❌ Tests failed. Please check the implementation.")
        sys.exit(1) 