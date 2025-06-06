from PySide6.QtWidgets import QCheckBox, QLabel
from PySide6.QtCore import QMimeDatabase, Qt
import sys

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

mimedb = QMimeDatabase()

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
