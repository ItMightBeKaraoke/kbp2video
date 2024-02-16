from PySide6.QtCore import *  # type: ignore
from PySide6.QtGui import *  # type: ignore
from PySide6.QtWidgets import *  # type: ignore
from .utils import ClickLabel
import json

class AdvancedEditor(QDialog):

    # Convenience method for adding a Qt object as a property in self and
    # setting its Qt object name
    # TODO: Util class?
    def bind(self, name, obj):
        setattr(self, name, obj)
        obj.setObjectName(name)
        return obj

    SETTING_NAMES = ("enable", "file", "length", "overlap", "fadeIn", "fadeOut", "sound")

    def __init__(self, tableWidget):
        super().__init__()
        rows = set(x.row() for x in tableWidget.selectedIndexes())
        self.outputs = [tableWidget.item(x, 3) for x in rows]
        self.loadSettings()
        self.setupUi()
    
    def loadSettings(self):
        self.settings = {}
        data = []
        for x in self.outputs:
            try:
                data.append(json.loads(x.text()))
            except json.JSONDecodeError:
                # Just skip those rows
                pass
        # 0 is for testing only
        if len(data) == 1:
            self.settings = data[0]
        elif len(data) > 1:
            for x in ("intro", "outro"):
                for setting in AdvancedEditor.SETTING_NAMES:
                    key = f"{x}_{setting}"
                    # TODO: none of the rows have a value - only possible if we can distinguish unset from empty
                    if all(key in data[0] and key in x and data[0][key] == x[key] for x in data):
                        self.settings[key] = data[0][key]
                    else:
                        self.settings[key] = None

    def saveSettings(self):
        result = {}
        for x in ("intro", "outro"):
            for setting in AdvancedEditor.SETTING_NAMES:
                widget = getattr(self, f"{x}_{setting}")
                if type(widget) == QCheckBox:
                    # Indeterminate to None?
                    val = True if widget.checkState() == Qt.Checked else False
                elif type(widget) == QLineEdit:
                    val = widget.text()
                elif type(widget) == QTimeEdit:
                    val = widget.time().toString("mm:ss.zzz")
                else:
                    print(f"Oops, missed type {type(widget).__name__} for {x}_{setting}")
                    val = None
                result[f"{x}_{setting}"] = val
        for x in self.outputs:
            print("Updating a row")
            x.setText(json.dumps(result))



    def setupUi(self):
        self.setObjectName("AdvancedEditor")
        self.bind("verticalLayout", QVBoxLayout(self))
        self.verticalLayout.addWidget(self.bind("tabs", QTabWidget(self)))
        self.verticalLayout.addWidget(self.bind("buttonBox", QDialogButtonBox(self,
            standardButtons=QDialogButtonBox.Cancel|QDialogButtonBox.Ok,
            orientation=Qt.Horizontal)))

        for x in ("intro", "outro"):
            self.bind(f"{x}Tab", QWidget())
            self.tabs.addTab(getattr(self,f"{x}Tab"), "")
            grid = self.bind(f"{x}Grid", QGridLayout(getattr(self,f"{x}Tab")))

            row = 0
            grid.addWidget(self.bind(f"{x}_enable", QCheckBox(stateChanged=self.checkbox_enabled_handler)), row, 0, alignment=Qt.AlignRight)
            grid.addWidget(self.bind(f"{x}_enable_label", ClickLabel(buddy=getattr(self,f"{x}_enable"), buddyMethod=QCheckBox.toggle)), row, 1, 1, 2)
            if (key := f"{x}_enable") in self.settings:
                if self.settings[key] == None:
                    getattr(self, key).setTristate(True)
                    getattr(self, key).setCheckState(Qt.PartiallyChecked)
                else:
                    getattr(self, key).setCheckState(Qt.Checked if self.settings[key] else Qt.Unchecked)

            row += 1
            grid.addWidget(self.bind(f"{x}_file", QLineEdit()), row, 1)
            grid.addWidget(self.bind(f"{x}_file_label", ClickLabel(buddy=getattr(self, f"{x}_file"))), row, 0)
            grid.addWidget(self.bind(f"{x}_file_button", QPushButton()), row, 2)

            if (key := f"{x}_file") in self.settings:
                if self.settings[key] == None:
                    getattr(self, key).setText("<Multiple Values>")
                else:
                    getattr(self, key).setText(self.settings[key])

            row += 1
            grid.addWidget(self.bind(f"{x}_length", QTimeEdit(displayFormat="mm:ss.zzz")), row, 1, 1, 2)
            grid.addWidget(self.bind(f"{x}_length_label", ClickLabel(buddy=getattr(self, f"{x}_length"))), row, 0)

            if (key := f"{x}_length") in self.settings:
                if self.settings[key] == None:
                    # getattr(self, key).setValue("<Multiple Values>") # TODO: how to handle indeterminate value? Gray but click enables edit?
                    pass
                else:
                    getattr(self, key).setTime(QTime.fromString(self.settings[key],"mm:ss.zzz"))

            row += 1
            grid.addWidget(self.bind(f"{x}_overlap", QTimeEdit(displayFormat="mm:ss.zzz")), row, 1, 1, 2)
            grid.addWidget(self.bind(f"{x}_overlap_label", ClickLabel(buddy=getattr(self, f"{x}_overlap"))), row, 0)

            if (key := f"{x}_overlap") in self.settings:
                if self.settings[key] == None:
                    # getattr(self, key).setValue("<Multiple Values>") # TODO: how to handle indeterminate value? Gray but click enables edit?
                    pass
                else:
                    getattr(self, key).setTime(QTime.fromString(self.settings[key],"mm:ss.zzz"))

            row += 1
            grid.addWidget(self.bind(f"{x}_fadeIn",
                QTimeEdit(
                    displayFormat="ss.zzz",
                    sizePolicy=QSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum))
                ), row, 1)
            grid.addWidget(self.bind(f"{x}_fade_label", ClickLabel(buddy=getattr(self, f"{x}_fadeIn"))), row, 0)
            grid.addWidget(self.bind(f"{x}_fadeOut",
                QTimeEdit(
                    displayFormat="ss.zzz",
                    sizePolicy=QSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum))
                ), row, 2)
            if (key := f"{x}_fadeIn") in self.settings:
                if self.settings[key] == None:
                    # getattr(self, key).setValue("<Multiple Values>") # TODO: how to handle indeterminate value? Gray but click enables edit?
                    pass
                else:
                    getattr(self, key).setTime(QTime.fromString(self.settings[key],"mm:ss.zzz"))
            if (key := f"{x}_fadeOut") in self.settings:
                if self.settings[key] == None:
                    # getattr(self, key).setValue("<Multiple Values>") # TODO: how to handle indeterminate value? Gray but click enables edit?
                    pass
                else:
                    getattr(self, key).setTime(QTime.fromString(self.settings[key],"mm:ss.zzz"))

            row += 1
            grid.addWidget(self.bind(f"{x}_sound", QCheckBox()), row, 0, alignment=Qt.AlignRight)
            grid.addWidget(self.bind(f"{x}_sound_label", ClickLabel(buddy=getattr(self,f"{x}_sound"), buddyMethod=QCheckBox.toggle)), row, 1, 1, 2)
            if (key := f"{x}_sound") in self.settings:
                if self.settings[key] == None:
                    getattr(self, key).setTristate(True)
                    getattr(self, key).setCheckState(Qt.PartiallyChecked)
                else:
                    getattr(self, key).setCheckState(Qt.Checked if self.settings[key] else Qt.Unchecked)

        self.retranslateUi()

        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

    def accept(self):
        self.saveSettings()
        super().accept()

    def checkbox_enabled_handler(self):
        pass

    def retranslateUi(self):
        self.setWindowTitle(QCoreApplication.translate(
            "AdvancedEditor", "Set Intro/Outro", None))
        for x in ("intro", "outro"):
            self.tabs.setTabText(self.tabs.indexOf(getattr(self, f"{x}Tab")), QCoreApplication.translate("AdvancedEditor", x.title(), None))
            getattr(self, f"{x}_enable_label").setText(QCoreApplication.translate("AdvancedEditor", f"&Enable {x.title()}"))
            getattr(self, f"{x}_file_label").setText(QCoreApplication.translate("AdvancedEditor", "&Image/Video File"))
            getattr(self, f"{x}_file_button").setText(QCoreApplication.translate("AdvancedEditor", "Bro&wse"))
            getattr(self, f"{x}_length_label").setText(QCoreApplication.translate("AdvancedEditor", "Display &Length"))
            getattr(self, f"{x}_overlap_label").setText(QCoreApplication.translate("AdvancedEditor", "&Overlap Length"))
            getattr(self, f"{x}_fade_label").setText(QCoreApplication.translate("AdvancedEditor", "&Fade In/Out"))
            getattr(self, f"{x}_sound_label").setText(QCoreApplication.translate("AdvancedEditor", "Enable &Sound"))
        
    def showAdvancedEditor(tableWidget):
        return AdvancedEditor(tableWidget).exec()
