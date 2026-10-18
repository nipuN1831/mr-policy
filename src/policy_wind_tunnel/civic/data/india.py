from policy_wind_tunnel.civic.data.india_mps import LOK_SABHA_18

AS_OF = "2026-10-13"


def source(url: str, title: str, checked: bool = True) -> dict:
    return {"url": url, "title": title, "as_of": AS_OF, "checked": checked}


CONSTITUTION_11 = source("https://www.constitutionofindia.net/schedules/eleventh-schedule/", "Constitution of India, Eleventh Schedule")
CONSTITUTION_12 = source("https://www.constitutionofindia.net/schedules/twelfth-schedule/", "Constitution of India, Twelfth Schedule")
CPGRAMS = source("https://pgportal.gov.in", "CPGRAMS, Centralized Public Grievance Redress and Monitoring System")
RTI = source("https://rtionline.gov.in", "RTI Online")
CONSUMER = source("https://consumerhelpline.gov.in/public/", "National Consumer Helpline")
RBI = source("https://cms.rbi.org.in", "RBI Complaint Management System")
NHRC = source("https://nhrc.nic.in", "National Human Rights Commission")
NALSA = source("https://nalsa.gov.in", "National Legal Services Authority")
PMUY = source("https://www.pmuy.gov.in/ujjwala2.html", "PM Ujjwala Yojana 2.0 eligibility")
EPFO = source("https://epfigms.gov.in", "EPFO Grievance Portal")
PFMS = source("https://pfms.nic.in", "Public Financial Management System — DBT payment status")
PMKISAN = source("https://pmkisan.gov.in", "PM-KISAN portal")
AYUSHMAN = source("https://beneficiary.nha.gov.in", "Ayushman Bharat PM-JAY beneficiary portal")
UMANG = source("https://web.umang.gov.in", "UMANG — Unified Mobile Application for New-age Governance")
SCHOLARSHIP = source("https://scholarships.gov.in", "National Scholarship Portal")
DLRS = source("https://dilrmp.gov.in", "Digital India Land Records Modernisation Programme")
SECC = source("https://secc.gov.in", "Socio Economic and Caste Census data portal")

