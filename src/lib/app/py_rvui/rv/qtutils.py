#
# Copyright (C) 2023  Autodesk, Inc. All Rights Reserved.
#
# SPDX-License-Identifier: Apache-2.0
#
import rv.commands

try:
    from PySide2 import QtGui, QtWidgets
    from shiboken2 import getCppPointer, wrapInstance
except ImportError:
    try:
        from PySide6 import QtGui, QtWidgets
        from shiboken6 import getCppPointer, wrapInstance
    except ImportError:
        pass


def __getattr__(name):
    # Resolve the public Qt classes only when requested. Expanding both modules
    # with wildcard imports constructs hundreds of unused binding types.
    if not name.startswith("_"):
        for module in (globals().get("QtWidgets"), globals().get("QtGui")):
            if module is not None:
                try:
                    value = getattr(module, name)
                except AttributeError:
                    continue
                globals()[name] = value
                return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    names = set(globals())
    for module in (globals().get("QtGui"), globals().get("QtWidgets")):
        if module is not None:
            names.update(getattr(module, "__all__", dir(module)))
    return sorted(names)


def sessionWindow():
    """
    Returns the QMainWindow for the current RV session window.
    """

    rvPyLongPtr = rv.commands.sessionWindow()
    if rvPyLongPtr is not None:
        return wrapInstance(rvPyLongPtr, QtWidgets.QMainWindow)
    else:
        return None


def sessionGLView():
    """
    Returns the QOpenGLWidget for the current RV session GL view.
    """

    rvPyLongPtr = rv.commands.sessionGLView()
    if rvPyLongPtr is not None:
        return wrapInstance(rvPyLongPtr, QtWidgets.QOpenGLWidget)
    else:
        return None


def sessionTopToolBar():
    """
    Returns the QToolBar for the current RV session top tool bar.
    """

    rvPyLongPtr = rv.commands.sessionTopToolBar()
    if rvPyLongPtr is not None:
        return wrapInstance(rvPyLongPtr, QtWidgets.QToolBar)
    else:
        return None


def sessionBottomToolBar():
    """
    Returns the QToolBar for the current RV session bottom tool bar.
    """

    rvPyLongPtr = rv.commands.sessionBottomToolBar()
    if rvPyLongPtr is not None:
        return wrapInstance(rvPyLongPtr, QtWidgets.QToolBar)
    else:
        return None


def javascriptExport(webFrame):
    """
    Add the "rvsession" object to the JavaScript instance of the given
    QWebFrame, connecting it to RV's event system and scripting layers.
    """

    from rv import runtime

    runtime.setup_webview_default_profile()
    rvPyLongPtrs = getCppPointer(webFrame)
    rv.commands.javascriptExport(rvPyLongPtrs[0])


# Preserve from-import and wildcard compatibility for existing packages.
__all__ = [name for name in __dir__() if not name.startswith("_")]
