#!/usr/bin/env python3
"""Rebuild only the original synthetic PDF; run with the recorded ReportLab pin."""
import argparse
import json
from pathlib import Path
from reportlab.pdfgen import canvas

HERE = Path(__file__).resolve().parent

def build(destination):
    spec = json.loads((HERE / 'corpus/authored-source.json').read_text())
    c = canvas.Canvas(str(destination), pagesize=(612, 792), invariant=1, pageCompression=0)
    c.setTitle('Lumen systems - qualification packet (synthetic)')
    c.setAuthor('Native Agent Stack contributors')
    for number, page in enumerate(spec['pages'], 1):
        c.setFont('Helvetica-Bold', 17)
        c.drawString(48, 748, page['title'])
        c.setFont('Helvetica', 11)
        for y, line in page['lines']:
            c.drawString(48, 792 - y, line)
        table = page['table']
        edges = table['column_edges']
        c.setFillColorRGB(0.91, 0.94, 0.97)
        c.rect(edges[0], 792 - table['header_top'] - 25, edges[-1] - edges[0], 25, fill=1, stroke=0)
        c.setFillColorRGB(0, 0, 0)
        for ri, row in enumerate([table['headers']] + table['rows']):
            y = table['header_top'] + 17 + 28 * ri
            c.setFont('Helvetica-Bold' if ri == 0 else 'Helvetica', 10)
            for x, value in zip(edges, row):
                c.drawString(x + 7, 792 - y, value)
            c.setStrokeColorRGB(0.7, 0.75, 0.8)
            c.line(edges[0], 792 - y - 8, edges[-1], 792 - y - 8)
        c.setFont('Helvetica', 9)
        c.drawString(48, 32, f'Synthetic fixture | Revision LUM-2026-09-A | Page {number} of 2')
        c.showPage()
    c.save()

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output', type=Path)
    build(p.parse_args().output)