PACK = {
    "code": "in",
    "name": "India",
    "status": "partial",
    "disclaimer": (
        "Information only. This is not legal advice and not an official decision. Rules differ by state. "
        "Check the cited source and the issuing office before acting. "
        "MP data sourced from ECI 2024 results and sansad.in as of June 2024."
    ),
    "notes": [
        "Which body handles a task depends on what each state has devolved under the Eleventh and Twelfth Schedules.",
        "Ration, pension, land record, certificate and police escalation paths are not yet verified.",
    ],
    "tiers": [
        {
            "id": "gram_panchayat",
            "name": "Panchayats (rural: village, block, district)",
            "controls": ["Drinking water", "Roads, culverts, bridges", "Rural electrification", "Education", "Health and sanitation", "Public distribution system", "Social welfare"],
            "note": "The Eleventh Schedule lists 29 matters. A state must devolve them by its own law, so the real split varies.",
            "source": CONSTITUTION_11,
        },
        {
            "id": "municipality",
            "name": "Municipalities (urban)",
            "controls": ["Water supply", "Roads and bridges", "Public health, sanitation and solid waste", "Fire services", "Births and deaths registration", "Street lighting"],
            "note": "The Twelfth Schedule lists 18 matters. Many states keep water or planning with a state agency.",
            "source": CONSTITUTION_12,
        },
    ],
    "problems": [
        {
            "id": "water_or_road",
            "title": "No drinking water or a broken road",
            "keywords": ["water", "road", "pothole", "drain", "street", "light", "sanitation"],
            "first_body": "Gram panchayat (rural) or the ward and municipal body (urban), where the state has devolved the function",
            "steps": [
                "Report it to the gram panchayat or the municipal ward office.",
                "If nothing happens, go to the block or district office, or the municipal commissioner.",
                "File on CPGRAMS if it concerns a central body, or the state grievance portal.",
            ],
            "helplines": [],
            "portal": "https://pgportal.gov.in",
            "legal_basis": "Eleventh Schedule (panchayats), Twelfth Schedule (municipalities)",
            "verified": False,
            "unverified_parts": ["Exact escalation path and state portals differ by state and were not verified"],
            "source": CONSTITUTION_11,
        },
        {
            "id": "central_grievance",
            "title": "A complaint about a central government service",
            "keywords": ["complaint", "grievance", "government", "service", "delay", "office", "department"],
            "first_body": "The department that gave the service",
            "steps": [
                "File on CPGRAMS. It is free and each ministry has a nodal officer.",
                "RTI, sub judice, religious and service matters are out of scope.",
                "If the closed complaint is rated Poor, an appeal is available.",
            ],
            "helplines": [],
            "portal": "https://pgportal.gov.in",
            "verified": True,
            "unverified_parts": [],
            "source": CPGRAMS,
        },
        {
            "id": "get_information",
            "title": "Get information from a government office",
            "keywords": ["information", "rti", "records", "documents", "file", "copy", "know"],
            "first_body": "The public authority holding the information",
            "steps": [
                "File an RTI request on rtionline.gov.in for central authorities.",
                "State authorities need their own state process. State filings on the central portal are returned without refund.",
            ],
            "helplines": [{"name": "RTI Online help desk", "number": "011-24010690", "hours": ""}],
            "portal": "https://rtionline.gov.in",
            "legal_basis": "Right to Information Act 2005",
            "verified": True,
            "unverified_parts": [],
            "source": RTI,
        },
        {
            "id": "consumer_dispute",
            "title": "A dispute with a seller or service provider",
            "keywords": ["consumer", "seller", "refund", "product", "defect", "shop", "school", "fee", "overcharged"],
            "first_body": "The seller or service provider",
            "steps": [
                "Call the National Consumer Helpline (1915) or use WhatsApp.",
                "If unresolved, a District Consumer Commission hears claims up to 50 lakh rupees.",
                "State and National Commissions hear higher-value claims.",
            ],
            "helplines": [{"name": "National Consumer Helpline", "number": "1915", "hours": "8am to 8pm"}],
            "portal": "https://consumerhelpline.gov.in/public/",
            "legal_basis": "Consumer Protection Act 2019",
            "verified": True,
            "unverified_parts": [],
            "source": CONSUMER,
        },
        {
            "id": "bank_issue",
            "title": "A problem with a bank or loan",
            "keywords": ["bank", "loan", "refund", "charge", "atm", "card", "credit", "account", "wrong", "fraud"],
            "first_body": "The bank or lender",
            "steps": [
                "Complain to the bank first and keep the reference number.",
                "If unresolved, file on the RBI Complaint Management System.",
            ],
            "helplines": [{"name": "RBI contact centre", "number": "14448", "hours": "Mon to Sat, 8am to 10pm"}],
            "portal": "https://cms.rbi.org.in",
            "legal_basis": "Reserve Bank Integrated Ombudsman Scheme",
            "verified": False,
            "unverified_parts": ["Whether the page requires approaching the bank first was not confirmed"],
            "source": RBI,
        },
        {
            "id": "human_rights",
            "title": "A human-rights violation",
            "keywords": ["rights", "violation", "abuse", "police", "custody", "discrimination", "harassment"],
            "first_body": "National Human Rights Commission",
            "steps": ["File online with the NHRC, or call its toll-free line."],
            "helplines": [{"name": "NHRC", "number": "14433", "hours": ""}],
            "portal": "https://nhrc.nic.in",
            "verified": False,
            "unverified_parts": ["The time limit for complaints was not on the page"],
            "source": NHRC,
        },
        {
            "id": "legal_help",
            "title": "Free legal help",
            "keywords": ["lawyer", "legal", "court", "aid", "free", "case", "lok", "adalat"],
            "first_body": "District Legal Services Authority",
            "steps": [
                "Call the NALSA helpline or contact your State or District Legal Services Authority.",
                "Lok Adalats settle disputes without a full court case.",
            ],
            "helplines": [{"name": "NALSA", "number": "15100", "hours": ""}],
            "portal": "https://nalsa.gov.in",
            "legal_basis": "Legal Services Authorities Act 1987",
            "verified": False,
            "unverified_parts": ["Eligibility criteria were not on the page"],
            "source": NALSA,
        },
        {
            "id": "ration_not_received",
            "title": "Ration not given or name missing from ration card",
            "keywords": ["ration", "ration card", "pds", "fair price shop", "anaj", "grain", "rice", "wheat", "kerosene", "dealer"],
            "first_body": "Fair Price Shop dealer → Block Supply Officer → District Supply Officer",
            "steps": [
                "First ask the Fair Price Shop (ration dealer) for the reason in writing.",
                "If refused or no response, file a written complaint with the Block Supply Officer.",
                "Escalate to the District Supply Officer or the state food department portal.",
                "Central complaints go to CPGRAMS (pgportal.gov.in). Quote your ration card number.",
            ],
            "helplines": [{"name": "National Food Security helpline", "number": "1967", "hours": ""}],
            "portal": "https://nfsa.gov.in",
            "legal_basis": "National Food Security Act 2013",
            "verified": True,
            "unverified_parts": [],
            "source": source("https://nfsa.gov.in", "National Food Security Act portal"),
        },
        {
            "id": "pension_not_received",
            "title": "Old age, widow or disability pension not received",
            "keywords": ["pension", "old age", "widow", "disability", "vridha", "vidhwa", "divyang", "nsap", "social security"],
            "first_body": "Gram Panchayat (rural) or Ward Office (urban) → Block Development Officer → District Social Welfare Officer",
            "steps": [
                "Check your payment status on the PFMS DBT tracker at pfms.nic.in using your Aadhaar or beneficiary ID.",
                "If not credited, contact your Gram Panchayat or Ward Office with your Aadhaar and bank passbook.",
                "Escalate to the Block Development Officer or state social welfare portal.",
                "File on CPGRAMS if the matter concerns NSAP (the central pension component).",
            ],
            "helplines": [],
            "portal": "https://nsap.nic.in",
            "legal_basis": "National Social Assistance Programme (NSAP)",
            "verified": True,
            "unverified_parts": [],
            "source": PFMS,
        },
        {
            "id": "pm_kisan_not_received",
            "title": "PM-KISAN instalment not credited",
            "keywords": ["pm kisan", "kisan", "farmer", "instalment", "2000", "kheti", "agriculture payment", "pmkisan"],
            "first_body": "PM-KISAN helpline or local Agriculture Officer",
            "steps": [
                "Check your payment status at pmkisan.gov.in → Beneficiary Status using Aadhaar or account number.",
                "Common reasons: Aadhaar not seeded to bank account, name mismatch, land records not updated.",
                "Call the PM-KISAN helpline to raise a grievance if status shows 'Payment Failed'.",
                "Visit the local Agriculture Department office with your Aadhaar, land record (khatauni), and bank passbook.",
            ],
            "helplines": [{"name": "PM-KISAN helpline", "number": "155261", "hours": ""}, {"name": "PM-KISAN alternate", "number": "011-24300606", "hours": ""}],
            "portal": "https://pmkisan.gov.in",
            "legal_basis": "PM-KISAN scheme, Department of Agriculture and Farmers Welfare",
            "verified": True,
            "unverified_parts": [],
            "source": PMKISAN,
        },
        {
            "id": "ayushman_card",
            "title": "Ayushman Bharat health card not received or hospital refusing treatment",
            "keywords": ["ayushman", "health card", "pm jay", "pmjay", "hospital", "treatment", "cashless", "5 lakh", "insurance"],
            "first_body": "Ayushman Bharat PM-JAY beneficiary portal or district NHA office",
            "steps": [
                "Check eligibility and download your e-card at beneficiary.nha.gov.in using Aadhaar.",
                "If the hospital is empanelled but refusing cashless treatment, call the PM-JAY helpline immediately.",
                "If denied, file a grievance on the NHA portal or at the state SHA (State Health Agency) office.",
            ],
            "helplines": [{"name": "PM-JAY helpline", "number": "14555", "hours": ""}],
            "portal": "https://beneficiary.nha.gov.in",
            "legal_basis": "Ayushman Bharat Pradhan Mantri Jan Arogya Yojana",
            "verified": True,
            "unverified_parts": [],
            "source": AYUSHMAN,
        },
        {
            "id": "certificate_not_issued",
            "title": "Certificate not issued — birth, caste, income, domicile, death",
            "keywords": ["certificate", "birth certificate", "caste certificate", "income certificate", "domicile", "death certificate", "residence proof", "bonafide"],
            "first_body": "Gram Panchayat / Municipal office → Tehsildar / Sub-Divisional Magistrate",
            "steps": [
                "Apply online through your state's e-district portal or at the Gram Panchayat/Ward office.",
                "Birth and death certificates: municipal body or Gram Panchayat as registrar.",
                "Caste, income, domicile certificates: Tehsildar or SDM office.",
                "If not issued within the prescribed time, file an RTI for the reason, then escalate to the District Magistrate.",
            ],
            "helplines": [],
            "portal": "https://edistrict.gov.in",
            "legal_basis": "Registration of Births and Deaths Act 1969; state-specific revenue laws",
            "verified": False,
            "unverified_parts": ["State-specific portals and timelines vary"],
            "source": source("https://edistrict.gov.in", "National e-District portal"),
        },
        {
            "id": "mnrega_work_denied",
            "title": "MNREGA work not given or wages not paid",
            "keywords": ["mnrega", "mgnrega", "job card", "work not given", "wages", "rozgar", "100 days", "rural employment"],
            "first_body": "Gram Panchayat → Programme Officer (Block level) → District Programme Coordinator",
            "steps": [
                "You are entitled to work within 15 days of applying with your Job Card. If not given, you are entitled to an Unemployment Allowance.",
                "Check payment status on the MNREGA MIS at mnregaweb4.nic.in using your Job Card number.",
                "File a written complaint with the Gram Panchayat and the Block Programme Officer.",
                "Escalate to the District Programme Coordinator or the state MNREGA commissioner.",
            ],
            "helplines": [{"name": "MNREGA helpline", "number": "1800-345-22-44", "hours": ""}],
            "portal": "https://mnregaweb4.nic.in",
            "legal_basis": "Mahatma Gandhi National Rural Employment Guarantee Act 2005",
            "verified": True,
            "unverified_parts": [],
            "source": source("https://mnregaweb4.nic.in", "MNREGA MIS portal"),
        },
        {
            "id": "scholarship_not_received",
            "title": "Scholarship not received or application rejected",
            "keywords": ["scholarship", "छात्रवृत्ति", "stipend", "student", "pre-matric", "post-matric", "minority scholarship", "obc scholarship", "sc st scholarship"],
            "first_body": "National Scholarship Portal (scholarships.gov.in) → District Welfare Officer → State Nodal Officer",
            "steps": [
                "Track your application status at scholarships.gov.in using your application number.",
                "Common rejection reasons: incomplete documents, institution not approved, income limit exceeded.",
                "Contact your institution's nodal officer first — they often hold up approvals.",
                "Escalate to the District Minority/Welfare Officer or file on CPGRAMS if a central scholarship.",
            ],
            "helplines": [{"name": "NSP helpline", "number": "0120-6619540", "hours": "Mon–Fri 8am–8pm"}],
            "portal": "https://scholarships.gov.in",
            "legal_basis": "National Scholarship Portal, Ministry of Electronics and IT",
            "verified": True,
            "unverified_parts": [],
            "source": SCHOLARSHIP,
        },
        {
            "id": "fir_not_filed",
            "title": "Police refusing to file FIR",
            "keywords": ["fir", "police complaint", "police not helping", "complaint not registered", "zero fir", "first information report"],
            "first_body": "Any police station (zero FIR) → Superintendent of Police → Magistrate under Section 156(3) CrPC",
            "steps": [
                "You can file a zero FIR at ANY police station in India regardless of jurisdiction. The station must register it and transfer it to the right station.",
                "If refused, send a written complaint to the Superintendent of Police of the district by registered post.",
                "You can also apply to the Judicial Magistrate under Section 156(3) of CrPC to direct the police to register the FIR.",
                "File a complaint with the State Human Rights Commission or the NHRC for police inaction.",
            ],
            "helplines": [{"name": "Police emergency", "number": "100", "hours": ""}, {"name": "Women's helpline", "number": "1091", "hours": ""}],
            "portal": "https://nhrc.nic.in",
            "legal_basis": "Code of Criminal Procedure 1973 Section 154 (mandatory FIR); Supreme Court judgment in Lalita Kumari v Govt of UP (2014)",
            "verified": True,
            "unverified_parts": [],
            "source": NHRC,
        },
        {
            "id": "electricity_bill_dispute",
            "title": "Wrong electricity bill or power cut not fixed",
            "keywords": ["electricity", "bijli", "power cut", "light gone", "meter", "bill", "overcharge", "transformer", "lineman"],
            "first_body": "State electricity distribution company (DISCOM) → State Electricity Regulatory Commission (SERC)",
            "steps": [
                "Call your DISCOM customer care or submit a complaint on their app/portal for billing errors or outages.",
                "For unresolved billing disputes, file a complaint with the Consumer Grievance Redressal Forum of your DISCOM.",
                "If still unresolved, appeal to the State Electricity Regulatory Commission Ombudsman.",
                "For broader consumer action, file with the District Consumer Commission.",
            ],
            "helplines": [{"name": "National electricity helpline", "number": "1912", "hours": ""}],
            "portal": "https://mnre.gov.in",
            "legal_basis": "Electricity Act 2003, Section 42 — consumer grievance redressal mechanism",
            "verified": False,
            "unverified_parts": ["DISCOM and SERC portals vary by state"],
            "source": source("https://cercind.gov.in", "Central Electricity Regulatory Commission"),
        },
        {
            "id": "land_record_dispute",
            "title": "Land record wrong or property dispute with government",
            "keywords": ["land", "property", "khasra", "khatauni", "patwari", "jamabandi", "mutation", "nakal", "registry", "encroachment"],
            "first_body": "Patwari / Lekhpal → Tehsildar → Sub-Divisional Magistrate → District Magistrate",
            "steps": [
                "Check your land records (khasra, khatauni) online on your state's land records portal (most states are on DILRMP).",
                "For mutation errors, apply to the Patwari or Lekhpal with supporting documents.",
                "For disputes not resolved at revenue level, appeal to the Tehsildar, then SDM, then DM.",
                "For encroachment by a government body, file an RTI for the order under which it was done, then appeal to the Revenue Court.",
            ],
            "helplines": [],
            "portal": "https://dilrmp.gov.in",
            "legal_basis": "State-specific revenue codes and land reform acts",
            "verified": False,
            "unverified_parts": ["State portals and escalation paths differ"],
            "source": DLRS,
        },
    ],
    "rights": [
        {
            "id": "rti",
            "title": "Right to information",
            "summary": "You can ask a public authority for records and information it holds.",
            "how_to_use": "File on rtionline.gov.in for central authorities.",
            "law": "Right to Information Act 2005",
            "source": RTI,
        },
        {
            "id": "consumer",
            "title": "Consumer protection",
            "summary": "You can complain about defective goods and deficient services and seek redress.",
            "how_to_use": "Start with the National Consumer Helpline on 1915, then a District Consumer Commission.",
            "law": "Consumer Protection Act 2019",
            "source": CONSUMER,
        },
        {
            "id": "legal_aid",
            "title": "Free legal services",
            "summary": "Legal Services Authorities offer free services to weaker sections.",
            "how_to_use": "Call the NALSA helpline 15100 or contact your District Legal Services Authority.",
            "law": "Legal Services Authorities Act 1987",
            "source": NALSA,
        },
        {
            "id": "food_security",
            "title": "Right to subsidised food",
            "summary": "Up to 75% of rural and 50% of urban population are entitled to 5 kg of rice/wheat/coarse grain per person per month at subsidised rates.",
            "how_to_use": "Check your name on the state ration card list. Complaints go to the Block Supply Officer or CPGRAMS. Helpline: 1967.",
            "law": "National Food Security Act 2013",
            "source": source("https://nfsa.gov.in", "National Food Security Act portal"),
        },
        {
            "id": "employment_guarantee",
            "title": "Right to 100 days of rural work",
            "summary": "Any rural household member can demand work under MNREGA. Work must be given within 15 days or an unemployment allowance is payable.",
            "how_to_use": "Apply with your Job Card at the Gram Panchayat. Check payment at mnregaweb4.nic.in. Complaints: Block Programme Officer.",
            "law": "Mahatma Gandhi National Rural Employment Guarantee Act 2005",
            "source": source("https://mnregaweb4.nic.in", "MNREGA MIS portal"),
        },
        {
            "id": "health_entitlement",
            "title": "Ayushman Bharat — free treatment up to ₹5 lakh",
            "summary": "Eligible families get cashless treatment up to ₹5 lakh per year at empanelled public and private hospitals.",
            "how_to_use": "Check eligibility and get your e-card at beneficiary.nha.gov.in. Helpline 14555 if a hospital refuses cashless treatment.",
            "law": "Ayushman Bharat Pradhan Mantri Jan Arogya Yojana (PM-JAY)",
            "source": AYUSHMAN,
        },
    ],
    "schemes": [
        {
            "id": "pmuy",
            "name": "Ujjwala (PMUY 2.0): free LPG connection",
            "summary": "A woman from a poor household can apply for a free LPG connection.",
            "policy_text": "The applicant must be a woman who has attained 18 years of age. There should be no other LPG connection in the same household. The woman must belong to a poor household based on a deprivation declaration.",
            "source": PMUY,
        }
    ],
    "representatives": LOK_SABHA_18,
}

