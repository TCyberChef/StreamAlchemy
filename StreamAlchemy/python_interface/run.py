#!/usr/bin/env python3
"""
Cross-platform launcher for StreamAlchemy
Supports Windows, macOS, and Linux
"""

import os
import sys
import subprocess
import platform
import shutil
import signal
import time
from pathlib import Path

def get_script_dir():
    """Get the directory where this script is located"""
    return Path(__file__).parent.absolute()

def check_dependencies():
    """Check if required dependencies are available"""
    missing_deps = []
    
    # Check Python version
    if sys.version_info < (3, 8):
        missing_deps.append(f"Python 3.8+ (found {sys.version})")
    
    # Check FFmpeg
    if not shutil.which('ffmpeg'):
        missing_deps.append("FFmpeg (not found in PATH)")
    
    # Check yt-dlp (optional but recommended)
    if not shutil.which('yt-dlp'):
        print("Warning: yt-dlp not found. YouTube support will be limited.")
    
    return missing_deps

def kill_port_processes(port):
    """Kill processes using the specified port"""
    system = platform.system().lower()
    
    try:
        if system == 'windows':
            # Windows: use netstat and taskkill
            result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if f':{port}' in line and 'LISTENING' in line:
                    parts = line.split()
                    if len(parts) > 4:
                        pid = parts[-1]
                        subprocess.run(['taskkill', '/F', '/PID', pid], capture_output=True)
        else:
            # Unix-like systems: use lsof and kill
            result = subprocess.run(['lsof', '-ti', f':{port}'], capture_output=True, text=True)
            if result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    if pid:
                        subprocess.run(['kill', '-9', pid], capture_output=True)
    except Exception as e:
        print(f"Warning: Could not free port {port}: {e}")

def setup_virtual_environment():
    """Set up Python virtual environment"""
    script_dir = get_script_dir()
    venv_dir = script_dir / 'venv'
    
    if not venv_dir.exists():
        print("Creating virtual environment...")
        result = subprocess.run([sys.executable, '-m', 'venv', str(venv_dir)])
        if result.returncode != 0:
            print("Failed to create virtual environment")
            return False
    else:
        print("Virtual environment already exists")
    
    return True

def install_dependencies():
    """Install Python dependencies"""
    script_dir = get_script_dir()
    venv_dir = script_dir / 'venv'
    
    # Determine pip executable path based on OS
    if platform.system().lower() == 'windows':
        pip_exe = venv_dir / 'Scripts' / 'pip.exe'
        python_exe = venv_dir / 'Scripts' / 'python.exe'
    else:
        pip_exe = venv_dir / 'bin' / 'pip'
        python_exe = venv_dir / 'bin' / 'python'
    
    if not pip_exe.exists():
        print("Virtual environment not properly set up")
        return False
    
    print("Installing dependencies...")
    requirements_file = script_dir / 'requirements.txt'
    
    if requirements_file.exists():
        result = subprocess.run([str(pip_exe), 'install', '-r', str(requirements_file)])
        if result.returncode != 0:
            print("Failed to install dependencies")
            return False
    else:
        print("requirements.txt not found")
        return False
    
    return True

def run_application():
    """Run the StreamAlchemy application"""
    script_dir = get_script_dir()
    venv_dir = script_dir / 'venv'
    
    # Determine python executable path based on OS
    if platform.system().lower() == 'windows':
        python_exe = venv_dir / 'Scripts' / 'python.exe'
    else:
        python_exe = venv_dir / 'bin' / 'python'
    
    if not python_exe.exists():
        print("Python executable not found in virtual environment")
        return False
    
    print("Starting StreamAlchemy...")
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version}")
    print(f"Working directory: {script_dir}")
    
    # Change to script directory
    os.chdir(script_dir)
    
    # Run the application
    try:
        subprocess.run([str(python_exe), 'app.py'])
    except KeyboardInterrupt:
        print("\nShutting down StreamAlchemy...")
    except Exception as e:
        print(f"Error running application: {e}")
        return False
    
    return True

def main():
    """Main entry point"""
    print("StreamAlchemy Cross-Platform Launcher")
    print("=" * 40)
    
    # Check dependencies
    missing_deps = check_dependencies()
    if missing_deps:
        print("Missing dependencies:")
        for dep in missing_deps:
            print(f"  - {dep}")
        print("\nPlease install missing dependencies and try again.")
        return 1
    
    # Free up port 5000
    print("Freeing up port 5000...")
    kill_port_processes(5000)
    time.sleep(1)
    
    # Set up virtual environment
    if not setup_virtual_environment():
        return 1
    
    # Install dependencies
    if not install_dependencies():
        return 1
    
    # Run application
    if not run_application():
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
