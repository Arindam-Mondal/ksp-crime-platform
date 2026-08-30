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
import collections
import csv
import math
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
N_HOTCELLS = {"metro": 5, "urban": 3, "semiurban": 3, "rural": 2, "border": 3}

# Police station roster: district -> [(station name, lat, lon, load weight)].
# Names are the real KSP station rosters; coordinates are the station locality. The load
# weight sets relative case volume — a city-market or bus-stand station books many times
# what a peri-urban station does, which is what makes the hotspot layer look like a real
# jurisdiction rather than a uniform blob.
KA_STATIONS = {
    "Bengaluru City": [
        ("Cubbon Park PS", 12.9763, 77.5929, 1.0), ("Vidhana Soudha PS", 12.9794, 77.5912, 0.7),
        ("High Grounds PS", 12.9878, 77.5905, 0.9), ("Sadashivanagar PS", 13.0068, 77.5806, 0.8),
        ("Shivajinagar PS", 12.9850, 77.6050, 1.5), ("Commercial Street PS", 12.9827, 77.6091, 1.4),
        ("Halasuru Gate PS", 12.9718, 77.5990, 1.3), ("Ashok Nagar PS", 12.9698, 77.6031, 1.2),
        ("J.C. Nagar PS", 13.0056, 77.5960, 1.1), ("Bharathi Nagar PS", 12.9853, 77.6156, 1.2),
        ("Halasuru PS", 12.9770, 77.6260, 1.0), ("Indiranagar PS", 12.9719, 77.6412, 1.2),
        ("Jeevan Bhima Nagar PS", 12.9628, 77.6570, 1.0), ("Banaswadi PS", 13.0139, 77.6510, 1.1),
        ("Ramamurthy Nagar PS", 13.0158, 77.6780, 1.1), ("K.R. Puram PS", 13.0080, 77.6950, 1.3),
        ("Whitefield PS", 12.9698, 77.7500, 1.4), ("Marathahalli PS", 12.9591, 77.6974, 1.3),
        ("HAL PS", 12.9600, 77.6480, 0.9), ("Mahadevapura PS", 12.9910, 77.6970, 1.2),
        ("Bellandur PS", 12.9260, 77.6760, 1.1), ("Varthur PS", 12.9400, 77.7480, 0.9),
        ("Kadugodi PS", 12.9950, 77.7580, 1.0), ("Vibhutipura PS", 12.9700, 77.6700, 0.9),
        ("Koramangala PS", 12.9352, 77.6245, 1.3), ("Madiwala PS", 12.9220, 77.6180, 1.3),
        ("Adugodi PS", 12.9430, 77.6100, 1.0), ("Wilson Garden PS", 12.9480, 77.5950, 1.0),
        ("Tilak Nagar PS", 12.9330, 77.5900, 0.9), ("Viveknagar PS", 12.9500, 77.6180, 1.0),
        ("Jayanagar PS", 12.9250, 77.5830, 1.1), ("Siddapura PS", 12.9420, 77.5750, 1.0),
        ("Banashankari PS", 12.9250, 77.5470, 1.2), ("Girinagar PS", 12.9430, 77.5450, 0.9),
        ("Kumaraswamy Layout PS", 12.9080, 77.5560, 1.0), ("Konanakunte PS", 12.8850, 77.5620, 0.9),
        ("Hulimavu PS", 12.8790, 77.5990, 1.0), ("Bannerughatta PS", 12.8000, 77.5770, 0.8),
        ("Puttenahalli PS", 12.8900, 77.5850, 0.9), ("J.P. Nagar PS", 12.9080, 77.5850, 1.1),
        ("Basavanagudi PS", 12.9420, 77.5730, 1.0), ("Hanumanthanagar PS", 12.9440, 77.5560, 0.9),
        ("Chamrajpet PS", 12.9600, 77.5650, 1.0), ("V.V. Puram PS", 12.9530, 77.5760, 0.9),
        ("Cottonpet PS", 12.9660, 77.5760, 1.2), ("Chickpet PS", 12.9690, 77.5790, 1.3),
        ("Upparpet PS", 12.9760, 77.5730, 1.4), ("Kalasipalyam PS", 12.9620, 77.5760, 1.2),
        ("Byatarayanapura PS", 13.0620, 77.5900, 1.0), ("Yelahanka PS", 13.1000, 77.5960, 1.1),
        ("Yeshwanthpur PS", 13.0230, 77.5500, 1.2), ("Rajajinagar PS", 12.9900, 77.5520, 1.1),
        ("Basaveshwaranagar PS", 12.9880, 77.5350, 1.0), ("Kamakshipalya PS", 12.9760, 77.5250, 1.1),
        ("Magadi Road PS", 12.9740, 77.5480, 1.1), ("Vijayanagar PS", 12.9720, 77.5300, 1.1),
        ("Govindarajanagar PS", 12.9660, 77.5220, 1.0), ("Annapoorneshwari Nagar PS", 12.9450, 77.4980, 0.9),
        ("Nandini Layout PS", 13.0080, 77.5400, 1.0), ("Peenya PS", 13.0290, 77.5170, 1.1),
        ("Bagalagunte PS", 13.0470, 77.5230, 0.9), ("Hebbal PS", 13.0350, 77.5920, 1.1),
        ("R.T. Nagar PS", 13.0200, 77.5940, 1.0), ("Sanjay Nagar PS", 13.0300, 77.5800, 0.9),
        ("Malleswaram PS", 13.0030, 77.5700, 1.0), ("Subramanyanagar PS", 13.0000, 77.5540, 0.9),
        ("Kengeri PS", 12.9160, 77.4820, 1.0), ("Jnanabharathi PS", 12.9400, 77.5100, 0.9),
        ("Rajarajeshwari Nagar PS", 12.9270, 77.5190, 1.1), ("Subramanyapura PS", 12.9010, 77.5420, 0.9),
        ("Electronic City PS", 12.8450, 77.6600, 1.2), ("Bommanahalli PS", 12.9000, 77.6200, 1.1),
        ("Begur PS", 12.8720, 77.6200, 0.9), ("Parappana Agrahara PS", 12.8600, 77.6500, 0.9),
        ("Seshadripuram PS", 12.9930, 77.5760, 1.0), ("Gandhinagar PS", 12.9780, 77.5800, 1.3),
    ],
    "Bengaluru Rural": [
        ("Devanahalli PS", 13.2437, 77.7118, 1.0), ("Doddaballapura Town PS", 13.2257, 77.5378, 1.1),
        ("Doddaballapura Rural PS", 13.2600, 77.5600, 0.7), ("Nelamangala PS", 13.0997, 77.3940, 1.0),
        ("Hoskote PS", 13.0707, 77.7980, 1.1), ("Vijayapura (B.R.) PS", 13.3200, 77.7900, 0.7),
        ("Anekal PS", 12.7110, 77.6960, 1.0), ("Attibele PS", 12.7830, 77.7730, 0.9),
        ("Jigani PS", 12.7830, 77.6400, 0.8), ("KIAL Airport PS", 13.1986, 77.7066, 0.8),
    ],
    "Mysuru": [
        ("Devaraja PS", 12.3090, 76.6540, 1.3), ("Lashkar PS", 12.3070, 76.6480, 1.1),
        ("Krishnaraja PS", 12.3020, 76.6390, 1.2), ("Narasimharaja PS", 12.3010, 76.6600, 1.2),
        ("Nazarbad PS", 12.3050, 76.6690, 1.0), ("Vidyaranyapuram PS", 12.2830, 76.6420, 1.0),
        ("Kuvempunagar PS", 12.2880, 76.6150, 1.0), ("Jayalakshmipuram PS", 12.3130, 76.6210, 0.9),
        ("Ashokapuram PS", 12.2930, 76.6520, 0.9), ("Metagalli PS", 12.3400, 76.6120, 0.9),
        ("Udayagiri PS", 12.2960, 76.6740, 1.1), ("Saraswathipuram PS", 12.3090, 76.6280, 0.9),
        ("Hunsur PS", 12.3040, 76.2930, 0.9), ("Nanjangud Town PS", 12.1200, 76.6830, 0.9),
        ("T. Narasipura PS", 12.2050, 76.8990, 0.8), ("Periyapatna PS", 12.3350, 76.0980, 0.7),
        ("H.D. Kote PS", 12.0930, 76.3480, 0.7),
    ],
    "Mandya": [
        ("Mandya Town PS", 12.5230, 76.8960, 1.2), ("Mandya Rural PS", 12.5400, 76.9100, 0.8),
        ("Maddur PS", 12.5850, 77.0450, 1.0), ("Malavalli PS", 12.3830, 77.0620, 0.9),
        ("Srirangapatna PS", 12.4180, 76.6940, 1.0), ("Pandavapura PS", 12.5020, 76.6650, 0.8),
        ("K.R. Pete PS", 12.6660, 76.4870, 0.8), ("Nagamangala PS", 12.8180, 76.7550, 0.7),
        ("Bharathinagara PS", 12.6300, 77.0100, 0.7),
    ],
    "Hassan": [
        ("Hassan Town PS", 13.0050, 76.0990, 1.2), ("Hassan Rural PS", 13.0200, 76.1200, 0.8),
        ("Arsikere PS", 13.3140, 76.2570, 1.0), ("Channarayapatna PS", 12.9070, 76.3880, 0.9),
        ("Holenarsipura PS", 12.7870, 76.2440, 0.8), ("Sakleshpur PS", 12.9420, 75.7860, 0.9),
        ("Belur PS", 13.1650, 75.8630, 0.8), ("Alur PS", 12.9840, 75.9500, 0.6),
        ("Arakalgud PS", 12.7620, 76.0570, 0.7),
    ],
    "Tumakuru": [
        ("Tumakuru Town PS", 13.3400, 77.1010, 1.3), ("Kyathsandra PS", 13.3700, 77.1200, 0.9),
        ("Upparahalli PS", 13.3300, 77.0900, 0.9), ("Batawadi PS", 13.3200, 77.1200, 0.8),
        ("Tiptur PS", 13.2560, 76.4770, 1.0), ("Sira PS", 13.7410, 76.9040, 0.9),
        ("Madhugiri PS", 13.6620, 77.2100, 0.8), ("Kunigal PS", 13.0230, 77.0250, 0.8),
        ("Gubbi PS", 13.3120, 76.9400, 0.7), ("Koratagere PS", 13.5220, 77.2380, 0.6),
    ],
    "Kolar": [
        ("Kolar Town PS", 13.1360, 78.1330, 1.2), ("Kolar Rural PS", 13.1500, 78.1500, 0.8),
        ("Kolar Gold Fields PS", 12.9560, 78.2740, 1.1), ("Bangarpet PS", 12.9910, 78.1780, 0.9),
        ("Malur PS", 13.0040, 77.9370, 0.9), ("Mulbagal PS", 13.1640, 78.3930, 0.8),
        ("Srinivaspur PS", 13.3400, 78.2100, 0.7), ("Robertsonpet PS", 12.9560, 78.2800, 1.0),
    ],
    "Chikkaballapur": [
        ("Chikkaballapur Town PS", 13.4350, 77.7310, 1.1), ("Chintamani PS", 13.4000, 78.0530, 1.0),
        ("Gauribidanur PS", 13.6070, 77.5150, 0.9), ("Sidlaghatta PS", 13.3900, 77.8640, 0.8),
        ("Bagepalli PS", 13.7830, 77.7950, 0.7), ("Gudibande PS", 13.6720, 77.7080, 0.6),
        ("Nandi Hills PS", 13.3700, 77.6830, 0.7),
    ],
    "Ramanagara": [
        ("Ramanagara Town PS", 12.7110, 77.2810, 1.1), ("Channapatna Town PS", 12.6510, 77.2060, 1.0),
        ("Magadi PS", 12.9570, 77.2260, 0.8), ("Kanakapura Town PS", 12.5460, 77.4200, 1.0),
        ("Bidadi PS", 12.7990, 77.3860, 0.9), ("Harohalli PS", 12.6600, 77.4600, 0.7),
        ("Sathanur PS", 12.4600, 77.3600, 0.6),
    ],
    "Chamarajanagar": [
        ("Chamarajanagar Town PS", 11.9260, 76.9440, 1.1), ("Gundlupet PS", 11.8110, 76.6900, 0.9),
        ("Kollegal PS", 12.1540, 77.1100, 1.0), ("Yelandur PS", 12.0490, 77.0300, 0.7),
        ("Hanur PS", 12.1000, 77.2700, 0.7), ("Male Mahadeshwara Hills PS", 11.9800, 77.5800, 0.6),
    ],
    "Chitradurga": [
        ("Chitradurga Town PS", 14.2250, 76.3980, 1.2), ("Chitradurga Rural PS", 14.2400, 76.4200, 0.8),
        ("Hiriyur PS", 13.9450, 76.6180, 0.9), ("Challakere PS", 14.3170, 76.6520, 0.9),
        ("Hosadurga PS", 13.7960, 76.2760, 0.8), ("Holalkere PS", 14.0430, 76.1850, 0.7),
        ("Molakalmuru PS", 14.7180, 76.7420, 0.6), ("Bharamasagara PS", 14.1500, 76.4500, 0.6),
    ],
    "Davanagere": [
        ("Davanagere Town PS", 14.4640, 75.9220, 1.3), ("Vidyanagar PS", 14.4500, 75.9100, 1.0),
        ("Azad Nagar PS", 14.4700, 75.9300, 1.0), ("Doddapete PS", 14.4600, 75.9200, 1.1),
        ("K.T.J. Nagar PS", 14.4550, 75.9350, 0.9), ("Harihara PS", 14.5130, 75.8050, 1.0),
        ("Channagiri PS", 14.0240, 75.9250, 0.8), ("Honnali PS", 14.2400, 75.6470, 0.7),
        ("Jagalur PS", 14.5200, 76.1400, 0.6),
    ],
    "Shivamogga": [
        ("Doddapete PS (Shivamogga)", 13.9290, 75.5680, 1.2), ("Kote PS", 13.9330, 75.5700, 1.1),
        ("Tunganagar PS", 13.9400, 75.5600, 1.0), ("Vinobanagar PS", 13.9200, 75.5750, 1.0),
        ("Jayanagar PS (Shivamogga)", 13.9250, 75.5620, 0.9), ("Bhadravathi Town PS", 13.8480, 75.7050, 1.0),
        ("Sagara PS", 14.1660, 75.0330, 0.9), ("Shikaripura PS", 14.2680, 75.3540, 0.8),
        ("Sorab PS", 14.3800, 75.0920, 0.7), ("Thirthahalli PS", 13.6880, 75.2440, 0.7),
    ],
    "Chikkamagaluru": [
        ("Chikkamagaluru Town PS", 13.3160, 75.7720, 1.1), ("Chikkamagaluru Rural PS", 13.3300, 75.7900, 0.7),
        ("Kadur PS", 13.5510, 76.0110, 0.9), ("Tarikere PS", 13.7100, 75.8150, 0.8),
        ("Mudigere PS", 13.1330, 75.6390, 0.7), ("Koppa PS", 13.5320, 75.3550, 0.7),
        ("Sringeri PS", 13.4180, 75.2520, 0.6), ("N.R. Pura PS", 13.4000, 75.4900, 0.6),
    ],
    "Udupi": [
        ("Udupi Town PS", 13.3410, 74.7420, 1.2), ("Malpe PS", 13.3500, 74.7050, 1.0),
        ("Manipal PS", 13.3520, 74.7930, 1.0), ("Kaup PS", 13.2200, 74.7500, 0.8),
        ("Karkala Town PS", 13.2160, 74.9900, 0.9), ("Kundapura PS", 13.6260, 74.6920, 1.0),
        ("Byndoor PS", 13.8670, 74.6330, 0.7), ("Brahmavar PS", 13.4270, 74.7460, 0.8),
        ("Hebri PS", 13.4600, 74.9800, 0.6),
    ],
    "Dakshina Kannada": [
        ("Mangaluru North (Barke) PS", 12.8700, 74.8420, 1.3), ("Mangaluru South (Pandeshwar) PS", 12.8600, 74.8390, 1.3),
        ("Kadri PS", 12.8890, 74.8560, 1.2), ("Kavoor PS", 12.9010, 74.8340, 1.0),
        ("Urwa PS", 12.8850, 74.8420, 1.0), ("Panambur PS", 12.9400, 74.8100, 0.9),
        ("Surathkal PS", 12.9930, 74.7940, 1.0), ("Ullal PS", 12.8060, 74.8560, 0.9),
        ("Konaje PS", 12.8100, 74.9200, 0.8), ("Bantwal Town PS", 12.8900, 75.0350, 0.9),
        ("Puttur Town PS", 12.7590, 75.2010, 1.0), ("Sullia PS", 12.5600, 75.3870, 0.7),
        ("Belthangady PS", 12.8700, 75.3000, 0.7), ("Moodabidri PS", 13.0700, 74.9950, 0.8),
        ("Vittal PS", 12.7600, 75.0900, 0.7),
    ],
    "Uttara Kannada": [
        ("Karwar Town PS", 14.8130, 74.1290, 1.1), ("Ankola PS", 14.6600, 74.3000, 0.8),
        ("Kumta PS", 14.4260, 74.4160, 0.9), ("Honnavar PS", 14.2810, 74.4450, 0.8),
        ("Bhatkal PS", 13.9850, 74.5550, 1.0), ("Sirsi Town PS", 14.6200, 74.8380, 1.0),
        ("Siddapur PS", 14.3430, 74.8940, 0.7), ("Yellapur PS", 14.9640, 74.7080, 0.7),
        ("Mundgod PS", 14.9700, 75.0400, 0.7), ("Haliyal PS", 15.3280, 74.7590, 0.8),
        ("Dandeli PS", 15.2670, 74.6180, 0.9), ("Joida PS", 15.1300, 74.5000, 0.5),
    ],
    "Belagavi": [
        ("Camp PS", 15.8600, 74.5100, 1.2), ("Market PS", 15.8520, 74.5000, 1.3),
        ("Malmaruti PS", 15.8650, 74.5150, 1.1), ("Khade Bazar PS", 15.8560, 74.5060, 1.2),
        ("Tilakwadi PS", 15.8400, 74.4980, 1.1), ("Udyambag PS", 15.8200, 74.4900, 1.0),
        ("APMC PS", 15.8700, 74.5200, 0.9), ("Shahapur PS", 15.8450, 74.5120, 1.0),
        ("Chikkodi PS", 16.4270, 74.5900, 0.9), ("Gokak PS", 16.1670, 74.8230, 0.9),
        ("Bailhongal PS", 15.8140, 74.8590, 0.8), ("Ramdurg PS", 15.9500, 75.3000, 0.7),
        ("Athani PS", 16.7280, 75.0640, 0.8), ("Saundatti PS", 15.7700, 75.1200, 0.7),
        ("Nippani PS", 16.4000, 74.3800, 0.8),
    ],
    "Bagalkot": [
        ("Bagalkot Town PS", 16.1690, 75.6620, 1.1), ("Navanagar PS", 16.1800, 75.6900, 0.9),
        ("Badami PS", 15.9150, 75.6800, 0.8), ("Jamkhandi PS", 16.5030, 75.2900, 0.9),
        ("Mudhol PS", 16.3330, 75.2830, 0.8), ("Bilagi PS", 16.3500, 75.6100, 0.6),
        ("Hungund PS", 16.0630, 76.0580, 0.7), ("Rabkavi Banhatti PS", 16.4800, 75.1100, 0.7),
    ],
    "Vijayapura": [
        ("Vijayapura Town PS", 16.8300, 75.7100, 1.2), ("Gandhi Chowk PS", 16.8250, 75.7150, 1.1),
        ("Adarsh Nagar PS", 16.8400, 75.7200, 1.0), ("Jalanagar PS", 16.8200, 75.7000, 0.9),
        ("Indi PS", 17.1770, 75.9500, 0.8), ("Sindagi PS", 16.9200, 76.2350, 0.8),
        ("Basavana Bagewadi PS", 16.5720, 75.9700, 0.7), ("Muddebihal PS", 16.3380, 76.1300, 0.7),
        ("Talikota PS", 16.4700, 76.3100, 0.7),
    ],
    "Kalaburagi": [
        ("Station Bazar PS", 17.3350, 76.8400, 1.3), ("Chowk PS", 17.3300, 76.8340, 1.2),
        ("Brahmapur PS", 17.3260, 76.8300, 1.1), ("Ashok Nagar PS (Kalaburagi)", 17.3400, 76.8250, 1.0),
        ("Raghavendra Nagar PS", 17.3200, 76.8200, 0.9), ("M.B. Nagar PS", 17.3450, 76.8450, 0.9),
        ("University PS", 17.3500, 76.8100, 0.8), ("Farhatabad PS", 17.4200, 76.8600, 0.7),
        ("Sedam PS", 17.1800, 77.2850, 0.8), ("Chittapur PS", 17.1200, 77.0800, 0.7),
        ("Aland PS", 17.5640, 76.5680, 0.7), ("Jewargi PS", 17.0140, 76.7700, 0.6),
    ],
    "Bidar": [
        ("Bidar Town PS", 17.9130, 77.5300, 1.2), ("Gandhi Gunj PS", 17.9200, 77.5350, 1.1),
        ("New Town PS", 17.9050, 77.5250, 1.0), ("Basavakalyan PS", 17.8750, 76.9480, 0.9),
        ("Humnabad PS", 17.7700, 77.1300, 0.8), ("Bhalki PS", 18.0430, 77.2050, 0.8),
        ("Aurad PS", 18.2560, 77.4160, 0.7), ("Chitguppa PS", 17.6800, 77.1700, 0.6),
    ],
    "Raichur": [
        ("Raichur Town PS", 16.2080, 77.3460, 1.2), ("Market Yard PS", 16.2150, 77.3520, 1.0),
        ("Sadar Bazar PS", 16.2050, 77.3400, 1.1), ("Netaji Nagar PS", 16.2000, 77.3550, 0.9),
        ("Sindhanur PS", 15.7680, 76.7580, 0.9), ("Manvi PS", 15.9900, 77.0500, 0.8),
        ("Devadurga PS", 16.4200, 76.9300, 0.7), ("Lingasugur PS", 16.1580, 76.5200, 0.7),
    ],
    "Koppal": [
        ("Koppal Town PS", 15.3550, 76.1550, 1.1), ("Gangavathi PS", 15.4310, 76.5290, 1.0),
        ("Yelburga PS", 15.6150, 76.0100, 0.7), ("Kushtagi PS", 15.7560, 76.1900, 0.8),
        ("Kanakagiri PS", 15.5600, 76.3400, 0.6), ("Munirabad PS", 15.3300, 76.3400, 0.7),
    ],
    "Ballari": [
        ("Ballari Town PS", 15.1390, 76.9210, 1.2), ("Cowl Bazar PS", 15.1450, 76.9250, 1.1),
        ("Brucepet PS", 15.1500, 76.9300, 1.0), ("Gandhi Nagar PS (Ballari)", 15.1350, 76.9150, 0.9),
        ("Sanduru PS", 15.0700, 76.5500, 0.8), ("Siruguppa PS", 15.6300, 76.8900, 0.8),
        ("Kampli PS", 15.4050, 76.6000, 0.7), ("Kurugodu PS", 15.2700, 76.8000, 0.6),
        ("Moka PS", 15.2000, 76.8500, 0.6),
    ],
    "Vijayanagara": [
        ("Hosapete Town PS", 15.2690, 76.3870, 1.1), ("Hampi PS", 15.3350, 76.4600, 0.8),
        ("Kottur PS", 15.1600, 76.0700, 0.7), ("Harapanahalli PS", 14.7900, 75.9900, 0.8),
        ("Hagaribommanahalli PS", 15.0400, 76.2000, 0.7), ("Huvina Hadagali PS", 15.0400, 75.9500, 0.6),
    ],
    "Yadgir": [
        ("Yadgir Town PS", 16.7700, 77.1380, 1.1), ("Shahapur PS (Yadgir)", 16.6980, 76.8400, 0.9),
        ("Surapura PS", 16.5150, 76.7570, 0.8), ("Gurmitkal PS", 16.8600, 77.3900, 0.7),
        ("Wadgera PS", 16.6800, 77.0500, 0.6),
    ],
    "Gadag": [
        ("Gadag Town PS", 15.4310, 75.6360, 1.1), ("Betageri PS", 15.4400, 75.6300, 0.9),
        ("Ron PS", 15.6950, 75.7350, 0.8), ("Naragund PS", 15.7250, 75.3900, 0.7),
        ("Mundargi PS", 15.2050, 75.8800, 0.7), ("Shirahatti PS", 15.2300, 75.5800, 0.6),
    ],
    "Haveri": [
        ("Haveri Town PS", 14.7950, 75.4040, 1.1), ("Ranebennur Town PS", 14.6220, 75.6290, 1.0),
        ("Byadgi PS", 14.6720, 75.4870, 0.8), ("Hirekerur PS", 14.4530, 75.3950, 0.7),
        ("Savanur PS", 14.9700, 75.3350, 0.7), ("Shiggaon PS", 14.9900, 75.2200, 0.7),
        ("Hangal PS", 14.7640, 75.1230, 0.7),
    ],
    "Dharwad": [
        ("Vidyanagar PS (Hubballi)", 15.3550, 75.1250, 1.3), ("Ashok Nagar PS (Hubballi)", 15.3600, 75.1300, 1.2),
        ("Gokul Road PS", 15.3800, 75.1000, 1.1), ("Old Hubballi PS", 15.3450, 75.1400, 1.2),
        ("Bendigeri PS", 15.3500, 75.1350, 1.0), ("Ghantikeri PS", 15.3520, 75.1450, 1.0),
        ("Keshwapur PS", 15.3700, 75.1200, 1.0), ("Dharwad Town PS", 15.4590, 75.0080, 1.1),
        ("Dharwad Sub-urban PS", 15.4700, 75.0200, 0.8), ("Vidyagiri PS", 15.4500, 75.0150, 0.9),
        ("Kelageri PS", 15.4400, 74.9900, 0.7), ("Navanagar PS (Hubballi)", 15.3900, 75.1100, 0.9),
        ("Kalghatgi PS", 15.1800, 74.9700, 0.6), ("Kundgol PS", 15.2560, 75.2470, 0.6),
    ],
    "Kodagu": [
        ("Madikeri Town PS", 12.4240, 75.7380, 1.1), ("Virajpet PS", 12.1970, 75.8050, 0.9),
        ("Somwarpet PS", 12.5960, 75.8500, 0.8), ("Kushalnagar PS", 12.4570, 75.9600, 0.9),
        ("Gonikoppal PS", 12.2100, 75.9100, 0.7), ("Ponnampet PS", 12.1400, 75.9400, 0.6),
        ("Napoklu PS", 12.3600, 75.6700, 0.6),
    ],
}

