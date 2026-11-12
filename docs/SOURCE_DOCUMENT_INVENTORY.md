# DeliverIQ — Source Document Inventory

**Status:** Content inspection complete; SHA-256, size and line count recorded for all 21 files (§2–3). Task 0 implemented (2026-11-12): automated check `backend/app/cli/source_registry.py` reads §2–3 directly; copies in `data/source/` (provenance `data/SOURCE_PROVENANCE.md`); CI job `source-integrity`; ADRs in `docs/adr/`. DB write to `ops.source_registry` follows in Task 5 (see §5). `EIB Data.xlsx` excluded (DDR-61)
**Prepared:** 11 November 2026
**Source root:** `/home/k/Downloads/task1/` (read-only; no file renamed, moved, modified or deleted)

---

## 1. Discovery summary

| Item | Result |
|---|---|
| Folders found | `customer/`, `kitchen/`, `kitchen/original/`, `deliver/`, `shareddsah/`, `data/`, `phases/` |
| Portal/shared Markdown files expected | 12 |
| Portal/shared Markdown files found | 12 |
| Kitchen SOP | 1 (`kitchen/original/Kitchen_SOP_Manual_Token_Friendly.md`) |
| Additional files found | 8 (`data/` × 2, `phases/` × 6) |
| Total files | 21 |
| Missing/unreadable files | None in `task1/`. Excel ingredient mapping and SOP PDF are **not present** (deleted / never supplied) |
| Content read status | All 21 files read end-to-end |
| SHA-256 hash status | Recorded for all 21 files on 2026-11-11 (§2–3) |

### 1.1 Folder-name resolution

The task brief described a different structure. The actual on-disk names are authoritative and were **not** renamed.

| Brief expected | Actual folder | Note |
|---|---|---|
| `customer/` | `customer/` | Match |
| `kitchen/` | `kitchen/` | Match |
| `delivery/` | `deliver/` | Different name; also contains the **Management** RAG prompt |
| `shared/` | `shareddsah/` | Different name; contains Management Dashboard docs and Shared AI spec |
| — | `data/` | Not in brief; seed-data documents |
| — | `phases/` | Not in brief; Phase 1–6 specifications |

### 1.2 Cited-filename resolution

Documents reference each other using names that do not exist on disk. Use this table to resolve references. Do not rename source files.

| Name cited inside documents | Resolves to (actual path) | Cited by |
|---|---|---|
| `DeliverIQ_Customer_Dashboard_Requirements.md` | `customer/Customer_Dashboard_Requirements.md` | Customer Dashboard AI Master Prompt |
| `DeliverIQ_Delivery_Agent_Portal_Requirements.md` | `deliver/Delivery_Agent_Portal_Requirements.md` | Delivery Agent AI Master Prompt |
| `DeliverIQ_Unified_Management_Dashboard_Requirements.md` | `shareddsah/Management_Dashboard_Requirements.md` | Management Dashboard AI Master Prompt |
| `DeliverIQ_Kitchen_SOP_Manual.pdf` | **Not available** | Kitchen SOP header, ETL spec, Business brief |
| `DeliverIQ_Kitchen_SOP_Manual_Token_Friendly.md` | `kitchen/original/Kitchen_SOP_Manual_Token_Friendly.md` | ETL spec, Business brief, Harness blueprint |
| `DeliverIQ_Kitchen_Data_Consolidated.xlsx` | **Not available** | ETL spec, Business brief |
| `DeliverIQ_Menu_Ingredient_Recipe_Mapping.xlsx` | **Deleted** (per product owner) | ETL spec, Business brief |
| `DeliverIQ_Tandoor_Recipe_Production_Standards.xlsx` | **Not available** | ETL spec, Business brief |

---

## 2. File inventory — portal and shared documents (12)

