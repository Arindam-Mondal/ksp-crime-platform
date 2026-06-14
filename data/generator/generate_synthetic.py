"""
Synthetic Karnataka crime dataset generator (standard library only).

Produces CSVs matching the Data Store model in project_tech_stack.md, enriched so the
analytics surface is wide and *insightful* rather than flat:

    locations.csv         district, station, lat, lon, population, socio_economic_index,
                          archetype, urban_rural
    persons.csv           id, role, name, age, age_group, gender, address_district
    incidents.csv         id, crime_type, crime_head, ipc_section, severity, district,
                          urban_rural, station, lat, lon, datetime, weapon,
                          victim_age, victim_gender, victim_age_group, fir_delay_days,
                          mo_tags, narrative, status
    incident_persons.csv  incident_id, person_id, role

What makes the data non-flat (so downstream features have real structure to find):
  * Population-weighted geography  -> Bengaluru Urban dominates; rural districts are sparse.
  * District archetypes            -> metro skews cyber/fraud; border skews drugs/extortion;
                                      rural skews assault/murder. Crime MIX varies by place.
  * Crime-specific demographics    -> each crime has its own offender & victim age profile and
                                      gender skew (chain-snatching victims older & female,
                                      cybercrime offenders young, murder offenders older...).
  * Temporal structure             -> long-term growth + seasonality + weekend uplift, a
                                      rising-cybercrime trend, and one emerging 30-day spike.
  * Clearance by severity          -> severe crimes clear less often (insightful KPI).
  * Network structure              -> repeat offenders + co-offenders create graph edges.

Usage:
    python data/generator/generate_synthetic.py --incidents 20000 --seed 42
    python data/generator/generate_synthetic.py --out data/output --persons 6000
"""
from __future__ import annotations

import argparse
import bisect
import csv
import os
import random
from datetime import datetime, timedelta

# --- Karnataka's 31 districts: approx centroid (lat, lon), population, socio-economic
#     index (0-1), and an archetype that shapes crime mix. Demo values only. ---
# archetype ∈ {metro, urban, semiurban, rural, border}
DISTRICTS = [
    ("Bengaluru Urban",   12.9716, 77.5946, 9621551, 0.82, "metro"),
    ("Bengaluru Rural",   13.2846, 77.6101,  990923, 0.61, "rural"),
    ("Mysuru",            12.2958, 76.6394, 3001127, 0.66, "urban"),
    ("Mandya",            12.5223, 76.8954, 1805769, 0.55, "rural"),
    ("Hassan",            13.0033, 76.1004, 1776421, 0.57, "rural"),
    ("Tumakuru",          13.3409, 77.1010, 2678980, 0.56, "semiurban"),
    ("Kolar",             13.1357, 78.1326, 1536401, 0.54, "rural"),
    ("Chikkaballapur",    13.4355, 77.7315, 1255104, 0.52, "rural"),
    ("Ramanagara",        12.7110, 77.2810, 1082739, 0.55, "rural"),
    ("Chamarajanagar",    11.9261, 76.9438, 1020791, 0.49, "rural"),
    ("Chitradurga",       14.2251, 76.3980, 1659456, 0.51, "rural"),
    ("Davanagere",        14.4644, 75.9218, 1945497, 0.58, "semiurban"),
    ("Shivamogga",        13.9299, 75.5681, 1752753, 0.60, "semiurban"),
    ("Chikkamagaluru",    13.3161, 75.7720, 1137961, 0.56, "rural"),
    ("Udupi",             13.3409, 74.7421, 1177361, 0.71, "urban"),
    ("Dakshina Kannada",  12.8703, 74.8806, 2089649, 0.74, "urban"),
    ("Uttara Kannada",    14.7937, 74.6869, 1437169, 0.59, "rural"),
    ("Belagavi",          15.8497, 74.4977, 4779661, 0.57, "border"),
    ("Bagalkot",          16.1691, 75.6615, 1889752, 0.50, "semiurban"),
    ("Vijayapura",        16.8302, 75.7100, 2177331, 0.47, "border"),
    ("Kalaburagi",        17.3297, 76.8343, 2566326, 0.45, "border"),
    ("Bidar",             17.9133, 77.5301, 1703300, 0.46, "border"),
    ("Raichur",           16.2076, 77.3463, 1928812, 0.43, "border"),
    ("Koppal",            15.3547, 76.1545, 1391292, 0.44, "rural"),
    ("Ballari",           15.1394, 76.9214, 2452595, 0.49, "semiurban"),
    ("Vijayanagara",      15.2667, 76.3833, 1353628, 0.48, "rural"),
    ("Yadgir",            16.7700, 77.1376, 1174271, 0.41, "border"),
    ("Gadag",             15.4315, 75.6355, 1064570, 0.52, "rural"),
    ("Haveri",            14.7951, 75.4044, 1597668, 0.51, "rural"),
    ("Dharwad",           15.4589, 75.0078, 1847023, 0.63, "urban"),
    ("Kodagu",            12.4244, 75.7382,  554519, 0.62, "rural"),
]