# ============================================================ legal layer ====
# Act master: ActCode (PK, VARCHAR), description, short name.
ACTS = [
    # The 2023 codes replaced the colonial trio with effect from 01-07-2024. Both eras stay
    # Active: an offence is charged under the law in force on the date it was COMMITTED, so
    # FIRs for pre-cutover incidents continue to cite IPC/CrPC long after the changeover.
    ("BNS",   "Bharatiya Nyaya Sanhita, 2023",                  "BNS"),
    ("BNSS",  "Bharatiya Nagarik Suraksha Sanhita, 2023",       "BNSS"),
    ("BSA",   "Bharatiya Sakshya Adhiniyam, 2023",              "BSA"),
    ("IPC",   "Indian Penal Code, 1860",                        "IPC"),
    ("CRPC",  "Code of Criminal Procedure, 1973",               "CrPC"),
    ("ITACT", "Information Technology Act, 2000",               "IT Act"),
    ("NDPS",  "Narcotic Drugs and Psychotropic Substances Act, 1985", "NDPS Act"),
    ("ARMS",  "Arms Act, 1959",                                 "Arms Act"),
    ("KPACT", "Karnataka Police Act, 1963",                     "KP Act"),
    ("DPACT", "Dowry Prohibition Act, 1961",                    "DP Act"),
    ("MVACT", "Motor Vehicles Act, 1988",                       "MV Act"),
    ("POCSO", "Protection of Children from Sexual Offences Act, 2012", "POCSO Act"),
    ("SCST",  "Scheduled Castes and Scheduled Tribes (Prevention of Atrocities) Act, 1989",
              "SC/ST (PoA) Act"),
    ("KEACT", "Karnataka Excise Act, 1965",                     "KE Act"),
    ("PCACT", "Prevention of Corruption Act, 1988",             "PC Act"),
    ("JJACT", "Juvenile Justice (Care and Protection of Children) Act, 2015", "JJ Act"),
]

