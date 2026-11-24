# Backend Comparison

| Sample | Backend | Clauses | Critical | High | Medium | Low | Score | Agree % |
|--------|---------|---------|----------|------|--------|-----|-------|----------|
| Sample_Rental_Agreement_Low_Ri | legalpro | 19 | 0 | 3 | 3 | 0 | 100.0 | 21.1% |
| Sample_Rental_Agreement_Low_Ri | tfidf | 19 | 0 | 4 | 2 | 0 | 73.84 | 21.1% |
| Sample_Rental_Agreement_Zero_R | legalpro | 19 | 0 | 3 | 3 | 0 | 100.0 | 21.1% |
| Sample_Rental_Agreement_Zero_R | tfidf | 19 | 0 | 4 | 1 | 0 | 62.0 | 21.1% |
| Sample_Rental_Agreement_Zero_R | legalpro | 18 | 0 | 1 | 3 | 0 | 61.78 | 16.7% |
| Sample_Rental_Agreement_Zero_R | tfidf | 18 | 0 | 0 | 1 | 0 | 10.0 | 16.7% |
| Sample_SaaS_Agreement.pdf | legalpro | 21 | 2 | 6 | 6 | 0 | 100.0 | 71.4% |
| Sample_SaaS_Agreement.pdf | tfidf | 21 | 2 | 6 | 8 | 0 | 100.0 | 71.4% |
| Sample_SaaS_Agreement_Low_Risk | legalpro | 14 | 0 | 4 | 1 | 0 | 98.74 | 42.9% |
| Sample_SaaS_Agreement_Low_Risk | tfidf | 14 | 0 | 0 | 3 | 0 | 31.71 | 42.9% |
| Sample_SaaS_Agreement_Medium_R | legalpro | 15 | 0 | 3 | 3 | 0 | 100.0 | 46.7% |
| Sample_SaaS_Agreement_Medium_R | tfidf | 15 | 0 | 1 | 3 | 0 | 51.28 | 46.7% |

## SaaS Agreement Disagreements

| Clause ID | First 60 chars | TF-IDF Label | LegalPro Label | LP Confidence |
|-----------|----------------|--------------|----------------|---------------|
| Sample_SaaS_Agreement-clause-1 | SOFTWARE-AS-A-SERVICE (SAAS) SUBSCRIPTION AGREEMENT SAM... | Effective Dates | Agreements | 0.9699 |
| Sample_SaaS_Agreement-clause-4 | 3. Service Levels The Provider shall make the Service a... | Payments | Fees | 0.9954 |
| Sample_SaaS_Agreement-clause-7 | 6. Customer Data The Customer retains all rights in Cus... | Records | General | 0.5814 |
| Sample_SaaS_Agreement-clause-14 | 13. Limitation of Liability In no event shall the Provi... | Fees | Remedies | 0.6061 |
| Sample_SaaS_Agreement-clause-16 | 15. Non-Solicitation and Non-Compete For 12 months afte... | Confidentiality | General | 0.3855 |
| Sample_SaaS_Agreement-clause-19 | 18. Governing Law and Jurisdiction This Agreement shall... | Applicable Laws | Governing Laws | 0.9171 |

## Heading Analysis

`split_into_clauses` keeps headings in clause text: **Yes**
