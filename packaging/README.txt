build_windows_installer.py is a script to create an NSIS-based installer for Windows. The only requirements should be that NSIS and Python 3 are installed and in your path. This should take care of pulling any python-based depencencies as well as an ffmpeg build. It has not been tested much yet.

Usage:

    $ python3 build_windows_installer.py

Result: Installer kbp2video_setup_VERSION.exe created in build/nsis