# The 2023 codes came into force on 01-07-2024. Offences committed on/after this date are
# charged under BNS/BNSS; earlier ones stay under IPC/CrPC. See era_sections().
BNS_CUTOVER = datetime(2024, 7, 1)

# IPC section -> BNS equivalent. Mapping follows the concordance published with the new code.
IPC_TO_BNS = {
    "34": "3(5)", "143": "189(2)", "147": "191(2)", "148": "191(3)", "149": "190",
    "279": "281", "302": "103(1)", "307": "109", "323": "115(2)", "324": "118(1)",
    "326": "118(2)", "337": "125(a)", "354": "74", "363": "137(2)", "379": "303(2)",
    "380": "305(a)", "384": "308(2)", "392": "309(4)", "395": "310(2)", "406": "316(2)",
    "420": "318(4)", "457": "331(4)", "498A": "85", "506": "351(2)",
    # BNS created a dedicated snatching offence; under the IPC this was charged as
    # theft (379) read with assault-in-attempt-to-commit-theft (356).
    "356": "304(2)",
}
CRPC_TO_BNSS = {"174": "194"}

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
    # --- Bharatiya Nyaya Sanhita, 2023 (in force 01-07-2024) ---
    ("BNS", "3(5)",   "Acts done by several persons in furtherance of common intention"),
    ("BNS", "74",     "Assault or criminal force to woman with intent to outrage modesty"),
    ("BNS", "85",     "Cruelty by husband or relative of husband"),
    ("BNS", "103(1)", "Murder"),
    ("BNS", "109",    "Attempt to murder"),
    ("BNS", "115(2)", "Voluntarily causing hurt"),
    ("BNS", "118(1)", "Voluntarily causing hurt by dangerous weapons or means"),
    ("BNS", "118(2)", "Voluntarily causing grievous hurt by dangerous weapons or means"),
    ("BNS", "125(a)", "Act endangering life or personal safety of others"),
    ("BNS", "137(2)", "Kidnapping"),
    ("BNS", "189(2)", "Being a member of an unlawful assembly"),
    ("BNS", "190",    "Every member of unlawful assembly guilty of offence committed in prosecution of common object"),
    ("BNS", "191(2)", "Rioting"),
    ("BNS", "191(3)", "Rioting, armed with deadly weapon"),
    ("BNS", "281",    "Rash driving or riding on a public way"),
    ("BNS", "303(2)", "Theft"),
    ("BNS", "304(2)", "Snatching"),
    ("BNS", "305(a)", "Theft in a dwelling house"),
    ("BNS", "308(2)", "Extortion"),
    ("BNS", "309(4)", "Robbery"),
    ("BNS", "310(2)", "Dacoity"),
    ("BNS", "316(2)", "Criminal breach of trust"),
    ("BNS", "318(4)", "Cheating and dishonestly inducing delivery of property"),
    ("BNS", "331(4)", "House-trespass by night after preparation for hurt"),
    ("BNS", "351(2)", "Criminal intimidation"),
    # --- Bharatiya Nagarik Suraksha Sanhita, 2023 ---
    ("BNSS", "194", "Police to enquire and report on suicide or unnatural death"),
    # --- special and local laws ---
    ("POCSO", "8",       "Punishment for sexual assault on a child"),
    ("POCSO", "12",      "Punishment for sexual harassment of a child"),
    ("SCST",  "3(1)(r)", "Intentional insult or intimidation with intent to humiliate a member of SC/ST"),
    ("SCST",  "3(1)(s)", "Abuse by caste name in any place within public view"),
    ("KEACT", "32",      "Unlawful import, export, transport or possession of liquor"),
    ("KEACT", "34",      "Unlawful manufacture or sale of intoxicant"),
    ("PCACT", "7",       "Public servant taking gratification other than legal remuneration"),
    ("JJACT", "75",      "Punishment for cruelty to a child"),
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

