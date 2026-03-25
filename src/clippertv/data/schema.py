"""Database schema creation and seeding for ClipperTV v2."""


def create_tables(conn) -> None:
    """Create the v2 schema tables."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trips (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            account_number  TEXT NOT NULL,
            trip_id         TEXT,
            start_datetime  TEXT NOT NULL,
            end_datetime    TEXT,
            start_location  TEXT,
            end_location    TEXT,
            fare            REAL,
            operator        TEXT NOT NULL,
            pass_type       TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_trip_id ON trips(trip_id) WHERE trip_id IS NOT NULL")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_account_number ON trips(account_number)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_start_datetime ON trips(start_datetime)")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS manual_trips (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            account_number  TEXT NOT NULL,
            trip_id         TEXT,
            start_datetime  TEXT NOT NULL,
            end_datetime    TEXT,
            start_location  TEXT,
            end_location    TEXT,
            fare            REAL,
            operator        TEXT NOT NULL,
            pass_type       TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS category_rules (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            operator  TEXT NOT NULL,
            location  TEXT NOT NULL DEFAULT '',
            category  TEXT NOT NULL
        )
    """)
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_category_rule ON category_rules(operator, location)")
    conn.commit()


# --- Seed data from current categories.py frozensets ---

_MUNI_METRO_STATIONS = [
    "Embarcadero", "Montgomery", "Powell", "Civic Center",
    "Van Ness", "Church", "Castro", "Forest Hill",
    "West Portal", "Balboa Park",
    "Sunset Tunnel East", "Sunset Tunnel West",
    "Duboce/Church", "Duboce/Noe",
    "Carl/Cole", "Carl/Hillway",
    "Judah/9th Ave", "Judah/19th Ave",
    "Taraval/19th Ave", "Taraval/32nd Ave",
    "SF State", "Stonestown", "Parkmerced",
    "Ocean/San Jose", "Ocean/Geneva",
    "4th/King", "4th/Brannan",
    "Sunnydale", "Bayshore/Arleta",
    "3rd/20th", "3rd/Carroll",
]

_CABLE_CAR_STOPS = [
    "Hyde/Beach", "Hyde/Lombard", "Hyde/Greenwich",
    "Hyde/Union", "Hyde/Jackson", "Hyde/California",
    "Powell/Market", "Powell/Mason", "Powell/Hyde",
    "Mason/Washington", "Mason/Jackson",
    "California/Van Ness", "California/Powell",
    "California/Drumm",
]

_OPERATOR_RULES = [
    ("BART", "", "BART"),
    ("Caltrain", "", "Caltrain"),
    ("AC Transit", "", "AC Transit"),
    ("SamTrans", "", "SamTrans"),
    ("VTA", "", "VTA"),
    ("Golden Gate Transit", "", "Golden Gate Transit"),
    ("WETA", "", "Ferry"),
    ("Golden Gate Ferry", "", "Ferry"),
    ("Muni", "", "Muni Bus"),  # fallback for unrecognized locations
]


def seed_category_rules(conn) -> None:
    """Populate category_rules with station/operator data. Idempotent."""
    existing = conn.execute("SELECT COUNT(*) FROM category_rules").fetchone()[0]
    if existing > 0:
        return

    rules = list(_OPERATOR_RULES)
    for station in _MUNI_METRO_STATIONS:
        rules.append(("Muni", station, "Muni Metro"))
    for stop in _CABLE_CAR_STOPS:
        rules.append(("Muni", stop, "Cable Car"))

    conn.executemany(
        "INSERT INTO category_rules (operator, location, category) VALUES (?, ?, ?)",
        rules,
    )
    conn.commit()
