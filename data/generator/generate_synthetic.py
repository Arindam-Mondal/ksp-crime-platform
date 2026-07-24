"""
Synthetic Karnataka Police FIR dataset generator (standard library only).

Emits one CSV per table of the official Police FIR ER Diagram (see ERD_SCHEMA.md —
table and column names match the PDF exactly):

    Masters:      State, District, UnitType, Unit, Rank, Designation, Employee, Court,
                  CaseCategory, GravityOffence, CaseStatusMaster, CasteMaster,
                  ReligionMaster, OccupationMaster, CrimeHead, CrimeSubHead,
                  Act, Section, CrimeHeadActSection
    Case data:    CaseMaster, ComplainantDetails, Victim, Accused,
                  ActSectionAssociation, ArrestSurrender, ChargesheetDetails

What makes the data non-flat (so the analytics have real structure to find):
  * Population-weighted geography  -> Bengaluru dominates; rural districts are sparse.
  * District archetypes            -> metro skews cyber/fraud; border skews NDPS/rioting;
                                      rural skews murder/assault. Crime MIX varies by place.
  * Crime-specific case lifecycle  -> reporting delay, arrest probability & lag,
                                      chargesheet rate & lag, and final-report type (A/B/C)
                                      all depend on the crime sub-head and gravity.
  * Crime-specific demographics    -> each sub-head has its own victim/accused age & gender
                                      profile; complainants carry occupation/religion/caste.
  * Temporal structure             -> growth + seasonality + weekend uplift, a rising
                                      cyber-crime trend, and one emerging 30-day spike.
  * Network structure              -> a repeat-offender identity pool recurs across cases and
                                      co-offends, so name-based entity resolution yields a
                                      real co-accused graph.

Usage:
    python data/generator/generate_synthetic.py --cases 20000 --seed 42
"""
from __future__ import annotations

import argparse
import bisect
import csv
import os
import random
from datetime import datetime, timedelta

# ============================================================== geography ====
# Karnataka's 31 districts: centroid (lat, lon), population, archetype.
# archetype ∈ {metro, urban, semiurban, rural, border} — shapes volume + crime mix.
KA_DISTRICTS = [
    ("Bengaluru City",    12.9716, 77.5946, 9621551, "metro"),
    ("Bengaluru Rural",   13.2846, 77.6101,  990923, "rural"),
    ("Mysuru",            12.2958, 76.6394, 3001127, "urban"),
    ("Mandya",            12.5223, 76.8954, 1805769, "rural"),
    ("Hassan",            13.0033, 76.1004, 1776421, "rural"),
    ("Tumakuru",          13.3409, 77.1010, 2678980, "semiurban"),
    ("Kolar",             13.1357, 78.1326, 1536401, "rural"),
    ("Chikkaballapur",    13.4355, 77.7315, 1255104, "rural"),
    ("Ramanagara",        12.7110, 77.2810, 1082739, "rural"),
    ("Chamarajanagar",    11.9261, 76.9438, 1020791, "rural"),
    ("Chitradurga",       14.2251, 76.3980, 1659456, "rural"),
    ("Davanagere",        14.4644, 75.9218, 1945497, "semiurban"),
    ("Shivamogga",        13.9299, 75.5681, 1752753, "semiurban"),
    ("Chikkamagaluru",    13.3161, 75.7720, 1137961, "rural"),
    ("Udupi",             13.3409, 74.7421, 1177361, "urban"),
    ("Dakshina Kannada",  12.8703, 74.8806, 2089649, "urban"),
    ("Uttara Kannada",    14.7937, 74.6869, 1437169, "rural"),
    ("Belagavi",          15.8497, 74.4977, 4779661, "border"),
    ("Bagalkot",          16.1691, 75.6615, 1889752, "semiurban"),
    ("Vijayapura",        16.8302, 75.7100, 2177331, "border"),
    ("Kalaburagi",        17.3297, 76.8343, 2566326, "border"),
    ("Bidar",             17.9133, 77.5301, 1703300, "border"),
    ("Raichur",           16.2076, 77.3463, 1928812, "border"),
    ("Koppal",            15.3547, 76.1545, 1391292, "rural"),
    ("Ballari",           15.1394, 76.9214, 2452595, "semiurban"),
    ("Vijayanagara",      15.2667, 76.3833, 1353628, "rural"),
    ("Yadgir",            16.7700, 77.1376, 1174271, "border"),
    ("Gadag",             15.4315, 75.6355, 1064570, "rural"),
    ("Haveri",            14.7951, 75.4044, 1597668, "rural"),
    ("Dharwad",           15.4589, 75.0078, 1847023, "urban"),
    ("Kodagu",            12.4244, 75.7382,  554519, "rural"),
]

# Neighbouring states (for out-of-state arrests). state -> representative districts.
NEIGHBOUR_STATES = [
    ("Maharashtra",    ["Pune", "Kolhapur", "Solapur"]),
    ("Tamil Nadu",     ["Chennai", "Coimbatore", "Krishnagiri"]),
    ("Andhra Pradesh", ["Anantapur", "Kurnool"]),
    ("Telangana",      ["Hyderabad", "Mahbubnagar"]),
    ("Kerala",         ["Kasaragod", "Kannur"]),
    ("Goa",            ["North Goa"]),
]

ARCHETYPE_PROPENSITY = {"metro": 1.9, "urban": 1.25, "semiurban": 1.0, "rural": 0.62, "border": 1.05}
N_STATIONS = {"metro": 14, "urban": 8, "semiurban": 6, "rural": 4, "border": 6}
N_HOTCELLS = {"metro": 5, "urban": 3, "semiurban": 3, "rural": 2, "border": 3}

# ============================================================ legal layer ====
# Act master: ActCode (PK, VARCHAR), description, short name.
ACTS = [
    ("IPC",   "Indian Penal Code, 1860",                        "IPC"),
    ("ITACT", "Information Technology Act, 2000",               "IT Act"),
    ("NDPS",  "Narcotic Drugs and Psychotropic Substances Act, 1985", "NDPS Act"),
    ("ARMS",  "Arms Act, 1959",                                 "Arms Act"),
    ("KPACT", "Karnataka Police Act, 1963",                     "KP Act"),
    ("DPACT", "Dowry Prohibition Act, 1961",                    "DP Act"),
    ("CRPC",  "Code of Criminal Procedure, 1973",               "CrPC"),
    ("MVACT", "Motor Vehicles Act, 1988",                       "MV Act"),
]

# Section master: (ActCode, SectionCode, SectionDescription)
SECTIONS = [
    ("IPC", "143",  "Unlawful assembly"),
    ("IPC", "147",  "Rioting"),
    ("IPC", "148",  "Rioting, armed with deadly weapon"),
    ("IPC", "279",  "Rash driving on a public way"),
    ("IPC", "302",  "Murder"),
    ("IPC", "307",  "Attempt to murder"),
    ("IPC", "323",  "Voluntarily causing hurt"),
    ("IPC", "324",  "Voluntarily causing hurt by dangerous weapons"),
    ("IPC", "326",  "Voluntarily causing grievous hurt by dangerous weapons"),
    ("IPC", "337",  "Causing hurt by act endangering life"),
    ("IPC", "34",   "Acts done by several persons in furtherance of common intention"),
    ("IPC", "149",  "Unlawful assembly - common object"),
    ("IPC", "354",  "Assault or criminal force to woman with intent to outrage modesty"),
    ("IPC", "356",  "Assault or criminal force in attempt to commit theft"),
    ("IPC", "363",  "Kidnapping"),
    ("IPC", "379",  "Theft"),
    ("IPC", "380",  "Theft in dwelling house"),
    ("IPC", "384",  "Extortion"),
    ("IPC", "392",  "Robbery"),
    ("IPC", "395",  "Dacoity"),
    ("IPC", "406",  "Criminal breach of trust"),
    ("IPC", "420",  "Cheating and dishonestly inducing delivery of property"),
    ("IPC", "457",  "Lurking house-trespass by night"),
    ("IPC", "498A", "Cruelty by husband or relatives of husband"),
    ("IPC", "506",  "Criminal intimidation"),
    ("ITACT", "66",  "Computer related offences"),
    ("ITACT", "66C", "Identity theft"),
    ("ITACT", "66D", "Cheating by personation using computer resource"),
    ("ITACT", "67",  "Publishing obscene material in electronic form"),
    ("NDPS", "20",  "Contravention in relation to cannabis"),
    ("NDPS", "21",  "Contravention in relation to manufactured drugs"),
    ("NDPS", "22",  "Contravention in relation to psychotropic substances"),
    ("ARMS", "25",  "Punishment for possession of illegal arms"),
    ("ARMS", "27",  "Punishment for using arms"),
    ("KPACT", "78", "Opening of gaming house"),
    ("KPACT", "79", "Being found in gaming house"),
    ("KPACT", "87", "Drunken and riotous behaviour in public"),
    ("KPACT", "92", "Petty cases - causing nuisance in public"),
    ("DPACT", "3",  "Penalty for giving or taking dowry"),
    ("DPACT", "4",  "Penalty for demanding dowry"),
    ("CRPC", "174", "Police to enquire and report on unnatural death"),
    ("MVACT", "184", "Driving dangerously"),
]