ROMAN = ["I", "II", "III", "IV", "V", "VI"]

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
    # Commissionerate ladder — the cities are policed by a Commissioner, not an SP.
    (10, "Commissioner of Police", 2), (11, "Deputy Commissioner of Police", 3),
    (12, "Assistant Commissioner of Police", 4),
]
DESIGNATIONS = [
    (1, "Station House Officer", 1), (2, "Investigating Officer", 2),
    (3, "Circle Inspector", 3), (4, "Superintendent of Police", 4),
    (5, "Station Writer", 5), (6, "Beat Constable", 6),
    (7, "Commissioner of Police", 7), (8, "Deputy Commissioner of Police", 8),
    (9, "Sub-Divisional Police Officer", 9),
]

# --- names -------------------------------------------------------------------------------
# Names are drawn community-first, then region-first, so a given name and a surname always
# come from the same tradition. The old pools crossed them at random and produced people
# called "Yogesh Sheikh" and "Mary Biradar", which is the first thing a Karnataka reader
# would notice. Surname geography matters too: Shetty/Poojary/Kamath are coastal, Patil/
# Biradar/Hiremath are north Karnataka, Gowda/Murthy/Swamy are old Mysuru.
NAMES = {
    "hindu": {
        "m": ["Ravi", "Suresh", "Kiran", "Anil", "Naveen", "Prakash", "Mahesh", "Vijay",
              "Ramesh", "Arun", "Sunil", "Pavan", "Harish", "Girish", "Santosh", "Madhu",
              "Vasanth", "Yogesh", "Chetan", "Praveen", "Manjunath", "Nagaraj", "Basavaraj",
              "Umesh", "Lokesh", "Raghavendra", "Shivakumar", "Venkatesh", "Srinivas",
              "Dinesh", "Gopal", "Krishna", "Mohan", "Shivanand", "Mallikarjun", "Ningappa",
              "Siddappa", "Channabasappa", "Veeresh", "Sharanappa", "Gurusiddappa",
              "Rachappa", "Hanumantha", "Nagendra", "Chandrashekar", "Jagadish", "Ashok",
              "Vinod", "Rajesh", "Sanjay", "Prashanth", "Shashidhar", "Muniraju",
              "Byrappa", "Puttaswamy", "Thimmappa", "Eshwarappa", "Devaraj", "Somashekar"],
        "f": ["Deepa", "Lakshmi", "Shilpa", "Geeta", "Roopa", "Nanda", "Bhavana", "Uma",
              "Divya", "Anita", "Kavya", "Pooja", "Sushma", "Rekha", "Vidya", "Asha",
              "Sneha", "Mamata", "Jyothi", "Sahana", "Sunitha", "Radha", "Savitha", "Meena",
              "Padma", "Shobha", "Vani", "Gangamma", "Renuka", "Parvathi", "Yashoda",
              "Bhagya", "Nagarathna", "Shanthamma", "Girija", "Sarojamma", "Chandrakala",
              "Manjula", "Hemalatha", "Pushpa", "Ratnamma", "Sowmya", "Nandini", "Ashwini"],
    },
    "muslim": {
        "m": ["Imran", "Abdul", "Salman", "Mohammed", "Syed", "Riyaz", "Nazeer", "Ilyas",
              "Rafiq", "Altaf", "Iqbal", "Javed", "Shabbir", "Mushtaq", "Ismail", "Yusuf",
              "Khaleel", "Sadiq", "Anwar", "Feroz", "Irfan", "Tanveer", "Zakir", "Mehboob"],
        "f": ["Fathima", "Ayesha", "Rehana", "Nasreen", "Shabana", "Zeenat", "Yasmin",
              "Rukhsana", "Sameena", "Farida", "Tabassum", "Shaheen", "Asma", "Nazia"],
    },
    "christian": {
        "m": ["Joseph", "Anthony", "Ronald", "Ivan", "Melwyn", "Wilson", "Clifford",
              "Denzil", "Alwyn", "Vincent", "Lawrence", "Norbert", "Stany", "Rovan"],
        "f": ["Mary", "Jessy", "Flavia", "Rita", "Sandra", "Melissa", "Anitha", "Sunitha",
              "Precilla", "Veronica", "Juliana", "Lavina"],
    },
}
SURNAMES = {
    "hindu": {
        "coastal": ["Shetty", "Poojary", "Kamath", "Pai", "Bhat", "Acharya", "Shenoy",
                    "Hegde", "Nayak", "Rao", "Prabhu", "Kini", "Kotian", "Suvarna",
                    "Devadiga", "Salian", "Karkera", "Amin", "Ballal", "Adyanthaya"],
        "north": ["Patil", "Biradar", "Hiremath", "Kulkarni", "Desai", "Angadi", "Jadhav",
                  "Chavan", "Kittur", "Savadi", "Katti", "Math", "Banakar", "Nadgouda",
                  "Gouda", "Malagi", "Hallikeri", "Yaligar", "Talwar", "Doddamani",
                  "Mullur", "Sindhur", "Kamble", "Wali", "Hanchinal"],
        "south": ["Gowda", "Murthy", "Swamy", "Reddy", "Kumar", "Naik", "Shastry",
                  "Gowdru", "Ningaiah", "Siddaiah", "Krishnappa", "Muniyappa", "Byrappa",
                  "Lingaiah", "Chandru", "Nanjundaswamy", "Puttaswamy", "Ramaiah",
                  "Shivanna", "Devaraju", "Mahadevappa", "Basavaraju", "Kempaiah"],
    },
    "muslim": {
        "coastal": ["Sheikh", "Bava", "Hassan", "Kunhi", "Beary", "Ahmed"],
        "north": ["Nadaf", "Mulla", "Bagwan", "Shaikh", "Jamadar", "Attar", "Bepari",
                  "Inamdar", "Sanadi", "Killedar", "Pinjar"],
        "south": ["Khan", "Sheikh", "Syed", "Pasha", "Baig", "Ahmed", "Sharief", "Peer"],
    },
    "christian": {
        "coastal": ["D'Souza", "Fernandes", "Lobo", "Pinto", "Rodrigues", "Menezes",
                    "Saldanha", "Mascarenhas", "Crasta", "Noronha", "Coelho", "Pais"],
        "north": ["Fernandes", "Rodrigues", "Pereira", "Gonsalves"],
        "south": ["Raj", "Thomas", "Peter", "Devadas", "Prakash", "Samuel"],
    },
}
# Region a district's naming tradition belongs to.
DISTRICT_REGION = {
    "Udupi": "coastal", "Dakshina Kannada": "coastal", "Uttara Kannada": "coastal",
    "Belagavi": "north", "Bagalkot": "north", "Vijayapura": "north", "Kalaburagi": "north",
    "Bidar": "north", "Raichur": "north", "Koppal": "north", "Ballari": "north",
    "Vijayanagara": "north", "Yadgir": "north", "Gadag": "north", "Haveri": "north",
    "Dharwad": "north",
}
# Community mix by region — coastal Karnataka has a far larger Christian population, and the
# north-east districts a larger Muslim one, than the state average.
REGION_COMMUNITY_W = {
    "coastal": {"hindu": 74, "muslim": 16, "christian": 10},
    "north":   {"hindu": 79, "muslim": 20, "christian": 1},
    "south":   {"hindu": 86, "muslim": 11, "christian": 3},
}

