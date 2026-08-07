import subprocess
import re
import os
from PyQt6.QtWidgets import (QWidget, QLabel, QVBoxLayout, QApplication, QSizeGrip, 
                             QHBoxLayout, QPushButton, QGraphicsDropShadowEffect,
                             QMenu, QSlider, QWidgetAction, QColorDialog, QMessageBox, QInputDialog)
from PyQt6.QtCore import Qt, QTimer, QSettings, qInstallMessageHandler
from PyQt6.QtGui import QFont, QColor, QLinearGradient, QPainter, QBrush, QPen, QAction

class SubtitleOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.dragging = False
        self.drag_start_pos = None
        self.drag_start_geometry = None
        self.resize_edge = None  # For edge resizing
        
        # Settings (Persist across sessions)
        self.settings = QSettings("LiveSubtitle", "Overlay")
        self.text_color = QColor(self.settings.value("text_color", "#FFFFFF"))
        self.bg_opacity = int(self.settings.value("bg_opacity", 220))
        self.glow_color = QColor(self.settings.value("glow_color", "#00DCFF"))
        self.font_size = int(self.settings.value("font_size", 22))
        self.bg_color_start = QColor(self.settings.value("bg_color_start", "#0F1423"))  # Dark blue
        self.bg_color_end = QColor(self.settings.value("bg_color_end", "#1E0F28"))  # Dark purple
        
        # Model Settings (Restart required)
        self.whisper_model = self.settings.value("whisper_model", "medium")
        self.trans_model = self.settings.value("trans_model", "translategemma:4b")
        
        # Cache for Ollama models
        self.ollama_models = []
        
        self.init_ui()

    def get_ollama_models(self):
        """Fetch local Ollama models dynamically"""
        if self.ollama_models:
            return self.ollama_models
            
        try:
            # Run 'ollama list' command
            # Use Shell=True to avoid issues with PATH on some systems
            if os.name == 'nt':
                 startupinfo = subprocess.STARTUPINFO()
                 startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                 result = subprocess.run(["ollama", "list"], capture_output=True, text=True, encoding="utf-8", startupinfo=startupinfo)
            else:
                 result = subprocess.run(["ollama", "list"], capture_output=True, text=True, encoding="utf-8")

            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                # Skip header, extract first column
                models = []
                for line in lines[1:]:
                    parts = line.split()
                    if parts:
                        models.append(parts[0])
                self.ollama_models = models
                return models
        except Exception as e:
            print(f"Failed to scan models: {e}")
            
        # Fallback if scan fails
        return ["translategemma:4b", "qwen:1.8b", "llama3", "gemma2"]

    def get_whisper_models(self):
        """Scan 'models' directory for local Whisper models"""
        models_dir = os.path.join(os.getcwd(), "models")
        found_models = []
        if os.path.exists(models_dir):
            for entry in os.scandir(models_dir):
                if entry.is_dir():
                    name = entry.name
                    # Filter out hidden folders, locks, and temps
                    if name.startswith(".") or name.endswith(".lock") or "temp" in name.lower():
                        continue
                        
                    # Verify it looks like a model (has model.bin)
                    if os.path.exists(os.path.join(entry.path, "model.bin")):
                        found_models.append(name)
        
        # Sort models
        found_models.sort()
        
        # If no local models found, provide defaults
        if not found_models:
            return ["small", "medium", "large-v3"]
        
        return found_models

    def init_ui(self):
        # Window setup
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(400, 100)
        self.setMouseTracking(True)  # Enable cursor updates on hover
        
        # ========== CLOSE BUTTON (Smaller) ==========
        self.close_btn = QPushButton("✕", self)
        self.close_btn.setFixedSize(18, 18)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.1);
                color: rgba(255, 255, 255, 0.5);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 9px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(255, 80, 80, 0.8);
                color: white;
            }
        """)
        self.close_btn.setGeometry(6, 6, 18, 18)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.close_application)

        # ========== SETTINGS BUTTON (Smaller) ==========
        self.settings_btn = QPushButton("⚙", self)
        self.settings_btn.setFixedSize(18, 18)
        self.settings_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.1);
                color: rgba(255, 255, 255, 0.5);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 9px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: rgba(100, 150, 255, 0.5);
                color: white;
            }
        """)
        self.settings_btn.setGeometry(28, 6, 18, 18)
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.clicked.connect(self.show_settings_menu)

        # ========== MAIN LAYOUT (Compact) ==========
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 26, 6, 4)  # Left, Top, Right, Bottom - minimal
        main_layout.setSpacing(2)  # Minimal space between labels
        self.setLayout(main_layout)

        # ========== JAPANESE TEXT LABEL ==========
        self.jp_label = QLabel("")
        self.jp_label.setFont(QFont("Yu Gothic UI", 15))  # Slightly larger
        self.jp_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.7);
                background-color: transparent;
                padding: 2px 8px;
                letter-spacing: 1px;
            }
        """)
        self.jp_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.jp_label.setWordWrap(True)
        self.jp_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)  # Pass mouse to parent
        self.jp_label.hide()
        main_layout.addWidget(self.jp_label)

        # ========== CHINESE TEXT LABEL ==========
        self.cn_label = QLabel("等待音频输入...")
        self.cn_label.setFont(QFont("Microsoft YaHei", 22, QFont.Weight.Bold))
        self.cn_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.cn_label.setWordWrap(True)
        self.cn_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)  # Pass mouse to parent
        self.apply_text_style()
        main_layout.addWidget(self.cn_label)
        
        # ========== SIZE GRIP (Visible Indicator) ==========
        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        
        # Custom resize indicator
        self.resize_indicator = QLabel("◢", self)
        self.resize_indicator.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.4);
                font-size: 16px;
                padding: 0;
                margin: 0;
            }
        """)
        self.resize_indicator.setFixedSize(20, 20)
        self.resize_indicator.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        bottom_row.addWidget(self.resize_indicator)
        
        self.size_grip = QSizeGrip(self)
        self.size_grip.setFixedSize(20, 20)
        self.size_grip.setStyleSheet("QSizeGrip { background: transparent; }")
        # Stack size grip on top of indicator
        self.size_grip.raise_()
        bottom_row.addWidget(self.size_grip)
        main_layout.addLayout(bottom_row)

        # ========== INITIAL POSITION ==========
        # Try to restore last position, otherwise center bottom
        saved_geo = self.settings.value("geometry")
        if saved_geo:
            self.restoreGeometry(saved_geo)
        else:
            screen = QApplication.primaryScreen().geometry()
            width = int(screen.width() * 0.5)
            height = 160
            x = (screen.width() - width) // 2
            y = screen.height() - height - 50
            self.setGeometry(x, y, width, height)

        # ========== AUTO-HIDE TIMER ==========
        self.hide_timer = QTimer(self)
        self.hide_timer.setInterval(300000)
        self.hide_timer.timeout.connect(self.clear_subtitles)
        self.hide_timer.start()

    def apply_text_style(self, is_preview=False):
        """Apply current color and font settings to Chinese label"""
        if is_preview:
            color = self.text_color.lighter(70)  # Dimmer for preview
            glow = QColor(150, 150, 150, 80)
        else:
            color = self.text_color
            glow = self.glow_color
        
        # Update font size
        self.cn_label.setFont(QFont("Microsoft YaHei", self.font_size, QFont.Weight.Bold))
            
        self.cn_label.setStyleSheet(f"""
            QLabel {{ 
                color: {color.name()}; 
                background-color: transparent;
                padding: 4px 10px;
                letter-spacing: 2px;
            }}
        """)
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(25)
        shadow.setColor(glow)
        shadow.setOffset(0, 0)
        self.cn_label.setGraphicsEffect(shadow)

    def paintEvent(self, event):
        """Custom paint for glassmorphism background"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        
        # Gradient with user-defined colors and opacity
        gradient = QLinearGradient(0, 0, rect.width(), rect.height())
        start_color = QColor(self.bg_color_start)
        start_color.setAlpha(self.bg_opacity)
        end_color = QColor(self.bg_color_end)
        end_color.setAlpha(self.bg_opacity)
        gradient.setColorAt(0, start_color)
        gradient.setColorAt(1, end_color)
        
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor(255, 255, 255, 40), 1))
        painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 12, 12)  # Smaller radius
        painter.end()

    def show_settings_menu(self):
        """Show settings context menu"""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: rgba(30, 30, 40, 240);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                padding: 5px;
            }
            QMenu::item {
                color: white;
                padding: 8px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: rgba(100, 150, 255, 0.5);
            }
            QMenu::separator {
                height: 1px;
                background: rgba(255, 255, 255, 0.2);
                margin: 5px 10px;
            }
        """)
        
        # --- Color Options ---
        color_menu = menu.addMenu("🎨 文字颜色")
        
        colors = [
            ("⚪ 白色", "#FFFFFF", "#00DCFF"),
            ("🟡 金色", "#FFD700", "#FFA500"),
            ("🟢 翠绿", "#00FF7F", "#00CC66"),
            ("🔵 天蓝", "#00BFFF", "#0080FF"),
            ("🟣 紫色", "#DA70D6", "#9932CC"),
            ("🔴 粉红", "#FF69B4", "#FF1493"),
        ]
        
        for name, text_hex, glow_hex in colors:
            action = color_menu.addAction(name)
            action.triggered.connect(lambda checked, t=text_hex, g=glow_hex: self.set_colors(t, g))
        
        color_menu.addSeparator()
        custom_color = color_menu.addAction("🖌️ 自定义颜色...")
        custom_color.triggered.connect(self.pick_custom_color)
        
        # --- Background Color Options ---
        bg_color_menu = menu.addMenu("🖼️ 背景颜色")
        
        bg_colors = [
            ("🌌 深空 (默认)", "#0F1423", "#1E0F28"),
            ("⬛ 纯黑", "#000000", "#000000"),
            ("🌑 深灰", "#1a1a1a", "#2a2a2a"),
            ("🔵 深蓝", "#0a1628", "#0a1628"),
            ("🟤 深褐", "#1a0f0a", "#2a1a0f"),
            ("🟣 深紫", "#140a1e", "#1e0a28"),
        ]
        
        for name, start_hex, end_hex in bg_colors:
            action = bg_color_menu.addAction(name)
            action.triggered.connect(lambda checked, s=start_hex, e=end_hex: self.set_bg_colors(s, e))
        
        bg_color_menu.addSeparator()
        custom_bg = bg_color_menu.addAction("🖌️ 自定义背景色...")
        custom_bg.triggered.connect(self.pick_custom_bg_color)
        
        menu.addSeparator()
        
        # --- Model Settings ---
        model_menu = menu.addMenu("🤖 模型设置")
        
        # Whisper Model Submenu
        whisper_menu = model_menu.addMenu("🎙️ 语音模型 (Whisper)")
        whisper_models = self.get_whisper_models()
        
        for m in whisper_models:
            action = whisper_menu.addAction(m)
            action.setCheckable(True)
            action.setChecked(m == self.whisper_model)
            action.triggered.connect(lambda checked, m=m: self.set_whisper_model(m))
            
        # Translation Model Submenu
        trans_menu = model_menu.addMenu("🌐 翻译模型 (Ollama)")
        
        # Fetch models (try to scan first)
        trans_models = self.get_ollama_models()
        if not trans_models:
            trans_models = ["translategemma:4b", "qwen:1.8b", "llama3"]
            
        for m in trans_models:
            action = trans_menu.addAction(m)
            action.setCheckable(True)
            action.setChecked(m == self.trans_model)
            # Use default value closure to capture 'm' correctly
            action.triggered.connect(lambda checked, model=m: self.set_trans_model(model))
            
        trans_menu.addSeparator()
        custom_trans = trans_menu.addAction("✏️ 输入模型名称...")
        custom_trans.triggered.connect(self.input_custom_trans_model)
        
        menu.addSeparator()
        
        # --- Opacity Slider ---
        opacity_label = QAction("🌓 背景透明度", self)
        opacity_label.setEnabled(False)
        menu.addAction(opacity_label)
        
        slider_widget = QSlider(Qt.Orientation.Horizontal)
        slider_widget.setRange(50, 255)
        slider_widget.setValue(self.bg_opacity)
        slider_widget.setFixedWidth(150)
        slider_widget.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 6px;
                background: rgba(255, 255, 255, 0.3);
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                width: 14px;
                height: 14px;
                margin: -4px 0;
                background: white;
                border-radius: 7px;
            }
        """)
        slider_widget.valueChanged.connect(self.set_opacity)
        
        slider_action = QWidgetAction(self)
        slider_action.setDefaultWidget(slider_widget)
        menu.addAction(slider_action)
        
        menu.addSeparator()
        
        # --- Font Size Slider ---
        font_label = QAction("🔤 字体大小", self)
        font_label.setEnabled(False)
        menu.addAction(font_label)
        
        font_slider = QSlider(Qt.Orientation.Horizontal)
        font_slider.setRange(14, 40)
        font_slider.setValue(self.font_size)
        font_slider.setFixedWidth(150)
        font_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 6px;
                background: rgba(255, 255, 255, 0.3);
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                width: 14px;
                height: 14px;
                margin: -4px 0;
                background: #00BFFF;
                border-radius: 7px;
            }
        """)
        font_slider.valueChanged.connect(self.set_font_size)
        
        font_slider_action = QWidgetAction(self)
        font_slider_action.setDefaultWidget(font_slider)
        menu.addAction(font_slider_action)
        
        menu.addSeparator()
        
        # --- Reset ---
        reset_action = menu.addAction("🔄 重置为默认")
        reset_action.triggered.connect(self.reset_settings)
        
        # Show menu at button position
        menu.exec(self.settings_btn.mapToGlobal(self.settings_btn.rect().bottomLeft()))

    def set_colors(self, text_hex, glow_hex):
        """Set text and glow colors"""
        self.text_color = QColor(text_hex)
        self.glow_color = QColor(glow_hex)
        self.apply_text_style()
        self.save_settings()

    def pick_custom_color(self):
        """Open color picker dialog"""
        color = QColorDialog.getColor(self.text_color, self, "选择文字颜色")
        if color.isValid():
            self.text_color = color
            # Generate complementary glow
            h, s, l, _ = color.getHsl()
            self.glow_color = QColor.fromHsl((h + 30) % 360, min(s + 50, 255), min(l + 30, 200))
            self.apply_text_style()
            self.save_settings()

    def set_opacity(self, value):
        """Set background opacity"""
        self.bg_opacity = value
        self.update()  # Trigger repaint
        self.save_settings()

    def set_font_size(self, size):
        """Set font size"""
        self.font_size = size
        self.apply_text_style()
        self.save_settings()

    def set_bg_colors(self, start_hex, end_hex):
        """Set background gradient colors"""
        self.bg_color_start = QColor(start_hex)
        self.bg_color_end = QColor(end_hex)
        self.update()
        self.save_settings()

    def pick_custom_bg_color(self):
        """Open color picker for background"""
        color = QColorDialog.getColor(self.bg_color_start, self, "选择背景颜色")
        if color.isValid():
            self.bg_color_start = color
            self.bg_color_end = color.darker(120)
            self.update()
            self.save_settings()

    def set_whisper_model(self, model_name):
        if self.whisper_model != model_name:
            self.whisper_model = model_name
            self.save_settings()
            QMessageBox.information(self, "重启生效", f"Whisper 模型已设置为: {model_name}\n请重启程序以应用更改。")

    def set_trans_model(self, model_name):
        if self.trans_model != model_name:
            self.trans_model = model_name
            self.save_settings()
            QMessageBox.information(self, "重启生效", f"翻译模型已设置为: {model_name}\n请重启程序以应用更改。")

    def input_custom_trans_model(self):
        text, ok = QInputDialog.getText(self, "自定义模型", "请输入 Ollama 模型名称 (例如: llama3:8b):")
        if ok and text:
            self.set_trans_model(text.strip())

    def reset_settings(self):
        """Reset to default settings"""
        self.text_color = QColor("#FFFFFF")
        self.glow_color = QColor("#00DCFF")
        self.bg_opacity = 220
        self.font_size = 22
        self.bg_color_start = QColor("#0F1423")
        self.bg_color_end = QColor("#1E0F28")
        self.apply_text_style()
        self.update()
        self.save_settings()

    def save_settings(self):
        """Persist settings"""
        self.settings.setValue("text_color", self.text_color.name())
        self.settings.setValue("glow_color", self.glow_color.name())
        self.settings.setValue("bg_opacity", self.bg_opacity)
        self.settings.setValue("font_size", self.font_size)
        self.settings.setValue("bg_color_start", self.bg_color_start.name())
        self.settings.setValue("bg_color_end", self.bg_color_end.name())
        self.settings.setValue("whisper_model", self.whisper_model)
        self.settings.setValue("trans_model", self.trans_model)
        self.settings.setValue("geometry", self.saveGeometry())

    def closeEvent(self, event):
        """Save geometry on close"""
        self.settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(event)

    def update_subtitles(self, jp_text, cn_text):
        self.hide_timer.start()
        
        if jp_text:
            self.jp_label.setText(jp_text)
            self.jp_label.show()
            self.cn_label.show()
        
        if cn_text == "PENDING_KEEP_OLD":
            self.apply_text_style(is_preview=True)
        elif cn_text:
            # Check if preview (gray) or final
            if "<span style='color: #cccccc;'>" in cn_text:
                clean_text = cn_text.replace("<span style='color: #cccccc;'>", "").replace("</span>", "")
                self.cn_label.setText(clean_text)
                self.apply_text_style(is_preview=True)
            else:
                self.cn_label.setText(cn_text)
                self.apply_text_style(is_preview=False)
        
        # Force UI refresh for transparent window
        self.jp_label.repaint()
        self.cn_label.repaint()
        self.repaint()
        QApplication.processEvents()
        # Backup: schedule another repaint in case first one missed
        QTimer.singleShot(10, self.repaint)
            
    def clear_subtitles(self):
        self.jp_label.hide()
        self.cn_label.setText("")

    def close_application(self):
        self.save_settings()
        QApplication.quit()
    
    # ========== EDGE RESIZE + DRAG TO MOVE ==========
    EDGE_MARGIN = 8  # Pixels from edge to trigger resize
    
    def get_edge(self, pos):
        """Determine which edge/corner the mouse is over"""
        rect = self.rect()
        x, y = pos.x(), pos.y()
        w, h = rect.width(), rect.height()
        margin = self.EDGE_MARGIN
        
        left = x < margin
        right = x > w - margin
        top = y < margin
        bottom = y > h - margin
        
        if top and left:
            return "top-left"
        elif top and right:
            return "top-right"
        elif bottom and left:
            return "bottom-left"
        elif bottom and right:
            return "bottom-right"
        elif left:
            return "left"
        elif right:
            return "right"
        elif top:
            return "top"
        elif bottom:
            return "bottom"
        else:
            return None
    
    def update_cursor(self, edge):
        """Update cursor based on which edge/corner is hovered"""
        cursors = {
            "left": Qt.CursorShape.SizeHorCursor,
            "right": Qt.CursorShape.SizeHorCursor,
            "top": Qt.CursorShape.SizeVerCursor,
            "bottom": Qt.CursorShape.SizeVerCursor,
            "top-left": Qt.CursorShape.SizeFDiagCursor,
            "bottom-right": Qt.CursorShape.SizeFDiagCursor,
            "top-right": Qt.CursorShape.SizeBDiagCursor,
            "bottom-left": Qt.CursorShape.SizeBDiagCursor,
        }
        if edge in cursors:
            self.setCursor(cursors[edge])
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_pos = event.globalPosition().toPoint()
            self.drag_start_geometry = self.geometry()
            self.resize_edge = self.get_edge(event.pos())
            
            if self.resize_edge:
                self.dragging = False  # Resizing, not dragging
            else:
                self.dragging = True  # Moving

    def mouseMoveEvent(self, event):
        if self.drag_start_pos is None:
            # Just hovering - update cursor
            edge = self.get_edge(event.pos())
            self.update_cursor(edge)
            return
        
        delta = event.globalPosition().toPoint() - self.drag_start_pos
        geo = self.drag_start_geometry
        
        if self.dragging:
            # Moving the window
            new_pos = geo.topLeft() + delta
            self.move(new_pos)
        elif self.resize_edge:
            # Resizing
            new_geo = geo.adjusted(0, 0, 0, 0)  # Copy
            min_w, min_h = self.minimumWidth(), self.minimumHeight()
            
            if "left" in self.resize_edge:
                new_left = geo.left() + delta.x()
                if geo.right() - new_left >= min_w:
                    new_geo.setLeft(new_left)
            if "right" in self.resize_edge:
                new_right = geo.right() + delta.x()
                if new_right - geo.left() >= min_w:
                    new_geo.setRight(new_right)
            if "top" in self.resize_edge:
                new_top = geo.top() + delta.y()
                if geo.bottom() - new_top >= min_h:
                    new_geo.setTop(new_top)
            if "bottom" in self.resize_edge:
                new_bottom = geo.bottom() + delta.y()
                if new_bottom - geo.top() >= min_h:
                    new_geo.setBottom(new_bottom)
            
            self.setGeometry(new_geo)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            self.resize_edge = None
            self.drag_start_pos = None
            self.save_settings()


if __name__ == "__main__":
    import sys
    
    # Suppress Qt warnings about UpdateLayeredWindowIndirect
    def message_handler(mode, context, message):
        if "UpdateLayeredWindowIndirect failed" in message:
            return
        sys.__stderr__.write(message + "\n")
        
    qInstallMessageHandler(message_handler)

    app = QApplication(sys.argv)
    window = SubtitleOverlay()
    window.show()
    sys.exit(app.exec())
