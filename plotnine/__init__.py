from importlib.metadata import PackageNotFoundError, version

from .coords import *  # noqa: F401,F403,E261
from .facets import *  # noqa: F401,F403,E261
from .geoms import *  # noqa: F401,F403,E261
from .ggplot import (  # noqa: F401
    ggplot,
    ggsave,
    save_as_pdf_pages,  # noqa: F401
)
from .guides import *  # noqa: F401,F403,E261
from .labels import *  # noqa: F401,F403,E261
from .mapping import *  # noqa: F401,F403,E261
from .positions import *  # noqa: F401,F403,E261
from .qplot import qplot  # noqa: F401
from .scales import *  # noqa: F401,F403,E261
from .stats import *  # noqa: F401,F403,E261
from .themes import *  # noqa: F401,F403,E261
from .watermark import watermark  # noqa: F401

try:
    __version__ = version('plotnine')
except PackageNotFoundError:
    # package is not installed
    pass
finally:
    del version
    del PackageNotFoundError


def _get_all_imports():
    """
    Return list of all the imports

    This prevents sub-modules (geoms, stats, utils, ...)
    from being imported into the user namespace by the
    following import statement

        from plotnine import *

    This is because `from Module import Something`
    leads to `Module` itself coming into the namespace!!
    """
    from types import ModuleType
    lst = [
        name
        for name, obj in globals().items()
        if not (name.startswith('_') or isinstance(obj, ModuleType))
    ]
    return lst


__all__ = _get_all_imports()
