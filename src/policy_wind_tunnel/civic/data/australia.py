AS_OF = "2026-10-13"


def source(url: str, title: str, as_of: str = AS_OF) -> dict:
    return {"url": url, "title": title, "as_of": as_of, "checked": True}


OAIC = source("https://www.oaic.gov.au/freedom-of-information", "Office of the Australian Information Commissioner: freedom of information")
NLA = source("https://nationallegalaid.org.au/", "National Legal Aid")
AEC = source("https://www.aec.gov.au/footer/Copyright.htm", "Australian Electoral Commission: copyright", "2017-02-06")

PACK = {
    "code": "au",
    "name": "Australia",
    "status": "partial",
    "disclaimer": (
        "Information only. This is not legal advice and not an official decision. "
        "Check the cited source and its date before acting. Representatives shown here are fictional demo data."
    ),
    "notes": [
        "The Age Pension income and assets thresholds could not be opened, so no eligibility check is offered for it.",
        "Government tiers, consumer, energy, tenancy and local-council problems were not verified from official pages.",
        "The official electorate finder URL could not be confirmed.",
    ],
    "tiers": [],
    "problems": [
        {
            "id": "information",
            "title": "I want to see information a government agency holds",
            "keywords": ["information", "records", "documents", "foi", "access", "request", "file", "agency"],
            "first_body": "The agency that holds the information",
            "steps": [
                "Make a freedom of information request to the agency.",
                "If you disagree with the outcome, you can ask for a review.",
            ],
            "helplines": [{"name": "OAIC", "number": "1300 363 992", "hours": "Mon to Thu 10am to 4pm AEST/AEDT"}],
            "portal": "https://www.oaic.gov.au/freedom-of-information",
            "legal_basis": "Freedom of Information Act 1982",
            "verified": True,
            "unverified_parts": [],
            "source": OAIC,
        },
        {
            "id": "legal_help",
            "title": "I need free legal help",
            "keywords": ["lawyer", "legal", "aid", "court", "advice", "free", "cannot afford"],
            "first_body": "Your state or territory legal aid commission",
            "steps": ["Find your state or territory legal aid commission through National Legal Aid."],
            "helplines": [{"name": "Legal Aid Victoria", "number": "1300 792 387", "hours": ""}],
            "portal": "https://nationallegalaid.org.au/",
            "verified": False,
            "unverified_parts": ["Only the Victorian number was seen; other states' numbers and all hours were not verified", "Eligibility rules were not read"],
            "source": NLA,
        },
    ],
    "rights": [
        {
            "id": "foi",
            "title": "Right to request government information",
            "summary": "The Freedom of Information Act 1982 gives you the right to request access to government-held information.",
            "how_to_use": "Make a request to the agency, and ask for a review if you disagree with the outcome.",
            "law": "Freedom of Information Act 1982",
            "source": OAIC,
        }
    ],
    "schemes": [],
    "representatives": [
        {
            "id": "demo-au-1",
            "name": "Jordan Hale (demo)",
            "role": "Member of the House of Representatives",
            "body": "Parliament of Australia",
            "region": "Demo State",
            "constituency": "Demo Division",
            "party": "Demo Party",
            "terms": 1,
            "fictional": True,
            "handles": {},
            "record": [{"label": "Terms served", "value": "1", "source": AEC}],
            "links": {},
        }
    ],
}
