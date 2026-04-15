import sqlite3
import os
import json

DB_PATH=  os.path.join(os.path.dirname(__file__), 'travel.db')

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def create_tables(conn):
    cursor = conn.cursor()
    cursor.executescript("""
        drop table if exists travel_history;
        drop table if exists members;
        drop table if exists recommendations;
        drop table if exists partners;
        
        CREATE TABLE partners (
            partner_id      TEXT PRIMARY KEY,
            name            TEXT NOT NULL,
            rec_cap         INTEGER,           -- NULL means unlimited
            excluded_cats   TEXT NOT NULL      -- JSON array e.g. ["cruise"]
        );
        
        CREATE TABLE members (
            member_id       TEXT PRIMARY KEY,
            name            TEXT NOT NULL,
            loyalty_tier    TEXT NOT NULL,     -- Silver / Gold / Platinum
            partner_id      TEXT NOT NULL,
            FOREIGN KEY (partner_id) REFERENCES partners(partner_id)
        );        
        
        CREATE TABLE travel_history (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id       TEXT NOT NULL,
            destination     TEXT NOT NULL,
            booking_type    TEXT NOT NULL,     -- flight / hotel / cruise / car
            travel_date     TEXT NOT NULL,
            FOREIGN KEY (member_id) REFERENCES members(member_id)
        );
        
        CREATE TABLE recommendations (
            rec_id          INTEGER PRIMARY KEY AUTOINCREMENT,
            destination     TEXT NOT NULL,
            category        TEXT NOT NULL,     -- flight / hotel / cruise / car
            description     TEXT NOT NULL,
            base_price      INTEGER NOT NULL   -- USD
        );
        """)
    conn.commit()
    print("Tables created successfully.")

def seed_partners(conn):
    partners = [
        # partner_id, name, rec_cap, excluded_cats
        ("PARTNER_A", "GlobalBank Rewards",  None,  json.dumps([])),
        ("PARTNER_B", "PremiumCard Travel",  3,     json.dumps([])),
        ("PARTNER_C", "FamilyFirst Points",  5,     json.dumps(["cruise"])),
    ]
    conn.executemany(
        "INSERT INTO partners VALUES (?, ?, ?, ?)", partners
    )
    conn.commit()
    print("  Partners seeded: GlobalBank (unlimited), PremiumCard (cap 3), FamilyFirst (no cruises).")

def seed_members(conn):
    members = [
        # member_id, name, loyalty_tier, partner_id
        ("MBR001", "Alice Johnson",   "Platinum", "PARTNER_A"),
        ("MBR002", "Bob Martinez",    "Gold",     "PARTNER_A"),
        ("MBR003", "Carol Williams",  "Silver",   "PARTNER_B"),
        ("MBR004", "David Chen",      "Platinum", "PARTNER_B"),
        ("MBR005", "Eva Rosario",     "Gold",     "PARTNER_C"),
        ("MBR006", "Frank Okafor",    "Silver",   "PARTNER_C"),
    ]
    conn.executemany(
        "INSERT INTO members VALUES (?, ?, ?, ?)", members
    )
    # conn.commit()
    print("  Members seeded: 6 members across 3 partners.")

def seed_travel_history(conn):
    history = [
        # MBR001 — Alice, Platinum, PARTNER_A
        ("MBR001", "Paris",        "flight",  "2024-11-10"),
        ("MBR001", "Paris",        "hotel",   "2024-11-10"),
        ("MBR001", "Tokyo",        "flight",  "2024-08-22"),
        ("MBR001", "Tokyo",        "hotel",   "2024-08-22"),
        ("MBR001", "Maldives",     "cruise",  "2024-05-14"),

        # MBR002 — Bob, Gold, PARTNER_A
        ("MBR002", "New York",     "hotel",   "2024-12-01"),
        ("MBR002", "Miami",        "cruise",  "2024-09-18"),
        ("MBR002", "Chicago",      "flight",  "2024-07-04"),
        ("MBR002", "Las Vegas",    "hotel",   "2024-03-21"),
        ("MBR002", "Orlando",      "car",     "2024-01-15"),

        # MBR003 — Carol, Silver, PARTNER_B
        ("MBR003", "Cancun",       "flight",  "2024-10-05"),
        ("MBR003", "Cancun",       "hotel",   "2024-10-05"),
        ("MBR003", "Barcelona",    "flight",  "2024-06-30"),
        ("MBR003", "Lisbon",       "hotel",   "2024-04-12"),
        ("MBR003", "Rome",         "flight",  "2024-02-28"),

        # MBR004 — David, Platinum, PARTNER_B
        ("MBR004", "Singapore",    "flight",  "2024-11-25"),
        ("MBR004", "Singapore",    "hotel",   "2024-11-25"),
        ("MBR004", "Bali",         "cruise",  "2024-08-10"),
        ("MBR004", "Sydney",       "flight",  "2024-05-01"),
        ("MBR004", "Sydney",       "hotel",   "2024-05-01"),

        # MBR005 — Eva, Gold, PARTNER_C
        ("MBR005", "Costa Rica",   "flight",  "2024-12-10"),
        ("MBR005", "Costa Rica",   "hotel",   "2024-12-10"),
        ("MBR005", "Hawaii",       "flight",  "2024-09-03"),
        ("MBR005", "Hawaii",       "hotel",   "2024-09-03"),
        ("MBR005", "Mexico City",  "car",     "2024-06-18"),

        # MBR006 — Frank, Silver, PARTNER_C
        ("MBR006", "London",       "flight",  "2024-10-20"),
        ("MBR006", "London",       "hotel",   "2024-10-20"),
        ("MBR006", "Amsterdam",    "flight",  "2024-07-14"),
        ("MBR006", "Dublin",       "hotel",   "2024-04-08"),
        ("MBR006", "Edinburgh",    "car",     "2024-02-01"),
    ]
    conn.executemany(
        "INSERT INTO travel_history (member_id, destination, booking_type, travel_date) VALUES (?, ?, ?, ?)",
        history
    )
    conn.commit()
    print("  Travel history seeded: 5 bookings per member.")
    
