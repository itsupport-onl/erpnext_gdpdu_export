## Was und warum

<!-- Was ändert sich, und welches Problem löst es? Issue verlinken. -->

Closes #

## Wie zu testen

<!-- Schritte auf einer Dev-Site oder welche Tests es abdecken. -->

## Checkliste

- [ ] Keine echten Buchhaltungs- oder Personendaten in Code, Tests, Logs,
      Screenshots oder dieser Beschreibung (siehe [SECURITY.md](../SECURITY.md))
- [ ] Nur lesender Zugriff auf Buchhaltungsdaten (CONTRIBUTING.md Regel 1)
- [ ] Bei Feldänderungen: [SPEC.md](../SPEC.md) zuerst angepasst (Regel 2)
- [ ] Tests ergänzt/aktualisiert; `bench --site <site> run-tests --app erpnext_gdpdu_export`
      läuft durch — auf **v15 und v16**
- [ ] `python -m unittest discover -s erpnext_gdpdu_export/tests -t .` läuft ohne Site
- [ ] Bei geändertem DocType oder Workspace: `modified`-Zeitstempel im JSON angehoben
- [ ] `pre-commit run --all-files` läuft durch
- [ ] [CHANGELOG.md](../CHANGELOG.md) unter `## [Unreleased]` ergänzt
