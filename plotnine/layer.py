from __future__ import annotations

import typing
from copy import copy, deepcopy
from typing import Iterable, List, overload

import pandas as pd

from .exceptions import PlotnineError
from .mapping.aes import NO_GROUP, SCALED_AESTHETICS, aes
from .mapping.evaluation import evaluate, stage
from .utils import array_kind, check_required_aesthetics, ninteraction

if typing.TYPE_CHECKING:
    from typing import Any, Optional, Sequence, SupportsIndex

    from patsy.eval import EvalEnvironment

    import plotnine as p9

    from .geoms.geom import geom
    from .positions.position import position
    from .stats.stat import stat
    from .typing import DataFrameConvertible, DataLike, LayerDataLike


class layer:
    """
    Layer

    When a ``geom`` or ``stat`` is added to a
    :class:`~plotnine.ggplot` object, it creates a single layer.
    This class is a representation of that layer.

    Parameters
    ----------
    geom : geom, optional
        geom to used to draw this layer.
    stat : stat, optional
        stat used for the statistical transformation of
        data in this layer
    mapping : aes, optional
        Aesthetic mappings.
    data : dataframe, optional
        Data plotted in this layer. If ``None``, the data from
        the :class:`~plotnine.ggplot` object will be used.
    position : position, optional
        Position object to adjust the geometries in this layer.
    inherit_aes : bool, optional
        If ``True`` inherit from the aesthetic mappings of
        the :class:`~plotnine.ggplot` object. Default ``True``.
    show_legend : bool or None, optional
        Whether to make up and show a legend for the mappings
        of this layer. If ``None`` then an automatic/good choice
        is made. Default is ``None``.
    raster : bool, optional (default: False)
        If ``True``, draw onto this layer a raster (bitmap) object
        even if the final image format is vector.

    Notes
    -----
    There is no benefit to manually creating a layer. You should
    always use a ``geom`` or ``stat``.
    """
    # Data for this layer
    data: pd.DataFrame

    def __init__(
        self,
        geom: geom,
        stat: stat,
        *,
        mapping: aes,
        data: Optional[LayerDataLike],
        position: position,
        inherit_aes: bool = True,
        show_legend: bool | None = None,
        raster: bool = False
    ) -> None:
        self.geom = geom
        self.stat = stat
        self._data = data
        self.mapping = mapping
        self.position = position
        self.inherit_aes = inherit_aes
        self.show_legend = show_legend
        self.raster = raster
        self.zorder = 0

    @staticmethod
    def from_geom(geom: geom) -> layer:
        """
        Create a layer given a :class:`geom`

        Parameters
        ----------
        geom : geom
            `geom` from which a layer will be created

        Returns
        -------
        out : layer
            Layer that represents the specific `geom`.
        """
        kwargs = geom._kwargs
        lkwargs = {
            'geom': geom,
            'mapping': geom.mapping,
            'data': geom.data,
            'stat': geom._stat,
            'position': geom._position
        }

        layer_params = ('inherit_aes', 'show_legend', 'raster')
        for param in layer_params:
            if param in kwargs:
                lkwargs[param] = kwargs[param]
            elif param in geom.DEFAULT_PARAMS:
                lkwargs[param] = geom.DEFAULT_PARAMS[param]
        return layer(**lkwargs)

    def __radd__(self, gg: p9.ggplot) -> p9.ggplot:
        """
        Add layer to ggplot object
        """
        try:
            gg.layers.append(self)
        except AttributeError:
            msg = "Cannot add layer to object of type {!r}".format
            raise PlotnineError(msg(type(gg)))
        return gg

    def __deepcopy__(self, memo: dict[Any, Any]) -> layer:
        """
        Deep copy without copying the self.data dataframe
        """
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        old = self.__dict__
        new = result.__dict__

        for key, item in old.items():
            if key == 'data':
                new[key] = old[key]
            else:
                new[key] = deepcopy(old[key], memo)

        return result

    def setup(self, plot: p9.ggplot) -> None:
        """
        Prepare layer for the plot building

        Give the layer access to the data, mapping and environment
        """
        self._make_layer_data(plot.data)
        self._make_layer_mapping(plot.mapping)
        self._make_layer_environments(plot.environment)

    def _make_layer_data(self, plot_data: DataLike | None) -> None:
        """
        Generate data to be used by this layer

        Parameters
        ----------
        plot_data : dataframe
            ggplot object data
        """
        if plot_data is None:
            data = pd.DataFrame()
        elif callable(plot_data):
            data = plot_data()
        elif hasattr(plot_data, "to_pandas"):
            data = typing.cast("DataFrameConvertible", plot_data).to_pandas()
        else:
            data = typing.cast("pd.DataFrame", plot_data)

        # Each layer that does not have data gets a copy of
        # of the ggplot.data. If it has data it is replaced
        # by copy so that we do not alter the users data
        if self._data is None:
            try:
                self.data = copy(data)
            except AttributeError:
                _geom_name = self.geom.__class__.__name__
                _data_name = data.__class__.__name__
                raise PlotnineError(
                    f"{_geom_name} layer expects a dataframe, "
                    f"but it got {_data_name} instead."
                )
        elif callable(self._data):
            self.data = self._data(data)
            if not isinstance(self.data, pd.DataFrame):
                raise PlotnineError(
                    "Data function must return a Pandas dataframe"
                )
        else:
            # Recognise polars dataframes
            if hasattr(self._data, "to_pandas"):
                self.data = (
                    typing.cast("DataFrameConvertible", self._data).to_pandas()
                )
            elif isinstance(self._data, pd.DataFrame):
                self.data = self._data.copy()
            else:
                raise TypeError(f"Data has a bad type: {type(self.data)}")

    def _make_layer_mapping(self, plot_mapping: aes) -> None:
        """
        Create the aesthetic mappings to be used by this layer

        Parameters
        ----------
        plot_mapping : aes
            ggplot object mapping
        """
        if self.inherit_aes:
            self.mapping = self.mapping.inherit(plot_mapping)

        # aesthetics set as parameters override the same
        # aesthetics set as mappings, so we can ignore
        # those in the mapping
        for ae in self.geom.aes_params:
            if ae in self.mapping:
                del self.mapping[ae]

        # Set group as a mapping if set as a parameter
        if 'group' in self.geom.aes_params:
            group = self.geom.aes_params['group']
            # Double quote str so that it evaluates to itself
            if isinstance(group, str):
                group = f'"{group}"'
            self.mapping['group'] = stage(start=group)

    def _make_layer_environments(
        self,
        plot_environment: EvalEnvironment
    ) -> None:
        """
        Create the aesthetic mappings to be used by this layer

        Parameters
        ----------
        plot_environment : ~patsy.Eval.EvalEnvironment
            Namespace in which to execute aesthetic expressions.
        """
        self.geom.environment = plot_environment
        self.stat.environment = plot_environment

    def compute_aesthetics(self, plot: p9.ggplot) -> None:
        """
        Return a dataframe where the columns match the aesthetic mappings

        Transformations like 'factor(cyl)' and other
        expression evaluation are  made in here
        """
        evaled = evaluate(self.mapping._starting, self.data, plot.environment)
        evaled_aes = aes(**{str(col): col for col in evaled})
        plot.scales.add_defaults(evaled, evaled_aes)

        if len(self.data) == 0 and len(evaled) > 0:
            # No data, and vectors suppled to aesthetics
            evaled['PANEL'] = 1
        else:
            evaled['PANEL'] = self.data['PANEL']

        data = add_group(evaled)
        self.data = data.sort_values('PANEL', kind='mergesort')

    def compute_statistic(self, layout: p9.facets.layout.Layout) -> None:
        """
        Compute & return statistics for this layer
        """
        data = self.data
        if not len(data):
            return

        params = self.stat.setup_params(data)
        data = self.stat.use_defaults(data)
        data = self.stat.setup_data(data)
        data = self.stat.compute_layer(data, params, layout)
        self.data = data

    def map_statistic(self, plot: p9.ggplot) -> None:
        """
        Mapping aesthetics to computed statistics
        """
        data = self.data
        if not len(data):
            return

        # Mixin default stat aesthetic mappings
        aesthetics = self.mapping.inherit(self.stat.DEFAULT_AES)
        stat_data = evaluate(aesthetics._calculated, data, plot.environment)

        if not len(stat_data):
            return

        # (see stat_spoke for one exception)
        if self.stat.retransform:
            stat_data = plot.scales.transform_df(stat_data)

        # When there are duplicate columns, we use the computed
        # ones in stat_data
        columns = data.columns.difference(stat_data.columns)
        self.data = pd.concat([data[columns], stat_data], axis=1)

        # Add any new scales, if needed
        new = {ae: ae for ae in stat_data.columns}
        plot.scales.add_defaults(self.data, new)

    def setup_data(self) -> None:
        """
        Prepare/modify data for plotting
        """
        data = self.data
        if len(data) == 0:
            return

        data = self.geom.setup_data(data)

        check_required_aesthetics(
            self.geom.REQUIRED_AES,
            set(data.columns) | set(self.geom.aes_params),
            self.geom.__class__.__name__
        )

        self.data = data

    def compute_position(self, layout: p9.facets.layout.Layout) -> None:
        """
        Compute the position of each geometric object

        This is in concert with the other objects in the panel depending
        on the position class of the geom
        """
        if len(self.data) == 0:
            return

        params = self.position.setup_params(self.data)
        data = self.position.setup_data(self.data, params)
        data = self.position.compute_layer(data, params, layout)
        self.data = data

    def draw(
        self,
        layout: p9.facets.layout.Layout,
        coord: p9.coords.coord.coord
    ) -> None:
        """
        Draw geom

        Parameters
        ----------
        layout : Layout
            Layout object created when the plot is getting
            built
        coord : coord
            Type of coordinate axes
        """
        params = copy(self.geom.params)
        params.update(self.stat.params)
        params['zorder'] = self.zorder
        params['raster'] = self.raster
        self.data = self.geom.handle_na(self.data)
        # At this point each layer must have the data
        # that is created by the plot build process
        self.geom.draw_layer(self.data, layout, coord, **params)

    def use_defaults(
        self,
        data: pd.DataFrame | None = None,
        aes_modifiers: dict[str, Any] | None = None
    ) -> pd.DataFrame:
        """
        Prepare/modify data for plotting

        Parameters
        ----------
        data : dataframe, optional
            Data
        aes_modifiers : dict
            Expression to evaluate and replace aesthetics in
            the data.
        """
        if data is None:
            data = self.data

        if aes_modifiers is None:
            aes_modifiers = self.mapping._scaled

        return self.geom.use_defaults(data, aes_modifiers)

    def finish_statistics(self) -> None:
        """
        Prepare/modify data for plotting
        """
        self.stat.finish_layer(self.data, self.stat.params)


