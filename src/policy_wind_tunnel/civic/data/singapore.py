from policy_wind_tunnel.civic import scheme_texts as texts

AS_OF = "2026-10-13"


def source(url: str, title: str, as_of: str = AS_OF) -> dict:
    return {"url": url, "title": title, "as_of": as_of, "checked": True}


PARLIAMENT = source("https://www.parliament.gov.sg/mps/find-mps-in-my-constituency", "Parliament of Singapore: find MPs in my constituency")
LEGAL_AID = source(texts.LEGAL_SOURCE["url"], texts.LEGAL_SOURCE["title"], texts.LEGAL_SOURCE["as_of"])
CCCS = source("https://www.ccs.gov.sg/", "Competition and Consumer Commission of Singapore")

PACK = {
    "code": "sg",
    "name": "Singapore",
    "status": "partial",
    "disclaimer": (
        "Information only. This is not legal advice and not an official decision. "
        "Check the cited source and its date before acting. Representatives shown here are fictional demo data."
    ),
    "notes": [
        "Government tiers, town councils and most problem-to-body mappings were not verified from official pages.",
        "Whether Singapore has a general freedom-of-information law was not verified, so no information-access right is listed.",
        "Parliament's terms bar copying MP lists, so only fictional demo MPs are shown and the official finder is linked.",
    ],
    "tiers": [],
    "problems": [
        {
            "id": "legal_help",
            "title": "I need free or low-cost legal help",
            "keywords": ["lawyer", "legal", "aid", "court", "advice", "free", "cannot afford", "means"],
            "first_body": "Legal Aid Bureau",
            "steps": [
                "Check the Means Test: it looks at household income per person, the home's Annual Value, savings and other property.",
                "Legal Advice and Assistance needs the Means Test. Legal Aid needs the Means and Merits Tests.",
            ],
            "helplines": [],
            "portal": "https://lab.mlaw.gov.sg/legal-services/do-i-qualify/",
            "legal_basis": "",
            "verified": False,
            "unverified_parts": ["No phone number or hours were verified", "The legal basis was not read from the statute"],
            "source": LEGAL_AID,
        },
        {
            "id": "consumer",
            "title": "A consumer complaint or unfair trading practice",
            "keywords": ["consumer", "seller", "shop", "refund", "unfair", "scam", "product", "trader"],
            "first_body": "The trader first, then the consumer regulator",
            "steps": ["See the Competition and Consumer Commission of Singapore for consumer protection information."],
            "helplines": [{"name": "ScamShield helpline", "number": "1799", "hours": "24/7"}],
            "portal": "https://www.ccs.gov.sg/",
            "verified": False,
            "unverified_parts": ["The consumer-protection page returned 404, so the complaint path was not verified", "CASE contact details were not verified"],
            "source": CCCS,
        },
    ],
    "rights": [],
    "schemes": [
        {
            "id": "sg_silver_support",
            "name": "Silver Support Scheme: quarterly cash for lower-income seniors",
            "summary": "Citizens aged 65 and above with low lifetime wages, living in a 1- to 5-room HDB flat, in a household with low income per person.",
            "policy_text": texts.SILVER_TEXT,
            "source": source(texts.SILVER_SOURCE["url"], texts.SILVER_SOURCE["title"], texts.SILVER_SOURCE["as_of"]),
        },
        {
            "id": "sg_legal_aid_means",
            "name": "Legal Aid Bureau Means Test",
            "summary": "The income, home value, savings and property limits for legal advice and legal aid.",
            "policy_text": texts.LEGAL_TEXT,
            "source": LEGAL_AID,
        },
    ],
    "representatives": [
        {
            "id": "demo-sg-1",
            "name": "Mei Lin Tan (demo)",
            "role": "Member of Parliament",
            "body": "Parliament of Singapore",
            "region": "Demo Region",
            "constituency": "Demo GRC",
            "party": "Demo Party",
            "terms": 2,
            "fictional": True,
            "handles": {},
            "record": [{"label": "Terms served", "value": "2", "source": source("https://www.parliament.gov.sg/mps/list-of-current-mps", "Source type for the real field: Parliament MP page")}],
            "links": {"Official MP finder": "https://www.parliament.gov.sg/mps/find-mps-in-my-constituency"},
        }
    ],
}
