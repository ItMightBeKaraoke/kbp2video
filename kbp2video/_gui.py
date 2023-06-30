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
from PySide6.QtCore import *  # type: ignore
from PySide6.QtGui import *  # type: ignore
from PySide6.QtWidgets import *  # type: ignore


# This should *probably* be redone as a QTableView with a proxy to better
# manage the data and separate it from display
class TrackTable(QTableWidget):

    def __init__(self, **kwargs):
        super().__init__(0, 3, **kwargs)
        self.setObjectName("tableWidget")
        self.setAcceptDrops(True)
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

    # TODO: try getting delete button on the keyboard to work

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
                    self,
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

    def importFiles(self, data):
        any_kbps = False
        if data and (result := self.generateFileList(data)):
            found = {"audio": set(), "background": set()}
            # for key, files in list(getattr(result, 'kbp').items()) + list(getattr(result, 'ass').items()):
            # For now, will assume files will be taken through the whole
            # process from kbp to video. Will later support going from .ass
            # file
            for key, files in getattr(result, 'kbp').items():
                any_kbps = True
                table = self.parentWidget().widget(0)
                current = table.rowCount()
                table.setRowCount(current + 1)
                # TODO: handle multiple kbp files under one key
                item = QTableWidgetItem(os.path.basename(files[0]))
                item.setData(Qt.UserRole, files[0])
                item.setToolTip(files[0])
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemNeverHasChildren)
                table.setItem(current, 0, item)
                for filetype, column in (('audio', 1), ('background', 2)):
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
                            self, f"Select {filetype} file to use",
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

        if any_kbps:
            # Ui_MainWindow > QWidget > QStackedWidget > DropLabel
            # TODO: Seems like there should be a better way - maybe pass convertButton to constructor
            self.parentWidget().parentWidget().parentWidget().convertButton.setEnabled(True)

        else:
            QMessageBox.information(
                self, "No KBP Files Found",
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
        if b := self.buddy():
            if self.buddyMethod:
                self.buddyMethod(b)
            else:
                b.setFocus(Qt.MouseFocusReason)

class Ui_MainWindow(QMainWindow):

    RELEVANT_FILE_FILTER = "*." + " *.".join(
        "kbp flac wav ogg opus mp3 aac mp4 mkv avi webm mov mpg mpeg jpg jpeg png gif jfif jxl bmp tiff webp".split())

    def __init__(self):
        super().__init__()
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

        self.leftPaneButtons.addWidget(
            self.bind("addButton", QPushButton(clicked=self.add_files_button)))
        self.leftPaneButtons.addWidget(
            self.bind(
                "removeButton", QPushButton(
                    clicked=self.remove_files_button)))
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
                    value=50,
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
                    value=50,
                    sizePolicy=QSizePolicy(
                        QSizePolicy.Maximum,
                        QSizePolicy.Maximum))),
            gridRow,
            2)

        gridRow += 1
        self.gridLayout.addWidget(self.bind("overrideOffset", QCheckBox(stateChanged=self.offset_check_box)), gridRow, 0, alignment=Qt.AlignRight)
        self.gridLayout.addWidget(self.bind("overrideOffsetLabel", ClickLabel(buddy=self.overrideOffset, buddyMethod=QCheckBox.toggle)), gridRow, 1, 1, 2)

        gridRow += 1
        self.gridLayout.addWidget(self.bind("offsetLabel", ClickLabel(buddyMethod=QCheckBox.toggle)), gridRow, 0)
        self.gridLayout.addWidget(
            self.bind(
                "offset",
                QDoubleSpinBox(
                    minimum=-5,
                    maximum=180,
                    singleStep=0.05,
                    suffix=" s",
                    value=0,
                    enabled=False
                    )),
            gridRow,
            1)

        gridRow += 1
        self.gridLayout.addWidget(self.bind("transparencyBox", QCheckBox(checkState=Qt.Checked)), gridRow, 0, alignment=Qt.AlignRight)
        self.gridLayout.addWidget(self.bind("transparencyLabel", ClickLabel(buddy=self.transparencyBox, buddyMethod=QCheckBox.toggle)), gridRow, 1, 1, 2)

        self.offsetLabel.setBuddy(self.transparencyBox)

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
        self.resolutionLabel.setBuddy(self.resolutionBox)

        gridRow += 1
        self.gridLayout.addWidget(self.bind("overrideBGResolution", QCheckBox()), gridRow, 0, alignment=Qt.AlignRight)
        self.gridLayout.addWidget(self.bind("overrideBGLabel", ClickLabel(buddy=self.overrideBGResolution, buddyMethod=QCheckBox.toggle)), gridRow, 1, 1, 2)

        gridRow += 1
        self.containerOptions = {
            "mp4": (("h264", "libvpx-vp9", "libx265", "libaom-av1"), ("aac", "mp3", "opus")),
            "mkv": (("libvpx-vp9", "h264", "libx265", "libaom-av1"), ("flac", "opus", "aac", "mp3")),
            "webm": (("libvpx-vp9", "libaom-av1"), ("opus",)),
        }
        self.gridLayout.addWidget(
            self.bind("containerLabel", ClickLabel()), gridRow, 0)
        self.gridLayout.addWidget(
            self.bind("containerBox", QComboBox()), gridRow, 1, 1, 2)
        self.containerBox.addItems(self.containerOptions.keys())
        self.containerLabel.setBuddy(self.containerBox)

        gridRow += 1
        self.gridLayout.addWidget(
            self.bind("vcodecLabel", ClickLabel()), gridRow, 0)
        self.gridLayout.addWidget(
            self.bind("vcodecBox", QComboBox()), gridRow, 1, 1, 2)
        self.vcodecBox.addItems(self.containerOptions["mp4"][0])
        self.vcodecLabel.setBuddy(self.vcodecBox)

        gridRow += 1
        self.gridLayout.addWidget(
            self.bind("acodecLabel", ClickLabel()), gridRow, 0)
        self.gridLayout.addWidget(
            self.bind("acodecBox", QComboBox()), gridRow, 1, 1, 2)
        self.acodecBox.addItems(self.containerOptions["mp4"][1])
        self.acodecLabel.setBuddy(self.acodecBox)

        gridRow += 1
        self.gridLayout.addWidget(
            self.bind("abitrateLabel", ClickLabel()), gridRow, 0)
        self.gridLayout.addWidget(
            self.bind("abitrateBox", QLineEdit(validator=QRegularExpressionValidator(QRegularExpression(r"^\d*[1-9]\d*k?$")))), gridRow, 1, 1, 2)
        self.abitrateLabel.setBuddy(self.abitrateBox)

        self.containerBox.currentTextChanged.connect(self.updateCodecs)

        #gridRow += 1
        #self.label_2 = QLabel()
        #self.label_2.setObjectName("label_2")

        #self.gridLayout.addWidget(self.label_2, gridRow, 0)

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
                    "All Files (*)")))
        if result:
            self.filedrop.importFiles(files)

    def offset_check_box(self):
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

    def updateColor(self):
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

    def runConversion(self):
        assOptions = ["-f"]
        width, border = self.aspectRatioOptions[self.aspectRatioBox.currentText()]
        if width != 300:
            assOptions += ["-W", f"{width}"]
        if not border:
            assOptions += ["--no-b"]
        assOptions += ["-F", f"{self.fadeIn.value()},{self.fadeOut.value()}"]
        if self.overrideOffset.checkState() == Qt.Checked:
            assOptions += ["-o", f"{self.offset.value()}"]
        if self.transparencyBox.checkState() != Qt.Checked:
            assOptions += ["--no-t"]
        print(" | ".join(assOptions))
        ffmpegOptions = ""
        # TODO: will use background specified, not default
        ffmpegOptions += f"-f lavfi -i color=color={self.colorText.text()[1:]}:r=60:s={self.resolutionBox.currentText().split(' ')[0]}"
        ffmpegOptions += " -i ADD_AUDIO_FILE_HERE"
        ffmpegOptions += " -vf ass=\"ADD_ASS_FILE_HERE\""
        ffmpegOptions += f" -map 0:v -map 1:a -shortest -c:a {self.acodecBox.currentText()} -b:a {self.abitrateBox.text() or '256k'}"
        ffmpegOptions += " OUTPUT_FILE"
        print(ffmpegOptions)

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
            "MainWindow", "If this is unchecked, the resolution setting is only used for tracks with\nthe background set as a color. If it is checked, background image/video\nis scaled (and letterboxed if the aspect ratio differs) to achieve the\ntarget resolution.", None))
        self.convertButton.setText(QCoreApplication.translate(
            "MainWindow", "&Convert", None))
    # retranslateUi


def run(argv=sys.argv):
    app = QApplication(argv)
    window = Ui_MainWindow()
    window.show()
    sys.exit(app.exec())
