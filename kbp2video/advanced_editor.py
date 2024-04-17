from PySide6.QtCore import *  # type: ignore
from PySide6.QtGui import *  # type: ignore
from PySide6.QtWidgets import *  # type: ignore
from .utils import ClickLabel, mimedb, check2bool, bool2check
import ffmpeg

class AdvancedEditor(QDialog):

    # Convenience method for adding a Qt object as a property in self and
    # setting its Qt object name
    # TODO: Util class?
    def bind(self, name, obj):
        setattr(self, name, obj)
        obj.setObjectName(name)
        return obj

    SETTING_NAMES = (
        "enable",
        "file",
        "length",
        #"overlap",
        "fadeIn",
        "fadeOut",
        "black"
    )

    def __init__(self, tableWidget):
        super().__init__()
        rows = set(x.row() for x in tableWidget.selectedIndexes())
        self.outputs = [tableWidget.item(x, 3) for x in rows]
        self.kbp = f'"{tableWidget.item(rows.pop(), 0).text()}"' if len(rows) == 1 else "<Multiple Files>"
        self.highlighted = set()
        self.loadSettings()
        self.setupUi()

    def loadSettings(self):
        self.settings = {}
        self.data = []
        for x in self.outputs:
            self.data.append(x.data(Qt.UserRole) or {})
        # If there is at least one row with data, attempt to fill in the form with what's in the rows
        if any(x for x in self.data):
            for x in ("intro", "outro"):
                for setting in AdvancedEditor.SETTING_NAMES:
                    key = f"{x}_{setting}"
                    firstvalid = next(x for x in self.data if x)
                    # If all the ones with data have the same value, consider it settable for all rows
                    if firstvalid and all(key not in x or firstvalid[key] == x[key] for x in self.data):
                        self.settings[key] = firstvalid[key]
                    # Otherwise it's indeterminate
                    else:
                        self.settings[key] = None

    def saveSettings(self):
        result = {}
        for x in ("intro", "outro"):
            for setting in AdvancedEditor.SETTING_NAMES:
                widget = getattr(self, f"{x}_{setting}")
                if widget in self.highlighted:
                    print(f"Not processing {x}_{setting} due to multiple values present")
                    continue
                if type(widget) == QCheckBox:
                    val = check2bool(widget.checkState())
                elif type(widget) == QLineEdit:
                    val = widget.text()
                elif type(widget) == QTimeEdit:
                    val = widget.time().toString("mm:ss.zzz")
                else:
                    print(f"Oops, missed type {type(widget).__name__} for {x}_{setting}")
                    val = None
                result[f"{x}_{setting}"] = val
        for i,x in enumerate(self.outputs):
            # TODO: Add default if row had no data but other rows made the value indeterminate
            # Alternate solutions: error message requiring the field to be filled in
            print("Updating a row")
            cur = self.data[i]
            cur.update(result)
            x.setData(Qt.UserRole, cur)

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

            grid.addWidget(self.bind(f"{x}_title", QLabel(wordWrap=True)), row, 0, 1, 3)
            if len(self.outputs) > 1:
                self.highlight(f"{x}_title")

            row += 1

            state = Qt.Unchecked
            if (key := f"{x}_enable") in self.settings:
                if self.settings[key] == None:
                    state = Qt.PartiallyChecked
                else:
                    state = bool2check(self.settings[key])

            grid.addWidget(self.bind(f"{x}_enable", QCheckBox(tristate=(True if state == Qt.PartiallyChecked else False), checkState=state)), row, 0, alignment=Qt.AlignRight)
            grid.addWidget(self.bind(f"{x}_enable_label", ClickLabel(buddy=getattr(self,f"{x}_enable"), buddyMethod=QCheckBox.toggle)), row, 1, 1, 2)

            # The signal apparently triggers immediately if initialized during
            # the constructor when also setting the tristate property?! Qt bug?
            getattr(self, f"{x}_enable").stateChanged.connect(self.checkbox_enabled_handler)

            row += 1
            grid.addWidget(self.bind(f"{x}_file", QLineEdit()), row, 1)
            grid.addWidget(self.bind(f"{x}_file_label", ClickLabel(buddy=getattr(self, f"{x}_file"))), row, 0)
            grid.addWidget(self.bind(f"{x}_file_button", QPushButton(clicked=getattr(self, f"load_{x}_file"))), row, 2)

            if (key := f"{x}_file") in self.settings:
                if self.settings[key] == None:
                    getattr(self, key).setText("<Multiple Values>")
                    self.highlight_once(key, "textChanged")
                else:
                    getattr(self, key).setText(self.settings[key])

            row += 1
            grid.addWidget(self.bind(f"{x}_length", QTimeEdit(displayFormat="mm:ss.zzz")), row, 1, 1, 2)
            grid.addWidget(self.bind(f"{x}_length_label", ClickLabel(buddy=getattr(self, f"{x}_length"))), row, 0)

            if (key := f"{x}_length") in self.settings:
                if self.settings[key] == None:
                    # getattr(self, key).setValue("<Multiple Values>") # TODO: how to handle indeterminate value? Gray but click enables edit?
                    self.highlight_once(key, "timeChanged")
                else:
                    getattr(self, key).setTime(QTime.fromString(self.settings[key],"mm:ss.zzz"))

            #row += 1
            #grid.addWidget(self.bind(f"{x}_overlap", QTimeEdit(displayFormat="mm:ss.zzz")), row, 1, 1, 2)
            #grid.addWidget(self.bind(f"{x}_overlap_label", ClickLabel(buddy=getattr(self, f"{x}_overlap"))), row, 0)

            #if (key := f"{x}_overlap") in self.settings:
            #    if self.settings[key] == None:
            #        self.highlight_once(key, "timeChanged")
            #        # getattr(self, key).setValue("<Multiple Values>") # TODO: how to handle indeterminate value? Gray but click enables edit?
            #    else:
            #        getattr(self, key).setTime(QTime.fromString(self.settings[key],"mm:ss.zzz"))

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
                    self.highlight_once(key, "timeChanged")
                else:
                    getattr(self, key).setTime(QTime.fromString(self.settings[key],"mm:ss.zzz"))
            if (key := f"{x}_fadeOut") in self.settings:
                if self.settings[key] == None:
                    # getattr(self, key).setValue("<Multiple Values>") # TODO: how to handle indeterminate value? Gray but click enables edit?
                    self.highlight_once(key, "timeChanged")
                else:
                    getattr(self, key).setTime(QTime.fromString(self.settings[key],"mm:ss.zzz"))

            row += 1
            grid.addWidget(self.bind(f"{x}_black", QCheckBox()), row, 0, alignment=Qt.AlignRight)
            grid.addWidget(self.bind(f"{x}_black_label", ClickLabel(buddy=getattr(self,f"{x}_black"), buddyMethod=QCheckBox.toggle)), row, 1, 1, 2)
            if (key := f"{x}_black") in self.settings:
                if self.settings[key] == None:
                    getattr(self, key).setTristate(True)
                    getattr(self, key).setCheckState(Qt.PartiallyChecked)
                    getattr(self, key).setStyleSheet("color: black; background-color: gold")
                    getattr(self, key).stateChanged.connect(self.fade_black_enabled_handler)
                else:
                    getattr(self, key).setCheckState(Qt.Checked if self.settings[key] else Qt.Unchecked)

        self.checkbox_enabled_handler()
        self.retranslateUi()

        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

    # Highlights a field, then adds a signal to remove the highlight, then finally its own connection
    def highlight_once(self, field, signal):
        self.highlight(field)

        obj = getattr(self, field)
        sig = getattr(obj, signal)
        
        def foo():
            self.highlight(field, enable=False)
            try:
                sig.disconnect()
            except:
                print(f"Failed to remove {signal} from {field}")

        sig.connect(foo)
            

    def highlight(self, field, enable=True):
        if 'setStyleSheet' not in dir(field):
            field = getattr(self, field)
        if enable:
            field.setStyleSheet("color: black; background-color: gold")
            self.highlighted.add(field)
        else:
            field.setStyleSheet("")
            if field in self.highlighted:
                self.highlighted.remove(field)

    def accept(self):
        self.saveSettings()
        super().accept()

    def fade_black_enabled_handler(self):
        for x in ("intro", "outro"):
            self.highlight(f"{x}_black", getattr(self, f"{x}_black").checkState() == Qt.PartiallyChecked)

    def checkbox_enabled_handler(self):
        for x in ("intro", "outro"):
            state = check2bool(getattr(self, f"{x}_enable").checkState())
            self.highlight(f"{x}_enable", getattr(self, f"{x}_enable").checkState() == Qt.PartiallyChecked)
            for y in (*AdvancedEditor.SETTING_NAMES, f"file_button"):
                if y == "enable":
                    continue
                getattr(self, f"{x}_{y}").setEnabled(state)

    IMAGE_FILE_FILTER = "*." + " *.".join(
       "jpg jpeg png gif jfif jxl bmp tiff webp".split())
    VIDEO_FILE_FILTER = "*." + " *.".join(
       "mp4 mkv avi webm mov mpg mpeg".split())

    def load_intro_file(self):
        self.load_file("intro")

    def load_outro_file(self):
        self.load_file("outro")

    def load_file(self, where):
        file, result = QFileDialog.getOpenFileName(
        self,
        f"Select {where} video/image file",
        filter=";;".join(
            (
                f"Video/Image Files ({AdvancedEditor.VIDEO_FILE_FILTER} {AdvancedEditor.IMAGE_FILE_FILTER})",
                f"Video Files ({AdvancedEditor.VIDEO_FILE_FILTER})",
                f"Image Files ({AdvancedEditor.IMAGE_FILE_FILTER})",
                "All Files (*)")))
        # TODO: figure out a starting dir?
        if result:
            getattr(self, f"{where}_file").setText(file)
            if mimedb.mimeTypeForFile(file).name().startswith('video/'):
                # Maybe not perfect if it contains multiple streams of varying sizes, but should be unlikely
                try:
                    if vid_length := ffmpeg.probe(file)['format']['duration']:
                        getattr(self, f"{where}_length").setTime(QTime.fromMSecsSinceStartOfDay(int(float(vid_length)*1000)))
                        #getattr(self, f"{where}_overlap").setTime(getattr(self, f"{where}_length").time())
                except:
                    QMessageBox.warning(self, "Invalid File", f"{file} seems to be an invalid or corrupt video file. You may want to try another.")

    def retranslateUi(self):
        self.setWindowTitle(QCoreApplication.translate("AdvancedEditor", "Set Intro/Outro", None))
        for x in ("intro", "outro"):
            self.tabs.setTabText(self.tabs.indexOf(getattr(self, f"{x}Tab")), QCoreApplication.translate("AdvancedEditor", x.title(), None))
            getattr(self, f"{x}_title").setText(QCoreApplication.translate("AdvancedEditor", f"{x.title()} Settings for ")+self.kbp)
            getattr(self, f"{x}_title").setToolTip(QCoreApplication.translate("AdvancedEditor", f"Add an {x} clip to tracks. If multiple tracks were selected and are\nnow shown in gold, that indicates a difference between their\nsettings. If the entry is left unchanged, those settings will remain\nat their current values."))
            # TODO: more tooltips
            getattr(self, f"{x}_enable_label").setText(QCoreApplication.translate("AdvancedEditor", f"&Enable {x.title()}"))
            getattr(self, f"{x}_file_label").setText(QCoreApplication.translate("AdvancedEditor", "&Image/Video File"))
            getattr(self, f"{x}_file_button").setText(QCoreApplication.translate("AdvancedEditor", "Bro&wse"))
            getattr(self, f"{x}_length_label").setText(QCoreApplication.translate("AdvancedEditor", "Display &Length"))
            #getattr(self, f"{x}_overlap_label").setText(QCoreApplication.translate("AdvancedEditor", "&Overlap Length"))
            getattr(self, f"{x}_fade_label").setText(QCoreApplication.translate("AdvancedEditor", "&Fade In/Out"))
            getattr(self, f"{x}_black_label").setText(QCoreApplication.translate("AdvancedEditor", f'Fade {"from" if x == "intro" else "to"} &black'))
        
    def showAdvancedEditor(tableWidget):
        return AdvancedEditor(tableWidget).exec()
