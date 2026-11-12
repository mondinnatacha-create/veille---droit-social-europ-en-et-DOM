# Veille droit social - Europe et DOM

Agent de veille hebdomadaire sur le droit du travail français : workflow Mistral
qui collecte les nouveautés sur les sources officielles, synthétise un rapport
avec un modèle Mistral, et publie le rapport dans une bibliothèque de documents Mistral.

## Fonctionnement

1. **Collecte** (`collect_sources`) : interroge chaque source (flux RSS ou page HTML),
   filtre par date (fenêtre glissante de 7 jours par défaut) et par mots-clés.
   Une source en échec n'interrompt jamais le run : elle est signalée dans le rapport.
2. **Synthèse** (`synthesize_report`) : un modèle Mistral rédige un rapport Markdown
   structuré (synthèse exécutif, textes officiels, jurisprudence, URSSAF/protection
   sociale, sources indisponibles) à partir des seuls éléments collectés.
3. **Publication** (`publish_report`) : le rapport est déposé dans la bibliothèque
   Mistral configurée (`VEILLE_LIBRARY_ID` ou `DEFAULT_LIBRARY_ID` dans `worker/config.py`).

## Sources surveillées

- Commission européenne (emploi, affaires sociales et inclusion)
- Cour de justice de l'UE (communiqués, filtrés protection sociale)
- EUR-Lex (Journal officiel de l'UE, filtré)
- Ministère du Travail et bulletins officiels sociaux (filtrés protection sociale)
- URSSAF (actualités)
- Vie-publique.fr (lois, filtrées protection sociale)

Pour ajouter ou retirer une source, éditer `apps/worker/src/worker/config.py`
(`kind`: `rss` ou `html`, option `keywords` pour filtrer, option `link_pattern`
pour les pages HTML, option `max_items`).

## Exécution

- Manuelle : input `{"lookback_days": 7, "dry_run": false}`.
- `dry_run: true` : collecte et synthèse sans publication en bibliothèque.
- Planification hebdomadaire (lundi matin) gérée via un schedule Mistral Workflows.

## Développement

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest tests
```

Le worker se lance avec `python -m worker.entrypoints.worker` (depuis la racine,
avec `PYTHONPATH=apps/worker/src`). En production, le déploiement géré Mistral
build l'image `Dockerfile` et injecte un jeton de compte de service : aucun secret
dans le dépôt.