| # | Relative path | Portal | Read | Bytes | Lines | SHA-256 |
|---:|---|---|---|---:|---:|---|
| 1 | `customer/Customer_Dashboard_Requirements.md` | Customer | Complete | 10990 | 279 | `68bfc821daff0182afcad6fa65d91159534e5e7b39e45c923d320e248b04292e` |
| 2 | `customer/Customer_Dashboard_AI_Master_Prompt.md` | Customer | Complete | 11308 | 269 | `85fefbe216f9f864593f3a54f7fee428aa7aa35f4e653e42737815263fd252ff` |
| 3 | `customer/Customer_RAG_AI_Master_Prompt.md` | Customer AI | Complete | 53787 | 1345 | `5583bf365808e0ae97d3d04a3b93c7cf7ed4c4c14054e85dba67f9d3be7048ad` |
| 4 | `kitchen/Kitchen_Portal_Requirements.md` | Kitchen | Complete | 19734 | 412 | `4d2c61959df1efa2808a8848008e331d444ca662a1db1c66a5d8247a746d0234` |
| 5 | `kitchen/Kitchen_Portal_AI_Master_Prompt.md` | Kitchen | Complete | 13773 | 294 | `c073d201e0bdbd36f0d0ad50435effa57d01df1801c5dacaff6b530d45a802dd` |
| 6 | `kitchen/Kitchen_RAG_AI_Master_Prompt.md` | Kitchen AI | Complete | 63047 | 1519 | `7e6d6ff135f53c092fdc3cbc0192d93e21df630befb34abedba7ce7a17229c02` |
| 7 | `deliver/Delivery_Agent_Portal_Requirements.md` | Delivery | Complete | 8885 | 155 | `be286a297f0452b6ee3cecc3699258e493844d7f2b9021c6771e83427d96a345` |
| 8 | `deliver/Delivery_Agent_AI_Master_Prompt.md` | Delivery | Complete | 9378 | 141 | `173865e253d630071c9cc4deec67191686a5af08ce2b712bd0b8d440f51b0d9f` |
| 9 | `deliver/DeliverIQ_Management_RAG_AI_Master_Prompt.md` | **Management AI** (misplaced folder) | Complete | 55842 | 1462 | `7c235cc08eb57817f10b92c52ae3eff36bfa24a9af94f15dbe77e485e9a42a64` |
| 10 | `shareddsah/Management_Dashboard_Requirements.md` | Management | Complete | 15900 | 340 | `ffaa40ada71cebaaecf9f59b7a5db2249ea047a10dbbb7d63bec1797761c8293` |
| 11 | `shareddsah/Management_Dashboard_AI_Master_Prompt.md` | Management | Complete | 9224 | 201 | `5edd049aa55673be120590293e27f2cbaa0617195875259812b2e3aaa88be8bd` |
| 12 | `shareddsah/DeliverIQ_Shared_AI_Infrastructure_Master_Specification.md` | Shared AI | Complete | 21598 | 510 | `51c9603ae803fd765018ddded8aec805046c08908eb26cc4a1aadcc21cef8414` |

## 3. File inventory — kitchen source and additional files (9)

