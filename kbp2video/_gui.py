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
from .utils import ClickLabel, bool2check, check2bool, mimedb
from .advanced_editor import AdvancedEditor
from .progress_window import ProgressWindow
import ffmpeg
from ._ffmpegcolor import ffmpeg_color
import enum
import kbputils
import io
import shutil
from . import __version__
import traceback
import lastversion

class TrackTableColumn(enum.Enum):
    KBP_ASS = 0
    Audio = 1
    Background = 2
    Advanced = 3

# TODO: Possibly pull PlayRes? from .ass to letterbox
class KBPASSWrapper:
    def __init__(self, path):
        if path.endswith(".ass"):
            self.ass_path = path
            # raise correct exception we would get later from opening
            with open(path, "r") as _:
                pass
        else:
            self.kbp_path = path
            self.kbp_obj = kbputils.KBPFile(path)
    def ass_data(self, **kwargs):
        if hasattr(self,"kbp_path"):
            # Re-read file in case it changed on disk
            self.kbp_obj = kbputils.KBPFile(self.kbp_path)

            tmp = io.StringIO()
            kbputils.AssConverter(self.kbp_obj,**kwargs).ass_document().dump_file(tmp)
            return tmp.getvalue()
        else:
            # Added for symmetry or something, but...
            print("Probably shouldn't reach this code")
            f = QFile(self.ass_path)
            if not f.open(QIODevice.ReadOnly | QIODevice.Text):                                                                                  
                raise IOError(f"Unable to open {self.ass_path}")
            res = QTextStream(f).readAll()
            f.close()
            return res

    def __str__(self):
        return self.kbp_path if hasattr(self,"kbp_path") else self.ass_path


# This should *probably* be redone as a QTableView with a proxy to better
# manage the data and separate it from display
class TrackTable(QTableWidget):

    def __init__(self, **kwargs):
        super().__init__(0, 4, **kwargs)
        self.setObjectName("tableWidget")
        self.setAcceptDrops(True)
        # If this is enabled, user gets stuck in the widget. Arrow keys can still be used to navigate within it
        self.setTabKeyNavigation(False)
        # TODO: update when support for both is included
        # self.setHorizontalHeaderLabels(["KBP/ASS", "Audio", "Background"])
        self.setHorizontalHeaderLabels([x.replace("_", "/") for x in TrackTableColumn.__members__.keys()])
        self.hideColumn(TrackTableColumn.Advanced.value)
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
            return str(res)
        else:
            return item.text()

    def item_filename(self, item):
        if res := item.data(Qt.UserRole):
            return str(res)
        else:
            return item.text()

    def handle_selection_change(self):
        mainWindow = self.parentWidget().parentWidget().parentWidget()
        if self.selectedRanges() == []:
            mainWindow.removeButton.setEnabled(False)
            mainWindow.editButton.setEnabled(False)
            mainWindow.advancedButton.setEnabled(False)
            mainWindow.colorApplyButton.setEnabled(False)
        else:
            mainWindow.removeButton.setEnabled(True)
            mainWindow.editButton.setEnabled(True)
            mainWindow.advancedButton.setEnabled(True)
            mainWindow.colorApplyButton.setEnabled(True)

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
            data[key] = set()
        data[key].add(file)

    # Include both kbp and ass results. If there is any key with both kbp and
    # ass results, keep only the kbp ones (assuming previous work of kbp2video
    # that needs redone)
    def merged_kbp_ass_data(self):
        data = self.ass.copy()
        data.update(self.kbp)
        return data

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
        self.mimedb = mimedb
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("font: bold 50px")

    def identifyFile(self, path):
        if path.casefold().endswith('.kbp'):
            return 'kbp'
        elif path.casefold().endswith('.ass'):
            return 'ass'
        elif path.casefold().endswith('.txt'):
            outfile = os.path.splitext(path)[0] + '.kbp'
            if not os.path.exists(outfile):
                try:
                    kbputils.DoblonTxtConverter(kbputils.doblontxt.DoblonTxt(path), **Ui_MainWindow.doblonsettings).kbpFile().writeFile(outfile)
                except:
                    print(traceback.format_exc())
                    return None
            return ('kbp', outfile)
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
                    # When identifyFile returns a tuple, it is overriding the path
                    if isinstance(filetype, tuple):
                        identified.add(*filetype)
                    else:
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
            for key, files in result.merged_kbp_ass_data().items():
            #for key, files in result.kbp.items():
                # TODO: handle multiple kbp files under one key
                kbpassFile = next(iter(files))
                try:
                    kbpassObj = KBPASSWrapper(kbpassFile)
                except:
                    QMessageBox.information(mainWindow, "Unable to process kbp", f"Failed to process .kbp file\n{kbpassFile}\n\nError Output:\n{traceback.format_exc()}")
                    continue
                table = self.parentWidget().widget(0)
                current = table.rowCount()
                table.setRowCount(current + 1)
                item = QTableWidgetItem(os.path.basename(kbpassFile))
                item.setData(Qt.UserRole, kbpassObj)
                item.setToolTip(kbpassFile)
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemNeverHasChildren)
                table.setItem(current, 0, item)
                #if not (outputdir := mainWindow.outputDir).text():
                #    outputdir.setText(os.path.dirname(kbpFile) + "/kbp2video")
                mainWindow.lastinputdir = os.path.dirname(kbpassFile)

                for filetype, column in (('audio', 1), ('background', 2)):
                    if column == 2 and drop and mainWindow.skipBackgrounds.checkState() == Qt.Checked:
                        continue
                    # Update current in case sort moved it. Needs to be done each time in case one of these columns is the sort field
                    current = table.row(item)
                    match = result.search(filetype, kbpassFile)

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
                            f"Multiple potential {filetype} files were found for {kbpassFile}. Please select one, or enter a different path.",
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

                # Process audio/background options from KBP file
                current = table.row(item)
                if hasattr((k := item.data(Qt.UserRole)), "kbp_obj"):
                    if not table.item(current, TrackTableColumn.Audio.value).text() and (audio := k.kbp_obj.trackinfo["Audio"]):
                        # Audio is either absolute path or relative to kbp
                        audio_path = os.path.join(os.path.dirname(str(k)), audio)
                        audio_item = QTableWidgetItem(os.path.basename(audio_path))
                        audio_item.setData(Qt.UserRole, audio_path)
                        audio_item.setToolTip(audio_path)
                        audio_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemNeverHasChildren)
                        table.setItem(current, TrackTableColumn.Audio.value, audio_item)
                    if not table.item(current, TrackTableColumn.Background.value).text():
                        bg_color = k.kbp_obj.colors.as_rgb24()[0]
                        bg_item = QTableWidgetItem(f"color: #{bg_color}")
                        table.setItem(current, TrackTableColumn.Background.value, bg_item)

        if result.kbp or result.ass:
            # Ui_MainWindow > QWidget > QStackedWidget > DropLabel
            # TODO: Seems like there should be a better way - maybe pass convertButton to constructor
            mainWindow.convertButton.setEnabled(True)
            mainWindow.convertAssButton.setEnabled(True)

        elif result and (table := self.parentWidget().widget(0)).rowCount() > 0:
            # Try to fill in gaps
            # Need the item itself instead of the row due to potential reordering with sorting
            # TODO: figure out what to do if a kbp file is in the list twice - currently it just updates the last one
            data = dict((table.key(row, TrackTableColumn.KBP_ASS.value), table.item(row, TrackTableColumn.KBP_ASS.value)) for row in range(table.rowCount()))
            for filetype, column in (('audio', TrackTableColumn.Audio.value), ('background', TrackTableColumn.Background.value)):
                if column == TrackTableColumn.Background.value and drop and mainWindow.skipBackgrounds.checkState() == Qt.Checked:
                    continue
                for key in getattr(result, filetype):
                    if len(filenames := list(getattr(result, filetype)[key])) > 1:
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

                    if match := dict((table.filename(table.indexFromItem(data[key]).row(), TrackTableColumn.KBP_ASS.value), data[key]) for key in search_results):
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
                            # filetype in audio, background
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
    started = Signal()
    finished = Signal()
    progress = Signal(int, int, str, int, int)
    error = Signal(str, bool)
    data = Signal(dict)

