import re
import time
import random
import unicodedata
from datetime import datetime

import requests
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials
import os
import json

# ============================================================
# CONFIGURATION
# ============================================================

SHEET = "1ocGyWz7njgjBcWL5kNxBfoNqZZILEQikYx96U4ew1FA"

WORKSHEET_NAME = "Offres IT"
CREDENTIALS_FILE = "credentials.json"

def get_credentials():

    # Sur GitHub Actions
    if os.getenv("GOOGLE_CREDENTIALS"):

        info = json.loads(
            os.environ["GOOGLE_CREDENTIALS"]
        )

        return Credentials.from_service_account_info(
            info,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ],
        )

    # En local
    return Credentials.from_service_account_file(
        CREDENTIALS_FILE,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )

# Villes ciblées
CITIES = {
    "Casablanca": 87750,
    "Rabat": 87607,
    "Salé": 87594,
    "Kénitra": 87667,
    "Mohammedia": 87643,
    "Bouznika": 87753,
}

LIMIT = 50

# Petite pause entre les requêtes
DELAY = (0.5, 1.2)

# Si l'API retourne 403, mettre True
USE_BROWSER = False


API = "https://api.stagiaires.ma/api/v1/public/annonces"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)


# ============================================================
# NORMALISATION
# ============================================================

def norm(text):
    """
    Normalise un texte :
    - supprime les accents
    - met en minuscules
    - nettoie les espaces
    """
    text = unicodedata.normalize("NFD", text or "")

    text = "".join(
        c for c in text
        if unicodedata.category(c) != "Mn"
    )

    return " ".join(text.lower().strip().split())


def strip_html(html):
    """
    Transforme une description HTML en texte simple.
    """
    return BeautifulSoup(
        html or "",
        "html.parser"
    ).get_text(" ", strip=True)


# ============================================================
# FILTRE DOMAINE INFORMATIQUE
# ============================================================

# Mots-clés très pertinents pour ton domaine.
# On reste volontairement large pour éviter de rater
# une bonne offre IA / Data / Dev / IT.

IT_KEYWORDS = [

    # Informatique générale
    "informatique",
    "informatique de gestion",
    "technologies de l'information",
    "technologies de l'information",
    "systeme d'information",
    "systemes d'information",
    "si",
    "it",

    # Développement
    "developpeur",
    "developpeuse",
    "developer",
    "software developer",
    "software engineer",
    "ingenieur logiciel",
    "ingenieur informatique",
    "developpement",
    "development",
    "programmation",
    "programming",

    # Web
    "web",
    "full stack",
    "fullstack",
    "front end",
    "frontend",
    "back end",
    "backend",
    "site web",
    "application web",
    "application mobile",

    # Langages
    "python",
    "java",
    "javascript",
    "typescript",
    "php",
    "laravel",
    "symfony",
    "node.js",
    "nodejs",
    "express",
    "react",
    "angular",
    "vue.js",
    "vuejs",
    ".net",
    "c#",
    "c++",

    # IA / Machine Learning
    "intelligence artificielle",
    "ia",
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "generative ai",
    "genai",
    "llm",
    "large language model",
    "nlp",
    "natural language processing",
    "computer vision",
    "vision par ordinateur",
    "reinforcement learning",
    "tensorflow",
    "pytorch",
    "keras",
    "scikit-learn",

    # Data
    "data science",
    "data scientist",
    "data analyst",
    "data engineer",
    "data engineering",
    "big data",
    "data mining",
    "data warehouse",
    "business intelligence",
    "bi",
    "power bi",
    "tableau",
    "etl",
    "elt",
    "sql",
    "nosql",
    "database",
    "base de donnees",
    "bases de donnees",
    "mongodb",
    "mysql",
    "postgresql",
    "oracle",
    "cassandra",
    "duckdb",

    # Cloud / DevOps / MLOps
    "cloud",
    "aws",
    "azure",
    "gcp",
    "devops",
    "devsecops",
    "mlops",
    "dataops",
    "docker",
    "kubernetes",
    "ci/cd",
    "jenkins",
    "github actions",
    "gitlab ci",

    # Réseaux / systèmes / cybersécurité
    "reseau",
    "reseaux",
    "network",
    "systeme",
    "systems",
    "linux",
    "windows server",
    "administrateur systeme",
    "administrateur reseau",
    "infrastructure",
    "infrastructure informatique",
    "cybersecurite",
    "cybersecurity",
    "securite informatique",
    "securite des systemes",
    "soc",
    "pentest",

    # ERP / CRM / logiciels
    "erp",
    "crm",
    "odoo",
    "sap",
    "salesforce",
    "oracle",
    "sage",
    "dynamics",

    # QA / automatisation
    "qa",
    "quality assurance",
    "test logiciel",
    "tests logiciels",
    "software testing",
    "automatisation",
    "automation",
    "rpa",

    # Mobile
    "android",
    "ios",
    "flutter",
    "react native",

    # API / architecture
    "api",
    "rest api",
    "microservices",
    "architecture logicielle",
    "architecture logiciel",

    # Git / outils techniques
    "git",
    "github",
    "gitlab",
    "bitbucket",
]


