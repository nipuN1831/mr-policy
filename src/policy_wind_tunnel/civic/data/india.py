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

PACK = {
    "code": "in",
    "name": "India",
    "status": "partial",
    "disclaimer": (
        "Information only. This is not legal advice and not an official decision. Rules differ by state. "
        "Check the cited source and the issuing office before acting. Representatives shown here are fictional demo data."
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
    "representatives": [
        {
            "id": "demo-in-1",
            "name": "Asha Verma (demo)",
            "role": "Member of Parliament (Lok Sabha)",
            "body": "Lok Sabha",
            "region": "Demo State",
            "constituency": "Demo Nagar",
            "party": "Demo Party",
            "terms": 2,
            "fictional": True,
            "handles": {"x": "demo_asha_verma"},
            "record": [
                {"label": "Terms served", "value": "2", "source": source("https://sansad.in", "Source type for the real field: Sansad member record")},
                {"label": "Qualification", "value": "Postgraduate", "source": source("https://sansad.in", "Source type for the real field: Sansad member record")},
            ],
            "links": {"Lok Sabha member page": "https://sansad.in", "PRS MP Track": "https://prsindia.org/mptrack"},
        },
        {
            "id": "demo-in-2",
            "name": "Ravi Menon (demo)",
            "role": "Member of Legislative Assembly",
            "body": "Demo State Legislative Assembly",
            "region": "Demo State",
            "constituency": "Demo Nagar",
            "party": "Demo Alliance",
            "terms": 1,
            "fictional": True,
            "handles": {},
            "record": [
                {"label": "Terms served", "value": "1", "source": source("https://sansad.in", "Source type for the real field: assembly member record")},
            ],
            "links": {},
        },
    ],
}

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
    }
]
