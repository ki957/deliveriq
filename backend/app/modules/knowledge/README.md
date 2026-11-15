# Kitchen Knowledge approval (Task 16C)

- Kitchen Managers can list SHA-keyed DRAFT Kitchen knowledge versions and approve or reject them for their own kitchen.
- Approval and rejection use audited `SECURITY DEFINER` functions; Kitchen Staff and all non-Kitchen roles are denied.
- Approval publishes only matching Kitchen chunks. The DDR-90 Kitchen golden-set endpoint remains blocked until approved cases exist.
- The 90-case benchmark draft is not the DDR-90 golden set. No knowledge is live before KM approval (DDR-46, DDR-122).
