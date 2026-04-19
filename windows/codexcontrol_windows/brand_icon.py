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

    outer_padding = _scale(size, 7)
    corner_radius = _scale(size, 16)
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
    glow_radius = _scale(size, 22)
    center = size / 2
    glow_draw.ellipse(
        (
            center - glow_radius,
            center - glow_radius,
            center + glow_radius,
            center + glow_radius,
        ),
        fill=_hex_to_rgba(glow, 128),
    )
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=max(2, int(size * 0.06))))
    image.alpha_composite(glow_layer)

    draw = ImageDraw.Draw(image)
    ring_padding = center - _scale_float(size, 15.5)
    ring_width = max(2, _scale(size, 6.4))
    ring_bounds = (ring_padding, ring_padding, size - ring_padding, size - ring_padding)
    draw.arc(ring_bounds, start=0, end=359, fill=dark, width=ring_width)
    _draw_arc_with_round_caps(
        draw,
        ring_bounds,
        start_angle=-70.0,
        end_angle=271.5,
        fill=accent,
        width=ring_width,
    )

    hub_radius = _scale_float(size, 6.1)
    draw.ellipse(
        (
            center - hub_radius,
            center - hub_radius,
            center + hub_radius,
            center + hub_radius,
        ),
        fill=dark,
    )

    center_dot_radius = _scale_float(size, 2.65)
    draw.ellipse(
        (
            center - center_dot_radius,
            center - center_dot_radius,
            center + center_dot_radius,
            center + center_dot_radius,
        ),
        fill=core,
    )

    orbit_x = _scale_float(size, 44.9)
    orbit_y = _scale_float(size, 23.4)
    orbit_dot_radius = _scale_float(size, 3.15)
    draw.ellipse(
        (
            orbit_x - orbit_dot_radius,
            orbit_y - orbit_dot_radius,
            orbit_x + orbit_dot_radius,
            orbit_y + orbit_dot_radius,
        ),
        fill=accent,
    )

    if panel_fill:
        border_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        border_draw = ImageDraw.Draw(border_layer)
        border_draw.rounded_rectangle(
            (outer_padding, outer_padding, size - outer_padding, size - outer_padding),
            radius=corner_radius,
            outline=_hex_to_rgba(border, 180),
            width=max(1, _scale(size, 1.25)),
        )
        image.alpha_composite(border_layer)

    return image


def _draw_arc_with_round_caps(
    draw: ImageDraw.ImageDraw,
    bounds: tuple[float, float, float, float],
    *,
    start_angle: float,
    end_angle: float,
    fill: str,
    width: int,
) -> None:
    segments: list[tuple[float, float]]
    if end_angle >= start_angle:
        segments = [(start_angle, end_angle)]
    else:
        segments = [(start_angle, 359.99), (0.0, end_angle)]

    for start, end in segments:
        draw.arc(bounds, start=start, end=end, fill=fill, width=width)

    cap_radius = width / 2
    for angle in (start_angle, end_angle):
        x, y = _point_on_circle(bounds, angle)
        draw.ellipse(
            (
                x - cap_radius,
                y - cap_radius,
                x + cap_radius,
                y + cap_radius,
            ),
            fill=fill,
        )


def _point_on_circle(bounds: tuple[float, float, float, float], angle: float) -> tuple[float, float]:
    left, top, right, bottom = bounds
    center_x = (left + right) / 2
    center_y = (top + bottom) / 2
    radius_x = (right - left) / 2
    radius_y = (bottom - top) / 2
    radians = math.radians(angle)
    return (
        center_x + (radius_x * math.cos(radians)),
        center_y + (radius_y * math.sin(radians)),
    )


def _scale(size: int, value: float) -> int:
    return max(1, int(round(size * (value / 64.0))))


def _scale_float(size: int, value: float) -> float:
    return size * (value / 64.0)


def _hex_to_rgba(value: str, alpha: int) -> tuple[int, int, int, int]:
    value = value.lstrip("#")
    red = int(value[0:2], 16)
    green = int(value[2:4], 16)
    blue = int(value[4:6], 16)
    return red, green, blue, alpha


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
