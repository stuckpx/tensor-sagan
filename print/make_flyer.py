#!/usr/bin/env python3
"""Generate print-ready A6 subscriber cards for masjid distribution.

Produces two PDFs in this directory:

  flyer-a6-bleed.pdf   111x154mm — A6 trim (105x148) plus 3mm bleed on all
                       sides. This is what a print shop wants.
  flyer-a6-4up.pdf     A4 with four cards tiled 2x2. Four A6 cards tile A4
                       almost exactly (210x296 of 210x297), so this is the
                       DIY option: print on card stock and guillotine along
                       the centre lines.

The QR points at ?utm_source=masjid so print traffic is separable from
everything else once analytics are live.

Usage:  .venv/bin/python3 print/make_flyer.py
Requires: segno (QR), and Google Chrome for HTML->PDF.
"""

import os
import re
import shutil
import subprocess
import sys

import segno

HERE = os.path.dirname(os.path.abspath(__file__))
SUBSCRIBE_URL = "https://www.haramainfridays.com/?utm_source=masjid"
DISPLAY_URL = "haramainfridays.com"

GREEN = "#0d5c3f"
GOLD = "#c89d2a"
INK = "#1c1c1c"
MUTED = "#5a5a5a"

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def qr_svg() -> str:
    """Inline QR as an <svg> sized by CSS. High EC so scuffs don't kill it."""
    path = os.path.join(HERE, "qr-masjid.svg")
    segno.make(SUBSCRIBE_URL, error="h").save(
        path, kind="svg", scale=10, border=0, dark=GREEN)
    svg = open(path, encoding="utf-8").read()
    svg = re.sub(r"<\?xml[^>]*\?>\s*", "", svg)
    # Let CSS drive the size; keep the aspect via viewBox.
    return svg.replace(
        '<svg xmlns="http://www.w3.org/2000/svg" width="410" height="410"',
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 410 410"'
        ' preserveAspectRatio="xMidYMid meet"', 1)


def card_html(qr: str) -> str:
    """One card's markup. Sized by its container so it can be tiled."""
    return f"""
  <div class="card">
    <div class="band">
      <div class="ar">الجمعة المباركة</div>
      <div class="brand">HARAMAIN FRIDAYS</div>
    </div>
    <div class="body">
      <h1>Missed Jumu&#8217;ah at<br>the Haramain?</h1>
      <p class="lede">
        Read a short summary of <strong>both</strong> Friday khutbahs &mdash;
        from Masjid al-Haram and Masjid an-Nabawi &mdash; in your inbox
        every week.
      </p>
      <div class="qr-wrap">
        <div class="qr">{qr}</div>
        <div class="qr-label">
          <div class="scan">Scan to subscribe</div>
          <div class="url">{DISPLAY_URL}</div>
        </div>
      </div>
      <div class="foot">Free &nbsp;&middot;&nbsp; No ads &nbsp;&middot;&nbsp; Unsubscribe anytime</div>
    </div>
  </div>"""


