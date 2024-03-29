#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Not sure why anyone would use this stuff, but just in case...
__all__ = ["TrackTable", "FileResultSet", "DropLabel", "Ui_MainWindow"]

import sys
import os
import collections
import glob
import difflib
import string
import re
import time #sleep
import fractions
from PySide6.QtCore import *  # type: ignore
from PySide6.QtGui import *  # type: ignore
from PySide6.QtWidgets import *  # type: ignore
from .utils import ClickLabel
import ffmpeg
from ._ffmpegcolor import ffmpeg_color

# This should *probably* be redone as a QTableView with a proxy to better
# manage the data and separate it from display
class TrackTable(QTableWidget):

    def __init__(self, **kwargs):
        super().__init__(0, 3, **kwargs)
        self.setObjectName("tableWidget")
        self.setAcceptDrops(True)
        # If this is enabled, user gets stuck in the widget. Arrow keys can still be used to navigate within it
        self.setTabKeyNavigation(False)
        # TODO: update when support for both is included
        # self.setHorizontalHeaderLabels(["KBP/ASS", "Audio", "Background"])
        self.setHorizontalHeaderLabels(["KBP", "Audio", "Background"])
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.setDragEnabled(False)
        self.setSortingEnabled(True)
        self.setDragDropMode(QAbstractItemView.DropOnly)
        self.setDefaultDropAction(Qt.CopyAction)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.acceptDrops()
        self.supportedDropActions()
        self.itemSelectionChanged.connect(self.handle_selection_change)

    # TODO: try getting delete button on the keyboard to work

    # Auto-vivify missing items
    def item(self, row, column):
        if (i := super().item(row, column)) is None:
            i = QTableWidgetItem("")
            self.setItem(row, column, i)
        return i

    def filename(self, row, column):
        item = self.item(row, column)
        if not item:
            return ""
        if res := item.data(Qt.UserRole):
            return res
        else:
            return item.text()

    def item_filename(self, item):
        if res := item.data(Qt.UserRole):
            return res
        else:
            return item.text()

    def handle_selection_change(self):
        mainWindow = self.parentWidget().parentWidget().parentWidget()
        if self.selectedRanges() == []:
            mainWindow.removeButton.setEnabled(False)
        else:
            mainWindow.removeButton.setEnabled(True)

    # TODO: Make user entered and imported work the same way

    def key(self, row, column):
        item = self.item(row, column)
        if item.data(Qt.UserRole):
            return item.text()
        else:
            return FileResultSet.normalize(item.text())


    def dragEnterEvent(self, event):
        mimedata = event.mimeData()
        if mimedata.hasUrls():
            urls = mimedata.urls()
            print(urls)
        elif mimedata.hasText():
            text = mimedata.text()
            files = text.splitlines()
            print(files)
        else:
            print("Unknown Data")
            print(event)
        event.acceptProposedAction()
        self.parentWidget().setCurrentIndex(1)

    def dropEvent(self, event):
        mimedata = event.mimeData()
        if mimedata.hasUrls():
            print(mimedata.urls())
        elif mimedata.hasText():
            print(mimedata.text())
        else:
            print("Unknown Data")
            print(event)

    def dropMimeData(self, row, col, mimedata, action):
        if mimedata.hasUrls():
            print(mimedata.urls())
        elif mimedata.hasText():
            print(mimedata.text())
        else:
            print("Unknown Data")
            print(event)


class FileResultSet(collections.namedtuple(
        'FileResultSet', ('kbp', 'ass', 'audio', 'background'))):
    __slots__ = ()
    PATH_REGEX = re.compile(r'^\w+-\d+|\w+-\d+$|\(Filtered.*|^[\d_]+')

    def __new__(cls):
        return super().__new__(cls, {}, {}, {}, {})

    def __bool__(self):
        return bool(self.kbp) or bool(self.ass) or bool(
            self.audio) or bool(self.background)

    def add(self, category, file):
        data = getattr(self, category)
        key = FileResultSet.normalize(file)
        if not key in data:
            data[key] = []
        data[key].append(file)

    def normalize(path):
        path = os.path.splitext(os.path.basename(path))[0]
        path = FileResultSet.PATH_REGEX.sub('', path)
        return path.casefold().translate(str.maketrans(
            "", "", string.punctuation + string.whitespace))

    def search(self, category, file, fuzziness=0.6):
        data = getattr(self, category)
        key = FileResultSet.normalize(file)
        # TODO: Include more results?
        if result := difflib.get_close_matches(
                key, data, n=3, cutoff=fuzziness):
            return [files for key in result for files in data[key]]
        else:
            return []

    def all_files(self, category):
        data = getattr(self, category)
        return [files for key, file_list in data.items()
                for files in file_list]