| # | Relative path | Type | Read | Bytes | Lines | SHA-256 |
|---:|---|---|---|---:|---:|---|
| 13 | `kitchen/original/Kitchen_SOP_Manual_Token_Friendly.md` | Kitchen recipe source of truth | Complete | 106671 | 1599 | `7ee63f622758d0e0cdbd1396a50485b71e00d9265b5f74501dc6b3e4bfc19211` |
| 14 | `data/DeliverIQ_Minimum_Required_Data_and_Synthetic_Seed_Dataset.md` | Seed-data requirements | Complete | 19957 | 454 | `2d8e45c155b29d715339f83a16aa770e462d60ae08db4433cc15eef5838387f3` |
| 15 | `data/DeliverIQ_Generated_POC_Seed_Data (1).md` | Generated seed fixtures | Complete | 12716 | 295 | `b118ec523605dbbb1e34bce3a86635cb32a6c2e680148bc39434e41786cfbdaa` |
| 16 | `phases/DeliverIQ_Phase_1_Technical_Discovery_and_Architecture_Validation.md` | Phase spec | Complete | 36205 | 838 | `1ded990a0ecb570c3a16d096c5a2c5a771a4aa38bebc232a8678599d7930615e` |
| 17 | `phases/DeliverIQ_Phase_2_Data_Architecture_and_Backend_Contracts.md` | Phase spec | Complete | 38864 | 1075 | `53a9685dbc442cfc74840944888786c4c7f3322be2b5c6bc610e401dbeeb331f` |
| 18 | `phases/DeliverIQ_Phase_3_Implementation_Planning_and_Engineering_Foundation.md` | Phase spec | Complete | 32424 | 908 | `40e928b4291409fbcd10103d714087bd88364a35404e8a6f463e77a1abce3ee2` |
| 19 | `phases/DeliverIQ_Phase_4_Engineering_Foundation_and_Core_Platform_Implementation.md` | Phase spec | Complete | 28355 | 836 | `c9134cee7f800a96c416ce503902110a79a01c658e52e9bc724b0e0d5127fc2d` |
| 20 | `phases/DeliverIQ_Phase_5_Shared_AI_Infrastructure_Implementation.md` | Phase spec | Complete | 27819 | 865 | `8dfdbfbb49de2d23d0c9ec771f57af10512c626e3ef7048147dc0b1a33166d9a` |
| 21 | `phases/DeliverIQ_Phase_6_Portal_Specific_AI_Harness_and_RAG_Integration.md` | Phase spec | Complete | 27116 | 753 | `72382adb9e0d2c658c0f83c52a1d76aa6d65a376b7627cd1d0f5a8ab6adec5fa` |

Hashes recorded 2026-11-11 with `sha256sum`; sizes with `stat -c %s`; lines with `wc -l` (newline count). Files were only read.

Note: file 15 contains a space and parentheses in its name (`(1)`), which suggests a browser duplicate download. Preserve the name; quote it in scripts.

## 4. Prior planning documents (outside `task1/`)

These were read earlier in this session and remain inputs. Not part of the 12-file verification set.

| Path | Read status | Role |
|---|---|---|
| `/home/k/Downloads/Harness_Engineering_Architecture_and_End_to_End_Build_Blueprint.md` | Read through §17 (definition of done partially) | 14-phase roadmap; **older consolidated design spec** (palettes) |
| `/home/k/Downloads/Business_Context_Technical_Briefing_and_Claude_Code_Plan.md` | Read through §12 (Part C onward supplied via chat) | Business rules |
| `/home/k/Downloads/ETL_ELT_Architecture_and_Workflow_Specification.md` | Complete | Data engineering contract (DE-0…DE-11) |
| `/home/k/Downloads/Requirements_and_Installation_Specification.md` | Read through §17 (§18–20 supplied via chat) | Environment/install baseline |
| `/home/k/Downloads/EIB Data.xlsx` | **Not inspected** | Excluded from DeliverIQ (DDR-61) unless relevance is established |

## 5. Hash verification

Hashes, byte sizes and line counts were computed once on 2026-11-11 from the exact files under `/home/k/Downloads/task1/` and recorded in §2–3. Commands used (read-only):

```bash
cd /home/k/Downloads/task1
find . -type f -print0 | sort -z | xargs -0 sha256sum
# size and lines per file: stat -c %s ; wc -l
```

This is hash **recording**, kept separate from content validation (`KITCHEN_SOURCE_VALIDATION.md`). Approved read-only copies committed to the repository are hash-verified against these values in CI (DDR-60). Task 0 turned this into an automated, re-runnable check: `PYTHONPATH=backend python -m app.cli.source_registry --root data/source --inventory docs/SOURCE_DOCUMENT_INVENTORY.md`. It parses the tables in §2–3, compares SHA-256, bytes and lines, reports missing and unlisted files, and exits non-zero on any difference. Writing each result to `ops.source_registry` is added with the pipeline framework (Task 5). **The tables in §2–3 are machine-read: keep their column order and backtick formatting.**

---

## 6. Requirements extracted per document

Requirement IDs refer to `PORTAL_REQUIREMENTS_MATRIX.md`. "Plan task" refers to `DELIVERIQ_EXECUTION_PLAN.md`.

