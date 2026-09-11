"""panel_v3.py -- compatibility shim. The EQ overlay now lives in
structure.py (the backbone). Everything here re-exports from there so
older imports keep working; new code should import structure directly.
"""

import panel as P
from structure import _eq_machine, eq_overlay, eq_display, states  # noqa


def structures(df, PIV=P.PIVOT_BARS, at_formation=False):
    state, hl, lh = P.trend_state(df, PIV, at_formation=at_formation)
    eq, labelled = eq_overlay(df, PIV, at_formation=at_formation)
    both = ((state == "UP") | (state == "DOWN")) & eq
    return dict(state=state, eq=eq, both=both, pivots=labelled,
                hl=hl, lh=lh)