# Per-capita crime propensity by archetype (more incidents per person in cities).
ARCHETYPE_PROPENSITY = {
    "metro": 1.9, "urban": 1.25, "semiurban": 1.0, "rural": 0.62, "border": 1.05,
}
URBAN_RURAL = {
    "metro": "Urban", "urban": "Urban", "semiurban": "Semi-urban",
    "rural": "Rural", "border": "Semi-urban",
}

# How each archetype tilts the crime mix (multiplier on the base weight; default 1.0).
ARCHETYPE_CRIME_MIX = {
    "metro": {"Cybercrime": 3.4, "Cheating/Fraud": 2.3, "Vehicle Theft": 1.7,
              "Chain Snatching": 1.6, "Theft": 1.3, "Robbery": 1.2, "Murder": 0.6,
              "Rioting": 0.6, "Drug Offence": 1.2},
    "urban": {"Cybercrime": 1.9, "Cheating/Fraud": 1.5, "Vehicle Theft": 1.3,
              "Theft": 1.15, "Chain Snatching": 1.2},
    "semiurban": {"Assault": 1.15, "Vehicle Theft": 1.05},
    "rural": {"Assault": 1.5, "Murder": 1.35, "House Burglary": 1.25, "Kidnapping": 1.2,
              "Cybercrime": 0.3, "Cheating/Fraud": 0.6, "Chain Snatching": 0.45,
              "Vehicle Theft": 0.7, "Robbery": 0.8},
    "border": {"Drug Offence": 2.7, "Extortion": 1.9, "Rioting": 1.7, "Murder": 1.25,
               "Assault": 1.2, "Cybercrime": 0.5, "Cheating/Fraud": 0.7},
}

