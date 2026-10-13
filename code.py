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

CITY_SLUGS = {
    87750: "casablanca",
    87607: "rabat",
    87594: "sale",
    87667: "kenitra",
    87643: "mohammedia",
    87753: "bouznika",
}

LIMIT = 50

# Petite pause entre les requêtes
DELAY = (0.5, 1.2)

# Si l'API retourne 403, mettre True
USE_BROWSER = True


API = "https://api.stagiaires.ma/api/v1/public/annonces"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/141.0.0.0 Safari/537.36"
)


class ApiUnavailable(Exception):
    pass


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

TITLE_IT_KEYWORDS = [
    keyword
    for keyword in IT_KEYWORDS
    if keyword not in {
        "si",
        "it",
        "ia",
        "bi",
        "web",
        "api",
        "git",
        "qa",
        "sql",
        "crm",
        "erp",
        "automation",
        "automatisation",
        "reseau",
        "reseaux",
        "network",
        "systeme",
        "systems",
        "soc",
        "development",
        "oracle",
        "sage",
        "dynamics",
    }
]

STRONG_DESCRIPTION_KEYWORDS = [
    "informatique",
    "systeme d'information",
    "systemes d'information",
    "developpeur",
    "developpeuse",
    "developer",
    "software",
    "logiciel",
    "programmation",
    "application web",
    "application mobile",
    "python",
    "java",
    "javascript",
    "typescript",
    "php",
    "laravel",
    "symfony",
    "node.js",
    "nodejs",
    "react",
    "angular",
    "vue",
    ".net",
    "c#",
    "c++",
    "intelligence artificielle",
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "llm",
    "nlp",
    "computer vision",
    "tensorflow",
    "pytorch",
    "data science",
    "data scientist",
    "data analyst",
    "data engineer",
    "big data",
    "business intelligence",
    "power bi",
    "etl",
    "sql",
    "nosql",
    "base de donnees",
    "cloud",
    "aws",
    "azure",
    "gcp",
    "devops",
    "mlops",
    "docker",
    "kubernetes",
    "cybersecurite",
    "cybersecurity",
    "securite informatique",
    "administrateur systeme",
    "administrateur reseau",
    "qa",
    "test logiciel",
    "software testing",
    "technical support",
    "support engineer",
    "android",
    "ios",
    "flutter",
    "react native",
    "api",
    "microservices",
]

WEAK_DESCRIPTION_KEYWORDS = [
    "web",
    "site web",
    "internet",
    "excel",
    "word",
    "powerpoint",
    "reseaux sociaux",
    "digital",
    "numerique",
    "crm",
    "erp",
    "sap",
    "odoo",
    "salesforce",
    "automatisation",
    "automation",
    "git",
    "github",
]

IT_TITLE_PATTERNS = [
    r"\bdata\b",
    r"\bdev\b",
    r"\bia\b",
    r"\bai\b",
    r"\bit\b",
    r"\bbi\b",
    r"\bqa\b",
    r"\bsoc\b",
    r"\bui\s*/?\s*ux\b",
]


# Mots qui indiquent généralement une offre
# clairement hors informatique.

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
    "agroalimentaire",
    "gestion administrative",
    "administratif",
    "assistanat",
    "assistant",
    "office manager",
    "community manager",
    "community management",
    "reseaux sociaux",
    "design graphique",
    "graphisme",
    "infographie",
    "video",
    "photographie",
    "evenementiel",
    "journalisme",
    "tourisme",
    "hotellerie",
    "restauration",
    "supply chain",
    "transport",
    "genie civil",
    "btp",
    "immobilier",
    "banque",
    "assurance",
    "sante",
    "medical",
    "pharmacie",
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

    title_matches = [
        keyword
        for keyword in TITLE_IT_KEYWORDS
        if keyword in title
    ]

    title_pattern_matches = [
        pattern
        for pattern in IT_TITLE_PATTERNS
        if re.search(pattern, title)
    ]

    strong_description_matches = [
        keyword
        for keyword in STRONG_DESCRIPTION_KEYWORDS
        if keyword in description
    ]

    weak_description_matches = [
        keyword
        for keyword in WEAK_DESCRIPTION_KEYWORDS
        if keyword in description
    ]

    non_it_matches = [
        keyword
        for keyword in NON_IT_KEYWORDS
        if keyword in title
    ]

    if title_matches or title_pattern_matches:
        return True

    strong_count = len(set(strong_description_matches))
    weak_count = len(set(weak_description_matches))

    # RH/communication/finance/etc. restent exclus sauf si
    # le titre annonce clairement une fonction IT.
    if non_it_matches:
        return False

    if strong_count >= 2:
        return True

    if strong_count >= 1 and weak_count >= 2 and not non_it_matches:
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


# _browser = {}


# # ============================================================
# # APPEL API
# # ============================================================

# def api_get(params):

#     for attempt in range(5):

#         try:

