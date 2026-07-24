# Police FIR System — Database Schema (from the official ER Diagram)

> Transcribed from `Police_FIR_ER_Diagram.pdf` (Karnataka Police Department — "Police FIR
> System — ER Diagram", provided with the challenge). **This schema is authoritative and must
> be strictly followed**: table names, column names, types, and keys below match the PDF
> exactly. The synthetic data generator (`data/generator/generate_synthetic.py`) emits one CSV
> per table with these column names, and the backend reads them as-is.

## Key legend

- **PK** — Primary Key: uniquely identifies each record in the table.
- **FK** — Foreign Key: references the Primary Key of another table.

## Table overview

| Group | Tables |
|---|---|
| Case core | `CaseMaster`, `ComplainantDetails`, `Victim`, `Accused`, `ActSectionAssociation`, `ArrestSurrender`, `ChargesheetDetails` |
| Legal reference | `Act`, `Section`, `CrimeHead`, `CrimeSubHead`, `CrimeHeadActSection` |
| Case lookups | `CaseCategory`, `GravityOffence`, `CaseStatusMaster` |
| Person lookups | `CasteMaster`, `ReligionMaster`, `OccupationMaster` |
| Organisation | `State`, `District`, `Unit`, `UnitType`, `Rank`, `Designation`, `Employee`, `Court` |

---

## 1. CaseMaster

One row per FIR/case — the hub of the entire schema.

| Column | Type | Key | Description |
|---|---|---|---|
| CaseMasterID | INT | PK | Unique identifier for each FIR/case |
| CrimeNo | VARCHAR | | Crime Number assigned at police-station level, linked to `PoliceStationID`. Format: **1-digit Case Category Code + 4-digit District ID + 4-digit Police Station ID (Unit ID) + 4-digit Year + 5-digit Running Serial Number**. A separate running serial is maintained per police station, case category and year. Examples: FIR `104430006202600001`, UDR `304430006202600001`, Zero FIR `804430006202600001`, PAR `404430006202600001` |
| CaseNo | VARCHAR | | Generated at police-station level, associated with `PoliceStationID`. Per case category, a unique serial per station per year. Format **YYYY + 5-digit running serial** (e.g. `202600001`) — the last 9 digits of `CrimeNo` |
| CrimeRegisteredDate | DATE | | Date when the FIR was registered |
| PolicePersonID | INT | FK | → `Employee.EmployeeID` — officer who registered the FIR |
| PoliceStationID | INT | FK | → `Unit.UnitID` — police station where FIR is registered |
| CaseCategoryID | INT | FK | → `CaseCategory.CaseCategoryID` — category |
| GravityOffenceID | INT | FK | → `GravityOffence.GravityOffenceID` — gravity level of the offence |
| CrimeMajorHeadID | INT | FK | → `CrimeHead.CrimeHeadID` — major crime head classification |
| CrimeMinorHeadID | INT | FK | → `CrimeSubHead.CrimeSubHeadID` — minor crime sub-head classification |
| CaseStatusID | INT | FK | → `CaseStatusMaster.CaseStatusID` — current status of the case |
| CourtID | INT | FK | → `Court.CourtID` — court where the case is being heard |
| IncidentFromDate | DATETIME | | Start date and time of the incident |
| IncidentToDate | DATETIME | | End date and time of the incident |
| InfoReceivedPSDate | DATETIME | | Date/time when the police station received information about the incident |
| latitude | DECIMAL | | GPS latitude of the incident location |
| longitude | DECIMAL | | GPS longitude of the incident location |
| BriefFacts | NVARCHAR(MAX) | | Summary of the case |

## 2. ComplainantDetails

| Column | Type | Key | Description |
|---|---|---|---|
| ComplainantID | INT | PK | Unique identifier for the complainant |
| CaseMasterID | INT | FK | → `CaseMaster.CaseMasterID` — FIR/case filed by this complainant |
| ComplainantName | VARCHAR | | Full name of the complainant |
| AgeYear | INT | | Age of the complainant |
| OccupationID | INT | FK | → `OccupationMaster.OccupationID` — occupation of the complainant |
| ReligionID | INT | FK | → `ReligionMaster.ReligionID` — religion of the complainant |
| CasteID | INT | FK | → `CasteMaster.caste_master_id` — caste of the complainant |
| GenderID | INT | | Gender of the complainant (lookup value) |

## 3. ActSectionAssociation

Junction: which act-sections are invoked in which case.

| Column | Type | Key | Description |
|---|---|---|---|
| CaseMasterID | INT | FK | → `CaseMaster.CaseMasterID` — FIR/case this act-section applies to |
| ActID | INT | FK | → `Act.ActCode` — legal act under which charges are framed |
| SectionID | INT | FK | → `Section.SectionCode` — specific section of the act invoked |
| ActOrderID | INT | | Display/print order of the act within the case |
| SectionOrderID | INT | | Display/print order of the section under the act |

## 4. Victim

| Column | Type | Key | Description |
|---|---|---|---|
| VictimMasterID | INT | PK | Unique identifier for each victim |
| CaseMasterID | INT | FK | → `CaseMaster.CaseMasterID` — FIR/case this victim belongs to |
| VictimName | VARCHAR | | Full name of the victim |
| AgeYear | INT | | Age of the victim in years |
| GenderID | INT | | Gender of the victim (lookup value) like M, F, T |
| VictimPolice | VARCHAR | | `1` if the victim is police, else `0` |

## 5. Accused

| Column | Type | Key | Description |
|---|---|---|---|
| AccusedMasterID | INT | PK | Unique identifier for each accused person |
| CaseMasterID | INT | FK | → `CaseMaster.CaseMasterID` — FIR/case this accused is linked to |
| AccusedName | VARCHAR | | Full name of the accused |
| AgeYear | INT | | Age of the accused |
| GenderID | INT | | Gender of the accused, mentioned as M/F/T |
| PersonID | VARCHAR | | Accused ordering within the case, like `A1`, `A2`, `A3`… |

## 6. ArrestSurrender

| Column | Type | Key | Description |
|---|---|---|---|
| ArrestSurrenderID | INT | PK | Unique identifier for each arrest/surrender event |
| CaseMasterID | INT | FK | → `CaseMaster.CaseMasterID` — FIR/case linked to this arrest/surrender |
| ArrestSurrenderTypeID | INT | | Type of event: arrest or voluntary surrender (lookup value) |
| ArrestSurrenderDate | DATE | | Date of arrest or surrender |
| ArrestSurrenderStateId | INT | FK | → `State.StateID` — state where arrest/surrender occurred |
| ArrestSurrenderDistrictId | INT | FK | → `District.DistrictID` — district where arrest/surrender occurred |
| PoliceStationID | INT | FK | → `Unit.UnitID` — police station handling the arrest |
| IOID | INT | FK | → `Employee.EmployeeID` — Investigating Officer who made the arrest |
| CourtID | INT | FK | → `Court.CourtID` — court before which the accused was produced |
| AccusedMasterID | INT | FK | → `Accused.AccusedMasterID` — accused person linked to this arrest/surrender |
| IsAccused | BIT | | Flag (0/1): whether the person is the primary accused in the case |
| IsComplainantAccused | BIT | | Flag (0/1): whether the complainant is also listed as accused |

## 7. Act

| Column | Type | Key | Description |
|---|---|---|---|
| ActCode | VARCHAR | PK | Unique code for the legal act (e.g. IPC, NDPS) |
| ActDescription | VARCHAR | | Full official name/description of the act |
| ShortName | VARCHAR | | Abbreviated/common name of the act |
| Active | BIT | | Whether the act is currently active (1=Active, 0=Inactive) |

## 8. Section

| Column | Type | Key | Description |
|---|---|---|---|
| ActCode | VARCHAR | FK | → `Act.ActCode` — parent act this section belongs to |
| SectionCode | VARCHAR | | Section number/code (e.g. 302, 307) |
| SectionDescription | VARCHAR | | Full description of the section |
| Active | BIT | | Whether the section is currently active (1=Active, 0=Inactive) |

## 9. CrimeHeadActSection

Maps crime heads to the act-sections that constitute them.

| Column | Type | Key | Description |
|---|---|---|---|
| CrimeHeadID | INT | FK | → `CrimeHead.CrimeHeadID` — crime head this act-section combination maps to |
| ActCode | VARCHAR | FK | → `Act.ActCode` — legal act linked to this crime head |
| SectionCode | VARCHAR | | Section code from the act applicable to this crime head |

## 10. CrimeHead

| Column | Type | Key | Description |
|---|---|---|---|
| CrimeHeadID | INT | PK | Unique identifier for the major crime head |
| CrimeGroupName | VARCHAR | | Name of the crime group/major head (e.g. Crimes Against Body) |
| Active | BIT | | Whether this crime head is active (1=Active, 0=Inactive) |

## 11. CrimeSubHead

| Column | Type | Key | Description |
|---|---|---|---|
| CrimeSubHeadID | INT | PK | Unique identifier for the crime sub-head |
| CrimeHeadID | INT | FK | → `CrimeHead.CrimeHeadID` — parent major crime head |
| CrimeHeadName | VARCHAR | | Name of this crime sub-head (e.g. Murder, Robbery) |
| SeqID | INT | | Display/sort sequence number for ordering sub-heads |

## 12. CasteMaster

| Column | Type | Key | Description |
|---|---|---|---|
| caste_master_id | INT | PK | Unique identifier for each caste. Referenced by `ComplainantDetails.CasteID` |
| caste_master_name | VARCHAR | | Name of the caste |

## 13. ReligionMaster

| Column | Type | Key | Description |
|---|---|---|---|
| ReligionID | INT | PK | Unique identifier for each religion. Referenced by `ComplainantDetails.ReligionID` |
| ReligionName | VARCHAR | | Name of the religion (e.g. Hindu, Muslim, Christian) |

## 14. OccupationMaster

| Column | Type | Key | Description |
|---|---|---|---|
| OccupationID | INT | PK | Unique identifier for each occupation. Referenced by `ComplainantDetails.OccupationID` |
| OccupationName | VARCHAR | | Name of the occupation (e.g. Farmer, Government Employee) |

## 15. CaseStatusMaster

| Column | Type | Key | Description |
|---|---|---|---|
| CaseStatusID | INT | PK | Unique identifier for each case status. Referenced by `CaseMaster.CaseStatusID` |
| CaseStatusName | VARCHAR | | Name of the status (e.g. Under Investigation, Charge Sheeted, Closed) |

## 16. Court

| Column | Type | Key | Description |
|---|---|---|---|
| CourtID | INT | PK | Unique identifier for the court. Referenced by `CaseMaster.CourtID`, `ArrestSurrender.CourtID` |
| CourtName | VARCHAR | | Full name of the court |
| DistrictID | INT | FK | → `District.DistrictID` — district where the court is located |
| StateID | INT | FK | → `State.StateID` — state where the court is located |
| Active | BIT | | Whether the court is active (1=Active, 0=Inactive) |

## 17. District

| Column | Type | Key | Description |
|---|---|---|---|
| DistrictID | INT | PK | Unique identifier for the district. Referenced by `Court`, `Unit`, `Employee`, `ArrestSurrender` |
| DistrictName | VARCHAR | | Name of the district |
| StateID | INT | FK | → `State.StateID` — state this district belongs to |
| Active | BIT | | Whether the district record is active (1=Active, 0=Inactive) |

## 18. State

| Column | Type | Key | Description |
|---|---|---|---|
| StateID | INT | PK | Unique identifier for the state. Referenced by `Court`, `District`, `Unit`, `ArrestSurrender` |
| StateName | VARCHAR | | Name of the state |
| NationalityID | INT | | Nationality reference ID |
| Active | BIT | | Whether the state record is active (1=Active, 0=Inactive) |

## 19. Unit

| Column | Type | Key | Description |
|---|---|---|---|
| UnitID | INT | PK | Unique identifier for the police unit. Referenced by `CaseMaster.PoliceStationID`, `Employee.UnitID`, `ArrestSurrender.PoliceStationID` |
| UnitName | VARCHAR | | Name of the unit or police station |
| TypeID | INT | FK | → `UnitType.UnitTypeID` — type/category of the unit |
| ParentUnit | INT | | Parent unit ID for hierarchy (self-reference to `UnitID`) |
| NationalityID | INT | | Nationality reference ID |
| StateID | INT | FK | → `State.StateID` — state the unit belongs to |
| DistrictID | INT | FK | → `District.DistrictID` — district the unit belongs to |
| Active | BIT | | Whether the unit is active (1=Active, 0=Inactive) |

## 20. UnitType

| Column | Type | Key | Description |
|---|---|---|---|
| UnitTypeID | INT | PK | Unique identifier for the unit type. Referenced by `Unit.TypeID` |
| UnitTypeName | VARCHAR | | Name of the unit type (e.g. Police Station, Circle Office) |
| CityDistState | VARCHAR | | Operational level: City / District / State |
| Hierarchy | INT | | Hierarchy level number (lower = higher authority) |
| Active | BIT | | Whether the unit type is active (1=Active, 0=Inactive) |

## 21. Rank

| Column | Type | Key | Description |
|---|---|---|---|
| RankID | INT | PK | Unique identifier for the rank. Referenced by `Employee.RankID` |
| RankName | VARCHAR | | Name of the police rank (e.g. Constable, Inspector, DSP) |
| Hierarchy | INT | | Rank hierarchy level (lower = higher rank) |
| Active | BIT | | Whether the rank is active (1=Active, 0=Inactive) |

## 22. Designation

| Column | Type | Key | Description |
|---|---|---|---|
| DesignationID | INT | PK | Unique identifier for the designation. Referenced by `Employee.DesignationID` |
| DesignationName | VARCHAR | | Name of the designation (e.g. Investigating Officer, SHO) |
| Active | BIT | | Whether the designation is active (1=Active, 0=Inactive) |
| SortOrder | INT | | Display sort order for dropdowns/reports |

## 23. Employee

| Column | Type | Key | Description |
|---|---|---|---|
| EmployeeID | INT | PK | Unique identifier for the police employee. Referenced by `CaseMaster.PolicePersonID`, `ArrestSurrender.IOID` |
| DistrictID | INT | FK | → `District.DistrictID` — district the employee is currently posted in |
| UnitID | INT | FK | → `Unit.UnitID` — unit/police station the employee is assigned to |
| RankID | INT | FK | → `Rank.RankID` — current rank of the employee |
| DesignationID | INT | FK | → `Designation.DesignationID` — current designation of the employee |
| KGID | VARCHAR | | Karnataka Government ID (unique government employee number) |
| FirstName | VARCHAR | | First name of the employee |
| EmployeeDOB | DATE | | Date of birth of the employee |
| GenderID | INT | | Gender of the employee (lookup value) |
| BloodGroupID | INT | | Blood group of the employee (lookup value) |
| PhysicallyChallenged | BIT | | Flag: whether the employee is physically challenged (1=Yes, 0=No) |
| AppointmentDate | DATE | | Date of appointment to government service |

## 24. CaseCategory

| Column | Type | Key | Description |
|---|---|---|---|
| CaseCategoryID | INT | PK | Unique identifier for the case category. Referenced by `CaseMaster.CaseCategoryID` |
| LookupValue | VARCHAR | | Category name (FIR, UDR, PAR, …) |

## 25. GravityOffence

| Column | Type | Key | Description |
|---|---|---|---|
| GravityOffenceID | INT | PK | Unique identifier for the gravity level. Referenced by `CaseMaster.GravityOffenceID` |
| LookupValue | VARCHAR | | Gravity description (e.g. Heinous, Non-Heinous) |

## 26. ChargesheetDetails

| Column | Type | Key | Description |
|---|---|---|---|
| CSID | INT | PK | Unique identifier for the chargesheet |
| CaseMasterID | INT | FK | → `CaseMaster.CaseMasterID` — case this chargesheet belongs to |
| csdate | DATETIME | | Chargesheeted date |
| cstype | CHAR | | Final report type: **A** → Chargesheet, **B** → False Case, **C** → Undetected |
| PolicePersonID | INT | FK | → `Employee.EmployeeID` — officer who filed the final report |

---

## Relationship matrix (from the PDF)

| Parent table | Parent column | Relationship | Child table | Child column | Description |
|---|---|---|---|---|---|
| CaseMaster | CaseMasterID | One to Many | Victim | CaseMasterID | One FIR can have multiple victims |
| CaseMaster | CaseMasterID | One to Many | Accused | CaseMasterID | One FIR can have multiple accused persons |
| CaseMaster | CaseMasterID | One to Many | ArrestSurrender | CaseMasterID | One FIR can have multiple arrest/surrender events |
| CaseMaster | CaseMasterID | One to Many | ComplainantDetails | CaseMasterID | One FIR can have multiple complainants |
| CaseMaster | CaseMasterID | One to Many | ActSectionAssociation | CaseMasterID | One FIR can invoke multiple act-sections |
| CaseMaster | CaseMasterID | One to One | Inv_OccuranceTime | CaseMasterID | One FIR has one occurrence time/location record |
| CaseMaster | CaseCategoryID | Many to One | CaseCategory | CaseCategoryID | Many FIRs share the same category |
| CaseMaster | GravityOffenceID | Many to One | GravityOffence | GravityOffenceID | Many FIRs share the same gravity level |
| CaseMaster | CrimeMajorHeadID | Many to One | CrimeHead | CrimeHeadID | Many FIRs share the same major crime head |
| CaseMaster | CrimeMinorHeadID | Many to One | CrimeSubHead | CrimeSubHeadID | Many FIRs share the same crime sub-head |
| CaseMaster | CaseStatusID | Many to One | CaseStatusMaster | CaseStatusID | Many FIRs share the same status |
| CaseMaster | CourtID | Many to One | Court | CourtID | Many FIRs tried in the same court |
| CaseMaster | PolicePersonID | Many to One | Employee | EmployeeID | Many FIRs registered by the same employee |
| ArrestSurrender | AccusedMasterID (via junction) | One to Many | inv_arrestsurrenderaccused | ArrestSurrenderID | One arrest event can link multiple accused via junction |
| inv_arrestsurrenderaccused | ArrestSurrenderID | Many to One | ArrestSurrender | ArrestSurrenderID | Junction links to the arrest/surrender event |
| ArrestSurrender | ArrestSurrenderStateId | Many to One | State | StateID | Many arrest events in the same state |
| ArrestSurrender | ArrestSurrenderDistrictId | Many to One | District | DistrictID | Many arrest events in the same district |
| ArrestSurrender | CourtID | Many to One | Court | CourtID | Accused may be produced before a court |
| ArrestSurrender | IOID | Many to One | Employee | EmployeeID | Many arrests by the same IO |
| ComplainantDetails | OccupationID | Many to One | OccupationMaster | OccupationID | Many complainants share the same occupation |
| ComplainantDetails | ReligionID | Many to One | ReligionMaster | ReligionID | Many complainants share the same religion |
| ComplainantDetails | CasteID | Many to One | CasteMaster | caste_master_id | Many complainants belong to the same caste |
| ActSectionAssociation | ActID | Many to One | Act | ActCode | Many case-sections reference the same act |
| ActSectionAssociation | SectionID | Many to One | Section | SectionCode | Many cases use the same section |
| CrimeSubHead | CrimeHeadID | Many to One | CrimeHead | CrimeHeadID | Multiple sub-heads under one major crime head |
| CrimeHead | CrimeHeadID | One to Many | CrimeHeadActSection | CrimeHeadID | One crime head maps to multiple act-sections |
| Act | ActCode | One to Many | CrimeHeadActSection | ActCode | One act linked to multiple crime heads |
| Act | ActCode | One to Many | Section | ActCode | One act contains multiple sections |
| Court | DistrictID | Many to One | District | DistrictID | Many courts in the same district |
| District | StateID | Many to One | State | StateID | Many districts belong to one state |
| Unit | TypeID | Many to One | UnitType | UnitTypeID | Many units share the same unit type |
| Unit | StateID | Many to One | State | StateID | Many units located in the same state |
| Unit | DistrictID | Many to One | District | DistrictID | Many units belong to the same district |
| Employee | DistrictID | Many to One | District | DistrictID | Many employees posted in the same district |
| Employee | UnitID | Many to One | Unit | UnitID | Many employees assigned to the same unit |
| Employee | RankID | Many to One | Rank | RankID | Many employees hold the same rank |
| Employee | DesignationID | Many to One | Designation | DesignationID | Many employees have the same designation |

### Notes and conventions

- **Tables referenced but not defined in the PDF:** the relationship matrix mentions
  `Inv_OccuranceTime` (one-to-one occurrence time/location per case) and
  `inv_arrestsurrenderaccused` (junction between arrest events and accused). The PDF gives no
  column definitions for them; occurrence time/location already lives on `CaseMaster`
  (`IncidentFromDate`/`IncidentToDate`/`latitude`/`longitude`) and `ArrestSurrender` already
  carries `AccusedMasterID` directly, so the platform does not generate these two tables.
- **GenderID convention** (used consistently for complainants, victims, accused, employees):
  `1` = Male (M), `2` = Female (F), `3` = Transgender (T).
- **ArrestSurrenderTypeID convention:** `1` = Arrest, `2` = Voluntary Surrender.
- **CrimeNo category codes** (first digit, per the PDF examples): `1` = FIR, `3` = UDR,
  `4` = PAR, `8` = Zero FIR.
- **`cstype` codes:** `A` = Chargesheet filed, `B` = False Case, `C` = Undetected.
- **Analytics identity resolution:** `Accused` rows are per-case (as in real CCTNS data). The
  link-analysis pillar resolves the same physical person across cases by (name, gender, age
  cohort) — this entity-resolution step is analytics-side and adds no columns to the schema.
