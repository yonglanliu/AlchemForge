
import os
import sys
import math
import re
import subprocess
from pathlib import Path

from PyQt5.QtCore import Qt, QSize, QPointF, QProcess, QTimer
from PyQt5.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QBrush
from PyQt5.QtWidgets import (
    QAction, QApplication, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QPushButton, QSizePolicy, QSplitter, QStatusBar, QTableWidget,
    QTableWidgetItem, QToolBar, QVBoxLayout, QWidget, QStyle, QStackedWidget
)
from PyQt5.QtWidgets import (
    QTreeWidget,
    QTreeWidgetItem,
)
from alchemforge.ui.dialogs.res_alchem_fep_dialog import (
    ResAlchemFEPDialog,
)

from alchemforge.ui.styles.style import STYLE
class MolecularSidebar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(205)
        self.setMaximumWidth(250)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        g = QLinearGradient(0, 0, 0, self.height())
        g.setColorAt(0.0, QColor("#f8fcff"))
        g.setColorAt(0.55, QColor("#edf6ff"))
        g.setColorAt(1.0, QColor("#dceefe"))
        p.fillRect(self.rect(), g)

        wave = QPainterPath()
        wave.moveTo(0, self.height() * 0.66)
        wave.cubicTo(
            self.width() * .25, self.height() * .59,
            self.width() * .58, self.height() * .84,
            self.width(), self.height() * .68
        )
        wave.lineTo(self.width(), self.height())
        wave.lineTo(0, self.height())
        wave.closeSubpath()
        p.fillPath(wave, QColor(176, 215, 249, 80))

        atoms = [
            (.13,.79,20),(.31,.74,14),(.48,.80,22),
            (.66,.74,14),(.82,.80,17),(.31,.87,14),(.53,.90,18)
        ]
        pts = [QPointF(self.width()*x, self.height()*y) for x,y,_ in atoms]

        p.setPen(QPen(QColor(107,166,220,125), 3))
        for a,b in [(0,1),(1,2),(2,3),(3,4),(1,5),(2,6),(5,6)]:
            p.drawLine(pts[a], pts[b])

        for i,(x,y,r) in enumerate(atoms):
            c = pts[i]
            rg = QLinearGradient(c.x()-r, c.y()-r, c.x()+r, c.y()+r)
            rg.setColorAt(0, QColor(235,247,255,235))
            rg.setColorAt(1, QColor(63,132,208,205))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(rg))
            p.drawEllipse(c, r, r)

        p.setPen(QPen(QColor(95,157,216,45), 2))
        upper = [QPointF(16,120), QPointF(45,104), QPointF(74,120), QPointF(103,104)]
        for a,b in zip(upper[:-1], upper[1:]):
            p.drawLine(a,b)
        for c in upper:
            p.drawEllipse(c, 5, 5)

        super().paintEvent(event)


