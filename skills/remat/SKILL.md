---
description: >
  Use this skill when the user asks about RE-Mat data, wants to search or explore
  experimental datasets on the RE-Mat Clowder platform, or asks about materials
  chemistry data. Invoke before querying any Clowder MCP tool to load space schemas,
  field paths, and search strategy context.
---

# RE-Mat Clowder Instance — Context & Usage Guide

You are working with the **RE-Mat** installation of Clowder, a materials science data
management platform used for storing and querying experimental datasets.

---

## Instance Overview

RE-Mat has three spaces:

- **DSC Cure Kinetics** — DSC experiments on polymer formulations (cure enthalpy, peak temperature)
- **Front Velocities** — FROMP experiments measuring front velocity and maximum temperature
- **DSC Post Cures** — DSC measurements on post-cured FROMP parts (Tg, residual enthalpy)

---

## Searching in RE-Mat

`search_in_space` requires a `space_id`. Use the following rules:

- **Space name given** → call `find_space_by_name(name)` to get the space ID, then search.
- **No space specified** → call `list_spaces`, then call `search_in_space` for each space and aggregate results.

Never assume a space ID. Always resolve it from the name at runtime.

### Restricting search to a field

Pass the `field` argument to narrow results, e.g.:

```
field = "inputs.catalysts.catalyst-inputs[].name"
query = "Grubbs 2nd generation"
```

### Discovering field names

Call `get_metadata_fields(space_id)` to get a sampled map of field paths → example values,
then use those paths as the `field` argument in `search_in_space`.

---

## Recommended Workflow

1. `list_spaces` → find the space ID for the area of interest
2. `get_metadata_fields(space_id)` → discover available field paths and example values
3. `search_in_space(query, space_id, field=...)` → find matching datasets
4. `get_dataset_metadata(dataset_id)` → read full metadata for a dataset
5. `get_dataset_files(dataset_id)` → list raw files if needed

---

## Space: DSC Cure Kinetics

Datasets capture differential scanning calorimetry (DSC) experiments on polymer formulations.

### Metadata Schema

**Top-level**
- `Batch ID`

**Procedure** (`procedure.general.*`)
- `Operator Initials`, `mix_date`, `mix_time`, `storage_conditions`, `mixing_type`

**Input materials** (`inputs.*`)
- `inputs.monomers.monomer-inputs[].name` — e.g. `"DCPD"`, `"ENB"`
- `inputs.monomers.monomer-inputs[].mass (g)`, `.moles`, `.mol%`
- `inputs.catalysts.catalyst-inputs[].name` — e.g. `"Grubbs 1st generation"`, `"Grubbs 2nd generation"`, `"Grubbs 3rd generation"`
- `inputs.catalysts.catalyst-inputs[].ppm`
- `inputs.inhibitors.inhibitor-inputs[].name` — e.g. `"DHF"`, `"BHT"`, `"ionox"`
- `inputs.inhibitors.inhibitor-inputs[].ppm`
- `inputs.solvents.solvent-inputs[].name`

**DSC Instrument** (`DSC Procedure.*`)
- `DSC Procedure.Experiment Type`, `.Ramp rate (°C/min)`, `.Temperature range (°C)`
- `DSC Procedure.Sample Name`, `.Sample mass (mg)`

**Analysis** (`Analysis.*`)
- `Analysis.Enthalpy (normalized)(J/g)`, `.Peak temperature (°C)`, `.Onset x (°C)`

### Useful Query Terms

| Category         | Example values                                                  |
| ---------------- | --------------------------------------------------------------- |
| Monomers         | `DCPD`, `ENB`                                                   |
| Catalysts        | `Grubbs`, `G1`, `G2`, `G3`, `1st generation`, `2nd generation` |
| Inhibitors       | `DHF`, `BHT`, `ionox`, `inert`                                  |
| Experiment type  | `DSC`, `cure kinetics`                                          |
| Units / ratios   | `ppm`, `mol%`                                                   |
| Batch / operator | use specific batch ID or operator initials                      |

