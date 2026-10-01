# Supplier invoice processing

Our finance shared-service centre receives about 40,000 supplier invoices a month as PDFs, by email and through a supplier portal. Today 25 accounts-payable clerks key them into SAP by hand.

- Invoices are uploaded as they arrive. An extraction job reads each PDF with OCR and a large language model, matches it to the purchase order and goods receipt in SAP S/4HANA through its OData APIs, and flags mismatches for a clerk.
- Volumes are bursty: most invoices arrive in the last five days of the month, so the pipeline should scale to zero in between.
- 300 finance employees in the UK and Ireland use a web dashboard for exceptions; invoices over 10,000 EUR need a second approver (a multi-step approval workflow).
- Invoices and the audit trail of every change must be kept for 10 years for tax and SOX audits. Personal data on invoices, such as names and bank details, must be protected.
- 4 developers maintain it. Budget is about $2,500 per month.