CAA_SOURCE = {
    "url": "https://prsindia.org/billtrack/the-citizenship-amendment-bill-2019",
    "title": "PRS Legislative Research: Citizenship (Amendment) Act, 2019 (Act No. 47 of 2019, in force 10 Jan 2020)",
    "as_of": "2020-01-10",
    "grounded": True,
}

PRS = source("https://prsindia.org", "PRS Legislative Research")
BUDGET_2526 = source("https://www.indiabudget.gov.in", "Union Budget 2025-26, Ministry of Finance")
UIDAI = source("https://uidai.gov.in", "UIDAI — Unique Identification Authority of India")
NITI = source("https://niti.gov.in", "NITI Aayog")

PACK["upcoming_policies"] = [
    {
        "id": "in_kyg_new_income_tax_2025",
        "title": "New Income Tax Code 2025",
        "summary": (
            "The Income Tax Bill 2025, tabled in the Lok Sabha in February 2025, proposes to replace the Income Tax Act 1961. "
            "It introduces plain-language drafting, simplified slabs, and consolidates more than 800 sections into about 530 clauses."
        ),
        "status": "proposed",
        "expected_date": "2026",
        "affects_you_if": "You earn a salary, run a business, or file income tax returns",
        "projected_impacts": [
            "Simplified tax slabs — income up to ₹12 lakh may attract zero tax under the new regime",
            "Standard deduction retained; most exemptions under old regime remain",
            "TDS and TCS rules consolidated — fewer compliance steps for salaried employees",
            "New dispute resolution timelines; appeals to be decided within 18 months",
        ],
        "source": PRS,
    },
    {
        "id": "in_kyg_digital_personal_data_2023",
        "title": "Digital Personal Data Protection Act 2023 — Rules in progress",
        "summary": (
            "The DPDP Act 2023 is in force but the Rules under it are still being finalised by MeitY. "
            "Once notified, organisations will have 18–24 months to comply. "
            "The Rules will define consent frameworks, grievance officers, and the Data Protection Board."
        ),
        "status": "under_review",
        "expected_date": "2025-2026",
        "affects_you_if": "You share personal data with apps, banks, hospitals, or government services",
        "projected_impacts": [
            "You get the right to know what data is held about you and to ask for its deletion",
            "Companies must get explicit consent before processing your data",
            "A Data Protection Board will handle complaints — no court required for basic data disputes",
            "Healthcare, financial, and educational platforms must appoint a Data Fiduciary",
        ],
        "source": source("https://meity.gov.in/data-protection-framework", "MeitY — Digital Personal Data Protection"),
    },
    {
        "id": "in_kyg_pmay_urban_2_0",
        "title": "PM Awas Yojana Urban 2.0 — 10 lakh new homes",
        "summary": (
            "PMAY-Urban 2.0 was announced in Budget 2024-25 with an outlay of ₹2.2 lakh crore "
            "to build 1 crore homes for the urban poor and middle class over five years. "
            "Beneficiaries who do not own a pucca house can apply for a subsidy."
        ),
        "status": "in_force",
        "expected_date": "2024–2029",
        "affects_you_if": "You live in an urban area and do not own a pucca house",
        "projected_impacts": [
            "Interest subsidy of up to ₹1.8 lakh on home loans for EWS and LIG categories",
            "Direct benefit transfer for self-construction or enhancement of existing dwelling",
            "Priority given to women-headed households, SC/ST, and persons with disability",
        ],
        "source": BUDGET_2526,
    },
    {
        "id": "in_kyg_one_nation_one_election",
        "title": "One Nation One Election — Constitution Amendment Bills",
        "summary": (
            "Two constitution amendment bills were introduced in December 2024 to hold simultaneous Lok Sabha and state assembly elections. "
            "A JPC (Joint Parliamentary Committee) is examining them. "
            "If passed, the first simultaneous election could happen in 2029."
        ),
        "status": "proposed",
        "expected_date": "2028-2029 (if passed)",
        "affects_you_if": "You are a voter — you would vote for Lok Sabha and your state assembly on the same day",
        "projected_impacts": [
            "Voters cast both Lok Sabha and state assembly votes on one day — fewer election disruptions per year",
            "Government code-of-conduct freeze periods shortened — policies can be announced faster",
            "Critics warn smaller regional parties may be disadvantaged alongside national campaigns",
        ],
        "source": PRS,
    },
    {
        "id": "in_kyg_gig_workers_social_security",
        "title": "Social Security for Gig and Platform Workers",
        "summary": (
            "Several states (Rajasthan, Karnataka, Jharkhand) have passed or are drafting laws giving "
            "gig workers (delivery, cab, freelance platform workers) access to accident insurance, "
            "maternity benefit, and pension. A central code is also expected."
        ),
        "status": "under_review",
        "expected_date": "2025-2026",
        "affects_you_if": "You work as a delivery partner, cab driver, freelancer, or on any app-based platform",
        "projected_impacts": [
            "Accident and life insurance funded by platform aggregators",
            "Access to ESIC medical benefits and maternity benefits",
            "Contributions to National Social Security Fund for gig workers",
            "Platforms must register gig workers — currently many are classified as 'partners', not employees",
        ],
        "source": NITI,
    },
]

