#!/usr/bin/env python3
# Quick and dirty script to build a NSIS installer for Windows
import sys
import subprocess
import string
import urllib.request
import zipfile
import io
import shutil
import os
import glob

# pynist used to run the build at the end
# kbputils to pull the latest version
subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check', '--target', 'tmp', '--upgrade', 'pynsist', 'kbputils'])
# Apparently required by feedparser required by lastversion, and sdist-only on PyPI
subprocess.check_call([sys.executable, '-m', 'pip', 'wheel', 'sgmllib3k'])

# Pull current version of kbp2video from parent dir
# Note that a fresh copy will be later fetched from PyPI which will ensure
# that the repository version exists there
# To intentionally package a custom version, edit the installer.cfg.template
with open('../kbp2video/__init__.py', 'r') as f:
    while (line := f.readline()):
        if line.startswith('__version__'):
            version = line.split()[2].strip("'\"")

# Pull version of latest kbputils fetched from PyPI
with open(f"tmp/kbputils/__init__.py", 'r') as f:
    while (line := f.readline()):
        if line.startswith('__version__'):
            kbputils_version = line.split()[2].strip("'\"")

# Create installer.cfg from template
with open('installer.cfg', 'w') as f:
    t = string.Template(open('installer.cfg.template', 'r').read())
    f.write(t.substitute(version=version, kbputils_version=kbputils_version))

# Pull down an ffmpeg zip and extract it if not already present
if not os.path.isfile('ffmpeg.zip') and not os.path.isdir('ffmpeg'):
    try:
        urllib.request.urlretrieve('https://github.com/GyanD/codexffmpeg/releases/download/7.1.1/ffmpeg-7.1.1-full_build-shared.zip', filename='ffmpeg.zip')
    except:
        # Remove any partial or zero-byte zip file that may be here
        os.remove('ffmpeg.zip')
        raise sys.exception()

if not os.path.isdir('ffmpeg'):
    try:
        with zipfile.ZipFile('ffmpeg.zip') as z:
            z.extractall()
    except:
        # Remove any bad zip file that may be here
        os.remove('ffmpeg.zip')
        # Remove any partially-extracted dir
        if (result := glob.glob('ffmpeg-*')):
            shutil.rmtree(result[0])
        raise sys.exception()
    shutil.move(glob.glob('ffmpeg-*')[0], 'ffmpeg')
    # Already extracted and renamed, no longer need zip
    os.remove('ffmpeg.zip')

# Run the NSIS build
sys.path.insert(0, 'tmp')
from nsist import main
sys.exit(main(['installer.cfg']))