# crime_type -> rich profile.
#   section, mo_tags, crime_head, severity, peak_hour, hour_spread, base_weight,
#   weapon_prob, (off_age_mean, off_age_sd), (vic_age_mean, vic_age_sd),
#   vic_female_share, off_female_share, rising (long-term upward trend?)
CRIME_TYPES = {
    "Theft":           dict(section="IPC 379",     mo=["pickpocket", "shoplifting", "opportunistic"],
                            head="Property Crime",  sev="Low",    peak=14, spread=6, w=1.0,
                            weapon=0.05, off=(27, 8),  vic=(35, 14), vfem=0.45, offem=0.12, rising=False),
    "House Burglary":  dict(section="IPC 457/380",  mo=["night-entry", "lock-break", "rear-window"],
                            head="Property Crime",  sev="Medium", peak=2,  spread=3, w=0.6,
                            weapon=0.08, off=(28, 8),  vic=(45, 14), vfem=0.40, offem=0.08, rising=False),
    "Robbery":         dict(section="IPC 392",      mo=["weapon", "two-wheeler-getaway", "ambush"],
                            head="Property Crime",  sev="High",   peak=21, spread=3, w=0.4,
                            weapon=0.80, off=(26, 7),  vic=(38, 14), vfem=0.35, offem=0.06, rising=False),
    "Chain Snatching": dict(section="IPC 379/356",  mo=["two-wheeler", "evening", "isolated-road"],
                            head="Property Crime",  sev="Medium", peak=19, spread=2, w=0.5,
                            weapon=0.20, off=(24, 5),  vic=(49, 14), vfem=0.68, offem=0.05, rising=False),
    "Vehicle Theft":   dict(section="IPC 379",      mo=["no-cctv", "parking-lot", "duplicate-key"],
                            head="Property Crime",  sev="Medium", peak=23, spread=4, w=0.7,
                            weapon=0.03, off=(25, 7),  vic=(37, 12), vfem=0.30, offem=0.07, rising=False),
    "Assault":         dict(section="IPC 323/324",  mo=["altercation", "alcohol", "group"],
                            head="Crime Against Person", sev="High", peak=22, spread=4, w=0.5,
                            weapon=0.50, off=(29, 9),  vic=(31, 11), vfem=0.30, offem=0.10, rising=False),
    "Murder":          dict(section="IPC 302",      mo=["personal-enmity", "premeditated", "weapon"],
                            head="Crime Against Person", sev="Severe", peak=1, spread=6, w=0.08,
                            weapon=0.95, off=(33, 10), vic=(35, 13), vfem=0.25, offem=0.09, rising=False),
    "Kidnapping":      dict(section="IPC 363",      mo=["minor", "ransom", "known-person"],
                            head="Crime Against Person", sev="Severe", peak=16, spread=5, w=0.07,
                            weapon=0.40, off=(31, 9),  vic=(16, 8),  vfem=0.55, offem=0.14, rising=False),
    "Cheating/Fraud":  dict(section="IPC 420",      mo=["fake-promise", "advance-fee", "impersonation"],
                            head="Economic Offence", sev="Medium", peak=12, spread=6, w=0.6,
                            weapon=0.01, off=(33, 9),  vic=(41, 13), vfem=0.40, offem=0.22, rising=True),
    "Cybercrime":      dict(section="IT Act 66",    mo=["otp-fraud", "phishing", "upi-scam"],
                            head="Economic Offence", sev="Medium", peak=15, spread=8, w=0.8,
                            weapon=0.0,  off=(26, 6),  vic=(43, 14), vfem=0.42, offem=0.18, rising=True),
    "Extortion":       dict(section="IPC 384",      mo=["threat-call", "gang", "protection-money"],
                            head="Economic Offence", sev="High",   peak=20, spread=5, w=0.15,
                            weapon=0.30, off=(32, 9),  vic=(40, 12), vfem=0.30, offem=0.10, rising=False),
    "Drug Offence":    dict(section="NDPS Act",     mo=["peddling", "possession", "transit"],
                            head="Special & Local Laws", sev="High", peak=23, spread=5, w=0.3,
                            weapon=0.10, off=(28, 7),  vic=(27, 8),  vfem=0.18, offem=0.12, rising=True),
    "Rioting":         dict(section="IPC 147",      mo=["mob", "communal", "property-damage"],
                            head="Special & Local Laws", sev="High", peak=18, spread=4, w=0.1,
                            weapon=0.60, off=(27, 8),  vic=(33, 12), vfem=0.20, offem=0.07, rising=False),
}

# Clearance probability by severity -> drives status + clearance-rate KPI.
CLEARANCE_BY_SEV = {"Low": 0.58, "Medium": 0.44, "High": 0.31, "Severe": 0.24}

FIRST_NAMES_M = ["Ravi", "Suresh", "Kiran", "Anil", "Naveen", "Prakash", "Mahesh", "Vijay",
                 "Ramesh", "Arun", "Sunil", "Pavan", "Harish", "Girish", "Santosh", "Madhu",
                 "Vasanth", "Yogesh", "Chetan", "Praveen", "Manju", "Nagaraj", "Basava", "Imran"]
FIRST_NAMES_F = ["Deepa", "Lakshmi", "Shilpa", "Geeta", "Roopa", "Nanda", "Bhavana", "Uma",
                 "Divya", "Anita", "Kavya", "Pooja", "Sushma", "Rekha", "Vidya", "Asha",
                 "Sneha", "Mamata", "Jyothi", "Sahana"]
LAST_NAMES = ["Gowda", "Shetty", "Rao", "Reddy", "Patil", "Kumar", "Hegde", "Naik",
              "Murthy", "Bhat", "Desai", "Iyer", "Swamy", "Achar", "Pujari", "Kamath",
              "Kulkarni", "Nayak", "Hiremath", "Joshi", "Angadi", "Banakar"]

AGE_BUCKETS = [(0, 17, "<18"), (18, 25, "18-25"), (26, 35, "26-35"),
               (36, 45, "36-45"), (46, 60, "46-60"), (61, 200, "60+")]