class DropLabel(QLabel):

    def __init__(self, parent=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.setAcceptDrops(True)
        self.mimedb = QMimeDatabase()
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("font: bold 50px")

    def identifyFile(self, path):
        if path.casefold().endswith('.kbp'):
            return 'kbp'
        elif path.casefold().endswith('.ass'):
            return 'ass'
        elif (mime := self.mimedb.mimeTypeForFile(path)).name().startswith('audio/'):
            return 'audio'
        elif mime.name().startswith('image/') or mime.name().startswith('video/'):
            return 'background'
        else:
            return None

    def generateFileList(self, paths, base_dir='',
                         dir_expand=None, identified=None):
        if identified is None:
            identified = FileResultSet()
        for path in paths:
            path = os.path.join(base_dir, path)
            isdir = os.path.isdir(path)
            if isdir and dir_expand is None:
                result = QMessageBox.question(
                    self.parentWidget(),
                    "Import folder?",
                    f"Import entire folder \"{path}\"?",
                    QMessageBox.StandardButtons(
                        QMessageBox.Yes | QMessageBox.YesToAll | QMessageBox.No | QMessageBox.NoToAll))
                if result == QMessageBox.Yes:
                    # TODO: fix rootdir
                    self.generateFileList(
                        glob.iglob(
                            '**',
                            root_dir=path,
                            recursive=True),
                        base_dir=path,
                        dir_expand=True,
                        identified=identified)
                    # Leave dir_expand to prompt next time
                elif result == QMessageBox.NoToAll:
                    dir_expand = False
                elif result == QMessageBox.YesToAll:
                    self.generateFileList(
                        glob.iglob(
                            '**',
                            root_dir=path,
                            recursive=True),
                        base_dir=path,
                        dir_expand=True,
                        identified=identified)
                    dir_expand = True
                # else Leave dir_expand to prompt next time
            if not isdir:
                if filetype := self.identifyFile(path):
                    identified.add(filetype, path)
            elif dir_expand:
                self.generateFileList(
                    glob.iglob(
                        '**',
                        root_dir=path,
                        recursive=True),
                    base_dir=path,
                    dir_expand=True,
                    identified=identified)
        return identified

    def importFiles(self, data, drop=True):
        mainWindow = self.parentWidget().parentWidget().parentWidget()
        if data and (result := self.generateFileList(data)):
            # for key, files in list(getattr(result, 'kbp').items()) + list(getattr(result, 'ass').items()):
            # For now, will assume files will be taken through the whole
            # process from kbp to video. Will later support going from .ass
            # file
            for key, files in result.kbp.items():
                table = self.parentWidget().widget(0)
                current = table.rowCount()
                table.setRowCount(current + 1)
                # TODO: handle multiple kbp files under one key
                item = QTableWidgetItem(os.path.basename(files[0]))
                item.setData(Qt.UserRole, files[0])
                item.setToolTip(files[0])
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemNeverHasChildren)
                table.setItem(current, 0, item)
                if not (outputdir := mainWindow.outputDir).text():
                    outputdir.setText(os.path.dirname(files[0]) + "/kbp2video")
                mainWindow.lastinputdir = os.path.dirname(files[0])

                for filetype, column in (('audio', 1), ('background', 2)):
                    if column == 2 and drop and mainWindow.skipBackgrounds.checkState() == Qt.Checked:
                        continue
                    # Update current in case sort moved it. Needs to be done each time in case one of these columns is the sort field
                    current = table.row(item)
                    match = result.search(filetype, files[0])

                    # If there happens to be only one kbp, assume all selected audio/backgrounds were intended for it
                    # Also, if there happens to be only one background, assume
                    # it's for all the KBPs
                    if not match and (len(result.all_files('kbp')) == 1 or (
                            filetype == 'background' and len(getattr(result, 'background')) == 1)):
                        match = result.all_files(filetype)
                        print(match)
                    if not match:
                        continue

                    print(f"Match found: {match}")

                    if len(match) > 1:
                        choice, ok = QInputDialog.getItem(
                            self.parentWidget(), f"Select {filetype} file to use",
                            f"Multiple potential {filetype} files were found for {files[0]}. Please select one, or enter a different path.",
                            match)
                        if ok:
                            match = [choice]
                        else:
                            continue

                    match_item = QTableWidgetItem(os.path.basename(match[0]))
                    match_item.setData(Qt.UserRole, match[0])
                    match_item.setToolTip(match[0])
                    match_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemNeverHasChildren)
                    table.setItem(current, column, match_item)

        if result.kbp:
            # Ui_MainWindow > QWidget > QStackedWidget > DropLabel
            # TODO: Seems like there should be a better way - maybe pass convertButton to constructor
            mainWindow.convertButton.setEnabled(True)

        elif result and (table := self.parentWidget().widget(0)).rowCount() > 0:
            # Try to fill in gaps
            # Need the item itself instead of the row due to potential reordering with sorting
            # TODO: figure out what to do if a kbp file is in the list twice - currently it just updates the last one
            data = dict((table.key(row, 0), table.item(row, 0)) for row in range(table.rowCount()))
            for filetype, column in (('audio', 1), ('background', 2)):
                if column == 2 and drop and mainWindow.skipBackgrounds.checkState() == Qt.Checked:
                    continue
                for key in getattr(result, filetype):
                    if len(filenames := getattr(result, filetype)[key]) > 1:
                        choice, ok = QInputDialog.getItem(
                            self.parentWidget(), f"Select {filetype} file to use",
                            f"Multiple potential {filetype} files were found with similar names. Please select one to import. If multiple are needed, rerun the import with those files after this one is completed. To skip all, hit cancel.",
                            filenames,
                            editable=False)
                        if ok:
                            filenames = [choice]
                        else:
                            continue

                    search_results = difflib.get_close_matches(key, data, n=3, cutoff=0.6)

                    # If just one file was dropped, assume it was intentional and prompt with all the kbps
                    if not search_results and len(result.all_files(filetype)) == 1:
                        search_results = data

                    if match := dict((table.filename(table.indexFromItem(data[key]).row(), 0), data[key]) for key in search_results):
                        if len(match) > 1:
                            choice, ok = QInputDialog.getItem(
                                self.parentWidget(), "Select KBP file to use",
                                f"Multiple potential KBP files were found for {filenames[0]}. Please select one or hit cancel to skip.",
                                match.keys(),
                                editable=False)
                            if ok:
                                match = {choice: match[choice]}
                            else:
                                continue
                        if match:
                            fname, kbp = match.popitem()
                            current = table.item(table.indexFromItem(kbp).row(), column)
                            if current and current.text():
                                answer = QMessageBox.question(
                                    self.parentWidget(),
                                    "Replace file?",
                                    f"Replace {filetype} file\n{table.item_filename(current)} for\n{fname}\nwith\n{filenames[0]}?",
                                    QMessageBox.StandardButtons(
                                        QMessageBox.Yes | QMessageBox.No))
                                if answer != QMessageBox.Yes:
                                    continue
                            match_item = QTableWidgetItem(os.path.basename(filenames[0]))
                            match_item.setData(Qt.UserRole, filenames[0])
                            match_item.setToolTip(filenames[0])
                            match_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemNeverHasChildren)
                            table.setItem(table.indexFromItem(kbp).row(), column, match_item)

        else:
            QMessageBox.information(
                self.parentWidget(), "No Files Found",
                "No relevant files discovered with provided file list.")

    def dropEvent(self, event):
        mimedata = event.mimeData()
        data = []
        if mimedata.hasUrls():
            data = [
                x.toDisplayString(
                    QUrl.ComponentFormattingOption(QUrl.PreferLocalFile))
                for x in mimedata.urls() if x.isLocalFile()]
        elif mimedata.hasText():
            for x in mimedata.text().splitlines():
                url = QUrl.fromUserInput(x, workingDirectory=os.getcwd())
                if url.isLocalFile():
                    data.append(url.toDisplayString(
                        QUrl.ComponentFormattingOption(QUrl.PreferLocalFile)))
        else:
            print("Unknown Data")
            print(event)
        self.importFiles(data)
        event.acceptProposedAction()
        self.parentWidget().setCurrentIndex(0)

    def dragEnterEvent(self, event):
        mimedata = event.mimeData()
        if mimedata.hasUrls():
            urls = mimedata.urls()
            print(urls)
        elif mimedata.hasText():
            text = mimedata.text()
            files = text.splitlines()
            print(files)
        else:
            print("Unknown Data")
            print(event)
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.parentWidget().setCurrentIndex(0)

