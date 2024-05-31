kbp2video
=========

kbp2video is a GUI for converting .kbp files from Karaoke Builder Studio into video files by converting to Advanced SubStation Alpha subtitles (.ass) as an intermediate format.

This project is still in beta, though several people are already using it daily to generate their karaoke videos. If you want to try it, I recommend joining the [diveBar Discord](https://discord.gg/diveBar) if you are not there already.

How to run kbp2video
--------------------

### Windows installer

If you are on Windows, you can use the installer exe provided with a [release](https://github.com/ItMightBeKaraoke/kbp2video/releases). This installs kbp2video, its Python dependencies, including a bundled Python itself, and ffmpeg. Thus it should be everything you need to get up and running. It will create two shortcuts in your start menu, one for running normally, and one for running in debug mode with a command prompt window to provide additional debug info and any uncaught errors.

### Manual install

If you are not on Windows, or otherwise want to install manually, it requires two main dependencies, Python 3 and ffmpeg. Almost any Linux distro will have both of these available in their package manager. On Windows, you can download Python from its [official site](https://www.python.org/), and it's also available in the Microsoft store and several package managers for Windows as well. For Windows builds of ffmpeg, I recommend the ones from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/). kbp2video uses both the ffmpeg and ffprobe binaries. You will need to add the ffmpeg bin directory to your PATH or kbp2video will prompt for it each time it opens. For Python, I'd recommend at least version 3.10 and for ffmpeg, at least 6.x.

Once you have Python and ffmpeg, you can install kbp2video with pip:

    python3 -m pip install kbp2video

Then you can run it with

    python3 -m kbp2video

If you are using a venv or otherwise have the pip's bin or scripts directory in your path, you can also just run

    kbp2video

### Install from Git

If you want to install directly from the repo, you can do so either using a normal Git clone or downloading a release zip/tar, then from within the directory run (optionally from within a venv):

    python3 -m pip install .

The repo has a pyproject.toml which will take care of handling Python dependencies automatically. You still need to install Python itself and ffmpeg for this to work.

### Building an installer for Windows

See the README.txt in the packaging directory. I use it myself to generate the Windows installers from my Linux system, but it doesn't get testing outside of that, so feel free to report any issues encountered.