def age_group(age: int) -> str:
    for lo, hi, label in AGE_BUCKETS:
        if lo <= age <= hi:
            return label
    return "60+"


def sample_age(mean: float, sd: float, rng: random.Random, lo: int = 15, hi: int = 82) -> int:
    return max(lo, min(hi, int(round(rng.gauss(mean, sd)))))


def jitter(value: float, km: float, rng: random.Random) -> float:
    """Offset a coordinate by up to ~km kilometres (rough: 1 deg ~= 111 km)."""
    return value + rng.uniform(-km, km) / 111.0


def make_name(gender: str, rng: random.Random) -> str:
    pool = FIRST_NAMES_F if gender == "F" else FIRST_NAMES_M
    return f"{rng.choice(pool)} {rng.choice(LAST_NAMES)}"


def build_locations(rng: random.Random):
    """Return (locations_rows, district_meta, station_index, hotspot_index)."""
    locations = []
    district_meta = {}   # name -> dict(lat, lon, pop, sei, archetype, urban_rural, weight)
    station_index = {}   # district -> list of (station, lat, lon)
    hotspot_index = {}   # district -> list of (lat, lon) hot cell centres
    for name, lat, lon, pop, sei, arch in DISTRICTS:
        urban_rural = URBAN_RURAL[arch]
        # Incident weight ∝ population × per-capita propensity (this de-flattens geography).
        weight = (pop / 1_000_000.0) * ARCHETYPE_PROPENSITY[arch]
        district_meta[name] = dict(lat=lat, lon=lon, pop=pop, sei=sei, archetype=arch,
                                   urban_rural=urban_rural, weight=weight)
        # Bigger places get more stations.
        n_stations = {"metro": 12, "urban": 8, "semiurban": 6, "rural": 4, "border": 6}[arch]
        n_stations += rng.randint(-1, 1)
        stations = []
        for s in range(max(3, n_stations)):
            sname = f"{name} PS-{s + 1}"
            slat, slon = jitter(lat, 12, rng), jitter(lon, 12, rng)
            stations.append((sname, slat, slon))
            locations.append({
                "district": name, "station": sname,
                "lat": round(slat, 5), "lon": round(slon, 5),
                "population": pop, "socio_economic_index": sei,
                "archetype": arch, "urban_rural": urban_rural,
            })
        station_index[name] = stations
        # More hot cells in dense places.
        n_hot = {"metro": 5, "urban": 3, "semiurban": 3, "rural": 2, "border": 3}[arch]
        hotspot_index[name] = [
            (jitter(lat, 8, rng), jitter(lon, 8, rng)) for _ in range(n_hot)
        ]
    return locations, district_meta, station_index, hotspot_index


def build_persons(n: int, rng: random.Random):
    persons = []
    for i in range(1, n + 1):
        role = "offender" if rng.random() < 0.45 else "victim"
        if role == "offender":
            gender = rng.choices(["M", "F"], weights=[0.9, 0.1])[0]
            age = sample_age(28, 9, rng)          # offenders skew young-adult
        else:
            gender = rng.choices(["M", "F"], weights=[0.6, 0.4])[0]
            age = sample_age(38, 15, rng)         # victims span a wider range
        persons.append({
            "id": f"P{i:06d}",
            "role": role,
            "name": make_name(gender, rng),
            "age": age,
            "age_group": age_group(age),
            "gender": gender,
            "address_district": rng.choice(DISTRICTS)[0],
        })
    offenders = [p["id"] for p in persons if p["role"] == "offender"]
    victims = [p["id"] for p in persons if p["role"] == "victim"]
    # ~12% of offenders are "repeat" / habitual -> drives network density
    repeat_offenders = rng.sample(offenders, max(1, int(len(offenders) * 0.12)))
    return persons, offenders, victims, repeat_offenders