GENDER_M, GENDER_F, GENDER_T = 1, 2, 3


# ================================================================ helpers ====
def gauss_int(rng, mean, sd, lo, hi):
    return max(lo, min(hi, int(round(rng.gauss(mean, sd)))))


def gauss_pos(rng, mean, sd, lo=0.0):
    return max(lo, rng.gauss(mean, sd))


def jitter(value, km, rng):
    """Offset a latitude by up to ~km kilometres (1 deg ~= 111 km)."""
    return value + rng.uniform(-km, km) / 111.0


def scatter(lat, lon, km, rng):
    """Offset a (lat, lon) pair within ~km kilometres, as a disc rather than a square.

    A degree of longitude shrinks with latitude, so the east-west offset is divided by
    cos(lat); without that correction clusters come out visibly squashed on the map.
    """
    r = km * math.sqrt(rng.random())
    theta = rng.uniform(0, 2 * math.pi)
    dlat = (r * math.cos(theta)) / 111.0
    dlon = (r * math.sin(theta)) / (111.0 * max(0.2, math.cos(math.radians(lat))))
    return lat + dlat, lon + dlon


# Caste distribution conditioned on religion. Drawing the two independently (as before) put
# Muslim complainants in "General" and Hindu ones in categories that do not apply to them.
CASTE_BY_RELIGION = {
    1: [26, 38, 20, 9, 4, 3],   # Hindu
    2: [4, 70, 1, 1, 19, 5],    # Muslim — overwhelmingly OBC in Karnataka's list
    3: [18, 30, 16, 3, 28, 5],  # Christian
}
CASTE_DEFAULT = [20, 34, 14, 6, 20, 6]


def pick_religion(rng, region):
    """Religion drawn from the region's community mix, not a flat statewide marginal."""
    community = pick_community(rng, region)
    if community == "muslim":
        return 2, community
    if community == "christian":
        return 3, community
    # A small Jain/Sikh/Buddhist tail sits inside the Hindu-majority draw.
    return rng.choices([1, 4, 5, 6, 7], weights=[95, 3, 0.6, 0.6, 0.8])[0], community


def pick_caste(rng, religion_id):
    return rng.choices([1, 2, 3, 4, 5, 6],
                       weights=CASTE_BY_RELIGION.get(religion_id, CASTE_DEFAULT))[0]


