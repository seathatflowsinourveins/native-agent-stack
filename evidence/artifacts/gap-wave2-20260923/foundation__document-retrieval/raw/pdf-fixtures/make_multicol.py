from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

c = canvas.Canvas("multicol.pdf", pagesize=letter)
width, height = letter

left_col = [
    "LEFTCOL-ALPHA one two three",
    "LEFTCOL-BETA four five six",
    "LEFTCOL-GAMMA seven eight nine",
    "LEFTCOL-DELTA ten eleven twelve",
]
right_col = [
    "RIGHTCOL-ECHO thirteen fourteen",
    "RIGHTCOL-FOXTROT fifteen sixteen",
    "RIGHTCOL-GOLF seventeen eighteen",
    "RIGHTCOL-HOTEL nineteen twenty",
]

c.setFont("Helvetica", 12)
y = height - 72
for line in left_col:
    c.drawString(72, y, line)
    y -= 20

y = height - 72
for line in right_col:
    c.drawString(320, y, line)
    y -= 20

c.showPage()
c.save()
print("wrote multicol.pdf")