class ConverterSignals(QObject):
    finished = Signal()
    progress = Signal(int, int)

class Converter(QRunnable):
    def __init__(self, function, *args, **kwargs):
        super().__init__()
        self.signals = ConverterSignals()
        self.function = function
        self.args = args
        self.kwargs = kwargs

    @Slot()
    def run(self):
        self.function(self.signals, *self.args, **self.kwargs)

class Ui_MainWindow(QMainWindow):

    RELEVANT_FILE_FILTER = "*." + " *.".join(
        "kbp flac wav ogg opus mp3 aac mp4 mkv avi webm mov mpg mpeg jpg jpeg png gif jfif jxl bmp tiff webp".split())

    def __init__(self):
        super().__init__()
        self.threadpool = QThreadPool()
        self.setupUi()

    # Convenience method for adding a Qt object as a property in self and and
    # setting its Qt object name
    def bind(self, name, obj):
        setattr(self, name, obj)
        obj.setObjectName(name)
        return obj

    def setupUi(self):
        if not self.objectName():
            self.setObjectName("KBP to Video")
        self.resize(1280, 720)
        self.bind("centralWidget", QWidget(self))

        self.setCentralWidget(self.centralWidget)
        # TODO: Create menubar with contents
        # self.menubar = QMenuBar()
        # self.menubar.setObjectName("menubar")
        # self.menubar.setGeometry(QRect(0, 0, 886, 25))
        # self.menubar.addMenu("test")
        # self.setMenuBar(self.menubar)
        self.setStatusBar(self.bind("statusbar", QStatusBar(self)))

        QCoreApplication.setOrganizationName("ItMightBeKaraoke")
        QCoreApplication.setApplicationName("kbp2video")
        QCoreApplication.setOrganizationDomain("itmightbekaraoke.com")

        self.settings = QSettings()

        ##################### Left pane #####################

        self.bind(
            "horizontalLayout",
            QHBoxLayout(
                self.centralWidget,
                sizeConstraint=QLayout.SetDefaultConstraint,
                contentsMargins=QMargins(
                    0,
                    0,
                    0,
                    0)))

        self.horizontalLayout.addItem(QSpacerItem(
            20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        self.horizontalLayout.addLayout(
            self.bind(
                "verticalLayout",
                QVBoxLayout(
                    sizeConstraint=QLayout.SetDefaultConstraint)),
            stretch=10)

        self.verticalLayout.addWidget(
            self.bind("stackedWidget", QStackedWidget(self.centralWidget)))

        self.stackedWidget.addWidget(self.bind("tableWidget", TrackTable()))
        self.stackedWidget.addWidget(
            self.bind(
                "filedrop",
                DropLabel(
                    self.stackedWidget,
                    text="+\nDrop files here")))

        self.verticalLayout.addItem(QSpacerItem(
            20, 5, QSizePolicy.Expanding, QSizePolicy.Maximum))

        self.verticalLayout.addWidget(
            self.bind("dragDropDescription", QLabel(alignment=Qt.AlignCenter)))

        self.verticalLayout.addItem(QSpacerItem(
            20, 5, QSizePolicy.Expanding, QSizePolicy.Maximum))

        self.verticalLayout.addLayout(
            self.bind("leftPaneButtons", QHBoxLayout()))

        self.lastinputdir = ""
        self.leftPaneButtons.addWidget(
            self.bind("addButton", QPushButton(clicked=self.add_files_button)))
        self.leftPaneButtons.addWidget(
            self.bind(
                "removeButton", QPushButton(
                    clicked=self.remove_files_button,
                    enabled=False)))
        self.leftPaneButtons.addWidget(
            self.bind(
                "addRowButton", QPushButton(
                    clicked=self.add_row_button)))

        self.horizontalLayout.addItem(QSpacerItem(
            20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        ##################### Right pane #####################

        self.horizontalLayout.addLayout(
            self.bind("gridLayout", QGridLayout()), stretch=0)

        gridRow = 0
        self.gridLayout.addItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding), gridRow, 0, 1, 3)
        self.gridLayout.setRowStretch(gridRow, 10)

        gridRow += 1
        self.gridLayout.addWidget(self.bind("assDivider", QLabel(
            alignment=Qt.AlignCenter)), gridRow, 0, 1, 3)

        gridRow += 1
        self.aspectRatioOptions = {
            "CDG, borders (25:18)": (300, True),
            "Wide, borders (16:9)": (384, True),
            "Standard, borders (4:3)": (288, True),
            "CDG no border (3:2)": (288, False),
            "Wide no border (16:9)": (341, False)
        }
        self.gridLayout.addWidget(
            self.bind("aspectLabel", ClickLabel()), gridRow, 0)
        self.gridLayout.addWidget(
            self.bind("aspectRatioBox",QComboBox()),gridRow, 1, 1, 2)
                    # sizePolicy=QSizePolicy(
                    #     QSizePolicy.Maximum,
                    #     QSizePolicy.Maximum))),
        self.aspectRatioBox.addItems(self.aspectRatioOptions.keys())
        self.aspectLabel.setBuddy(self.aspectRatioBox)
        self.aspectRatioBox.setCurrentIndex(self.settings.value("subtitle/aspect_ratio_index", type=int, defaultValue=0))

        gridRow += 1
        self.gridLayout.addWidget(self.bind("fades", ClickLabel()), gridRow, 0)
        self.gridLayout.addWidget(
            self.bind(
                "fadeIn",
                QSpinBox(
                    minimum=0,
                    maximum=5000,
                    singleStep=10,
                    suffix=" ms",
                    value=self.settings.value("subtitle/fade_in", type=int, defaultValue=50),
                    sizePolicy=QSizePolicy(
                        QSizePolicy.Maximum,
                        QSizePolicy.Maximum))),
            gridRow,
            1)
        self.fades.setBuddy(self.fadeIn)
        self.gridLayout.addWidget(
            self.bind(
                "fadeOut",
                QSpinBox(
                    minimum=0,
                    maximum=5000,
                    singleStep=10,
                    suffix=" ms",
                    value=self.settings.value("subtitle/fade_out", type=int, defaultValue=50),
                    sizePolicy=QSizePolicy(
                        QSizePolicy.Maximum,
                        QSizePolicy.Maximum))),
            gridRow,
            2)

        gridRow += 1
        self.gridLayout.addWidget(self.bind("overrideOffset", QCheckBox(stateChanged=self.offset_check_box)), gridRow, 0, alignment=Qt.AlignRight)
        self.gridLayout.addWidget(self.bind("overrideOffsetLabel", ClickLabel(buddy=self.overrideOffset, buddyMethod=QCheckBox.toggle)), gridRow, 1, 1, 2)

        gridRow += 1
        self.gridLayout.addWidget(
            self.bind(
                "offset",
                QDoubleSpinBox(
                    minimum=-5,
                    maximum=180,
                    singleStep=0.05,
                    suffix=" s",
                    value=self.settings.value("subtitle/offset", type=float, defaultValue=0.0),
                    enabled=False
                    )),
            gridRow,
            1)
        self.gridLayout.addWidget(self.bind("offsetLabel", ClickLabel(buddy=self.offset)), gridRow, 0)

        self.offset_check_box(setState=Qt.Checked if self.settings.value("subtitle/override_offset", type=bool, defaultValue=False) else Qt.Unchecked)

        gridRow += 1
        self.gridLayout.addWidget(self.bind("transparencyBox", QCheckBox(checkState=Qt.Checked if self.settings.value("subtitle/transparent_bg", type=bool, defaultValue=True) else Qt.Unchecked)), gridRow, 0, alignment=Qt.AlignRight)
        self.gridLayout.addWidget(self.bind("transparencyLabel", ClickLabel(buddy=self.transparencyBox, buddyMethod=QCheckBox.toggle)), gridRow, 1, 1, 2)

        gridRow += 1
        self.gridLayout.addItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding), gridRow, 0, 1, 3)
        self.gridLayout.setRowStretch(gridRow, 10)

        gridRow += 1
        self.gridLayout.addWidget(self.bind("ffmpegDivider", ClickLabel(
            alignment=Qt.AlignCenter)), gridRow, 0, 1, 3)

        gridRow += 1
        self.gridLayout.addWidget(self.bind("colorApplyButton", QPushButton(
            clicked=self.color_apply_button)), gridRow, 0)
        self.gridLayout.addWidget(self.bind("colorText", QLineEdit(
            text="#000000", inputMask="\\#HHHHHH", styleSheet="color: #FFFFFF; background-color: #000000", textChanged=self.updateColor)), gridRow, 1)

        self.updateColor(setColor=self.settings.value("video/background_color", type=str, defaultValue="#000000"))

        # TODO: Find a better way to set this to a reasonable width for 7 characters
        # minimumSizeHint is enough for about 3
        # sizeHint is enough for about 12
        self.colorText.setFixedWidth(
            self.colorText.minimumSizeHint().width() * 7 / 3)

        self.gridLayout.addWidget(self.bind("colorChooseButton", QPushButton(
            clicked=self.color_choose_button)), gridRow, 2)

        gridRow += 1
        self.resolutionOptions = [
            "1500x1080",
            "1920x1080 (1080p)",
            "3000x2160",
            "3840x2160 (4K)",
            "1000x720",
            "1280x720 (720p)",
            "640x480"
        ]
        self.gridLayout.addWidget(
            self.bind("resolutionLabel", ClickLabel()), gridRow, 0)
        self.gridLayout.addWidget(
            self.bind("resolutionBox", QComboBox()), gridRow, 1, 1, 2)
        self.resolutionBox.addItems(self.resolutionOptions)
        self.resolutionBox.setCurrentIndex(self.settings.value("video/output_resolution_index", type=int, defaultValue=0))
        self.resolutionLabel.setBuddy(self.resolutionBox)

        gridRow += 1
        # TODO: implement feature
        self.gridLayout.addWidget(self.bind("overrideBGResolution", QCheckBox(enabled=False)), gridRow, 0, alignment=Qt.AlignRight)
        #self.gridLayout.addWidget(self.bind("overrideBGResolution", QCheckBox(checkState=Qt.Checked if self.settings.value("video/override_bg_resolution", type=bool, defaultValue=False) else Qt.Unchecked)), gridRow, 0, alignment=Qt.AlignRight)
        self.gridLayout.addWidget(self.bind("overrideBGLabel", ClickLabel(buddy=self.overrideBGResolution, buddyMethod=QCheckBox.toggle)), gridRow, 1, 1, 2)

        gridRow += 1
        self.containerOptions = {
            "mp4": (("h264", "libvpx-vp9", "libx265", "libaom-av1"), ("aac", "mp3", "libopus")),
            "mkv": (("libvpx-vp9", "h264", "libx265", "libaom-av1"), ("flac", "libopus", "aac", "mp3")),
            "webm": (("libvpx-vp9", "libaom-av1"), ("libopus",)),
        }
        self.gridLayout.addWidget(
            self.bind("containerLabel", ClickLabel()), gridRow, 0)
        self.gridLayout.addWidget(
            self.bind("containerBox", QComboBox()), gridRow, 1, 1, 2)
        self.containerBox.addItems(self.containerOptions.keys())
        self.containerBox.setCurrentIndex(self.settings.value("video/container_format_index", type=int, defaultValue=0))
        self.containerLabel.setBuddy(self.containerBox)

        gridRow += 1
        self.gridLayout.addWidget(
            self.bind("vcodecLabel", ClickLabel()), gridRow, 0)
        self.gridLayout.addWidget(
            self.bind("vcodecBox", QComboBox()), gridRow, 1, 1, 2)
        self.vcodecBox.addItems(self.containerOptions[self.containerBox.currentText()][0])
        self.vcodecBox.setCurrentIndex(self.settings.value("video/video_codec_index", type=int, defaultValue=0))
        self.vcodecLabel.setBuddy(self.vcodecBox)

        gridRow += 1
        self.gridLayout.addWidget(
            self.bind("acodecLabel", ClickLabel()), gridRow, 0)
        self.gridLayout.addWidget(
            self.bind("acodecBox", QComboBox()), gridRow, 1, 1, 2)
        self.acodecBox.addItems(self.containerOptions[self.containerBox.currentText()][1])
        self.acodecBox.setCurrentIndex(self.settings.value("video/audio_codec_index", type=int, defaultValue=0))
        self.acodecLabel.setBuddy(self.acodecBox)

        gridRow += 1
        self.gridLayout.addWidget(
            self.bind("abitrateLabel", ClickLabel()), gridRow, 0)
        self.gridLayout.addWidget(
            self.bind("abitrateBox", QLineEdit(validator=QRegularExpressionValidator(QRegularExpression(r"^\d*[1-9]\d*k?$")), text=self.settings.value("video/audio_bitrate", type=str, defaultValue=""))), gridRow, 1, 1, 2)
        self.abitrateLabel.setBuddy(self.abitrateBox)

        self.containerBox.currentTextChanged.connect(self.updateCodecs)

        #gridRow += 1
        #self.label_2 = QLabel()
        #self.label_2.setObjectName("label_2")

        #self.gridLayout.addWidget(self.label_2, gridRow, 0)

        gridRow += 1
        self.gridLayout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding), gridRow, 0, 1, 3)
        self.gridLayout.setRowStretch(gridRow, 10)

        gridRow += 1
        self.gridLayout.addWidget(self.bind("generalDivider", ClickLabel(
            alignment=Qt.AlignCenter)), gridRow, 0, 1, 3)

        gridRow += 1
        self.gridLayout.addWidget(
            self.bind("outputDirLabel", ClickLabel()), gridRow, 0)
        self.gridLayout.addWidget(
            self.bind("outputDir", QLineEdit()), gridRow, 1)
        self.gridLayout.addWidget(
            self.bind("outputDirButton", QPushButton(clicked=self.output_dir)), gridRow, 2)
        self.outputDirLabel.setBuddy(self.outputDir)

        gridRow += 1
        self.gridLayout.addWidget(self.bind("skipBackgrounds", QCheckBox(checkState=Qt.Checked if self.settings.value("video/ignore_bg_files_drag_drop", type=bool, defaultValue=False) else Qt.Unchecked)), gridRow, 0, alignment=Qt.AlignRight)
        self.gridLayout.addWidget(self.bind("skipBackgroundsLabel", ClickLabel(buddy=self.skipBackgrounds, buddyMethod=QCheckBox.toggle)), gridRow, 1, 1, 2)

        gridRow += 1
        self.gridLayout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding), gridRow, 0, 1, 3)
        self.gridLayout.setRowStretch(gridRow, 30)

        gridRow += 1
        self.gridLayout.addWidget(
            self.bind("convertButton", QPushButton(enabled=False, clicked=self.runConversion)), gridRow, 0, 1, 3)

        self.horizontalLayout.addItem(QSpacerItem(
            20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        self.retranslateUi()

        QMetaObject.connectSlotsByName(self)
    # setupUi

    def add_files_button(self):
        files, result = QFileDialog.getOpenFileNames(
            self,
            "Select files to import (either kbp or kbp plus associated files)",
            filter=";;".join(
                (
                    f"All Relevant Files, hopefully ({Ui_MainWindow.RELEVANT_FILE_FILTER})",
                    "Karaoke Builder Studio Project files (*.kbp)",
                    "All Files (*)")),
            dir=self.lastinputdir)
        if result:
            self.filedrop.importFiles(files, drop=False)

    def offset_check_box(self, *_ignored, setState=None):
        if setState != None:
            self.overrideOffset.setCheckState(setState)
        if self.overrideOffset.checkState() == Qt.Checked:
            self.offset.setEnabled(True)
        else:
            self.offset.setEnabled(False)

    def color_apply_button(self):
        for row in range(self.tableWidget.rowCount()):
            if not (cur := self.tableWidget.item(row, 2)) or not cur.text():
                self.tableWidget.setItem(row, 2, QTableWidgetItem(
                    f"color: {self.colorText.text()}"))

    def color_choose_button(self):
        result = QColorDialog.getColor(
            initial=QColor.fromString(self.colorText.text()))
        if result.isValid():
            self.colorText.setText(result.name())

    def remove_files_button(self):
        # remove from the end to avoid re-order
        for row in sorted(
                set(x.row() for x in self.tableWidget.selectedIndexes()),
                reverse=True):
            self.tableWidget.removeRow(row)
        if self.tableWidget.rowCount() == 0:
            self.convertButton.setEnabled(False)

    def add_row_button(self):
        self.tableWidget.setRowCount(self.tableWidget.rowCount() + 1)
        self.convertButton.setEnabled(True)

    def updateColor(self, *_ignored, setColor=None):
        if setColor != None:
            self.colorText.setText(setColor)
        bgcolor = QColor.fromString(self.colorText.text())
        textcolor = "#000000"
        if bgcolor.lightness() <= 128:
            textcolor = "#FFFFFF"
        self.colorText.setStyleSheet(f"color: {textcolor}; background-color: {bgcolor.name()}")

    def updateCodecs(self):
        for idx, box in enumerate((self.vcodecBox, self.acodecBox)):
            box.setMaxCount(0)
            box.setMaxCount(10)
            box.addItems(self.containerOptions[self.containerBox.currentText()][idx])

    def output_dir(self):
        outputdir = QFileDialog.getExistingDirectory(self, dir=os.path.dirname(self.outputDir.text()))
        if outputdir:
            self.outputDir.setText(outputdir)

    def saveSettings(self):
        to_save = {
            "subtitle/aspect_ratio_index": self.aspectRatioBox.currentIndex(),
            "subtitle/fade_in": self.fadeIn.value(),
            "subtitle/fade_out": self.fadeOut.value(),
            "subtitle/offset": self.offset.value(),
            "subtitle/override_offset": True if self.overrideOffset.checkState() == Qt.Checked else False,
            "subtitle/transparent_bg": True if self.transparencyBox.checkState() == Qt.Checked else False,
            "video/background_color": self.colorText.text(),
            "video/output_resolution_index": self.resolutionBox.currentIndex(),
            #"overrideBGResolution": True if self.overrideBGResolution.checkState() == Qt.Checked else False,
            "video/container_format_index": self.containerBox.currentIndex(),
            "video/video_codec_index": self.vcodecBox.currentIndex(),
            "video/audio_codec_index": self.acodecBox.currentIndex(),
            "video/audio_bitrate": self.abitrateBox.text(),
            "video/ignore_bg_files_drag_drop": True if self.skipBackgrounds.checkState() == Qt.Checked else False,
        }
        for setting, value in to_save.items():
            self.settings.setValue(setting, value)
        self.settings.sync()

    def runConversion(self):
        self.saveSettings()
        converter = Converter(self.conversion_runner)
        # worker.signals.finished.connect
        self.threadpool.start(converter)
    
    def assFile(self, kbp):
        filename = os.path.basename(kbp)
        # This REALLY needs to be set...
        while not self.outputDir.text():
            self.output_dir()
        return self.outputDir.text() + "/" + filename[:-4].translate(str.maketrans("","",":;,'=\"")) + ".ass"
    
    def vidFile(self, kbp):
        filename = os.path.basename(kbp)
        return self.outputDir.text() + "/" + filename[:-4] + "." + self.containerBox.currentText()

    def audioffmpegBitrate(self):
        if self.acodecBox.currentText() == 'flac':
            # return ''
            return {}
        # TODO: Good defaults based on format
        else:
            #return self.abitrateBox.text() or '-b:a 256k' # This couldn't have been working before for manually entered
            return {"audio_bitrate": self.abitrateBox.text() or '256k'}

    # Defining this to be invoked from a thread
    @Slot(str, str, result=int)
    def yesno(self, title, text):
        return QMessageBox.question(
            self,
            title,
            text,
            QMessageBox.StandardButtons(
                QMessageBox.Yes | QMessageBox.No))

    @Slot(str, str)
    def info(self, title, text):
        QMessageBox.information(self, title, text)

    def conversion_runner(self, signals):
        unsupported_message = False
        assOptions = ["-f"]
        width, border = self.aspectRatioOptions[self.aspectRatioBox.currentText()]
        default_bg = self.colorText.text().strip(" #")
        if width != 300:
            assOptions += ["-W", f"{width}"]
        if not border:
            assOptions += ["--no-b"]
        assOptions += ["-F", f"{self.fadeIn.value()},{self.fadeOut.value()}"]
        if self.overrideOffset.checkState() == Qt.Checked:
            assOptions += ["-o", f"{self.offset.value()}"]
        if self.transparencyBox.checkState() != Qt.Checked:
            assOptions += ["--no-t"]
        resolution = self.resolutionBox.currentText().split()[0]
        for row in range(self.tableWidget.rowCount()):
            kbp = self.tableWidget.filename(row, 0)
            audio = self.tableWidget.filename(row, 1)
            background = self.tableWidget.filename(row, 2)
            if not kbp:
                continue
            self.statusbar.showMessage(f"Converting file {row+1} of {self.tableWidget.rowCount()} ({kbp})")
            background_type = None
            if not background:
                pass
            elif background.startswith("color:"):
                background = background[6:].strip(" #")
                background_type = 0
            elif (mimename := self.filedrop.mimedb.mimeTypeForFile(background).name()).startswith('image/'):
                background_type = 1
            elif mimename.startswith('video/'):
                background_type = 2
            # bad mime type (not image/video or nonexistant file), or no background specified
            if background_type == None:
                background_type = 0
                background = default_bg
            print("kbp2ass " + " ".join(assOptions) + " " + kbp)
            q = QProcess(program="kbp2ass", arguments=assOptions+[kbp])
            q.start()
            q.waitForFinished(-1)
            data = q.readAllStandardOutput()
            if q.exitStatus() != QProcess.NormalExit or data.isEmpty():
                QMetaObject.invokeMethod(
                    self,
                    'info', 
                    Qt.AutoConnection,
                    Q_ARG(str, "Failed to process kbp"),
                    Q_ARG(str, f"Failed to process .kbp file\n{kbp}\n\nError Output:\n{q.readAllStandardError().toStdString()}"))
                continue
            assfile = self.assFile(kbp)

            # QDir is inconsistent. Needs to be static to check existence, and
            # mkdir needs to be run from an instantiated instance in the parent
            # directory, not worth the hassle
            if not os.path.isdir(outdir := os.path.dirname(assfile)):
                os.mkdir(outdir)

            f = QFile(assfile)
            if f.exists():
                answer = QMessageBox.StandardButton(QMetaObject.invokeMethod(
                    self,
                    'yesno',
                    Qt.BlockingQueuedConnection,
                    Q_RETURN_ARG(int),
                    Q_ARG(str, "Replace file?"),
                    Q_ARG(str, f"Overwrite {assfile}?")))
                if answer != QMessageBox.Yes:
                    continue
            if not f.open(QIODevice.WriteOnly | QIODevice.Text):
                continue
            out = QTextStream(f)
            out << data
            f.close()
            #ffmpeg_options = ["-y"]
            output_options = {}
            base_assfile = os.path.basename(assfile)
            if background_type == 0:
                #ffmpeg_options += f"-f lavfi -i color=color={background}:r=60:s={resolution}".split()
                background_video = ffmpeg.input(f"color=color={background}:r=60:s={resolution}", f="lavfi")
                bg_size = QSize(*(int(x) for x in resolution.split('x')))
            elif background_type == 1:
                bg_size = QImage(background).size()
                #ffmpeg_options += f"-loop 1 -framerate 60 -i".split() + [background]
                background_video = ffmpeg.input(background, loop=1, framerate=60)
            elif background_type == 2:
                # Pull the dimensions of the first video stream found in the file
                bginfo = ffmpeg.probe(background)
                bg_size = next(QSize(x['width'],x['height']) for x in bginfo['streams'] if x['codec_type'] == 'video')
                #ffmpeg_options += ["-i", background]
                background_video = ffmpeg.input(background).video
            #ffmpeg_options += ["-i", audio]
            audio_stream = ffmpeg.input(audio).audio
            if background_type == 1 or background_type == 2:
                if not bg_size:
                    QMetaObject.invokeMethod(
                        self,
                        'info',
                        Qt.AutoConnection,
                        Q_ARG(str, "Unsupported Background file"),
                        Q_ARG(str, f"Unable to determine the resolution of file\n{background}"))
                    continue
                if self.overrideBGResolution.checkState == Qt.Checked and not unsupported_message:
                    QMetaObject.invokeMethod(
                        self,
                        'info',
                        Qt.AutoConnection,
                        Q_ARG(str, "Unsupported Option"),
                        Q_ARG(str, f"Override background resolution option not supported yet!"))
                    unsupported_message = True
                    continue

            bg_ratio = fractions.Fraction(bg_size.width(), bg_size.height())
            ass_ratio = fractions.Fraction(width, border and 216 or 192)
            if bg_ratio > ass_ratio:
                # letterbox sides
                ass_size = QSize(round(bg_size.height() * ass_ratio), bg_size.height())
                # ass_move = f":x={round((bg_size.width() - ass_size.width())/2)}"
                ass_move = {"x": round((bg_size.width() - ass_size.width())/2)}
            elif bg_ratio < ass_ratio:
                # letterbox top/bottom
                ass_size = QSize(bg_size.width(), round(bg_size.width() / ass_ratio))
                # ass_move = f":y={round((bg_size.height() - ass_size.height())/2)}"
                ass_move = {"y": round((bg_size.height() - ass_size.height())/2)}
            else:
                ass_size = bg_size
                # ass_move = ""
                ass_move = {}

            if ass_move:
                # ffmpeg_options += ["-filter_complex", f"color=color=000000@0:r=60:s={ass_size.width()}x{ass_size.height()},format=rgba,ass={base_assfile}:alpha=1[out1];[0:v][out1]overlay=eof_action=pass{ass_move}[out]", "-map", "[out]:v", "-map", "1:a"]
                filtered_video = background_video.overlay(
                    ffmpeg_color(color="000000@0", r=60, s=f"{ass_size.width()}x{ass_size.height()}")
                        .filter_("format", "rgba")
                        .filter_("ass", base_assfile, alpha=1),
                    eof_action="pass",
                    **ass_move
                )
            else:
                # ffmpeg_options += ["-vf", f"ass={base_assfile}"]
                filtered_video = background_video.filter_("ass", base_assfile)
            if background_type == 0 or background_type == 1:
                #ffmpeg_options += ["-shortest"]
                output_options["shortest"] = None
            # TODO: should pix_fmt be configurable or change default based on codec?
            #ffmpeg_options += f"-pix_fmt yuv420p -c:a {self.acodecBox.currentText()} {self.audioffmpegBitrate()} -c:v {self.vcodecBox.currentText()}".split()
            output_options.update(self.audioffmpegBitrate())
            output_options.update({"pix_fmt": "yuv420p", "c:a": self.acodecBox.currentText(), "c:v": self.vcodecBox.currentText()})
            # ffmpeg_options += [self.vidFile(kbp)]
            # TODO: determine if it's best to leave this as a QProcess, or use ffmpeg.run() and have it POpen itself
            ffmpeg_options = ffmpeg.output(filtered_video, audio_stream, self.vidFile(kbp), **output_options).overwrite_output().get_args()
            print("ffmpeg" + " " + " ".join(ffmpeg_options))
            q = QProcess(program="ffmpeg", arguments=ffmpeg_options, workingDirectory=os.path.dirname(assfile))
            # cwd= , overwrite_output=True
            q.start()
            q.waitForFinished(-1)
        
        self.statusbar.showMessage("Conversion completed!")
        signals.finished.emit()

    def retranslateUi(self):
        self.setWindowTitle(QCoreApplication.translate(
            "MainWindow", "KBP to Video", None))
        self.addButton.setText(QCoreApplication.translate(
            "MainWindow", "&Add Files...", None))
        self.colorChooseButton.setText(QCoreApplication.translate(
            "MainWindow", "C&hoose...", None))
        self.colorChooseButton.setToolTip(QCoreApplication.translate(
            "MainWindow", "Choose a background color with a color picker", None))
        self.colorApplyButton.setText(QCoreApplication.translate(
            "MainWindow", "< A&pply BG", None))
        self.colorApplyButton.setToolTip(
            QCoreApplication.translate(
                "MainWindow",
                "Set the background color on everything in the left pane without a background",
                None))
        self.removeButton.setText(QCoreApplication.translate(
            "MainWindow", "&Remove Selected", None))
        self.addRowButton.setText(QCoreApplication.translate(
            "MainWindow", "Add &empty row", None))
        self.dragDropDescription.setText(
            QCoreApplication.translate(
                "MainWindow",
                "Drag/Drop files/folders above or use buttons below",
                None))
        self.assDivider.setText(QCoreApplication.translate(
            "MainWindow", "Subtitle options", None))
        self.fades.setText(QCoreApplication.translate(
            "MainWindow", "&Fade In/Out", None))
        self.aspectLabel.setText(QCoreApplication.translate(
            "MainWindow", "A&spect Ratio", None))
        self.transparencyLabel.setText(QCoreApplication.translate(
            "MainWindow", "&Draw BG color transparent", None))
        self.transparencyLabel.setToolTip(QCoreApplication.translate(
            "MainWindow", "When using palette index 0 as a font or border color in KBS, make that color\ntransparent in the resulting .ass file. This improves compatibility with\ndrawing appearing and overlapping text. ", None))
        self.overrideOffsetLabel.setText(QCoreApplication.translate(
            "MainWindow", "Overr&ide Timestamp Offset", None))
        self.overrideOffsetLabel.setToolTip(QCoreApplication.translate(
            "MainWindow", "Set an offset to be applied to every timestamp in the KBP file when converting\nto .ass. If not overridden, the setting from within KBS is used if it can be located.", None))
        self.offsetLabel.setText(QCoreApplication.translate(
            "MainWindow", "Timesta&mp Offset", None))
        self.ffmpegDivider.setText(QCoreApplication.translate(
            "MainWindow", "Video options", None))
        self.resolutionLabel.setText(QCoreApplication.translate(
            "MainWindow", "&Output Resolution", None))
        self.containerLabel.setText(QCoreApplication.translate(
            "MainWindow", "Output File &Type", None))
        self.vcodecLabel.setText(QCoreApplication.translate(
            "MainWindow", "&Video Codec", None))
        self.acodecLabel.setText(QCoreApplication.translate(
            "MainWindow", "A&udio Codec", None))
        self.abitrateLabel.setText(QCoreApplication.translate(
            "MainWindow", "Audio &Bitrate", None))
        self.abitrateLabel.setToolTip(QCoreApplication.translate(
            "MainWindow", "Enter a number in bits per second, or suffixed with a k for kilobits per second.", None))
        self.abitrateBox.setPlaceholderText(QCoreApplication.translate(
            "MainWindow", "Leave blank for default", None))
        self.overrideBGLabel.setText(QCoreApplication.translate(
            "MainWindow", "Override back&ground", None))
        self.overrideBGLabel.setToolTip(QCoreApplication.translate(
            "MainWindow", "If this is unchecked, the resolution setting is only used for tracks with\nthe background set as a color. If it is checked, background image/video\nis scaled (and letterboxed if the aspect ratio differs) to achieve the\ntarget resolution.\n\nFEATURE NOT SUPPORTED YET", None))
        self.skipBackgroundsLabel.setText(QCoreApplication.translate(
            "MainWindow", "Ig&nore BG files in drag/drop", None))
        self.skipBackgroundsLabel.setToolTip(QCoreApplication.translate(
            "MainWindow", "When dragging and dropping files, do not import any image or video files\nas backgrounds. This is useful if you have your output and input files\nin the same place and usually use solid color backgrounds.", None))
        self.generalDivider.setText(QCoreApplication.translate(
            "MainWindow", "kbp2video options", None))
        self.outputDirLabel.setText(QCoreApplication.translate(
            "MainWindow", "Output Fo&lder", None))
        self.outputDirButton.setText(QCoreApplication.translate(
            "MainWindow", "Bro&wse...", None))
        self.convertButton.setText(QCoreApplication.translate(
            "MainWindow", "&Convert", None))
    # retranslateUi


def run(argv=sys.argv):
    app = QApplication(argv)
    window = Ui_MainWindow()
    window.show()
    sys.exit(app.exec())
