import numpy as np
import pandas as pd

from ..doctools import document
from ..exceptions import PlotnineError
from ..mapping.evaluation import after_stat
from ..utils import resolution
from .stat import stat


@document
class stat_count(stat):
    """
    Counts the number of cases at each x position

    {usage}

    Parameters
    ----------
    {common_parameters}
    width : float, optional (default: None)
        Bar width. By default, set to 90% of the
        resolution of the data

    See Also
    --------
    plotnine.stats.stat_bin
    """

    _aesthetics_doc = """
    {aesthetics_table}

    .. rubric:: Options for computed aesthetics

    ::

        'count'  # Number of observations at a position
        'prop'   # Ratio of points in the panel at a position

    """

    REQUIRED_AES = {'x'}
    DEFAULT_PARAMS = {'geom': 'histogram', 'position': 'stack',
                      'na_rm': False, 'width': None}
    DEFAULT_AES = {'y': after_stat('count')}
    CREATES = {'count', 'prop'}

    def setup_params(self, data):
        params = self.params.copy()
        if params['width'] is None:
            params['width'] = resolution(data['x'], False) * 0.9

        return params

    @classmethod
    def compute_group(cls, data, scales, **params):
        x = data['x']
        if ('y' in data) or ('y' in params):
            msg = 'stat_count() must not be used with a y aesthetic'
            raise PlotnineError(msg)

        weight = data.get('weight', np.ones(len(x), dtype=int))
        width = params['width']
        df = pd.DataFrame({'weight': weight, 'x': x})
        # weighted frequency count
        count = df.pivot_table(
            'weight', index=['x'], aggfunc=np.sum)['weight']
        x = count.index
        count = count.values
        return pd.DataFrame({'count': count,
                             'prop': count / np.abs(count).sum(),
                             'x': x,
                             'width': width})