# Crime heads (CrimeHeadID, CrimeGroupName)
CRIME_HEADS = [
    (1, "Crimes Against Body"),
    (2, "Crimes Against Property"),
    (3, "Crimes Against Women"),
    (4, "Economic Offences"),
    (5, "Cyber Crime"),
    (6, "Crimes Against Public Order"),
    (7, "Special & Local Laws"),
    (8, "Others"),
]

# Crime sub-heads with full behavioural profile.
#   id, name, head, w        : identity, parent head, base sampling weight
#   secs                     : primary (act, section) list -> ActSectionAssociation
#   extra                    : optional [(prob, (act, section))] secondary sections
#   heinous                  : probability the case is classed Heinous
#   peak, spread             : hour-of-day profile
#   delay                    : (mean, sd) days between incident and informing the PS
#   vic_n                    : weights for 0/1/2 victims
#   acc_n                    : weights for 0/1/2/3 accused (0 = unknown offender)
#   vic, acc                 : (age_mean, age_sd) victim / accused
#   vfem, afem               : female share of victims / accused
#   arrest                   : probability an accused gets arrested
#   arrest_lag               : (mean, sd) days from registration to arrest
#   cs                       : probability of an A-type final report (chargesheet) once mature
#   undet                    : probability of C-type (undetected) once mature
#   cs_lag                   : (mean, sd) days from registration to final report
#   rising                   : long-term upward trend (cyber/fraud pattern)
#   mix                      : archetype -> weight multiplier
SUB_HEADS = [
    dict(id=1,  name="Murder", head=1, w=0.08, secs=[("IPC", "302")],
         extra=[(0.5, ("IPC", "34")), (0.25, ("ARMS", "27"))],
         heinous=1.0, peak=1, spread=6, delay=(0.3, 0.5), vic_n=[0, 88, 12], acc_n=[6, 50, 28, 16],
         vic=(35, 13), acc=(33, 10), vfem=0.25, afem=0.08, arrest=0.85, arrest_lag=(9, 8),
         cs=0.80, undet=0.08, cs_lag=(95, 30), rising=False,
         mix={"rural": 1.35, "border": 1.25, "metro": 0.6}),
    dict(id=2,  name="Attempt to Murder", head=1, w=0.09, secs=[("IPC", "307")],
         extra=[(0.4, ("IPC", "34")), (0.3, ("ARMS", "27"))],
         heinous=0.9, peak=22, spread=4, delay=(0.5, 0.8), vic_n=[0, 90, 10], acc_n=[4, 48, 30, 18],
         vic=(32, 11), acc=(30, 9), vfem=0.22, afem=0.06, arrest=0.78, arrest_lag=(12, 10),
         cs=0.72, undet=0.10, cs_lag=(100, 35), rising=False,
         mix={"rural": 1.2, "border": 1.2, "metro": 0.75}),
    dict(id=3,  name="Assault / Grievous Hurt", head=1, w=0.50, secs=[("IPC", "323"), ("IPC", "324")],
         extra=[(0.25, ("IPC", "326")), (0.3, ("IPC", "506")), (0.2, ("IPC", "34"))],
         heinous=0.12, peak=21, spread=4, delay=(1.2, 1.5), vic_n=[0, 82, 18], acc_n=[3, 52, 30, 15],
         vic=(31, 11), acc=(29, 9), vfem=0.28, afem=0.10, arrest=0.62, arrest_lag=(15, 12),
         cs=0.60, undet=0.14, cs_lag=(110, 40), rising=False,
         mix={"rural": 1.5, "semiurban": 1.15, "metro": 0.8}),
    dict(id=4,  name="Kidnapping / Abduction", head=1, w=0.07, secs=[("IPC", "363")],
         extra=[(0.25, ("IPC", "506"))],
         heinous=0.75, peak=16, spread=5, delay=(1.0, 1.2), vic_n=[0, 96, 4], acc_n=[8, 58, 24, 10],
         vic=(17, 8), acc=(30, 9), vfem=0.55, afem=0.14, arrest=0.68, arrest_lag=(14, 12),
         cs=0.62, undet=0.16, cs_lag=(120, 40), rising=False,
         mix={"rural": 1.2}),
    dict(id=5,  name="Rash & Negligent Driving", head=8, w=0.42, secs=[("IPC", "279"), ("MVACT", "184")],
         extra=[(0.35, ("IPC", "337"))],
         heinous=0.02, peak=19, spread=5, delay=(0.2, 0.3), vic_n=[8, 74, 18], acc_n=[2, 92, 5, 1],
         vic=(36, 15), acc=(31, 10), vfem=0.32, afem=0.04, arrest=0.80, arrest_lag=(3, 3),
         cs=0.82, undet=0.06, cs_lag=(60, 25), rising=False,
         mix={"metro": 1.3, "urban": 1.2}),

    dict(id=6,  name="Theft", head=2, w=1.00, secs=[("IPC", "379")],
         heinous=0.01, peak=14, spread=6, delay=(1.8, 2.5), vic_n=[0, 92, 8], acc_n=[38, 46, 12, 4],
         vic=(35, 14), acc=(27, 8), vfem=0.45, afem=0.12, arrest=0.48, arrest_lag=(22, 18),
         cs=0.38, undet=0.42, cs_lag=(120, 45), rising=False,
         mix={"metro": 1.3, "urban": 1.15, "rural": 0.75}),
    dict(id=7,  name="House Burglary", head=2, w=0.55, secs=[("IPC", "457"), ("IPC", "380")],
         heinous=0.05, peak=2, spread=3, delay=(0.8, 1.0), vic_n=[0, 94, 6], acc_n=[42, 40, 13, 5],
         vic=(45, 14), acc=(28, 8), vfem=0.40, afem=0.08, arrest=0.42, arrest_lag=(28, 20),
         cs=0.34, undet=0.48, cs_lag=(130, 45), rising=False,
         mix={"rural": 1.25, "semiurban": 1.1}),
    dict(id=8,  name="Robbery", head=2, w=0.35, secs=[("IPC", "392")],
         extra=[(0.35, ("ARMS", "25")), (0.2, ("IPC", "34"))],
         heinous=0.55, peak=21, spread=3, delay=(0.4, 0.6), vic_n=[0, 90, 10], acc_n=[12, 40, 32, 16],
         vic=(38, 14), acc=(26, 7), vfem=0.35, afem=0.06, arrest=0.60, arrest_lag=(16, 14),
         cs=0.55, undet=0.24, cs_lag=(110, 40), rising=False,
         mix={"metro": 1.2, "border": 1.1, "rural": 0.8}),
    dict(id=9,  name="Dacoity", head=2, w=0.05, secs=[("IPC", "395")],
         extra=[(0.5, ("ARMS", "25"))],
         heinous=1.0, peak=1, spread=3, delay=(0.3, 0.4), vic_n=[0, 80, 20], acc_n=[10, 8, 30, 52],
         vic=(42, 13), acc=(29, 8), vfem=0.30, afem=0.04, arrest=0.66, arrest_lag=(20, 15),
         cs=0.58, undet=0.20, cs_lag=(130, 45), rising=False,
         mix={"border": 1.5, "rural": 1.2, "metro": 0.5}),
    dict(id=10, name="Chain Snatching", head=2, w=0.45, secs=[("IPC", "379"), ("IPC", "356")],
         heinous=0.04, peak=19, spread=2, delay=(0.3, 0.4), vic_n=[0, 97, 3], acc_n=[30, 42, 24, 4],
         vic=(49, 13), acc=(24, 5), vfem=0.70, afem=0.04, arrest=0.50, arrest_lag=(18, 15),
         cs=0.42, undet=0.38, cs_lag=(110, 40), rising=False,
         mix={"metro": 1.6, "urban": 1.25, "rural": 0.45}),
    dict(id=11, name="Vehicle Theft", head=2, w=0.65, secs=[("IPC", "379")],
         heinous=0.01, peak=23, spread=4, delay=(0.6, 0.8), vic_n=[0, 97, 3], acc_n=[45, 40, 12, 3],
         vic=(37, 12), acc=(25, 7), vfem=0.30, afem=0.05, arrest=0.40, arrest_lag=(30, 22),
         cs=0.32, undet=0.52, cs_lag=(140, 50), rising=False,
         mix={"metro": 1.7, "urban": 1.3, "rural": 0.7}),

    dict(id=12, name="Outraging Modesty of Women", head=3, w=0.28, secs=[("IPC", "354")],
         extra=[(0.3, ("IPC", "506"))],
         heinous=0.30, peak=20, spread=4, delay=(2.5, 3.0), vic_n=[0, 98, 2], acc_n=[6, 78, 12, 4],
         vic=(27, 9), acc=(31, 10), vfem=1.0, afem=0.01, arrest=0.66, arrest_lag=(10, 9),
         cs=0.62, undet=0.12, cs_lag=(100, 35), rising=False, mix={}),
    dict(id=13, name="Cruelty / Dowry Harassment", head=3, w=0.30,
         secs=[("IPC", "498A"), ("DPACT", "3"), ("DPACT", "4")],
         heinous=0.18, peak=12, spread=7, delay=(20, 18), vic_n=[0, 98, 2], acc_n=[0, 30, 38, 32],
         vic=(28, 6), acc=(38, 12), vfem=1.0, afem=0.42, arrest=0.55, arrest_lag=(25, 20),
         cs=0.58, undet=0.06, cs_lag=(130, 45), rising=False, mix={"rural": 1.15}),

    dict(id=14, name="Cheating / Fraud", head=4, w=0.55, secs=[("IPC", "420")],
         extra=[(0.3, ("IPC", "406"))],
         heinous=0.06, peak=12, spread=6, delay=(12, 14), vic_n=[0, 88, 12], acc_n=[14, 56, 20, 10],
         vic=(41, 13), acc=(34, 9), vfem=0.40, afem=0.22, arrest=0.45, arrest_lag=(35, 25),
         cs=0.46, undet=0.28, cs_lag=(150, 50), rising=True,
         mix={"metro": 2.0, "urban": 1.4, "rural": 0.6}),
    dict(id=15, name="Criminal Breach of Trust", head=4, w=0.15, secs=[("IPC", "406")],
         heinous=0.05, peak=13, spread=5, delay=(18, 16), vic_n=[0, 94, 6], acc_n=[6, 76, 14, 4],
         vic=(44, 12), acc=(37, 9), vfem=0.35, afem=0.20, arrest=0.42, arrest_lag=(40, 28),
         cs=0.44, undet=0.22, cs_lag=(150, 50), rising=False, mix={"metro": 1.4, "urban": 1.2}),
    dict(id=16, name="Extortion", head=4, w=0.12, secs=[("IPC", "384")],
         extra=[(0.4, ("IPC", "506"))],
         heinous=0.35, peak=20, spread=5, delay=(4, 5), vic_n=[0, 95, 5], acc_n=[8, 44, 30, 18],
         vic=(40, 12), acc=(32, 9), vfem=0.30, afem=0.10, arrest=0.58, arrest_lag=(18, 14),
         cs=0.52, undet=0.18, cs_lag=(120, 40), rising=False, mix={"border": 1.9, "metro": 1.1}),

    dict(id=17, name="Online Financial Fraud", head=5, w=0.70,
         secs=[("ITACT", "66C"), ("ITACT", "66D"), ("IPC", "420")],
         heinous=0.03, peak=15, spread=8, delay=(3.5, 4.0), vic_n=[0, 96, 4], acc_n=[62, 28, 8, 2],
         vic=(43, 14), acc=(26, 6), vfem=0.42, afem=0.16, arrest=0.22, arrest_lag=(55, 35),
         cs=0.18, undet=0.68, cs_lag=(170, 55), rising=True,
         mix={"metro": 3.2, "urban": 1.9, "rural": 0.3, "border": 0.5}),
    dict(id=18, name="Identity Theft / Impersonation", head=5, w=0.20,
         secs=[("ITACT", "66C"), ("ITACT", "66")],
         heinous=0.02, peak=16, spread=7, delay=(5, 6), vic_n=[0, 97, 3], acc_n=[58, 32, 8, 2],
         vic=(38, 13), acc=(27, 6), vfem=0.45, afem=0.18, arrest=0.24, arrest_lag=(50, 32),
         cs=0.20, undet=0.62, cs_lag=(160, 55), rising=True,
         mix={"metro": 2.6, "urban": 1.6, "rural": 0.35}),
    dict(id=19, name="Obscene Electronic Content", head=5, w=0.10,
         secs=[("ITACT", "67"), ("ITACT", "66")],
         heinous=0.05, peak=22, spread=6, delay=(6, 7), vic_n=[0, 92, 8], acc_n=[30, 60, 8, 2],
         vic=(26, 8), acc=(28, 8), vfem=0.75, afem=0.06, arrest=0.40, arrest_lag=(30, 22),
         cs=0.36, undet=0.40, cs_lag=(140, 50), rising=True,
         mix={"metro": 2.0, "urban": 1.4, "rural": 0.5}),

    dict(id=20, name="Rioting / Unlawful Assembly", head=6, w=0.12,
         secs=[("IPC", "147"), ("IPC", "143")],
         extra=[(0.4, ("IPC", "148")), (0.5, ("IPC", "149"))],
         heinous=0.30, peak=18, spread=4, delay=(0.4, 0.5), vic_n=[35, 45, 20], acc_n=[2, 4, 24, 70],
         vic=(33, 12), acc=(27, 8), vfem=0.20, afem=0.06, arrest=0.70, arrest_lag=(8, 7),
         cs=0.64, undet=0.10, cs_lag=(100, 35), rising=False,
         mix={"border": 1.8, "rural": 1.1, "metro": 0.6}),
    dict(id=21, name="Drunken / Riotous Behaviour", head=6, w=0.20, secs=[("KPACT", "87")],
         heinous=0.0, peak=22, spread=3, delay=(0.1, 0.1), vic_n=[55, 40, 5], acc_n=[0, 78, 18, 4],
         vic=(35, 12), acc=(31, 10), vfem=0.15, afem=0.03, arrest=0.90, arrest_lag=(1, 1),
         cs=0.85, undet=0.03, cs_lag=(35, 15), rising=False, mix={"metro": 1.2}),

    dict(id=22, name="NDPS - Drug Offence", head=7, w=0.25,
         secs=[("NDPS", "20"), ("NDPS", "21")],
         extra=[(0.25, ("NDPS", "22"))],
         heinous=0.40, peak=23, spread=5, delay=(0.1, 0.1), vic_n=[100, 0, 0], acc_n=[0, 55, 30, 15],
         vic=(0, 0), acc=(27, 7), vfem=0.0, afem=0.10, arrest=0.96, arrest_lag=(1, 1),
         cs=0.78, undet=0.05, cs_lag=(90, 30), rising=True,
         mix={"border": 2.6, "metro": 1.3, "rural": 0.5}),
    dict(id=23, name="Arms Act Violation", head=7, w=0.06, secs=[("ARMS", "25")],
         heinous=0.35, peak=22, spread=5, delay=(0.1, 0.2), vic_n=[100, 0, 0], acc_n=[0, 80, 15, 5],
         vic=(0, 0), acc=(30, 8), vfem=0.0, afem=0.03, arrest=0.95, arrest_lag=(1, 1),
         cs=0.75, undet=0.06, cs_lag=(85, 30), rising=False, mix={"border": 1.9}),
    dict(id=24, name="Gambling (KP Act)", head=7, w=0.18,
         secs=[("KPACT", "78"), ("KPACT", "79")],
         heinous=0.0, peak=21, spread=4, delay=(0.1, 0.1), vic_n=[100, 0, 0], acc_n=[0, 20, 30, 50],
         vic=(0, 0), acc=(36, 11), vfem=0.0, afem=0.05, arrest=0.92, arrest_lag=(1, 1),
         cs=0.86, undet=0.02, cs_lag=(30, 12), rising=False, mix={"semiurban": 1.3, "urban": 1.1}),

    dict(id=25, name="Unnatural Death (UDR)", head=8, w=0.28, secs=[("CRPC", "174")],
         heinous=0.0, peak=8, spread=8, delay=(0.3, 0.4), vic_n=[0, 100, 0], acc_n=[100, 0, 0, 0],
         vic=(41, 16), acc=(0, 0), vfem=0.35, afem=0.0, arrest=0.0, arrest_lag=(0, 0),
         cs=0.0, undet=0.0, cs_lag=(0, 0), rising=False, mix={}),
    dict(id=26, name="Public Nuisance (Petty Case)", head=8, w=0.22, secs=[("KPACT", "92")],
         heinous=0.0, peak=20, spread=5, delay=(0.1, 0.1), vic_n=[85, 15, 0], acc_n=[0, 88, 10, 2],
         vic=(37, 13), acc=(33, 11), vfem=0.20, afem=0.05, arrest=0.85, arrest_lag=(1, 1),
         cs=0.90, undet=0.02, cs_lag=(20, 10), rising=False, mix={"metro": 1.2}),
]

