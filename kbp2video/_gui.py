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
from PySide6.QtCore import QObject, QRunnable, QFile, QThreadPool, Q_ARG, QUrl, Q_RETURN_ARG, QDir, QEvent, QIODevice, QSettings, QSize, QRect, QMetaObject, QMargins, QCoreApplication, QTextStream, QProcess, QRegularExpression, Signal, Slot, QCommandLineParser
from PySide6.QtGui import QColor, QImage, QKeySequence, Qt, QDesktopServices, QRegularExpressionValidator
from PySide6.QtWidgets import QVBoxLayout, QFileDialog, QHBoxLayout, QSlider, QLabel, QLineEdit, QDoubleSpinBox, QSpacerItem, QInputDialog, QStackedWidget, QComboBox, QTableWidget, QGridLayout, QTableWidgetItem, QPushButton, QSpinBox, QHeaderView, QApplication, QTableView, QAbstractItemView, QMessageBox, QMainWindow, QLayout, QWidget, QMenuBar, QScrollArea, QSizePolicy, QStatusBar, QColorDialog, QCheckBox
import PySide6
from .utils import ClickLabel, bool2check, check2bool, mimedb
from .advanced_editor import AdvancedEditor
from .advanced_options import AdvancedOptions
from .progress_window import ProgressWindow
import ffmpeg
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
        if path.casefold().endswith(".ass"):
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
                    kbputils.DoblonTxtConverter(kbputils.DoblonTxt(path), **Ui_MainWindow.lyricsettings).kbpFile().writeFile(outfile)
                except:
                    print(traceback.format_exc())
                    return None
        elif path.casefold().endswith('.lrc'):
            outfile = os.path.splitext(path)[0] + '.kbp'
            if not os.path.exists(outfile):
                try:
                    kbputils.LRCConverter(kbputils.LRC(path), **Ui_MainWindow.lyricsettings).kbpFile().writeFile(outfile)
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
            path = os.path.abspath(os.path.join(base_dir, path))
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
            for key, files in (kbp_ass_data := result.merged_kbp_ass_data()).items():
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
                    if not match and (len(kbp_ass_data) == 1 or (
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
        super().__init__(QMessageBox.Information, "Check for updates", "Checking for updates…", QMessageBox.StandardButton(QMessageBox.Ok), parent=parent)
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

    def __init__(self, app, preload_files=None):
        super().__init__()
        self.app = app
        self.preload_files = preload_files
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
        self.resize(1280, 800)
        self.bind("centralWidget", QWidget(self))

        self.setCentralWidget(self.centralWidget)

        # TODO: Create menubar contents
        self.menubar = QMenuBar()
        self.menubar.setObjectName("menubar")
        #self.menubar.setGeometry(QRect(0, 0, 886, 25))
        self.filemenu = self.menubar.addMenu("&File")
        self.filemenu.addAction("&Add/Import Files", Qt.CTRL | Qt.Key_I, self.add_files_button)
        self.filemenu.addAction("&Load settings from file…", Qt.CTRL | Qt.Key_L, self.prompt_import_settings_file)
        self.filemenu.addAction("&Export settings…", Qt.CTRL | Qt.Key_E, self.prompt_export_settings_file)
        self.filemenu.addAction("&Quit", QKeySequence.Quit, self.app.quit)
        self.editmenu = self.menubar.addMenu("&Edit")
        # TODO: Ctrl-A already works, would this be helpful
        #self.editmenu.addAction("&Select All", self.select_all)
        self.editmenu.addAction("&Remove Selected", QKeySequence.Delete, self.remove_files_button)
        self.editmenu.addAction("&Add empty row", self.add_row_button)
        self.editmenu.addAction("&Open/Edit Selected Files", QKeySequence.Open, self.remove_files_button)
        self.editmenu.addAction("&Intro/Outro Settings", Qt.CTRL | Qt.Key_Return, self.advanced_button)
        self.editmenu.addAction("&Lyrics Import Options", self.advanced_options)
        self.helpmenu = self.menubar.addMenu("&Help")
        self.helpmenu.addAction("&About", lambda: QMessageBox.about(self, "About kbp2video", f"kbp2video version: {__version__}\n\nUsing:\nkbputils version: {kbputils.__version__}\nPySide6 version: {PySide6.__version__}\nffmpeg version: {ffmpeg_version}"))
        self.helpmenu.addAction("&Check for Updates…", lambda: UpdateBox.update_check(self))
        self.setMenuBar(self.menubar)

        self.setStatusBar(self.bind("statusbar", QStatusBar(self)))

        # No point in updating the status bar with empty messages
        self.installEventFilter(EventFilter(self, lambda obj, event: True if event.type() == QEvent.StatusTip and not event.tip() else False))

        ffmpeg_version=""

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
            stretch=10
        )

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

        self.bind("rightPane", QWidget(
            layout=self.bind("gridLayout", QGridLayout())
        ))
        self.horizontalLayout.addWidget(
            self.bind("rightPaneScroll", QScrollArea(
                widget=self.rightPane,
                widgetResizable=True,
                sizePolicy=QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred),
                horizontalScrollBarPolicy=Qt.ScrollBarAlwaysOff
            )),
            stretch=0
        )

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
            text="#000000", inputMask="\\#HHHHHHHH", styleSheet="color: #FFFFFF; background-color: #000000", textChanged=self.updateColor)), gridRow, 1)

        #self.updateColor(setColor=self.settings.value("video/background_color", type=str, defaultValue="#000000"))

        # TODO: Find a better way to set this to a reasonable width for 9 characters
        # minimumSizeHint is enough for about 3
        # sizeHint is enough for about 12
        self.colorText.setFixedWidth(
            self.colorText.minimumSizeHint().width() * 9 / 3)

        self.gridLayout.addWidget(self.bind("colorChooseButton", QPushButton(
            clicked=self.color_choose_button)), gridRow, 2)

        gridRow += 1
        self.gridLayout.addWidget(self.bind("loopBGBox", QCheckBox()), gridRow, 0, alignment=Qt.AlignRight)
        self.gridLayout.addWidget(self.bind("loopBGLabel", ClickLabel(buddy=self.loopBGBox, buddyMethod=QCheckBox.toggle)), gridRow, 1, 1, 2)

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

        #gridRow += 1
        ## TODO: implement feature
        #self.gridLayout.addWidget(self.bind("overrideBGResolution", QCheckBox(enabled=False)), gridRow, 0, alignment=Qt.AlignRight)
        #self.gridLayout.addWidget(self.bind("overrideBGLabel", ClickLabel(buddy=self.overrideBGResolution, buddyMethod=QCheckBox.toggle)), gridRow, 1, 1, 2)

        gridRow += 1
        self.containerOptions = {
            "mp4": (("h264", "libvpx-vp9", "libx265", "libsvtav1"), ("aac", "mp3", "libopus")),
            "mkv": (("libvpx-vp9", "h264", "libx265", "libsvtav1"), ("flac", "libopus", "aac", "mp3")),
            "webm": (("libvpx-vp9", "libsvtav1"), ("libopus",)),
            "mov": (("png",), ("aac",)),
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
            self.bind("abitrateBox", 
                QSpinBox(
                    minimum=32,
                    maximum=320,
                    singleStep=4,
                    suffix=" k",
                    #sizePolicy=QSizePolicy(
                    #    QSizePolicy.Maximum,
                    #    QSizePolicy.Maximum)
                    )), gridRow, 1, 1, 2)
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
        self.gridLayout.addWidget(self.bind("checkUpdates", QCheckBox()), gridRow, 0, alignment=Qt.AlignRight)
        self.gridLayout.addWidget(self.bind("checkUpdatesLabel", ClickLabel(buddy=self.checkUpdates, buddyMethod=QCheckBox.toggle)), gridRow, 1, 1, 2)

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

        try:
            q = QProcess(program="ffmpeg", arguments=["-version"])
            q.start()
        except:
            ffmpeg_version="UNKNOWN"

        versions = {"kbp2video": __version__, "kbputils": kbputils.__version__}
        if check2bool(self.checkUpdates):
            version = lastversion.has_update(repo=f"ItMightBeKaraoke/kbp2video", at="github", pre_ok=True, current_version=versions["kbp2video"])
            if version:
                versions["kbp2video"] += f" [update to {version}]"
            version = lastversion.has_update(repo=f"kbputils", at="pip", current_version=versions["kbputils"])
            if version:
                versions["kbputils"] += f" [update to {version}]"

        if not ffmpeg_version:
            try:
                q.waitForFinished(1000 if check2bool(self.checkUpdates) else 2000)
                q.setReadChannel(QProcess.StandardOutput)
                version_line = q.readLine().toStdString().split()
                ffmpeg_version = version_line[i+1] if (i := version_line.index("version")) else 'UNKNOWN'
            except:
                ffmpeg_version = "MISSING/UNKNOWN"
        self.statusbar.showMessage(f"kbp2video {versions['kbp2video']} (kbputils {versions['kbputils']}, ffmpeg {ffmpeg_version}, PySide6 {PySide6.__version__})")

        QMetaObject.connectSlotsByName(self)

        if self.preload_files:
            self.filedrop.importFiles(self.preload_files)
            delattr(self, "preload_files")

    # setupUi

    def prompt_import_settings_file(self):
        file, _ = QFileDialog.getOpenFileName(self, "Import Settings File", filter="Settings (*.ini)")
        if file:
            self.loadSettings(file)

    def prompt_export_settings_file(self):
        dialog = QFileDialog(self, "Export Settings File", filter="Settings (*.ini)", acceptMode=QFileDialog.AcceptSave, defaultSuffix="ini")
        if dialog.exec():
            self.saveSettings(dialog.selectedFiles()[0])

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

    def advanced_options(self):
        AdvancedOptions.showAdvancedOptions(self.lyricsettings)

    def edit_button(self):
        rows = set(x.row() for x in self.tableWidget.selectedIndexes())
        if len(rows) == 1 or QMessageBox.question(self, f"Open {len(rows)} files?", f"Are you sure you want to open {len(rows)} files at the same time?") == QMessageBox.Yes:
            for row in rows:
                QDesktopServices.openUrl(QUrl.fromLocalFile(self.tableWidget.filename(row, TrackTableColumn.KBP_ASS.value)))

    def color_choose_button(self):
        result = QColorDialog.getColor(
            initial=QColor.fromString(self.colorText.text()),
            options = QColorDialog.ColorDialogOption.ShowAlphaChannel
          )
        if result.isValid():
            self.colorText.setText(result.name(QColor.HexArgb) if result.alpha() < 255 else result.name())

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
        bgcolor_rgbf = bgcolor.getRgbF()[0:3]
        # If I calculated right, bgcolor_dark/bgcolor_light are the color including alpha on top of 25%/75% gray backgrounds
        # I couldn't figure out a way to get the normal checkerboard thing
        bgcolor_dark = QColor.fromRgbF(*(c * bgcolor.alphaF() + 0.25 * (1 - bgcolor.alphaF()) for c in bgcolor_rgbf)).name()
        bgcolor_light = QColor.fromRgbF(*(1 + bgcolor.alphaF() * (c - 1) - 0.25 * (1 - bgcolor.alphaF()) for c in bgcolor_rgbf)).name()
        self.colorText.setStyleSheet(f"""
                                        color: {textcolor}; background: qlineargradient(
                                                                         x1:0, y1:0, x2:1, y2: 0,
                                                                         stop:0 {bgcolor_dark},
                                                                         stop:0.075 {bgcolor_dark},
                                                                         stop:0.07501 {bgcolor_light},
                                                                         stop:0.15 {bgcolor_light},
                                                                         stop:0.15001 {bgcolor_dark},
                                                                         stop:0.225 {bgcolor_dark},
                                                                         stop:0.22501 {bgcolor_light},
                                                                         stop:0.3 {bgcolor_light},
                                                                         stop:0.30001 {bgcolor.name()},
                                                                         stop:1 {bgcolor.name()}
                                                                         )
                                     """)

    def updateCodecs(self):
        for idx, box in enumerate((self.vcodecBox, self.acodecBox)):
            box.setMaxCount(0)
            box.setMaxCount(10)
            box.addItems(self.containerOptions[self.containerBox.currentText()][idx])
            if box == self.acodecBox:
                box.addItem("None")
        if self.containerBox.currentText() == "mov":
            self.old_lossless_state = self.lossless.checkState()
            self.lossless.setChecked(True)
            self.lossless.setEnabled(False)
        elif hasattr(self, "old_lossless_state"):
            self.lossless.setEnabled(True)
            self.lossless.setCheckState(self.old_lossless_state)
            del self.old_lossless_state

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

    def saveSettings(self, file = None):
        if file:
            if os.path.exists(file):
                # In case it's an invalid settings file or has additional settings
                os.remove(file)
            settings = QSettings(file, QSettings.IniFormat)
        else:
            settings = self.settings

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
            "video/loop_bg": check2bool(self.loopBGBox),
            "video/output_resolution": self.resolutionBox.currentText(),
            #"video/override_bg_resolution": check2bool(self.overrideBGResolution),
            "video/container_format_index": self.containerBox.currentIndex(),
            "video/video_codec_index": self.vcodecBox.currentIndex(),
            "video/lossless": check2bool(self.lossless),
            "video/quality": self.quality.value(),
            "video/audio_codec_index": self.acodecBox.currentIndex(),
            "video/audio_bitrate_kb": self.abitrateBox.value(),
            "kbp2video/relative_path": check2bool(self.relative),
            "kbp2video/output_dir": self.outputDir.text(),
            "kbp2video/ignore_bg_files_drag_drop": check2bool(self.skipBackgrounds),
            "kbp2video/check_updates": check2bool(self.checkUpdates),
            **{"lyricimport/" + x: Ui_MainWindow.lyricsettings[x] for x in Ui_MainWindow.lyricsettings},
        }
        for setting, value in to_save.items():
            settings.setValue(setting, value)
        settings.sync()

    def loadSettings(self, file = None):
        
        if file:
            try:
                settings = QSettings(file, QSettings.IniFormat)
            except:
                QMessageBox.warning(self, "Unable to load settings file", f"Unable to load {file}\n{traceback.format_exc()}")
                return
        else:
            settings = self.settings
                
        # legacy options
        self.aspectRatioBox.setCurrentIndex(settings.value("subtitle/aspect_ratio_index", type=int, defaultValue=0))
        settings.remove("subtitle/aspect_ratio_index")
        #self.overrideBGResolution.setCheckState(bool2check(settings.value("overrideBGResolution", type=bool, defaultValue=False)))
        #settings.remove("overrideBGResolution")
        self.resolutionBox.setCurrentIndex(settings.value("video/output_resolution_index", type=int, defaultValue=0))
        settings.remove("video/output_resolution_index")

        # Restore existing or custom option
        aspect_text = settings.value("subtitle/aspect_ratio", type=str, defaultValue="<NONEXISTENT>")
        if (index := self.aspectRatioBox.findText(aspect_text)) != -1:
            self.aspectRatioBox.setCurrentIndex(index)
        elif aspect_text != "<NONEXISTENT>":
            self.aspectRatioBox.setCurrentText(aspect_text)

        self.fadeIn.setValue(settings.value("subtitle/fade_in", type=int, defaultValue=50))
        self.fadeOut.setValue(settings.value("subtitle/fade_out", type=int, defaultValue=50))
        self.offset.setValue(settings.value("subtitle/offset", type=float, defaultValue=0.0))
        self.offset_check_box(setState=bool2check(settings.value("subtitle/override_offset", type=bool, defaultValue=False)))
        self.transparencyBox.setCheckState(bool2check(settings.value("subtitle/transparent_bg", type=bool, defaultValue=True)))
        self.ktBox.setCheckState(bool2check(settings.value("subtitle/allow_kt", type=bool, defaultValue=False)))
        self.spacingBox.setCheckState(bool2check(settings.value("subtitle/style1_spacing", type=bool, defaultValue=False)))
        self.overflowBox.setCurrentText(settings.value("subtitle/overflow", type=str, defaultValue="no wrap"))
        self.updateColor(setColor=settings.value("video/background_color", type=str, defaultValue="#000000"))
        self.loopBGBox.setCheckState(bool2check(settings.value("video/loop_bg", type=bool, defaultValue=False)))

        # Restore existing or custom option
        resolution_text = settings.value("video/output_resolution", type=str, defaultValue="<NONEXISTENT>")
        if (index := self.resolutionBox.findText(resolution_text)) != -1:
            self.resolutionBox.setCurrentIndex(index)
        elif resolution_text != "<NONEXISTENT>":
            self.resolutionBox.setCurrentText(resolution_text)

        #self.overrideBGResolution.setCheckState(bool2check(settings.value("video/override_bg_resolution", type=bool, defaultValue=False)))
        self.containerBox.setCurrentIndex(settings.value("video/container_format_index", type=int, defaultValue=0))
        self.updateCodecs()
        self.vcodecBox.setCurrentIndex(settings.value("video/video_codec_index", type=int, defaultValue=0))
        self.lossless.setCheckState(bool2check(settings.value("video/lossless", type=bool, defaultValue=False)))
        self.quality.setValue(settings.value("video/quality", type=int, defaultValue=23))
        self.acodecBox.setCurrentIndex(settings.value("video/audio_codec_index", type=int, defaultValue=0))

        # transition from previous str type
        if settings.contains("video/audio_bitrate") and not settings.contains("video/audio_bitrate_kb"):
            old_bitrate = settings.value("video/audio_bitrate", type=str, defaultValue="")
            try:
                new_bitrate = int(old_bitrate[:-1]) if old_bitrate.endswith('k') else int(old_bitrate)/1000
            except:
                new_bitrate = 256
            new_bitrate=max(32, new_bitrate)
            settings.remove("video/audio_bitrate")
            settings.setValue("video/audio_bitrate_kb", new_bitrate)

        self.abitrateBox.setValue(settings.value("video/audio_bitrate_kb", type=int, defaultValue=256))
        self.relative.setCheckState(bool2check(settings.value("kbp2video/relative_path", type=bool, defaultValue=True)))
        self.outputDir.setText(settings.value("kbp2video/output_dir", type=str, defaultValue="kbp2video"))
        self.skipBackgrounds.setCheckState(bool2check(settings.value("kbp2video/ignore_bg_files_drag_drop", type=bool, defaultValue=False)))
        self.checkUpdates.setCheckState(bool2check(settings.value("kbp2video/check_updates", type=bool, defaultValue=False)))
        Ui_MainWindow.lyricsettings = {
            "max_lines_per_page": 6,
            "min_gap_for_new_page": 1000,
            "display_before_wipe": 1000,
            "remove_after_wipe": 500,
            "template_file": '',
            "comments": 'Created with kbp2video\nhttps://github.com/itmightbekaraoke/kbp2video/'
        }
        for x in Ui_MainWindow.lyricsettings:
            val = Ui_MainWindow.lyricsettings[x]
            Ui_MainWindow.lyricsettings[x] = settings.value("lyricimport/" + x, type=type(val), defaultValue=val)
        if not file:
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
            if kbp.casefold().endswith(".ass"):
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
            kbputils_options['offset'] = int(self.offset.value()*1000)
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
            use_alpha = False
            print(f"Retrieved Advanced settings for {kbp}:")
            print(advanced)
            if not kbp:
                continue
            self.statusbar.showMessage(f"Converting file {row+1} of {self.tableWidget.rowCount()} ({kbp})")
            signals.progress.emit(row, self.tableWidget.rowCount(), kbp, 0, 0)
            if not background:
                background_type = 0
                background = default_bg
            elif background.startswith("color:"):
                background = background[6:].strip(" #")
                if len(background) == 8:
                    use_alpha = True
                background_type = 0
            else:
                background_type = 1

            assfile = self.assFile(kbp)

            # Handle manually-typed filename. TODO: convert earlier, when the text value is updated
            if not isinstance(kbp_obj, KBPASSWrapper):
                try:
                    kbp_obj = KBPASSWrapper(kbp_obj)
                except:
                    conversion_errors = True
                    signals.error.emit(f"Failed to process file\n{kbp}\n\nError Output:\n{traceback.format_exc()}", True)
                    continue
            if hasattr(kbp_obj, "kbp_path"):
                print(kbputils_options)
                try:
                    data = kbp_obj.ass_data(**kbputils_options)
                except:
                    conversion_errors = True
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
                    signals.error.emit(f"Failed to create output folder\n{outdir}\nassociated with .kbp file\n{kbp}\n\nError Output:\n{traceback.format_exc()}", True)
                    continue

            # File was converted and .ass file needs to be written
            if kbp.casefold().endswith(".kbp"):
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

            if (container := self.containerBox.currentText()) == 'mkv':
                container = 'matroska'

            # Retrieve the enabled intro/outro parameters, excluding the X_enabled keys themselves
            advanced_params = {k: v for k, v in advanced.items() if (
                        (k.startswith('intro_') and advanced['intro_enable']) or 
                        (k.startswith('outro') and advanced['outro_enable'])) 
                    and not k.endswith('_enable')}

            if self.acodecBox.currentText() != "None":
                audio_opts = {
                        "audio_file": audio,
                        "audio_codec": self.acodecBox.currentText(),
                        "audio_bitrate": self.abitrateBox.value(),
                    }
            else:
                audio_opts = {}

            converter = kbputils.VideoConverter(
                        assfile,
                        self.vidFile(kbp),
                        preview = True,
                        aspect_ratio = kbputils.Ratio(*ratio),
                        target_x = resolution.split('x')[0],
                        target_y = resolution.split('x')[1],
                        **({"background_color": background} if background_type == 0 else {"background_media": background}),
                        loop_background_video = check2bool(self.loopBGBox),
                        media_container = container,
                        video_codec = self.vcodecBox.currentText(),
                        video_quality = 0 if check2bool(self.lossless) else self.quality.value(),
                        **audio_opts,
                        **advanced_params,
                        output_options = {
                                "pix_fmt": "rgba" if self.vcodecBox.currentText() == "png" else "yuva420p" if use_alpha else "yuv420p",
                                "hide_banner": None,
                                "progress": "-",
                                "loglevel": "warning"
                            }
                    )

            # This is going to be a slight regression in error reporting for now,
            # as kbputils doesn't have as much explicit error handling yet
            try:
                ffmpeg_cmdinfo = converter.run()
            except:
                conversion_errors = True
                signals.error.emit(f"Skipped {kbp}:\nUnable to generate ffmpeg command\n{traceback.format_exc()}", True)
                continue

            q = QProcess(program=ffmpeg_cmdinfo['args'][0], arguments=ffmpeg_cmdinfo['args'][1:], workingDirectory=ffmpeg_cmdinfo['cwd'])
            q.setReadChannel(QProcess.StandardOutput)
            ffmpeg_processes.append((kbp, ffmpeg_cmdinfo['length'], q))

        for row, (kbp, song_length_ms, q) in enumerate(ffmpeg_processes):
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
                            out_time = int(ffmpeg_out_line.split("=")[1]) / 1000
                        except:
                            pass # TODO: maybe switch to throbber if ffmpeg isn't outputting progress properly?
                        else:
                            signals.progress.emit(row, len(ffmpeg_processes), kbp, out_time, song_length_ms)

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

            signals.progress.emit(row, len(ffmpeg_processes), kbp, song_length_ms, song_length_ms)
        
        self.statusbar.showMessage(f"Conversion completed{' (with errors)' if conversion_errors else ''}!")
        signals.finished.emit()

    def retranslateUi(self):
        self.setWindowTitle(QCoreApplication.translate(
            "MainWindow", "KBP to Video", None))
        self.addButton.setText(QCoreApplication.translate(
            "MainWindow", "Add Files…", None))
        self.editButton.setText(QCoreApplication.translate(
            "MainWindow", "Edit Files…", None))
        self.advancedButton.setText(QCoreApplication.translate(
            "MainWindow", "Intro/Outro…", None))
        self.colorChooseButton.setText(QCoreApplication.translate(
            "MainWindow", "Choo&se…", None))
        self.colorChooseButton.setToolTip(QCoreApplication.translate(
            "MainWindow", "Choose a background color with a color picker", None))
        self.colorApplyButton.setText(QCoreApplication.translate(
            "MainWindow", "&< Apply BG", None))
        self.colorApplyButton.setToolTip(
            QCoreApplication.translate(
                "MainWindow",
                "Set the background color on everything in the left pane without a background",
                None))
        self.removeButton.setText(QCoreApplication.translate(
            "MainWindow", "Remove Row(s)", None))
        self.addRowButton.setText(QCoreApplication.translate(
            "MainWindow", "New row", None))
        self.dragDropDescription.setText(
            QCoreApplication.translate(
                "MainWindow",
                "Drop project and media files/folders above or use buttons below",
                None))
        self.assDivider.setText(QCoreApplication.translate(
            "MainWindow", "Subtitle options", None))
        self.fades.setText(QCoreApplication.translate(
            "MainWindow", "Fade &In/Out", None))
        self.aspectLabel.setText(QCoreApplication.translate(
            "MainWindow", "&Aspect Ratio", None))
        self.transparencyLabel.setText(QCoreApplication.translate(
            "MainWindow", "&Draw BG color transparent", None))
        self.transparencyLabel.setToolTip(QCoreApplication.translate(
            "MainWindow", "When using palette index 0 as a font or border color in KBS, make that color\ntransparent in the resulting .ass file. This improves compatibility with\ndrawing appearing and overlapping text. ", None))
        self.ktLabel.setText(QCoreApplication.translate(
            "MainWindow", "Use \\&kt to allow overlapping wipes", None))
        self.ktLabel.setToolTip(QCoreApplication.translate(
            "MainWindow", "When wipes overlap on the same line, handle it by adding \\kt tags\nto show the wipes at their chosen times. Note that\n1) This is different from KBS that just tries to wipe it fast after the previous wipe\n2) It's not supported by some ASS tools, including Aegisub.", None))
        self.spacingLabel.setText(QCoreApplication.translate(
            "MainWindow", "Experimental style &1 spacing", None))
        self.spacingLabel.setToolTip(QCoreApplication.translate(
            "MainWindow", "Attempt to set the line spacing based on style 1 like KBS does.\nThis is currently working with a set list of fonts.\nIf your style 1 font is not in the list, conversion will fail.", None))
        self.overflowLabel.setText(QCoreApplication.translate(
            "MainWindow", "Word Wrappin&g", None))
        self.overflowBox.setToolTip(QCoreApplication.translate(
            "MainWindow", "When a line is too wide for the screen, use this strategy to wrap words\n  no wrap: Allow text to go off screen\n  even split: Wrap words in a way that makes the following line(s) about the same size\n  top split: Keep the first line long, only wrap at the word that causes it to go offscreen\n  bottom split: Make the bottom line long when wrapping", None))
        self.overrideOffsetLabel.setText(QCoreApplication.translate(
            "MainWindow", "Override Timestamp Offset (&Z)", None))
        self.overrideOffsetLabel.setToolTip(QCoreApplication.translate(
            "MainWindow", "Set an offset to be applied to every timestamp in the KBP file when converting\nto .ass. If not overridden, the setting from within KBS is used if it can be located.", None))
        self.offsetLabel.setText(QCoreApplication.translate(
            "MainWindow", "Timesta&mp Offset", None))
        self.ffmpegDivider.setText(QCoreApplication.translate(
            "MainWindow", "Video options", None))
        self.loopBGLabel.setText(QCoreApplication.translate(
            "MainWindow", "Loop background video", None))
        self.loopBGLabel.setToolTip(QCoreApplication.translate(
            "MainWindow", "If unchecked and a background video is set, the video will play\nexactly once, to its full duration. If the duration is less than\nthe audio, the last frame will repeat.\n\nIf checked, the background video will loop as many times as needed\nto the duration of the audio (even if that is less than 1, so the\nbackground video would truncate if longer than the audio).", None))
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
            "MainWindow", "Enter a number for audio bitrate in kilobits per second.", None))
        #self.overrideBGLabel.setText(QCoreApplication.translate(
        #    "MainWindow", "Override background", None))
        #self.overrideBGLabel.setToolTip(QCoreApplication.translate(
        #    "MainWindow", "If this is unchecked, the resolution setting is only used for tracks with\nthe background set as a color. If it is checked, background image/video\nis scaled (and letterboxed if the aspect ratio differs) to achieve the\ntarget resolution.\n\nFEATURE NOT SUPPORTED YET", None))
        self.losslessLabel.setText(QCoreApplication.translate(
            "MainWindow", "&Lossless video", None))
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
        self.checkUpdatesLabel.setText(QCoreApplication.translate(
            "MainWindow", "Check for updates at start (&X)", None))
        self.skipBackgroundsLabel.setToolTip(QCoreApplication.translate(
            "MainWindow", "When kbp2video is started, check for updates and alert if one is available.", None))
        self.generalDivider.setText(QCoreApplication.translate(
            "MainWindow", "kbp2video options", None))
        self.outputDirLabel.setText(QCoreApplication.translate(
            "MainWindow", "Output Folde&r", None))
        self.relativeLabel.setText(QCoreApplication.translate(
            "MainWindow", "Use relative &path from project file", None))
        self.relativeLabel.setToolTip(QCoreApplication.translate(
            "MainWindow", "Interpret Output Folder as a relative path from your .kbp file.\nE.g. leave it blank to have it in the same folder as your .kbp.", None))
        self.outputDirButton.setText(QCoreApplication.translate(
            "MainWindow", "Bro&wse…", None))
        self.resetButton.setText(QCoreApplication.translate(
            "MainWindow", "Reset Settings…", None))
        self.convertButton.setText(QCoreApplication.translate(
            "MainWindow", "&Convert to Video", None))
        self.convertAssButton.setText(QCoreApplication.translate(
            "MainWindow", "Subtitle onl&y", None))
    # retranslateUi


def run(argv=sys.argv, ffmpeg_path=None):
    QApplication.setStyle("Fusion")
    QApplication.setApplicationName("kbp2video")
    QApplication.setApplicationVersion(__version__)
    app = QApplication(argv)
    parser = QCommandLineParser()
    parser.setApplicationDescription(QCoreApplication.translate("MainWindow", "Tool to work with karaoke projects and render high quality videos. Input files can be provided via the command line, but the GUI is shown regardless, to configure options for conversion.", None))
    parser.addPositionalArgument(QCoreApplication.translate("MainWindow", "files", None),
                                 QCoreApplication.translate("MainWindow", "files to import", None),
                                 f'[{QCoreApplication.translate("MainWindow", "files", None)}...]')
    parser.addHelpOption()
    parser.addVersionOption()
    parser.process(app)
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
    if preload_files := parser.positionalArguments():
        print(f"Found preload files: {preload_files}")
    window = Ui_MainWindow(app, preload_files)
    window.show()
    sys.exit(app.exec())
