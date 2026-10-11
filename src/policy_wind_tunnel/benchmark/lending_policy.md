# Fictional Retail Lending Eligibility Policy (benchmark v1)

Synthetic demonstration policy. Not based on any real lender or regulation.
All amounts are in rupees. All thresholds are inclusive unless stated.

## L1 Age
The applicant must be at least 21 and at most 65 years old on the application date.
Otherwise the application is rejected (reason AGE).

## L2 Documents
ID proof, address proof and income proof are mandatory.
Self-employed applicants must also provide business proof.
If any mandatory document is missing, the application is INCOMPLETE (reason DOCS) and no other rule is evaluated.

## L3 Income
Salaried applicants: verified monthly income must be at least 25,000.
Self-employed applicants: verified average monthly income over the last 12 months must be at least 35,000
and the business must be at least 24 months old.
Otherwise the application is rejected (reason INCOME).

## L4 Debt-to-income
(Existing monthly obligations + proposed EMI) divided by verified monthly income must not exceed 45%.
Otherwise the application is rejected (reason DTI).

## L5 Loan cap
The loan amount must not exceed 20 times verified monthly income.
Otherwise the application is rejected (reason CAP).

## L6 Credit score
Applied only when L1, L3, L4 and L5 all pass.
- Score missing: REFER to manual review (reason NO_SCORE).
- Score at least 700: APPROVE.
- Score from 650 to 699: REFER to manual review (reason SCORE_REVIEW).
- Score below 650: REJECT (reason SCORE).

## L7 Existing-customer exception
An applicant with a relationship of at least 24 months and no delinquency has both L6 score thresholds lowered by 20 points
(700 becomes 680, 650 becomes 630).

## Evaluation order
L2 first. If L2 passes, L1, L3, L4 and L5 are all evaluated and every failing reason is reported in clause order.
If any of them fails the outcome is REJECT. Otherwise L6 (with L7) decides.