class Converter(QRunnable):
    def __init__(self, function, *args, **kwargs):
        super().__init__()
        self.signals = ConverterSignals()
        self.function = function
        self.signals.cancelled = False #TODO: Seems to work, but is this a good idea?
        self.args = args
        self.kwargs = kwargs

    @Slot()
    def run(self):
        self.function(self.signals, *self.args, **self.kwargs)

class EventFilter(QObject):
    def __init__(self, parent, filter_fn):
        super().__init__(parent)
        self.eventFilter = filter_fn
        

class UpdateBox(QMessageBox):
    def _lastversion_wrap(self, signals):
        try:
            result = {}
            version = lastversion.has_update(repo="ItMightBeKaraoke/kbp2video", at="github", pre_ok=True, current_version=__version__)
            if version:
                result['version'] = version
                result['urls'] = lastversion.latest(repo='ItMightBeKaraoke/kbp2video', pre_ok=True, output_format='assets')
        except:
            result = {'error': traceback.format_exc(limit=2)}
        signals.data.emit(result)

    def __init__(self, parent):
        super().__init__(QMessageBox.Information, "Check for updates", "Checking for updates...", QMessageBox.StandardButton(QMessageBox.Ok), parent=parent)
        self.runner = Converter(self._lastversion_wrap)
        self.runner.signals.data.connect(self._display_data)
        QThreadPool.globalInstance().start(self.runner)
    
    def update_check(parent):
        box = UpdateBox(parent)
        box.exec()

    def _display_data(self, data):
        if 'error' in data:
            self.setWindowTitle("Check for updates: failed!")
            self.setText(f"Failed to check for update:\n{data['error']}")
        elif data:
            self.setWindowTitle("Check for updates: update available!")
            dl_info = ''.join(f'<br>Download <a href="{url}">{url.split("/")[-1]}</a>' for url in data['urls'])
            self.setText(f"New version of kbp2video available ({data['version']})<br>&nbsp;{dl_info}")
        else:
            self.setWindowTitle("Check for updates: kbp2video up to date!")
            self.setText(f"kbp2video current version {__version__} is running")

        