def seed_recommendations(conn):
    recs = [
        # destination, category, description, base_price
        ("Bali",           "flight",  "Direct flights to Bali from major US hubs",        850),
        ("Bali",           "hotel",   "Luxury beachfront resorts in Seminyak",             220),
        ("Tokyo",          "flight",  "Premium economy flights to Tokyo Narita",           1200),
        ("Tokyo",          "hotel",   "Boutique hotels in Shinjuku",                       180),
        ("Paris",          "flight",  "Business class deals to Paris CDG",                 1800),
        ("Paris",          "hotel",   "Charming hotels near the Eiffel Tower",             300),
        ("Cancun",         "flight",  "Budget flights to Cancun International",            420),
        ("Cancun",         "hotel",   "All-inclusive resorts on Hotel Zone",               150),
        ("Maldives",       "cruise",  "7-night Maldives island-hopping cruise",            3200),
        ("Caribbean",      "cruise",  "14-night Caribbean luxury cruise",                  4500),
        ("Mediterranean",  "cruise",  "10-night Mediterranean ports cruise",               2800),
        ("Alaska",         "cruise",  "7-night Alaska glacier cruise",                     2200),
        ("Amalfi Coast",   "car",     "Self-drive Amalfi Coast road trip package",         180),
        ("New Zealand",    "car",     "Campervan road trip across South Island",            220),
        ("Scotland",       "car",     "Classic Highland driving tour",                     160),
        ("Singapore",      "flight",  "Stopover deals to Singapore Changi",                950),
        ("Singapore",      "hotel",   "Marina Bay Sands and city-centre hotels",           380),
        ("Sydney",         "flight",  "Seasonal deals to Sydney Kingsford Smith",          1100),
        ("Sydney",         "hotel",   "Harbour-view hotels in the CBD",                    260),
        ("Costa Rica",     "flight",  "Eco-adventure flights to San Jose",                 510),
        ("Costa Rica",     "hotel",   "Rainforest lodges and beach resorts",               140),
        ("Hawaii",         "flight",  "Inter-island hopper packages from LAX",             380),
        ("Hawaii",         "hotel",   "Beachfront resorts on Maui and Oahu",               290),
        ("London",         "flight",  "Transatlantic deals to London Heathrow",            740),
        ("London",         "hotel",   "Central London boutique hotels",                    240),
        ("Barcelona",      "flight",  "Direct flights to Barcelona El Prat",               680),
        ("Barcelona",      "hotel",   "Gothic Quarter hotels and beach apartments",        170),
    ]
    conn.executemany(
        "INSERT INTO recommendations (destination, category, description, base_price) VALUES (?, ?, ?, ?)",
        recs
    )
    conn.commit()
    print("  Recommendations seeded: 27 catalog items across flights, hotels, cruises, cars.")
    
def verify(conn):
    cursor = conn.cursor()
    print("\n  Verification:")
    for table in ["partners", "members", "travel_history", "recommendations"]:
        count = cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"    {table}: {count} rows")

    print("\n  Partner rules check:")
    for row in cursor.execute("SELECT partner_id, name, rec_cap, excluded_cats FROM partners"):
        cap = row["rec_cap"] if row["rec_cap"] else "unlimited"
        print(f"    {row['partner_id']} ({row['name']}): cap={cap}, excluded={row['excluded_cats']}")

if __name__ == "__main__":
    print("\nSeeding travel.db...\n")
    conn = get_connection()
    create_tables(conn)
    seed_partners(conn)
    seed_members(conn)
    seed_travel_history(conn)
    seed_recommendations(conn)
    verify(conn)
    conn.close()
    print("\nDone. travel.db is ready.\n")