def build_day_curves(num_days: int, rng: random.Random):
    """Precompute cumulative day-weights so timestamps have growth + seasonality.

    Returns (days_list, cum_general, cum_rising) where cum_* are cumulative weight
    arrays usable with bisect for O(log n) weighted day sampling. 'rising' biases
    toward recent days (for cybercrime/fraud/drugs trending upward).
    """
    # Seasonal multiplier by calendar month (summer up, monsoon dip, festive Oct-Nov up).
    month_factor = {1: 0.95, 2: 0.98, 3: 1.08, 4: 1.14, 5: 1.16, 6: 1.02,
                    7: 0.9, 8: 0.92, 9: 1.0, 10: 1.12, 11: 1.1, 12: 1.05}
    start = datetime.now() - timedelta(days=num_days)
    gen_w, ris_w = [], []
    for d in range(num_days):
        day = start + timedelta(days=d)
        frac = d / max(1, num_days - 1)            # 0 (old) .. 1 (recent)
        growth = 0.8 + 0.5 * frac                  # gentle long-term rise
        season = month_factor[day.month]
        weekend = 1.12 if day.weekday() >= 5 else 1.0
        base = growth * season * weekend
        gen_w.append(base)
        # rising crimes grow ~2.6x across the window (steep recent uptick)
        ris_w.append(base * (0.45 + 2.2 * (frac ** 1.6)))
    days = [start + timedelta(days=d) for d in range(num_days)]

    def cumulate(weights):
        acc, out = 0.0, []
        for w in weights:
            acc += w
            out.append(acc)
        return out

    return days, cumulate(gen_w), cumulate(ris_w)


def pick_day(days, cum, rng: random.Random) -> datetime:
    target = rng.uniform(0, cum[-1])
    idx = bisect.bisect_left(cum, target)
    return days[min(idx, len(days) - 1)]


def status_for(severity: str, ts: datetime, now: datetime, rng: random.Random) -> str:
    """Recent cases skew open; clearance odds fall with severity."""
    cleared_p = CLEARANCE_BY_SEV[severity]
    age_days = (now - ts).days
    if age_days < 45:
        cleared_p *= 0.35          # fresh cases rarely resolved yet
    elif age_days < 120:
        cleared_p *= 0.7
    if rng.random() < cleared_p:
        return rng.choices(["Charge-sheeted", "Closed"], weights=[0.62, 0.38])[0]
    return rng.choices(["Under Investigation", "Pending Trial"], weights=[0.7, 0.3])[0]