class Ui_MainWindow(QMainWindow):

    RELEVANT_FILE_FILTER = "*." + " *.".join(
        "kbp flac wav ogg opus mp3 aac mp4 mkv avi webm mov mpg mpeg jpg jpeg png gif jfif jxl bmp tiff webp".split())

    def __init__(self, app):
        super().__init__()
        self.app = app
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

        # TODO: Create menubar contents
        self.menubar = QMenuBar()
        self.menubar.setObjectName("menubar")
        #self.menubar.setGeometry(QRect(0, 0, 886, 25))
        self.filemenu = self.menubar.addMenu("File")
        self.filemenu.addAction("&Add/Import Files", Qt.CTRL | Qt.Key_I, self.add_files_button)
        self.filemenu.addAction("&Quit", QKeySequence.Quit, self.app.quit)
        self.editmenu = self.menubar.addMenu("Edit")
        # TODO: Ctrl-A already works, would this be helpful
        #self.editmenu.addAction("&Select All", self.select_all)
        self.editmenu.addAction("&Remove Selected", QKeySequence.Delete, self.remove_files_button)
        self.editmenu.addAction("&Add empty row", self.add_row_button)
        self.editmenu.addAction("&Open/Edit Selected Files", QKeySequence.Open, self.remove_files_button)
        self.editmenu.addAction("&Intro/Outro Settings", Qt.CTRL | Qt.Key_Return, self.advanced_button)
        self.helpmenu = self.menubar.addMenu("Help")
        self.helpmenu.addAction("&About", lambda: QMessageBox.about(self, "About kbp2video", f"kbp2video version: {__version__}\n\nUsing:\nkbputils version: {kbputils.__version__}\nffmpeg version: {ffmpeg_version}"))
        self.helpmenu.addAction("&Check for Updates...", lambda: UpdateBox.update_check(self))
        self.setMenuBar(self.menubar)

        self.setStatusBar(self.bind("statusbar", QStatusBar(self)))

        # No point in updating the status bar with empty messages
        self.installEventFilter(EventFilter(self, lambda obj, event: True if event.type() == QEvent.StatusTip and not event.tip() else False))

        try:
            q = QProcess(program="ffmpeg", arguments=["-version"])
            q.start()
            q.waitForFinished(1000)
            q.setReadChannel(QProcess.StandardOutput)
            version_line = q.readLine().toStdString().split()
            ffmpeg_version = version_line[i+1] if (i := version_line.index("version")) else 'UNKNOWN'
        except:
            ffmpeg_version = "MISSING/UNKNOWN"
        self.statusbar.showMessage(f"kbp2video {__version__} (kbputils {kbputils.__version__}, ffmpeg {ffmpeg_version})")

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

        self.leftPaneButtons.addWidget(
            self.bind(
                "editButton", QPushButton(
                    clicked=self.edit_button,
                    enabled=False))) 

        self.leftPaneButtons.addWidget(
            self.bind(
                "advancedButton", QPushButton(
                    clicked=self.advanced_button,
                    enabled=False))) 

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
        self.aspectRatioOptions = [
            "CDG, borders (25:18, True)",
            "Wide, borders (16:9, True)",
            "Standard, borders (4:3, True)",
            "CDG no border (3:2, False)",
            "Wide no border (16:9, False)",
        ]
        self.gridLayout.addWidget(
            self.bind("aspectLabel", ClickLabel()), gridRow, 0)
        self.gridLayout.addWidget(
            self.bind("aspectRatioBox",QComboBox(editable=True, insertPolicy=QComboBox.NoInsert)),gridRow, 1, 1, 2)
                    # sizePolicy=QSizePolicy(
                    #     QSizePolicy.Maximum,
                    #     QSizePolicy.Maximum))),
        self.aspectRatioBox.addItems(self.aspectRatioOptions)
        self.aspectLabel.setBuddy(self.aspectRatioBox)
        #self.aspectRatioBox.setCurrentIndex(self.settings.value("subtitle/aspect_ratio_index", type=int, defaultValue=0))

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
                    #value=self.settings.value("subtitle/fade_in", type=int, defaultValue=50),
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
                    #value=self.settings.value("subtitle/fade_out", type=int, defaultValue=50),
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
                    #value=self.settings.value("subtitle/offset", type=float, defaultValue=0.0),
                    enabled=False
                    )),
            gridRow,
            1)
        self.gridLayout.addWidget(self.bind("offsetLabel", ClickLabel(buddy=self.offset)), gridRow, 0)

        #self.offset_check_box(setState=Qt.Checked if self.settings.value("subtitle/override_offset", type=bool, defaultValue=False) else Qt.Unchecked)

        gridRow += 1
        #self.gridLayout.addWidget(self.bind("transparencyBox", QCheckBox(checkState=Qt.Checked if self.settings.value("subtitle/transparent_bg", type=bool, defaultValue=True) else Qt.Unchecked)), gridRow, 0, alignment=Qt.AlignRight)
        self.gridLayout.addWidget(self.bind("transparencyBox", QCheckBox()), gridRow, 0, alignment=Qt.AlignRight)
        self.gridLayout.addWidget(self.bind("transparencyLabel", ClickLabel(buddy=self.transparencyBox, buddyMethod=QCheckBox.toggle)), gridRow, 1, 1, 2)

        gridRow += 1
        self.gridLayout.addWidget(self.bind("ktBox", QCheckBox()), gridRow, 0, alignment=Qt.AlignRight)
        self.gridLayout.addWidget(self.bind("ktLabel", ClickLabel(buddy=self.ktBox, buddyMethod=QCheckBox.toggle)), gridRow, 1, 1, 2)

        gridRow += 1
        self.gridLayout.addWidget(self.bind("spacingBox", QCheckBox()), gridRow, 0, alignment=Qt.AlignRight)
        self.gridLayout.addWidget(self.bind("spacingLabel", ClickLabel(buddy=self.spacingBox, buddyMethod=QCheckBox.toggle)), gridRow, 1, 1, 2)

        gridRow += 1
        self.gridLayout.addWidget(
            self.bind("overflowBox", QComboBox()), gridRow, 1, 1, 2)
        self.gridLayout.addWidget(
            self.bind("overflowLabel", ClickLabel(buddy=self.overflowBox)), gridRow, 0)
        self.overflowBox.addItems(["no wrap","even split","top split","bottom split"])

        gridRow += 1
        self.gridLayout.addItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding), gridRow, 0, 1, 3)
        self.gridLayout.setRowStretch(gridRow, 10)

        gridRow += 1
        self.gridLayout.addWidget(self.bind("ffmpegDivider", ClickLabel(
            alignment=Qt.AlignCenter)), gridRow, 0, 1, 3)

        gridRow += 1
        self.gridLayout.addWidget(self.bind("colorApplyButton", QPushButton(
            clicked=self.color_apply_button, enabled=False)), gridRow, 0)
        self.gridLayout.addWidget(self.bind("colorText", QLineEdit(
            text="#000000", inputMask="\\#HHHHHH", styleSheet="color: #FFFFFF; background-color: #000000", textChanged=self.updateColor)), gridRow, 1)

        #self.updateColor(setColor=self.settings.value("video/background_color", type=str, defaultValue="#000000"))

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
            self.bind("resolutionBox", QComboBox(editable=True)), gridRow, 1, 1, 2)
        self.resolutionBox.addItems(self.resolutionOptions)
        #self.resolutionBox.setCurrentIndex(self.settings.value("video/output_resolution_index", type=int, defaultValue=0))
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
        #self.containerBox.setCurrentIndex(self.settings.value("video/container_format_index", type=int, defaultValue=0))
        self.containerLabel.setBuddy(self.containerBox)

        gridRow += 1
        self.gridLayout.addWidget(
            self.bind("vcodecLabel", ClickLabel()), gridRow, 0)
        self.gridLayout.addWidget(
            self.bind("vcodecBox", QComboBox()), gridRow, 1, 1, 2)
        #self.vcodecBox.setCurrentIndex(self.settings.value("video/video_codec_index", type=int, defaultValue=0))
        #self.vcodecBox.addItems(self.containerOptions[self.containerBox.currentText()][0])
        self.vcodecLabel.setBuddy(self.vcodecBox)

        gridRow += 1
        # TODO: implement feature
        self.gridLayout.addWidget(self.bind("lossless", QCheckBox(stateChanged=self.lossless_check_box)), gridRow, 0, alignment=Qt.AlignRight)
        #self.gridLayout.addWidget(self.bind("lossless", QCheckBox(checkState=Qt.Checked if self.settings.value("video/lossless", type=bool, defaultValue=False) else Qt.Unchecked)), gridRow, 0, alignment=Qt.AlignRight)
        self.gridLayout.addWidget(self.bind("losslessLabel", ClickLabel(buddy=self.lossless, buddyMethod=QCheckBox.toggle)), gridRow, 1, 1, 2)

        gridRow += 1
        self.gridLayout.addWidget(
            self.bind("qualityLabel", ClickLabel()), gridRow, 0)
        self.gridLayout.addWidget(
            self.bind("quality", QSlider(Qt.Horizontal, minimum=10, maximum=40, invertedAppearance=True, invertedControls=True, tickInterval=5, pageStep=5, tickPosition=QSlider.TicksAbove)), gridRow, 1, 1, 2)
        self.qualityLabel.setBuddy(self.quality)

        gridRow += 1
        self.gridLayout.addWidget(
            self.bind("acodecLabel", ClickLabel()), gridRow, 0)
        self.gridLayout.addWidget(
            self.bind("acodecBox", QComboBox()), gridRow, 1, 1, 2)
        self.acodecBox.addItems(self.containerOptions[self.containerBox.currentText()][1])
        #self.acodecBox.setCurrentIndex(self.settings.value("video/audio_codec_index", type=int, defaultValue=0))
        self.acodecLabel.setBuddy(self.acodecBox)

        gridRow += 1
        self.gridLayout.addWidget(
            self.bind("abitrateLabel", ClickLabel()), gridRow, 0)
        #self.gridLayout.addWidget(
        #    self.bind("abitrateBox", QLineEdit(validator=QRegularExpressionValidator(QRegularExpression(r"^\d*[1-9]\d*k?$")), text=self.settings.value("video/audio_bitrate", type=str, defaultValue=""))), gridRow, 1, 1, 2)
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
        self.gridLayout.setRowStretch(gridRow, 10)

        gridRow += 1
        self.gridLayout.addWidget(self.bind("generalDivider", ClickLabel(
            alignment=Qt.AlignCenter)), gridRow, 0, 1, 3)

        gridRow += 1
        # TODO: implement feature
        self.gridLayout.addWidget(self.bind("relative", QCheckBox(stateChanged=self.relative_check_box)), gridRow, 0, alignment=Qt.AlignRight)
        self.gridLayout.addWidget(self.bind("relativeLabel", ClickLabel(buddy=self.relative, buddyMethod=QCheckBox.toggle)), gridRow, 1, 1, 2)

        gridRow += 1
        self.gridLayout.addWidget(
            self.bind("outputDirLabel", ClickLabel()), gridRow, 0)
        self.gridLayout.addWidget(
            self.bind("outputDir", QLineEdit()), gridRow, 1)
        self.gridLayout.addWidget(
            self.bind("outputDirButton", QPushButton(clicked=self.output_dir)), gridRow, 2)
        self.outputDirLabel.setBuddy(self.outputDir)

        gridRow += 1
        #self.gridLayout.addWidget(self.bind("skipBackgrounds", QCheckBox(checkState=Qt.Checked if self.settings.value("video/ignore_bg_files_drag_drop", type=bool, defaultValue=False) else Qt.Unchecked)), gridRow, 0, alignment=Qt.AlignRight)
        self.gridLayout.addWidget(self.bind("skipBackgrounds", QCheckBox()), gridRow, 0, alignment=Qt.AlignRight)
        self.gridLayout.addWidget(self.bind("skipBackgroundsLabel", ClickLabel(buddy=self.skipBackgrounds, buddyMethod=QCheckBox.toggle)), gridRow, 1, 1, 2)

        gridRow += 1
        self.gridLayout.addItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding), gridRow, 0, 1, 3)
        self.gridLayout.setRowStretch(gridRow, 10)

        gridRow += 1
        self.gridLayout.addWidget(
            self.bind("resetButton", QPushButton(clicked=self.reset_settings, sizePolicy=QSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum))), gridRow, 0, 1, 3, alignment=Qt.AlignCenter)

        gridRow += 1
        self.gridLayout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding), gridRow, 0, 1, 3)
        self.gridLayout.setRowStretch(gridRow, 30)

        gridRow += 1
        self.gridLayout.addWidget(
            self.bind("convertAssButton", QPushButton(enabled=False, clicked=self.runAssConversion)), gridRow, 0, 1, 1)
        self.gridLayout.addWidget(
            self.bind("convertButton", QPushButton(enabled=False, clicked=self.runConversion)), gridRow, 1, 1, 2)

        self.horizontalLayout.addItem(QSpacerItem(
            20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        self.loadSettings()

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
        if check2bool(self.overrideOffset):
            self.offset.setEnabled(True)
        else:
            self.offset.setEnabled(False)

    def lossless_check_box(self, *_ignored, setState=None):
        if setState != None:
            self.quality.setCheckState(setState)
        if not check2bool(self.lossless):
            self.quality.setEnabled(True)
        else:
            self.quality.setEnabled(False)

    def relative_check_box(self, *_ignored, setState=None):
        pass
        # if setState != None:
        #     self.quality.setCheckState(setState)
        # if self.lossless.checkState() == Qt.Unchecked:
        #     self.quality.setEnabled(True)
        # else:
        #     self.quality.setEnabled(False)

    def reset_settings(self):
        if QMessageBox.Yes == QMessageBox.question(self, "Reset Settings?", "Reset all settings above back to their defaults?"):
            self.settings.clear()
            self.loadSettings()

    def color_apply_button(self):
        for row in sorted(
                set(x.row() for x in self.tableWidget.selectedIndexes()),
                reverse=True):
            if self.tableWidget.item(row, TrackTableColumn.Background.value).text():
                result = QMessageBox.question(
                    self.parentWidget(),
                    "Overwrite background fields?",
                    f"Replace any existing background files or colors of the selected files with color {self.colorText.text()}?")
                if result == QMessageBox.Yes:
                    break
                else:
                    return

        for row in sorted(
                set(x.row() for x in self.tableWidget.selectedIndexes()),
                reverse=True):
            self.tableWidget.setItem(row, TrackTableColumn.Background.value, QTableWidgetItem(
                f"color: {self.colorText.text()}"))

    def advanced_button(self):
        if self.tableWidget.selectedIndexes():
            AdvancedEditor.showAdvancedEditor(self.tableWidget)

    def edit_button(self):
        rows = set(x.row() for x in self.tableWidget.selectedIndexes())
        if len(rows) == 1 or QMessageBox.question(self, f"Open {len(rows)} files?", f"Are you sure you want to open {len(rows)} files at the same time?") == QMessageBox.Yes:
            for row in rows:
                QDesktopServices.openUrl(QUrl.fromLocalFile(self.tableWidget.filename(row, TrackTableColumn.KBP_ASS.value)))

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
            self.convertAssButton.setEnabled(False)

    def add_row_button(self):
        self.tableWidget.setRowCount(self.tableWidget.rowCount() + 1)
        self.convertButton.setEnabled(True)
        self.convertAssButton.setEnabled(True)

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
            if check2bool(self.relative):
                if self.lastinputdir:
                    self.outputDir.setText(os.path.relpath(outputdir, self.lastinputdir))
                else:
                    # Ok, now we're in murky territory, just pick something possibly correct
                    self.outputDir.setText(os.path.basename(outputdir))
            else:
                self.outputDir.setText(outputdir)

    def saveSettings(self):
        to_save = {
            "subtitle/aspect_ratio": self.aspectRatioBox.currentText(),
            "subtitle/fade_in": self.fadeIn.value(),
            "subtitle/fade_out": self.fadeOut.value(),
            "subtitle/offset": self.offset.value(),
            "subtitle/override_offset": check2bool(self.overrideOffset),
            "subtitle/transparent_bg": check2bool(self.transparencyBox),
            "subtitle/allow_kt": check2bool(self.ktBox),
            "subtitle/style1_spacing": check2bool(self.spacingBox),
            "subtitle/overflow": self.overflowBox.currentText(),
            "video/background_color": self.colorText.text(),
            "video/output_resolution": self.resolutionBox.currentText(),
            "video/override_bg_resolution": check2bool(self.overrideBGResolution),
            "video/container_format_index": self.containerBox.currentIndex(),
            "video/video_codec_index": self.vcodecBox.currentIndex(),
            "video/lossless": check2bool(self.lossless),
            "video/quality": self.quality.value(),
            "video/audio_codec_index": self.acodecBox.currentIndex(),
            "video/audio_bitrate": self.abitrateBox.text(),
            "kbp2video/relative_path": check2bool(self.relative),
            "kbp2video/output_dir": self.outputDir.text(),
            "kbp2video/ignore_bg_files_drag_drop": check2bool(self.skipBackgrounds),
            **{"doblontxt/" + x: Ui_MainWindow.doblonsettings[x] for x in Ui_MainWindow.doblonsettings},
        }
        for setting, value in to_save.items():
            self.settings.setValue(setting, value)
        self.settings.sync()

    def loadSettings(self):
        # legacy options
        self.aspectRatioBox.setCurrentIndex(self.settings.value("subtitle/aspect_ratio_index", type=int, defaultValue=0))
        self.settings.remove("subtitle/aspect_ratio_index")
        self.overrideBGResolution.setCheckState(bool2check(self.settings.value("overrideBGResolution", type=bool, defaultValue=False)))
        self.settings.remove("overrideBGResolution")
        self.resolutionBox.setCurrentIndex(self.settings.value("video/output_resolution_index", type=int, defaultValue=0))
        self.settings.remove("video/output_resolution_index")

        # Restore existing or custom option
        aspect_text = self.settings.value("subtitle/aspect_ratio", type=str, defaultValue="<NONEXISTENT>")
        if (index := self.aspectRatioBox.findText(aspect_text)) != -1:
            self.aspectRatioBox.setCurrentIndex(index)
        elif aspect_text != "<NONEXISTENT>":
            self.aspectRatioBox.setCurrentText(aspect_text)

        self.fadeIn.setValue(self.settings.value("subtitle/fade_in", type=int, defaultValue=50))
        self.fadeOut.setValue(self.settings.value("subtitle/fade_out", type=int, defaultValue=50))
        self.offset.setValue(self.settings.value("subtitle/offset", type=float, defaultValue=0.0))
        self.offset_check_box(setState=bool2check(self.settings.value("subtitle/override_offset", type=bool, defaultValue=False)))
        self.transparencyBox.setCheckState(bool2check(self.settings.value("subtitle/transparent_bg", type=bool, defaultValue=True)))
        self.ktBox.setCheckState(bool2check(self.settings.value("subtitle/allow_kt", type=bool, defaultValue=False)))
        self.spacingBox.setCheckState(bool2check(self.settings.value("subtitle/style1_spacing", type=bool, defaultValue=False)))
        self.overflowBox.setCurrentText(self.settings.value("subtitle/overflow", type=str, defaultValue="no wrap"))
        self.updateColor(setColor=self.settings.value("video/background_color", type=str, defaultValue="#000000"))

        # Restore existing or custom option
        resolution_text = self.settings.value("video/output_resolution", type=str, defaultValue="<NONEXISTENT>")
        if (index := self.resolutionBox.findText(resolution_text)) != -1:
            self.resolutionBox.setCurrentIndex(index)
        elif resolution_text != "<NONEXISTENT>":
            self.resolutionBox.setCurrentText(resolution_text)

        self.overrideBGResolution.setCheckState(bool2check(self.settings.value("video/override_bg_resolution", type=bool, defaultValue=False)))
        self.containerBox.setCurrentIndex(self.settings.value("video/container_format_index", type=int, defaultValue=0))
        self.updateCodecs()
        self.vcodecBox.setCurrentIndex(self.settings.value("video/video_codec_index", type=int, defaultValue=0))
        self.lossless.setCheckState(bool2check(self.settings.value("video/lossless", type=bool, defaultValue=False)))
        self.quality.setValue(self.settings.value("video/quality", type=int, defaultValue=23))
        self.acodecBox.setCurrentIndex(self.settings.value("video/audio_codec_index", type=int, defaultValue=0))
        self.abitrateBox.setText(self.settings.value("video/audio_bitrate", type=str, defaultValue=""))
        self.relative.setCheckState(bool2check(self.settings.value("kbp2video/relative_path", type=bool, defaultValue=True)))
        self.outputDir.setText(self.settings.value("kbp2video/output_dir", type=str, defaultValue="kbp2video"))
        self.skipBackgrounds.setCheckState(bool2check(self.settings.value("kbp2video/ignore_bg_files_drag_drop", type=bool, defaultValue=False)))
        Ui_MainWindow.doblonsettings = {
            "max_lines_per_page": 6,
            "min_gap_for_new_page": 1000,
            "display_before_wipe": 1000,
            "remove_after_wipe": 500,
            "template_file": '',
            "comments": 'Created with kbputils\nConverted from Doblon .txt file'
        }
        for x in Ui_MainWindow.doblonsettings:
            val = Ui_MainWindow.doblonsettings[x]
            Ui_MainWindow.doblonsettings[x] = self.settings.value("doblontxt/" + x, type=type(val), defaultValue=val)
        self.saveSettings()  # Save to disk any new defaults that were used

    def runAssConversion(self):
        self.saveSettings()
        converter = Converter(self.conversion_runner, assOnly = True)
        # worker.signals.finished.connect
        QThreadPool.globalInstance().start(converter)

    def runConversion(self):
        self.saveSettings()
        converter = Converter(self.conversion_runner)
        # worker.signals.finished.connect
        QThreadPool.globalInstance().start(converter)
        if not ProgressWindow.showProgressWindow(self.tableWidget.rowCount(), converter.signals, self):
            converter.signals.cancelled = True

    def resolved_output_dir(self, kbp):
        if check2bool(self.relative):

            # If relative is set, assume .ass dir is the output dir because we
            # no longer know the project file
            if kbp.endswith(".ass"):
                return os.path.dirname(kbp)
            else:
                # TODO: check if self.outputDir starts with a slash? Otherwise it behaves like an absolute path
                return os.path.join(os.path.dirname(kbp), self.outputDir.text())
        else:
            return self.outputDir.text()
    
    def assFile(self, kbp):
        filename = os.path.basename(kbp)
        # This REALLY needs to be set...
        while not check2bool(self.relative) and not self.outputDir.text():
            self.output_dir()
        return self.resolved_output_dir(kbp) + "/" + filename[:-4].translate(str.maketrans("","",":;,'=\"")) + ".ass"
    
    def vidFile(self, kbp):
        filename = os.path.basename(kbp)
        return self.resolved_output_dir(kbp) + "/" + filename[:-4] + "." + self.containerBox.currentText()

    def audioffmpegBitrate(self):
        if self.acodecBox.currentText() == 'flac':
            return {}
        # TODO: Good defaults based on format
        else:
            return {"audio_bitrate": self.abitrateBox.text() or '256k'}

    def get_aspect_ratio(self):
        text = self.aspectRatioBox.currentText()
        if (res := re.search(r'\((.*)\)', text)):
            text = res.group(1)
        ratio, border = (x.strip() for x in text.partition(",")[0:3:2])
        if border.upper() == "TRUE" or border == "":
            border = True
        elif border.upper() == "FALSE":
            border = False
        else:
            border = None
        ratio = list(ratio.partition(":")[0:3:2])
        for n, i in enumerate(ratio):
            try:
                ratio[n] = int(i.strip())
            except ValueError:
                ratio[n] = None
        return (ratio, border)
       

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

    def conversion_runner(self, signals, assOnly = False):
        signals.started.emit()
        unsupported_message = False
        kbputils_options = {}
        ratio, border = self.get_aspect_ratio()
        if ratio[0] is None or border is None:
            QMetaObject.invokeMethod(
                self,
                'info', 
                Qt.AutoConnection,
                Q_ARG(str, "Invalid Aspect Ratio setting"),
                Q_ARG(str, f"Invalid Aspect Ratio setting\nPlease choose from the available options or follow the format in parens if you set a custom value."))
            return
        if ratio[1] is None:
            ratio[1] = 216
        resolution = self.resolutionBox.currentText().split()[0]
        if len(tmp := resolution.split("x")) != 2 or any(not re.match(r'\d+$', x) for x in tmp):
            QMetaObject.invokeMethod(
                self,
                'info', 
                Qt.AutoConnection,
                Q_ARG(str, "Invalid Resolution setting"),
                Q_ARG(str, f"Invalid Resolution setting\nPlease choose from the available options or enter a width and height separated by x."))
            return
        tmp = [int(x) for x in tmp]
        if tmp[1] * ratio[0] / ratio[1] >= tmp[0]:
            kbputils_options['target_x'] = tmp[0]
            kbputils_options['target_y'] = int(tmp[0] * ratio[1] / ratio[0])
        else:
            kbputils_options['target_y'] = tmp[1]
            kbputils_options['target_x'] = int(tmp[1] * ratio[0] / ratio[1])
        width = round((216 if border else 192) * ratio[0] / ratio[1])
        default_bg = self.colorText.text().strip(" #")
        if not border:
            kbputils_options['border'] = False
        kbputils_options['fade_in'] = self.fadeIn.value()
        kbputils_options['fade_out'] = self.fadeOut.value()
        if self.overrideOffset.checkState() == Qt.Checked:
            kbputils_options['offset'] = self.offset.value()
        if self.transparencyBox.checkState() != Qt.Checked:
            kbputils_options['transparency'] = False
        if self.ktBox.checkState() == Qt.Checked:
            kbputils_options['allow_kt'] = True
        if self.spacingBox.checkState() == Qt.Checked:
            kbputils_options['experimental_spacing'] = True
        kbputils_options['overflow'] = kbputils.AssOverflow[self.overflowBox.currentText().replace(" ", "_").upper()]
        conversion_errors = False
        ffmpeg_processes = []
        for row in range(self.tableWidget.rowCount()):
            kbp_table_item = self.tableWidget.item(row, TrackTableColumn.KBP_ASS.value)
            kbp_obj = kbp_table_item.data(Qt.UserRole) or kbp_table_item.text()
            kbp = str(kbp_obj)
            audio = self.tableWidget.filename(row, TrackTableColumn.Audio.value)
            background = self.tableWidget.filename(row, TrackTableColumn.Background.value)
            advanced = self.tableWidget.item(row, TrackTableColumn.Advanced.value).data(Qt.UserRole) or {}
            print(f"Retrieved Advanced settings for {kbp}:")
            print(advanced)
            if not kbp:
                continue
            self.statusbar.showMessage(f"Converting file {row+1} of {self.tableWidget.rowCount()} ({kbp})")
            signals.progress.emit(row, self.tableWidget.rowCount(), kbp, 0, 0)
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

            assfile = self.assFile(kbp)

            # Handle manually-typed filename. TODO: convert earlier, when the text value is updated
            if not isinstance(kbp_obj, KBPASSWrapper):
                try:
                    kbp_obj = KBPASSWrapper(kbp_obj)
                except:
                    conversion_errors = True
                    #QMetaObject.invokeMethod(
                    #    self,
                    #    'info', 
                    #    Qt.AutoConnection,
                    #    Q_ARG(str, "Failed to process file"),
                    #    Q_ARG(str, f"Failed to process file\n{kbp}\n\nError Output:\n{traceback.format_exc()}"))
                    signals.error.emit(f"Failed to process file\n{kbp}\n\nError Output:\n{traceback.format_exc()}", True)
                    continue
            if hasattr(kbp_obj, "kbp_path"):
                print("Converting the new way")
                print(kbputils_options)
                try:
                    data = kbp_obj.ass_data(**kbputils_options)
                except:
                    conversion_errors = True
                    #QMetaObject.invokeMethod(
                    #    self,
                    #    'info', 
                    #    Qt.AutoConnection,
                    #    Q_ARG(str, "Failed to process kbp"),
                    #    Q_ARG(str, f"Failed to process .kbp file\n{kbp}\n\nError Output:\n{traceback.format_exc()}"))
                    signals.error.emit(f"Failed to process .kbp file\n{kbp}\n\nError Output:\n{traceback.format_exc()}", True)
                    continue
            else: # kbp_obj is a KBPASSWrapper with a .ass file
                if any(x in kbp for x in ":;,'=\""):
                    print("Already .ass file, but needs new filename for ffmpeg")
                    QFile(kbp).copy(assfile)
                else:
                    print("Using existing .ass file")
                    assfile = kbp
                    
            # QDir is inconsistent. Needs to be static to check existence, and
            # mkdir needs to be run from an instantiated instance in the parent
            # directory, not worth the hassle
            if not os.path.isdir(outdir := self.resolved_output_dir(kbp)):
                try:
                    os.mkdir(outdir)
                except:
                    conversion_errors = True
                    #QMetaObject.invokeMethod(
                    #    self,
                    #    'info', 
                    #    Qt.AutoConnection,
                    #    Q_ARG(str, "Failed to create output folder"),
                    #    Q_ARG(str, f"Failed to create missing output folder\n{outdir}\n\nError Output:\n{traceback.format_exc()}"))
                    signals.error.emit(f"Failed to create output folder\n{outdir}\nassociated with .kbp file\n{kbp}\n\nError Output:\n{traceback.format_exc()}", True)
                    continue

            # File was converted and .ass file needs to be written
            if kbp.endswith(".kbp"):
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
                        signals.error.emit(f"Skipped {kbp} per user request (.ass file exists)", True)
                        continue
                if not f.open(QIODevice.WriteOnly | QIODevice.Text):
                    continue
                out = QTextStream(f)
                out << data
                f.close()
                if assOnly:
                    kbp_table_item.setData(Qt.UserRole, KBPASSWrapper(assfile))
                    kbp_table_item.setText(os.path.basename(assfile))
                    kbp_table_item.setToolTip(assfile)
                    kbp_table_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemNeverHasChildren)

            if assOnly:
                continue

            output_options = {}
            base_assfile = os.path.basename(assfile)
            if background_type == 0:
                background_video = ffmpeg.input(f"color=color={background}:r=60:s={resolution}", f="lavfi")
                bg_size = QSize(*(int(x) for x in resolution.split('x')))
            elif background_type == 1:
                bg_size = QImage(background).size()
                background_video = ffmpeg.input(background, loop=1, framerate=60)
            elif background_type == 2:
                # Pull the dimensions of the first video stream found in the file
                try:
                    bginfo = ffmpeg.probe(background)
                except:
                    conversion_errors = True
                    #QMetaObject.invokeMethod(
                    #    self,
                    #    'info',
                    #    Qt.AutoConnection,
                    #    Q_ARG(str, "Unable to process background video"),
                    #    Q_ARG(str, f"Unable to determine the resolution of file\n{background}\n{traceback.format_exc()}"))
                    signals.error.emit(f"Skipped {kbp}:\nUnable to determine the resolution of background file\n{background}\n{traceback.format_exc()}", True)
                    continue
                bg_size = next(QSize(x['width'],x['height']) for x in bginfo['streams'] if x['codec_type'] == 'video')
                background_video = ffmpeg.input(background).video

            try:
                song_length = ffmpeg.probe(audio)['format']['duration']
                song_length_float = float(song_length)
            except:
                conversion_errors = True
                #QMetaObject.invokeMethod(
                #    self,
                #    'info',
                #    Qt.AutoConnection,
                #    Q_ARG(str, "Unable to process audio"),
                #    Q_ARG(str, f"Unable to process audio file\n{audio}\n{traceback.format_exc()}"))
                signals.error.emit(f"Skipped {kbp}:\nUnable to process audio file\n{audio}\n{traceback.format_exc()}", True)
                continue
            song_length_us = int(song_length_float * 1e6)
            # TODO figure out time/frame for outro
            for x in ("intro", "outro"):
                if f"{x}_enable" in advanced and advanced[f"{x}_enable"]:
                    # TODO: alpha, sound?
                    opts = {}
                    if self.filedrop.mimedb.mimeTypeForFile(advanced[f"{x}_file"]).name().startswith('image/'):
                        opts["loop"]=1
                        opts["framerate"]=60
                    # TODO skip scale if matching?
                    # TODO set x/y if mismatched aspect ratio?
                    overlay = ffmpeg.input(advanced[f"{x}_file"], t=advanced[f"{x}_length"], **opts).filter_(
                        "scale", s=f"{bg_size.width()}x{bg_size.height()}")
                    if x == "outro":
                        #leadin = ffmpeg_color("000000", s=f"{bg_size.width()}x{bg_size.height()}", r=60, d=(float(song_length) - float(advanced[f"{x}_length"].split(":")[1]))).filter_("format", "rgba")
                        leadin = ffmpeg.input(f"color=color=000000:r=60:s={bg_size.width()}x{bg_size.height()}", f="lavfi", t=(song_length_float - float(advanced[f"{x}_length"].split(":")[1])))
                        overlay = leadin.concat(overlay)
                    for y in ("In", "Out"):
                        if float(advanced[f"{x}_fade{y}"].split(":")[1]):
                            # TODO: minutes
                            fade_settings = {}
                            print(advanced[f"{x}_black"])
                            if not advanced[f"{x}_black"] or (x, y) == ("intro", "Out") or (x, y) == ("outro", "In"):
                                fade_settings["alpha"] = 1
                            if x == "intro":
                                if y == "In":
                                    fade_settings["st"] = 0
                                else:
                                    fade_settings["st"] = float(advanced[f"{x}_length"].split(":")[1]) - float(advanced[f"{x}_fadeOut"].split(":")[1])
                            else:
                                if y == "Out":
                                    fade_settings["st"] = song_length_float - float(advanced[f"{x}_fadeOut"].split(":")[1])
                                else:
                                    fade_settings["st"] = song_length_float - float(advanced[f"{x}_length"].split(":")[1])
                            overlay = overlay.filter_("fade", t=y.lower(), d=advanced[f"{x}_fade{y}"].split(":")[1], **fade_settings)
                    background_video = background_video.overlay(overlay, eof_action=("pass" if x == "intro" else "repeat"))

            audio_stream = ffmpeg.input(audio).audio
            if background_type == 1 or background_type == 2:
                if not bg_size:
                    #QMetaObject.invokeMethod(
                    #    self,
                    #    'info',
                    #    Qt.AutoConnection,
                    #    Q_ARG(str, "Unsupported Background file"),
                    #    Q_ARG(str, f"Unable to determine the resolution of file\n{background}"))
                    signals.error.emit(f"Skipped {kbp}:\nUnable to determine the resolution of background file\n{background}\n{traceback.format_exc()}", True)
                    continue
                if self.overrideBGResolution.checkState == Qt.Checked and not unsupported_message:
                    #QMetaObject.invokeMethod(
                    #    self,
                    #    'info',
                    #    Qt.AutoConnection,
                    #    Q_ARG(str, "Unsupported Option"),
                    #    Q_ARG(str, f"Override background resolution option not supported yet!"))
                    signals.error.emit(f"Unsupported option Override Background selected, ignoring", False)
                    unsupported_message = True

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
                filtered_video = background_video.overlay(
                    ffmpeg_color(color="000000@0", r=60, s=f"{ass_size.width()}x{ass_size.height()}")
                        .filter_("format", "rgba")
                        .filter_("ass", base_assfile, alpha=1),
                    eof_action="pass",
                    **ass_move
                )
            else:
                filtered_video = background_video.filter_("ass", base_assfile)
            if background_type == 0 or background_type == 1:
                output_options["shortest"] = None
            # TODO: should pix_fmt be configurable or change default based on codec?
            output_options.update(self.audioffmpegBitrate())

            if check2bool(self.lossless):
                if self.vcodecBox.currentText() == "libvpx-vp9":
                    output_options["lossless"]=1
                elif self.vcodecBox.currentText() == "libx265":
                    output_options["x265-params"]="lossless=1"
                else:
                    output_options["crf"]=0
            else:
                output_options["crf"]=self.quality.value()

            if self.vcodecBox.currentText() == "libvpx-vp9":
                output_options["video_bitrate"] = 0 # Required for the format to use CRF only
                output_options["row-mt"] = 1 # Speeds up encode for most multicore systems

            output_options.update({
                "pix_fmt": "yuv420p",
                "c:a": self.acodecBox.currentText(),
                "c:v": self.vcodecBox.currentText(),
                "hide_banner": None,
                "progress": "-",
                "loglevel": "warning"
            })
            # TODO: determine if it's best to leave this as a QProcess, or use ffmpeg.run() and have it POpen itself
            ffmpeg_options = ffmpeg.output(filtered_video, audio_stream, self.vidFile(kbp), **output_options).overwrite_output().get_args()
            print(f'cd "{os.path.dirname(assfile)}"')
            print("ffmpeg" + " " + " ".join(f'"{x}"' for x in ffmpeg_options))
            q = QProcess(program="ffmpeg", arguments=ffmpeg_options, workingDirectory=os.path.dirname(assfile))
            q.setReadChannel(QProcess.StandardOutput)
            ffmpeg_processes.append((kbp, song_length_us, q))

        for row, (kbp, song_length_us, q) in enumerate(ffmpeg_processes):
            q.start()
            q.waitForStarted(-1)
            while not q.waitForFinished(100):
                if signals.cancelled:
                    self.statusbar.showMessage(f"Conversion cancelled during file {row+1} of {len(ffmpeg_processes)}!")
                    signals.finished.emit()
                    return
                while q.canReadLine():
                    if (ffmpeg_out_line := q.readLine().toStdString()).startswith("out_time_us="):
                        try:
                            out_time = int(ffmpeg_out_line.split("=")[1])
                        except:
                            pass # TODO: maybe switch to throbber if ffmpeg isn't outputting progress properly?
                        else:
                            signals.progress.emit(row, len(ffmpeg_processes), kbp, out_time, song_length_us)

            if q.exitStatus() != QProcess.NormalExit or q.exitCode() != 0:
                conversion_errors = True
                #QMetaObject.invokeMethod(
                #    self,
                #    'info',
                #    Qt.AutoConnection,
                #    Q_ARG(str, "Failed to convert file"),
                #    Q_ARG(str, f"Failed to process file\n{kbp}\n\nError Output:\n{q.readAllStandardError().toStdString()}"))
                signals.error.emit(f"Failed to process file\n{kbp}\n\nError Output:\n{q.readAllStandardError().toStdString()}", True)
                print(q.exitStatus())
                print(q.exitCode())

            signals.progress.emit(row, len(ffmpeg_processes), kbp, song_length_us, song_length_us)
        
        self.statusbar.showMessage(f"Conversion completed{' (with errors)' if conversion_errors else ''}!")
        signals.finished.emit()

    def retranslateUi(self):
        self.setWindowTitle(QCoreApplication.translate(
            "MainWindow", "KBP to Video", None))
        self.addButton.setText(QCoreApplication.translate(
            "MainWindow", "&Add Files...", None))
        self.editButton.setText(QCoreApplication.translate(
            "MainWindow", "Edit files...", None))
        self.advancedButton.setText(QCoreApplication.translate(
            "MainWindow", "Set Intro&/Outro...", None))
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
        self.ktLabel.setText(QCoreApplication.translate(
            "MainWindow", "Use \\&kt to allow overlapping wipes", None))
        self.ktLabel.setToolTip(QCoreApplication.translate(
            "MainWindow", "When wipes overlap on the same line, handle it by adding \\kt tags\nto show the wipes at their chosen times. Note that\n1) This is different from KBS that just tries to wipe it fast after the previous wipe\n2) It's not supported by some ASS tools, including Aegisub.", None))
        self.spacingLabel.setText(QCoreApplication.translate(
            "MainWindow", "Experimental style 1 spacing", None))
        self.spacingLabel.setToolTip(QCoreApplication.translate(
            "MainWindow", "Attempt to set the line spacing based on style 1 like KBS does.\nThis is currently working with a set list of fonts.\nIf your style 1 font is not in the list, conversion will fail.", None))
        self.overflowLabel.setText(QCoreApplication.translate(
            "MainWindow", "Word Wrappin&g", None))
        self.overflowBox.setToolTip(QCoreApplication.translate(
            "MainWindow", "When a line is too wide for the screen, use this strategy to wrap words\n  no wrap: Allow text to go off screen\n  even split: Wrap words in a way that makes the following line(s) about the same size\n  top split: Keep the first line long, only wrap at the word that causes it to go offscreen\n  bottom split: Make the bottom line long when wrapping", None))
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
            "MainWindow", "Override background", None))
        self.overrideBGLabel.setToolTip(QCoreApplication.translate(
            "MainWindow", "If this is unchecked, the resolution setting is only used for tracks with\nthe background set as a color. If it is checked, background image/video\nis scaled (and letterboxed if the aspect ratio differs) to achieve the\ntarget resolution.\n\nFEATURE NOT SUPPORTED YET", None))
        self.losslessLabel.setText(QCoreApplication.translate(
            "MainWindow", "Lossless video", None))
        self.lossless.setToolTip(QCoreApplication.translate(
            "MainWindow", "Use lossless quality settings on video (may create very large files).\nFor lossless audio and video, use an mkv container with this checked and flac codec for audio.", None))
        self.qualityLabel.setText(QCoreApplication.translate(
            "MainWindow", "Video &Quality", None))
        self.quality.setToolTip(QCoreApplication.translate(
            "MainWindow", "Quality of the output video.\nAt the very left is very low quality (CRF 40) and at the right is very high (CRF 10).\nffmpeg typically recommends between CRF 15-35. The default here is 23.\nNote, these are not entirely consistent across formats.\nFor example, CRF 28 H265 is supposedly about even with CRF 23 H264.", None))
        self.skipBackgroundsLabel.setText(QCoreApplication.translate(
            "MainWindow", "Ig&nore BG files in drag/drop", None))
        self.skipBackgroundsLabel.setToolTip(QCoreApplication.translate(
            "MainWindow", "When dragging and dropping files, do not import any image or video files\nas backgrounds. This is useful if you have your output and input files\nin the same place and usually use solid color backgrounds.", None))
        self.generalDivider.setText(QCoreApplication.translate(
            "MainWindow", "kbp2video options", None))
        self.outputDirLabel.setText(QCoreApplication.translate(
            "MainWindow", "Output Fo&lder", None))
        self.relativeLabel.setText(QCoreApplication.translate(
            "MainWindow", "Use relative &path from project file", None))
        self.relativeLabel.setToolTip(QCoreApplication.translate(
            "MainWindow", "Interpret Output Folder as a relative path from your .kbp file.\nE.g. leave it blank to have it in the same folder as your .kbp.", None))
        self.outputDirButton.setText(QCoreApplication.translate(
            "MainWindow", "Bro&wse...", None))
        self.resetButton.setText(QCoreApplication.translate(
            "MainWindow", "Reset Settings&...", None))
        self.convertButton.setText(QCoreApplication.translate(
            "MainWindow", "&Convert to Video", None))
        self.convertAssButton.setText(QCoreApplication.translate(
            "MainWindow", "Subtitle onl&y", None))
    # retranslateUi


