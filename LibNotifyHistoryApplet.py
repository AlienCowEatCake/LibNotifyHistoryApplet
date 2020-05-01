#!/usr/bin/env python3

import datetime
import dbus
import os
import sys
from dbus.mainloop.glib import DBusGMainLoop
from PyQt5 import QtCore, QtGui, QtWidgets


class LibNotifyHistoryApplet(QtCore.QObject):
    _icon = os.path.join(os.path.dirname(os.path.realpath(__file__)), "LibNotifyHistoryApplet.svg")

    def __init__(self):
        super(LibNotifyHistoryApplet, self).__init__()
        self._trayIcon = QtWidgets.QSystemTrayIcon()
        QtWidgets.qApp.aboutToQuit.connect(self._trayIcon.hide)
        self._trayIcon.setIcon(QtGui.QIcon(self._icon))
        self._trayIcon.activated.connect(self._on_tray_icon_activated)
        self._trayMenu = QtWidgets.QMenu()
        self._trayIcon.setContextMenu(self._trayMenu)
        self._trayMenu.addAction("Show Notifications History").triggered.connect(self._show_notifications_history)
        self._trayMenu.addSeparator()
        self._trayMenu.addAction("Exit").triggered.connect(QtWidgets.qApp.quit)
        self._notifications = []

    def show(self):
        while not self._trayIcon.geometry().isValid():
            self._trayIcon.hide()
            self._trayIcon.show()

    def appendNotification(self, notification):
        if notification["app_name"] != "LibNotifyHistoryApplet":
            self._notifications.insert(0, notification)

    def _show_notification(self, text):
        if not QtCore.QProcess.startDetached("notify-send", [
            "-u", "critical",
            "-i", self._icon,
            "-a", "LibNotifyHistoryApplet",
            "Notifications History",
            text
        ]):
            self._trayIcon.showMessage("Notifications History", text, self._trayIcon.icon())

    def _on_tray_icon_activated(self, reason):
        if reason in [QtWidgets.QSystemTrayIcon.Trigger, QtWidgets.QSystemTrayIcon.DoubleClick, QtWidgets.QSystemTrayIcon.MiddleClick]:
            self._show_notifications_history()

    def _show_notifications_history(self):
        delimeter = "========================================\n"
        notifications_text = delimeter
        for notification in self._notifications:
            notification_text = ""
            summary = notification["summary"]
            body = notification["body"]
            if summary and body:
                notification_text = summary + "\n" + body
            elif summary:
                notification_text = summary
            elif body:
                notification_text = body
            if notification_text:
                notifications_text += "Time: " + notification["datetime"] + "\n" + notification_text + "\n" + delimeter
        self._show_notification(notifications_text)


def main():
    app = QtWidgets.QApplication([])
    app.setQuitOnLastWindowClosed(False)
    applet = LibNotifyHistoryApplet()
    applet.show()

    def handle_notifications(bus, message):
        keys = ["app_name", "replaces_id", "app_icon", "summary", "body", "actions", "hints", "expire_timeout"]
        args = message.get_args_list()
        if len(args) == 8:
            notification = dict([(keys[i], args[i]) for i in range(8)])
            timestamp = datetime.datetime.now()
            notification["datetime"] = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            applet.appendNotification(notification)

    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    bus.add_match_string_non_blocking("eavesdrop=true, interface='org.freedesktop.Notifications', member='Notify'")
    bus.add_message_filter(handle_notifications)

    return app.exec_()


if __name__ == '__main__':
    sys.exit(main())
