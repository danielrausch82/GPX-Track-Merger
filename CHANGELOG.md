# Changelog

## [1.0.2] - 2026-03-18

### Features
- **Richtungsampeln (Pfeile)**: Kompakte, stilisierte Richtungspfeile wurden entlang des Tracks integriert, um dem Nutzer eine intuitive visuelle Führung durch den Verlauf zu bieten
- Die Pfeile folgen exakt der lokalen Tangente des Pfades und zeigen die Bewegungsrichtung an
- Alle 10 km werden ein Pfeil platziert (basierend auf geographischer Distanz mit Haversine-Formel)
- Die Pfeile sind farblich an den jeweiligen Track angepasst (10 Pixel Größe)

### Technical
- Implementierung von `haversine_distance()` für präzise Entfernungsberechnung zwischen GPS-Punkten
- Optimierung der Pfeilverteilung für gleichmäßige Sichtbarkeit auf der Karte

## [1.0.1] - 2026-03-XX

*(Vorherige Versionen sind hier dokumentiert)*