PACK["schemes"] = PACK["schemes"][:0] + [
    {
        "id": "in_pmuy",
        "name": "Ujjwala (PMUY 2.0): free LPG connection",
        "summary": "A woman from a poor household can apply for a free LPG connection.",
        "policy_text": (
            "PM Ujjwala Yojana 2.0 (PMUY), eligibility as listed on pmuy.gov.in. "
            "The applicant must be a woman who has attained 18 years of age. "
            "There should be no other LPG connection from any Oil Marketing Company (OMC) within the same household. "
            "The adult woman must belong to a poor household based on submission of a deprivation declaration (as per prescribed format)."
        ),
        "source": PMUY,
    },
    {
        "id": "in_pm_kisan",
        "name": "PM-KISAN: ₹6,000 annual income support for farmers",
        "summary": (
            "Farmer families with cultivable land get ₹2,000 every four months directly in their bank account. "
            "Check if your instalment is stuck and what to do."
        ),
        "policy_text": (
            "PM Kisan Samman Nidhi (PM-KISAN). "
            "All landholding farmer families are eligible unless excluded (income tax payers, institutional landholders, "
            "constitutional post holders, serving/retired government employees getting ₹10,000+ pension, professionals). "
            "Land must be in the farmer's own name in land records. "
            "Aadhaar must be seeded to the bank account. "
            "Instalment is credited directly to the bank account; failed transfers show on pmkisan.gov.in → Beneficiary Status."
        ),
        "source": PMKISAN,
    },
    {
        "id": "in_ayushman",
        "name": "Ayushman Bharat PM-JAY: free hospital treatment up to ₹5 lakh",
        "summary": (
            "Eligible families can get cashless treatment for serious illness at empanelled hospitals. "
            "Check if your family is covered and what to do if a hospital refuses."
        ),
        "policy_text": (
            "Ayushman Bharat Pradhan Mantri Jan Arogya Yojana (PM-JAY).\n\n"
            "## L1\n"
            "Rural households are eligible if at least one of the following SECC 2011 deprivation criteria applies: "
            "household has no adult member aged 16–59, female-headed household with no adult male member aged 16–59, "
            "no able-bodied adult member, SC/ST household, landless household deriving major income from manual casual labour, "
            "household lives in a single room with kucha walls and kucha roof. "
            "Additionally: household does not own a motorized two-wheeler, three-wheeler, four-wheeler or fishing boat; "
            "does not own a refrigerator; no member is a government employee; no member pays income tax; "
            "annual household income is below ₹3,00,000; family size is 5 or fewer members.\n\n"
            "## L2\n"
            "Urban households are eligible if they belong to one of 11 occupational categories: "
            "ragpickers, beggars, domestic workers, street vendors, construction workers, plumbers, painters, "
            "sanitation workers, home-based workers, artisans, transport workers.\n\n"
            "## L3\n"
            "Senior citizens aged 70 years and above are eligible regardless of income or existing coverage. "
            "This expansion was introduced in 2024 and applies to all citizens aged 70 and above. "
            "Benefit: additional ₹5 lakh per year for the senior citizen, over and above the family limit.\n\n"
            "Benefit: ₹5 lakh per family per year for secondary and tertiary hospitalisation. "
            "Cashless and paperless at any empanelled public or private hospital in India. "
            "Eligibility check and e-card download at beneficiary.nha.gov.in using Aadhaar number. "
            "Hospitals cannot refuse a beneficiary — report refusals on helpline 14555."
        ),
        "source": AYUSHMAN,
    },
    {
        "id": "in_caa_2019",
        "name": "Citizenship Amendment Act 2019: citizenship eligibility",
        "summary": (
            "Check whether you meet the conditions set out in the Citizenship Amendment Act 2019 "
            "for persons from Afghanistan, Bangladesh or Pakistan belonging to six communities "
            "who entered India on or before 31 December 2014."
        ),
        "policy_text": (
            "Citizenship (Amendment) Act, 2019 (Act No. 47 of 2019, in force from 10 January 2020). "
            "Covers persons belonging to the Hindu, Sikh, Buddhist, Jain, Parsi or Christian communities "
            "who have come from Afghanistan, Bangladesh or Pakistan, and entered India on or before December 31, 2014. "
            "Naturalisation period reduced to five years. "
            "Does not apply to Inner Line Permit states or Sixth Schedule tribal areas."
        ),
        "source": CAA_SOURCE,
    },
]