| # | Document | Key requirements extracted | Depends on | Plan task(s) | Incorporated |
|---:|---|---|---|---|---|
| 1 | Customer_Dashboard_Requirements | Browse after location; OTP before order; 4 km/6 km; ₹500 min; 30-min price protection; filters (price, veg, spice, popularity); free customization; cart persistence; UPI/card/COD sim; 9 customer statuses + 3 terminal; reviews; support tickets; Palette B; navigation; CD-01…CD-18 | Kitchen (customization, availability), Delivery (tracking), Management (coupons, moderation) | 4, 6, 7, 9, 11, 17 | Yes |
| 2 | Customer_Dashboard_AI_Master_Prompt | Inputs to collect (logo, font, imagery, Add behaviour, 250-char limit); no chatbot UI until all dashboards done; responsive breakpoints; mock-vs-real honesty | #1 | 4, 6, 21 | Yes |
| 3 | Customer_RAG_AI_Master_Prompt | Customer-only harness; source-of-truth matrix (live API vs RAG); allowlisted tools; mandatory filters; abstention; allergen caution; cross-portal tests; feature flag | #12 | 16, 17 | Yes |
| 4 | Kitchen_Portal_Requirements | KM/KS permission matrix; Normal/Busy/Paused; capacity; FIFO; order & item statuses; recipe pinning; reserve/deduct/release; shortage → dish dependency; RM approval; agent pickup = Handed Over; Kitchen palette; KP-01…KP-24 | #13, #10 | 3, 5, 8, 11 | Yes |
| 5 | Kitchen_Portal_AI_Master_Prompt | Stage A–E gated workflow; 7 screens; KDS primary/tablet secondary; status colours; no decorative controls | #4 | 4, 8, 21 | Yes |
| 6 | Kitchen_RAG_AI_Master_Prompt | Read-only Kitchen copilot; recipe-version-aware retrieval; Staff vs Manager tools; food-safety abstention; prohibited tools | #12, #4, #13 | 16 | Yes |
| 7 | Delivery_Agent_Portal_Requirements | Hybrid assignment; one active delivery; 60 s; masked phone; pickup → tracking; OTP ×3; 5-min wait; failure approval; GPS 3–5 s; OSM/Leaflet/OSRM; Palette A; DA-01…DA-25 | #10 | 9, 11 | Yes |
| 8 | Delivery_Agent_AI_Master_Prompt | 11 screens; mobile-first; PWA validation; simulated GPS labelling; no Google Maps; inputs to ask | #7 | 9, 21 | Yes |
| 9 | DeliverIQ_Management_RAG_AI_Master_Prompt | RM/CA scope; four knowledge categories; KPI definitions in RAG, values via API; RM/CA tool lists; prohibited tools | #10, #12 | 15 | Yes |
| 10 | Management_Dashboard_Requirements | RM/CA capability table; staff lifecycle; dish approval; refunds; promotions; reports + CSV; YAML; audit; Management palette; 20 acceptance criteria | #4, #7, #1 | 10, 13 | Yes |
| 11 | Management_Dashboard_AI_Master_Prompt | Gate A/B/C; module list; minimum tests; open decisions list | #10 | 10, 21 | Yes |
| 12 | DeliverIQ_Shared_AI_Infrastructure_Master_Specification | LLM gateway contract; embedding service; ingestion lifecycle states; per-portal schemas & DB roles; observability; evaluation; failure table | #3, #6, #9 | 15 | Yes |
| 13 | Kitchen_SOP_Manual_Token_Friendly | 104 recipe cards; global controls; inventory command SOP (excluded from MVP); release checklist | — | 5, 16 | Yes (see `KITCHEN_SOURCE_VALIDATION.md`) |
| 14 | Minimum_Required_Data_and_Synthetic_Seed_Dataset | 20 master-data groups (P0/P1); sample seeds; data NOT to collect; validation checklist; owner inputs | #13 | 3, 5, 14 | Yes |
| 15 | Generated_POC_Seed_Data (1) | Concrete seed IDs; MOCK_OTP adapter; config keys; payment simulator scenarios; 4 order scenarios; RAG registry drafts | #14 | 3, 4, 7 | Yes |
| 16 | Phase 1 | Repo audit; gap classification; ADR-001…014; MongoDB/OpenRouter questions; event candidates | Prior docs | 1 | Yes |
| 17 | Phase 2 | Domain ownership; entity catalogue; transaction contracts; idempotency list; RBAC matrix; API/event templates; retention | #16 | 3, 4, 7 | Yes |
| 18 | Phase 3 | Dependency order; vertical slices; epics E01–E18; milestones M0–M9 | #16, #17 | All | Yes |
| 19 | Phase 4 | Core platform build; workstreams A–N; E2E scenarios; gates P4.0–P4.10 | #18 | 2–11 | Yes |
| 20 | Phase 5 | Shared AI; Groq/OpenRouter options A/B/C; embedding benchmark; gates P5.0–P5.10 | #19 | 15 | Yes |
| 21 | Phase 6 | Portal harness contract; per-portal tools and tests; gates P6.0–P6.8 | #20 | 15–17 | Yes |

