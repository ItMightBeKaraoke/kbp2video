#!python3
import sys, os
import site

scriptdir, script = os.path.split(os.path.abspath(__file__))
pkgdir = os.path.join(scriptdir, 'pkgs')
# Ensure .pth files in pkgdir are handled properly
site.addsitedir(pkgdir)
sys.path.insert(0, pkgdir)

import kbp2video
kbp2video.run(ffmpeg_path=os.path.join(os.path.dirname(sys.executable), "..", "ffmpeg", "bin"))