# Known limitations

The POC is a portfolio demo. These source decisions remain open or out of scope:

| DDR | POC behaviour |
|---|---|
| DDR-06 | The food-card Add interaction remains as currently implemented; final add/customize choice is open. |
| DDR-08 | A placeholder wordmark and neutral brand wording stand in for final branding. |
| DDR-15 | Background geolocation is not implemented; location is collected only through the existing foreground flow. |
| DDR-32 | Only labelled `TEST –` menu data is orderable; real SOP dish data and prep/allergen details are not supplied, and no SOP recipe is activated (DDR-50). |
| DDR-33 | Prepared-component batch recipes and buy-vs-make composition remain unresolved in the SOP review queue. |
| DDR-34 | Ambiguous ingredient names and alternates remain unresolved in the SOP review queue. |
| DDR-35 | MENU008/MENU057 remains a quarantined duplicate candidate. |
| DDR-36 | MENU001–MENU012 category assignments remain unconfirmed in the SOP review queue. |
| DDR-39 | The demo kitchen uses a labelled synthetic address and coordinates. |
| DDR-40 | OTP uses a local/test mock adapter; no SMS provider or India DLT delivery is configured. |
| DDR-41 | Lost-mobile recovery safeguards are not finalized; the POC has no production recovery workflow. |
| DDR-42 | Kitchen capacity, Busy mode, acceptance timeout, delay and low-stock thresholds use labelled test defaults. |
| DDR-43 | GPS sampling interval is not finalized; demo tracks are synthetic. |
| DDR-44 | Exceptional refunds remain disabled; KPI/accounting definitions, audit retention/export, and YAML editing/upload are unresolved. |
| DDR-47 | Neutral “image unavailable” states stand in for approved reference imagery. |
| DDR-49 | This POC demonstrates workflows only; production-only blockers remain limitations. |
| DDR-50 | The supplied SOP remains the only real recipe source; review and reconciliation exist, but no SOP recipe is activated. |

K3 Management knowledge ingestion is not implemented; there is no Management RAG pipeline in this POC.

## Owner-pending work

- Customer and Management DRAFT knowledge and golden sets await CA approval; Kitchen DRAFT knowledge and golden sets await KM approval in the app. No draft is approved by this handover.
- The Customer Assistant UI remains gated by CD-18.
- Task 21's manual keyboard and screen-reader pass remains for the owner.
