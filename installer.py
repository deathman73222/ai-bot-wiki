"""AI Bot Installation Wizard.

Professional installer with language selection, location picker,
dependency installation, Wikipedia dumps, and password setup.
"""
import sys
import os
import subprocess
import threading
from pathlib import Path
from typing import Optional
import json

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QLineEdit, QProgressBar,
    QFileDialog, QMessageBox, QCheckBox, QTextEdit, QRadioButton
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QSize
from PyQt5.QtGui import QFont, QPixmap, QColor, QIcon
from PyQt5.QtSvg import QSvgWidget


def is_removable_path(path: str) -> bool:
    """Best-effort check whether a path is on a removable drive.

    On Windows this uses GetDriveTypeW; on POSIX it checks common mount
    points for removable media.
    """
    try:
        p = Path(path)
        if os.name == 'nt':
            # Windows: check drive type
            import ctypes
            drive = p.drive
            if not drive:
                return False
            DRIVE_REMOVABLE = 2
            try:
                dtype = ctypes.windll.kernel32.GetDriveTypeW(str(drive))
                return int(dtype) == DRIVE_REMOVABLE
            except Exception:
                return False
        # POSIX heuristics
        s = str(p)
        prefixes = ['/media', '/run/media', '/Volumes']
        return any(s.startswith(pref) for pref in prefixes)
    except Exception:
        return False


class InstallWorker(QThread):
    """Worker thread for installation tasks."""

    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, install_path: str, language: str, download_mode: str = "full", external_dump_path: Optional[str] = None):
        """Initialize worker.

        Args:
            install_path: Directory to install to.
            language: Selected language code.
        """
        super().__init__()
        self.install_path = install_path
        self.language = language
        # download_mode: 'full' or 'sample'
        self.download_mode = download_mode
        # external_dump_path: if provided, write dumps to this path (e.g., USB)
        self.external_dump_path = external_dump_path
        self.stopped = False

    def run(self):
        """Execute installation process."""
        try:
            # Create directories
            self.status.emit("Creating directories...")
            self.progress.emit(5)
            os.makedirs(self.install_path, exist_ok=True)
            os.makedirs(os.path.join(self.install_path, "data"), exist_ok=True)

            # Install Python dependencies
            self.status.emit("Installing Python packages...")
            self.progress.emit(15)
            self._install_dependencies()

            # Download Wikipedia data
            self.status.emit(
                f"Downloading Wikipedia data for {self.language}...")
            self.progress.emit(50)
            self._download_wikipedia()

            # Copy application files
            self.status.emit("Setting up application files...")
            self.progress.emit(80)
            self._copy_app_files()

            # Create configuration
            self.status.emit("Creating configuration...")
            self.progress.emit(90)
            self._create_config()

            self.progress.emit(100)
            self.status.emit("Installation complete!")
            self.finished.emit(True, "Installation successful!")

        except Exception as exc:  # pylint: disable=broad-except
            self.finished.emit(False, f"Error: {str(exc)}")

    def _install_dependencies(self) -> None:
        """Install Python packages from requirements.txt."""
        requirements_file = Path(__file__).parent / "requirements.txt"
        if requirements_file.exists():
            try:
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install", "-r",
                    str(requirements_file)
                ])
            except subprocess.CalledProcessError as exc:
                raise RuntimeError("Failed to install dependencies") from exc

    def _download_wikipedia(self) -> None:
        """Download Wikipedia data for selected language.

        Supports downloading full or a limited sample. If an external_dump_path
        is provided and looks like a removable drive, dumps will be written there.
        """
        try:
            script = Path(__file__).parent / "wiki_dumps.py"
            # Choose outdir: external if requested else local install path
            if self.external_dump_path:
                outdir = os.path.join(self.external_dump_path, self.language)
            else:
                outdir = os.path.join(self.install_path, "data", "wiki_dumps")

            os.makedirs(outdir, exist_ok=True)

            if script.exists():
                self.status.emit(
                    "Downloading and extracting Wikipedia dump (this may take a long time)...")
                cmd = [sys.executable, str(
                    script), "--lang", self.language, "--outdir", outdir]
                # If sample mode requested, ask the extractor to limit articles
                if getattr(self, 'download_mode', 'full') == 'sample':
                    cmd.extend(["--max", "1000"])

                # Run extractor and stream stdout to update progress
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                current_progress = 50
                assert proc.stdout is not None
                for raw_line in proc.stdout:
                    line = raw_line.strip()
                    if not line:
                        continue
                    if line.startswith('PROGRESS_DOWNLOAD:'):
                        try:
                            _, pct_str, _ = line.split(':', 2)
                            pct = int(pct_str)
                            prog = 20 + int(pct * 0.5)
                            current_progress = max(current_progress, prog)
                            self.progress.emit(current_progress)
                            self.status.emit(f"Downloading: {pct}%")
                        except Exception:
                            self.status.emit(line)
                    elif line.startswith('EXTRACTED:'):
                        try:
                            _, cnt_str = line.split(':', 1)
                            cnt = int(cnt_str)
                            current_progress = min(95, current_progress + 1)
                            self.progress.emit(current_progress)
                            self.status.emit(f"Extracted {cnt} articles")
                        except Exception:
                            self.status.emit(line)
                    else:
                        self.status.emit(line)

                proc.wait()
                if proc.returncode != 0:
                    raise subprocess.CalledProcessError(proc.returncode, cmd)

                # After extraction, attempt to convert per-article text files into sqlite DB
                converter = Path(__file__).parent / 'wiki_to_sqlite.py'
                if converter.exists():
                    try:
                        conv_cmd = [sys.executable, str(
                            converter), '--outdir', outdir, '--lang', self.language]
                        if getattr(self, 'download_mode', 'full') == 'sample':
                            conv_cmd.extend(['--max', '1000'])
                        subprocess.check_call(conv_cmd)
                    except subprocess.CalledProcessError:
                        # Non-fatal: extraction succeeded but conversion failed
                        self.status.emit(
                            'Warning: conversion to sqlite DB failed')
            else:
                # If the script is not available, create placeholder data folder
                os.makedirs(os.path.join(
                    self.install_path, "data"), exist_ok=True)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                "Failed to download or extract Wikipedia dump") from exc

    def _copy_app_files(self) -> None:
        """Copy application files to install directory."""
        source_dir = Path(__file__).parent
        ai_bot_dir = source_dir / "ai_bot"
        dest_ai_bot = Path(self.install_path) / "ai_bot"

        if ai_bot_dir.exists():
            import shutil
            if dest_ai_bot.exists():
                shutil.rmtree(dest_ai_bot)
            shutil.copytree(ai_bot_dir, dest_ai_bot)

    def _create_config(self) -> None:
        """Create configuration file."""
        config = {
            "language": self.language,
            "install_path": self.install_path,
            "version": "1.0",
            "first_run": True
        }
        config_file = os.path.join(self.install_path, "config.json")
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)


