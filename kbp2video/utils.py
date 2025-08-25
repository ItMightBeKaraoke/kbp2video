import sys
import io

from PySide6.QtWidgets import QCheckBox, QLabel
from PySide6.QtCore import QMimeDatabase, Qt

import kbputils

mimedb = QMimeDatabase()

# Minor enhancement to QLabel - if it has a buddy configured, that will not
# only allow a keyboard mnemonic to be associated, but will also focus the buddy
# widget when the label is clicked (like the "for" attribute in html). To enable
# an action other than focus, like clicking a checkbox, set buddyMethod to the
# method to call on the buddy widget (in that example QCheckBox.toggle
class ClickLabel(QLabel):

    def __init__(self, buddyMethod=None, **kwargs):
        super().__init__(**kwargs)
        self.buddyMethod=buddyMethod

    def mousePressEvent(self, event):
        if (b := self.buddy()) and b.isEnabled():
            if self.buddyMethod:
                self.buddyMethod(b)
            else:
                b.setFocus(Qt.MouseFocusReason)

def check2bool(state_or_checkbox):
    if 'checkState' in dir(state_or_checkbox):
        state_or_checkbox = state_or_checkbox.checkState()
    return state_or_checkbox != Qt.Unchecked

def bool2check(boolVal):
    return Qt.Checked if boolVal else Qt.Unchecked

# This is kind of ugly, but so are the terminal windows that pop up in Windows
if sys.platform == "win32":
    print("Wrapping popen for Windows...")
    import subprocess
    
    _orig_popen_init = subprocess.Popen.__init__

    # Patch the __init__  for Popen to avoid creating windows in very specific cases
    def _wrapped_popen_init(self, *args, **kwargs):
        print(f"Popen launched with {args}, {kwargs}")
        if 'creationflags' not in kwargs and ("ffmpeg" in args[0] or "ffprobe" in args[0]):
            print("creationflags added to popen call")
            kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
        return _orig_popen_init(self, *args, **kwargs)

    subprocess.Popen.__init__ = _wrapped_popen_init

    print("done")

# TODO: Possibly pull PlayRes? from .ass to letterbox
class KBPASSWrapper:
    def __init__(self, path):
        if path.casefold().endswith(".ass"):
            self.ass_path = path
            # raise correct exception we would get later from opening
            with open(path, "r") as _:
                pass
        else:
            self.kbp_path = path
            self.kbp_obj = kbputils.KBPFile(path)
    def ass_data(self, **kwargs):
        if hasattr(self,"kbp_path"):
            # Re-read file in case it changed on disk
            self.kbp_obj = kbputils.KBPFile(self.kbp_path)

            tmp = io.StringIO()
            kbputils.AssConverter(self.kbp_obj,**kwargs).ass_document().dump_file(tmp)
            return tmp.getvalue()
        else:
            # Added for symmetry or something, but...
            print("Probably shouldn't reach this code")
            f = QFile(self.ass_path)
            if not f.open(QIODevice.ReadOnly | QIODevice.Text):                                                                                  
                raise IOError(f"Unable to open {self.ass_path}")
            res = QTextStream(f).readAll()
            f.close()
            return res

    def __str__(self):
        return self.kbp_path if hasattr(self,"kbp_path") else self.ass_path