def pick_occupation(rng, age, gender, arch):
    """Occupation conditioned on age, gender and how urban the district is.

    Previously these were independent draws, which produced male homemakers, retired
    19-year-olds, and as many IT professionals in Yadgir as in Bengaluru.
    """
    # index:      1farm 2wage 3priv 4govt 5busi 6stud 7home 8driv 9it 10unemp 11ret 12oth
    if age < 23:
        w = [4, 8, 10, 0.5, 3, 55, 6, 2, 4, 6, 0, 1]
    elif age >= 60:
        w = [26, 8, 3, 2, 10, 0, 18, 1, 0.5, 3, 27, 2]
    else:
        w = [20, 16, 18, 7, 14, 1, 12, 6, 6, 4, 0.5, 1]

    if gender == GENDER_F:
        w = [v * m for v, m in zip(w, [0.7, 0.8, 0.9, 0.9, 0.5, 1.1, 6.0,
                                       0.05, 0.7, 0.8, 0.7, 1.0])]
    else:
        # "Homemaker" is recorded for men only very rarely; driving and manual labour skew
        # the other way.
        w = [v * m for v, m in zip(w, [1.1, 1.15, 1.0, 1.0, 1.2, 1.0, 0.02,
                                       1.4, 1.1, 1.1, 1.1, 1.0])]
    if arch == "metro":
        w = [v * m for v, m in zip(w, [0.05, 0.8, 2.0, 1.2, 1.3, 1.2, 0.9,
                                       1.6, 6.0, 1.1, 0.9, 1.0])]
    elif arch == "urban":
        w = [v * m for v, m in zip(w, [0.35, 0.9, 1.5, 1.1, 1.2, 1.1, 1.0,
                                       1.3, 2.0, 1.0, 1.0, 1.0])]
    elif arch == "rural":
        w = [v * m for v, m in zip(w, [1.9, 1.2, 0.5, 0.8, 0.8, 0.9, 1.1,
                                       0.7, 0.04, 0.9, 1.0, 1.0])]
    return rng.choices([o[0] for o in OCCUPATIONS], weights=w)[0]


def pick_community(rng, region):
    w = REGION_COMMUNITY_W[region]
    return rng.choices(list(w.keys()), weights=list(w.values()))[0]


def make_name(gender_id, rng, used=None, region="south", community=None):
    """A community- and region-coherent Karnataka name.

    Uniqueness matters beyond cosmetics: analytics resolve an accused across FIRs by
    (AccusedName, GenderID) alone, so two distinct people sharing a name would silently
    merge into one offender and fabricate cross-district links. Callers that mint durable
    identities MUST pass `used`; the shape variety below exists partly to keep that
    namespace wide enough to stay collision-free at demo scale.
    """
    community = community or pick_community(rng, region)
    key = "f" if gender_id == GENDER_F else "m"
    givens = NAMES[community][key]
    fathers = NAMES[community]["m"]
    surnames = SURNAMES[community][region]

    for _ in range(60):
        shape = rng.random()
        given = rng.choice(givens)
        if shape < 0.34:
            name = "{} {}".format(given, rng.choice(surnames))
        elif shape < 0.62:
            # given + father's given + surname — the full form used on a charge sheet
            name = "{} {} {}".format(given, rng.choice(fathers), rng.choice(surnames))
        elif shape < 0.82:
            # village/father initial prefix, e.g. "K. Manjunath Gowda"
            name = "{}. {} {}".format(rng.choice("BCDGHKLMNPRSTVY"), given,
                                      rng.choice(surnames))
        elif shape < 0.93:
            # double initial then given name — very common in south Karnataka records
            name = "{}. {}. {}".format(rng.choice("BCDGHKLMNPRSTVY"),
                                       rng.choice("BCDGHKLMNPRSTVY"), given)
        else:
            # given name followed by a trailing initial, no surname
            name = "{} {}.".format(given, rng.choice("BCDGHKLMNPRSTVY"))
        if used is None:
            return name
        if name not in used:
            used.add(name)
            return name
    return name  # extremely unlikely fallback: allow a collision


# Opening sentence of BriefFacts, varied by crime head so 20k narratives don't read as one
# template. {d}=date, {t}=time, {s}=station, {D}=district, {n}=sub-head name.
NARRATIVES = {
    1: [  # crimes against body
        "On {d} at about {t} hrs, a case of {n} was reported within the limits of {s}, {D} district.",
        "On {d} at about {t} hrs, information was received at {s}, {D} district regarding an incident of {n}.",
        "A complaint of {n} was lodged at {s}, {D} district in respect of an incident that occurred on {d} at about {t} hrs.",
    ],
    2: [  # property
        "On {d} at about {t} hrs, unknown persons committed {n} within the limits of {s}, {D} district.",
        "On {d} at about {t} hrs, a case of {n} was reported at {s}, {D} district; property was removed from the spot.",
        "The complainant reported at {s}, {D} district that {n} took place on {d} at about {t} hrs.",
    ],
    3: [  # crimes against women
        "On {d} at about {t} hrs, a complaint of {n} was received at {s}, {D} district.",
        "A written complaint alleging {n} was submitted at {s}, {D} district concerning events of {d} at about {t} hrs.",
    ],
    5: [  # cyber
        "The complainant reported at {s}, {D} district that on {d} at about {t} hrs they were defrauded through an online transaction ({n}).",
        "On {d} at about {t} hrs, a case of {n} was reported at {s}, {D} district following an electronic communication received by the complainant.",
    ],
    6: [  # public order
        "On {d} at about {t} hrs, a case of {n} was registered on police report within the limits of {s}, {D} district.",
        "On {d} at about {t} hrs, staff of {s}, {D} district on patrol duty came across an incident of {n}.",
    ],
    7: [  # special & local laws
        "On {d} at about {t} hrs, staff of {s}, {D} district acting on credible information detected a case of {n}.",
        "On {d} at about {t} hrs, during a raid conducted within the limits of {s}, {D} district, a case of {n} was booked.",
    ],
}
NARRATIVE_DEFAULT = [
    "On {d} at about {t} hrs, a case of {n} was reported within the limits of {s}, {D} district.",
    "On {d} at about {t} hrs, a report of {n} was received at {s}, {D} district.",
]


def narrative_opening(rng, sub, inc_from, station_name, district_name):
    templates = NARRATIVES.get(sub["head"], NARRATIVE_DEFAULT)
    return rng.choice(templates).format(
        d=inc_from.strftime("%d-%m-%Y"), t=inc_from.strftime("%H:%M"),
        s=station_name, D=district_name, n=sub["name"])