class AIBotInstaller(QMainWindow):
    """Main installer window."""

    def __init__(self):
        """Initialize the installer."""
        super().__init__()
        self.install_path = ""
        self.language = "en"
        self.install_worker = None
        self.current_step = 0

        self.setWindowTitle("AI Bot Installation Wizard")
        self.setGeometry(100, 100, 700, 500)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            QLabel {
                color: #333333;
            }
            QPushButton {
                background-color: #0066cc;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0052a3;
            }
            QPushButton:pressed {
                background-color: #003d7a;
            }
            QComboBox, QLineEdit {
                padding: 6px;
                border: 1px solid #cccccc;
                border-radius: 4px;
                background-color: white;
            }
        """)

        self.setup_ui()
        self.show_welcome()

    def setup_ui(self):
        """Setup main UI."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setContentsMargins(40, 40, 40, 40)
        self.main_layout.setSpacing(20)

    def show_welcome(self):
        """Show welcome screen."""
        self.clear_layout()
        self.current_step = 1

        # Title
        title = QLabel("Welcome to AI Bot Setup")
        title.setFont(QFont("Arial", 24, QFont.Bold))
        self.main_layout.addWidget(title)

        # Icon placeholder
        icon_label = QLabel("🤖 AI Bot - Hybrid Search Engine 🤖")
        icon_label.setFont(QFont("Arial", 16))
        icon_label.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(icon_label)

        # Description
        desc = QLabel(
            "This installer will:\n"
            "• Install all required dependencies\n"
            "• Download Wikipedia data\n"
            "• Setup your installation\n"
            "• Create a secure password\n\n"
            "Click Next to continue."
        )
        desc.setFont(QFont("Arial", 11))
        self.main_layout.addWidget(desc)

        self.main_layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        next_btn = QPushButton("Next")
        next_btn.clicked.connect(self.show_language_select)
        button_layout.addWidget(next_btn)

        quit_btn = QPushButton("Cancel")
        quit_btn.setStyleSheet("""
            QPushButton {
                background-color: #666666;
            }
            QPushButton:hover {
                background-color: #555555;
            }
        """)
        quit_btn.clicked.connect(self.close)
        button_layout.addWidget(quit_btn)

        self.main_layout.addLayout(button_layout)

    def show_language_select(self):
        """Show language selection screen."""
        self.clear_layout()
        self.current_step = 2

        title = QLabel("Select Language")
        title.setFont(QFont("Arial", 20, QFont.Bold))
        self.main_layout.addWidget(title)

        desc = QLabel(
            "Choose the primary language for Wikipedia data:\n"
            "(You can add more languages later)"
        )
        self.main_layout.addWidget(desc)

        # Language selector
        lang_layout = QHBoxLayout()
        lang_layout.addWidget(QLabel("Language:"))

        self.language_combo = QComboBox()
        self.language_combo.addItems([
            "English (en)",
            "Spanish (es)",
            "French (fr)",
            "German (de)",
            "Italian (it)",
            "Portuguese (pt)",
            "Russian (ru)",
            "Chinese (zh)",
            "Japanese (ja)",
            "Korean (ko)"
        ])
        lang_layout.addWidget(self.language_combo)
        lang_layout.addStretch()

        self.main_layout.addLayout(lang_layout)
        self.main_layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        back_btn = QPushButton("Back")
        back_btn.clicked.connect(self.show_welcome)
        button_layout.addWidget(back_btn)

        next_btn = QPushButton("Next")
        next_btn.clicked.connect(self.show_location_select)
        button_layout.addWidget(next_btn)

        self.main_layout.addLayout(button_layout)

    def show_location_select(self):
        """Show installation location selection."""
        self.clear_layout()
        self.current_step = 3

        # Extract language code
        lang_text = self.language_combo.currentText()
        self.language = lang_text.split("(")[1].rstrip(")")

        title = QLabel("Installation Location")
        title.setFont(QFont("Arial", 20, QFont.Bold))
        self.main_layout.addWidget(title)

        desc = QLabel("Where would you like to install AI Bot?")
        self.main_layout.addWidget(desc)

        # Location selector
        location_layout = QHBoxLayout()

        self.location_input = QLineEdit()
        default_path = os.path.join(
            str(Path.home()), "AI Bot"
        )
        self.location_input.setText(default_path)
        location_layout.addWidget(self.location_input)

        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_location)
        location_layout.addWidget(browse_btn)

        self.main_layout.addLayout(location_layout)
        self.main_layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        back_btn = QPushButton("Back")
        back_btn.clicked.connect(self.show_language_select)
        button_layout.addWidget(back_btn)

        next_btn = QPushButton("Next")
        next_btn.clicked.connect(self.show_summary)
        button_layout.addWidget(next_btn)

        self.main_layout.addLayout(button_layout)

    def browse_location(self):
        """Browse for installation location."""
        path = QFileDialog.getExistingDirectory(
            self, "Select Installation Location"
        )
        if path:
            self.location_input.setText(path)

    def _toggle_external_ui(self) -> None:
        """Enable/disable external path controls depending on checkbox."""
        enabled = False
        if hasattr(self, 'use_external_checkbox') and self.use_external_checkbox.isChecked():
            enabled = True
        # show/hide or enable/disable controls
        try:
            self.external_path_display.setEnabled(enabled)
            self.external_browse_btn.setEnabled(enabled)
            self.external_auth_btn.setEnabled(enabled)
        except Exception:
            pass

    def browse_external(self) -> None:
        """Browse for an external (USB) directory to store wiki dumps."""
        path = QFileDialog.getExistingDirectory(
            self, "Select external (USB) folder")
        if path:
            self.selected_external_path = path
            self.external_path_display.setText(path)

    def _update_install_button_state(self) -> None:
        """Enable or disable the Install button based on selections.

        Rules:
        - If "Sample" is selected, allow install.
        - If "Full" is selected, require the full_confirm_checkbox to be checked.
        - If external storage is selected, require a selected & authenticated external path.
        """
        try:
            # Default: disabled
            enabled = False
            # Sample download always allowed
            if hasattr(self, 'download_sample_radio') and self.download_sample_radio.isChecked():
                enabled = True
            # Full download requires explicit confirmation
            elif hasattr(self, 'download_full_radio') and self.download_full_radio.isChecked():
                if getattr(self, 'full_confirm_checkbox', None) and self.full_confirm_checkbox.isChecked():
                    enabled = True

            # If external is selected, require selected_external_path exists and auth file present
            if enabled and hasattr(self, 'use_external_checkbox') and self.use_external_checkbox.isChecked():
                sel = getattr(self, 'selected_external_path', None)
                if not sel:
                    enabled = False
                else:
                    auth_file = Path(sel) / '.ai_bot_usb_auth'
                    if not auth_file.exists():
                        enabled = False

            if hasattr(self, 'install_btn'):
                self.install_btn.setEnabled(enabled)
        except Exception:
            # Fail-safe: enable button so user isn't blocked by UI errors
            try:
                if hasattr(self, 'install_btn'):
                    self.install_btn.setEnabled(True)
            except Exception:
                pass

    def authenticate_usb(self) -> None:
        """Authenticate selected USB path to ensure it's removable and writable."""
        path = getattr(self, 'selected_external_path', None)
        if not path:
            QMessageBox.warning(self, "No USB Selected",
                                "Please select a USB drive/folder first.")
            return

        if not is_removable_path(path):
            QMessageBox.warning(self, "Not a Removable Drive",
                                "The selected path does not appear to be a removable USB drive. Please select the correct drive.")
            return

        # Try to write a small auth file
        try:
            test_file = Path(path) / ".ai_bot_usb_auth"
            with test_file.open('w', encoding='utf-8') as fh:
                fh.write('AI Bot USB authentication - do not remove')
            # read back
            if test_file.exists():
                QMessageBox.information(
                    self, "USB Authenticated", f"USB authenticated: {path}")
                # keep the selected_external_path
                self.selected_external_path = path
                return
        except Exception as exc:
            QMessageBox.warning(self, "USB Authentication Failed",
                                f"Could not write to selected USB: {exc}")
            return

    def show_summary(self):
        """Show installation summary."""
        self.clear_layout()
        self.current_step = 4

        self.install_path = self.location_input.text()

        title = QLabel("Installation Summary")
        title.setFont(QFont("Arial", 20, QFont.Bold))
        self.main_layout.addWidget(title)

        # Summary
        summary_text = f"""
Installation Path: {self.install_path}
Language: {self.language}
Package: Latest AI Bot

This will install:
• AI Bot Application
• Python Dependencies
• Wikipedia Database ({self.language})
• Desktop Shortcuts (if selected)

Space Required: ~500MB - 2GB (depending on language)
        """

        summary = QLabel(summary_text)
        summary.setFont(QFont("Arial", 11))
        self.main_layout.addWidget(summary)

        # Wikipedia download options
        dl_label = QLabel("Wikipedia download:")
        dl_label.setFont(QFont("Arial", 11, QFont.Bold))
        self.main_layout.addWidget(dl_label)

        dl_layout = QHBoxLayout()
        self.download_full_radio = QRadioButton(
            "Full (recommended for offline)")
        self.download_sample_radio = QRadioButton("Sample (fast, smaller)")
        self.download_full_radio.setChecked(True)
        dl_layout.addWidget(self.download_full_radio)
        dl_layout.addWidget(self.download_sample_radio)
        dl_layout.addStretch()
        self.main_layout.addLayout(dl_layout)

        # Full-download confirmation checkbox (must be checked to allow full download)
        self.full_confirm_checkbox = QCheckBox(
            "I understand this may take many hours and require many GB of disk space")
        self.full_confirm_checkbox.setChecked(False)
        self.main_layout.addWidget(self.full_confirm_checkbox)

        # External (USB) option
        self.use_external_checkbox = QCheckBox(
            "Store Wikipedia dumps on external drive (USB)")
        self.use_external_checkbox.setChecked(False)
        self.use_external_checkbox.stateChanged.connect(
            lambda _: self._toggle_external_ui())
        self.main_layout.addWidget(self.use_external_checkbox)

        # External path selector (hidden until checkbox checked)
        ext_layout = QHBoxLayout()
        self.external_path_display = QLineEdit()
        self.external_path_display.setReadOnly(True)
        self.external_path_display.setPlaceholderText(
            "No external path selected")
        ext_layout.addWidget(self.external_path_display)
        self.external_browse_btn = QPushButton("Browse USB")
        self.external_browse_btn.clicked.connect(self.browse_external)
        ext_layout.addWidget(self.external_browse_btn)
        self.external_auth_btn = QPushButton("Authenticate USB")
        self.external_auth_btn.clicked.connect(self.authenticate_usb)
        ext_layout.addWidget(self.external_auth_btn)
        self.main_layout.addLayout(ext_layout)
        # Ensure external UI is initially disabled
        self._toggle_external_ui()

        # Desktop shortcut option
        self.desktop_checkbox = QCheckBox(
            "Create desktop shortcut"
        )
        self.desktop_checkbox.setChecked(True)
        self.main_layout.addWidget(self.desktop_checkbox)

        self.main_layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        back_btn = QPushButton("Back")
        back_btn.clicked.connect(self.show_location_select)
        button_layout.addWidget(back_btn)

        # Install button will be enabled only when requirements are met
        self.install_btn = QPushButton("Install")
        self.install_btn.clicked.connect(self.start_installation)
        button_layout.addWidget(self.install_btn)

        # Connect toggles to update install button availability
        try:
            self.download_full_radio.toggled.connect(
                self._update_install_button_state)
            self.download_sample_radio.toggled.connect(
                self._update_install_button_state)
            self.full_confirm_checkbox.stateChanged.connect(
                self._update_install_button_state)
        except Exception:
            pass

        # Initialize install button state
        self._update_install_button_state()

        self.main_layout.addLayout(button_layout)

    def start_installation(self):
        """Start the installation process."""
        self.clear_layout()
        self.current_step = 5

        title = QLabel("Installing AI Bot")
        title.setFont(QFont("Arial", 20, QFont.Bold))
        self.main_layout.addWidget(title)

        # Status label
        self.status_label = QLabel("Initializing...")
        self.main_layout.addWidget(self.status_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setMinimum(0)
        self.main_layout.addWidget(self.progress_bar)

        # Details
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(150)
        self.main_layout.addWidget(self.details_text)

        self.main_layout.addStretch()

        # Start installation thread
        # Determine download_mode and external path selection
        download_mode = 'full'
        if hasattr(self, 'download_sample_radio') and self.download_sample_radio.isChecked():
            download_mode = 'sample'

        external_path = None
        if hasattr(self, 'use_external_checkbox') and self.use_external_checkbox.isChecked():
            external_path = getattr(self, 'selected_external_path', None)

        # If full download selected, show a confirmation dialog with warnings
        if download_mode == 'full':
            reply = QMessageBox.question(
                self,
                "Confirm full Wikipedia download",
                "You selected a FULL Wikipedia download. This will download and extract a very large file (many GB) and can take hours. Do you want to continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                # Return to summary screen
                QMessageBox.information(
                    self, "Aborted", "Full download aborted. You can choose Sample or try again.")
                self.show_summary()
                return

        # If external storage selected, ensure the selected path has been authenticated
        if external_path:
            sel = getattr(self, 'selected_external_path', None)
            if not sel:
                QMessageBox.warning(self, "External storage not authenticated",
                                    "You selected external storage but did not authenticate a USB. Please authenticate or uncheck the option.")
                self.show_summary()
                return
            auth_file = Path(sel) / '.ai_bot_usb_auth'
            if not auth_file.exists():
                QMessageBox.warning(self, "External storage not authenticated",
                                    "The selected external storage does not appear to be authenticated. Please run 'Authenticate USB' or choose another location.")
                self.show_summary()
                return

        self.install_worker = InstallWorker(
            self.install_path, self.language, download_mode=download_mode, external_dump_path=external_path)
        self.install_worker.progress.connect(self.update_progress)
        self.install_worker.status.connect(self.update_status)
        self.install_worker.finished.connect(self.installation_finished)
        self.install_worker.start()

    def update_progress(self, value: int):
        """Update progress bar.

        Args:
            value: Progress percentage.
        """
        self.progress_bar.setValue(value)

    def update_status(self, status: str):
        """Update status text.

        Args:
            status: Status message.
        """
        self.status_label.setText(status)
        self.details_text.append(f"• {status}")

    def installation_finished(self, success: bool, message: str):
        """Handle installation completion.

        Args:
            success: Whether installation was successful.
            message: Completion message.
        """
        if success:
            if self.desktop_checkbox.isChecked():
                self.create_shortcut()
            self.show_password_setup()
        else:
            QMessageBox.critical(self, "Installation Failed", message)
            self.show_welcome()

    def create_shortcut(self):
        """Create desktop shortcut."""
        try:
            from win32com.client import Dispatch
            shell = Dispatch("WScript.Shell")
            desktop = Path.home() / "Desktop" / "AI Bot.lnk"
            shortcut = shell.CreateShortCut(str(desktop))
            shortcut.TargetPath = os.path.join(
                self.install_path, "run_ai_bot.py"
            )
            shortcut.WorkingDirectory = self.install_path
            shortcut.Description = "AI Bot - Hybrid Search Engine"
            shortcut.save()
        except Exception as exc:  # pylint: disable=broad-except
            self.details_text.append(f"Note: Could not create shortcut: {exc}")

    def show_password_setup(self):
        """Show password setup screen."""
        self.clear_layout()
        self.current_step = 6

        title = QLabel("Secure Your Installation")
        title.setFont(QFont("Arial", 20, QFont.Bold))
        self.main_layout.addWidget(title)

        desc = QLabel(
            "Create a password to secure your AI Bot installation.\n"
            "This password will be used to protect your search history "
            "and settings.\n\n"
            "Password must be at least 8 characters."
        )
        self.main_layout.addWidget(desc)

        # Password input
        password_layout = QVBoxLayout()

        password_layout.addWidget(QLabel("Password:"))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        password_layout.addWidget(self.password_input)

        password_layout.addWidget(QLabel("Confirm Password:"))
        self.password_confirm = QLineEdit()
        self.password_confirm.setEchoMode(QLineEdit.Password)
        password_layout.addWidget(self.password_confirm)

        self.main_layout.addLayout(password_layout)
        self.main_layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        complete_btn = QPushButton("Complete Installation")
        complete_btn.clicked.connect(self.complete_installation)
        button_layout.addWidget(complete_btn)

        self.main_layout.addLayout(button_layout)

    def complete_installation(self):
        """Complete installation with password setup."""
        password = self.password_input.text()
        confirm = self.password_confirm.text()

        if len(password) < 8:
            QMessageBox.warning(
                self, "Invalid Password",
                "Password must be at least 8 characters."
            )
            return

        if password != confirm:
            QMessageBox.warning(
                self, "Password Mismatch",
                "Passwords do not match."
            )
            return

        # Save password (hashed)
        try:
            import hashlib
            password_hash = hashlib.sha256(
                password.encode()
            ).hexdigest()
            config_file = os.path.join(self.install_path, "config.json")
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
            config["password_hash"] = password_hash
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
        except Exception as exc:  # pylint: disable=broad-except
            QMessageBox.warning(
                self, "Error", f"Failed to save password: {exc}")
            return

        # Show completion
        self.show_completion()

    def show_completion(self):
        """Show installation completion screen."""
        self.clear_layout()

        title = QLabel("Installation Complete!")
        title.setFont(QFont("Arial", 24, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(title)

        completion_msg = QLabel(
            "🎉 AI Bot has been successfully installed!\n\n"
            f"Location: {self.install_path}\n"
            f"Language: {self.language}\n\n"
            "You can now:\n"
            "• Launch AI Bot from the desktop shortcut\n"
            "• Use the CLI with: python cli_interface.py\n"
            "• Enjoy hybrid search capabilities!\n\n"
            "Click Finish to exit this installer."
        )
        completion_msg.setFont(QFont("Arial", 12))
        completion_msg.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(completion_msg)

        self.main_layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        finish_btn = QPushButton("Finish")
        finish_btn.clicked.connect(self.close)
        button_layout.addWidget(finish_btn)

        self.main_layout.addLayout(button_layout)

    def clear_layout(self):
        """Clear the main layout."""
        while self.main_layout.count():
            child = self.main_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                self._clear_layout_recursive(child.layout())

    def _clear_layout_recursive(self, layout):
        """Recursively clear layout.

        Args:
            layout: Layout to clear.
        """
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                self._clear_layout_recursive(child.layout())


def main():
    """Main entry point."""
    app = QApplication(sys.argv)
    installer = AIBotInstaller()
    installer.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
