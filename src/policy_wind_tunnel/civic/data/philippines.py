AS_OF = "2026-10-13"


def source(url: str, title: str, as_of: str = AS_OF) -> dict:
    return {"url": url, "title": title, "as_of": as_of, "checked": True}


LGC = source("https://lawphil.net/statutes/repacts/ra1991/ra_7160_1991.html", "Republic Act 7160, Local Government Code of 1991 (Lawphil)")
EO2 = source("https://lawphil.net/executive/execord/eo2016/eo_2_2016.html", "Executive Order No. 2, s. 2016 (Lawphil)")
RA11916 = source("https://lawphil.net/statutes/repacts/ra2022/ra_11916_2022.html", "Republic Act 11916 (Lawphil)")
DBM = source("https://www.dbm.gov.ph/index.php/management-2/2737-social-pension-budget-for-", "DBM: social pension budget release (2024)", "2024-01-01")
DTI = source("https://www.dti.gov.ph", "Department of Trade and Industry")
OMBUDSMAN = source("https://www.ombudsman.gov.ph", "Office of the Ombudsman")

PACK = {
    "code": "ph",
    "name": "Philippines",
    "status": "partial",
    "disclaimer": (
        "Information only. This is not legal advice and not an official decision. "
        "Check the cited source and its date before acting. Representatives shown here are fictional demo data."
    ),
    "notes": [
        "Most official Philippine sites blocked verification, so many hotlines, hours and escalation paths are not listed.",
        "The social pension has no numeric means threshold on any page read and uses caseworker judgement, so no self-check is offered.",
        "The date on the DBM release is approximate (year only).",
    ],
    "tiers": [
        {
            "id": "barangay",
            "name": "Barangay",
            "controls": ["Health centre and day-care centre", "Hygiene, sanitation and solid-waste collection", "Katarungang pambarangay (local dispute settlement)", "Barangay roads, bridges and water supply"],
            "note": "Services listed in Section 17(b). Province, city and municipality service lists were not read.",
            "source": LGC,
        }
    ],
    "problems": [
        {
            "id": "neighbour_dispute",
            "title": "A dispute with a neighbour",
            "keywords": ["neighbour", "neighbor", "dispute", "boundary", "quarrel", "settle", "mediation", "barangay"],
            "first_body": "Lupong Tagapamayapa (barangay justice committee)",
            "steps": ["Bring the dispute to the barangay. The Lupon covers disputes between parties living in the same city or municipality."],
            "helplines": [],
            "portal": "",
            "legal_basis": "Local Government Code, Sections 399 and 408",
            "verified": False,
            "unverified_parts": ["The escalation path if settlement fails was not verified"],
            "source": LGC,
        },
        {
            "id": "garbage",
            "title": "Garbage is not being collected",
            "keywords": ["garbage", "trash", "waste", "rubbish", "collection", "sanitation"],
            "first_body": "Barangay",
            "steps": ["Barangays provide solid-waste collection under Section 17(b)."],
            "helplines": [],
            "portal": "",
            "legal_basis": "Local Government Code, Section 17(b)",
            "verified": False,
            "unverified_parts": ["City and municipal escalation was not verified"],
            "source": LGC,
        },
        {
            "id": "consumer",
            "title": "A consumer complaint",
            "keywords": ["consumer", "seller", "refund", "product", "shop", "defect", "price"],
            "first_body": "Department of Trade and Industry",
            "steps": ["Contact the DTI consumer hotline."],
            "helplines": [{"name": "DTI hotline", "number": "1-DTI (384)", "hours": ""}],
            "portal": "https://www.dti.gov.ph",
            "verified": False,
            "unverified_parts": ["Hours and the complaint steps were not verified"],
            "source": DTI,
        },
        {
            "id": "corruption",
            "title": "Report corruption or misconduct by a public official",
            "keywords": ["corruption", "bribe", "misconduct", "official", "graft", "abuse", "complaint"],
            "first_body": "Office of the Ombudsman",
            "steps": ["Contact the Ombudsman."],
            "helplines": [{"name": "Ombudsman central office", "number": "(+632) 5317-8300", "hours": ""}],
            "portal": "https://www.ombudsman.gov.ph",
            "verified": False,
            "unverified_parts": ["Hours and how to file were not verified"],
            "source": OMBUDSMAN,
        },
        {
            "id": "information",
            "title": "I want a government record or document",
            "keywords": ["information", "records", "documents", "foi", "request", "access", "copy"],
            "first_body": "The Executive Branch agency that holds it",
            "steps": [
                "Make a written request with your name, contact details, a valid ID and a description of the information.",
                "The receiving official must help you free of charge, and your request is stamped with date and time.",
            ],
            "helplines": [],
            "portal": "",
            "legal_basis": "Executive Order No. 2, s. 2016, Section 9",
            "verified": False,
            "unverified_parts": ["The response deadline was cut off in the text read", "Whether the order binds local governments was not verified", "The eFOI portal was not opened"],
            "source": EO2,
        },
    ],
    "rights": [
        {
            "id": "foi",
            "title": "Right to information",
            "summary": "The Constitution recognises the people's right to information, and Executive Order 2 operationalises it in the Executive Branch.",
            "how_to_use": "Write to the agency with your name, ID and a description of what you want.",
            "law": "Executive Order No. 2, s. 2016",
            "source": EO2,
        }
    ],
    "schemes": [
        {
            "id": "ph_social_pension",
            "name": "Social Pension for Indigent Senior Citizens",
            "summary": "A monthly stipend of at least P1,000 for indigent senior citizens. Eligibility is judged by a caseworker.",
            "policy_text": (
                "Indigent senior citizens shall be entitled to a monthly stipend amounting to not less than One thousand pesos (P1,000.00). "
                "Eligible recipients must be 60 years old and above, frail and sickly, and without pensions from other government sources "
                "such as the GSIS, PVAO, SSS, and private insurance companies. They should not have a regular source of income or support "
                "from family or relatives to cover their basic needs."
            ),
            "source": RA11916,
        }
    ],
    "representatives": [
        {
            "id": "demo-ph-1",
            "name": "Maria Santos (demo)",
            "role": "Punong Barangay",
            "body": "Demo Barangay",
            "region": "Demo Province",
            "constituency": "Demo Barangay",
            "party": "",
            "terms": 1,
            "fictional": True,
            "handles": {},
            "record": [{"label": "Terms served", "value": "1", "source": LGC}],
            "links": {},
        }
    ],
}
