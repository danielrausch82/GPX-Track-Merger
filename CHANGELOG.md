# Changelog

## [1.0.3] - 2026-03-20

### Features
- GPX-Tracks und Waypoints werden gemeinsam importiert, in getrennten Listen angezeigt und in der Kartenansicht dargestellt.
- Waypoints werden mit Garmin-aehnlichen Symbolen angezeigt; unbekannte GPX-Symbole erhalten ein generisches Fallback-Icon.
- Der Export uebernimmt Waypoints und benennt den zusammengefuehrten Track standardmaessig nach der Quelldatei ohne Dateiendung.
- Neuer Ride-with-GPS-Helfer: exportiert nach gpx-export, oeffnet die Upload-Seite und kopiert den Dateinamen in die Zwischenablage.

### Technical
- Vollstaendige Garmin-GIF-Symbolsammlung in assets/waypoints integriert und die Symbolzuordnung fuer GPX-Symbole verbessert.
- Gemeinsame GPX-Exportlogik fuer Datei-Export und Ride-with-GPS-Vorbereitung eingefuehrt.
- Build- und Versionsmetadaten auf 1.0.3 aktualisiert.

## [1.0.2] - 2026-03-18

### Features
- **Richtungsampeln (Pfeile)**: Kompakte, stilisierte Richtungspfeile wurden entlang des Tracks integriert, um dem Nutzer eine intuitive visuelle Führung durch den Verlauf zu bieten
- Die Pfeile folgen exakt der lokalen Tangente des Pfades und zeigen die Bewegungsrichtung an
- Alle 10 km werden ein Pfeil platziert (basierend auf geographischer Distanz mit Haversine-Formel)
- Die Pfeile sind farblich an den jeweiligen Track angepasst (10 Pixel Größe)

### Technical
- Implementierung von `haversine_distance()` für präzise Entfernungsberechnung zwischen GPS-Punkten
- Optimierung der Pfeilverteilung für gleichmäßige Sichtbarkeit auf der Karte

## [1.0.1] - 2026-03-17

Überarbeitetes helles UI mit kompakterem Layout.
Integrierte OSM-Vorschau für importierte Tracks.
Anzeige von Distanz und Höhenmetern pro Track und gesamt.
Eindeutige Farblogik für Tracks bei importierten GPX-Farbdopplungen.
Bereinigte Lösch- und Importdialoge.
