#!/usr/bin/env python3
# -*- coding: utf-8 -*-

################################################################################
# Form generated from reading UI file 'testCpPZPi.ui'
##
# Created by: Qt User Interface Compiler version 5.15.9
##
# WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName(u"tableWidget")
        self.setAcceptDrops(True)
        self.setColumnCount(3)
        self.setRowCount(0)
        self.setHorizontalHeaderLabels(["KBP/ASS", "Audio", "Background"])
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.setDragEnabled(False)
        self.setSortingEnabled(True)
        self.setDragDropMode(QAbstractItemView.DropOnly)
        self.setDefaultDropAction(Qt.CopyAction)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        print(self.acceptDrops())
        print(self.supportedDropActions())

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


class FileResultSet(collections.namedtuple('FileResultSet', ('kbp', 'ass', 'audio', 'background'))):
    __slots__ = ()

    def __new__(cls):
        return super().__new__(cls, {}, {}, {}, {})

    def __bool__(self):
        return bool(self.kbp) or bool(self.ass) or bool(self.audio) or bool(self.background)

    def add(self, category, file):
        data = getattr(self, category)
        key = FileResultSet.normalize(file)
        if not key in data:
            data[key] = []
        data[key].append(file)

    def normalize(path):
        path = os.path.splitext(os.path.basename(path))[0]
        path = re.sub('^\w+-\d+|\w+-\d+$|\(Filtered.*|^[\d_]+', '', path)
        return path.casefold().translate(str.maketrans("", "", string.punctuation + string.whitespace))

    def search(self, category, file, fuzziness=0.6):
        data = getattr(self, category)
        key = FileResultSet.normalize(file)
        # TODO: Include more results?
        if result := difflib.get_close_matches(key, data, n=3, cutoff=fuzziness):
            return [files for key in result for files in data[key]]
        else:
            return []

    def all_files(self, category):
        data = getattr(self, category)
        return [files for key, file_list in data.items() for files in file_list]