---

## Space: Front Velocities

Datasets capture FROMP experiments — measuring front velocity, maximum temperature, and
geometry for various monomer/catalyst/inhibitor formulations under thermal, chemical, or
photo-controlled initiation.

### Metadata Schema

**Top-level**
- `Batch ID`

**FROMP Measurements** (`FROMP Measurements.*`)
- `FROMP Measurements.Measured frontal velocity (mm/s)`
- `FROMP Measurements.Measured frontal velocity with light exposure (mm/s)`
- `FROMP Measurements.Measured maximum temperature (°C)`
- `FROMP Measurements.Type of front` — e.g. `"SPIN"`, `"LINEAR"`

**Procedure** (`procedure.general.*`)
- `procedure.general.Operator Initials`
- `procedure.general.Mix Date and Time`, `.Polymerization Date and Time`
- `procedure.general.Initiation method` — `"THERMAL"` or `"CHEMICAL"`
- `procedure.general.Photocontrol?` — `"YES"` or `"NO"`
- `procedure.general.Geometry - Select from library` — e.g. `"TUBE-2"`, `"SNL-1"`, `"TUBE-3"`
- Dimensions: `.Diameter (mm)`, `.Tube length (mm)`, `.Thickness (mm)`, `.Resin height (mm)`

Initiation-specific sub-schemas (only one present per dataset):
- `procedure.thermal initiation.*` — heat source (e.g. `"RESISTIVE WIRE"`), current/voltage, induction time
- `procedure.chemical initiation.*` — initiator catalyst + solvent (e.g. GC-3 in THF), concentration
- `procedure.photo control.*` — wavelength (nm), intensity (W/mm²), exposure duration, preirradiation flag

**Input materials** (`inputs.*`)
- `inputs.monomers.monomer-inputs[].name` — e.g. `"COD"`, `"ENB"`
- `inputs.monomers.monomer-inputs[].Moles`, `.Monomer mol%`
- `inputs.catalysts.catalyst-inputs[].name` — e.g. `"GC-2"`, `"Grubbs Catalyst gen-2 (GC2 - M207)"`
- `inputs.catalysts.catalyst-inputs[].Monomer:Catalyst molar ratio`
- `inputs.inhibitors.inhibitor-inputs[].name` — e.g. `"TBP"`, `"Tributyl phosphite (TBP)"`
- `inputs.inhibitors.inhibitor-inputs[].Inhibitor:Catalyst molar ratio`

### Useful Query Terms

| Category           | Example values                                                                |
| ------------------ | ----------------------------------------------------------------------------- |
| Monomers           | `COD`, `ENB`, `Ethylidene Norbornene`                                         |
| Catalysts          | `GC2`, `GC-2`, `GC-3`, `Grubbs`, `gen-2`, `gen-3`, `M204`, `M207`           |
| Inhibitors         | `TBP`, `Tributyl phosphite`                                                   |
| Initiation method  | `THERMAL`, `CHEMICAL`                                                         |
| Photocontrol       | `photocontrol`, `light exposure`, `365 nm`, `preirradiation`                  |
| Front type         | `SPIN`, `LINEAR`                                                              |
| Geometry           | `TUBE`, `SNL`, `tube`, `channel`                                              |
| Heat source        | `RESISTIVE WIRE`, `SOLDERING IRON`, `Kanthal`                                 |
| Chemical initiator | `THF`, `tetrahydrofuran`, `GC-3`                                              |
| Operators          | use specific operator initials (e.g. `ACC`, `DRD`, `AC`)                     |
| Batch / date       | use specific batch ID or ISO date                                             |

---

## Space: DSC Post Cures

Datasets capture DSC measurements on post-cured polymer samples (primarily FROMP-polymerized
parts). Key outputs are glass transition temperature (Tg) and residual enthalpy.

### Metadata Schema

**Top-level**
- `Batch ID`

