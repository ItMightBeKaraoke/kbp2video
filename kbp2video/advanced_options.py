from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import QDialogButtonBox, QVBoxLayout, QTextEdit, QLineEdit, QTabWidget, QDialog, QGridLayout
from .utils import ClickLabel, mimedb, check2bool, bool2check

class AdvancedOptions(QDialog):

    # Convenience method for adding a Qt object as a property in self and
    # setting its Qt object name
    # TODO: Util class?
    def bind(self, name, obj):
        setattr(self, name, obj)
        obj.setObjectName(name)
        return obj

    def __init__(self, options):
        super().__init__()
        self.options = options
        self.setupUi()

    def saveSettings(self):
        for x in self.options:
            if x == 'comments':
                self.options[x] = type(self.options[x])(getattr(self, f"{x}_input").toPlainText())
            else:
                self.options[x] = type(self.options[x])(getattr(self, f"{x}_input").text())

    def setupUi(self):
        self.setObjectName("AdvancedOptions")
        self.bind("verticalLayout", QVBoxLayout(self))
        #self.verticalLayout.addWidget(self.bind("tabs", QTabWidget(self)))
        self.verticalLayout.addLayout(self.bind("gridLayout", QGridLayout()))
        self.verticalLayout.addWidget(self.bind("buttonBox", QDialogButtonBox(self,
            standardButtons=QDialogButtonBox.Cancel|QDialogButtonBox.Ok,
            orientation=Qt.Horizontal)))

        gridRow=0
        for x in self.options:
            if x == 'comments':
                self.gridLayout.addWidget(self.bind(f"{x}_input", QTextEdit(text=str(self.options[x]), acceptRichText=False, lineWrapMode=QTextEdit.NoWrap)), gridRow, 1)
                self.gridLayout.addWidget(self.bind(f"{x}_label", ClickLabel(buddy=getattr(self, f"{x}_input"))), gridRow, 0)
            else:
                self.gridLayout.addWidget(self.bind(f"{x}_input", QLineEdit(text=str(self.options[x]))), gridRow, 1)
                self.gridLayout.addWidget(self.bind(f"{x}_label", ClickLabel(buddy=getattr(self, f"{x}_input"))), gridRow, 0)
                if type(self.options[x]) is int:
                    getattr(self, f"{x}_input").setValidator(QIntValidator())
            gridRow += 1

        self.max_lines_per_page_input.setValidator(QIntValidator(bottom=0, top=20))


        self.retranslateUi()

        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)


    def accept(self):
        self.saveSettings()
        super().accept()


    def retranslateUi(self):
        self.setWindowTitle(QCoreApplication.translate("AdvancedOptions", "Lyrics Import Options", None))
        for x in self.options:
            getattr(self, f"{x}_label").setText(x)
        
    def showAdvancedOptions(options):
        return AdvancedOptions(options).exec()
