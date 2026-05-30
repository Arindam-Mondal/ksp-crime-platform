"""
Synthetic Karnataka crime dataset generator (standard library only).

Produces CSVs matching the Data Store model in project_tech_stack.md:
    locations.csv         (district, station, lat, lon, population, socio_economic_index)
    persons.csv           (id, role, name, age, gender, address_district)
    incidents.csv         (id, crime_type, ipc_section, district, station, lat, lon,
                           datetime, mo_tags, narrative, status)
    incident_persons.csv  (incident_id, person_id, role)

Design goals (so downstream features have something real to find):
  * Spatiotemporal HOTSPOTS  -> each district has a few hot cells; incidents cluster there.
  * Time-of-day patterns     -> burglary at night, chain-snatching in the evening, etc.
  * An emerging SPIKE        -> one district+category surges in the last ~30 days (trend alerts).
  * Network structure        -> repeat offenders and co-offenders create graph edges.

Usage:
    python data/generator/generate_synthetic.py --incidents 20000 --seed 42
    python data/generator/generate_synthetic.py --out data/output --persons 6000
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import random
from datetime import datetime, timedelta

# --- Karnataka districts: approx centroid (lat, lon), population, socio-economic index (0-1) ---
# Coordinates/populations are approximate, for demo visualization only.
DISTRICTS = [
    ("Bengaluru Urban", 12.9716, 77.5946, 9621551, 0.82),
    ("Bengaluru Rural", 13.2846, 77.6101, 990923, 0.61),
    ("Mysuru", 12.2958, 76.6394, 3001127, 0.66),
    ("Mandya", 12.5223, 76.8954, 1805769, 0.55),
    ("Hassan", 13.0033, 76.1004, 1776421, 0.57),
    ("Tumakuru", 13.3409, 77.1010, 2678980, 0.56),
    ("Kolar", 13.1357, 78.1326, 1536401, 0.54),
    ("Chikkaballapura", 13.4355, 77.7315, 1255104, 0.52),
    ("Ramanagara", 12.7110, 77.2810, 1082739, 0.55),
    ("Chamarajanagar", 11.9261, 76.9438, 1020791, 0.49),
    ("Chitradurga", 14.2251, 76.3980, 1659456, 0.51),
    ("Davanagere", 14.4644, 75.9218, 1945497, 0.58),
    ("Shivamogga", 13.9299, 75.5681, 1752753, 0.60),
    ("Chikkamagaluru", 13.3161, 75.7720, 1137961, 0.56),
    ("Udupi", 13.3409, 74.7421, 1177361, 0.71),
    ("Dakshina Kannada", 12.8703, 74.8806, 2089649, 0.74),
    ("Uttara Kannada", 14.7937, 74.6869, 1437169, 0.59),
    ("Belagavi", 15.8497, 74.4977, 4779661, 0.57),
    ("Bagalkot", 16.1691, 75.6615, 1889752, 0.50),
    ("Vijayapura", 16.8302, 75.7100, 2177331, 0.47),
    ("Kalaburagi", 17.3297, 76.8343, 2566326, 0.45),
    ("Bidar", 17.9133, 77.5301, 1703300, 0.46),
    ("Raichur", 16.2076, 77.3463, 1928812, 0.43),
    ("Koppal", 15.3547, 76.1545, 1391292, 0.44),
    ("Ballari", 15.1394, 76.9214, 2452595, 0.49),
    ("Vijayanagara", 15.2667, 76.3833, 1353628, 0.48),
    ("Davangere Rural", 14.5000, 75.9000, 600000, 0.50),
    ("Yadgir", 16.7700, 77.1376, 1174271, 0.41),
    ("Gadag", 15.4315, 75.6355, 1064570, 0.52),
    ("Haveri", 14.7951, 75.4044, 1597668, 0.51),
    ("Dharwad", 15.4589, 75.0078, 1847023, 0.63),
    ("Kodagu", 12.4244, 75.7382, 554519, 0.62),
]

# crime_type -> (ipc/act section, [mo tags], peak_hour, hour_spread, base_weight)
CRIME_TYPES = {
    "Theft":            ("IPC 379",      ["pickpocket", "shoplifting", "opportunistic"], 14, 6, 1.0),
    "House Burglary":   ("IPC 457/380",  ["night-entry", "lock-break", "rear-window"],   2,  3, 0.6),
    "Robbery":          ("IPC 392",      ["weapon", "two-wheeler-getaway", "ambush"],    21, 3, 0.4),
    "Chain Snatching":  ("IPC 379/356",  ["two-wheeler", "evening", "isolated-road"],    19, 2, 0.5),
    "Vehicle Theft":    ("IPC 379",      ["no-cctv", "parking-lot", "duplicate-key"],    23, 4, 0.7),
    "Assault":          ("IPC 323/324",  ["altercation", "alcohol", "group"],            22, 4, 0.5),
    "Murder":           ("IPC 302",      ["personal-enmity", "premeditated", "weapon"],  1,  6, 0.08),
    "Kidnapping":       ("IPC 363",      ["minor", "ransom", "known-person"],            16, 5, 0.07),
    "Cheating/Fraud":   ("IPC 420",      ["fake-promise", "advance-fee", "impersonation"],12, 6, 0.6),
    "Cybercrime":       ("IT Act 66",    ["otp-fraud", "phishing", "upi-scam"],          15, 8, 0.8),
    "Extortion":        ("IPC 384",      ["threat-call", "gang", "protection-money"],    20, 5, 0.15),
    "Drug Offence":     ("NDPS Act",     ["peddling", "possession", "transit"],          23, 5, 0.3),
    "Rioting":          ("IPC 147",      ["mob", "communal", "property-damage"],         18, 4, 0.1),
}

STATUSES = ["Under Investigation", "Charge-sheeted", "Closed", "Pending Trial"]
FIRST_NAMES = ["Ravi", "Suresh", "Manju", "Kiran", "Anil", "Deepa", "Lakshmi", "Naveen",
               "Prakash", "Shilpa", "Mahesh", "Vijay", "Ramesh", "Geeta", "Arun", "Sunil",
               "Pavan", "Roopa", "Harish", "Nanda", "Girish", "Bhavana", "Santosh", "Uma",
               "Madhu", "Vasanth", "Yogesh", "Chetan", "Divya", "Praveen"]
LAST_NAMES = ["Gowda", "Shetty", "Rao", "Reddy", "Patil", "Kumar", "Hegde", "Naik",
              "Murthy", "Bhat", "Desai", "Iyer", "Swamy", "Achar", "Pujari", "Kamath",
              "Kulkarni", "Nayak", "Hiremath", "Joshi"]


def jitter(value: float, km: float, rng: random.Random) -> float:
    """Offset a coordinate by up to ~km kilometres (rough: 1 deg ~= 111 km)."""
    return value + rng.uniform(-km, km) / 111.0


def make_name(rng: random.Random) -> str:
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"


def build_locations(rng: random.Random):
    """Return (locations_rows, station_index, hotspot_index)."""
    locations = []
    station_index = {}   # district -> list of (station, lat, lon)
    hotspot_index = {}   # district -> list of (lat, lon) hot cell centres
    for district, lat, lon, pop, sei in DISTRICTS:
        n_stations = rng.randint(3, 8)
        stations = []
        for s in range(n_stations):
            sname = f"{district} PS-{s + 1}"
            slat, slon = jitter(lat, 12, rng), jitter(lon, 12, rng)
            stations.append((sname, slat, slon))
            locations.append({
                "district": district, "station": sname,
                "lat": round(slat, 5), "lon": round(slon, 5),
                "population": pop, "socio_economic_index": sei,
            })
        station_index[district] = stations
        # 2-3 hotspot cells per district
        hotspot_index[district] = [
            (jitter(lat, 8, rng), jitter(lon, 8, rng)) for _ in range(rng.randint(2, 3))
        ]
    return locations, station_index, hotspot_index


def build_persons(n: int, rng: random.Random):
    persons = []
    for i in range(1, n + 1):
        role = "offender" if rng.random() < 0.45 else "victim"
        persons.append({
            "id": f"P{i:06d}",
            "role": role,
            "name": make_name(rng),
            "age": rng.randint(16, 70),
            "gender": rng.choices(["M", "F"], weights=[0.78, 0.22])[0],
            "address_district": rng.choice(DISTRICTS)[0],
        })
    offenders = [p["id"] for p in persons if p["role"] == "offender"]
    victims = [p["id"] for p in persons if p["role"] == "victim"]
    # ~12% of offenders are "repeat" / habitual -> drives network density
    repeat_offenders = rng.sample(offenders, max(1, int(len(offenders) * 0.12)))
    return persons, offenders, victims, repeat_offenders


def pick_hour(peak: int, spread: int, rng: random.Random) -> int:
    return int(round(random.gauss(peak, spread))) % 24 if False else int(round(rng.gauss(peak, spread))) % 24


def build_incidents(args, rng, station_index, hotspot_index, offenders, victims, repeat_offenders):
    incidents = []
    links = []
    now = datetime.now()
    start = now - timedelta(days=args.days)
    crime_names = list(CRIME_TYPES.keys())
    crime_weights = [CRIME_TYPES[c][4] for c in crime_names]

    # Choose a district+category to spike in the final 30 days (emerging-trend demo).
    spike_district = rng.choice([d[0] for d in DISTRICTS])
    spike_crime = "Chain Snatching"

    for i in range(1, args.incidents + 1):
        district = rng.choice(DISTRICTS)[0]
        crime = rng.choices(crime_names, weights=crime_weights)[0]
        section, mo_pool, peak, spread, _ = CRIME_TYPES[crime]

        # 65% of incidents fall inside a district hotspot cell, else spread across stations.
        if rng.random() < 0.65 and hotspot_index[district]:
            hlat, hlon = rng.choice(hotspot_index[district])
            lat, lon = jitter(hlat, 1.5, rng), jitter(hlon, 1.5, rng)
        else:
            _, lat, lon = rng.choice(station_index[district])
            lat, lon = jitter(lat, 4, rng), jitter(lon, 4, rng)
        station = min(station_index[district], key=lambda s: (s[1] - lat) ** 2 + (s[2] - lon) ** 2)[0]

        # Timestamp: uniform over window, with a recent surge for the spike combo.
        if district == spike_district and crime == spike_crime and rng.random() < 0.7:
            ts = now - timedelta(days=rng.uniform(0, 30),
                                 hours=rng.uniform(0, 24))
        else:
            ts = start + timedelta(seconds=rng.uniform(0, (now - start).total_seconds()))
        ts = ts.replace(hour=pick_hour(peak, spread, rng),
                        minute=rng.randint(0, 59), second=0, microsecond=0)

        mo_tags = "|".join(rng.sample(mo_pool, k=min(2, len(mo_pool))))
        iid = f"FIR{i:07d}"
        narrative = (
            f"On {ts.strftime('%d-%m-%Y')} around {ts.strftime('%H:%M')}, a {crime.lower()} "
            f"({section}) was reported near {station}, {district}. "
            f"Modus operandi: {mo_tags.replace('|', ', ')}."
        )
        incidents.append({
            "id": iid, "crime_type": crime, "ipc_section": section,
            "district": district, "station": station,
            "lat": round(lat, 5), "lon": round(lon, 5),
            "datetime": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "mo_tags": mo_tags, "narrative": narrative,
            "status": rng.choices(STATUSES, weights=[0.45, 0.2, 0.2, 0.15])[0],
        })

        # --- offenders: repeat offenders bias + occasional co-offenders (graph edges) ---
        if rng.random() < 0.85:
            n_off = rng.choices([1, 2, 3], weights=[0.7, 0.22, 0.08])[0]
            chosen = set()
            for _ in range(n_off):
                if rng.random() < 0.35 and repeat_offenders:
                    off = rng.choice(repeat_offenders)
                else:
                    off = rng.choice(offenders)
                if off not in chosen:
                    chosen.add(off)
                    links.append({"incident_id": iid, "person_id": off, "role": "offender"})
        # --- victims ---
        for _ in range(rng.choices([1, 2], weights=[0.85, 0.15])[0]):
            links.append({"incident_id": iid, "person_id": rng.choice(victims), "role": "victim"})

    return incidents, links, spike_district, spike_crime


def write_csv(path: str, rows: list, fieldnames: list):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description="Generate synthetic Karnataka crime data.")
    ap.add_argument("--incidents", type=int, default=20000)
    ap.add_argument("--persons", type=int, default=6000)
    ap.add_argument("--days", type=int, default=730, help="history window in days")
    ap.add_argument("--seed", type=int, default=42)
    default_out = os.path.join(os.path.dirname(__file__), "..", "output")
    ap.add_argument("--out", default=default_out)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    os.makedirs(args.out, exist_ok=True)

    locations, station_index, hotspot_index = build_locations(rng)
    persons, offenders, victims, repeat_offenders = build_persons(args.persons, rng)
    incidents, links, spike_d, spike_c = build_incidents(
        args, rng, station_index, hotspot_index, offenders, victims, repeat_offenders
    )

    write_csv(os.path.join(args.out, "locations.csv"), locations,
              ["district", "station", "lat", "lon", "population", "socio_economic_index"])
    write_csv(os.path.join(args.out, "persons.csv"), persons,
              ["id", "role", "name", "age", "gender", "address_district"])
    write_csv(os.path.join(args.out, "incidents.csv"), incidents,
              ["id", "crime_type", "ipc_section", "district", "station", "lat", "lon",
               "datetime", "mo_tags", "narrative", "status"])
    write_csv(os.path.join(args.out, "incident_persons.csv"), links,
              ["incident_id", "person_id", "role"])

    out = os.path.abspath(args.out)
    print(f"Wrote synthetic dataset to {out}")
    print(f"  locations.csv        {len(locations):>7} rows")
    print(f"  persons.csv          {len(persons):>7} rows  ({len(repeat_offenders)} repeat offenders)")
    print(f"  incidents.csv        {len(incidents):>7} rows")
    print(f"  incident_persons.csv {len(links):>7} rows")
    print(f"  emerging-trend spike seeded: '{spike_c}' in {spike_d} (last 30 days)")


if __name__ == "__main__":
    main()
