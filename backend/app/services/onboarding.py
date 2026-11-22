import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, Profile, TransactionType
from app.repositories import categories as categories_repo
from app.repositories import profiles as profiles_repo

Sub = tuple[str, str | None]


@dataclass(frozen=True, slots=True)
class DefaultCategory:
    name: str
    kind: TransactionType
    icon: str
    color: str
    description: str | None = None
    children: tuple[Sub, ...] = ()


EXPENSE = TransactionType.EXPENSE
INCOME = TransactionType.INCOME

DEFAULT_CATEGORIES: list[DefaultCategory] = [
    DefaultCategory(
        "Jedzenie",
        EXPENSE,
        "restaurant",
        "#EB6834",
        None,
        (
            ("Spożywcze", "sklepy spożywcze, także zakupy spożywcze online"),
            ("Restauracje", "restauracje, obiady na mieście, bary"),
            ("Kawiarnie", "kawa i ciastko na mieście"),
            ("Zamówienia online", "dostawy jedzenia: Pyszne, Glovo, Uber Eats, Wolt"),
        ),
    ),
    DefaultCategory(
        "Transport",
        EXPENSE,
        "bus",
        "#2A78D6",
        "codzienne przemieszczanie się: dojazdy, komunikacja miejska, paliwo, taksówki",
        (
            ("Komunikacja miejska", "bilety i karty miejskie, regularne dojazdy pociągiem"),
            ("Paliwo", "paliwo, ładowanie auta"),
            ("Taksówki", "taksówki, Bolt, Uber"),
        ),
    ),
    DefaultCategory(
        "Podróże",
        EXPENSE,
        "airplane",
        "#1BAF7A",
        "wyjazdy poza miasto: przejazdy, noclegi, atrakcje",
        (
            ("Przejazdy", "pociąg, autobus lub samolot na wyjazd do innego miasta"),
            ("Noclegi", "hotele, apartamenty, Airbnb"),
            ("Atrakcje", "bilety wstępu i wycieczki na wyjeździe"),
        ),
    ),
    DefaultCategory(
        "Mieszkanie",
        EXPENSE,
        "home",
        "#6250D6",
        None,
        (
            ("Czynsz", "czynsz, najem"),
            ("Wyposażenie", "meble, sprzęt i dodatki do domu"),
            ("Remonty", "remonty, naprawy, materiały budowlane"),
        ),
    ),
    DefaultCategory(
        "Rachunki",
        EXPENSE,
        "receipt",
        "#EDA100",
        None,
        (
            ("Prąd i gaz", None),
            ("Woda i ogrzewanie", None),
            ("Internet i telefon", None),
            ("Ubezpieczenia", "OC, ubezpieczenie mieszkania, na życie"),
            ("Subskrypcje", "iCloud, aplikacje, oprogramowanie; rozrywkowe to Streaming"),
        ),
    ),
    DefaultCategory(
        "Zdrowie",
        EXPENSE,
        "medkit",
        "#E34948",
        None,
        (
            ("Apteka", "leki, suplementy"),
            ("Lekarz", "wizyty, dentysta, badania"),
            ("Sport", "siłownia, zajęcia, sprzęt sportowy"),
        ),
    ),
    DefaultCategory(
        "Rozrywka",
        EXPENSE,
        "game-controller",
        "#E87BA4",
        None,
        (
            ("Kino", None),
            ("Koncerty", None),
            ("Kultura", "teatr, muzea, wystawy, opera"),
            ("Książki", "książki, e-booki, audiobooki"),
            ("Gry", "gry, planszówki"),
            ("Streaming", "Spotify, Netflix i inne serwisy rozrywkowe"),
        ),
    ),
    DefaultCategory(
        "Zakupy",
        EXPENSE,
        "bag-handle",
        "#008300",
        None,
        (
            ("Ubrania", "ubrania, obuwie, dodatki"),
            ("Elektronika", "telefony, komputery, słuchawki, akcesoria"),
            ("Drogeria", "kosmetyki i chemia domowa: Rossmann, Hebe"),
            ("Inne zakupy", "zakupy, które nie pasują do innych podkategorii"),
        ),
    ),
    DefaultCategory("Inne", EXPENSE, "ellipsis-horizontal", "#94A3B8"),
    DefaultCategory("Wynagrodzenie", INCOME, "cash", "#22C55E"),
    DefaultCategory("Inne przychody", INCOME, "add-circle", "#84CC16"),
]


def build_defaults(user_id: uuid.UUID) -> list[Category]:
    rows: list[Category] = []
    for d in DEFAULT_CATEGORIES:
        parent = Category(
            id=uuid.uuid4(),
            user_id=user_id,
            name=d.name,
            kind=d.kind,
            icon=d.icon,
            color=d.color,
            description=d.description,
            is_default=True,
        )
        rows.append(parent)
        rows += [
            Category(
                user_id=user_id,
                name=name,
                kind=d.kind,
                color=d.color,
                description=description,
                is_default=True,
                parent_id=parent.id,
            )
            for name, description in d.children
        ]
    return rows


async def accept_consent(session: AsyncSession, profile: Profile, currency: str) -> Profile:
    profile = await profiles_repo.set_consent(session, profile, currency)
    if not await categories_repo.user_has_any(session, profile.id):
        await categories_repo.add_many(session, build_defaults(profile.id))
    return profile