#             # ------------------------------------------------
#             # Mode navigateur
#             # ------------------------------------------------

#             if USE_BROWSER:

#                 if "ctx" not in _browser:

#                     from playwright.sync_api import sync_playwright

#                     pw = sync_playwright().start()

#                     browser = pw.chromium.launch(
#                         headless=True
#                     )

#                     ctx = browser.new_context(
#                         user_agent=UA
#                     )

#                     page = ctx.new_page()

#                     page.goto(
#                         "https://www.stagiaires.ma/stage-emploi-maroc",
#                         wait_until="networkidle",
#                         timeout=60000
#                     )

#                     _browser["ctx"] = ctx

#                 response = _browser["ctx"].request.get(
#                     API,
#                     params=params
#                 )

#                 if response.ok:
#                     return response.json()

#                 status = response.status

#             # ------------------------------------------------
#             # Requests classique
#             # ------------------------------------------------

#             else:

#                 response = session.get(
#                     API,
#                     params=params,
#                     timeout=40
#                 )

#                 if response.status_code == 200:
#                     return response.json()

#                 status = response.status_code

#             print(
#                 f"   ! HTTP {status}, "
#                 f"nouvelle tentative..."
#             )

#         except Exception as e:

#             print(
#                 f"   ! erreur réseau : {e}"
#             )

#         time.sleep(
#             4 * (attempt + 1)
#         )

#     raise SystemExit(
#         "\nAPI inaccessible.\n"
#         "Essaie USE_BROWSER = True si tu reçois des 403."
#     )


_browser = {}


def init_browser():
    """
    Initialise Chromium une seule fois.
    Le navigateur ouvre d'abord le site Stagiaires.ma
    afin d'obtenir une session/cookies avant d'appeler l'API.
    """

    if "ctx" in _browser:
        return _browser["ctx"]

    from playwright.sync_api import sync_playwright

    print("   🌐 Initialisation du navigateur...")

    pw = sync_playwright().start()

    browser = pw.chromium.launch(
        headless=True
    )

    ctx = browser.new_context(
        user_agent=UA,
        viewport={
            "width": 1366,
            "height": 768
        },
        locale="fr-FR",
        timezone_id="Africa/Casablanca",
    )

    page = ctx.new_page()

    print("   🌐 Ouverture de Stagiaires.ma...")

    page.goto(
        "https://www.stagiaires.ma/stage-emploi-maroc",
        wait_until="domcontentloaded",
        timeout=60000
    )

    # Petite attente pour laisser le site initialiser
    page.wait_for_timeout(3000)

    print(
        f"   🌐 Page chargée : {page.title()}"
    )

    _browser["pw"] = pw
    _browser["browser"] = browser
    _browser["ctx"] = ctx
    _browser["page"] = page

    return ctx


def api_get(params):

    for attempt in range(5):

        try:

            # =================================================
            # MODE PLAYWRIGHT
            # =================================================

            if USE_BROWSER:

                ctx = init_browser()

                print(
                    f"   🌐 Requête API via navigateur "
                    f"(tentative {attempt + 1}/5)..."
                )

                response = ctx.request.get(
                    API,
                    params=params,
                    headers={
                        "Accept": "application/json",
                        "Referer": "https://www.stagiaires.ma/",
                    },
                    timeout=60000,
                )

                status = response.status

                print(
                    f"   API HTTP {status}"
                )

                if response.ok:
                    return response.json()

            # =================================================
            # MODE REQUESTS
            # =================================================

            else:

                response = session.get(
                    API,
                    params=params,
                    timeout=40
                )

                status = response.status_code

                if status == 200:
                    return response.json()

                print(
                    f"   ! HTTP {status}"
                )

        except Exception as e:

            print(
                f"   ! erreur réseau : {e}"
            )

        if attempt < 4:

            wait = 4 * (attempt + 1)

            print(
                f"   Attente {wait}s avant nouvelle tentative..."
            )

            time.sleep(wait)

    raise ApiUnavailable(
        "API inaccessible après plusieurs tentatives."
    )


def get_browser_page():

    init_browser()

    return _browser["page"]


def visible_cards_from_page(page):

    return page.evaluate(
        """
        () => Array.from(
            document.querySelectorAll('[data-slot="card"]')
        ).map((card, index) => {
            const lines = (card.innerText || '')
                .split('\\n')
                .map((line) => line.trim())
                .filter(Boolean);

            if (
                lines.length < 6
                ||
                !lines.includes('Voir')
            ) {
                return null;
            }

            return {
                index,
                titre: lines[0] || '',
                entreprise: {nom: lines[1] || ''},
                ville: lines[2] || '',
                type_stage: lines[3] || '',
                type_de_lieu_de_travail: lines[4] || '',
                description: lines.join(' '),
                lien_publique: '',
                lien_annonce: '',
            };
        }).filter(Boolean)
        """
    )


