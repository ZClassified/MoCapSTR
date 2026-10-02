"""
Per-user folders of MoCapSTR (independent of the working directory the app is started from).

    config_dir()  %APPDATA%\\MoCapSTR        settings.json, presets.json, export_settings.json
    data_dir()    %LOCALAPPDATA%\\MoCapSTR   instance.pid
    logs_dir()    %LOCALAPPDATA%\\MoCapSTR\\logs
"""
import os
import shutil
import sys

APP_NAME = "MoCapSTR"


def _base(env_var):
    root = os.environ.get(env_var) or os.path.join(os.path.expanduser("~"), ".mocapstr")
    return os.path.join(root, APP_NAME) if os.environ.get(env_var) else root


def config_dir():
    path = _base("APPDATA")
    os.makedirs(path, exist_ok=True)
    return path


def data_dir():
    path = _base("LOCALAPPDATA")
    os.makedirs(path, exist_ok=True)
    return path


def logs_dir():
    path = os.path.join(data_dir(), "logs")
    os.makedirs(path, exist_ok=True)
    return path


def config_file(filename):
    """
    Path of a settings file in config_dir(). Files that versions <= 1.5.1 wrote
    into the working directory (or next to the app) are copied over once.
    """
    target = os.path.join(config_dir(), filename)
    if not os.path.exists(target):
        app_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) \
            else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for legacy in (os.path.join(os.getcwd(), filename), os.path.join(app_dir, filename)):
            if os.path.isfile(legacy):
                try:
                    shutil.copy2(legacy, target)
                except OSError:
                    pass
                break
    return target