class Layers(List[layer]):
    """
    List of layers

    During the plot building pipeline, many operations are
    applied at all layers in the plot. This class makes those
    tasks easier.
    """
    @overload
    def __radd__(self, other: Iterable[layer]) -> Layers: ...

    @overload
    def __radd__(self, other: p9.ggplot) -> p9.ggplot: ...

    def __radd__(
        self,
        other: Iterable[layer] | p9.ggplot
    ) -> Layers | p9.ggplot:
        """
        Add layers to ggplot object
        """
        # Add layers to ggplot object
        from .ggplot import ggplot
        if isinstance(other, ggplot):
            for obj in self:
                other += obj
        else:
            raise PlotnineError(
                f"Cannot add Layers to object of type {type(other)}"
            )
        return other

    @overload
    def __getitem__(self, key: SupportsIndex) -> layer: ...

    @overload
    def __getitem__(self, key: slice) -> Layers: ...

    def __getitem__(
        self,
        key: SupportsIndex | slice
    ) -> layer | Layers:
        result = super().__getitem__(key)
        if isinstance(result, Iterable):
            result = Layers(result)
        return result

    @property
    def data(self) -> list[pd.DataFrame]:
        return [l.data for l in self]

    def setup(self, plot: p9.ggplot) -> None:
        for l in self:
            l.setup(plot)

    def setup_data(self) -> None:
        for l in self:
            l.setup_data()

    def draw(
        self,
        layout: p9.facets.layout.Layout,
        coord: p9.coords.coord.coord
    ) -> None:
        # If zorder is 0, it is left to MPL
        for i, l in enumerate(self, start=1):
            l.zorder = i
            l.draw(layout, coord)

    def compute_aesthetics(self, plot: p9.ggplot) -> None:
        for l in self:
            l.compute_aesthetics(plot)

    def compute_statistic(self, layout: p9.facets.layout.Layout) -> None:
        for l in self:
            l.compute_statistic(layout)

    def map_statistic(self, plot: p9.ggplot) -> None:
        for l in self:
            l.map_statistic(plot)

    def compute_position(self, layout: p9.facets.layout.Layout) -> None:
        for l in self:
            l.compute_position(layout)

    def use_defaults(
        self,
        data: pd.DataFrame | None = None,
        aes_modifiers: dict[str, Any] | None = None
    ) -> None:
        for l in self:
            l.use_defaults(data, aes_modifiers)

    def transform(self, scales: p9.scales.scale.scale) -> None:
        for l in self:
            l.data = scales.transform_df(l.data)

    def train(self, scales: p9.scales.scale.scale) -> None:
        for l in self:
            l.data = scales.train_df(l.data)

    def map(self, scales: p9.scales.scale.scale) -> None:
        for l in self:
            l.data = scales.map_df(l.data)

    def finish_statistics(self) -> None:
        for l in self:
            l.finish_statistics()

    def update_labels(self, plot: p9.ggplot) -> None:
        for l in self:
            plot._update_labels(l)


def add_group(data: pd.DataFrame) -> pd.DataFrame:
    """
    Add group to the dataframe

    The group depends on the interaction of the discrete
    aesthetic columns in the dataframe.
    """
    if len(data) == 0:
        return data

    if 'group' not in data:
        ignore = data.columns.difference(list(SCALED_AESTHETICS))
        disc = discrete_columns(data, ignore=ignore)
        if disc:
            data['group'] = ninteraction(data[disc], drop=True)
        else:
            data['group'] = NO_GROUP
    else:
        data['group'] = ninteraction(data[['group']], drop=True)

    return data


def discrete_columns(
    df: pd.DataFrame,
    ignore: Sequence[str] | pd.Index
) -> list[str]:
    """
    Return a list of the discrete columns in the dataframe

    Parameters
    ----------
    df : dataframe
        Data
    ignore : list[str]
        A list|set|tuple with the names of the columns to skip.
    """
    lst = []
    for col in df:
        if array_kind.discrete(df[col]) and (col not in ignore):
            # Some columns are represented as object dtype
            # but may have compound structures as values.
            try:
                hash(df[col].iloc[0])
            except TypeError:
                continue
            lst.append(str(col))
    return lst
