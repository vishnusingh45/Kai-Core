import os
import sys
import html
import math
import time
import random
import threading
import traceback

# Hamesha isi file wale folder me kaam karo (kai.py, kai_memory.db yahin se milenge)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QTextEdit, QGraphicsDropShadowEffect,
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QPointF, QRectF, QPropertyAnimation
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont,
    QRadialGradient, QLinearGradient,
)

from kai import run_kai


# Signal bridge: KAI's thread emits, the GUI (main thread) receives
class KaiSignals(QObject):
    status_changed = Signal(str)
    message_added = Signal(str, str)
    exit_requested = Signal()


# ---------------------------------------------------------------
# ORB (glow, particles, equalizer bars, smooth colour change)
# ---------------------------------------------------------------
class OrbWidget(QWidget):
    COLORS = {
        "Listening...": "#00BFFF",
        "Processing!!!": "#FFB300",
        "Responding :) ": "#39FF88",
    }

    def __init__(self):
        super().__init__()
        self.setFixedSize(440, 440)
        self.t = 0
        self.state = "Listening..."

        start = QColor(self.COLORS[self.state])
        self.rgb = [float(start.red()), float(start.green()), float(start.blue())]
        self.target = start

        rnd = random.Random(7)
        # (start angle, speed, radius, size)
        self.particles = [
            (rnd.uniform(0, 6.28),
             rnd.uniform(0.004, 0.014) * rnd.choice([-1, 1]),
             rnd.uniform(135, 235),
             rnd.uniform(1.5, 3.5))
            for _ in range(18)
        ]

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(30)

    def set_state(self, state):
        self.state = state
        self.target = QColor(self.COLORS.get(state, "#00BFFF"))

    def tick(self):
        self.t += 1
        goal = (self.target.red(), self.target.green(), self.target.blue())
        for i in range(3):
            self.rgb[i] += (goal[i] - self.rgb[i]) * 0.08
        self.update()

    def c(self, alpha=255):
        q = QColor(int(self.rgb[0]), int(self.rgb[1]), int(self.rgb[2]))
        q.setAlpha(max(0, min(255, int(alpha))))
        return q

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        s = min(self.width(), self.height()) / 500
        p.translate(self.width() / 2, self.height() / 2)
        p.scale(s, s)

        t = self.t
        origin = QPointF(0, 0)
        pulse = (math.sin(t * 0.06) + 1) / 2  # 0..1

        # 1) Ambient glow
        g = QRadialGradient(origin, 250)
        g.setColorAt(0.0, self.c(110 + 40 * pulse))
        g.setColorAt(0.45, self.c(35))
        g.setColorAt(1.0, self.c(0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(origin, 250, 250)

        # 2) Outer thin ring + rotating dotted ring
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(self.c(150), 1.5))
        p.drawEllipse(origin, 235, 235)

        dotted = QPen(self.c(110), 2)
        dotted.setDashPattern([1.0, 7.0])
        dotted.setDashOffset(t * 0.4)
        dotted.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(dotted)
        p.drawEllipse(origin, 218, 218)

        # 3) Comet jo outer ring pe ghoomta hai (tail ke saath)
        a = t * 0.03
        p.setPen(Qt.PenStyle.NoPen)
        for k in range(14):
            ang = a - k * 0.035
            pos = QPointF(235 * math.cos(ang), 235 * math.sin(ang))
            p.setBrush(self.c(200 - k * 14))
            r = 3.2 - k * 0.18
            p.drawEllipse(pos, r, r)
        head = QPointF(235 * math.cos(a), 235 * math.sin(a))
        hg = QRadialGradient(head, 20)
        hg.setColorAt(0.0, QColor(255, 255, 255, 255))
        hg.setColorAt(0.35, self.c(140))
        hg.setColorAt(1.0, self.c(0))
        p.setBrush(QBrush(hg))
        p.drawEllipse(head, 20, 20)

        # 4) Tick ring (clockwise)
        rot = t * 0.5
        p.setPen(QPen(self.c(190), 1.5))
        for deg in range(0, 360, 5):
            ang = math.radians(deg + rot)
            inner = 188 if deg % 30 == 0 else 196
            p.drawLine(
                QPointF(inner * math.cos(ang), inner * math.sin(ang)),
                QPointF(206 * math.cos(ang), 206 * math.sin(ang)),
            )

        # 5) Thick segmented arcs (counter-clockwise)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(self.c(40), 1))
        p.drawEllipse(origin, 170, 170)
        arc_pen = QPen(self.c(230), 7)
        arc_pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        p.setPen(arc_pen)
        rect = QRectF(-170, -170, 340, 340)
        for start in range(0, 360, 60):
            p.drawArc(rect, int((start + t * 0.8) * 16), 40 * 16)

        # 6) Inner fast arcs (clockwise)
        inner_pen = QPen(self.c(200), 3)
        inner_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(inner_pen)
        rect2 = QRectF(-135, -135, 270, 270)
        for i in range(3):
            p.drawArc(rect2, int((-(i * 120) - t * 1.6) * 16), 70 * 16)

        # 7) Equalizer bars (state ke hisaab se alag behaviour)
        bar_pen = QPen(self.c(240), 3)
        bar_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(bar_pen)
        for i in range(60):
            deg = i * 6
            ang = math.radians(deg)
            if self.state == "Responding :) ":
                h = 4 + 20 * abs(math.sin(t * 0.2 + i * 0.5) * math.sin(t * 0.07 + i * 0.13))
            elif self.state == "Processing!!!":
                sweep = (t * 5) % 360
                diff = (sweep - deg) % 360
                h = 4 + 24 * max(0.0, 1 - diff / 120)
            else:
                h = 3 + 4 * (math.sin(t * 0.05 + i * 0.4) + 1) / 2
            p.drawLine(
                QPointF(92 * math.cos(ang), 92 * math.sin(ang)),
                QPointF((92 + h) * math.cos(ang), (92 + h) * math.sin(ang)),
            )

        # 8) Core (glow + white centre)
        boost = 8 if self.state == "Responding :) " else 4
        cr = 34 + boost * pulse
        cg = QRadialGradient(origin, cr * 2.2)
        cg.setColorAt(0.0, QColor(255, 255, 255, 255))
        cg.setColorAt(0.35, self.c(220))
        cg.setColorAt(1.0, self.c(0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(cg))
        p.drawEllipse(origin, cr * 2.2, cr * 2.2)
        p.setBrush(QColor(255, 255, 255))
        p.drawEllipse(origin, 18 + 3 * pulse, 18 + 3 * pulse)

        # 9) Floating particles
        p.setPen(Qt.PenStyle.NoPen)
        for a0, sp, r, size in self.particles:
            ang = a0 + sp * t
            alpha = 120 + 100 * abs(math.sin(t * 0.05 + a0))
            p.setBrush(self.c(alpha))
            p.drawEllipse(QPointF(r * math.cos(ang), r * math.sin(ang)), size, size)


# ---------------------------------------------------------------
# MAIN WINDOW (gradient background, grid, scanline, HUD corners)
# ---------------------------------------------------------------
class KaiWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.t = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(30)

    def tick(self):
        self.t += 1
        self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Background gradient
        bg = QRadialGradient(w / 2, h * 0.4, max(w, h) * 0.8)
        bg.setColorAt(0.0, QColor("#0D1530"))
        bg.setColorAt(1.0, QColor("#03050D"))
        p.fillRect(0, 0, w, h, QBrush(bg))

        # Faint grid
        p.setPen(QPen(QColor(0, 191, 255, 14), 1))
        for x in range(0, w, 50):
            p.drawLine(x, 0, x, h)
        for y in range(0, h, 50):
            p.drawLine(0, y, w, y)

        # Moving scanline
        y = (self.t * 2) % (h + 240) - 120
        sg = QLinearGradient(0, y - 60, 0, y + 60)
        sg.setColorAt(0.0, QColor(0, 191, 255, 0))
        sg.setColorAt(0.5, QColor(0, 191, 255, 22))
        sg.setColorAt(1.0, QColor(0, 191, 255, 0))
        p.fillRect(0, int(y - 60), w, 120, QBrush(sg))

        # HUD corner brackets
        p.setPen(QPen(QColor(0, 191, 255, 170), 2))
        L, m = 30, 16
        p.drawLine(m, m, m + L, m)
        p.drawLine(m, m, m, m + L)
        p.drawLine(w - m, m, w - m - L, m)
        p.drawLine(w - m, m, w - m, m + L)
        p.drawLine(m, h - m, m + L, h - m)
        p.drawLine(m, h - m, m, h - m - L)
        p.drawLine(w - m, h - m, w - m - L, h - m)
        p.drawLine(w - m, h - m, w - m, h - m - L)


def glow(widget, color, blur=30):
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setOffset(0, 0)
    eff.setColor(QColor(color))
    widget.setGraphicsEffect(eff)
    return eff


app = QApplication([])

window = KaiWindow()
window.setWindowTitle("KAI AI ASSISTANT")
window.resize(900, 860)

root = QVBoxLayout(window)
root.setContentsMargins(40, 30, 40, 30)
root.setSpacing(6)

# Top HUD bar
top = QHBoxLayout()
sys_label = QLabel("● SYSTEM ONLINE")
sys_label.setStyleSheet("color: rgba(57,255,136,220); font-size: 12px; font-family: Consolas;")
clock_label = QLabel("")
clock_label.setStyleSheet("color: rgba(0,191,255,210); font-size: 12px; font-family: Consolas;")
top.addWidget(sys_label)
top.addStretch()
top.addWidget(clock_label)
root.addLayout(top)

# Title
title_font = QFont("Segoe UI", 40)
title_font.setBold(True)
title_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 16)
kai_label = QLabel("KAI")
kai_label.setFont(title_font)
kai_label.setStyleSheet("color: #D4AF37;")
glow(kai_label, "#D4AF37", 35)
root.addWidget(kai_label, alignment=Qt.AlignmentFlag.AlignCenter)

sub_font = QFont("Segoe UI", 9)
sub_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 6)
sub_label = QLabel("VOICE ASSISTANT")
sub_label.setFont(sub_font)
sub_label.setStyleSheet("color: rgba(160,175,210,200);")
root.addWidget(sub_label, alignment=Qt.AlignmentFlag.AlignCenter)