# Mots qui indiquent généralement une offre
# clairement hors informatique.
# Ils ne bloquent PAS automatiquement une offre :
# ils servent uniquement à éviter certains faux positifs.

NON_IT_KEYWORDS = [
    "comptabilite",
    "comptable",
    "finance",
    "controle de gestion",
    "audit financier",
    "ressources humaines",
    "rh",
    "recrutement",
    "marketing",
    "communication",
    "commercial",
    "vente",
    "sales",
    "architecture d'interieur",
    "architecture interieur",
    "architecte d'interieur",
    "decoration",
    "decorateur",
    "juridique",
    "avocat",
    "logistique",
    "achat",
    "achats",
    "qualite alimentaire",
]


def is_it_offer(a):
    """
    Détermine si une offre est suffisamment liée
    à l'informatique.

    Le titre est plus important que la description.
    """

    title = norm(a.get("titre", ""))
    description = norm(
        strip_html(a.get("description", ""))
    )

    # --------------------------------------------------------
    # 1. Recherche dans le titre
    # --------------------------------------------------------

    title_matches = [
        keyword
        for keyword in IT_KEYWORDS
        if keyword in title
    ]

    # --------------------------------------------------------
    # 2. Recherche dans la description
    # --------------------------------------------------------

    description_matches = [
        keyword
        for keyword in IT_KEYWORDS
        if keyword in description
    ]

    # --------------------------------------------------------
    # 3. Score
    #
    # Un mot informatique dans le titre = 3 points
    # Un mot informatique dans la description = 1 point
    # --------------------------------------------------------

    score = (
        len(set(title_matches)) * 3
        +
        len(set(description_matches))
    )

    # --------------------------------------------------------
    # 4. Détection des domaines clairement hors IT
    # --------------------------------------------------------

    non_it_matches = [
        keyword
        for keyword in NON_IT_KEYWORDS
        if keyword in title
    ]

    # --------------------------------------------------------
    # 5. Décision
    # --------------------------------------------------------

    # Si le titre contient un mot IT :
    # on accepte quasiment toujours.
    if title_matches:
        return True

    # Si le titre est hors domaine ET qu'il n'y a
    # pratiquement aucun signal informatique :
    if non_it_matches and score < 3:
        return False

    # Si plusieurs éléments IT apparaissent
    # dans la description, on garde.
    if score >= 3:
        return True

    return False


# ============================================================
# SESSION HTTP
# ============================================================

session = requests.Session()

session.headers.update({
    "User-Agent": UA,
    "Accept": "application/json",
    "Origin": "https://www.stagiaires.ma",
    "Referer": "https://www.stagiaires.ma/",
})


_browser = {}


# ============================================================
# APPEL API
# ============================================================

