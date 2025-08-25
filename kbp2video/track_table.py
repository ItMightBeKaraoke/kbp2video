import enum
import collections
import re
import os
import glob
import difflib
import string
import traceback

from PySide6.QtCore import QUrl
from PySide6.QtGui import Qt
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QLabel, QMessageBox, QTableWidget, QTableWidgetItem, QWidget

import kbputils

from .utils import mimedb, KBPASSWrapper

class TrackTableColumn(enum.Enum):
    KBP_ASS = 0
    Audio = 1
    Background = 2
    Advanced = 3

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

