"""Иконка приложения: распиливаем `mobile/assets/brand/icon-master.png` на
все нужные форматы для Android (mipmap + adaptive icon).

Запускать локально, не на CI. Изменения коммитятся в репо как обычно.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
MASTER = ROOT / "mobile" / "assets" / "brand" / "icon-master.png"
RES = ROOT / "mobile" / "android" / "app" / "src" / "main" / "res"

# Стандартные плотности Android — px на 48dp.
DENSITIES = {
    "mdpi": 48,
    "hdpi": 72,
    "xhdpi": 96,
    "xxhdpi": 144,
    "xxxhdpi": 192,
}

# Adaptive icon: каждый layer 108dp в полный размер.
ADAPTIVE_DENSITIES = {
    "mdpi": 108,
    "hdpi": 162,
    "xhdpi": 216,
    "xxhdpi": 324,
    "xxxhdpi": 432,
}

BG_COLOR = (9, 9, 11, 255)  # #09090B как у нас в дизайн-системе
SAFE_ZONE_RATIO = 0.66  # safe zone 72dp из 108dp


def round_corners(img: Image.Image, radius_pct: float = 0.22) -> Image.Image:
    """Применяем мягкие скругления для legacy round-icon (некоторые лаунчеры
    игнорируют пути и рисуют квадрат → дадим сами квадрат с округлёнными)."""
    w, h = img.size
    radius = int(min(w, h) * radius_pct)
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle((0, 0, w, h), radius=radius, fill=255)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste(img.convert("RGBA"), (0, 0), mask)
    return out


def make_circle(img: Image.Image) -> Image.Image:
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse((0, 0, w, h), fill=255)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste(img.convert("RGBA"), (0, 0), mask)
    return out


def main() -> None:
    if not MASTER.exists():
        raise SystemExit(f"icon-master.png not found at {MASTER}")
    print(f"Loading master: {MASTER}")
    master = Image.open(MASTER).convert("RGB")
    print(f"  size: {master.size}")

    # Чистим старые иконки
    for d in DENSITIES:
        folder = RES / f"mipmap-{d}"
        folder.mkdir(parents=True, exist_ok=True)
        for fname in ("ic_launcher.png", "ic_launcher_round.png",
                       "ic_launcher_foreground.png"):
            p = folder / fname
            if p.exists():
                p.unlink()

    # 1. Legacy ic_launcher.png + ic_launcher_round.png (квадрат и круглая
    #    маска для всех плотностей).
    for density, px in DENSITIES.items():
        folder = RES / f"mipmap-{density}"
        sq = master.resize((px, px), Image.LANCZOS)
        sq.save(folder / "ic_launcher.png", optimize=True)

        rounded = round_corners(sq, radius_pct=0.22)
        rounded.save(folder / "ic_launcher_round.png", optimize=True)

        print(f"  mipmap-{density}: {px}x{px}")

    # 2. Adaptive icon foreground: контент в safe zone (66% от 108dp).
    #    Обратный паддинг создаёт прозрачные поля, которые лаунчер обрежет
    #    своей маской (круг/сквиркл) поверх background.
    for density, full_px in ADAPTIVE_DENSITIES.items():
        folder = RES / f"mipmap-{density}"
        canvas = Image.new("RGBA", (full_px, full_px), (0, 0, 0, 0))
        content_px = int(full_px * SAFE_ZONE_RATIO)
        scaled = master.resize((content_px, content_px), Image.LANCZOS).convert("RGBA")
        offset = (full_px - content_px) // 2
        canvas.paste(scaled, (offset, offset))
        canvas.save(folder / "ic_launcher_foreground.png", optimize=True)
        print(f"  fg mipmap-{density}: {content_px}px content on {full_px}px canvas")

    # 3. Adaptive background — solid color resource.
    values = RES / "values"
    values.mkdir(parents=True, exist_ok=True)
    colors_xml = values / "ic_launcher_colors.xml"
    colors_xml.write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<resources>\n'
        '    <color name="ic_launcher_background">#09090B</color>\n'
        '</resources>\n',
        encoding="utf-8",
    )
    print(f"  {colors_xml.relative_to(ROOT)}")

    # 4. Adaptive icon XML (Android 8+).
    anydpi = RES / "mipmap-anydpi-v26"
    anydpi.mkdir(parents=True, exist_ok=True)
    adaptive_xml = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
        '    <background android:drawable="@color/ic_launcher_background"/>\n'
        '    <foreground android:drawable="@mipmap/ic_launcher_foreground"/>\n'
        '</adaptive-icon>\n'
    )
    (anydpi / "ic_launcher.xml").write_text(adaptive_xml, encoding="utf-8")
    (anydpi / "ic_launcher_round.xml").write_text(adaptive_xml, encoding="utf-8")
    print(f"  {(anydpi / 'ic_launcher.xml').relative_to(ROOT)}")
    print(f"  {(anydpi / 'ic_launcher_round.xml').relative_to(ROOT)}")

    # 5. RuStore / Google Play listing — мастер 512×512.
    listing = ROOT / "deploy" / "store_assets"
    listing.mkdir(parents=True, exist_ok=True)
    master_512 = master.resize((512, 512), Image.LANCZOS)
    master_512.save(listing / "icon-512.png", optimize=True)
    print(f"  {(listing / 'icon-512.png').relative_to(ROOT)}")

    # 6. Лендинг: сохранить на одну из стандартных позиций
    landing = ROOT / "landing" / "assets"
    landing.mkdir(parents=True, exist_ok=True)
    master_192 = master.resize((192, 192), Image.LANCZOS)
    master_192.save(landing / "icon-192.png", optimize=True)
    print(f"  {(landing / 'icon-192.png').relative_to(ROOT)}")

    print("\nDone. flutter clean + rebuild APK to apply.")


if __name__ == "__main__":
    main()