# Orb
core = OrbWidget()
root.addWidget(core, alignment=Qt.AlignmentFlag.AlignCenter)

# Status
status_font = QFont("Segoe UI", 13)
status_font.setBold(True)
status_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 6)
status_label = QLabel("LISTENING")
status_label.setFont(status_font)
status_label.setStyleSheet("color: #00BFFF;")
status_glow = glow(status_label, "#00BFFF", 25)
root.addWidget(status_label, alignment=Qt.AlignmentFlag.AlignCenter)

# Chat box
chat_box = QTextEdit()
chat_box.setReadOnly(True)
chat_box.setFixedHeight(170)
chat_box.setStyleSheet("""
    QTextEdit {
        background-color: rgba(8, 14, 32, 200);
        color: #E0E6F0;
        border: 1px solid rgba(0, 191, 255, 130);
        border-radius: 12px;
        padding: 10px;
        font-size: 14px;
        font-family: Consolas;
    }
    QScrollBar:vertical { background: transparent; width: 6px; margin: 2px; }
    QScrollBar::handle:vertical { background: rgba(0, 191, 255, 120); border-radius: 3px; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
""")
root.addWidget(chat_box)

STATUS_STYLE = {
    "Listening...": ("LISTENING", "#00BFFF"),
    "Processing!!!": ("PROCESSING", "#FFB300"),
    "Responding :) ": ("RESPONDING", "#39FF88"),
}


