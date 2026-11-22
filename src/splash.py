"""Ekran startowy: tło rysowane w kodzie (chmura nad mozaiką zdjęć), jasne albo ciemne według motywu
systemu, z nazwą programu i autorami (bez numeru wersji)."""
import math
import random

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

W, H = 720, 420
MIN_MS = 1400  # tyle co najmniej widać ekran startowy

PALETTE = {
    False: dict(bg0=(0.96, 0.95, 1.0), bg1=(0.92, 0.97, 1.0), tile=((0.49, 0.36, 1.0), (0.13, 0.72, 0.90),
                (1.0, 0.62, 0.45), (0.98, 0.78, 0.35), (0.45, 0.80, 0.55)), tile_a=0.30,
                cloud=(1, 1, 1), cloud_a=0.92, title=(0.12, 0.10, 0.23), sub=(0.35, 0.33, 0.50)),
    True: dict(bg0=(0.05, 0.06, 0.10), bg1=(0.10, 0.07, 0.18), tile=((0.66, 0.33, 0.97), (0.13, 0.83, 0.93),
               (0.95, 0.45, 0.55), (0.98, 0.70, 0.30), (0.30, 0.75, 0.55)), tile_a=0.28,
               cloud=(0.16, 0.18, 0.30), cloud_a=0.90, title=(0.93, 0.92, 1.0), sub=(0.66, 0.70, 0.85)),
}


def _rounded(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def draw(cr, w, h, dark):
    import cairo

    p = PALETTE[dark]
    g = cairo.LinearGradient(0, 0, w, h)
    g.add_color_stop_rgb(0, *p["bg0"])
    g.add_color_stop_rgb(1, *p["bg1"])
    _rounded(cr, 0, 0, w, h, 18)
    cr.set_source(g)
    cr.fill_preserve()
    cr.save()
    cr.clip()
    # mozaika „zdjęć” po prawej, lekko obrócona
    rnd = random.Random(7)
    cr.save()
    cr.translate(w * 0.68, -40)
    cr.rotate(0.18)
    size, gap = 70, 10
    for row in range(8):
        for col in range(6):
            c = p["tile"][rnd.randrange(len(p["tile"]))]
            x, y = col * (size + gap), row * (size + gap)
            tg = cairo.LinearGradient(x, y, x + size, y + size)
            tg.add_color_stop_rgba(0, *c, p["tile_a"] + 0.18)
            tg.add_color_stop_rgba(1, *c, p["tile_a"] * 0.5)
            _rounded(cr, x, y, size, size, 12)
            cr.set_source(tg)
            cr.fill()
    cr.restore()
    # poświata
    for (cx, cy, rad, c, a) in ((w * 0.15, h * 0.05, 340, p["tile"][1], 0.22),
                                (w * 0.95, h * 1.05, 360, p["tile"][0], 0.26)):
        rg = cairo.RadialGradient(cx, cy, 0, cx, cy, rad)
        rg.add_color_stop_rgba(0, *c, a)
        rg.add_color_stop_rgba(1, *c, 0)
        cr.set_source(rg)
        cr.paint()
    # chmura (logo) po lewej
    cx, cy = 150, 150
    cr.set_source_rgba(*p["cloud"], p["cloud_a"])
    for (dx, dy, r) in ((-48, 10, 38), (-8, -18, 52), (44, 4, 40), (0, 22, 44)):
        cr.arc(cx + dx, cy + dy, r, 0, 2 * math.pi)
        cr.fill()
    _rounded(cr, cx - 86, cy + 4, 172, 58, 29)
    cr.fill()
    # mały „obrazek” w chmurze
    cg = cairo.LinearGradient(cx - 30, cy - 10, cx + 30, cy + 40)
    cg.add_color_stop_rgb(0, *p["tile"][0])
    cg.add_color_stop_rgb(1, *p["tile"][1])
    _rounded(cr, cx - 32, cy - 6, 64, 48, 9)
    cr.set_source(cg)
    cr.fill()
    cr.set_source_rgba(1, 1, 1, 0.9)
    cr.move_to(cx - 26, cy + 36)
    cr.line_to(cx - 8, cy + 14)
    cr.line_to(cx + 4, cy + 26)
    cr.line_to(cx + 14, cy + 18)
    cr.line_to(cx + 26, cy + 36)
    cr.close_path()
    cr.fill()
    cr.arc(cx + 16, cy + 4, 5, 0, 2 * math.pi)
    cr.fill()
    cr.restore()
    # napisy
    cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    cr.set_font_size(34)
    cr.set_source_rgb(*p["title"])
    cr.move_to(48, 286)
    cr.show_text("Linux iCloud Photos")
    cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    cr.set_font_size(15)
    cr.set_source_rgb(*p["sub"])
    cr.move_to(50, 322)
    cr.show_text("Created by: JGu")
    cr.move_to(50, 346)
    cr.show_text("Supported by Claude")


class Splash(Gtk.Window):
    def __init__(self, app):
        super().__init__(application=app, title="Linux iCloud Photos", decorated=False, resizable=False,
                         default_width=W, default_height=H)
        self.add_css_class("splash")
        css = Gtk.CssProvider()
        css.load_from_string("window.splash, window.splash > * { background: transparent; box-shadow: none; }")
        Gtk.StyleContext.add_provider_for_display(self.get_display(), css,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 5)
        self.dark = Adw.StyleManager.get_default().get_dark()
        area = Gtk.DrawingArea(content_width=W, content_height=H)
        area.set_draw_func(lambda _a, cr, w, h: draw(cr, w, h, self.dark))
        self.set_child(area)
        self._t0 = GLib.get_monotonic_time()

    def finish(self, then):
        """Zamknij po co najmniej MIN_MS od pokazania, potem wywołaj then()."""
        left = MIN_MS - (GLib.get_monotonic_time() - self._t0) // 1000

        def go():
            then()
            self.close()
            return False

        GLib.timeout_add(max(0, int(left)), go)
