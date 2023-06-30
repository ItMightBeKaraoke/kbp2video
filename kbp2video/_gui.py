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
        print(self.acceptDrops())
        print(self.supportedDropActions())

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
        if data and (result := self.generateFileList(data)):
            found = {"audio": set(), "background": set()}
            # for key, files in list(getattr(result, 'kbp').items()) + list(getattr(result, 'ass').items()):
            # For now, will assume files will be taken through the whole
            # process from kbp to video. Will later support going from .ass
            # file
            for key, files in getattr(result, 'kbp').items():
                table = self.parentWidget().widget(0)
                current = table.rowCount()
                table.setRowCount(current + 1)
                # TODO: handle multiple kbp files under one key
                item = QTableWidgetItem(os.path.basename(files[0]))
                item.setData(Qt.UserRole, files[0])
                item.setToolTip(files[0])
                table.setItem(current, 0, item)
                for filetype, column in (('audio', 1), ('background', 2)):
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

                    # TODO: FIX MISMATCH DUE TO SORT!
                    match_item = QTableWidgetItem(os.path.basename(match[0]))
                    match_item.setData(Qt.UserRole, match[0])
                    match_item.setToolTip(match[0])
                    table.setItem(current, column, match_item)

        else:
            QMessageBox.information(
                self, "No Files Found",
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
                    text="Drop files here")))

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

        self.horizontalLayout.addLayout(
            self.bind("gridLayout", QGridLayout()), stretch=0)

        gridRow = 0
        self.gridLayout.addWidget(self.bind("assDivider", QLabel(
            alignment=Qt.AlignCenter)), gridRow, 0, 1, 3)

        gridRow += 1
        self.gridLayout.addWidget(self.bind("fades", QLabel()), gridRow, 0)
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
        self.gridLayout.addWidget(
            self.bind("aspectLabel", QLabel()), gridRow, 0)
        self.aspectRatioOptions = {
            "CDG, borders (25:18)": (300, True),
            "Wide, borders (16:9)": (384, True),
            "Standard, borders (4:3)": (288, True),
            "CDG no border (3:2)": (288, False),
            "Wide no border (16:9)": (341, False)
        }
        self.gridLayout.addWidget(
            self.bind(
                "aspectRatioBox",
                QComboBox(
                    sizePolicy=QSizePolicy(
                        QSizePolicy.Maximum,
                        QSizePolicy.Maximum))),
            gridRow,
            1,
            1,
            2)
        self.aspectRatioBox.addItems(self.aspectRatioOptions.keys())
        self.aspectLabel.setBuddy(self.aspectRatioBox)

        gridRow += 1
        self.gridLayout.addWidget(self.bind("ffmpegDivider", QLabel(
            alignment=Qt.AlignCenter)), gridRow, 0, 1, 3)

        gridRow += 1
        self.gridLayout.addWidget(self.bind("colorApplyButton", QPushButton(
            clicked=self.color_apply_button)), gridRow, 0)
        self.gridLayout.addWidget(self.bind("colorText", QLineEdit(
            text="#000000", inputMask="\\#HHHHHH")), gridRow, 1)

        # TODO: Find a better way to set this to a reasonable width for 7 characters
        # minimumSizeHint is enough for about 3
        # sizeHint is enough for about 12
        self.colorText.setFixedWidth(
            self.colorText.minimumSizeHint().width() * 7 / 3)

        self.gridLayout.addWidget(self.bind("colorChooseButton", QPushButton(
            clicked=self.color_choose_button)), gridRow, 2)

        gridRow += 1

        self.label_2 = QLabel()
        self.label_2.setObjectName("label_2")

        self.gridLayout.addWidget(self.label_2, gridRow, 0)

        gridRow += 1

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

    def add_row_button(self):
        self.tableWidget.setRowCount(self.tableWidget.rowCount() + 1)

    def retranslateUi(self):
        self.setWindowTitle(QCoreApplication.translate(
            "MainWindow", "KBP to Video", None))
        self.addButton.setText(QCoreApplication.translate(
            "MainWindow", "&Add Files...", None))
        self.colorChooseButton.setText(QCoreApplication.translate(
            "MainWindow", "&Choose...", None))
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
            "MainWindow", "A&dd empty row", None))
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
        self.ffmpegDivider.setText(QCoreApplication.translate(
            "MainWindow", "Video options", None))
        # self.label_2.setText(QCoreApplication.translate(
        #    "MainWindow", "&Second Label", None))
    # retranslateUi


def run(argv=sys.argv):
    app = QApplication(argv)
    window = Ui_MainWindow()
    window.show()
    sys.exit(app.exec())
