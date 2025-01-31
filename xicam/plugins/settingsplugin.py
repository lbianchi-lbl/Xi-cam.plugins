from typing import List
from qtpy.QtCore import QObject, QSettings
from yapsy.IPlugin import IPlugin
from xicam import plugins
from pyqtgraph.parametertree import ParameterTree
from pyqtgraph.parametertree.parameterTypes import GroupParameter
import cloudpickle as pickle
from xicam.core import msg


class SettingsPlugin(QObject, IPlugin):
    def __new__(cls, *args, **kwargs):
        if not plugins.qt_is_safe:
            return None
        return super(SettingsPlugin, cls).__new__(cls, *args, **kwargs)

    def __init__(self, icon, name, widget):
        super(SettingsPlugin, self).__init__()
        self.icon = icon
        self._name = name
        self._widget = widget

    @property
    def widget(self):
        return self._widget

    @widget.setter
    def widget(self, widget):
        self._widget = widget

    def name(self):
        return self._name

    def apply(self):
        ...

    def toState(self):
        self.apply()
        ...

    def fromState(self, state):
        ...

    def save(self):
        QSettings().setValue(self.name(), pickle.dumps(self.toState()))

    def restore(self):
        try:
            self.fromState(pickle.loads(QSettings().value(self.name())))
        except (AttributeError, TypeError, SystemError, KeyError, ModuleNotFoundError) as ex:
            # No settings saved
            msg.logError(ex)
            msg.logMessage(
                f"Could not restore settings for {self.name} plugin; re-initializing settings...", level=msg.WARNING
            )


class ParameterSettingsPlugin(GroupParameter, SettingsPlugin):
    def __init__(self, icon, name: str, paramdicts: List[dict], **kwargs):
        SettingsPlugin.__init__(self, icon, name, None)
        GroupParameter.__init__(self, name=name, type="group", children=paramdicts, **kwargs)
        self.restore()

    name = SettingsPlugin.name  # must be re-overridden because of GroupParameter

    @property
    def widget(self):
        widget = ParameterTree()
        widget.setParameters(self, showTop=False)
        return widget

    def apply(self):
        pass

    def toState(self):
        self.apply()
        return self.saveState(filter="user")

    def fromState(self, state):
        self.restoreState(state, addChildren=False, removeChildren=False)
