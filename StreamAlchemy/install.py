#!/usr/bin/env python3
"""
Cross-platform installation script for StreamAlchemy
Supports Windows, macOS, and Linux
"""

import os
import sys
import platform
import subprocess
import shutil
from pathlib import Path

def get_script_dir():
    """Get the directory where this script is located"""
    return Path(__file__).parent.absolute()

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        print(f"Error: Python 3.8+ required, found {sys.version}")
        return False
    print(f"✓ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    return True

def check_ffmpeg():
    """Check if FFmpeg is installed"""
    if shutil.which('ffmpeg'):
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
            if result.returncode == 0:
                version_line = result.stdout.split('\n')[0]
                print(f"✓ FFmpeg: {version_line}")
                return True
        except:
            pass
    
    print("✗ FFmpeg not found")
    print_ffmpeg_install_instructions()
    return False

def check_yt_dlp():
    """Check if yt-dlp is installed"""
    if shutil.which('yt-dlp'):
        try:
            result = subprocess.run(['yt-dlp', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✓ yt-dlp: {result.stdout.strip()}")
                return True
        except:
            pass
    
    print("✗ yt-dlp not found (optional but recommended)")
    print_yt_dlp_install_instructions()
    return False

def print_ffmpeg_install_instructions():
    """Print FFmpeg installation instructions for current OS"""
    system = platform.system().lower()
    
    print("\nFFmpeg Installation Instructions:")
    print("-" * 35)
    
    if system == 'windows':
        print("Windows:")
        print("1. Download from https://ffmpeg.org/download.html")
        print("2. Extract and add to PATH")
        print("3. Or use chocolatey: choco install ffmpeg")
        print("4. Or use winget: winget install ffmpeg")
    elif system == 'darwin':
        print("macOS:")
        print("1. Install Homebrew: /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"")
        print("2. Install FFmpeg: brew install ffmpeg")
    else:  # Linux
        print("Linux:")
        print("Ubuntu/Debian: sudo apt update && sudo apt install ffmpeg")
        print("CentOS/RHEL: sudo yum install ffmpeg")
        print("Fedora: sudo dnf install ffmpeg")
        print("Arch: sudo pacman -S ffmpeg")

def print_yt_dlp_install_instructions():
    """Print yt-dlp installation instructions"""
    system = platform.system().lower()
    
    print("\nyt-dlp Installation Instructions:")
    print("-" * 32)
    
    if system == 'windows':
        print("Windows:")
        print("1. pip install yt-dlp")
        print("2. Or download from https://github.com/yt-dlp/yt-dlp/releases")
    elif system == 'darwin':
        print("macOS:")
        print("1. brew install yt-dlp")
        print("2. Or pip install yt-dlp")
    else:  # Linux
        print("Linux:")
        print("1. pip install yt-dlp")
        print("2. Or use package manager (if available)")

def install_python_dependencies():
    """Install Python dependencies"""
    script_dir = get_script_dir()
    requirements_file = script_dir / 'python_interface' / 'requirements.txt'
    
    if not requirements_file.exists():
        print("✗ requirements.txt not found")
        return False
    
    print("\nInstalling Python dependencies...")
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', str(requirements_file)], check=True)
        print("✓ Python dependencies installed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install Python dependencies: {e}")
        return False

def create_directories():
    """Create necessary directories"""
    script_dir = get_script_dir()
    python_interface_dir = script_dir / 'python_interface'
    
    directories = [
        python_interface_dir / 'browseable_videos',
        python_interface_dir / 'data',
        python_interface_dir / 'test_videos'
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"✓ Created directory: {directory}")

def make_scripts_executable():
    """Make shell scripts executable on Unix-like systems"""
    if platform.system().lower() != 'windows':
        script_dir = get_script_dir()
        python_interface_dir = script_dir / 'python_interface'
        
        scripts = [
            python_interface_dir / 'run.sh',
            python_interface_dir / 'run.py'
        ]
        
        for script in scripts:
            if script.exists():
                os.chmod(script, 0o755)
                print(f"✓ Made executable: {script}")

def main():
    """Main installation function"""
    print("StreamAlchemy Cross-Platform Installation")
    print("=" * 40)
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Architecture: {platform.machine()}")
    print()
    
    # Check requirements
    all_good = True
    
    if not check_python_version():
        all_good = False
    
    if not check_ffmpeg():
        all_good = False
    
    check_yt_dlp()  # Optional, don't fail if missing
    
    if not all_good:
        print("\n❌ Installation failed due to missing requirements")
        print("Please install the missing dependencies and run this script again.")
        return 1
    
    # Install Python dependencies
    if not install_python_dependencies():
        return 1
    
    # Create directories
    print("\nCreating directories...")
    create_directories()
    
    # Make scripts executable
    print("\nSetting up scripts...")
    make_scripts_executable()
    
    print("\n✅ Installation completed successfully!")
    print("\nTo run StreamAlchemy:")
    print("- Windows: Double-click run.bat or run: python python_interface/run.py")
    print("- macOS/Linux: ./python_interface/run.sh or run: python python_interface/run.py")
    print("\nThen open your browser to: http://localhost:5000")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
