#!/usr/bin/env python3

import datetime
import dbus
import os
import sqlite3
import sys
from dbus.mainloop.glib import DBusGMainLoop
from PyQt5 import QtCore, QtGui, QtWidgets


class LibNotifyHistoryApplet(QtCore.QObject):
    _icon = os.path.join(os.path.dirname(os.path.realpath(__file__)), "LibNotifyHistoryApplet.svg")
    _default_notifications_num = 10

    def __init__(self):
        super(LibNotifyHistoryApplet, self).__init__()
        self._trayIcon = QtWidgets.QSystemTrayIcon()
        QtWidgets.qApp.aboutToQuit.connect(self._trayIcon.hide)
        self._trayIcon.setIcon(QtGui.QIcon(self._icon))
        self._trayIcon.activated.connect(self._on_tray_icon_activated)
        self._trayMenu = QtWidgets.QMenu()
        self._trayIcon.setContextMenu(self._trayMenu)
        self._trayMenu.addAction("Show Last {} Notifications".format(self._default_notifications_num)).triggered.connect(self._show_last_notifications)
        self._trayMenu.addAction("Show All Notifications").triggered.connect(self._show_all_notifications)
        self._trayMenu.addSeparator()
        self._trayMenu.addAction("Replay Last {} Notifications".format(self._default_notifications_num)).triggered.connect(self._replay_last_notifications)
        self._trayMenu.addAction("Replay All Notifications").triggered.connect(self._replay_all_notifications)
        self._trayMenu.addSeparator()
        self._trayMenu.addAction("Forget Last {} Notifications".format(self._default_notifications_num)).triggered.connect(self._forget_last_notifications)
        self._trayMenu.addAction("Forget All Notifications").triggered.connect(self._forget_all_notifications)
        self._trayMenu.addSeparator()
        self._trayMenu.addAction("Exit").triggered.connect(QtWidgets.qApp.quit)
        dbpath = os.path.join(os.getenv('XDG_CACHE_HOME', os.path.expanduser('~/.cache')), "LibNotifyHistoryApplet", "notifications.db")
        os.makedirs(os.path.dirname(dbpath), mode=0o700, exist_ok=True)
        self._notifications_db = sqlite3.connect(dbpath)
        QtWidgets.qApp.aboutToQuit.connect(self._notifications_db.close)
        self._notifications_db.execute('''
                CREATE TABLE IF NOT EXISTS notifications (
                    id integer primary key AUTOINCREMENT,
                    time_stamp text,
                    app_name text,
                    app_icon text,
                    summary text,
                    body text,
                    expire_timeout text
                    );
                ''')
        self._notifications_db.commit()

    def show(self):
        while not self._trayIcon.geometry().isValid():
            self._trayIcon.hide()
            self._trayIcon.show()

    def appendNotification(self, notification):
        if notification["app_name"] != "LibNotifyHistoryApplet":
            self._notifications_db.execute('''
                    INSERT INTO notifications(time_stamp, app_name, app_icon, summary, body, expire_timeout)
                        VALUES (?, ?, ?, ?, ?, ?);
                    ''', (
                str(notification["datetime"]),
                str(notification["app_name"]),
                str(notification["app_icon"]),
                str(notification["summary"]),
                str(notification["body"]),
                str(notification["expire_timeout"]),
            ))
            self._notifications_db.commit()

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
            self._show_last_notifications()

    def _show_notifications_history(self, num):
        delimeter = "========================================\n"
        notifications_text = delimeter
        for row in self._notifications_db.execute('''
                SELECT id, summary, body, time_stamp FROM notifications ORDER BY id DESC limit {};
                '''.format(num)):
            summary = row[1]
            body = row[2]
            datetime = row[3]
            notification_text = ""
            if summary and body:
                notification_text = summary + "\n" + body
            elif summary:
                notification_text = summary
            elif body:
                notification_text = body
            if notification_text:
                notifications_text += "Time: " + datetime + "\n" + notification_text + "\n" + delimeter
        self._show_notification(notifications_text)

    def _show_all_notifications(self):
        self._show_notifications_history(-1)

    def _show_last_notifications(self):
        self._show_notifications_history(self._default_notifications_num)

    def _replay_notifications_history(self, num):
        for row in self._notifications_db.execute('''
                SELECT id, app_icon, expire_timeout, summary, body FROM notifications ORDER BY id DESC limit {};
                '''.format(num)):
            app_icon = row[1]
            expire_timeout = row[2]
            summary = row[3]
            body = row[4]
            if not app_icon:
                app_icon = self._icon
            QtCore.QProcess.startDetached("notify-send", [
                "-i", app_icon,
                "-a", "LibNotifyHistoryApplet",
                "-t", expire_timeout,
                summary,
                body
            ])

    def _replay_all_notifications(self):
        self._replay_notifications_history(-1)

    def _replay_last_notifications(self):
        self._replay_notifications_history(self._default_notifications_num)

    def _forget_all_notifications(self):
        self._notifications_db.execute('''
            DELETE FROM notifications;
            ''')
        self._notifications_db.commit()

    def _forget_last_notifications(self):
        self._notifications_db.execute('''
            DELETE FROM notifications WHERE id IN (
                SELECT id FROM notifications ORDER BY id DESC limit {}
                )
            '''.format(self._default_notifications_num))
        self._notifications_db.commit()


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