# CrimeHeadActSection: head -> primary sections of its sub-heads (built at runtime).

# =============================================================== lookups =====
CASE_CATEGORIES = [(1, "FIR"), (2, "Zero FIR"), (3, "UDR"), (4, "PAR")]
# CrimeNo first digit per PDF examples: FIR=1, UDR=3, Zero FIR=8, PAR=4.
CATEGORY_CODE = {"FIR": "1", "UDR": "3", "Zero FIR": "8", "PAR": "4"}
GRAVITY = [(1, "Heinous"), (2, "Non-Heinous")]
CASE_STATUSES = [
    (1, "Under Investigation"),
    (2, "Charge Sheeted"),
    (3, "Pending Trial"),
    (4, "Convicted"),
    (5, "Acquitted"),
    (6, "Closed - False Case"),
    (7, "Closed - Undetected"),
    (8, "Closed - Others"),
    (9, "Transferred"),
]
RELIGIONS = [(1, "Hindu"), (2, "Muslim"), (3, "Christian"), (4, "Jain"),
             (5, "Sikh"), (6, "Buddhist"), (7, "Others"), (8, "Not Stated")]
RELIGION_W = [72, 14, 6, 2, 1, 1, 1, 3]
CASTES = [(1, "General"), (2, "OBC"), (3, "SC"), (4, "ST"), (5, "Others"), (6, "Not Stated")]
CASTE_W = [28, 34, 18, 8, 4, 8]
OCCUPATIONS = [
    (1, "Farmer"), (2, "Daily Wage Labourer"), (3, "Private Employee"),
    (4, "Government Employee"), (5, "Business / Trader"), (6, "Student"),
    (7, "Homemaker"), (8, "Driver"), (9, "IT Professional"), (10, "Unemployed"),
    (11, "Retired"), (12, "Others"),
]
OCCUPATION_W = [16, 14, 16, 6, 12, 9, 10, 5, 5, 4, 2, 1]