## 7. Cross-document conflicts and duplications found

Detailed decisions are in `DESIGN_DECISION_REGISTER.md`. Summary:

| ID | Conflict | Documents |
|---|---|---|
| X-01 | Customer palette A in older docs vs B in portal-specific docs | Harness blueprint §10.2, data #14 §5, data #15 §15 vs #1, #2 |
| X-02 | Palette A assigned to Customer in older docs, to Delivery in portal-specific docs | Same as X-01 vs #7, #8 |
| X-03 | Plain HTML/CSS / "do not assume framework" vs approved React/Vite/Tailwind/shadcn | #2, #5, #8, #11 vs owner decision |
| X-04 | SOP AI stock-deduction command vs read-only Kitchen AI | #13 vs #4, #6 |
| X-05 | SOP lots/FEFO/expiry vs Kitchen exclusion of expiry/batch tracking | #13 vs #4 §7.4 |
| X-06 | Customer-unavailable wait "configured period" vs "five minutes" | #1, #2 vs #7, #10, #11, #15 |
| X-07 | Order status vocabularies differ per portal | #1, #4, #7, #19, Harness blueprint §8.1 |
| X-08 | MongoDB "to verify" in Phase 1 vs excluded in baseline | #16 vs Requirements spec §1.2 |
| X-09 | Groq vs OpenRouter relationship unresolved | #16, #20 |
| X-10 | Phase 6 AI order Customer→Kitchen→Management vs owner order Management→Kitchen→Customer | #21 vs owner decision |
| X-11 | Seed IDs differ: `REG-001`/`KIT-001` vs `REG-CHN-001`/`KIT-CHN-001` | #14 vs #15 |
| X-12 | Delivery fee ₹30 sample vs "not generated, awaiting confirmation" | #14 vs #15 |
| X-13 | Acceptance timeout 5 min test default vs not fixed | #14 vs #15 |
| X-14 | Both seed docs assume the Excel ingredient mapping exists | #14, #15 vs owner (deleted) |
| X-15 | Schema naming: per-domain schemas (Phase 2) vs `app/raw/staging/analytics/...` (ETL spec) | #17 vs ETL spec §3.2 |
| X-16 | MinIO / Parquet / DuckDB listed as baseline in Management docs; optional elsewhere | #10 §14, #11 vs Requirements spec |
| X-17 | Management RAG prompt stored in `deliver/` folder | #9 |
| X-18 | Customer chatbot deferred "until all five dashboards completed" vs Customer RAG prompt reads as implementable now | #1, #2 vs #3 |

Duplicated requirements (consistent across documents; consolidate in matrix, do not re-implement): one active delivery, 60 s timeout, OTP ×3, 4 km/6 km, ₹500, payment/fulfilment separation, recipe pinning, reserve/deduct/release, RM dish approval, read-only AI, cross-portal isolation, deny-by-default.

## 8. Discovery completion statement

- Content inspection of all 21 files in `task1/`: **complete**.
- SHA-256, size and line count: **recorded** for all 21 files (§2–3).
- Source discovery is complete as a documentation activity.
- Task 0 is **not complete**: automated registry script, `ops.source_registry`, committed read-only copies, CI hash check (DDR-60) and ADRs remain. `EIB Data.xlsx` is excluded (DDR-61).
