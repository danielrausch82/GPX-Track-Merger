# main.py - GPX Track Manager 1.0.1

import sys
import os
import math
import ctypes
import urllib.error
import urllib.request
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QLabel, QListWidget, QListWidgetItem, QFileDialog,
        QMessageBox, QFrame, QSizePolicy, QAbstractItemView, QListView
    )
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFont, QColor, QPainter, QPen, QPainterPath, QImage, QPixmap, QIcon
except ImportError:
    print("Fehler: Die Bibliothek PyQt6 ist nicht installiert!")
    print("Bitte installieren Sie sie mit:")
    print("   pip install PyQt6 gpxpy")
    sys.exit(1)

try:
    import gpxpy
    import gpxpy.gpx
    import gpxpy.geo
except ImportError:
    print("Fehler: Die Bibliothek gpxpy ist nicht installiert!")
    print("Bitte installieren Sie sie mit:")
    print("   pip install gpxpy")
    sys.exit(1)


def resource_path(*relative_parts):
    """Liefert einen Pfad zu gebündelten Ressourcen für Entwicklung und PyInstaller."""
    if getattr(sys, "frozen", False):
        base_path = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    else:
        base_path = Path(__file__).resolve().parent
    return base_path.joinpath(*relative_parts)


@dataclass
class TrackEntry:
    """Interne Repräsentation eines Tracks mit stabiler ID."""

    track_id: int
    name: str
    track: gpxpy.gpx.GPXTrack
    color: str
    distance_m: float
    elevation_gain_m: float