def run(argv=sys.argv, ffmpeg_path=None):
    if '--help' in argv or '-h' in argv:
        print("kbp2video [[--help | -h] | [--version | -V]] [Qt6 options]")
        sys.exit(0)
    elif '--version' in argv or '-V' in argv:
        print(__version__)
        sys.exit(0)
    # Look better on Windows
    QApplication.setStyle("Fusion")
    app = QApplication(argv)
    orig_path = os.environ['PATH']
    if ffmpeg_path:
        os.environ['PATH'] = os.pathsep.join([ffmpeg_path, os.environ['PATH']])
    if not shutil.which("ffmpeg"):
        result = QFileDialog.getExistingDirectory(None, "Locate folder with ffmpeg and ffprobe")
        if result:
            os.environ['PATH'] = os.pathsep.join([result, orig_path])
        if not shutil.which("ffmpeg"):
            QMessageBox.critical(None, "ffmpeg not found", "ffmpeg still not found, please download the full release or otherwise install ffmpeg.")
            sys.exit(1)
    if not shutil.which("ffprobe"):
        QMessageBox.critical(None, "ffprobe not found", "ffprobe still not found, please download the full release or otherwise install ffmpeg.")
        sys.exit(1)
    window = Ui_MainWindow(app)
    window.show()
    sys.exit(app.exec())
