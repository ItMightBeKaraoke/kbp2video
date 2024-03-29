from PySide6.QtWidgets import *

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
