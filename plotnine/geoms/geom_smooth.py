from __future__ import annotations

import typing

from matplotlib.patches import Rectangle

from ..doctools import document
from .geom import geom
from .geom_line import geom_line, geom_path
from .geom_ribbon import geom_ribbon

if typing.TYPE_CHECKING:
    from typing import Any

    import matplotlib as mpl
    import pandas as pd

    import plotnine as p9


@document
class geom_smooth(geom):
    """
    A smoothed conditional mean

    {usage}

    Parameters
    ----------
    {common_parameters}
    legend_fill_ratio : float (default: 0.5)
        How much (vertically) of the legend box should be filled by
        the color that indicates the confidence intervals. Should be
        in the range [0, 1].
    """
    DEFAULT_AES = {'alpha': 0.4, 'color': 'black', 'fill': '#999999',
                   'linetype': 'solid', 'size': 1,
                   'ymin': None, 'ymax': None}
    REQUIRED_AES = {'x', 'y'}
    DEFAULT_PARAMS = {'stat': 'smooth', 'position': 'identity',
                      'na_rm': False, 'legend_fill_ratio': 0.5}

    def use_defaults(
        self,
        data: pd.DataFrame,
        aes_modifiers: dict[str, Any]
    ) -> pd.DataFrame:
        has_ribbon = 'ymin' in data and 'ymax' in data
        data = super().use_defaults(data, aes_modifiers)

        # When there is no ribbon, the default values for 'ymin'
        # and 'ymax' are None (not numeric). So we remove them
        # prevent any computations that may use them without checking.
        if not has_ribbon:
            del data['ymin']
            del data['ymax']
        return data

    def setup_data(self, data: pd.DataFrame) -> pd.DataFrame:
        return data.sort_values(['PANEL', 'group', 'x'])

    @staticmethod
    def draw_group(
        data: pd.DataFrame,
        panel_params: p9.iapi.panel_view,
        coord: p9.coords.coord.coord,
        ax: mpl.axes.Axes,
        **params: Any
    ) -> None:
        has_ribbon = 'ymin' in data and 'ymax' in data
        if has_ribbon:
            data2 = data.copy()
            data2['color'] = 'none'
            params2 = params.copy()
            params2['outline_type'] = 'full'
            geom_ribbon.draw_group(data2, panel_params,
                                   coord, ax, **params2)

        data['alpha'] = 1
        geom_line.draw_group(data, panel_params, coord, ax, **params)

    @staticmethod
    def draw_legend(
        data: pd.Series[Any],
        da: mpl.patches.DrawingArea,
        lyr: p9.layer.layer
    ) -> mpl.patches.DrawingArea:
        """
        Draw letter 'a' in the box

        Parameters
        ----------
        data : dataframe
            Legend data
        da : DrawingArea
            Canvas
        lyr : layer
            Layer

        Returns
        -------
        out : DrawingArea
        """
        assert lyr.stat is not None
        assert lyr.geom is not None

        try:
            has_se = lyr.stat.params['se']
        except KeyError:
            has_se = False

        if has_se:
            r = lyr.geom.params['legend_fill_ratio']
            bg = Rectangle(
                (0, (1-r)*da.height/2),
                width=da.width,
                height=r*da.height,
                alpha=data['alpha'],
                facecolor=data['fill'],
                linewidth=0
            )
            da.add_artist(bg)

        data['alpha'] = 1
        return geom_path.draw_legend(data, da, lyr)
