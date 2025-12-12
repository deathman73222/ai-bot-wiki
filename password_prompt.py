from __future__ import annotations

import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox
)
from PyQt5.QtCore import Qt

from ai_bot.security.password_store import verify_password, is_password_set


class PasswordPrompt(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Enter Password')
        layout = QVBoxLayout(self)
        label = QLabel('Please enter your password to continue')
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        self.pw = QLineEdit()
        self.pw.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.pw)
        btn = QPushButton('Unlock')
        btn.clicked.connect(self._check)
        layout.addWidget(btn)

    def _check(self):
        if verify_password(self.pw.text()):
            QApplication.instance().exit(0)
        else:
            QMessageBox.critical(self, 'Access denied', 'Incorrect password')


def main():
    if not is_password_set():
        # No password set; block and instruct the user
        app = QApplication(sys.argv)
        QMessageBox.warning(
            None, 'Password', 'No password set. Please run password.bat to create one.')
        sys.exit(1)
    app = QApplication(sys.argv)
    w = PasswordPrompt()
    w.resize(360, 150)
    w.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
