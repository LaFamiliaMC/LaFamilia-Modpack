# La Familia: Drei ZIP-Dateien fuer den aktuellen Launcher aufbereiten

Dieser Workflow macht deinen bestehenden **Release-Entwurf modpack-v1.0.1** mit
dem automatischen Modpack-Manager des Electron-Launchers kompatibel.

Der aktuelle Launcher v1.4.57 verwendet **Manifest-Schema 2** und erwartet:
- Mods als einzelne signierte/gehashte GitHub-Release-JARs
- `resourcepacks.zip` und `config.zip`
- `manifest.json` mit Dateinamen, Dateigroessen und SHA-256-Werten.

Ein Release mit nur drei ZIPs kann der Launcher nicht installieren.

## Einmalige Vorbereitung

1. Im GitHub-Repository `LaFamiliaMC/LaFamilia-Modpack` unter **Actions**
   den Workflow **ZIP-Modpack fuer La Familia Launcher vorbereiten** waehlen.
2. **Run workflow** mit Version `1.0.1` starten.
3. Der Workflow prueft `mods.zip`, `resourcepacks.zip` und `config.zip`,
   laedt einzelne Mod-JARs in denselben *Entwurf* und erstellt `manifest.json`.
4. Erneut unter **Releases** kontrollieren, dass das Manifest und alle Mod-Dateien
   vorhanden sind. Vor der Veroeffentlichung die ZIPs auf sensible Konfigurationen
   und auf erlaubte Redistribution der enthaltenen Mods pruefen.
5. Erst danach den Release ueber **Publish release** veroeffentlichen.
6. Den Launcher v1.4.57 oeffnen, **Auf Updates pruefen** und eine
   Testinstallation auf einem zweiten Rechner oder in einem separaten
   Minecraft-Spielordner durchfuehren.

## Sicherheitsverhalten

- Aendert keinen veroeffentlichten Release; nur *Entwuerfe*.
- Kein automatisches Veroeffentlichen oder Loeschen alter Releases.
- Prueft problematische Dateinamen, Duplikate, ZIP-Symlinks und Dateigroessen.
- SHA-256-Hashes werden aus den ZIP-Inhalten berechnet.
- Der Launcher prueft SHA-256 erneut und schuetzt manuell geaenderte Dateien.
- Verwendet GitHub Actions `GITHUB_TOKEN`; kein PAT auf dem Desktop erforderlich.

**Hinweis:** Das Entpacken der ZIPs in den Workflow wird zur Erstellung des
Manifests gebraucht; die Dateien werden nicht direkt in die Spielerinstallation
geschrieben. Fuer grosse Modpacks kann die Aufbereitung mehrere Minuten dauern.