def era_act_section(act, sec, incident_dt):
    """Map a canonical (IPC/CrPC) citation onto the code in force when the offence was
    committed. SUB_HEADS declare IPC/CrPC sections; offences on or after 01-07-2024 are
    charged under the BNS/BNSS equivalent instead. Other statutes are unaffected."""
    if incident_dt < BNS_CUTOVER:
        return act, sec
    if act == "IPC" and sec in IPC_TO_BNS:
        return "BNS", IPC_TO_BNS[sec]
    if act == "CRPC" and sec in CRPC_TO_BNSS:
        return "BNSS", CRPC_TO_BNSS[sec]
    return act, sec


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
        district_meta[did] = dict(name=name, lat=lat, lon=lon, pop=pop, arch=arch,
                                  weight=weight, region=DISTRICT_REGION.get(name, "south"))

        uid += 1
        units.append({"UnitID": uid, "UnitName": f"District Police Office, {name}",
                      "TypeID": 2, "ParentUnit": hq_unit, "NationalityID": 1,
                      "StateID": ka_state_id, "DistrictID": did, "Active": 1})
        dpo_unit = uid
        district_meta[did]["dpo_unit"] = dpo_unit

        roster = KA_STATIONS[name]
        n_circles = max(1, len(roster) // 6)
        circle_ids = []
        for c in range(n_circles):
            uid += 1
            units.append({"UnitID": uid, "UnitName": f"{name} Circle-{c + 1} Office",
                          "TypeID": 3, "ParentUnit": dpo_unit, "NationalityID": 1,
                          "StateID": ka_state_id, "DistrictID": did, "Active": 1})
            circle_ids.append(uid)
        district_meta[did]["circle_units"] = circle_ids

        stations_by_district[did] = []
        for s, (sname, slat, slon, sweight) in enumerate(roster):
            uid += 1
            # Hot cells are the recurring trouble spots inside a beat — a market, a bus
            # stand, a bar strip. Tight jitter keeps them as identifiable clusters.
            hotcells = [scatter(slat, slon, 1.8, rng) for _ in range(rng.randint(1, 3))]
            units.append({"UnitID": uid, "UnitName": sname,
                          "TypeID": 4, "ParentUnit": circle_ids[s % n_circles],
                          "NationalityID": 1, "StateID": ka_state_id, "DistrictID": did,
                          "Active": 1})
            station_meta[uid] = dict(district_id=did, name=sname, lat=slat, lon=slon,
                                     hotcells=hotcells, weight=sweight)
            stations_by_district[did].append(uid)
            eid_units.append(uid)

        # Courts: Sessions + numbered magistrate courts, scaled to district size, plus the
        # special courts that actually try NDPS and POCSO matters.
        cid += 1
        courts.append({"CourtID": cid, "CourtName": f"Principal District & Sessions Court, {name}",
                       "DistrictID": did, "StateID": ka_state_id, "Active": 1})
        entries = [(cid, "sessions")]
        n_magistrate = max(1, min(6, len(roster) // 6))
        for m in range(n_magistrate):
            cid += 1
            if arch == "metro":
                label = f"{ROMAN[m]} Addl. Chief Metropolitan Magistrate Court, {name}"
            elif m == 0:
                label = f"JMFC Court, {name}"
            else:
                label = f"{ROMAN[m]} Addl. JMFC Court, {name}"
            courts.append({"CourtID": cid, "CourtName": label, "DistrictID": did,
                           "StateID": ka_state_id, "Active": 1})
            entries.append((cid, "jmfc"))
        for special in ("Special Court for NDPS Cases", "Special Court under POCSO Act"):
            cid += 1
            courts.append({"CourtID": cid, "CourtName": f"{special}, {name}",
                           "DistrictID": did, "StateID": ka_state_id, "Active": 1})
            entries.append((cid, "special"))
        courts_by_district[did] = entries

    # neighbour-state districts (arrest destinations only)
    for sidx, (sname, dnames) in enumerate(NEIGHBOUR_STATES, start=2):
        neighbour_district_ids[sidx] = []
        for dname in dnames:
            did += 1
            districts.append({"DistrictID": did, "DistrictName": dname, "StateID": sidx, "Active": 1})
            neighbour_district_ids[sidx].append(did)

    return (states, districts, units, courts, district_meta, station_meta,
            stations_by_district, courts_by_district, neighbour_district_ids)


def build_employees(rng, station_meta, district_meta, ref_year):
    """SHO + IOs + writers per station, plus a district command element per district."""
    employees = []
    eid = 0
    used_kgid = set()
    sho_by_station, ios_by_station = {}, {}

    districts_seen = set()
    for unit_id, meta in station_meta.items():
        did = meta["district_id"]
        dmeta = district_meta[did]
        region = dmeta["region"]
        if did not in districts_seen:
            districts_seen.add(did)
            # District command sits at the District Police Office, not at a station. A
            # commissionerate is headed by a Commissioner with DCPs under him; a district
            # by an SP with DySPs. Both are posted to the DPO unit.
            metro = dmeta["arch"] == "metro"
            head_rank, head_desig = (10, 7) if metro else (3, 4)
            depu_rank, depu_desig = (11, 8) if metro else (4, 9)
            eid += 1
            employees.append(_employee(rng, eid, did, dmeta["dpo_unit"], rank=head_rank,
                                       desig=head_desig, ref_year=ref_year, used=used_kgid,
                                       region=region))
            eid += 1
            employees.append(_employee(rng, eid, did, dmeta["dpo_unit"], rank=depu_rank,
                                       desig=depu_desig, ref_year=ref_year, used=used_kgid,
                                       region=region))
            # One Police Inspector heads each circle.
            for circle_unit in dmeta["circle_units"]:
                eid += 1
                employees.append(_employee(rng, eid, did, circle_unit, rank=5, desig=3,
                                           ref_year=ref_year, used=used_kgid, region=region))
        # SHO — Inspector or PSI
        eid += 1
        employees.append(_employee(rng, eid, did, unit_id, rank=rng.choice([5, 5, 6]),
                                   desig=1, ref_year=ref_year, used=used_kgid, region=region))
        sho_by_station[unit_id] = eid
        # IOs — PSI/ASI
        ios = []
        for _ in range(rng.randint(2, 4)):
            eid += 1
            employees.append(_employee(rng, eid, did, unit_id, rank=rng.choice([6, 6, 7]),
                                       desig=2, ref_year=ref_year, used=used_kgid,
                                       region=region))
            ios.append(eid)
        ios_by_station[unit_id] = ios
        # station writer + beat constables
        for desig, rank in ((5, 8), (6, 9)):
            eid += 1
            employees.append(_employee(rng, eid, did, unit_id, rank=rank, desig=desig,
                                       ref_year=ref_year, used=used_kgid, region=region))
    return employees, sho_by_station, ios_by_station


def _employee(rng, eid, district_id, unit_id, rank, desig, ref_year, used, region="south"):
    gender = GENDER_F if rng.random() < 0.12 else GENDER_M
    # The ERD gives Employee a single FirstName column; a real KSP roster records the full
    # name there (e.g. "Manjunath B Hiremath"), not a bare given name.
    first = make_name(gender, rng, region=region)
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
def build_offender_pool(rng, n_pool, district_ids, district_meta, district_weights):
    """Identity pool for accused. ~12% are habitual and recur across cases; habitual
    offenders also cluster into small 'gangs' that co-offend (network structure)."""
    used_names = set()
    pool = []
    for i in range(n_pool):
        gender = GENDER_F if rng.random() < 0.14 else GENDER_M
        # Home district is drawn on the same population/archetype weights as cases, so
        # offender supply tracks case volume. Spreading the pool uniformly instead would
        # leave Bengaluru City's ~130 local offenders carrying 5,500 cases between them.
        home = rng.choices(district_ids, weights=district_weights)[0]
        pool.append(dict(
            name=make_name(gender, rng, used_names, region=district_meta[home]["region"]),
            gender=gender,
            birth_year_offset=rng.gauss(0, 1),   # scaled per sub-head at use time
            birth_year=None,                     # fixed on first appearance; see build_cases
            home_district=home,
        ))
    habitual = rng.sample(range(n_pool), max(1, int(n_pool * 0.12)))
    # Gangs form among habitual offenders who live in the same district. A gang whose
    # members are scattered across the state is not a gang — co-offending is local, and
    # building it that way is what makes the community detection findable rather than noise.
    by_home = collections.defaultdict(list)
    for i in habitual:
        by_home[pool[i]["home_district"]].append(i)
    gangs = []
    for members in by_home.values():
        hs = members[:]
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

    if args.end_date:
        now = datetime.strptime(args.end_date, "%Y-%m-%d").replace(hour=23)
    else:
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

    # Station load weights within each district, and an inverse-distance table used to place
    # out-of-district arrests near the case district rather than uniformly across the state.
    station_weights = {
        did: [station_meta[s]["weight"] for s in stations_by_district[did]]
        for did in district_ids
    }
    nearby_ids, nearby_weights = {}, {}
    for did in district_ids:
        a = district_meta[did]
        others = [o for o in district_ids if o != did]
        nearby_ids[did] = others
        nearby_weights[did] = [
            1.0 / (0.5 + (district_meta[o]["lat"] - a["lat"]) ** 2
                   + (district_meta[o]["lon"] - a["lon"]) ** 2)
            for o in others
        ]

    # emerging spike: one weighted district, chain snatching surge in the last 30 days
    spike_district = rng.choices(district_ids, weights=district_weights)[0]
    spike_sub = 10  # Chain Snatching

    gang_of = {}
    for g in gangs:
        for m in g:
            gang_of[m] = g

    pool_male = [i for i, p in enumerate(pool) if p["gender"] == GENDER_M]
    pool_female = [i for i, p in enumerate(pool) if p["gender"] == GENDER_F]

    # Offenders are indexed by home district and gender so a case draws from people who
    # actually live in that jurisdiction. Without this an offender accumulates cases in
    # 18 districts at once, which reads as a name collision rather than a career criminal.
    local_pool = collections.defaultdict(lambda: {GENDER_M: [], GENDER_F: []})
    for i, p in enumerate(pool):
        local_pool[p["home_district"]][p["gender"]].append(i)
    local_habitual = collections.defaultdict(list)
    for i in habitual:
        local_habitual[pool[i]["home_district"]].append(i)

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
        # An FIR cannot be registered in the future — the overnight slip above can otherwise
        # push the last day's cases past the end of the window.
        if reg_date > now:
            reg_date = now

        # --- where ---
        station = rng.choices(stations_by_district[did], weights=station_weights[did])[0]
        smeta = station_meta[station]
        if rng.random() < 0.65 and smeta["hotcells"]:
            hlat, hlon = rng.choice(smeta["hotcells"])
            lat, lon = scatter(hlat, hlon, 0.7, rng)
        else:
            lat, lon = scatter(smeta["lat"], smeta["lon"], 2.5, rng)

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
        # How the number is actually written and spoken at a station ("FIR No. 123/2026").
        # CrimeNo/CaseNo keep the ERD-mandated machine format; this is narrative only.
        display_no = f"{serial}/{year}"

        gravity_id = 1 if rng.random() < sub["heinous"] else 2
        case_age_days = (now - reg_date).days

        # --- accused (identity pool; habitual offenders and gangs recur) ---
        n_acc = rng.choices([0, 1, 2, 3], weights=sub["acc_n"])[0]
        acc_pool_ids = []
        if n_acc:
            local_hab = local_habitual.get(did) or habitual
            if rng.random() < 0.30 and local_hab:
                seed_off = rng.choice(local_hab)
                gang = gang_of.get(seed_off, [seed_off])
                picks = [seed_off] + [m for m in gang if m != seed_off]
                acc_pool_ids = picks[:n_acc]
                # Pad a short gang from the same district, not from anywhere in the state —
                # otherwise every cluster acquires members from five districts and the
                # community view stops looking like a local crew.
                pad = local_pool[did][GENDER_M] or list(range(len(pool)))
                guard = 0
                while len(acc_pool_ids) < n_acc and guard < 40:
                    guard += 1
                    extra = rng.choice(pad)
                    if extra not in acc_pool_ids:
                        acc_pool_ids.append(extra)
            else:
                # Draw from the gender-matched half of the pool rather than flipping an
                # identity's gender at emit time. Analytics resolve a person by
                # (name, gender), so overriding gender per case splits one offender into
                # two and silently destroys the co-accused links between their FIRs.
                want = GENDER_F if rng.random() < sub["afem"] else GENDER_M
                # Mostly local offenders; a minority travel, which is what makes a genuine
                # cross-jurisdiction link worth flagging on the network page.
                if rng.random() < 0.85 and local_pool[did][want]:
                    bucket = local_pool[did][want]
                else:
                    bucket = (pool_female if want == GENDER_F else pool_male) or \
                        list(range(len(pool)))
                guard = 0
                while len(acc_pool_ids) < n_acc and guard < 40:
                    guard += 1
                    p = rng.choice(bucket)
                    if p not in acc_pool_ids:
                        acc_pool_ids.append(p)

        case_accused = []
        for order, pidx in enumerate(acc_pool_ids, start=1):
            ident = pool[pidx]
            acc_id += 1
            # Age is fixed to the identity, not redrawn per FIR: the first case an identity
            # appears in sets an implied birth year (from that crime's age profile), and
            # every later FIR ages them forward from it. Otherwise the same offender shows a
            # different age in each of their own cases.
            if ident["birth_year"] is None:
                first_age = gauss_int(
                    rng, sub["acc"][0] + ident["birth_year_offset"] * sub["acc"][1] * 0.6,
                    3, 15, 78)
                ident["birth_year"] = inc_from.year - first_age
            age = max(12, min(90, inc_from.year - ident["birth_year"]))
            gender = ident["gender"]
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
                # NDPS and POCSO matters go to their special courts; heinous offences are
                # committed to Sessions; the rest are spread across the magistrate courts.
                if sub["id"] == 22:
                    kind = "special"
                elif gravity_id == 1:
                    kind = "sessions"
                else:
                    kind = "jmfc"
                bench = [c for c, k in courts_by_district[did] if k == kind]
                court_id = rng.choice(bench)
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
                # An absconding accused is picked up a district or two away far more often
                # than across the state, so weight the draw by proximity.
                a_state, a_district = 1, rng.choices(
                    nearby_ids[did], weights=nearby_weights[did])[0]
            else:
                a_state = rng.randrange(2, 2 + len(NEIGHBOUR_STATES))
                a_district = rng.choice(neighbour_district_ids[a_state])
            # The accused is produced before the jurisdictional magistrate, not the Sessions
            # judge — remand is a magistrate's function.
            magistrate = [c for c, k in courts_by_district[did] if k == "jmfc"]
            arrest_rows.append({
                "ArrestSurrenderID": arr_id, "CaseMasterID": case_id,
                "ArrestSurrenderTypeID": arr_type, "ArrestSurrenderDate": fmt_d(arr_dt),
                "ArrestSurrenderStateId": a_state, "ArrestSurrenderDistrictId": a_district,
                "PoliceStationID": station, "IOID": io,
                "CourtID": rng.choice(magistrate),
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
            v_name = make_name(v_gender, rng, region=meta["region"])
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
                c_name = make_name(c_gender, rng, used_comp_names, region=meta["region"])
            religion_id, _ = pick_religion(rng, meta["region"])
            complainant_rows.append({
                "ComplainantID": comp_id, "CaseMasterID": case_id,
                "ComplainantName": c_name, "AgeYear": c_age,
                "OccupationID": pick_occupation(rng, c_age, c_gender, meta["arch"]),
                "ReligionID": religion_id,
                "CasteID": pick_caste(rng, religion_id),
                "GenderID": c_gender,
            })

        # --- act-section associations ---
        act_order = {}
        sec_no = 0
        primary_cited = []
        for act, sec in sub["secs"]:
            act, sec = era_act_section(act, sec, inc_from)
            sec_no += 1
            act_order.setdefault(act, len(act_order) + 1)
            primary_cited.append((act, sec))
            assoc_rows.append({"CaseMasterID": case_id, "ActID": act, "SectionID": sec,
                               "ActOrderID": act_order[act], "SectionOrderID": sec_no})
        for prob, (act, sec) in sub.get("extra", []):
            if rng.random() < prob:
                act, sec = era_act_section(act, sec, inc_from)
                sec_no += 1
                act_order.setdefault(act, len(act_order) + 1)
                assoc_rows.append({"CaseMasterID": case_id, "ActID": act, "SectionID": sec,
                                   "ActOrderID": act_order[act], "SectionOrderID": sec_no})

        # --- brief facts ---
        # NOTE: the " Victim: …" and " Accused: …" spans are a privacy contract with
        # backend/app/routers/assistant.py::_redact, which strips them before any text
        # reaches the LLM. Keep their shape (name, then "(age/G)." for the victim) stable —
        # only the surrounding narrative varies.
        sec_str = ", ".join(f"{a} {s}" for a, s in primary_cited)
        vic_str = (f" Victim: {victim_names[0]} ({victim_rows[-n_vic]['AgeYear']}/"
                   f"{'MFT'[victim_rows[-n_vic]['GenderID'] - 1]})." if n_vic else "")
        acc_str = (f" Accused: {', '.join(pool[p]['name'] for _, p, _ in case_accused)}."
                   if case_accused else " Accused unknown at registration.")
        brief = (f"{narrative_opening(rng, sub, inc_from, smeta['name'], meta['name'])} "
                 f"Offence u/s {sec_str}.{vic_str}{acc_str} "
                 f"Case registered as {category} No. {display_no}.")

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
    ap.add_argument("--days", type=int, default=1095, help="history window in days")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--end-date", dest="end_date", default=None,
                    help="last day of the history window as YYYY-MM-DD (default: today). "
                         "Pin this to make a run reproducible — without it the window "
                         "slides with the wall clock and the same seed gives new dates.")
    default_out = os.path.join(os.path.dirname(__file__), "..", "output")
    ap.add_argument("--out", default=default_out)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    os.makedirs(args.out, exist_ok=True)

    geo = build_geo_org(rng)
    (states, districts, units, courts, district_meta, station_meta,
     stations_by_district, courts_by_district, neighbour_district_ids) = geo

    ref_year = (datetime.strptime(args.end_date, "%Y-%m-%d").year if args.end_date
                else datetime.now().year)
    employees, sho_by_station, ios_by_station = build_employees(
        rng, station_meta, district_meta, ref_year=ref_year)
    _dids = list(district_meta.keys())
    pool, habitual, gangs = build_offender_pool(
        rng, args.pool, _dids, district_meta,
        [district_meta[d]["weight"] for d in _dids])

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