class GPXPreviewWidget(QWidget):
    """Zeichnet eine statische OSM-Karte mit GPX-Overlay."""

    TILE_SIZE = 256
    MIN_ZOOM = 3
    MAX_ZOOM = 16
    MAX_TILE_COUNT = 36

    def __init__(self, parent=None):
        super().__init__(parent)
        self.track_entries = []
        self.selected_track_id = None
        self.tile_cache = {}
        self.tile_error = False
        self.setMinimumHeight(240)

    def set_tracks(self, track_entries, selected_track_id=None):
        """Aktualisiert die Vorschau-Daten."""
        self.track_entries = list(track_entries)
        self.selected_track_id = selected_track_id
        self.update()

    def is_interactive_map_available(self):
        """Die Kartenansicht ist bewusst statisch und immer verfügbar."""
        return False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.setPen(QPen(QColor("#dbe4ee"), 1))
        painter.setBrush(QColor("#f8fbff"))
        painter.drawRoundedRect(rect, 16, 16)

        bounds = self._calculate_bounds()
        if bounds is None:
            painter.setPen(QColor("#94a3b8"))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Keine GPX-Vorschau verfügbar")
            return

        draw_rect = rect.adjusted(20, 20, -20, -20)
        projection = self._calculate_projection(draw_rect, bounds)
        if projection is None:
            self._draw_grid(painter, draw_rect)
            return

        self._draw_osm_background(painter, draw_rect, projection)
        if self.tile_error:
            self._draw_grid(painter, draw_rect)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.save()
        painter.setClipRect(draw_rect)

        for entry in self.track_entries:
            is_selected = self.selected_track_id is not None and entry.track_id == self.selected_track_id
            track_color = QColor(entry.color)

            if is_selected:
                outline_color = QColor("#ffffff")
                outline_color.setAlpha(220)
                outline_pen = QPen(outline_color, 6.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
                painter.setPen(outline_pen)
                self._draw_track(painter, draw_rect, projection, entry)

                track_color.setAlpha(255)
                pen = QPen(track_color, 4.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            else:
                track_color.setAlpha(225)
                pen = QPen(track_color, 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)

            painter.setPen(pen)
            self._draw_track(painter, draw_rect, projection, entry)

        painter.restore()

    def _calculate_bounds(self):
        """Ermittelt die geographischen Grenzen aller Trackpunkte."""
        latitudes = []
        longitudes = []

        for entry in self.track_entries:
            for segment in entry.track.segments:
                for point in segment.points:
                    latitudes.append(point.latitude)
                    longitudes.append(point.longitude)

        if not latitudes or not longitudes:
            return None

        min_lat = min(latitudes)
        max_lat = max(latitudes)
        min_lon = min(longitudes)
        max_lon = max(longitudes)

        if min_lat == max_lat:
            min_lat -= 0.0005
            max_lat += 0.0005
        if min_lon == max_lon:
            min_lon -= 0.0005
            max_lon += 0.0005

        return min_lat, max_lat, min_lon, max_lon

    def _project_point(self, draw_rect, bounds, latitude, longitude):
        """Projiziert geographische Koordinaten in Widget-Koordinaten."""
        zoom = bounds["zoom"]
        world_left = bounds["world_left"]
        world_top = bounds["world_top"]
        scale = bounds["scale"]
        world_x, world_y = self._latlon_to_world(latitude, longitude, zoom)

        x = draw_rect.left() + (world_x - world_left) * scale
        y = draw_rect.top() + (world_y - world_top) * scale
        return x, y

    def _latlon_to_world(self, latitude, longitude, zoom):
        """Projiziert geographische Koordinaten in Web-Mercator-Pixel."""
        scale = self.TILE_SIZE * (2 ** zoom)
        lat = max(min(latitude, 85.05112878), -85.05112878)
        x = (longitude + 180.0) / 360.0 * scale
        sin_lat = math.sin(math.radians(lat))
        y = (0.5 - math.log((1 + sin_lat) / (1 - sin_lat)) / (4 * math.pi)) * scale
        return x, y

    def _calculate_projection(self, draw_rect, bounds):
        """Berechnet Zoom und Kartenausschnitt für die statische OSM-Karte."""
        min_lat, max_lat, min_lon, max_lon = bounds

        for zoom in range(self.MAX_ZOOM, self.MIN_ZOOM - 1, -1):
            left, bottom = self._latlon_to_world(min_lat, min_lon, zoom)
            right, top = self._latlon_to_world(max_lat, max_lon, zoom)

            world_left = min(left, right)
            world_right = max(left, right)
            world_top = min(top, bottom)
            world_bottom = max(top, bottom)

            width = max(world_right - world_left, 64.0)
            height = max(world_bottom - world_top, 64.0)

            padding_x = width * 0.18
            padding_y = height * 0.18
            world_left -= padding_x
            world_right += padding_x
            world_top -= padding_y
            world_bottom += padding_y

            width = world_right - world_left
            height = world_bottom - world_top
            target_aspect = draw_rect.width() / max(draw_rect.height(), 1)
            current_aspect = width / max(height, 1)

            if current_aspect > target_aspect:
                desired_height = width / target_aspect
                extra = (desired_height - height) / 2
                world_top -= extra
                world_bottom += extra
            else:
                desired_width = height * target_aspect
                extra = (desired_width - width) / 2
                world_left -= extra
                world_right += extra

            tile_left = math.floor(world_left / self.TILE_SIZE)
            tile_right = math.floor((world_right - 1) / self.TILE_SIZE)
            tile_top = math.floor(world_top / self.TILE_SIZE)
            tile_bottom = math.floor((world_bottom - 1) / self.TILE_SIZE)
            tile_count = (tile_right - tile_left + 1) * (tile_bottom - tile_top + 1)

            if tile_count <= self.MAX_TILE_COUNT:
                scale = draw_rect.width() / max(world_right - world_left, 1)
                return {
                    "zoom": zoom,
                    "world_left": world_left,
                    "world_right": world_right,
                    "world_top": world_top,
                    "world_bottom": world_bottom,
                    "tile_left": tile_left,
                    "tile_right": tile_right,
                    "tile_top": tile_top,
                    "tile_bottom": tile_bottom,
                    "scale": scale,
                }

        return None

    def _fetch_tile_image(self, zoom, tile_x, tile_y):
        """Lädt eine OSM-Kachel und cacht sie lokal im Speicher."""
        key = (zoom, tile_x, tile_y)
        if key in self.tile_cache:
            return self.tile_cache[key]

        max_index = 2 ** zoom
        wrapped_x = tile_x % max_index
        if tile_y < 0 or tile_y >= max_index:
            return None

        url = f"https://tile.openstreetmap.org/{zoom}/{wrapped_x}/{tile_y}.png"
        request = urllib.request.Request(
            url,
            headers={"User-Agent": f"GPX-Track-Merger/{GPXTrackManagerGUI.APP_VERSION} (+https://github.com/danielrausch82/GPX-Track-Merger)"},
        )

        try:
            with urllib.request.urlopen(request, timeout=4) as response:
                tile_data = response.read()
        except (urllib.error.URLError, TimeoutError, ValueError):
            self.tile_error = True
            return None

        image = QImage()
        if not image.loadFromData(tile_data):
            self.tile_error = True
            return None

        self.tile_cache[key] = image
        return image

    def _draw_osm_background(self, painter, draw_rect, projection):
        """Zeichnet die statische OSM-Karte in den Hintergrund."""
        self.tile_error = False
        painter.save()
        painter.setClipRect(draw_rect)
        painter.fillRect(draw_rect, QColor("#eef4f8"))

        for tile_x in range(projection["tile_left"], projection["tile_right"] + 1):
            for tile_y in range(projection["tile_top"], projection["tile_bottom"] + 1):
                image = self._fetch_tile_image(projection["zoom"], tile_x, tile_y)
                if image is None:
                    placeholder_x = draw_rect.left() + (tile_x * self.TILE_SIZE - projection["world_left"]) * projection["scale"]
                    placeholder_y = draw_rect.top() + (tile_y * self.TILE_SIZE - projection["world_top"]) * projection["scale"]
                    placeholder_size = self.TILE_SIZE * projection["scale"]
                    painter.fillRect(
                        int(placeholder_x),
                        int(placeholder_y),
                        max(1, int(math.ceil(placeholder_size))),
                        max(1, int(math.ceil(placeholder_size))),
                        QColor("#f1f5f9"),
                    )
                    continue

                draw_x = draw_rect.left() + (tile_x * self.TILE_SIZE - projection["world_left"]) * projection["scale"]
                draw_y = draw_rect.top() + (tile_y * self.TILE_SIZE - projection["world_top"]) * projection["scale"]
                draw_size = self.TILE_SIZE * projection["scale"]
                painter.drawImage(
                    int(draw_x),
                    int(draw_y),
                    image.scaled(
                        max(1, int(math.ceil(draw_size))),
                        max(1, int(math.ceil(draw_size))),
                        Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    ),
                )

        painter.restore()

    def _draw_grid(self, painter, draw_rect):
        """Zeichnet ein dezentes Raster im Hintergrund."""
        painter.save()
        painter.setPen(QPen(QColor("#e7edf5"), 1, Qt.PenStyle.DashLine))
        for fraction in (0.25, 0.5, 0.75):
            x = draw_rect.left() + draw_rect.width() * fraction
            y = draw_rect.top() + draw_rect.height() * fraction
            painter.drawLine(int(x), int(draw_rect.top()), int(x), int(draw_rect.bottom()))
            painter.drawLine(int(draw_rect.left()), int(y), int(draw_rect.right()), int(y))
        painter.restore()

    def _draw_track(self, painter, draw_rect, bounds, entry):
        """Zeichnet einen einzelnen Track in die Vorschau."""
        for segment in entry.track.segments:
            path = QPainterPath()
            has_started = False
            for point in segment.points:
                x, y = self._project_point(draw_rect, bounds, point.latitude, point.longitude)
                if not has_started:
                    path.moveTo(x, y)
                    has_started = True
                else:
                    path.lineTo(x, y)

            if has_started:
                painter.drawPath(path)


class GPXTrackManagerGUI(QMainWindow):
    """GPX Track Manager - PyQt6 Version mit Drag & Drop Sortierung"""

    APP_VERSION = "1.0.1"

    DEFAULT_TRACK_COLORS = [
        "#2563eb",
        "#16a34a",
        "#dc2626",
        "#ca8a04",
        "#7c3aed",
        "#0f766e",
        "#ea580c",
        "#db2777",
    ]

    GPX_COLOR_MAP = {
        "black": "#000000",
        "darkred": "#8b0000",
        "darkgreen": "#006400",
        "darkyellow": "#b8860b",
        "darkblue": "#1d4ed8",
        "darkmagenta": "#8b008b",
        "darkcyan": "#0f766e",
        "lightgray": "#d1d5db",
        "darkgray": "#4b5563",
        "red": "#dc2626",
        "green": "#16a34a",
        "yellow": "#ca8a04",
        "blue": "#2563eb",
        "magenta": "#c026d3",
        "cyan": "#0891b2",
        "white": "#ffffff",
        "orange": "#ea580c",
        "purple": "#7c3aed",
    }

    def __init__(self):
        super().__init__()
        
        self.current_gpx_file = None
        self.tracks = []
        self.track_entries = []
        
        self.scale_factor = self._get_dpi_scale()
        
        print(f"DPI-Skalierung: {self.scale_factor:.2f} ({int(self.scale_factor * 100)}%)")
        
        self.setWindowTitle(f"GPX Track Manager {self.APP_VERSION}")
        self.setMinimumSize(800, 600)
        self.setStyleSheet(self._build_stylesheet())
        
        screen = QApplication.primaryScreen()
        if screen is not None:
            geometry = screen.geometry()
            self.move((geometry.width() - self.width()) // 2, (geometry.height() - self.height()) // 2)
        
        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)

        header_frame = QFrame()
        header_frame.setObjectName("headerFrame")
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(14, 12, 14, 12)
        header_layout.setSpacing(4)

        title_font = self._scaled_font(14, "Segoe UI")
        self.title_label = QLabel("GPX Track Manager", self)
        self.title_label.setObjectName("titleLabel")
        self.title_label.setFont(title_font)
        header_layout.addWidget(self.title_label)

        subtitle_font = self._scaled_font(9, "Segoe UI")
        self.subtitle_label = QLabel("Tracks per Drag-and-Drop sortieren, per Button löschen und in der sichtbaren Reihenfolge exportieren.", self)
        self.subtitle_label.setObjectName("subtitleLabel")
        self.subtitle_label.setFont(subtitle_font)
        self.subtitle_label.setWordWrap(True)
        header_layout.addWidget(self.subtitle_label)

        meta_layout = QHBoxLayout()
        meta_layout.setContentsMargins(0, 2, 0, 0)
        meta_layout.setSpacing(8)

        self.file_badge_label = QLabel("Keine Datei geladen", self)
        self.file_badge_label.setObjectName("metaBadge")
        meta_layout.addWidget(self.file_badge_label)

        self.count_badge_label = QLabel("0 Tracks", self)
        self.count_badge_label.setObjectName("metaBadge")
        meta_layout.addWidget(self.count_badge_label)

        self.distance_badge_label = QLabel("0,0 km", self)
        self.distance_badge_label.setObjectName("metaBadge")
        meta_layout.addWidget(self.distance_badge_label)

        self.elevation_badge_label = QLabel("0 hm", self)
        self.elevation_badge_label.setObjectName("metaBadge")
        meta_layout.addWidget(self.elevation_badge_label)

        meta_layout.addStretch(1)

        header_layout.addLayout(meta_layout)
        main_layout.addWidget(header_frame)
        
        controls_frame = QFrame()
        controls_frame.setObjectName("controlsPanel")
        controls_layout = QHBoxLayout(controls_frame)
        controls_layout.setContentsMargins(10, 10, 10, 10)
        controls_layout.setSpacing(8)
        
        self.btn_import = QPushButton("GPX-Datei öffnen", self)
        self.btn_import.setObjectName("btnImport")
        self.btn_import.setMinimumHeight(34)
        self.btn_import.clicked.connect(self.load_gpx_file)
        controls_layout.addWidget(self.btn_import)
        
        self.btn_delete = QPushButton("Track löschen", self)
        self.btn_delete.setObjectName("btnDelete")
        self.btn_delete.setMinimumHeight(34)
        self.btn_delete.clicked.connect(self.delete_selected_track_from_menu)
        controls_layout.addWidget(self.btn_delete)
        
        self.btn_export = QPushButton("GPX exportieren", self)
        self.btn_export.setObjectName("btnExport")
        self.btn_export.setMinimumHeight(34)
        self.btn_export.clicked.connect(self.export_gpx_file)
        controls_layout.addWidget(self.btn_export)
        
        self.btn_quit = QPushButton("Beenden", self)
        self.btn_quit.setObjectName("btnQuit")
        self.btn_quit.setMinimumHeight(34)
        self.btn_quit.clicked.connect(self.close)
        controls_layout.addWidget(self.btn_quit)
        
        main_layout.addWidget(controls_frame)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)
        
        list_frame = QFrame()
        list_frame.setObjectName("listFrame")
        list_layout = QVBoxLayout(list_frame)
        list_layout.setContentsMargins(12, 12, 12, 12)
        list_layout.setSpacing(8)

        list_header_layout = QHBoxLayout()
        list_header_layout.setContentsMargins(0, 0, 0, 0)

        self.list_title_label = QLabel("Trackliste", self)
        self.list_title_label.setObjectName("sectionTitleLabel")
        self.list_title_label.setFont(self._scaled_font(11, "Segoe UI"))
        list_header_layout.addWidget(self.list_title_label)

        self.list_hint_label = QLabel("Sortieren per Drag-and-Drop", self)
        self.list_hint_label.setObjectName("sectionHintLabel")
        list_header_layout.addStretch(1)
        list_header_layout.addWidget(self.list_hint_label)

        list_layout.addLayout(list_header_layout)
        
        self.track_list = QListWidget()
        self.track_list.setObjectName("trackList")
        self.track_list.setMinimumHeight(self._scaled_int(210))
        self.track_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.track_list.setDragEnabled(True)
        self.track_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.track_list.setAcceptDrops(True)
        self.track_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.track_list.setViewMode(QListView.ViewMode.ListMode)
        self.track_list.setAlternatingRowColors(True)
        self.track_list.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        model = self.track_list.model()
        if model is not None:
            model.rowsMoved.connect(self._on_track_rows_moved)
        self.track_list.currentItemChanged.connect(self._on_current_track_changed)
        
        self.track_list.itemDoubleClicked.connect(self._on_item_double_click)
        
        list_layout.addWidget(self.track_list, 1)

        preview_frame = QFrame()
        preview_frame.setObjectName("previewFrame")
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(12, 12, 12, 12)
        preview_layout.setSpacing(8)

        preview_header_layout = QHBoxLayout()
        preview_header_layout.setContentsMargins(0, 0, 0, 0)

        self.preview_title_label = QLabel("GPX-Vorschau", self)
        self.preview_title_label.setObjectName("sectionTitleLabel")
        self.preview_title_label.setFont(self._scaled_font(11, "Segoe UI"))
        preview_header_layout.addWidget(self.preview_title_label)

        self.preview_hint_label = QLabel("Auswahl wird hervorgehoben", self)
        self.preview_hint_label.setObjectName("sectionHintLabel")
        preview_header_layout.addStretch(1)
        preview_header_layout.addWidget(self.preview_hint_label)
        preview_layout.addLayout(preview_header_layout)

        self.preview_info_label = QLabel("Lade eine GPX-Datei, um die Strecke auf der OSM-Karte zu sehen.", self)
        self.preview_info_label.setObjectName("previewInfoLabel")
        self.preview_info_label.setWordWrap(True)
        preview_layout.addWidget(self.preview_info_label)

        self.preview_widget = GPXPreviewWidget(self)
        self.preview_widget.setObjectName("previewCanvas")
        preview_layout.addWidget(self.preview_widget, 1)

        content_layout.addWidget(list_frame, 5)
        content_layout.addWidget(preview_frame, 6)
        main_layout.addLayout(content_layout, 1)

        self._update_meta_labels()

    def _scaled_int(self, value):
        """Skaliert Größenwerte für Qt-APIs, die Integer erwarten."""
        return max(1, int(round(value * self.scale_factor)))

    def _scaled_font(self, point_size, family="Arial"):
        """Erzeugt eine skalierte Schrift mit ganzzahliger Punktgröße."""
        return QFont(family, self._scaled_int(point_size))

    def _get_dpi_scale(self):
        """Qt übernimmt High-DPI-Skalierung bereits selbst, daher keine Extraskalierung."""
        screen = QApplication.primaryScreen()
        if screen is None:
            print("Kein Bildschirm erkannt - Verwendung von Standard (100%)")
            return 1.0

        dpi = screen.logicalDotsPerInch()
        print(f"Qt-DPI erkannt: {dpi:.2f} - zusätzliche App-Skalierung deaktiviert")
        return 1.0

    def _build_stylesheet(self):
        """Erzeugt ein helles, reduziertes Styling für die Anwendung."""
        return """
        QMainWindow {
            background-color: #f4f6f8;
            color: #1f2937;
        }
        QWidget#centralWidget {
            background-color: #f4f6f8;
        }
        QWidget {
            color: #1f2937;
            font-family: 'Segoe UI';
            font-size: 10.5pt;
        }
        QLabel {
            background: transparent;
            border: none;
        }
        QFrame#headerFrame {
            background-color: #ffffff;
            border: 1px solid #e7ebf0;
            border-radius: 18px;
        }
        QFrame#controlsPanel, QFrame#listFrame, QFrame#previewFrame {
            background-color: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 16px;
        }
        QLabel#titleLabel {
            color: #0f172a;
            font-weight: 700;
        }
        QLabel#subtitleLabel {
            color: #475569;
            line-height: 1.4;
        }
        QLabel#metaBadge {
            background-color: #f8fafc;
            border: 1px solid #dbe4ee;
            border-radius: 999px;
            padding: 4px 10px;
            color: #334155;
            font-weight: 600;
        }
        QLabel#sectionTitleLabel {
            color: #0f172a;
            font-weight: 700;
        }
        QLabel#sectionHintLabel {
            color: #64748b;
        }
        QLabel#previewInfoLabel {
            color: #475569;
            padding-bottom: 4px;
        }
        QPushButton {
            background-color: #ffffff;
            color: #111827;
            border: 1px solid #d5dbe3;
            border-radius: 12px;
            padding: 8px 14px;
            font-weight: 600;
        }
        QPushButton:hover {
            background-color: #f1f5f9;
            border-color: #94a3b8;
        }
        QPushButton:pressed {
            background-color: #eef2f7;
        }
        QPushButton#btnImport {
            background-color: #eff6ff;
            border-color: #bfdbfe;
        }
        QPushButton#btnImport:hover {
            background-color: #dbeafe;
            border-color: #60a5fa;
        }
        QPushButton#btnImport:pressed {
            background-color: #bfdbfe;
        }
        QPushButton#btnExport {
            background-color: #ecfdf5;
            border-color: #bbf7d0;
        }
        QPushButton#btnExport:hover {
            background-color: #d1fae5;
            border-color: #34d399;
        }
        QPushButton#btnExport:pressed {
            background-color: #a7f3d0;
        }
        QPushButton#btnDelete {
            background-color: #fff5f5;
            border-color: #fecaca;
        }
        QPushButton#btnDelete:hover {
            background-color: #fee2e2;
            border-color: #f87171;
        }
        QPushButton#btnDelete:pressed {
            background-color: #fecaca;
        }
        QPushButton#btnQuit {
            background-color: #f8fafc;
        }
        QPushButton#btnQuit:hover {
            background-color: #e2e8f0;
            border-color: #94a3b8;
        }
        QPushButton#btnQuit:pressed {
            background-color: #cbd5e1;
        }
        QListWidget#trackList {
            background-color: #ffffff;
            border: none;
            border-radius: 14px;
            padding: 4px;
            outline: 0;
        }
        QListWidget#trackList::item {
            background-color: #ffffff;
            border: 1px solid #e7ebf0;
            border-radius: 12px;
            padding: 10px 12px;
            margin: 4px 2px;
        }
        QListWidget#trackList::item:alternate {
            background-color: #fcfdff;
        }
        QListWidget#trackList::item:selected {
            background-color: #edf5ff;
            border-color: #93c5fd;
            color: #0f172a;
        }
        QListWidget#trackList::item:hover {
            border-color: #cbd5e1;
            background-color: #f8fafc;
        }
        QScrollBar:vertical {
            background: transparent;
            width: 14px;
            margin: 6px 2px 6px 2px;
        }
        QScrollBar::handle:vertical {
            background: #cbd5e1;
            border-radius: 7px;
            min-height: 36px;
        }
        QScrollBar::handle:vertical:hover {
            background: #94a3b8;
        }
        QScrollBar::handle:vertical:pressed {
            background: #64748b;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            background: transparent;
            border: none;
            height: 0px;
        }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
            background: transparent;
        }
        QScrollBar:horizontal {
            background: transparent;
            height: 14px;
            margin: 2px 6px 2px 6px;
        }
        QScrollBar::handle:horizontal {
            background: #cbd5e1;
            border-radius: 7px;
            min-width: 36px;
        }
        QScrollBar::handle:horizontal:hover {
            background: #94a3b8;
        }
        QScrollBar::handle:horizontal:pressed {
            background: #64748b;
        }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            background: transparent;
            border: none;
            width: 0px;
        }
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
            background: transparent;
        }
        QWidget#previewCanvas {
            background: transparent;
        }
        """

    def _message_box_stylesheet(self):
        """Styling für Meldungsdialoge passend zum App-Design."""
        return """
        QMessageBox {
            background-color: #f8fafc;
        }
        QLabel#qt_msgbox_label {
            color: #1f2937;
            background: transparent;
            min-width: 0;
            padding: 2px 0 2px 0;
        }
        QLabel#qt_msgboxex_icon_label {
            background: transparent;
            min-width: 34px;
            min-height: 34px;
            padding-left: 12px;
            padding-right: 12px;
            padding-top: 6px;
            padding-bottom: 6px;
        }
        QMessageBox QPushButton {
            background-color: #ffffff;
            color: #111827;
            border: 1px solid #d5dbe3;
            border-radius: 10px;
            padding: 8px 16px;
            min-width: 92px;
            font-weight: 600;
        }
        QMessageBox QPushButton:hover {
            background-color: #f8fafc;
            border-color: #94a3b8;
        }
        QMessageBox QPushButton:pressed {
            background-color: #eef2f7;
        }
        """

    def _localize_message_box_buttons(self, message_box):
        """Setzt deutsche Beschriftungen für Standard-Buttons in Dialogen."""
        button_labels = {
            QMessageBox.StandardButton.Ok: "OK",
            QMessageBox.StandardButton.Yes: "Ja",
            QMessageBox.StandardButton.No: "Nein",
            QMessageBox.StandardButton.Cancel: "Abbrechen",
            QMessageBox.StandardButton.Close: "Schließen",
        }

        for standard_button, label in button_labels.items():
            button = message_box.button(standard_button)
            if button is not None:
                button.setText(label)

    def _show_message_box(self, title, text, icon, buttons=QMessageBox.StandardButton.Ok,
                          default_button=QMessageBox.StandardButton.NoButton):
        """Zeigt einen gestylten Meldungsdialog an."""
        message_box = QMessageBox(self)
        message_box.setWindowTitle(title)
        message_box.setText(text)
        message_box.setTextFormat(Qt.TextFormat.PlainText)
        message_box.setIcon(icon)
        message_box.setStandardButtons(buttons)
        message_box.setMinimumWidth(460)
        if default_button != QMessageBox.StandardButton.NoButton:
            message_box.setDefaultButton(default_button)
        message_box.setStyleSheet(self._message_box_stylesheet())
        self._localize_message_box_buttons(message_box)
        return message_box.exec()

    def _show_info(self, title, text):
        """Zeigt einen gestylten Info-Dialog an."""
        return self._show_message_box(title, text, QMessageBox.Icon.Information)

    def _show_warning(self, title, text):
        """Zeigt einen gestylten Warn-Dialog an."""
        return self._show_message_box(title, text, QMessageBox.Icon.Warning)

    def _show_error(self, title, text):
        """Zeigt einen gestylten Fehler-Dialog an."""
        return self._show_message_box(title, text, QMessageBox.Icon.Critical)

    def _ask_question(self, title, text,
                      buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                      default_button=QMessageBox.StandardButton.No):
        """Zeigt einen gestylten Bestätigungsdialog an."""
        return self._show_message_box(title, text, QMessageBox.Icon.Question, buttons, default_button)

    def _set_status_message(self, text):
        """Statusmeldungen werden aktuell nicht separat in der GUI angezeigt."""
        return

    def _update_meta_labels(self):
        """Aktualisiert die Meta-Informationen im Kopfbereich."""
        file_text = "Keine Datei geladen"
        if self.current_gpx_file:
            file_text = f"Datei: {Path(self.current_gpx_file).name}"

        track_count = len(self.track_entries)
        track_text = f"{track_count} Track" if track_count == 1 else f"{track_count} Tracks"
        total_distance_m = sum(entry.distance_m for entry in self.track_entries)
        total_elevation_gain_m = sum(entry.elevation_gain_m for entry in self.track_entries)

        self.file_badge_label.setText(file_text)
        self.count_badge_label.setText(track_text)
        self.distance_badge_label.setText(f"Gesamt: {self._format_distance(total_distance_m)}")
        self.elevation_badge_label.setText(f"Anstieg: {self._format_elevation(total_elevation_gain_m)}")

    def _format_distance(self, distance_m):
        """Formatiert Meter als Kilometeranzeige für die GUI."""
        distance_km = max(0.0, distance_m) / 1000.0
        return f"{distance_km:.1f}".replace(".", ",") + " km"

    def _format_elevation(self, elevation_gain_m):
        """Formatiert positive Höhenmeter für die GUI."""
        return f"{int(round(max(0.0, elevation_gain_m)))} hm"

    def _calculate_track_metrics(self, track):
        """Berechnet Distanz und positive Höhenmeter eines Tracks."""
        distance_m = 0.0
        elevation_gain_m = 0.0
        previous_point = None

        for segment in getattr(track, "segments", []):
            for point in segment.points:
                if previous_point is not None:
                    distance_m += gpxpy.geo.haversine_distance(
                        previous_point.latitude,
                        previous_point.longitude,
                        point.latitude,
                        point.longitude,
                    )

                    if previous_point.elevation is not None and point.elevation is not None:
                        elevation_delta = point.elevation - previous_point.elevation
                        if elevation_delta > 0:
                            elevation_gain_m += elevation_delta

                previous_point = point

        return distance_m, elevation_gain_m

    def _xml_local_name(self, tag_name):
        """Liefert den lokalen XML-Tag-Namen ohne Namespace."""
        if not tag_name:
            return ""
        return tag_name.split("}", 1)[-1].split(":")[-1]

    def _normalize_track_color(self, color_value):
        """Normalisiert Farbwerte aus GPX-Extensions auf #RRGGBB."""
        if not color_value:
            return None

        value = color_value.strip()
        if not value:
            return None

        compact_value = value.lower().replace(" ", "").replace("-", "")
        if compact_value in self.GPX_COLOR_MAP:
            return self.GPX_COLOR_MAP[compact_value]

        if value.startswith("#"):
            hex_value = value[1:]
        else:
            hex_value = value

        if len(hex_value) == 3 and all(char in "0123456789abcdefABCDEF" for char in hex_value):
            hex_value = "".join(char * 2 for char in hex_value)

        if len(hex_value) == 6 and all(char in "0123456789abcdefABCDEF" for char in hex_value):
            return f"#{hex_value.lower()}"

        return None

    def _extract_color_from_extensions(self, extensions):
        """Sucht rekursiv nach einer Track-Farbe in GPX-Extensions."""
        for extension in extensions or []:
            tag_name = self._xml_local_name(getattr(extension, "tag", "")).lower()
            text_value = (getattr(extension, "text", "") or "").strip()

            if tag_name in {"displaycolor", "color", "linecolor", "trackcolor", "stroke"}:
                normalized_color = self._normalize_track_color(text_value)
                if normalized_color is not None:
                    return normalized_color

            child_extensions = list(extension)
            if child_extensions:
                nested_color = self._extract_color_from_extensions(child_extensions)
                if nested_color is not None:
                    return nested_color

        return None

    def _fallback_track_color(self, track_id):
        """Liefert eine stabile Fallback-Farbe pro Track."""
        return self.DEFAULT_TRACK_COLORS[track_id % len(self.DEFAULT_TRACK_COLORS)]

    def _extract_source_track_color(self, track):
        """Liefert die bevorzugte Track-Farbe direkt aus der GPX-Quelldatei."""
        track_color = self._extract_color_from_extensions(getattr(track, "extensions", []))
        if track_color is not None:
            return track_color

        for segment in getattr(track, "segments", []):
            segment_color = self._extract_color_from_extensions(getattr(segment, "extensions", []))
            if segment_color is not None:
                return segment_color

        return None

    def _build_unique_color_candidates(self, preferred_color, track_id):
        """Erzeugt Kandidaten für eine eindeutige Track-Farbe."""
        candidates = []

        def add_candidate(color_value):
            normalized_color = self._normalize_track_color(color_value)
            if normalized_color is not None and normalized_color not in candidates:
                candidates.append(normalized_color)

        add_candidate(preferred_color)

        palette_size = len(self.DEFAULT_TRACK_COLORS)
        for offset in range(palette_size):
            add_candidate(self.DEFAULT_TRACK_COLORS[(track_id + offset) % palette_size])

        base_color = QColor(preferred_color if preferred_color is not None else self._fallback_track_color(track_id))
        if not base_color.isValid():
            base_color = QColor(self._fallback_track_color(track_id))

        base_hue = base_color.hue()
        if base_hue < 0:
            base_hue = (track_id * 47) % 360
        base_saturation = max(base_color.saturation(), 140)
        base_value = max(base_color.value(), 130)

        for hue_step in range(0, 360, 29):
            for value_shift in (0, 20, -20, 35, -35):
                variant = QColor()
                variant.setHsv(
                    (base_hue + hue_step + (track_id * 17)) % 360,
                    min(255, base_saturation),
                    max(90, min(245, base_value + value_shift)),
                )
                add_candidate(variant.name())

        return candidates

    def _assign_unique_track_color(self, track, track_id, used_colors):
        """Vergibt eine eindeutige Track-Farbe unter Bevorzugung der GPX-Quellfarbe."""
        preferred_color = self._extract_source_track_color(track)
        if preferred_color is None:
            preferred_color = self._fallback_track_color(track_id)

        for candidate in self._build_unique_color_candidates(preferred_color, track_id):
            if candidate not in used_colors:
                used_colors.add(candidate)
                return candidate

        fallback_color = self._fallback_track_color(track_id)
        used_colors.add(fallback_color)
        return fallback_color

    def _selected_track_entry(self):
        """Liefert den aktuell ausgewählten Track-Eintrag."""
        current_item = self.track_list.currentItem()
        if current_item is None:
            return None

        track_id = current_item.data(Qt.ItemDataRole.UserRole)
        return self._find_track_entry(track_id)

    def _track_point_count(self, entry):
        """Zählt die Punkte eines Track-Eintrags."""
        return sum(len(segment.points) for segment in entry.track.segments)

    def _update_preview(self):
        """Aktualisiert den GPX-Viewer und die zugehörigen Hinweise."""
        selected_entry = self._selected_track_entry()
        selected_track_id = selected_entry.track_id if selected_entry is not None else None
        self.preview_widget.set_tracks(self.track_entries, selected_track_id)

        if not self.track_entries:
            self.preview_info_label.setText("Lade eine GPX-Datei, um die Strecke auf der OSM-Karte zu sehen.")
            return

        if selected_entry is None:
            total_points = sum(self._track_point_count(entry) for entry in self.track_entries)
            self.preview_info_label.setText(
                f"OSM-Kartenvorschau mit {len(self.track_entries)} Tracks und {total_points} Punkten. "
                "Wähle links einen Track aus, um ihn hervorzuheben."
            )
            return

        point_count = self._track_point_count(selected_entry)
        segment_count = len(selected_entry.track.segments)
        self.preview_info_label.setText(
            f"Ausgewählt: {selected_entry.name} | {self._format_distance(selected_entry.distance_m)} | "
            f"{self._format_elevation(selected_entry.elevation_gain_m)} | {segment_count} Segmente | {point_count} Punkte"
        )

    def _find_track_entry(self, track_id):
        """Liefert den Track-Eintrag zu einer stabilen Track-ID."""
        for entry in self.track_entries:
            if entry.track_id == track_id:
                return entry
        return None

    def _sync_track_names(self):
        """Hält die Namensliste kompatibel zur internen Track-Reihenfolge."""
        self.tracks = [entry.name for entry in self.track_entries]

    def _sync_entries_from_list_widget(self):
        """Übernimmt die aktuell sichtbare Listenreihenfolge in das Datenmodell."""
        if self.track_list.count() != len(self.track_entries):
            self._sync_track_names()
            return

        ordered_ids = []
        for row in range(self.track_list.count()):
            item = self.track_list.item(row)
            if item is None:
                continue
            track_id = item.data(Qt.ItemDataRole.UserRole)
            if track_id is not None:
                ordered_ids.append(track_id)

        if len(ordered_ids) != len(self.track_entries):
            self._sync_track_names()
            return

        entries_by_id = {entry.track_id: entry for entry in self.track_entries}
        self.track_entries = [entries_by_id[track_id] for track_id in ordered_ids if track_id in entries_by_id]
        self._sync_track_names()

    def _on_track_rows_moved(self, parent, start, end, destination, row):
        """Synchronisiert Datenmodell und Nummerierung nach Drag & Drop."""
        selected_row = min(row, max(0, len(self.track_entries) - 1))
        self._sync_entries_from_list_widget()
        self._refresh_track_list_display(selected_row)
        self._update_meta_labels()
        self._update_preview()
        self._set_status_message("Track-Reihenfolge aktualisiert")

    def _on_current_track_changed(self, current, previous):
        """Aktualisiert die Vorschau bei geänderter Track-Auswahl."""
        self._update_preview()

    def load_gpx_file(self):
        """GPX-Datei öffnen und laden
        
        Die Reihenfolge der Tracks wird explizit gespeichert, um sicherzustellen,
        dass beim Export die Ausgabeordnung exakt mit der sortierten Eingabereihenfolge übereinstimmt.
        """
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "GPX-Datei auswählen",
            "",
            "GPX Dateien (*.gpx *.GPX);;Alle Dateien (**)"
        )
        
        if filepath:
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    gpx = gpxpy.parse(f)
                
                self.current_gpx_file = filepath
                
                track_entries = []
                used_colors = set()
                for track_id, track in enumerate(gpx.tracks):
                    if hasattr(track, 'name') and track.name:
                        distance_m, elevation_gain_m = self._calculate_track_metrics(track)
                        track_entries.append(
                            TrackEntry(
                                track_id=track_id,
                                name=track.name,
                                track=track,
                                color=self._assign_unique_track_color(track, track_id, used_colors),
                                distance_m=distance_m,
                                elevation_gain_m=elevation_gain_m,
                            )
                        )

                self.track_entries = track_entries
                self._refresh_track_list_display()
                self._update_meta_labels()
                self._update_preview()
                self._set_status_message(f"Geladen: {filepath}")
                self._show_info("GPX-Datei importortiert",
                                f"GPX-Datei '{filepath}' erfolgreich geladen!\n{len(self.tracks)} Tracks gefunden.")
                
            except Exception as e:
                self._show_error("Fehler", f"Fehler beim Laden der GPX-Datei:\n{e}")

    def _on_item_double_click(self, item):
        """Doppelklick auf Track"""
        track_id = item.data(Qt.ItemDataRole.UserRole)
        track_entry = self._find_track_entry(track_id)
        if track_entry is not None:
            track_name = track_entry.name
            self._show_info("Track Info", f"Track: {track_name}\n\nDieser Track wurde ausgewählt.")

    def _confirm_delete_track(self, index):
        """Bestätigungsdialog vor der Track-Löschung"""
        if not self.tracks:
            self._show_warning("Warnung", "Keine Tracks vorhanden zum Löschen!")
            return
        
        # Prüfen ob Index gültig ist (index ist 0-basiert)
        if index < 0 or index >= len(self.tracks):
            self._show_error("Fehler", "Ungültiger Track-Index!")
            return
        
        track_name = self.tracks[index]
        
        # Bestätigungsdialog anzeigen
        reply = self._ask_question(
            "Track löschen",
            f"Möchten Sie den Track '{track_name}' wirklich löschen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._delete_track(index)

    def _delete_track(self, index):
        """Einen Track löschen"""
        self._sync_entries_from_list_widget()
        track_entry = self.track_entries.pop(index)
        track_name = track_entry.name
        self._refresh_track_list_display(min(index, len(self.track_entries) - 1))
        self._update_meta_labels()
        self._update_preview()
        self._set_status_message(f"Track '{track_name}' gelöscht. Verbleibend: {len(self.tracks)}")

    def delete_selected_track_from_menu(self):
        """Button-Click Handler - zeigt Bestätigungsdialog (wie Context Menu)"""
        if not self.tracks:
            self._show_warning("Warnung", "Keine Tracks vorhanden zum Löschen!")
            return
        
        # In PyQt6: currentRow() gibt den 0-basierten Index zurück oder -1 wenn keine Auswahl
        row = self.track_list.currentRow()
        if row < 0:
            self._show_info("Info", "Bitte zuerst einen Track auswählen.")
            return
        
        index = row
        track_name = self.tracks[index]
        
        # Bestätigungsdialog anzeigen (wie beim Context Menu)
        reply = self._ask_question(
            "Track löschen",
            f"Möchten Sie den Track '{track_name}' wirklich löschen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._delete_track(index)

    def delete_tracks(self):
        """Tracks löschen - veraltet, wird durch Single-Selection ersetzt"""
        # Diese Methode bleibt für Kompatibilität bestehen
        self._show_info("Info", "Verwenden Sie bitte den 'Track löschen' Button.")

    def export_gpx_file(self):
        """Verbleibende Tracks als neue GPX-Datei exportieren
        
        Die Exportdateien werden exakt in der Reihenfolge erzeugt, die durch 
        die Sortierung der Quelldatenliste vorgegeben ist. Dies wird sichergestellt,
        indem eine explizite Kopie der sortierten Track-Reihenfolge erstellt wird,
        bevor die XML-Erzeugung erfolgt, um Cache-Probleme und Reihenfolge-Fehler zu vermeiden.
        """
        if not self.tracks:
            self._show_warning("Warnung", "Keine Tracks vorhanden zum Exportieren!")
            return
        
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "GPX-Datei speichern",
            "",
            "GPX Dateien (*.gpx *.GPX)"
        )
        
        if filepath:
            try:
                self._sync_entries_from_list_widget()
                
                gpx_output = gpxpy.gpx.GPX()
                
                combined_track = gpxpy.gpx.GPXTrack()
                combined_track.name = "Zusammengeführter GPX-Track"
                
                segment = gpxpy.gpx.GPXTrackSegment()
                combined_track.segments.append(segment)
                
                for track_entry in self.track_entries:
                    for source_segment in track_entry.track.segments:
                        for point in source_segment.points:
                            new_point = gpxpy.gpx.GPXTrackPoint(
                                latitude=point.latitude,
                                longitude=point.longitude,
                                elevation=point.elevation,
                                time=point.time
                            )
                            segment.points.append(new_point)
                
                gpx_output.tracks.append(combined_track)
                
                # XML-Erzeugung mit expliziter Version-Angabe zur Vermeidung von Cache-Problemen
                gpx_xml = gpx_output.to_xml(version="1.1", prettyprint=True)
                
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(gpx_xml)

                self._update_meta_labels()
                self._set_status_message(f"Exportiert nach: {filepath}")
                self._show_info(
                    "Erfolg",
                    "GPX-Datei erfolgreich exportiert!\n"
                    "Alle Tracks zu einem einzigen Track zusammengefasst.\n"
                    "Reihenfolge entspricht der sortierten Quelldatenliste."
                )
                
            except Exception as e:
                self._show_error("Fehler", f"Fehler beim Exportieren:\n{e}")

    def dragEnterEvent(self, event):
        """Behandle Drag-Enter-Ereignis für Drag & Drop Sortierung
        
        Erlaubt das Absetzen von Text (Track-Namen) in der Track-Liste.
        """
        # Nur Text-Drag & Drop erlauben
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def _refresh_track_list_display_with_selection(self, selected_row):
        """Rendert die Track-Liste neu und erhält optional die Auswahl."""
        self._sync_track_names()
        self.track_list.clear()
        for index, entry in enumerate(self.track_entries, 1):
            item = QListWidgetItem(
                f"{index}. {entry.name} | {self._format_distance(entry.distance_m)} | {self._format_elevation(entry.elevation_gain_m)}"
            )
            item.setData(Qt.ItemDataRole.UserRole, entry.track_id)
            item.setForeground(QColor(entry.color))
            icon_pixmap = QPixmap(14, 14)
            icon_pixmap.fill(Qt.GlobalColor.transparent)
            icon_painter = QPainter(icon_pixmap)
            icon_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            icon_painter.setPen(Qt.PenStyle.NoPen)
            icon_painter.setBrush(QColor(entry.color))
            icon_painter.drawEllipse(1, 1, 12, 12)
            icon_painter.end()
            item.setIcon(QIcon(icon_pixmap))
            self.track_list.addItem(item)

        if 0 <= selected_row < self.track_list.count():
            self.track_list.setCurrentRow(selected_row)

    def _refresh_track_list_display(self, selected_row=None):
        """Update die Track-Liste neu rendern"""
        if selected_row is None:
            selected_row = self.track_list.currentRow()
        self._refresh_track_list_display_with_selection(selected_row)

    def dropEvent(self, event):
        """Leitet Drop-Ereignisse an die Standardverarbeitung weiter."""
        super().dropEvent(event)


def main():
    """Startet die GUI-Anwendung"""
    if os.name == "nt":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("danielrausch82.GPXTrackMerger.1.0.1")

    app = QApplication(sys.argv)
    if os.name == "nt":
        icon_path = resource_path("assets", "gpx-track-merger.ico")
    else:
        icon_path = resource_path("assets", "gpx-track-merger.png")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    
    window = GPXTrackManagerGUI()
    if icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))
    window.showMaximized()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