class HeroBanner(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(335)
        self.setMaximumHeight(385)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect()

        g = QLinearGradient(0, 0, r.width(), r.height())
        g.setColorAt(0, QColor("#f7fcff"))
        g.setColorAt(.52, QColor("#d8ecff"))
        g.setColorAt(1, QColor("#83bced"))
        p.fillRect(r, g)

        # ribbon motif
        p.setPen(QPen(QColor(255,255,255,110), 3))
        for offset in range(0, 40, 8):
            path = QPainterPath()
            path.moveTo(0, r.height()-55+offset)
            path.cubicTo(
                r.width()*.28, r.height()-135+offset,
                r.width()*.50, r.height()+10+offset,
                r.width()*.78, r.height()-100+offset
            )
            p.drawPath(path)

        # faint chemistry motifs
        p.setPen(QPen(QColor(78,150,218,48), 2))
        for cx, cy in [(70,45),(140,78),(215,42),(300,82),(380,52)]:
            hp = QPainterPath()
            for i in range(7):
                a = math.radians(60*i-30)
                x = cx + 17*math.cos(a)
                y = cy + 17*math.sin(a)
                if i == 0: hp.moveTo(x,y)
                else: hp.lineTo(x,y)
            p.drawPath(hp)

        # abstract protein pocket
        colors = [
            QColor(248,252,255,240),
            QColor(191,222,248,230),
            QColor(111,174,228,225),
            QColor(45,118,190,220),
        ]
        blobs = [
            (.80,.18,55,0),(.87,.17,64,1),(.94,.22,62,0),
            (.79,.34,70,2),(.88,.34,75,3),(.97,.37,66,1),
            (.80,.54,76,2),(.89,.53,84,3),(.98,.56,72,1),
            (.83,.74,70,1),(.94,.73,78,0)
        ]
        p.setPen(Qt.NoPen)
        for xr,yr,rad,ci in blobs:
            p.setBrush(colors[ci])
            p.drawEllipse(QPointF(r.width()*xr, r.height()*yr), rad, rad)

        pocket = QPointF(r.width()*.88, r.height()*.48)
        p.setBrush(QColor(21,73,133,205))
        p.drawEllipse(pocket, 68, 56)

        ligand = [
            QPointF(pocket.x()-34,pocket.y()+13),
            QPointF(pocket.x()-10,pocket.y()-10),
            QPointF(pocket.x()+15,pocket.y()+3),
            QPointF(pocket.x()+40,pocket.y()-20),
            QPointF(pocket.x()+50,pocket.y()+14),
        ]
        p.setPen(QPen(QColor("#ffffff"), 7, Qt.SolidLine, Qt.RoundCap))
        for a,b in zip(ligand[:-1],ligand[1:]):
            p.drawLine(a,b)
        for i,c in enumerate(ligand):
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#f0443e") if i in (3,4) else QColor("#2465c4"))
            p.drawEllipse(c,7,7)

        # hero copy
        p.setPen(QColor("#103f7c"))
        p.setFont(QFont("Arial", 34, QFont.Bold))
        p.drawText(52, 96, "AlchemForge")

        p.setPen(QColor("#57779a"))
        p.setFont(QFont("Arial", 18))
        p.drawText(54, 133, "Molecular Alchemy for Real Discovery")

        p.setPen(QColor("#365d84"))
        p.setFont(QFont("Arial", 11))
        p.drawText(54, 173, "An integrated platform for alchemical free-energy calculations,")
        p.drawText(54, 195, "molecular simulation, and drug discovery.")

        p.setPen(QColor("#245f9b"))
        p.setFont(QFont("Arial", 10))
        p.drawText(55, 238, "⚡  Streamline")
        p.drawText(55, 258, "    complex workflows")
        p.drawText(230, 238, "▥  From structure")
        p.drawText(230, 258, "    to insight")
        p.drawText(415, 238, "◎  Accelerate")
        p.drawText(415, 258, "    real discovery")

        p.setPen(QColor("#2f7ed8"))
        p.setFont(QFont("Arial", 11, QFont.StyleItalic))
        p.drawText(55, 302, "Turning molecular ideas into real impact.")
        p.setPen(QPen(QColor("#76adea"), 2))
        p.drawLine(55, 310, 300, 310)

        super().paintEvent(event)


class ActionCard(QFrame):
    def __init__(self, title, subtitle, icon, callback=None):
        super().__init__()
        self.setObjectName("Card")
        self.callback = callback
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(120)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14,14,14,14)
        lay.setSpacing(6)

        ico = QLabel()
        ico.setAlignment(Qt.AlignCenter)
        ico.setPixmap(icon.pixmap(36,36))

        ttl = QLabel(title)
        ttl.setAlignment(Qt.AlignCenter)
        ttl.setStyleSheet("font-size:12pt; font-weight:700;")

        sub = QLabel(subtitle)
        sub.setAlignment(Qt.AlignCenter)
        sub.setWordWrap(True)
        sub.setObjectName("Muted")

        lay.addWidget(ico)
        lay.addWidget(ttl)
        lay.addWidget(sub)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.callback:
            self.callback()
        super().mousePressEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.project_path = None
        self.working_directory = os.getcwd()
        self.job_records = []
        self.job_processes = {}

        self.setWindowTitle("AlchemForge")
        self.resize(1500, 930)
        self.setMinimumSize(1120, 720)

        self.build_menu_bar()
        self.build_toolbar()
        self.build_ui()
        self.build_status_bar()

    def build_menu_bar(self):
        mb = self.menuBar()
        fm = mb.addMenu("File")

        a = QAction("New Project", self)
        a.setShortcut("Ctrl+N")
        a.triggered.connect(self.new_project)
        fm.addAction(a)

        a = QAction("Open Project...", self)
        a.setShortcut("Ctrl+O")
        a.triggered.connect(self.open_project)
        fm.addAction(a)

        self.recent_menu = fm.addMenu("Open Recent Project")
        fm.addSeparator()

        a = QAction("Close Project", self)
        a.triggered.connect(self.close_project)
        fm.addAction(a)

        fm.addSeparator()

        a = QAction("Change Working Directory...", self)
        a.setShortcut("Ctrl+D")
        a.triggered.connect(self.change_working_directory)
        fm.addAction(a)

        fm.addSeparator()
        fm.addAction("Exit", self.close, "Ctrl+Q")

        em = mb.addMenu("Edit")
        em.addAction("Undo")
        em.addAction("Redo")
        em.addSeparator()
        em.addAction("Preferences...")

        wm = mb.addMenu("Workspace")
        wm.addAction("Project Settings...")
        wm.addAction("Task Manager")
        wm.addSeparator()
        wm.addAction("Refresh Workspace")

        sm = mb.addMenu("Scripts")
        sm.addAction("Run Script...")
        sm.addAction("Open Script Editor")
        sm.addAction("Recent Scripts")

        vm = mb.addMenu("View")
        vm.addAction("Home")
        vm.addAction("Show Sidebar")
        vm.addAction("Show Project Panel")
        vm.addSeparator()
        vm.addAction("Reset Layout")

        winm = mb.addMenu("Window")
        winm.addAction("Minimize", self.showMinimized)
        winm.addAction("Maximize", self.showMaximized)
        winm.addAction("Restore", self.showNormal)

        hm = mb.addMenu("Help")
        hm.addAction("Documentation")
        hm.addAction("About AlchemForge", self.show_about)

    def build_toolbar(self):
        tb = QToolBar("Main")
        tb.setIconSize(QSize(28,28))
        tb.setMovable(False)
        self.addToolBar(tb)
        s = self.style()

        for icon, text, cb in [
            (QStyle.SP_FileIcon, "New", self.new_project),
            (QStyle.SP_DirOpenIcon, "Open", self.open_project),
            (QStyle.SP_DialogSaveButton, "Save", None),
        ]:
            a = QAction(s.standardIcon(icon), text, self)
            if cb: a.triggered.connect(cb)
            tb.addAction(a)

        tb.addSeparator()

        for icon, text, cb in [
            (QStyle.SP_MediaPlay, "Run", self.run_workflow),
            (QStyle.SP_MediaStop, "Stop", None),
        ]:
            a = QAction(s.standardIcon(icon), text, self)
            if cb: a.triggered.connect(cb)
            tb.addAction(a)

        tb.addSeparator()
        a = QAction(s.standardIcon(QStyle.SP_FileDialogDetailedView), "Settings", self)
        tb.addAction(a)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search (Ctrl+K)")
        self.search_edit.setMaximumWidth(220)
        tb.addWidget(self.search_edit)

        brand = QLabel("   AlchemForge")
        brand.setStyleSheet("font-size:19pt; font-weight:700; color:#123f76; padding:0 18px;")
        tb.addWidget(brand)

    def build_ui(self):
        split = QSplitter(Qt.Horizontal)
        split.setHandleWidth(1)
        split.addWidget(self.build_sidebar())
        self.center_stack = QStackedWidget()
        self.home_page = self.build_center()
        self.center_stack.addWidget(self.home_page)
        self.jobs_page = self.build_jobs_page()
        self.center_stack.addWidget(self.jobs_page)
        split.addWidget(self.center_stack)
        split.addWidget(self.build_right())
        split.setSizes([220,930,320])
        self.setCentralWidget(split)

    def build_jobs_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        title = QLabel("Jobs")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        self.jobs_table = QTableWidget(0, 5)
        self.jobs_table.setHorizontalHeaderLabels(
            ["Job", "Task", "Status", "SLURM IDs", "Error"]
        )
        self.jobs_table.verticalHeader().setVisible(False)
        self.jobs_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.jobs_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.jobs_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeToContents
        )
        self.jobs_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch
        )
        self.jobs_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeToContents
        )
        self.jobs_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeToContents
        )
        self.jobs_table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.Stretch
        )
        layout.addWidget(self.jobs_table)
        self.job_timer = QTimer(self)
        self.job_timer.timeout.connect(self.poll_jobs)
        self.job_timer.start(5000)
        return page

    def start_backend_job(self, task_directory, script_path, config_path):
        process = QProcess(self)
        process.setWorkingDirectory(task_directory)
        process.setProgram("bash")
        process.setArguments([script_path, config_path])
        record = {
            "name": Path(task_directory).name,
            "task": task_directory,
            "status": "RUNNING",
            "ids": [],
            "error": "",
            "output": "",
            "process": process,
        }
        self.job_records.append(record)
        self.job_processes[id(process)] = record
        process.readyReadStandardOutput.connect(
            lambda: self.read_job_output(process)
        )
        process.readyReadStandardError.connect(
            lambda: self.read_job_error(process)
        )
        process.finished.connect(
            lambda code, status: self.backend_job_finished(process, code, status)
        )
        process.start()
        self.center_stack.setCurrentWidget(self.jobs_page)
        self.refresh_jobs_table()

    def read_job_output(self, process):
        record = self.job_processes.get(id(process))
        if record is not None:
            record["output"] += bytes(process.readAllStandardOutput()).decode(
                errors="replace"
            )

    def read_job_error(self, process):
        record = self.job_processes.get(id(process))
        if record is not None:
            record["error"] += bytes(process.readAllStandardError()).decode(
                errors="replace"
            )

    def backend_job_finished(self, process, exit_code, _exit_status):
        self.read_job_output(process)
        self.read_job_error(process)
        record = self.job_processes.get(id(process))
        if record is None:
            return

        if exit_code != 0:
            record["status"] = "FAILED"
            record["error"] = (
                record["error"].strip()
                or record["output"].strip()
                or f"Submission exited with code {exit_code}."
            )
        else:
            record["ids"] = re.findall(
                r"(?:job:|Submitted batch job)\s*([0-9]+)",
                record["output"],
                flags=re.IGNORECASE,
            )
            record["status"] = "SUBMITTED" if record["ids"] else "COMPLETED"
        self.refresh_jobs_table()

    def poll_jobs(self):
        for record in self.job_records:
            if record["status"] != "SUBMITTED" or not record["ids"]:
                continue
            try:
                result = subprocess.run(
                    [
                        "sacct",
                        "-X",
                        "-j",
                        ",".join(record["ids"]),
                        "--format=State",
                        "--noheader",
                        "--parsable2",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            except (OSError, subprocess.TimeoutExpired):
                continue
            if result.returncode != 0:
                continue
            states = {
                line.strip().split("+")[0]
                for line in result.stdout.splitlines()
                if line.strip()
            }
            if not states:
                continue
            failed_states = {
                "FAILED", "CANCELLED", "TIMEOUT", "OUT_OF_MEMORY", "NODE_FAIL"
            }
            if states & failed_states:
                record["status"] = "FAILED"
                record["error"] = "SLURM state: " + ", ".join(sorted(states))
            elif states and states <= {"COMPLETED"}:
                record["status"] = "COMPLETED"
        self.refresh_jobs_table()

    def refresh_jobs_table(self):
        if not hasattr(self, "jobs_table"):
            return
        self.jobs_table.setRowCount(0)
        for record in self.job_records:
            row = self.jobs_table.rowCount()
            self.jobs_table.insertRow(row)
            values = (
                record["name"],
                record["task"],
                record["status"],
                ", ".join(record["ids"]),
                record["error"].strip(),
            )
            for column, value in enumerate(values):
                self.jobs_table.setItem(row, column, QTableWidgetItem(value))

    def build_sidebar(self):
        side = MolecularSidebar()

        lay = QVBoxLayout(side)
        lay.setContentsMargins(0, 8, 0, 12)

        # ============================================================
        # Navigation tree
        # ============================================================

        self.nav = QTreeWidget()
        self.nav.setObjectName("Navigation")
        self.nav.setStyleSheet("""
            QTreeWidget {
                background: transparent;
                border: none;
                outline: none;
                color: #23486f;
                font-size: 11pt;
            }

            QTreeWidget::item {
                height: 38px;
                padding-left: 8px;
                border-radius: 6px;
            }

            QTreeWidget::item:hover {
                background: rgba(72, 145, 215, 35);
            }

            QTreeWidget::item:selected {
                background: rgba(72, 145, 215, 55);
                color: #155b9e;
                font-weight: 600;
            }

            QTreeWidget::branch {
                background: transparent;
            }
            """)

        # Hide normal tree header
        self.nav.setHeaderHidden(True)

        # Remove root decoration lines
        self.nav.setRootIsDecorated(True)

        # Indentation for child items
        self.nav.setIndentation(22)

        # ============================================================
        # Home
        # ============================================================

        home = QTreeWidgetItem(
            self.nav,
            ["⌂   Home"]
        )

        home.setData(
            0,
            Qt.UserRole,
            "home"
        )

        # ============================================================
        # Binding Free Energy
        # ============================================================

        binding = QTreeWidgetItem(
            self.nav,
            ["▥   Binding Free Energy"]
        )

        binding.setData(
            0,
            Qt.UserRole,
            "binding_free_energy"
        )

        # -------------------------
        # ABFE
        # -------------------------

        abfe = QTreeWidgetItem(
            binding,
            ["ABFE"]
        )

        abfe.setData(
            0,
            Qt.UserRole,
            "abfe"
        )

        # -------------------------
        # RBFE
        # -------------------------

        rbfe = QTreeWidgetItem(
            binding,
            ["RBFE"]
        )

        rbfe.setData(
            0,
            Qt.UserRole,
            "rbfe"
        )

        # RBFE -> ResAlchemFEP

        res_fep = QTreeWidgetItem(
            rbfe,
            ["ResAlchemFEP"]
        )

        res_fep.setData(
            0,
            Qt.UserRole,
            "res_alchem_fep"
        )

        # RBFE -> LigAlchemFEP

        lig_fep = QTreeWidgetItem(
            rbfe,
            ["LigAlchemFEP"]
        )

        lig_fep.setData(
            0,
            Qt.UserRole,
            "lig_alchem_fep"
        )

        # ============================================================
        # Analysis
        # ============================================================

        analysis = QTreeWidgetItem(
            self.nav,
            ["↗   Analysis"]
        )

        analysis.setData(
            0,
            Qt.UserRole,
            "analysis"
        )

        # ============================================================
        # Jobs
        # ============================================================

        jobs = QTreeWidgetItem(
            self.nav,
            ["☷   Jobs"]
        )

        jobs.setData(
            0,
            Qt.UserRole,
            "jobs"
        )

        # ============================================================
        # Results
        # ============================================================

        results = QTreeWidgetItem(
            self.nav,
            ["▰   Results"]
        )

        results.setData(
            0,
            Qt.UserRole,
            "results"
        )

        # ============================================================
        # Initial state
        # ============================================================

        # Initially collapse Binding Free Energy
        binding.setExpanded(False)

        # Initially collapse RBFE
        rbfe.setExpanded(False)

        # Select Home
        self.nav.setCurrentItem(home)

        # ============================================================
        # Signals
        # ============================================================

        self.nav.itemClicked.connect(
            self.on_navigation_clicked
        )

        lay.addWidget(
            self.nav,
            1
        )

        # ============================================================
        # Bottom tagline
        # ============================================================

        tag = QLabel(
            "Explore\n"
            "Simulate\n"
            "Design\n"
            "Discover"
        )

        tag.setAlignment(
            Qt.AlignCenter
        )

        tag.setStyleSheet(
            """
            color: #4f90d7;
            font-size: 12pt;
            font-style: italic;
            padding-bottom: 18px;
            """
        )

        lay.addWidget(tag)

        return side

    def build_center(self):
        c = QWidget()
        lay = QVBoxLayout(c)
        lay.setContentsMargins(10,10,10,10)
        lay.setSpacing(10)

        tab = QFrame()
        tab.setObjectName("Card")
        t = QHBoxLayout(tab)
        t.setContentsMargins(10,6,10,6)
        lab = QLabel("⌂  Home")
        lab.setStyleSheet("font-weight:700;")
        t.addWidget(lab)
        t.addStretch()
        x = QLabel("×")
        x.setStyleSheet("font-size:16pt; color:#44688e;")
        t.addWidget(x)
        lay.addWidget(tab)

        hero = HeroBanner()
        hero.setObjectName("Card")
        lay.addWidget(hero)

        sec = QLabel("⚡  Quick Start")
        sec.setObjectName("SectionTitle")
        lay.addWidget(sec)

        cards = QGridLayout()
        cards.setSpacing(10)
        s = self.style()
        cards.addWidget(ActionCard("New Project","Start a new workflow",s.standardIcon(QStyle.SP_FileIcon),self.new_project),0,0)
        cards.addWidget(ActionCard("Open Project","Open an existing project",s.standardIcon(QStyle.SP_DirOpenIcon),self.open_project),0,1)
        cards.addWidget(ActionCard("Set Working Directory","Choose working directory",s.standardIcon(QStyle.SP_DirIcon),self.change_working_directory),0,2)
        lay.addLayout(cards)

        rh = QHBoxLayout()
        ttl = QLabel("◷  Recent Projects")
        ttl.setObjectName("SectionTitle")
        rh.addWidget(ttl)
        rh.addStretch()
        b = QPushButton("View All →")
        b.setStyleSheet("border:none; color:#2f7ed8; font-weight:700; background:transparent;")
        rh.addWidget(b)
        lay.addLayout(rh)

        self.recent_table = QTableWidget(0,3)
        self.recent_table.setHorizontalHeaderLabels(["Name","Path","Last Opened"])
        self.recent_table.verticalHeader().setVisible(False)
        self.recent_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.recent_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.recent_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeToContents)
        self.recent_table.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch)
        self.recent_table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeToContents)
        lay.addWidget(self.recent_table,1)
        return c

    def build_right(self):
        right = QWidget()
        right.setMinimumWidth(280)
        right.setMaximumWidth(350)
        lay = QVBoxLayout(right)
        lay.setContentsMargins(8,10,10,10)
        lay.setSpacing(12)

        project = QFrame()
        project.setObjectName("RightCard")
        p = QVBoxLayout(project)
        p.setContentsMargins(14,12,14,12)
        title = QLabel("▰  Project")
        title.setObjectName("SideTitle")
        p.addWidget(title)
        self.project_label = QLabel("No project open")
        self.project_label.setObjectName("Muted")
        p.addWidget(self.project_label)
        p.addSpacing(8)
        p.addWidget(QLabel("Working Directory:"))
        self.workdir_label = QLabel(self.working_directory)
        self.workdir_label.setWordWrap(True)
        p.addWidget(self.workdir_label)
        ch = QPushButton("Change Directory...")
        ch.clicked.connect(self.change_working_directory)
        p.addWidget(ch)
        lay.addWidget(project)

        quick = QFrame()
        quick.setObjectName("RightCard")
        q = QVBoxLayout(quick)
        q.setContentsMargins(14,12,14,12)
        title = QLabel("⌄  Quick Actions")
        title.setObjectName("SideTitle")
        q.addWidget(title)
        for label, cb in (
            ("New Project",self.new_project),
            ("Open Project...",self.open_project),
            ("Run Workflow...",self.run_workflow),
        ):
            btn = QPushButton(label)
            btn.clicked.connect(cb)
            q.addWidget(btn)
        lay.addWidget(quick)

        tips = QFrame()
        tips.setObjectName("RightCard")
        t = QVBoxLayout(tips)
        t.setContentsMargins(14,12,14,12)
        title = QLabel("ⓘ  Tips")
        title.setObjectName("SideTitle")
        t.addWidget(title)
        body = QLabel("Create or open a project to get started. Use the sidebar to navigate through the AlchemForge workflow.")
        body.setObjectName("Muted")
        body.setWordWrap(True)
        t.addWidget(body)
        mol = QLabel("⌬      ⌬\n   ╲  ╱\n    ⌬")
        mol.setAlignment(Qt.AlignCenter)
        mol.setStyleSheet("font-size:24pt; color:#c4ddf5; padding:20px 0;")
        t.addWidget(mol)
        slogan = QLabel("Small Molecules\nBig Possibilities")
        slogan.setAlignment(Qt.AlignCenter)
        slogan.setStyleSheet("color:#2f7ed8; font-size:12pt; font-style:italic;")
        t.addWidget(slogan)
        lay.addWidget(tips,1)

        return right

    def build_status_bar(self):
        st = QStatusBar()
        self.setStatusBar(st)
        ready = QLabel("●  Ready")
        ready.setStyleSheet("color:#169c4b;")
        st.addWidget(ready)
        st.addPermanentWidget(QLabel(f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"))
        self.status_project = QLabel("No project")
        st.addPermanentWidget(self.status_project)
        self.status_workdir = QLabel(self.working_directory)
        st.addPermanentWidget(self.status_workdir)

    def new_project(self):
        p, _ = QFileDialog.getSaveFileName(self,"Create AlchemForge Project",self.working_directory,"AlchemForge Project (*.afp)")
        if not p:
            return
        project = Path(p)
        if project.suffix.lower() != ".afp":
            project = project.with_suffix(".afp")
        project.touch(exist_ok=True)
        self.project_path = project
        self.project_label.setText(project.stem)
        self.status_project.setText(project.stem)
        self.setWindowTitle(f"AlchemForge — {project.stem}")
        self.add_recent(project)

    def open_project(self):
        p, _ = QFileDialog.getOpenFileName(self,"Open AlchemForge Project",self.working_directory,"AlchemForge Project (*.afp);;All Files (*)")
        if not p:
            return
        project = Path(p)
        self.project_path = project
        self.project_label.setText(project.stem)
        self.status_project.setText(project.stem)
        self.setWindowTitle(f"AlchemForge — {project.stem}")
        self.add_recent(project)

    def close_project(self):
        self.project_path = None
        self.project_label.setText("No project open")
        self.status_project.setText("No project")
        self.setWindowTitle("AlchemForge")

    def change_working_directory(self):
        d = QFileDialog.getExistingDirectory(self,"Change Working Directory",self.working_directory)
        if d:
            self.working_directory = d
            self.workdir_label.setText(d)
            self.status_workdir.setText(d)

    def run_workflow(self):
        QMessageBox.information(self,"Run Workflow","Workflow execution will be connected to your task system.")

    def add_recent(self, project):
        row = self.recent_table.rowCount()
        self.recent_table.insertRow(row)
        self.recent_table.setItem(row,0,QTableWidgetItem(project.name))
        self.recent_table.setItem(row,1,QTableWidgetItem(str(project.parent)))
        self.recent_table.setItem(row,2,QTableWidgetItem("Now"))

    def show_about(self):
        QMessageBox.about(
            self,
            "About AlchemForge",
            "<b>AlchemForge</b><br><br>A graphical workbench for alchemical free-energy calculations, molecular simulation, and HPC workflows."
        )

    def on_navigation_clicked(self, item, column):
        page = item.data(
            0,
            Qt.UserRole
        )

        # ------------------------------------
        # Parent menus
        # ------------------------------------

        if page == "binding_free_energy":

            item.setExpanded(
                not item.isExpanded()
            )

            return

        if page == "rbfe":

            item.setExpanded(
                not item.isExpanded()
            )

            return

        # ------------------------------------
        # Workflow pages
        # ------------------------------------

        if page == "home":
            self.center_stack.setCurrentWidget(self.home_page)
            print("Open Home")

        elif page == "abfe":
            print("Open ABFE")

        elif page == "res_alchem_fep":
            dialog = ResAlchemFEPDialog(
                working_directory=self.working_directory,
                parent=self
            )
            dialog.job_requested.connect(self.start_backend_job)
            dialog.exec_()
            print("Open Residue Alchemical FEP")

        elif page == "lig_alchem_fep":
            print("Open Ligand Alchemical FEP")

        elif page == "analysis":
            print("Open Analysis")

        elif page == "jobs":
            self.center_stack.setCurrentWidget(self.jobs_page)
            self.refresh_jobs_table()
            print("Open Jobs")

        elif page == "results":
            print("Open Results")

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("AlchemForge")
    app.setFont(QFont("Arial",10))
    app.setStyleSheet(STYLE)

    w = MainWindow()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