def api_get(params):

    for attempt in range(5):

        try:

            # ------------------------------------------------
            # Mode navigateur
            # ------------------------------------------------

            if USE_BROWSER:

                if "ctx" not in _browser:

                    from playwright.sync_api import sync_playwright

                    pw = sync_playwright().start()

                    browser = pw.chromium.launch(
                        headless=True
                    )

                    ctx = browser.new_context(
                        user_agent=UA
                    )

                    page = ctx.new_page()

                    page.goto(
                        "https://www.stagiaires.ma/stage-emploi-maroc",
                        wait_until="networkidle",
                        timeout=60000
                    )

                    _browser["ctx"] = ctx

                response = _browser["ctx"].request.get(
                    API,
                    params=params
                )

                if response.ok:
                    return response.json()

                status = response.status

            # ------------------------------------------------
            # Requests classique
            # ------------------------------------------------

            else:

                response = session.get(
                    API,
                    params=params,
                    timeout=40
                )

                if response.status_code == 200:
                    return response.json()

                status = response.status_code

            print(
                f"   ! HTTP {status}, "
                f"nouvelle tentative..."
            )

        except Exception as e:

            print(
                f"   ! erreur réseau : {e}"
            )

        time.sleep(
            4 * (attempt + 1)
        )

    raise SystemExit(
        "\nAPI inaccessible.\n"
        "Essaie USE_BROWSER = True si tu reçois des 403."
    )


# ============================================================
# RÉCUPÉRATION DES OFFRES D'UNE VILLE
# ============================================================

def fetch_city(city_id):

    items = []
    offset = 0

    while True:

        data = api_get({

            "limit": LIMIT,

            "offset": offset,

            "statut": "Validée",

            "entreprise_valid": "true",

            "city": city_id,

            "sortBy": "date_publication",

            "order": "DESC",
        })

        batch = data.get(
            "data",
            []
        )

        pagination = data.get(
            "pagination",
            {}
        )

        items.extend(batch)

        print(
            f"   offset {offset}: "
            f"+{len(batch)} "
            f"/ total ville : "
            f"{pagination.get('total', '?')}"
        )

        if (
            not batch
            or
            not pagination.get("hasNextPage")
        ):
            break

        offset += len(batch)

        time.sleep(
            random.uniform(*DELAY)
        )

    return items


# ============================================================
# FILTRE DATE
# ============================================================

def not_expired(a):

    expiration = (
        a.get("date_expiration") or ""
    )[:10]

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    return (
        not expiration
        or
        expiration >= today
    )


# ============================================================
# GOOGLE SHEETS
# ============================================================

HEADER = [
    "Titre",
    "Entreprise",
    "Ville",
    "Type de stage",
    "Mode",
    "Publié le",
    "Expire le",
    "URL Stagiaires",
    "URL Source",
    "Scrapé le",
]


def get_sheet():

    credentials = get_credentials()

    print(
        "Compte de service :",
        credentials.service_account_email
    )

    spreadsheet_id = SHEET

    # --------------------------------------------------------
    # Connexion au Google Sheet
    # --------------------------------------------------------

    try:
        spreadsheet = (
            gspread
            .authorize(credentials)
            .open_by_key(spreadsheet_id)
        )

    except gspread.exceptions.SpreadsheetNotFound:

        raise SystemExit(
            "\nSheet introuvable.\n"
            f"ID utilisé : {spreadsheet_id}\n"
            f"Partage le Sheet avec : "
            f"{credentials.service_account_email}"
        )

    # --------------------------------------------------------
    # Chercher l'onglet "Offres IT"
    # --------------------------------------------------------

    try:

        ws = spreadsheet.worksheet(
            WORKSHEET_NAME
        )

        print(
            f"Onglet '{WORKSHEET_NAME}' trouvé ✅"
        )

    except gspread.WorksheetNotFound:

        print(
            f"Création de l'onglet "
            f"'{WORKSHEET_NAME}'..."
        )

        ws = spreadsheet.add_worksheet(
            title=WORKSHEET_NAME,
            rows=1000,
            cols=len(HEADER)
        )

        ws.append_row(
            HEADER,
            value_input_option="RAW"
        )

        print(
            f"Onglet '{WORKSHEET_NAME}' créé ✅"
        )

        return ws

    # --------------------------------------------------------
    # Vérifier si l'onglet possède déjà un header
    # --------------------------------------------------------

    first_row = ws.row_values(1)

    if not first_row:

        ws.append_row(
            HEADER,
            value_input_option="RAW"
        )

        print(
            "Header ajouté ✅"
        )

    return ws


