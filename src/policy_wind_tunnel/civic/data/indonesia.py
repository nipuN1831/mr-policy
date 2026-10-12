AS_OF = "2026-10-13"


def source(url: str, title: str, as_of: str = AS_OF) -> dict:
    return {"url": url, "title": title, "as_of": as_of, "checked": True}


LAPOR = source("https://lapor.go.id", "LAPOR! Layanan Aspirasi dan Pengaduan Online Rakyat")
OMBUDSMAN = source("https://ombudsman.go.id", "Ombudsman Republik Indonesia")
KPK = source("https://www.kpk.go.id/id", "Komisi Pemberantasan Korupsi")

PACK = {
    "code": "id",
    "name": "Indonesia",
    "status": "partial",
    "disclaimer": (
        "Information only. This is not legal advice and not an official decision. "
        "Check the cited source and its date before acting. Representatives shown here are fictional demo data."
    ),
    "notes": [
        "The laws on government tiers, information access, consumer protection and legal aid could not be opened, so none are listed.",
        "PKH and other social assistance depend on a government database a citizen cannot self-check, and the official page was unreachable, so no scheme is offered.",
        "Hotlines for OJK, Komnas HAM and BPKN were not verified.",
    ],
    "tiers": [],
    "problems": [
        {
            "id": "public_complaint",
            "title": "A complaint or question about a public service",
            "keywords": ["complaint", "pengaduan", "service", "government", "report", "aspiration", "information", "request"],
            "first_body": "LAPOR! national complaint portal",
            "steps": [
                "File a report on LAPOR!. You need an account, and you can choose anonymous or confidential.",
                "The portal verifies the report within 3 days and forwards it; the agency acts within 5 days; you can reply within 10 days.",
            ],
            "helplines": [],
            "portal": "https://lapor.go.id",
            "legal_basis": "",
            "verified": False,
            "unverified_parts": ["No hotline number or hours were listed on the page", "The legal basis was not stated"],
            "source": LAPOR,
        },
        {
            "id": "maladministration",
            "title": "Poor service or maladministration by a public body",
            "keywords": ["ombudsman", "maladministration", "service", "official", "delay", "complaint", "public"],
            "first_body": "Ombudsman Republik Indonesia",
            "steps": ["Contact the Ombudsman."],
            "helplines": [{"name": "Ombudsman RI", "number": "137", "hours": ""}],
            "portal": "https://ombudsman.go.id",
            "verified": False,
            "unverified_parts": ["Hours and the process were not read"],
            "source": OMBUDSMAN,
        },
        {
            "id": "corruption",
            "title": "Report corruption",
            "keywords": ["corruption", "korupsi", "bribe", "graft", "official", "misconduct"],
            "first_body": "Komisi Pemberantasan Korupsi (KPK)",
            "steps": ["Use the public complaint service. The page says the reporter's identity is kept confidential."],
            "helplines": [
                {"name": "KPK call centre", "number": "198", "hours": ""},
                {"name": "KPK", "number": "021-2557-8300", "hours": ""},
            ],
            "portal": "https://www.kpk.go.id/id",
            "verified": False,
            "unverified_parts": ["Hours were not shown"],
            "source": KPK,
        },
    ],
    "rights": [],
    "schemes": [],
    "representatives": [
        {
            "id": "demo-id-1",
            "name": "Budi Santoso (demo)",
            "role": "Member of regional council (DPRD)",
            "body": "Demo Regency Council",
            "region": "Demo Province",
            "constituency": "Demo Dapil 1",
            "party": "Demo Party",
            "terms": 1,
            "fictional": True,
            "handles": {},
            "record": [{"label": "Terms served", "value": "1", "source": LAPOR}],
            "links": {},
        }
    ],
}
