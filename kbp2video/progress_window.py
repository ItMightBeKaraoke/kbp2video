from PySide6.QtCore import *  # type: ignore
from PySide6.QtGui import *  # type: ignore
from PySide6.QtWidgets import *  # type: ignore
from .utils import ClickLabel, mimedb, check2bool, bool2check

#class ProgressSignals(QObject):
#    # File has reached current of max steps
#    file_progress = Signal(str, int, int)
#    # Error processing file. Remove it from queue
#    error = Signal(str, bool)
#    # TODO: Autoclose?
#    finished = Signal()

class ProgressWindow(QDialog):

    # Convenience method for adding a Qt object as a property in self and
    # setting its Qt object name
    # TODO: Util class?
    def bind(self, name, obj):
        setattr(self, name, obj)
        obj.setObjectName(name)
        return obj

    def __init__(self, file_count, parent=None):
        super().__init__(parent)
        self.file_count = file_count
        self.fatal_errors = 0
        self.setupUi()

    def setupUi(self):
        self.setObjectName("ProgressWindow")
        self.bind("verticalLayout", QVBoxLayout(self))
        self.verticalLayout.addWidget(self.bind("overall_label", QLabel(self)))
        self.verticalLayout.addWidget(self.bind("overall", QProgressBar(self)))
        self.verticalLayout.addWidget(self.bind("file_label", QLabel(self)))
        self.verticalLayout.addWidget(self.bind("file", QProgressBar(self)))
        self.verticalLayout.addWidget(self.bind("errors_label", QLabel(self)))
        self.verticalLayout.addWidget(self.bind("errors", QTextEdit(self, readOnly=True)))
        self.verticalLayout.addWidget(self.bind("buttonBox", QDialogButtonBox(self,
            standardButtons=QDialogButtonBox.Cancel, 
            orientation=Qt.Horizontal)))

        self.retranslateUi()

        self.buttonBox.rejected.connect(self.reject)
        self.buttonBox.accepted.connect(self.accept)
        # Hide option?

    def retranslateUi(self):
        self.setWindowTitle(QCoreApplication.translate("ProgressWindow", "Conversion Progress", None))
        self.overall_label.setText(QCoreApplication.translate("ProgressWindow", "Overall progress"))
        self.file_label.setText(QCoreApplication.translate("ProgressWindow", "File progress"))
        self.errors_label.setText(QCoreApplication.translate("ProgressWindow", "Errors encountered:"))

    def process_progress(self, cur, rows, file, progress, total):
        # Avoid double-counting ones that were removed during initial processing
        cur = cur - self.fatal_errors + self.file_count - rows
        count = self.file_count - self.fatal_errors
        self.file_label.setText(f"Processing file {cur + 1} of {count}: {file}")
        self.file.setMaximum(total)
        self.file.setValue(progress)
        if count == 0:
            self.overall.setMaximum(100)
            self.overall.setValue(100)
        elif total != 0:
            self.overall.setMaximum(count * 100)
            self.overall.setValue(cur * 100 + int(progress * 100 / total))

    def process_error(self, message, fatal):
        if fatal:
            self.fatal_errors += 1
        self.errors.append(message)
    
    def process_finished(self):
        self.buttonBox.setStandardButtons(QDialogButtonBox.Ok)
        if self.fatal_errors:
            self.file_label.setText("Complete with errors! Please review below.")
        else:
            timer = QTimer(self, singleShot=True)
            timer.timeout.connect(self.accept)
            self.file_label.setText("Complete! Closing window in 5 seconds")
            timer.start(5000)
        
    def showProgressWindow(file_count, sig_object, parent=None):
        p = ProgressWindow(file_count, parent)
        sig_object.progress.connect(p.process_progress)
        sig_object.error.connect(p.process_error)
        sig_object.finished.connect(p.process_finished)
        return p.exec()
