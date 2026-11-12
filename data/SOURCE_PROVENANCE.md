# Source copies — provenance

`data/source/` holds read-only copies of the 21 DeliverIQ source documents (DDR-60).

| Item | Value |
|---|---|
| Origin | Owner's local folder `task1/` (the originals are never modified) |
| Copied | 2026-11-12, byte-for-byte (`cp -a`), files then marked read-only |
| Expected values | `docs/SOURCE_DOCUMENT_INVENTORY.md` §2–3 (SHA-256, bytes, lines), recorded 2026-11-11 |
| Verified by | `backend/app/cli/source_registry.py`; CI job `source-integrity` |
| Excluded | `EIB Data.xlsx` (DDR-61); it was never part of `task1/` |
| Publication | Repository is public by owner decision (2026-11-12). A scan before copying found no emails, phone numbers, API keys or private keys |

## Rules

- Never edit, rename, reformat or delete a file in `data/source/`. Any byte change fails CI.
- A genuine new source version needs an owner-approved inventory update first (new hash recorded), then the copy is replaced in the same PR.
- Hash verification is separate from content validation (`docs/KITCHEN_SOURCE_VALIDATION.md`).
- `kitchen/original/Kitchen_SOP_Manual_Token_Friendly.md` is the only real recipe source. Its recipes import as DRAFT and are never activated in this POC (DDR-09, DDR-50).

## Folder names

On-disk names are authoritative and were not renamed:

| Expected in briefs | Actual folder | Note |
|---|---|---|
| `delivery/` | `deliver/` | Also contains the Management RAG prompt |
| `shared/` | `shareddsah/` | Management Dashboard docs and the Shared AI spec |
| — | `data/` | Seed-data documents |
| — | `phases/` | Phase 1–6 specifications |

## Cited-filename resolution

Documents reference each other with names that don't exist on disk:

| Name cited inside documents | Resolves to (under `data/source/`) |
|---|---|
| `DeliverIQ_Customer_Dashboard_Requirements.md` | `customer/Customer_Dashboard_Requirements.md` |
| `DeliverIQ_Delivery_Agent_Portal_Requirements.md` | `deliver/Delivery_Agent_Portal_Requirements.md` |
| `DeliverIQ_Unified_Management_Dashboard_Requirements.md` | `shareddsah/Management_Dashboard_Requirements.md` |
| `DeliverIQ_Kitchen_SOP_Manual_Token_Friendly.md` | `kitchen/original/Kitchen_SOP_Manual_Token_Friendly.md` |
| `DeliverIQ_Kitchen_SOP_Manual.pdf` | Not available |
| `DeliverIQ_Kitchen_Data_Consolidated.xlsx` | Not available |
| `DeliverIQ_Menu_Ingredient_Recipe_Mapping.xlsx` | Deleted (per product owner) |
| `DeliverIQ_Tandoor_Recipe_Production_Standards.xlsx` | Not available |

`data/DeliverIQ_Generated_POC_Seed_Data (1).md` keeps its space and `(1)` suffix; quote it in scripts.
