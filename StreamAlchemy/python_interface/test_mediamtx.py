#!/usr/bin/env python3
"""
Test script to verify MediaMTX integration
"""
import os
import subprocess
import time
import sys

def check_mediamtx_binary():
    """Check if MediaMTX binary exists and is executable"""
    mediamtx_path = os.path.join('mediamtx', 'mediamtx')
    
    if not os.path.exists(mediamtx_path):
        print(f"❌ MediaMTX binary not found at {mediamtx_path}")
        return False
    
    if not os.access(mediamtx_path, os.X_OK):
        print(f"❌ MediaMTX binary is not executable")
        return False
    
    print(f"✅ MediaMTX binary found and is executable")
    return True

def check_mediamtx_config():
    """Check if MediaMTX config exists"""
    config_path = os.path.join('mediamtx', 'mediamtx.yml')
    
    if not os.path.exists(config_path):
        print(f"❌ MediaMTX config not found at {config_path}")
        return False
    
    print(f"✅ MediaMTX config found")
    return True

def check_port_availability():
    """Check if RTSP port is available"""
    result = subprocess.run(['lsof', '-i', ':8554'], capture_output=True, text=True)
    
    if result.returncode == 0:
        print("❌ Port 8554 is already in use")
        print(result.stdout)
        return False
    
    print("✅ Port 8554 is available")
    return True

def test_mediamtx_startup():
    """Test starting MediaMTX"""
    print("\nTesting MediaMTX startup...")
    
    mediamtx_path = os.path.join('mediamtx', 'mediamtx')
    config_path = os.path.join('mediamtx', 'mediamtx.yml')
    
    try:
        # Start MediaMTX
        process = subprocess.Popen(
            [mediamtx_path, config_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        print("Waiting for MediaMTX to start...")
        time.sleep(3)
        
        # Check if process is still running
        if process.poll() is None:
            print("✅ MediaMTX started successfully")
            print(f"   PID: {process.pid}")
            
            # Stop the process
            process.terminate()
            process.wait(timeout=5)
            print("✅ MediaMTX stopped successfully")
            return True
        else:
            print(f"❌ MediaMTX failed to start, exit code: {process.poll()}")
            stdout, stderr = process.communicate()
            if stdout:
                print("STDOUT:", stdout.decode())
            if stderr:
                print("STDERR:", stderr.decode())
            return False
            
    except Exception as e:
        print(f"❌ Error testing MediaMTX: {e}")
        return False

def main():
    """Run all tests"""
    print("StreamAlchemy MediaMTX Integration Test")
    print("=" * 40)
    
    tests = [
        ("Binary Check", check_mediamtx_binary),
        ("Config Check", check_mediamtx_config),
        ("Port Check", check_port_availability),
        ("Startup Test", test_mediamtx_startup)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        results.append(test_func())
    
    print("\n" + "=" * 40)
    print("Summary:")
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("✅ All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 