def has_next_dom_page(page):

    return page.evaluate(
        """
        () => {
            const next = Array.from(
                document.querySelectorAll('a, button')
            ).find((el) => (el.innerText || '').trim() === 'Suivant');

            if (!next) {
                return false;
            }

            const classes = String(
                next.getAttribute('class') || ''
            ).split(/\\s+/);

            return (
                !next.disabled
                &&
                !classes.includes('pointer-events-none')
                &&
                !classes.includes('opacity-50')
            );
        }
        """
    )


def click_next_dom_page(page):

    first_title = ""

    cards = visible_cards_from_page(page)

    if cards:
        first_title = cards[0].get("titre", "")

    page.get_by_text("Suivant", exact=True).click()

    if first_title:
        page.wait_for_function(
            """
            (oldTitle) => {
                const card = document.querySelector('[data-slot="card"]');
                return card && !card.innerText.includes(oldTitle);
            }
            """,
            arg=first_title,
            timeout=30000,
        )
    else:
        page.wait_for_timeout(1500)


def enrich_offer_url(page, card_index):

    cards = page.locator('[data-slot="card"]')
    card = cards.nth(card_index)
    current_url = page.url

    try:
        card.click(timeout=10000)
        page.wait_for_url(
            lambda url: url != current_url,
            timeout=15000,
        )

        url = page.url
        detail_text = extract_detail_description(page)

        page.go_back(
            wait_until="domcontentloaded",
            timeout=30000,
        )
        page.wait_for_timeout(1000)

        return url, detail_text

    except Exception as e:

        print(
            f"   ! URL détail indisponible : {e}"
        )

        try:
            if page.url != current_url:
                page.goto(
                    current_url,
                    wait_until="domcontentloaded",
                    timeout=30000,
                )
                page.wait_for_timeout(1000)
        except Exception:
            pass

    return "", ""


def extract_detail_description(page):

    text = page.locator("body").inner_text(timeout=10000)

    if "Description du poste" in text:
        text = text.split(
            "Description du poste",
            1
        )[1]

    for marker in [
        "Profil recherché",
        "Postuler maintenant",
        "Plateforme de stages",
        "Nous contacter",
        "RECHERCHE AVANCÉE",
    ]:
        if marker in text:
            text = text.split(
                marker,
                1
            )[0]

    return text[:2500]


def fetch_city_from_site(city_id):

    slug = CITY_SLUGS.get(city_id)

    if not slug:
        raise ApiUnavailable(
            f"Aucun slug web configuré pour city={city_id}."
        )

    page = get_browser_page()
    url = f"https://www.stagiaires.ma/stage-emploi-ville/{slug}"

    print(
        "   🌐 Fallback page web : "
        f"{url}"
    )

    page.goto(
        url,
        wait_until="domcontentloaded",
        timeout=60000,
    )
    page.wait_for_timeout(2500)

    items = []
    seen_keys = set()
    page_number = 1

    while True:

        cards = visible_cards_from_page(page)

        print(
            f"   page web {page_number}: "
            f"{len(cards)} cartes"
        )

        for card in cards:

            key = (
                norm(card.get("titre", "")),
                norm(
                    (
                        card.get("entreprise")
                        or
                        {}
                    ).get("nom", "")
                ),
                norm(card.get("ville", "")),
            )

            if key in seen_keys:
                continue

            seen_keys.add(key)

            if is_it_offer(card):

                detail_url, detail_text = enrich_offer_url(
                    page,
                    card["index"],
                )

                if detail_url:
                    card["lien_publique"] = detail_url

                if detail_text:
                    card["description"] = detail_text

            items.append(card)

        if not has_next_dom_page(page):
            break

        click_next_dom_page(page)
        page_number += 1
        time.sleep(
            random.uniform(*DELAY)
        )

    return items




# ============================================================
# RÉCUPÉRATION DES OFFRES D'UNE VILLE
# ============================================================

def fetch_city(city_id):

    items = []
    offset = 0
    used_fallback = False

    while True:

        try:

            data = api_get({

                "limit": LIMIT,

                "offset": offset,

                "statut": "Validée",

                "entreprise_valid": "true",

                "city": city_id,

                "sortBy": "date_publication",

                "order": "DESC",
            })

        except ApiUnavailable:

            if offset == 0 and USE_BROWSER:

                print(
                    "   API bloquée, passage au scraping page web..."
                )

                items = fetch_city_from_site(city_id)
                used_fallback = True
                break

            raise

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

    if used_fallback:
        return items

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

        try:

            items = fetch_city(
                city_id
            )

        except ApiUnavailable as e:

            print(
                f"   ! {e}"
            )

            print(
                "   -> Ville ignorée pour cette exécution."
            )

            print()

            continue

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

    if total_scraped == 0:

        print(
            "\nAucune offre récupérée. "
            "La Sheet reste inchangée."
        )

        raise SystemExit(
            "Aucune offre récupérée : API et fallback page web indisponibles."
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