def build_incidents(args, rng, district_meta, station_index, hotspot_index,
                    offenders, victims, repeat_offenders):
    incidents = []
    links = []
    now = datetime.now()
    crime_names = list(CRIME_TYPES.keys())

    districts = list(district_meta.keys())
    district_weights = [district_meta[d]["weight"] for d in districts]

    # Per-district crime weights (base × archetype tilt), precomputed once.
    district_crime_weights = {}
    for d in districts:
        arch = district_meta[d]["archetype"]
        mix = ARCHETYPE_CRIME_MIX.get(arch, {})
        district_crime_weights[d] = [CRIME_TYPES[c]["w"] * mix.get(c, 1.0) for c in crime_names]

    days, cum_gen, cum_ris = build_day_curves(args.days, rng)

    # Emerging spike: one district+category surges in the final 30 days.
    spike_district = rng.choices(districts, weights=district_weights)[0]
    spike_crime = "Chain Snatching"

    for i in range(1, args.incidents + 1):
        district = rng.choices(districts, weights=district_weights)[0]
        crime = rng.choices(crime_names, weights=district_crime_weights[district])[0]
        prof = CRIME_TYPES[crime]
        meta = district_meta[district]

        # ~65% of incidents fall inside a district hotspot cell, else spread across stations.
        if rng.random() < 0.65 and hotspot_index[district]:
            hlat, hlon = rng.choice(hotspot_index[district])
            lat, lon = jitter(hlat, 1.5, rng), jitter(hlon, 1.5, rng)
        else:
            _, slat, slon = rng.choice(station_index[district])
            lat, lon = jitter(slat, 4, rng), jitter(slon, 4, rng)
        station = min(station_index[district], key=lambda s: (s[1] - lat) ** 2 + (s[2] - lon) ** 2)[0]

        # Date: spike combo surges recently; rising crimes use the recency-biased curve.
        if district == spike_district and crime == spike_crime and rng.random() < 0.7:
            day = now - timedelta(days=rng.uniform(0, 30))
        else:
            day = pick_day(days, cum_ris if prof["rising"] else cum_gen, rng)
        hour = int(round(rng.gauss(prof["peak"], prof["spread"]))) % 24
        ts = day.replace(hour=hour, minute=rng.randint(0, 59), second=0, microsecond=0)

        # Victim demographics from the crime's profile.
        v_age = sample_age(prof["vic"][0], prof["vic"][1], rng, lo=3, hi=92)
        v_gender = "F" if rng.random() < prof["vfem"] else "M"
        weapon = "Yes" if rng.random() < prof["weapon"] else "No"
        fir_delay = max(0, int(round(rng.gauss(2.2, 3.5))))  # days between event and FIR

        mo_tags = "|".join(rng.sample(prof["mo"], k=min(2, len(prof["mo"]))))
        iid = f"FIR{i:07d}"
        status = status_for(prof["sev"], ts, now, rng)
        narrative = (
            f"On {ts.strftime('%d-%m-%Y')} around {ts.strftime('%H:%M')}, a {crime.lower()} "
            f"({prof['section']}) was reported near {station}, {district} "
            f"({meta['urban_rural']}). Victim: {v_gender}/{v_age}. "
            f"Modus operandi: {mo_tags.replace('|', ', ')}. Weapon involved: {weapon.lower()}."
        )
        incidents.append({
            "id": iid, "crime_type": crime, "crime_head": prof["head"],
            "ipc_section": prof["section"], "severity": prof["sev"],
            "district": district, "urban_rural": meta["urban_rural"],
            "station": station, "lat": round(lat, 5), "lon": round(lon, 5),
            "datetime": ts.strftime("%Y-%m-%d %H:%M:%S"), "weapon": weapon,
            "victim_age": v_age, "victim_gender": v_gender,
            "victim_age_group": age_group(v_age), "fir_delay_days": fir_delay,
            "mo_tags": mo_tags, "narrative": narrative, "status": status,
        })

        # --- offenders: repeat-offender bias + occasional co-offenders (graph edges) ---
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

    locations, district_meta, station_index, hotspot_index = build_locations(rng)
    persons, offenders, victims, repeat_offenders = build_persons(args.persons, rng)
    incidents, links, spike_d, spike_c = build_incidents(
        args, rng, district_meta, station_index, hotspot_index, offenders, victims, repeat_offenders
    )

    write_csv(os.path.join(args.out, "locations.csv"), locations,
              ["district", "station", "lat", "lon", "population", "socio_economic_index",
               "archetype", "urban_rural"])
    write_csv(os.path.join(args.out, "persons.csv"), persons,
              ["id", "role", "name", "age", "age_group", "gender", "address_district"])
    write_csv(os.path.join(args.out, "incidents.csv"), incidents,
              ["id", "crime_type", "crime_head", "ipc_section", "severity", "district",
               "urban_rural", "station", "lat", "lon", "datetime", "weapon",
               "victim_age", "victim_gender", "victim_age_group", "fir_delay_days",
               "mo_tags", "narrative", "status"])
    write_csv(os.path.join(args.out, "incident_persons.csv"), links,
              ["incident_id", "person_id", "role"])

    # --- console summary with a few distribution insights ---
    from collections import Counter
    by_district = Counter(r["district"] for r in incidents)
    by_head = Counter(r["crime_head"] for r in incidents)
    cleared = sum(1 for r in incidents if r["status"] in ("Charge-sheeted", "Closed"))
    out = os.path.abspath(args.out)
    print(f"Wrote synthetic dataset to {out}")
    print(f"  locations.csv        {len(locations):>7} rows ({len(DISTRICTS)} districts)")
    print(f"  persons.csv          {len(persons):>7} rows  ({len(repeat_offenders)} repeat offenders)")
    print(f"  incidents.csv        {len(incidents):>7} rows")
    print(f"  incident_persons.csv {len(links):>7} rows")
    print(f"  clearance rate:      {cleared / max(1, len(incidents)) * 100:5.1f}%")
    print(f"  top 3 districts:     {', '.join(f'{d} ({n})' for d, n in by_district.most_common(3))}")
    print(f"  crime heads:         {', '.join(f'{h} ({n})' for h, n in by_head.most_common())}")
    print(f"  emerging spike:      '{spike_c}' in {spike_d} (last 30 days)")


if __name__ == "__main__":
    main()
