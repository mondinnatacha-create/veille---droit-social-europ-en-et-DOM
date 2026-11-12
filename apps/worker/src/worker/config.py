"""Configuration de l'agent de veille droit social (Europe et DOM)."""

AGENT_TITLE = "Veille droit social - Europe et DOM"
WORKFLOW_NAME = "veille-droit-social-ue-dom"
DEFAULT_LIBRARY_ID = "01a1cff3-5f8c-725f-8169-4ef5eb12b548"
LLM_MODEL = "mistral-medium-latest"

DOM_KEYWORDS = [
    "outre-mer", "outremer", "ultrapériphérique", "guadeloupe", "martinique",
    "guyane", "la réunion", "réunion", "mayotte", "polynésie", "calédonie",
    "saint-pierre", "wallis", "saint-martin", "dom",
]

SOCIAL_KEYWORDS = [
    "sécurité sociale", "protection sociale", "retraite", "maladie",
    "prestation", "allocation", "rsa", "invalidité", "chômage", "famille",
    "santé", "inclusion", "pauvreté", "handicap", "cotisation", "urssaf",
    "cpam", "cnaf", "cnav", "solidarité",
]

SOURCES = [
    {
        "name": "Commission européenne - Emploi, affaires sociales et inclusion",
        "url": "https://ec.europa.eu/social/rss.jsp?langId=fr&feedId=27",
        "kind": "rss",
        "max_items": 15,
        "keywords": SOCIAL_KEYWORDS,
    },
    {
        "name": "Cour de justice de l'UE - Communiqués de presse",
        "url": "https://curia.europa.eu/site/jcms/qua1_6621/fr/rss",
        "kind": "rss",
        "max_items": 12,
        "keywords": SOCIAL_KEYWORDS,
    },
    {
        "name": "EUR-Lex - Journal officiel de l'UE",
        "url": "https://eur-lex.europa.eu/rss/oj.html",
        "kind": "rss",
        "max_items": 12,
        "keywords": SOCIAL_KEYWORDS + DOM_KEYWORDS,
    },
    {
        "name": "Ministère du Travail - filtre protection sociale",
        "url": "https://travail-emploi.gouv.fr/rss.xml",
        "kind": "rss",
        "max_items": 12,
        "keywords": SOCIAL_KEYWORDS,
    },
    {
        "name": "Bulletins officiels sociaux - filtre protection sociale",
        "url": "https://bulletins-officiels.social.gouv.fr/rss.xml",
        "kind": "rss",
        "max_items": 12,
        "keywords": SOCIAL_KEYWORDS + DOM_KEYWORDS,
    },
    {
        "name": "URSSAF - Actualités",
        "url": "https://www.urssaf.fr/portail/home/actualites.html",
        "kind": "html",
        "link_pattern": "/accueil/actualites/.+",
        "max_items": 12,
    },
    {
        "name": "Vie-publique.fr - Lois, filtre protection sociale",
        "url": "https://www.vie-publique.fr/lois-feeds.xml",
        "kind": "rss",
        "max_items": 12,
        "keywords": SOCIAL_KEYWORDS + DOM_KEYWORDS,
    },
    {
        "name": "Vie-publique.fr - Actualités, filtre Europe",
        "url": "https://www.vie-publique.fr/actualites-feeds.xml",
        "kind": "rss",
        "max_items": 12,
        "keywords": [
            "europe", "européen", "union européenne", "directive",
            "cjue", "cour de justice", "commission européenne",
        ],
    },
]
