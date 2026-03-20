# GPX Track Merger

Desktop-Anwendung für Windows zum Sortieren, Prüfen, Bereinigen und Exportieren von GPX-Tracks und Waypoints. Die Anwendung bietet eine helle PyQt6-Oberfläche, eine statische OSM-Vorschau, eindeutige Track-Farben, waypointbasierte Symbolanzeige und einen vorbereiteten Export-Workflow für Ride with GPS.

## Download

[Aktuelle EXE herunterladen (v1.0.3)](https://github.com/danielrausch82/GPX-Track-Merger/releases/download/v1.0.3/GPX-Track-Merger-1.0.3.exe)

[Alle Releases ansehen](https://github.com/danielrausch82/GPX-Track-Merger/releases)

## Changelog

[Änderungen zwischen den Versionen ansehen](CHANGELOG.md)

## Screenshot

![Screenshot der Anwendung](assets/screenshot.png)

## Funktionen

- GPX-Dateien importieren und enthaltene Tracks direkt in einer Liste anzeigen.
- Importierte Waypoints separat in einer eigenen Liste anzeigen.
- Tracks per Drag-and-Drop sortieren.
- Einzelne Tracks und einzelne Waypoints gezielt löschen.
- OSM-Vorschau mit allen Tracks und Waypoints anzeigen.
- Ausgewählte Tracks oder Waypoints in der Vorschau hervorheben.
- GPX-Symbole auf Garmin-ähnliche Waypoint-Icons abbilden.
- Bei unbekannten Symbolen automatisch ein generisches Standard-Icon verwenden.
- Track-Farben aus der GPX-Datei übernehmen und bei Farbdopplungen automatisch auf eindeutige Alternativen ausweichen.
- Gesamtkilometer und Höhenmeter der geladenen Tracks anzeigen.
- Alle verbleibenden Tracks in der sichtbaren Reihenfolge zu einer neuen GPX-Datei exportieren.
- Waypoints beim Export vollständig in die neue GPX-Datei übernehmen.
- Den exportierten zusammengeführten Track automatisch nach der Quelldatei ohne Dateiendung benennen.
- Ride-with-GPS-Helfer: exportiert die GPX-Datei in den Ordner gpx-export neben der Anwendung, öffnet die Upload-Seite im Browser und kopiert den Dateinamen in die Zwischenablage.

## Systemanforderungen

- Windows 10 oder Windows 11
- Python 3.10 oder neuer empfohlen
- PyQt6
- gpxpy

## Installation für Entwicklung

1. Virtuelle Umgebung anlegen.
2. Virtuelle Umgebung aktivieren.
3. Abhängigkeiten installieren.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Anwendung starten

```powershell
.\.venv\Scripts\python.exe .\main.py
```

## Bedienung

1. GPX-Datei öffnen.
2. Tracks in der linken Liste per Drag-and-Drop sortieren.
3. Optional einen Track oder einen Waypoint auswählen, um den Eintrag in der Vorschau hervorzuheben.
4. Nicht benötigte Tracks oder Waypoints über Eintrag löschen entfernen.
5. Die verbleibenden Inhalte über GPX exportieren als neue GPX-Datei speichern.
6. Optional Zu Ride with GPS verwenden, um eine Exportdatei im Ordner gpx-export vorzubereiten und direkt die Upload-Seite im Browser zu öffnen.

## Ride with GPS

Der Button Zu Ride with GPS erzeugt eine exportierte GPX-Datei im Ordner gpx-export neben der Anwendung beziehungsweise neben dem Skript im Entwicklungsmodus. Anschließend wird die Ride-with-GPS-Upload-Seite im Browser geöffnet. Der Exportname wird zusätzlich in die Zwischenablage kopiert, damit er beim Upload direkt als Bezeichnung verwendet werden kann.

## EXE-Build

Für einen lokalen Release-Build unter Windows kann PyInstaller verwendet werden:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pyinstaller --noconfirm --clean .\GPX-Track-Merger-1.0.3.spec
```

Die fertige Datei liegt danach unter dist\GPX-Track-Merger-1.0.3.exe.

## Hinweise

- Der Export fasst alle verbleibenden Tracks zu einem einzelnen GPX-Track zusammen.
- Die Exportreihenfolge entspricht immer der sichtbaren Reihenfolge in der Trackliste.
- Waypoints werden beim Export in die neue GPX-Datei übernommen.
- Der Name des exportierten zusammengeführten Tracks entspricht standardmäßig dem Namen der Quelldatei ohne Endung.
- Die Kartenansicht verwendet statische OSM-Kacheln und ist bewusst nicht interaktiv.
- Beim direkten GPX-Import in Hammerhead werden POI- beziehungsweise Waypoint-Punkte laut Plattformverhalten nicht zuverlässig dargestellt, obwohl sie korrekt in der GPX-Datei enthalten sind.

## Release 1.0.3

- Waypoints werden beim Import separat gelistet und in der Kartenansicht dargestellt.
- Garmin-ähnliche Waypoint-Symbole wurden integriert und die Symbolzuordnung verbessert.
- Export übernimmt Waypoints und verwendet den Quelldateinamen als Tracknamen.
- Neuer Ride-with-GPS-Helfer mit Export in den Ordner gpx-export.
- Build- und Versionsmetadaten auf 1.0.3 aktualisiert.

## Troubleshooting

### Import schlägt fehl

Prüfen, ob die GPX-Datei gültig ist und ob PyQt6 sowie gpxpy installiert sind.

### Kein Modul gefunden

```powershell
pip install -r requirements.txt
```

### EXE-Build fehlt

```powershell
pip install -r requirements.txt
```