class DropLabel(QLabel):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName(u"dropLabel")
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

    def generateFileList(self, paths, base_dir='', dir_expand=None, identified=None):
        if identified == None:
            identified = FileResultSet()
        for path in paths:
            path = os.path.join(base_dir, path)
            isdir = os.path.isdir(path)
            if isdir and dir_expand == None:
                result = QMessageBox.question(self, "Import folder?", f"Import entire folder \"{path}\"?", QMessageBox.StandardButtons(
                    QMessageBox.Yes | QMessageBox.YesToAll | QMessageBox.No | QMessageBox.NoToAll))
                if result == QMessageBox.Yes:
                    # TODO: fix rootdir
                    self.generateFileList(glob.iglob(
                        '**', root_dir=path, recursive=True), base_dir=path, dir_expand=True, identified=identified)
                    # Leave dir_expand to prompt next time
                elif result == QMessageBox.NoToAll:
                    dir_expand = False
                elif result == QMessageBox.YesToAll:
                    self.generateFileList(glob.iglob(
                        '**', root_dir=path, recursive=True), base_dir=path, dir_expand=True, identified=identified)
                    dir_expand = True
                # else Leave dir_expand to prompt next time
            if not isdir:
                if filetype := self.identifyFile(path):
                    identified.add(filetype, path)
            elif dir_expand:
                self.generateFileList(glob.iglob(
                    '**', root_dir=path, recursive=True), base_dir=path, dir_expand=True, identified=identified)
        return identified

    def importFiles(self, data):
        if data and (result := self.generateFileList(data)):
            found = {"audio": set(), "background": set()}
            # for key, files in list(getattr(result, 'kbp').items()) + list(getattr(result, 'ass').items()):
            # For now, will assume files will be taken through the whole process from kbp to video. Will later support going from .ass file
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
                    # Also, if there happens to be only one background, assume it's for all the KBPs
                    if not match and (len(result.all_files('kbp')) == 1 or (filetype == 'background' and len(getattr(result, 'background')) == 1)):
                        match = result.all_files(filetype)
                        print(match)
                    if not match:
                        continue

                    print(f"Match found: {match}")

                    if len(match) > 1:
                        choice, ok = QInputDialog.getItem(
                            self, f"Select {filetype} file to use", f"Multiple potential {filetype} files were found for {files[0]}. Please select one, or enter a different path.", match)
                        if ok:
                            match = [choice]
                        else:
                            continue

                    match_item = QTableWidgetItem(os.path.basename(match[0]))
                    match_item.setData(Qt.UserRole, match[0])
                    match_item.setToolTip(match[0])
                    table.setItem(current, column, match_item)

        else:
            QMessageBox.information(
                self, "No Files Found", "No relevant files discovered with provided file list.")

    def dropEvent(self, event):
        mimedata = event.mimeData()
        data = []
        if mimedata.hasUrls():
            data = [x.toDisplayString(QUrl.ComponentFormattingOption(
                QUrl.PreferLocalFile)) for x in mimedata.urls() if x.isLocalFile()]
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
    def __init__(self):
        super().__init__()
        self.setupUi()
    def setupUi(self):
        if not self.objectName():
            self.setObjectName(u"KBP to Video")
        self.resize(886, 664)
        #self.centralwidget = QWidget(MainWindow)
        # self.centralwidget.setObjectName(u"centralwidget")
        #self.horizontalLayoutWidget = QWidget(self.centralwidget)
        self.horizontalLayoutWidget = QWidget(self)
        self.horizontalLayoutWidget.setObjectName(u"horizontalLayoutWidget")
        #self.horizontalLayoutWidget.setGeometry(QRect(0, 0, 791, 561))
        self.horizontalLayout = QHBoxLayout(self.horizontalLayoutWidget)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setSizeConstraint(QLayout.SetDefaultConstraint)
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout = QVBoxLayout()
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setSizeConstraint(QLayout.SetDefaultConstraint)
        self.stackedWidget = QStackedWidget(self.horizontalLayoutWidget)
        self.filedrop = DropLabel(self.stackedWidget)
        self.filedrop.setText("Drop files here")
        self.tableWidget = TrackTable(self.stackedWidget)
        self.stackedWidget.addWidget(self.tableWidget)
        self.stackedWidget.addWidget(self.filedrop)

        # self.verticalLayout.addWidget(self.tableWidget)
        self.verticalLayout.addWidget(self.stackedWidget)

        self.horizontalSpacer = QSpacerItem(
            40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.verticalLayout.addItem(self.horizontalSpacer)

        self.leftPaneButtons = QHBoxLayout()

        self.verticalLayout.addItem(self.leftPaneButtons)

        self.addButton = QPushButton()
        self.addButton.setObjectName(u"pushButton")
        self.addButton.clicked.connect(self.add_files_button)
        self.leftPaneButtons.addWidget(self.addButton)

        self.removeButton = QPushButton()
        self.removeButton.setObjectName(u"removeButton")
        self.removeButton.clicked.connect(self.remove_files_button)
        self.leftPaneButtons.addWidget(self.removeButton)


        self.horizontalLayout.addLayout(self.verticalLayout, stretch=10)

        self.verticalSpacer = QSpacerItem(
            20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.horizontalLayout.addItem(self.verticalSpacer)

        self.gridLayout = QGridLayout()
        self.gridLayout.setObjectName(u"gridLayout")
        self.label = QLabel(self.horizontalLayoutWidget)
        self.label.setObjectName(u"label")

        self.gridLayout.addWidget(self.label, 0, 0)

        self.lineEdit_2 = QLineEdit()
        self.lineEdit_2.setObjectName(u"lineEdit_2")
        self.label.setBuddy(self.lineEdit_2)

        self.gridLayout.addWidget(self.lineEdit_2, 0, 1)

        self.label_2 = QLabel()
        self.label_2.setObjectName(u"label_2")

        self.gridLayout.addWidget(self.label_2, 1, 0)

        self.lineEdit_3 = QLineEdit(self.horizontalLayoutWidget)
        self.lineEdit_3.setObjectName(u"lineEdit_3")
        self.label_2.setBuddy(self.lineEdit_3)

        self.gridLayout.addWidget(self.lineEdit_3, 1, 1)

        self.gridLayout.addItem(QSpacerItem(0,200,vData=QSizePolicy.Minimum), 2, 0, 1, 2)

        self.horizontalLayout.addLayout(self.gridLayout, stretch=5)

        self.setCentralWidget(self.horizontalLayoutWidget)
        self.menubar = QMenuBar(self)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 886, 25))
        self.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(self)
        self.statusbar.setObjectName(u"statusbar")
        self.setStatusBar(self.statusbar)

        self.retranslateUi()

        QMetaObject.connectSlotsByName(self)
    # setupUi

    def add_files_button(self):
        files,result = QFileDialog.getOpenFileNames(self, "Select files to import (either kbp or kbp plus associated files)", filter="All Relevant Files, hopefully (*.kbp *.flac *.wav *.ogg *.opus *.mp3 *.aac *.mp4 *.mkv *.avi *.webm *.mov *.jpg *.jpeg *.png *.gif *.jfif *.jxl *.bmp *.tiff *.webp);;Karaoke Builder Studio Project files (*.kbp);;All Files (*)")
        if result:
            self.filedrop.importFiles(files)

    def remove_files_button(self):
        for row in sorted(set(x.row() for x in self.tableWidget.selectedIndexes()), reverse=True):
            self.tableWidget.removeRow(row)

    def retranslateUi(self):
        self.setWindowTitle(QCoreApplication.translate(
            "MainWindow", u"KBP to Video", None))
        self.addButton.setText(QCoreApplication.translate(
            "MainWindow", u"&Add Files...", None))
        self.removeButton.setText(QCoreApplication.translate(
            "MainWindow", u"&Remove Selected", None))
        self.label.setText(QCoreApplication.translate(
            "MainWindow", u"&First Label", None))
        self.label_2.setText(QCoreApplication.translate(
            "MainWindow", u"&Second Label", None))
    # retranslateUi

def run(argv=sys.argv):
    app = QApplication(argv)
    window = Ui_MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    run(sys.argv)
