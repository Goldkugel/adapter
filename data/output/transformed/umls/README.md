# UMLS output

`UMLSAdapter.to_csv()` writes the EAV table of the UMLS Metathesaurus here,
as `umls.csv` by default (see `adapter.umls.output_file` in
`config/config.yaml`). The CSV files are not tracked by version control.

## Content

IDs are UMLS CUIs with the prefix `UMLS:` (see `adapter.umls.prefix`),
e.g. `UMLS:C0000005`. Only English, non-suppressed rows (`SUPPRESS = N`)
are used.

| attribute | value | additional | Source file |
|---|---|---|---|
| `label` | String with term type `PT` or `PN`; otherwise the string of the preferred atom (see below) | `source_abbreviation` (SAB) | `MRCONSO.RRF` |
| `synonym` | String with term type `SY` or `AB` | `source_abbreviation` (SAB) | `MRCONSO.RRF` |
| `reference` | Code of the atom in its source vocabulary (CODE) | `source_abbreviation` (SAB) | `MRCONSO.RRF` |
| `definition` | Definition | `source_abbreviation` (SAB) | `MRDEF.RRF` |

Strings with other term types (e.g. `FN`, `MH`, `ET`) produce no synonym
row, but their codes still produce `reference` rows. A concept without a
`PT` or `PN` string gets exactly one label from its preferred atom: the atom
with `TS = P`, `STT = PF` and `ISPREF = Y` (if none has all three, the one
with the most, in that order of importance; ties keep the first in the
file). Duplicate
`(id, attribute, value)` rows are dropped, so when the same string or code
comes from several sources, only the first source abbreviation is kept.

All fields are quoted and separated by `;` (configurable). The
`additional` column is a Python dict literal; read it with
`ast.literal_eval`.
