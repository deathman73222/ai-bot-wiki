from __future__ import annotations

import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox
)
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtCore import Qt

from ai_bot.security.password_store import set_password, is_password_set


class PasswordSetup(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Set Password')
        pal = self.palette()
        pal.setColor(QPalette.Window, QColor('white'))
        self.setPalette(pal)
        self.setAutoFillBackground(True)

        layout = QVBoxLayout(self)
        title = QLabel('Create your password')
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            'font-size: 18px; font-weight: bold; color: black;')
        layout.addWidget(title)

        self.pw1 = QLineEdit()
        self.pw1.setEchoMode(QLineEdit.Password)
        self.pw1.setPlaceholderText('Enter password')
        layout.addWidget(self.pw1)

        self.pw2 = QLineEdit()
        self.pw2.setEchoMode(QLineEdit.Password)
        self.pw2.setPlaceholderText('Confirm password')
        layout.addWidget(self.pw2)

        self.save_btn = QPushButton('Save Password')
        self.save_btn.clicked.connect(self._save)
        layout.addWidget(self.save_btn)

    def _save(self):
        p1 = self.pw1.text()
        p2 = self.pw2.text()
        if not p1:
            QMessageBox.warning(self, 'Missing', 'Please enter a password')
            return
        if p1 != p2:
            QMessageBox.warning(self, 'Mismatch', 'Passwords do not match')
            return
        try:
            set_password(p1)
            QMessageBox.information(self, 'Success', 'Password saved')
            QApplication.instance().exit(0)
        except Exception as e:
            QMessageBox.critical(
                self, 'Error', f'Failed to save password: {e}')


def main():
    if is_password_set():
        # If already set, inform and exit to avoid accidental overwrite
        app = QApplication(sys.argv)
        QMessageBox.information(
            None, 'Password', 'Password already set. You can run the app.')
        sys.exit(0)
    app = QApplication(sys.argv)
    w = PasswordSetup()
    w.resize(360, 200)
    w.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
