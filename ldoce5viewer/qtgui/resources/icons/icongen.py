#!/usr/bin/env python2

import sys

from PIL import Image, ImageFilter, ImageChops, ImageEnhance, ImageDraw


OFFSET_S = 4
OFFSET_H = 4


def cast_gradation(img, b1, b2):
    (w, h) = img.size
    pix = img.load()
    for y in xrange(h):
        c = b1 + (b2 - b1) * (float(y) / (h - 1))
        for x in xrange(w):
            pix[x, y] += int(c + 0.5)
    return img


def make_inset_shadow(alpha):
    mc = alpha.copy()
    for i in xrange(6):
        mc = mc.filter(ImageFilter.SMOOTH_MORE)
    mc = ImageChops.subtract(alpha, mc)
    mcb = ImageEnhance.Brightness(mc).enhance(0.35)

    m1 = alpha.copy()
    for i in xrange(6):
        m1 = m1.filter(ImageFilter.SMOOTH_MORE)
    m1 = ImageChops.offset(m1, 0, OFFSET_S)
    m1 = ImageChops.subtract(alpha, m1)
    m1b = ImageEnhance.Brightness(m1).enhance(0.35)

    m = ImageChops.lighter(mc, m1)
    mb = ImageChops.lighter(mcb, m1b)
    return (m, mb)


def make_highlight(alpha):
    mc = alpha.copy()
    for i in xrange(3):
        mc = mc.filter(ImageFilter.SMOOTH_MORE)
    mc = ImageChops.subtract(mc, alpha)
    mcb = ImageEnhance.Brightness(mc).enhance(0.35)

    m1 = alpha.copy()
    for i in xrange(2):
        m1 = m1.filter(ImageFilter.SMOOTH_MORE)
    m1 = ImageChops.offset(m1, 0, OFFSET_H)
    m1 = ImageChops.subtract(m1, alpha)
    m1b = ImageEnhance.Brightness(m1).enhance(0.35)

    m = ImageChops.lighter(mc, m1)
    mb = ImageChops.lighter(mcb, m1b)

    return (m, mb)


def make(src_path, out_path):
    src = Image.open(src_path)
    src = src.copy()
    (srcr, srcg, srcb, srca) = src.split()
    white = ImageChops.constant(src, 255)

    outr = cast_gradation(srcr, 0, 90)
    outg = cast_gradation(srcg, 0, 90)
    outb = cast_gradation(srcb, 0, 90)
    outa = srca.copy()

    outr = ImageChops.composite(srcr, white, srca)
    outg = ImageChops.composite(srcg, white, srca)
    outb = ImageChops.composite(srcb, white, srca)

    (shadow_a, shadow) = make_inset_shadow(srca)
    outr = ImageChops.subtract(outr, shadow, 1, 0)
    outg = ImageChops.subtract(outg, shadow, 1, 0)
    outb = ImageChops.subtract(outb, shadow, 1, 0)
    outa = ImageChops.lighter(outa, shadow_a)

    (highlight_a, highlight) = make_highlight(srca)
    outa = ImageChops.lighter(outa, highlight)

    outa = ImageChops.subtract(outa, ImageChops.constant(outa, 25), 1, 0)

    out = Image.merge('RGBA', (outr, outg, outb, outa))
    out.save(out_path)


if __name__ == "__main__":
    src_path = sys.argv[1]
    out_path = sys.argv[2]
    make(src_path, out_path)