def set_status(status):
    core.set_state(status)
    text, col = STATUS_STYLE.get(status, (status.upper(), "#00BFFF"))
    status_label.setText(text)
    status_label.setStyleSheet(f"color: {col};")
    status_glow.setColor(QColor(col))


def on_message(who, text):
    safe_text = html.escape(text).replace("\n", "<br>")
    name_color = "#00BFFF" if who == "YOU" else "#D4AF37"
    chat_box.append(
        f'<div style="margin-bottom:6px;"><span style="color:{name_color};">'
        f'<b>{who} &rsaquo;</b></span> {safe_text}</div>'
    )
    bar = chat_box.verticalScrollBar()
    bar.setValue(bar.maximum())


def update_clock():
    clock_label.setText(time.strftime("%I:%M:%S %p   |   %a %d %b %Y").upper())


clock_timer = QTimer(window)
clock_timer.timeout.connect(update_clock)
clock_timer.start(1000)
update_clock()

# Connect KAI's signals to the GUI (Queued = thread-safe)
signals = KaiSignals()
signals.status_changed.connect(set_status, Qt.ConnectionType.QueuedConnection)
signals.message_added.connect(on_message, Qt.ConnectionType.QueuedConnection)
signals.exit_requested.connect(app.quit, Qt.ConnectionType.QueuedConnection)


def kai_thread():
    try:
        run_kai(signals)
    except Exception:
        print("KAI thread crashed:")
        traceback.print_exc()
    signals.exit_requested.emit()


# Fade-in jab window khule
window.setWindowOpacity(0.0)
window.show()
fade_anim = QPropertyAnimation(window, b"windowOpacity")
fade_anim.setDuration(1200)
fade_anim.setStartValue(0.0)
fade_anim.setEndValue(1.0)
fade_anim.start()

# Run KAI's voice loop in a background thread so the GUI never freezes
threading.Thread(target=kai_thread, daemon=True).start()

app.exec()