# Card metrics are shared by both layouts; only the page setup differs.
CARD_CSS = f"""
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{ width: 100%; height: 100%; }}
  body {{
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    color: {INK};
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }}
  .card {{
    width: 105mm; height: 148mm;
    background: #ffffff;
    display: flex; flex-direction: column;
    overflow: hidden;
    position: relative;
  }}
  /* Gold hairline under the band reads as a rule in mono printing too. */
  .band {{
    background: {GREEN};
    color: #ffffff;
    padding: 7mm 8mm 6mm;
    text-align: center;
    border-bottom: 1.2mm solid {GOLD};
  }}
  .ar {{
    font-family: "Geeza Pro", "Al Bayan", "Baghdad", serif;
    font-size: 15pt; line-height: 1.5; margin-bottom: 1.5mm;
  }}
  .brand {{
    font-size: 8.5pt; letter-spacing: 0.22em; font-weight: 600;
    text-transform: uppercase; opacity: 0.92;
  }}
  .body {{
    flex: 1;
    padding: 7mm 9mm 6mm;
    display: flex; flex-direction: column; align-items: center;
    text-align: center;
  }}
  h1 {{
    font-size: 17pt; line-height: 1.25; color: {GREEN};
    font-weight: 700; letter-spacing: -0.01em;
  }}
  .lede {{
    font-size: 9.5pt; line-height: 1.55; color: {MUTED};
    margin-top: 3.5mm; max-width: 78mm;
  }}
  .lede strong {{ color: {INK}; font-weight: 600; }}
  /* auto on both sides splits the slack above and below the QR block */
  .qr-wrap {{
    margin-top: auto; margin-bottom: auto;
    display: flex; flex-direction: column; align-items: center;
  }}
  /* Quiet zone around the QR is required for reliable scanning. */
  .qr {{
    width: 34mm; height: 34mm;
    padding: 2.5mm; background: #ffffff;
    border: 0.4mm solid #d8d8d8;
  }}
  .qr svg {{ width: 100%; height: 100%; display: block; }}
  .qr-label {{ margin-top: 3mm; }}
  .scan {{ font-size: 8.5pt; color: {MUTED}; letter-spacing: 0.03em; }}
  .url {{
    font-size: 11.5pt; font-weight: 700; color: {GREEN};
    margin-top: 1mm; letter-spacing: 0.01em;
  }}
  .foot {{
    font-size: 7.5pt; color: {MUTED};
    border-top: 0.3mm solid #e2e2e2;
    padding-top: 3mm; width: 100%;
  }}
"""


def single_html(qr: str) -> str:
    """A6 + 3mm bleed.

    Bleed has to continue whatever colour sits at each trim edge, or a trim
    that drifts by a fraction leaves a contrasting sliver. The card is white
    at its sides and foot, so the bleed sheet is white; the green band is the
    only thing that reaches an edge, so it alone is pulled out into the bleed.
    """
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
  @page {{ size: 111mm 154mm; margin: 0; }}
{CARD_CSS}
  .bleed {{
    width: 111mm; height: 154mm;
    background: #ffffff;
    padding: 3mm;
  }}
  .bleed .band {{
    margin: -3mm -3mm 0 -3mm;   /* run green off the top and upper sides */
    padding-top: 10mm;
  }}
</style></head><body>
<div class="bleed">{card_html(qr)}</div>
</body></html>"""


def fourup_html(qr: str) -> str:
    """2x2 on A4 for DIY printing; hairlines mark the cuts."""
    cards = "\n".join(card_html(qr) for _ in range(4))
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
  @page {{ size: A4; margin: 0; }}
{CARD_CSS}
  .sheet {{
    width: 210mm; height: 297mm;
    display: grid;
    grid-template-columns: 105mm 105mm;
    grid-template-rows: 148mm 148mm;
    align-content: start;
  }}
  .card {{ outline: 0.2mm dashed #b9b9b9; outline-offset: -0.1mm; }}
</style></head><body>
<div class="sheet">{cards}</div>
</body></html>"""


def to_pdf(html_path: str, pdf_path: str):
    if not os.path.exists(CHROME):
        sys.exit(f"Chrome not found at {CHROME}; cannot render PDF.")
    subprocess.run([
        CHROME, "--headless", "--disable-gpu", "--no-sandbox",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path}", f"file://{html_path}",
    ], check=True, capture_output=True, timeout=120)


def main():
    qr = qr_svg()
    for name, html in (("flyer-a6-bleed", single_html(qr)),
                       ("flyer-a6-4up", fourup_html(qr))):
        html_path = os.path.join(HERE, name + ".html")
        pdf_path = os.path.join(HERE, name + ".pdf")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        to_pdf(html_path, pdf_path)
        print(f"  ✓ {name}.pdf  ({os.path.getsize(pdf_path):,} bytes)")
    print(f"\nQR target: {SUBSCRIBE_URL}")


if __name__ == "__main__":
    main()