**DSC Instrument** (`DSC Procedure.*`)
- `DSC Procedure.Experiment Type` — e.g. `"LERK_COD_ENB_POST_CURE"`, `"LMD_DCPD_POST_CURE"`
- `DSC Procedure.Operator`, `.Run Date`
- `DSC Procedure.Sample Name`, `.Sample Mass (mg)`
- `DSC Procedure.Ramp rate (°C/min)`, `.Ramp Min Temp (°C)`, `.Ramp Max Temp (°C)`
- `DSC Procedure.Instrument Name`, `.Instrument Type`, `.Serial Number`

**Analysis** (`Analysis.*`)
- `Analysis.Glass transition temperature` — Tg (°C)
- `Analysis.Enthalpy (normalized)(J/g)` — residual cure enthalpy
- `Analysis.Peak temperature (°C)`, `.Onset x (°C)`
- `Analysis.Max Heat Flow`, `.Min Baseline Temp`, `.Max Baseline Temp`

**FROMP Measurements** (`FROMP Measurements.*`) — present when sample was produced via FROMP
- `FROMP Measurements.Measured frontal velocity (mm/s)`
- `FROMP Measurements.Measured maximum temperature (°C)`
- `FROMP Measurements.Type of front` — e.g. `"SPIN"`, `"LINEAR"`

**Procedure** (`procedure.general.*`)
- `procedure.general.Operator Initials`
- `procedure.general.Mix Date and Time`, `.Polymerization Date and Time`
- `procedure.general.Type of polymerization` — e.g. `"FROMP"`, `"NONE"`
- `procedure.general.Initiation method` — `"THERMAL"`, `"CHEMICAL"`, or `"NONE"`
- `procedure.general.Geometry - Select from library` — e.g. `"MOLD-1"`, `"SCIN-VIAL"`, `"NONE"`
- `procedure.general.Post Cure Sampling Location` — e.g. `"Bulk"`
- Dimensions: `.Thickness (mm)`, `.Resin height (mm)`, `.Total width (mm)`, `.Total height (mm)`

**Input materials** (`inputs.*`)
- `inputs.monomers.monomer-inputs[].name` — e.g. `"COD"`, `"ENB"`, `"Dicyclopentadiene (DCPD)"`
- `inputs.monomers.monomer-inputs[].Moles`, `.Monomer mol%`
- `inputs.catalysts.catalyst-inputs[].name` — e.g. `"GC-2"`, `"Grubbs Catalyst gen-2 (GC2 - M202)"`
- `inputs.catalysts.catalyst-inputs[].Monomer:Catalyst molar ratio`
- `inputs.inhibitors.inhibitor-inputs[].name` — e.g. `"TBP"`, `"diethoxy(phenyl)phosphane (CAS 1638-86-4)"`
- `inputs.inhibitors.inhibitor-inputs[].Inhibitor:Catalyst molar ratio`
- `inputs.solvents.solvent-inputs[].name` — e.g. `"Phenyl Cyclohexane"`
- `inputs.solvents.solvent-inputs[].Solvent concentration (mL/g)`

### Useful Query Terms

| Category          | Example values                                                               |
| ----------------- | ---------------------------------------------------------------------------- |
| Monomers          | `COD`, `ENB`, `DCPD`, `Dicyclopentadiene`                                   |
| Catalysts         | `GC-2`, `Grubbs`, `gen-2`, `M202`                                           |
| Inhibitors        | `TBP`, `diethoxy(phenyl)phosphane`, `1638-86-4`, `490023-37-5`              |
| Solvents          | `Phenyl Cyclohexane`                                                         |
| Experiment type   | `POST_CURE`, `COD_ENB_POST_CURE`, `DCPD_POST_CURE`                          |
| Polymerization    | `FROMP`, `NONE`                                                              |
| Initiation method | `THERMAL`, `CHEMICAL`, `NONE`                                                |
| Geometry          | `MOLD-1`, `SCIN-VIAL`                                                        |
| Sampling location | `Bulk`                                                                       |
| Operator / batch  | use specific operator initials (e.g. `LERK`, `RC`, `AC`) or batch ID       |