UNIT_TYPES = [
    (1, "State Police Headquarters", "State", 1),
    (2, "District Police Office",    "District", 2),
    (3, "Circle Office",             "District", 3),
    (4, "Police Station",            "City", 4),
]
RANKS = [
    (1, "Director General of Police", 1), (2, "Inspector General of Police", 2),
    (3, "Superintendent of Police", 3), (4, "Deputy Superintendent of Police", 4),
    (5, "Police Inspector", 5), (6, "Police Sub-Inspector", 6),
    (7, "Assistant Sub-Inspector", 7), (8, "Head Constable", 8), (9, "Police Constable", 9),
]
DESIGNATIONS = [
    (1, "Station House Officer", 1), (2, "Investigating Officer", 2),
    (3, "Circle Inspector", 3), (4, "Superintendent of Police", 4),
    (5, "Station Writer", 5), (6, "Beat Constable", 6),
]

FIRST_NAMES_M = ["Ravi", "Suresh", "Kiran", "Anil", "Naveen", "Prakash", "Mahesh", "Vijay",
                 "Ramesh", "Arun", "Sunil", "Pavan", "Harish", "Girish", "Santosh", "Madhu",
                 "Vasanth", "Yogesh", "Chetan", "Praveen", "Manjunath", "Nagaraj", "Basavaraj",
                 "Imran", "Abdul", "Salman", "Joseph", "Anthony", "Umesh", "Lokesh", "Raghavendra",
                 "Shivakumar", "Venkatesh", "Srinivas", "Dinesh", "Gopal", "Krishna", "Mohan"]
FIRST_NAMES_F = ["Deepa", "Lakshmi", "Shilpa", "Geeta", "Roopa", "Nanda", "Bhavana", "Uma",
                 "Divya", "Anita", "Kavya", "Pooja", "Sushma", "Rekha", "Vidya", "Asha",
                 "Sneha", "Mamata", "Jyothi", "Sahana", "Fathima", "Ayesha", "Mary", "Sunitha",
                 "Radha", "Savitha", "Meena", "Padma", "Shobha", "Vani"]
LAST_NAMES = ["Gowda", "Shetty", "Rao", "Reddy", "Patil", "Kumar", "Hegde", "Naik",
              "Murthy", "Bhat", "Desai", "Iyer", "Swamy", "Achar", "Pujari", "Kamath",
              "Kulkarni", "Nayak", "Hiremath", "Joshi", "Angadi", "Banakar", "Khan",
              "Sheikh", "Dsouza", "Fernandes", "Biradar", "Talwar"]

GENDER_M, GENDER_F, GENDER_T = 1, 2, 3


# ================================================================ helpers ====
def gauss_int(rng, mean, sd, lo, hi):
    return max(lo, min(hi, int(round(rng.gauss(mean, sd)))))


def gauss_pos(rng, mean, sd, lo=0.0):
    return max(lo, rng.gauss(mean, sd))


def jitter(value, km, rng):
    """Offset a coordinate by up to ~km kilometres (1 deg ~= 111 km)."""
    return value + rng.uniform(-km, km) / 111.0


def make_name(gender_id, rng, used=None):
    pool = FIRST_NAMES_F if gender_id == GENDER_F else FIRST_NAMES_M
    for _ in range(50):
        name = "{} {} {}".format(rng.choice(pool), rng.choice("ABCDGHKLMNPRSV"),
                                 rng.choice(LAST_NAMES))
        if used is None:
            return name
        if name not in used:
            used.add(name)
            return name
    return name  # extremely unlikely fallback: allow a collision


def fmt_dt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def fmt_d(dt):
    return dt.strftime("%Y-%m-%d")