# ============================================================
# CONVERSION OFFRE → LIGNE GOOGLE SHEETS
# ============================================================

def to_row(a, ville_label):

    return [

        # Titre
        a.get(
            "titre",
            ""
        ),

        # Entreprise
        (
            a.get("entreprise") or {}
        ).get(
            "nom",
            ""
        ),

        # Ville
        ville_label,

        # Type de stage
        a.get(
            "type_stage",
            ""
        ) or "",

        # Mode
        a.get(
            "type_de_lieu_de_travail",
            ""
        ) or "",

        # Date publication
        (
            a.get("date_publication") or ""
        )[:10],

        # Date expiration
        (
            a.get("date_expiration") or ""
        )[:10],

        # URL Stagiaires
        a.get(
            "lien_publique",
            ""
        ),

        # URL source
        a.get(
            "lien_annonce",
            ""
        ) or "",

        # Date scraping
        datetime.now().strftime(
            "%Y-%m-%d %H:%M"
        ),
    ]


# ============================================================
# PROGRAMME PRINCIPAL
# ============================================================

def main():

    ws = get_sheet()

    print(
        "\nConnexion Google Sheet OK ✅\n"
    )

    # --------------------------------------------------------
    # Récupérer les URLs déjà présentes
    # --------------------------------------------------------
    #
    # URL Stagiaires = colonne H
    #
    # Cela permet d'éviter les doublons
    # sans avoir besoin de l'ID.
    # --------------------------------------------------------

    existing_urls = set(
        ws.col_values(8)[1:]
    )

    selected = []

    seen_urls = set()

    total_scraped = 0
    total_it = 0

    # ========================================================
    # PARCOURIR LES VILLES
    # ========================================================

    for ville, city_id in CITIES.items():

        print(
            f"== {ville} "
            f"(city={city_id}) =="
        )

        items = fetch_city(
            city_id
        )

        total_scraped += len(items)

        # ----------------------------------------------------
        # Filtrage
        # ----------------------------------------------------

        kept = []

        for offer in items:

            # Offre encore active
            if not not_expired(offer):
                continue

            # Offre informatique
            if not is_it_offer(offer):
                continue

            kept.append(
                offer
            )

        total_it += len(kept)

        print(
            f"   -> {len(items)} offres récupérées"
        )

        print(
            f"   -> {len(kept)} offres IT pertinentes"
        )

        # ----------------------------------------------------
        # Déduplication
        # ----------------------------------------------------

        for offer in kept:

            url = (
                offer.get(
                    "lien_publique",
                    ""
                )
                or
                offer.get(
                    "lien_annonce",
                    ""
                )
            )

            if not url:
                continue

            # Déjà vue pendant ce scraping
            if url in seen_urls:
                continue

            seen_urls.add(url)

            selected.append(
                (
                    offer,
                    ville,
                    url
                )
            )

        print()

    # ========================================================
    # PRÉPARER LES NOUVELLES LIGNES
    # ========================================================

    rows = []

    for offer, ville, url in selected:

        # Déjà présente dans Google Sheets
        if url in existing_urls:
            continue

        rows.append(
            to_row(
                offer,
                ville
            )
        )

    # ========================================================
    # RÉSULTAT
    # ========================================================

    print(
        "======================================"
    )

    print(
        f"Total offres récupérées : "
        f"{total_scraped}"
    )

    print(
        f"Offres IT pertinentes : "
        f"{total_it}"
    )

    print(
        f"Nouvelles offres à ajouter : "
        f"{len(rows)}"
    )

    print(
        "======================================"
    )

    # ========================================================
    # AJOUT DANS GOOGLE SHEETS
    # ========================================================

    if not rows:

        print(
            "\nAucune nouvelle offre à ajouter."
        )

        return

    for i in range(
        0,
        len(rows),
        200
    ):

        ws.append_rows(
            rows[i:i + 200],
            value_input_option="RAW"
        )

    print(
        "\nTerminé ✅"
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()