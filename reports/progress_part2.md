# Part 2 Progress: Backend Comparison & Heading Analysis

## Summary Table
| Sample | Backend | Clauses | Critical | High | Medium | Low | Overall Score | Agreement % |
|---|---|---|---|---|---|---|---|---|
| Sample_Rental_Agreement_Low_Risk.pdf | legalpro | 19 | 0 | 3 | 3 | 0 | 100.0 | 21.1% |
| Sample_Rental_Agreement_Low_Risk.pdf | tfidf | 19 | 0 | 4 | 2 | 0 | 73.84 | 21.1% |
| Sample_Rental_Agreement_Zero_Risk.pdf | legalpro | 19 | 0 | 3 | 3 | 0 | 100.0 | 21.1% |
| Sample_Rental_Agreement_Zero_Risk.pdf | tfidf | 19 | 0 | 4 | 1 | 0 | 62.0 | 21.1% |
| Sample_Rental_Agreement_Zero_Risk_v2.pdf | legalpro | 18 | 0 | 1 | 3 | 0 | 61.78 | 16.7% |
| Sample_Rental_Agreement_Zero_Risk_v2.pdf | tfidf | 18 | 0 | 0 | 1 | 0 | 10.0 | 16.7% |
| Sample_SaaS_Agreement.pdf | legalpro | 21 | 2 | 6 | 6 | 0 | 100.0 | 71.4% |
| Sample_SaaS_Agreement.pdf | tfidf | 21 | 2 | 6 | 8 | 0 | 100.0 | 71.4% |
| Sample_SaaS_Agreement_Low_Risk.pdf | legalpro | 14 | 0 | 4 | 1 | 0 | 98.74 | 42.9% |
| Sample_SaaS_Agreement_Low_Risk.pdf | tfidf | 14 | 0 | 0 | 3 | 0 | 31.71 | 42.9% |
| Sample_SaaS_Agreement_Medium_Risk.pdf | legalpro | 15 | 0 | 3 | 3 | 0 | 100.0 | 46.7% |
| Sample_SaaS_Agreement_Medium_Risk.pdf | tfidf | 15 | 0 | 1 | 3 | 0 | 51.28 | 46.7% |

## SaaS Agreement Disagreements (Sample_SaaS_Agreement.pdf)
- **Sample_SaaS_Agreement-clause-1**: "SOFTWARE-AS-A-SERVICE (SAAS) SUBSCRIPTION AGREEMENT SAM..." | TF-IDF: Effective Dates | LegalPro: Agreements (0.9699)
- **Sample_SaaS_Agreement-clause-4**: "3. Service Levels The Provider shall make the Service a..." | TF-IDF: Payments | LegalPro: Fees (0.9954)
- **Sample_SaaS_Agreement-clause-7**: "6. Customer Data The Customer retains all rights in Cus..." | TF-IDF: Records | LegalPro: General (0.5814)
- **Sample_SaaS_Agreement-clause-14**: "13. Limitation of Liability In no event shall the Provi..." | TF-IDF: Fees | LegalPro: Remedies (0.6061)
- **Sample_SaaS_Agreement-clause-16**: "15. Non-Solicitation and Non-Compete For 12 months afte..." | TF-IDF: Confidentiality | LegalPro: General (0.3855)
- **Sample_SaaS_Agreement-clause-19**: "18. Governing Law and Jurisdiction This Agreement shall..." | TF-IDF: Applicable Laws | LegalPro: Governing Laws (0.9171)

## Heading Analysis
Does `split_into_clauses` keep the section heading (e.g. "8. Governing Law.") inside `clause.text`?
**Yes.** Clause texts preserve the original section numbers and heading lines at the start of the clause string.
