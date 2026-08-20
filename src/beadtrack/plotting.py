"""Matplotlib display and style helpers."""

from tkinter import TclError

import matplotlib.pyplot as plt

__all__ = ["apply_plot_scale", "maximize_current_figure"]


def apply_plot_scale(scale: float) -> None:
    """Scale the main Matplotlib typography and line-width settings."""
    if scale <= 0:
        raise ValueError("scale must be positive")

    plt.rcParams.update(
        {
            "font.size": 14 * scale,
            "axes.titlesize": 18 * scale,
            "axes.labelsize": 16 * scale,
            "xtick.labelsize": 13 * scale,
            "ytick.labelsize": 13 * scale,
            "legend.fontsize": 13 * scale,
            "lines.linewidth": 2.0 * scale,
            "grid.linewidth": 0.8 * scale,
        }
    )


def maximize_current_figure() -> bool:
    """Maximize the current figure when supported; return whether it succeeded."""
    manager = plt.get_current_fig_manager()
    if manager is None:
        return False

    window = getattr(manager, "window", None)
    if window is not None:
        for method_name, arguments in (("showMaximized", ()), ("state", ("zoomed",))):
            method = getattr(window, method_name, None)
            if callable(method):
                try:
                    method(*arguments)
                    return True
                except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
                    continue

    toggle_fullscreen = getattr(manager, "full_screen_toggle", None)
    if callable(toggle_fullscreen):
        try:
            toggle_fullscreen()
            return True
        except (AttributeError, RuntimeError, TclError, TypeError, ValueError):
            pass

    return False