# ============================================================ org builders ===
def build_geo_org(rng):
    """States, districts, unit types, units, courts (+ internal geo/station indexes)."""
    states, districts, units, courts = [], [], [], []
    ka_state_id = 1
    states.append({"StateID": 1, "StateName": "Karnataka", "NationalityID": 1, "Active": 1})
    for i, (sname, _) in enumerate(NEIGHBOUR_STATES, start=2):
        states.append({"StateID": i, "StateName": sname, "NationalityID": 1, "Active": 1})

    district_meta = {}         # DistrictID -> dict(name, lat, lon, pop, arch, weight)
    station_meta = {}          # UnitID -> dict(district_id, name, lat, lon, hotcells)
    stations_by_district = {}  # DistrictID -> [UnitID]
    courts_by_district = {}    # DistrictID -> [(CourtID, kind)]
    neighbour_district_ids = {}  # StateID -> [DistrictID]

    did = 400
    uid = 0
    cid = 0
    eid_units = []

    # State HQ unit
    uid += 1
    units.append({"UnitID": uid, "UnitName": "Karnataka State Police Headquarters, Bengaluru",
                  "TypeID": 1, "ParentUnit": "", "NationalityID": 1, "StateID": ka_state_id,
                  "DistrictID": "", "Active": 1})
    hq_unit = uid

    for name, lat, lon, pop, arch in KA_DISTRICTS:
        did += 1
        districts.append({"DistrictID": did, "DistrictName": name, "StateID": ka_state_id, "Active": 1})
        weight = (pop / 1_000_000.0) * ARCHETYPE_PROPENSITY[arch]
        district_meta[did] = dict(name=name, lat=lat, lon=lon, pop=pop, arch=arch, weight=weight)

        uid += 1
        units.append({"UnitID": uid, "UnitName": f"District Police Office, {name}",
                      "TypeID": 2, "ParentUnit": hq_unit, "NationalityID": 1,
                      "StateID": ka_state_id, "DistrictID": did, "Active": 1})
        dpo_unit = uid

        n_st = max(3, N_STATIONS[arch] + rng.randint(-1, 1))
        n_circles = max(1, n_st // 4)
        circle_ids = []
        for c in range(n_circles):
            uid += 1
            units.append({"UnitID": uid, "UnitName": f"{name} Circle-{c + 1} Office",
                          "TypeID": 3, "ParentUnit": dpo_unit, "NationalityID": 1,
                          "StateID": ka_state_id, "DistrictID": did, "Active": 1})
            circle_ids.append(uid)

        stations_by_district[did] = []
        for s in range(n_st):
            uid += 1
            slat, slon = jitter(lat, 12, rng), jitter(lon, 12, rng)
            hotcells = [(jitter(slat, 4, rng), jitter(slon, 4, rng))
                        for _ in range(rng.randint(1, 2))]
            units.append({"UnitID": uid, "UnitName": f"{name} Police Station {s + 1}",
                          "TypeID": 4, "ParentUnit": circle_ids[s % n_circles],
                          "NationalityID": 1, "StateID": ka_state_id, "DistrictID": did,
                          "Active": 1})
            station_meta[uid] = dict(district_id=did, name=f"{name} Police Station {s + 1}",
                                     lat=slat, lon=slon, hotcells=hotcells)
            stations_by_district[did].append(uid)
            eid_units.append(uid)

        # two courts per district: Sessions + JMFC
        cid += 1
        courts.append({"CourtID": cid, "CourtName": f"Principal District & Sessions Court, {name}",
                       "DistrictID": did, "StateID": ka_state_id, "Active": 1})
        sessions_court = cid
        cid += 1
        courts.append({"CourtID": cid, "CourtName": f"JMFC Court, {name}",
                       "DistrictID": did, "StateID": ka_state_id, "Active": 1})
        courts_by_district[did] = [(sessions_court, "sessions"), (cid, "jmfc")]

    # neighbour-state districts (arrest destinations only)
    for sidx, (sname, dnames) in enumerate(NEIGHBOUR_STATES, start=2):
        neighbour_district_ids[sidx] = []
        for dname in dnames:
            did += 1
            districts.append({"DistrictID": did, "DistrictName": dname, "StateID": sidx, "Active": 1})
            neighbour_district_ids[sidx].append(did)

    return (states, districts, units, courts, district_meta, station_meta,
            stations_by_district, courts_by_district, neighbour_district_ids)


def build_employees(rng, station_meta, ref_year):
    """SHO + IOs + writers per station, an SP per district."""
    employees = []
    eid = 0
    used_kgid = set()
    sho_by_station, ios_by_station = {}, {}

    districts_seen = set()
    for unit_id, meta in station_meta.items():
        did = meta["district_id"]
        if did not in districts_seen:
            districts_seen.add(did)
            eid += 1
            employees.append(_employee(rng, eid, did, unit_id, rank=3, desig=4,
                                       ref_year=ref_year, used=used_kgid))
        # SHO — Inspector or PSI
        eid += 1
        employees.append(_employee(rng, eid, did, unit_id, rank=rng.choice([5, 5, 6]),
                                   desig=1, ref_year=ref_year, used=used_kgid))
        sho_by_station[unit_id] = eid
        # IOs — PSI/ASI
        ios = []
        for _ in range(rng.randint(2, 4)):
            eid += 1
            employees.append(_employee(rng, eid, did, unit_id, rank=rng.choice([6, 6, 7]),
                                       desig=2, ref_year=ref_year, used=used_kgid))
            ios.append(eid)
        ios_by_station[unit_id] = ios
        # station writer + beat constables
        for desig, rank in ((5, 8), (6, 9)):
            eid += 1
            employees.append(_employee(rng, eid, did, unit_id, rank=rank, desig=desig,
                                       ref_year=ref_year, used=used_kgid))
    return employees, sho_by_station, ios_by_station


def _employee(rng, eid, district_id, unit_id, rank, desig, ref_year, used):
    gender = GENDER_F if rng.random() < 0.12 else GENDER_M
    first = rng.choice(FIRST_NAMES_F if gender == GENDER_F else FIRST_NAMES_M)
    dob_year = ref_year - rng.randint(28, 56)
    dob = datetime(dob_year, rng.randint(1, 12), rng.randint(1, 28))
    appt = dob + timedelta(days=365 * rng.randint(21, 26) + rng.randint(0, 300))
    while True:
        kgid = f"KG{rng.randint(100000, 999999)}"
        if kgid not in used:
            used.add(kgid)
            break
    return {"EmployeeID": eid, "DistrictID": district_id, "UnitID": unit_id,
            "RankID": rank, "DesignationID": desig, "KGID": kgid, "FirstName": first,
            "EmployeeDOB": fmt_d(dob), "GenderID": gender,
            "BloodGroupID": rng.randint(1, 8),
            "PhysicallyChallenged": 1 if rng.random() < 0.02 else 0,
            "AppointmentDate": fmt_d(appt)}


# ======================================================== offender pool ======
def build_offender_pool(rng, n_pool, district_ids):
    """Identity pool for accused. ~12% are habitual and recur across cases; habitual
    offenders also cluster into small 'gangs' that co-offend (network structure)."""
    used_names = set()
    pool = []
    for i in range(n_pool):
        gender = GENDER_F if rng.random() < 0.10 else GENDER_M
        pool.append(dict(
            name=make_name(gender, rng, used_names),
            gender=gender,
            birth_year_offset=rng.gauss(0, 1),   # scaled per sub-head at use time
            home_district=rng.choice(district_ids),
        ))
    habitual = rng.sample(range(n_pool), max(1, int(n_pool * 0.12)))
    gangs = []
    hs = habitual[:]
    rng.shuffle(hs)
    while len(hs) >= 2:
        size = min(len(hs), rng.choices([2, 3, 4, 5], weights=[35, 35, 20, 10])[0])
        gangs.append([hs.pop() for _ in range(size)])
    return pool, habitual, gangs


# ========================================================== time curves ======
def build_day_curves(num_days, end, rng):
    month_factor = {1: 0.95, 2: 0.98, 3: 1.08, 4: 1.14, 5: 1.16, 6: 1.02,
                    7: 0.9, 8: 0.92, 9: 1.0, 10: 1.12, 11: 1.1, 12: 1.05}
    start = end - timedelta(days=num_days)
    gen_w, ris_w = [], []
    for d in range(num_days):
        day = start + timedelta(days=d)
        frac = d / max(1, num_days - 1)
        growth = 0.8 + 0.5 * frac
        season = month_factor[day.month]
        weekend = 1.12 if day.weekday() >= 5 else 1.0
        base = growth * season * weekend
        gen_w.append(base)
        ris_w.append(base * (0.45 + 2.2 * (frac ** 1.6)))
    days = [start + timedelta(days=d) for d in range(num_days)]

    def cumulate(ws):
        acc, out = 0.0, []
        for w in ws:
            acc += w
            out.append(acc)
        return out

    return days, cumulate(gen_w), cumulate(ris_w)


def pick_day(days, cum, rng):
    idx = bisect.bisect_left(cum, rng.uniform(0, cum[-1]))
    return days[min(idx, len(days) - 1)]


# ============================================================ case build =====
def build_cases(args, rng, geo, employees_ctx, pool_ctx):
    (states, districts, units, courts, district_meta, station_meta,
     stations_by_district, courts_by_district, neighbour_district_ids) = geo
    sho_by_station, ios_by_station = employees_ctx
    pool, habitual, gangs = pool_ctx

    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    days, cum_gen, cum_ris = build_day_curves(args.days, now, rng)

    sub_by_id = {s["id"]: s for s in SUB_HEADS}
    district_ids = list(district_meta.keys())
    district_weights = [district_meta[d]["weight"] for d in district_ids]

    # per-district sub-head weights (base w × archetype mix)
    district_sub_weights = {}
    for did in district_ids:
        arch = district_meta[did]["arch"]
        district_sub_weights[did] = [s["w"] * s["mix"].get(arch, 1.0) for s in SUB_HEADS]

    # emerging spike: one weighted district, chain snatching surge in the last 30 days
    spike_district = rng.choices(district_ids, weights=district_weights)[0]
    spike_sub = 10  # Chain Snatching

    gang_of = {}
    for g in gangs:
        for m in g:
            gang_of[m] = g

    case_rows, complainant_rows, victim_rows, accused_rows = [], [], [], []
    assoc_rows, arrest_rows, cs_rows = [], [], []
    serials = {}          # (station, category, year) -> running serial
    comp_id = vic_id = acc_id = arr_id = cs_id = 0
    used_comp_names = set()

    for case_id in range(1, args.cases + 1):
        did = rng.choices(district_ids, weights=district_weights)[0]
        sub = rng.choices(SUB_HEADS, weights=district_sub_weights[did])[0]
        meta = district_meta[did]

        # --- when ---
        if did == spike_district and sub["id"] == spike_sub and rng.random() < 0.65:
            day = now - timedelta(days=rng.uniform(0, 30))
        else:
            day = pick_day(days, cum_ris if sub["rising"] else cum_gen, rng)
        hour = int(round(rng.gauss(sub["peak"], sub["spread"]))) % 24
        inc_from = day.replace(hour=hour, minute=rng.randint(0, 59), second=0, microsecond=0)
        span_h = rng.uniform(0.2, 8.0) if rng.random() < 0.25 else rng.uniform(0.1, 1.5)
        inc_to = inc_from + timedelta(hours=span_h)
        delay_days = gauss_pos(rng, sub["delay"][0], sub["delay"][1])
        info_dt = inc_to + timedelta(days=delay_days, hours=rng.uniform(0, 6))
        if info_dt > now:
            info_dt = now - timedelta(hours=rng.uniform(1, 24))
        reg_date = info_dt + (timedelta(days=1) if rng.random() < 0.08 else timedelta(0))

        # --- where ---
        station = rng.choice(stations_by_district[did])
        smeta = station_meta[station]
        if rng.random() < 0.65 and smeta["hotcells"]:
            hlat, hlon = rng.choice(smeta["hotcells"])
            lat, lon = jitter(hlat, 1.2, rng), jitter(hlon, 1.2, rng)
        else:
            lat, lon = jitter(smeta["lat"], 5, rng), jitter(smeta["lon"], 5, rng)

        # --- category ---
        if sub["id"] == 25:
            category = "UDR"
        elif sub["id"] == 26:
            category = "PAR"
        elif sub["id"] == 24 and rng.random() < 0.5:
            category = "PAR"
        else:
            category = "Zero FIR" if rng.random() < 0.02 else "FIR"
        cat_id = {c[1]: c[0] for c in CASE_CATEGORIES}[category]

        year = reg_date.year
        key = (station, category, year)
        serials[key] = serials.get(key, 0) + 1
        serial = serials[key]
        crime_no = f"{CATEGORY_CODE[category]}{did:04d}{station:04d}{year:04d}{serial:05d}"
        case_no = f"{year:04d}{serial:05d}"

        gravity_id = 1 if rng.random() < sub["heinous"] else 2
        case_age_days = (now - reg_date).days

        # --- accused (identity pool; habitual offenders and gangs recur) ---
        n_acc = rng.choices([0, 1, 2, 3], weights=sub["acc_n"])[0]
        acc_pool_ids = []
        if n_acc:
            if rng.random() < 0.30 and habitual:
                seed_off = rng.choice(habitual)
                gang = gang_of.get(seed_off, [seed_off])
                picks = [seed_off] + [m for m in gang if m != seed_off]
                acc_pool_ids = picks[:n_acc]
                while len(acc_pool_ids) < n_acc:
                    extra = rng.randrange(len(pool))
                    if extra not in acc_pool_ids:
                        acc_pool_ids.append(extra)
            else:
                while len(acc_pool_ids) < n_acc:
                    p = rng.randrange(len(pool))
                    if p not in acc_pool_ids:
                        acc_pool_ids.append(p)

        case_accused = []
        for order, pidx in enumerate(acc_pool_ids, start=1):
            ident = pool[pidx]
            acc_id += 1
            age = gauss_int(rng, sub["acc"][0] + ident["birth_year_offset"] * sub["acc"][1] * 0.6,
                            3, 15, 78)
            gender = ident["gender"]
            if sub["afem"] > 0.3 and rng.random() < 0.5:
                gender = GENDER_F
            accused_rows.append({
                "AccusedMasterID": acc_id, "CaseMasterID": case_id,
                "AccusedName": ident["name"], "AgeYear": age,
                "GenderID": gender, "PersonID": f"A{order}",
            })
            case_accused.append((acc_id, pidx, order))

        # --- outcome: final report / status / court ---
        court_id = ""
        status_id = 1
        cstype = None
        cs_dt = None
        io = rng.choice(ios_by_station[station])
        mature = case_age_days > max(30, rng.gauss(sub["cs_lag"][0] * 0.7, 20))
        if sub["id"] == 25:  # UDR: enquiry, then closed
            status_id = 8 if case_age_days > rng.uniform(40, 120) else 1
        elif mature:
            r = rng.random()
            eff_cs = sub["cs"] if n_acc else sub["cs"] * 0.25
            eff_undet = sub["undet"] if n_acc == 0 else sub["undet"] * 0.5
            if r < eff_cs:
                cstype = "A"
            elif r < eff_cs + 0.04:
                cstype = "B"
            elif r < eff_cs + 0.04 + eff_undet:
                cstype = "C"
            else:
                status_id = 1 if rng.random() < 0.9 else 9
        if cstype:
            cs_id += 1
            cs_lag = gauss_pos(rng, sub["cs_lag"][0], sub["cs_lag"][1], lo=15)
            cs_dt = min(reg_date + timedelta(days=cs_lag), now - timedelta(days=1))
            cs_rows.append({"CSID": cs_id, "CaseMasterID": case_id,
                            "csdate": fmt_dt(cs_dt), "cstype": cstype, "PolicePersonID": io})
            if cstype == "A":
                kind = "sessions" if gravity_id == 1 else "jmfc"
                court_id = next(c for c, k in courts_by_district[did] if k == kind)
                since_cs = (now - cs_dt).days
                if since_cs > 400:
                    status_id = rng.choices([4, 5, 3], weights=[38, 22, 40])[0]
                elif since_cs > 150:
                    status_id = rng.choices([3, 2, 4, 5], weights=[55, 20, 15, 10])[0]
                else:
                    status_id = rng.choices([2, 3], weights=[55, 45])[0]
            elif cstype == "B":
                status_id = 6
            else:
                status_id = 7

        # --- arrests ---
        for acc_master_id, pidx, order in case_accused:
            if cstype == "B" or rng.random() >= sub["arrest"]:
                continue
            arr_id += 1
            lag = gauss_pos(rng, sub["arrest_lag"][0], sub["arrest_lag"][1])
            arr_dt = reg_date + timedelta(days=lag)
            if cs_dt:
                arr_dt = min(arr_dt, cs_dt - timedelta(days=1))
            if arr_dt > now:
                continue
            arr_type = 1 if rng.random() < 0.9 else 2
            roll = rng.random()
            if roll < 0.80:
                a_state, a_district = 1, did
            elif roll < 0.96:
                a_state, a_district = 1, rng.choice(list(district_meta.keys()))
            else:
                a_state = rng.randrange(2, 2 + len(NEIGHBOUR_STATES))
                a_district = rng.choice(neighbour_district_ids[a_state])
            arrest_rows.append({
                "ArrestSurrenderID": arr_id, "CaseMasterID": case_id,
                "ArrestSurrenderTypeID": arr_type, "ArrestSurrenderDate": fmt_d(arr_dt),
                "ArrestSurrenderStateId": a_state, "ArrestSurrenderDistrictId": a_district,
                "PoliceStationID": station, "IOID": io,
                "CourtID": courts_by_district[did][1][0],
                "AccusedMasterID": acc_master_id,
                "IsAccused": 1 if order == 1 else 0,
                "IsComplainantAccused": 1 if rng.random() < 0.01 else 0,
            })

        # --- victims ---
        n_vic = rng.choices([0, 1, 2], weights=sub["vic_n"])[0]
        victim_names = []
        for _ in range(n_vic):
            vic_id += 1
            v_gender = GENDER_F if rng.random() < sub["vfem"] else GENDER_M
            if rng.random() < 0.005:
                v_gender = GENDER_T
            v_age = gauss_int(rng, sub["vic"][0], sub["vic"][1], 3, 92)
            v_name = make_name(v_gender, rng)
            victim_names.append(v_name)
            victim_rows.append({
                "VictimMasterID": vic_id, "CaseMasterID": case_id,
                "VictimName": v_name, "AgeYear": v_age, "GenderID": v_gender,
                "VictimPolice": "1" if (sub["head"] in (1, 6) and rng.random() < 0.03) else "0",
            })

        # --- complainant(s) ---
        n_comp = 2 if rng.random() < 0.04 else 1
        for _ in range(n_comp):
            comp_id += 1
            if victim_names and rng.random() < 0.55 and sub["id"] != 25:
                c_name = victim_names[0]
                c_gender = victim_rows[-n_vic]["GenderID"] if n_vic else GENDER_M
                c_age = max(18, victim_rows[-n_vic]["AgeYear"]) if n_vic else 35
            else:
                c_gender = GENDER_F if rng.random() < 0.30 else GENDER_M
                c_age = gauss_int(rng, 41, 13, 18, 85)
                c_name = make_name(c_gender, rng, used_comp_names)
            complainant_rows.append({
                "ComplainantID": comp_id, "CaseMasterID": case_id,
                "ComplainantName": c_name, "AgeYear": c_age,
                "OccupationID": rng.choices([o[0] for o in OCCUPATIONS], weights=OCCUPATION_W)[0],
                "ReligionID": rng.choices([r[0] for r in RELIGIONS], weights=RELIGION_W)[0],
                "CasteID": rng.choices([c[0] for c in CASTES], weights=CASTE_W)[0],
                "GenderID": c_gender,
            })

        # --- act-section associations ---
        act_order = {}
        sec_no = 0
        for act, sec in sub["secs"]:
            sec_no += 1
            act_order.setdefault(act, len(act_order) + 1)
            assoc_rows.append({"CaseMasterID": case_id, "ActID": act, "SectionID": sec,
                               "ActOrderID": act_order[act], "SectionOrderID": sec_no})
        for prob, (act, sec) in sub.get("extra", []):
            if rng.random() < prob:
                sec_no += 1
                act_order.setdefault(act, len(act_order) + 1)
                assoc_rows.append({"CaseMasterID": case_id, "ActID": act, "SectionID": sec,
                                   "ActOrderID": act_order[act], "SectionOrderID": sec_no})

        # --- brief facts ---
        sec_str = ", ".join(f"{a} {s}" for a, s in sub["secs"])
        vic_str = (f" Victim: {victim_names[0]} ({victim_rows[-n_vic]['AgeYear']}/"
                   f"{'MFT'[victim_rows[-n_vic]['GenderID'] - 1]})." if n_vic else "")
        acc_str = (f" Accused: {', '.join(pool[p]['name'] for _, p, _ in case_accused)}."
                   if case_accused else " Accused unknown at registration.")
        brief = (f"On {inc_from.strftime('%d-%m-%Y')} at about {inc_from.strftime('%H:%M')} hrs, "
                 f"a case of {sub['name']} ({sec_str}) occurred within the limits of "
                 f"{smeta['name']}, {meta['name']} district.{vic_str}{acc_str} "
                 f"Case registered as {category} No. {case_no}.")

        case_rows.append({
            "CaseMasterID": case_id, "CrimeNo": crime_no, "CaseNo": case_no,
            "CrimeRegisteredDate": fmt_d(reg_date), "PolicePersonID": sho_by_station[station],
            "PoliceStationID": station, "CaseCategoryID": cat_id,
            "GravityOffenceID": gravity_id, "CrimeMajorHeadID": sub["head"],
            "CrimeMinorHeadID": sub["id"], "CaseStatusID": status_id, "CourtID": court_id,
            "IncidentFromDate": fmt_dt(inc_from), "IncidentToDate": fmt_dt(inc_to),
            "InfoReceivedPSDate": fmt_dt(info_dt),
            "latitude": round(lat, 6), "longitude": round(lon, 6), "BriefFacts": brief,
        })

    spike_name = district_meta[spike_district]["name"]
    return (case_rows, complainant_rows, victim_rows, accused_rows, assoc_rows,
            arrest_rows, cs_rows, spike_name, sub_by_id[spike_sub]["name"])


# ================================================================== main =====
def write_csv(path, rows, fieldnames):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description="Generate synthetic Police FIR data per the ERD.")
    ap.add_argument("--cases", type=int, default=20000)
    ap.add_argument("--pool", type=int, default=4000, help="accused identity pool size")
    ap.add_argument("--days", type=int, default=730, help="history window in days")
    ap.add_argument("--seed", type=int, default=42)
    default_out = os.path.join(os.path.dirname(__file__), "..", "output")
    ap.add_argument("--out", default=default_out)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    os.makedirs(args.out, exist_ok=True)

    geo = build_geo_org(rng)
    (states, districts, units, courts, district_meta, station_meta,
     stations_by_district, courts_by_district, neighbour_district_ids) = geo

    employees, sho_by_station, ios_by_station = build_employees(
        rng, station_meta, ref_year=datetime.now().year)
    pool, habitual, gangs = build_offender_pool(rng, args.pool, list(district_meta.keys()))

    (case_rows, complainant_rows, victim_rows, accused_rows, assoc_rows,
     arrest_rows, cs_rows, spike_district, spike_sub) = build_cases(
        args, rng, geo, (sho_by_station, ios_by_station), (pool, habitual, gangs))

    out = args.out
    write_csv(os.path.join(out, "State.csv"), states,
              ["StateID", "StateName", "NationalityID", "Active"])
    write_csv(os.path.join(out, "District.csv"), districts,
              ["DistrictID", "DistrictName", "StateID", "Active"])
    write_csv(os.path.join(out, "UnitType.csv"),
              [{"UnitTypeID": t[0], "UnitTypeName": t[1], "CityDistState": t[2],
                "Hierarchy": t[3], "Active": 1} for t in UNIT_TYPES],
              ["UnitTypeID", "UnitTypeName", "CityDistState", "Hierarchy", "Active"])
    write_csv(os.path.join(out, "Unit.csv"), units,
              ["UnitID", "UnitName", "TypeID", "ParentUnit", "NationalityID",
               "StateID", "DistrictID", "Active"])
    write_csv(os.path.join(out, "Rank.csv"),
              [{"RankID": r[0], "RankName": r[1], "Hierarchy": r[2], "Active": 1} for r in RANKS],
              ["RankID", "RankName", "Hierarchy", "Active"])
    write_csv(os.path.join(out, "Designation.csv"),
              [{"DesignationID": d[0], "DesignationName": d[1], "Active": 1, "SortOrder": d[2]}
               for d in DESIGNATIONS],
              ["DesignationID", "DesignationName", "Active", "SortOrder"])
    write_csv(os.path.join(out, "Employee.csv"), employees,
              ["EmployeeID", "DistrictID", "UnitID", "RankID", "DesignationID", "KGID",
               "FirstName", "EmployeeDOB", "GenderID", "BloodGroupID",
               "PhysicallyChallenged", "AppointmentDate"])
    write_csv(os.path.join(out, "Court.csv"), courts,
              ["CourtID", "CourtName", "DistrictID", "StateID", "Active"])
    write_csv(os.path.join(out, "CaseCategory.csv"),
              [{"CaseCategoryID": c[0], "LookupValue": c[1]} for c in CASE_CATEGORIES],
              ["CaseCategoryID", "LookupValue"])
    write_csv(os.path.join(out, "GravityOffence.csv"),
              [{"GravityOffenceID": g[0], "LookupValue": g[1]} for g in GRAVITY],
              ["GravityOffenceID", "LookupValue"])
    write_csv(os.path.join(out, "CaseStatusMaster.csv"),
              [{"CaseStatusID": s[0], "CaseStatusName": s[1]} for s in CASE_STATUSES],
              ["CaseStatusID", "CaseStatusName"])
    write_csv(os.path.join(out, "CasteMaster.csv"),
              [{"caste_master_id": c[0], "caste_master_name": c[1]} for c in CASTES],
              ["caste_master_id", "caste_master_name"])
    write_csv(os.path.join(out, "ReligionMaster.csv"),
              [{"ReligionID": r[0], "ReligionName": r[1]} for r in RELIGIONS],
              ["ReligionID", "ReligionName"])
    write_csv(os.path.join(out, "OccupationMaster.csv"),
              [{"OccupationID": o[0], "OccupationName": o[1]} for o in OCCUPATIONS],
              ["OccupationID", "OccupationName"])
    write_csv(os.path.join(out, "CrimeHead.csv"),
              [{"CrimeHeadID": h[0], "CrimeGroupName": h[1], "Active": 1} for h in CRIME_HEADS],
              ["CrimeHeadID", "CrimeGroupName", "Active"])
    write_csv(os.path.join(out, "CrimeSubHead.csv"),
              [{"CrimeSubHeadID": s["id"], "CrimeHeadID": s["head"],
                "CrimeHeadName": s["name"], "SeqID": i + 1}
               for i, s in enumerate(SUB_HEADS)],
              ["CrimeSubHeadID", "CrimeHeadID", "CrimeHeadName", "SeqID"])
    write_csv(os.path.join(out, "Act.csv"),
              [{"ActCode": a[0], "ActDescription": a[1], "ShortName": a[2], "Active": 1}
               for a in ACTS],
              ["ActCode", "ActDescription", "ShortName", "Active"])
    write_csv(os.path.join(out, "Section.csv"),
              [{"ActCode": s[0], "SectionCode": s[1], "SectionDescription": s[2], "Active": 1}
               for s in SECTIONS],
              ["ActCode", "SectionCode", "SectionDescription", "Active"])
    head_act_sec = []
    seen = set()
    for s in SUB_HEADS:
        for act, sec in s["secs"]:
            key = (s["head"], act, sec)
            if key not in seen:
                seen.add(key)
                head_act_sec.append({"CrimeHeadID": s["head"], "ActCode": act, "SectionCode": sec})
    write_csv(os.path.join(out, "CrimeHeadActSection.csv"), head_act_sec,
              ["CrimeHeadID", "ActCode", "SectionCode"])

    write_csv(os.path.join(out, "CaseMaster.csv"), case_rows,
              ["CaseMasterID", "CrimeNo", "CaseNo", "CrimeRegisteredDate", "PolicePersonID",
               "PoliceStationID", "CaseCategoryID", "GravityOffenceID", "CrimeMajorHeadID",
               "CrimeMinorHeadID", "CaseStatusID", "CourtID", "IncidentFromDate",
               "IncidentToDate", "InfoReceivedPSDate", "latitude", "longitude", "BriefFacts"])
    write_csv(os.path.join(out, "ComplainantDetails.csv"), complainant_rows,
              ["ComplainantID", "CaseMasterID", "ComplainantName", "AgeYear",
               "OccupationID", "ReligionID", "CasteID", "GenderID"])
    write_csv(os.path.join(out, "Victim.csv"), victim_rows,
              ["VictimMasterID", "CaseMasterID", "VictimName", "AgeYear", "GenderID",
               "VictimPolice"])
    write_csv(os.path.join(out, "Accused.csv"), accused_rows,
              ["AccusedMasterID", "CaseMasterID", "AccusedName", "AgeYear", "GenderID",
               "PersonID"])
    write_csv(os.path.join(out, "ActSectionAssociation.csv"), assoc_rows,
              ["CaseMasterID", "ActID", "SectionID", "ActOrderID", "SectionOrderID"])
    write_csv(os.path.join(out, "ArrestSurrender.csv"), arrest_rows,
              ["ArrestSurrenderID", "CaseMasterID", "ArrestSurrenderTypeID",
               "ArrestSurrenderDate", "ArrestSurrenderStateId", "ArrestSurrenderDistrictId",
               "PoliceStationID", "IOID", "CourtID", "AccusedMasterID", "IsAccused",
               "IsComplainantAccused"])
    write_csv(os.path.join(out, "ChargesheetDetails.csv"), cs_rows,
              ["CSID", "CaseMasterID", "csdate", "cstype", "PolicePersonID"])

    # --- console summary ---
    from collections import Counter
    head_names = dict(CRIME_HEADS)
    by_head = Counter(head_names[r["CrimeMajorHeadID"]] for r in case_rows)
    by_cat = Counter(r["CaseCategoryID"] for r in case_rows)
    cat_names = dict(CASE_CATEGORIES)
    cs_types = Counter(r["cstype"] for r in cs_rows)
    n_habitual_rows = sum(1 for r in accused_rows
                          if r["AccusedName"] in {pool[h]["name"] for h in habitual})
    print(f"Wrote FIR dataset ({len(case_rows)} cases) to {os.path.abspath(out)}")
    print(f"  Units: {len(units)} | Employees: {len(employees)} | Courts: {len(courts)}")
    print(f"  Complainants: {len(complainant_rows)} | Victims: {len(victim_rows)} | "
          f"Accused: {len(accused_rows)} (habitual-linked rows: {n_habitual_rows})")
    print(f"  ActSections: {len(assoc_rows)} | Arrests: {len(arrest_rows)} | "
          f"Chargesheets: {len(cs_rows)} {dict(cs_types)}")
    print(f"  Categories: {', '.join(f'{cat_names[c]}={n}' for c, n in by_cat.most_common())}")
    print(f"  Crime heads: {', '.join(f'{h}={n}' for h, n in by_head.most_common())}")
    print(f"  Emerging spike: '{spike_sub}' in {spike_district} (last 30 days)")


if __name__ == "__main__":
    main()
