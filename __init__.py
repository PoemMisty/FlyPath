import os


def classFactory(iface):
    from .flypath_i18n import install
    install(os.path.dirname(__file__))
    from .flypath import FlyPath
    return FlyPath(iface)
