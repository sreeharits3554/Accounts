# Accounting & Inventory System: Design Proposal

**Company:** Mechotronix (sole proprietorship), Karnataka
**GSTIN:** 29APHPS6234A1ZV (State code 29 = Karnataka; PAN APHPS6234A is the proprietor's PAN)
**Headcount:** about 8 employees, registered for ESI, EPF and TDS (TAN)
**Current system:** Tally Prime

> Note: I could not open www.mechotronix.in from this environment. This design
> assumes a small engineering business that **buys, stocks and sells goods and
> may also bill services or do light assembly**. Tell me if you manufacture
> heavily, work on projects/contracts, or export, and I'll adjust the design.

---

## 1. Recommendation first: build, adopt, or stay?

| Option | Fit for an 8-person GST + ESI/EPF/TDS business | Cost | Risk |
|---|---|---|---|
| **A. Stay on Tally Prime + add-ons** | Very good for accounts and GST. Payroll and inventory are basic. | Low (licence + TSS) | Low |
| **B. Adopt ERPNext + "India Compliance" app** (open source) | Very good. Accounts, GST (e-invoice/e-way bill), stock, BOM, payroll (HRMS), CRM and multi-user web access. | Free to self-host, or a small monthly fee on Frappe Cloud. Implementation help is optional. | Medium (you'll need someone to set it up) |
| **C. Zoho Books + Zoho Inventory + Zoho Payroll** | Good. Cloud-based and easy to use, with GST filing built in. | Monthly subscription per module | Low. Your data sits with the vendor. |
| **D. Build custom software** (this repo) | Can match your workflow exactly. | Highest: development plus ongoing tax-law maintenance | **High.** GST, TDS and labour rules change every year, and every change needs new code. |

**My advice:** at your size, **Option B (ERPNext + India Compliance)** is the best
long-term upgrade. It is modern, web-based and customisable, and you can fully own the data.
If you still want your own system, the rest of this document is the blueprint. It also
works as a checklist for judging any product you consider.

---

## 2. System overview

```
                    ┌──────────────────────────────────────────┐
                    │        Web App (browser / mobile)        │
                    │  Role-based: Owner · Accountant · Stores │
                    │              · Sales · HR/Payroll        │
                    └──────────────┬───────────────────────────┘
                                   │
 ┌───────────┬───────────┬─────────┴───┬────────────┬────────────┬───────────┐
 │ Masters   │ Accounting│ Inventory   │ GST        │ TDS        │ Payroll   │
 │ (parties, │ (vouchers,│ (items,     │ (e-invoice,│ (deduction,│ (EPF, ESI,│
 │ items,    │ ledgers,  │ godowns,    │ e-way bill,│ challans,  │ PT, TDS on│
 │ ledgers)  │ banking)  │ BOM, stock) │ GSTR-1/3B) │ 24Q/26Q)   │ salary)   │
 └───────────┴─────┬─────┴──────┬──────┴─────┬──────┴─────┬──────┴─────┬─────┘
                   └────────────┴─── Double-entry ledger engine ────────┘
                                   │
                         PostgreSQL + audit log + daily backups
```

Every module posts its entries through **one double-entry engine**. For example, a
sales invoice creates ledger lines (Customer Dr / Sales Cr / CGST Cr / SGST Cr) and
stock movements (Item out of Godown). This way the books, stock and GST figures always agree.

---

## 3. Modules

### 3.1 Company & settings
- Company profile: name, address, GSTIN, PAN, TAN, EPF establishment code, ESI code,
  Karnataka Professional Tax registration (PTRC/PTEC), bank accounts, logo.
- Financial year: April to March. Year closing carries balances forward automatically.
- Voucher numbering series for each FY (e.g. `MX/25-26/0001`). GST allows at most 16 characters
  and each number must be unique within the FY.

### 3.2 Chart of accounts (Tally-style groups, so your team feels at home)
```
Capital Account ─ Proprietor's Capital, Drawings
Loans (Liability) ─ Secured / Unsecured Loans
Current Liabilities ─ Sundry Creditors, Duties & Taxes (CGST/SGST/IGST output,
                      TDS payable by section, PF/ESI/PT payable), Provisions
Fixed Assets ─ Plant & Machinery, Computers, Furniture, Vehicles (+ Depreciation)
Current Assets ─ Stock-in-hand, Sundry Debtors, Bank, Cash, Input CGST/SGST/IGST,
                 TDS receivable, Loans & Advances
Income ─ Sales (goods), Service income, Other income
Expenses ─ Purchases, Direct expenses (freight inward, job work),
           Indirect expenses (salary, rent, power, repairs, bank charges)
```

### 3.3 Accounting vouchers
Sales, Purchase, Receipt, Payment, Contra, Journal, Credit Note, Debit Note,
Sales Order, Purchase Order, Delivery Challan, Goods Receipt Note (GRN).

- Bill-wise tracking: match receipts and payments against specific invoices, with ageing (0–30/31–60/61–90/90+).
- Bank reconciliation: import the bank statement (CSV/Excel) and auto-match entries.
- Cost centres (optional): track profit per project, customer or division.
- **MSME 45-day rule:** flag unpaid bills from MSME suppliers older than 45 days
  (Income Tax Act rule 43B(h). Unpaid amounts are disallowed as expenses).

### 3.4 Inventory
- Item master: code, name, HSN/SAC, GST rate, UOM (with alternate units), category,
  make/model, reorder level, minimum stock, standard cost.
- Godowns/locations: main store, workshop, customer site, and a job-work location.
- Batch and serial numbers for machines/components that need warranty tracking.
- Valuation: weighted average (recommended) or FIFO, following AS-2.
- Stock transactions: GRN, delivery, stock transfer, stock adjustment (damage/shortage),
  material issue to jobs, and job-work out/in (ITC-04 register).
- Bill of Materials (BOM) and assembly vouchers, if you assemble panels/machines.
- Reports: stock summary, godown-wise stock, item movement, reorder list,
  slow/non-moving stock, stock ageing, and physical-vs-book reconciliation.

### 3.5 GST (Karnataka, state code 29)
- Tax is chosen automatically from place of supply: **CGST + SGST** inside Karnataka,
  **IGST** for other states.
- HSN/SAC summary on invoices and in GSTR-1 (the number of HSN digits depends on turnover).
- Reverse Charge (RCM): GTA freight, legal fees, etc. Output and input entries are created automatically.
- **E-way bill** for goods movements above ₹50,000. **E-invoice (IRN + QR)** if
  aggregate turnover in any year since 2017-18 exceeded ₹5 crore.
- Returns: GSTR-1 and GSTR-3B data (JSON export), **GSTR-2B reconciliation**
  (match supplier invoices against your purchase register before claiming ITC), GSTR-9 summary.
- ITC register: eligible vs blocked credit (Sec 17(5)), and reversal on non-payment within 180 days.

### 3.6 TDS
- Party master records the TDS nature of payment, rate, threshold, PAN status
  (higher rate if no PAN, or if PAN is not linked to Aadhaar), and lower-deduction certificates.
- Deduction on booking or payment, whichever comes first. The software deducts automatically once thresholds are crossed.
- Common cases for your business: contractors/job work, professional/technical fees,
  rent, commission, purchase of goods over ₹50 lakh, and salary.
- Challan (ITNS 281) tracking with due dates (7th of the next month; 30 April for March),
  quarterly **24Q (salary) / 26Q (others)** return data, and Form 16/16A tracking.
- ⚠️ **The Income-tax Act, 2025 applies from 1 April 2026** and renumbers the TDS
  sections. Keep rates and section codes in an **editable master table**, never hard-coded.
  Check the current codes with your CA.

### 3.7 Payroll (8 employees)
- Employee master: PAN, Aadhaar, UAN, ESI IP number, bank account, date of joining,
  salary structure.
- Monthly attendance and leave, then salary computation and a payslip PDF.
- **EPF:** employee 12%. Employer 12% (3.67% EPF + 8.33% EPS on wages up to ₹15,000),
  plus EDLI and admin charges. Produces the ECR file for the EPFO portal. Due on the 15th.
- **ESI:** applies when gross is ≤ ₹21,000. Employee 0.75%, employer 3.25%. Produces the monthly
  contribution file. Due on the 15th.
- **Karnataka Professional Tax:** slab-based and deducted monthly. Confirm the current slab.
- **TDS on salary:** projected yearly income, choice of new/old regime, flows into 24Q.
- ⚠️ The new **Labour Codes** (in force from November 2025) define "wages" so that
  allowances above 50% of pay count toward PF/ESI/gratuity. Keep the wage-definition rule configurable.
- Salary journal is posted automatically: Salary Dr → PF/ESI/PT/TDS Payable Cr, Bank Cr.
- Gratuity and bonus provisions (optional).

### 3.8 Reports & dashboard
- **Owner dashboard:** cash + bank balance, receivables/payables due this week,
  sales this month vs last month, GST payable, stock value, low-stock alerts.
- Books: Day Book, Ledger, Trial Balance, Profit & Loss, Balance Sheet, Cash Flow.
- Registers: Sales, Purchase, Journal, Cash/Bank books.
- Statutory: GST, TDS, PF/ESI, and a compliance calendar with reminders.
- **Tax audit support:** if turnover exceeds ₹1 crore (₹10 crore when cash
  transactions are ≤ 5%), the system produces the schedules your CA needs for Form 3CD.
- Everything exports to Excel/PDF.

### 3.9 Security & controls
- Users and roles: Owner (all access), Accountant, Stores, Sales, HR.
  Payroll is visible only to Owner and HR.
- **Audit trail:** every create, edit and delete is logged with user and time and cannot be switched off.
- Period lock: once GST returns are filed, entries for that month are locked.
- Approval flow for payments above a set amount.
- Automatic daily backup to a second location (cloud + external disk).

---

## 4. Core data model (simplified)

```
company(id, name, gstin, pan, tan, state_code, fy_start)
ledger(id, name, group_id, gstin, pan, state_code, tds_section_id, is_msme, opening_bal)
account_group(id, name, parent_id, nature[Asset|Liability|Income|Expense])
item(id, code, name, hsn_sac, gst_rate, uom, valuation_method, reorder_level)
godown(id, name)
voucher(id, type, number, date, party_ledger_id, place_of_supply, narration,
        irn, eway_bill_no, status, created_by, created_at)
voucher_line(id, voucher_id, ledger_id, debit, credit, cost_centre_id)      -- Σdr = Σcr
stock_move(id, voucher_id, item_id, godown_id, qty_in, qty_out, rate, batch, serial)
tax_line(id, voucher_id, tax_type[CGST|SGST|IGST|CESS|TDS], rate, taxable, amount)
bill_ref(id, voucher_id, ledger_id, ref_no, amount, due_date)               -- bill-wise
employee(id, name, pan, uan, esi_no, doj, salary_structure_id)
payroll_run(id, month, status) / payslip(id, run_id, employee_id, components_json)
audit_log(id, table, record_id, action, before_json, after_json, user_id, at)
```

## 5. Suggested technology (if building)
- **Backend:** Python (Django) or Frappe framework, with **PostgreSQL**.
- **Frontend:** a web app that works on office PCs and phones. Invoices print in A4/A5 formats.
- **Integrations:** GSP/ASP APIs for e-invoice, e-way bill and GSTR data. Bank statement import.
  WhatsApp/email for sending invoices and payment reminders.
- **Hosting:** a small cloud server (Indian region), or a local office server with cloud backup.

## 6. Moving from Tally
1. Pick a clean cut-over date. **1 April (start of a financial year)** is best.
2. Export masters (ledgers, items, godowns) and closing balances from Tally as Excel/XML.
3. Import them as opening balances: ledger balances, outstanding bills (bill-wise) and stock
   quantity + value per godown.
4. Run both systems in parallel for 1 month and compare the trial balance, GST and stock.
5. Keep Tally read-only for historical years, for audit/assessment reference.

## 7. Phased roadmap
| Phase | Scope | Result |
|---|---|---|
| 1 | Masters, vouchers, GST invoicing, bank, core reports | Replaces daily Tally use |
| 2 | Inventory: godowns, GRN/delivery, batch/serial, reorder, BOM | Stock control |
| 3 | GST returns, GSTR-2B reconciliation, e-invoice/e-way bill, TDS | Compliance |
| 4 | Payroll with EPF/ESI/PT and salary TDS | HR/payroll in the same system |
| 5 | Dashboard, approvals, WhatsApp/email reminders, mobile view | Owner visibility |

---

## 8. Questions to finalise the design
1. What do you mainly do: trading, manufacturing/assembly, service/AMC, or projects? Do you do job work?
2. What was your approximate annual turnover last year? (This decides e-invoicing, tax audit and HSN digits.)
3. How many users need access, and do you have more than one location/godown?
4. Do you sell to other states, or export?
5. Do you want to **own/customise** the software (ERPNext or custom build) or prefer a
   **ready subscription** (Zoho, or staying on Tally)?

*Tax rates, thresholds and due dates above reflect my understanding as of 2026. Have your CA
confirm them before relying on them, and keep them editable in the software.*
