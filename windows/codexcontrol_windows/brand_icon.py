from __future__ import annotations

import math

from PIL import Image, ImageDraw, ImageFilter


def build_orbit_dial_icon(
    size: int,
    *,
    accent: str,
    core: str = "#ff4a4a",
    panel_fill: str = "#171d24",
    panel_fill_end: str = "#0b1015",
    dark: str = "#121820",
    border: str = "#29323c",
    glow: str = "#0d1611",
) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    gradient = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gradient_draw = ImageDraw.Draw(gradient)
    top_rgb = _hex_to_rgb(panel_fill)
    bottom_rgb = _hex_to_rgb(panel_fill_end)
    for y in range(size):
        mix = y / max(1, size - 1)
        rgb = tuple(int(top_rgb[idx] + (bottom_rgb[idx] - top_rgb[idx]) * mix) for idx in range(3))
        gradient_draw.line((0, y, size, y), fill=rgb + (255,))

    outer_padding = max(2, int(size * 0.08))
    corner_radius = max(8, int(size * 0.24))
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle(
        (outer_padding, outer_padding, size - outer_padding, size - outer_padding),
        radius=corner_radius,
        fill=255,
    )
    image.paste(gradient, mask=mask)

    glow_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)
    glow_radius = int(size * 0.28)
    center = size / 2
    glow_draw.ellipse(
        (
            center - glow_radius,
            center - glow_radius,
            center + glow_radius,
            center + glow_radius,
        ),
        fill=_hex_to_rgba(glow, 92),
    )
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=max(2, size * 0.05)))
    image.alpha_composite(glow_layer)

    draw = ImageDraw.Draw(image)
    ring_padding = int(size * 0.258)
    ring_width = max(2, int(size * 0.1))
    ring_bounds = (ring_padding, ring_padding, size - ring_padding, size - ring_padding)
    draw.arc(ring_bounds, start=0, end=359, fill=dark, width=ring_width)
    draw.arc(ring_bounds, start=-58, end=64, fill=accent, width=ring_width)

    hub_radius = size * 0.095
    draw.ellipse(
        (
            center - hub_radius,
            center - hub_radius,
            center + hub_radius,
            center + hub_radius,
        ),
        fill=dark,
    )

    center_dot_radius = size * 0.037
    draw.ellipse(
        (
            center - center_dot_radius,
            center - center_dot_radius,
            center + center_dot_radius,
            center + center_dot_radius,
        ),
        fill=core,
    )

    orbit_radius = size * 0.24
    orbit_angle = math.radians(-34)
    orbit_x = center + math.cos(orbit_angle) * orbit_radius
    orbit_y = center + math.sin(orbit_angle) * orbit_radius
    orbit_dot_radius = size * 0.049
    draw.ellipse(
        (
            orbit_x - orbit_dot_radius,
            orbit_y - orbit_dot_radius,
            orbit_x + orbit_dot_radius,
            orbit_y + orbit_dot_radius,
        ),
        fill=dark,
    )

    if panel_fill:
        border = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        border_draw = ImageDraw.Draw(border)
        border_draw.rounded_rectangle(
            (outer_padding, outer_padding, size - outer_padding, size - outer_padding),
            radius=corner_radius,
            outline=_hex_to_rgba(border, 180),
            width=max(1, int(size * 0.03)),
        )
        image.alpha_composite(border)

    return image


def _hex_to_rgba(value: str, alpha: int) -> tuple[int, int, int, int]:
    value = value.lstrip("#")
    red = int(value[0:2], 16)
    green = int(value[2:4], 16)
    blue = int(value[4:6], 16)
    return red, green, blue, alpha


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
