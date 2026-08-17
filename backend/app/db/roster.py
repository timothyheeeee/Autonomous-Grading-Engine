"""Canonical mock roster used to validate messy CSV name resolution."""

ROSTER = [
    {
        "canonical_name": "Timothy He",
        "aliases": ["Tim He", "T. He", "Timothy"],
        "email": "timothy.he@university.edu",
        "unit_track": "data_science",
    },
    {
        "canonical_name": "Clementine Gleeson-Cook",
        "aliases": ["Clem Gleeson-Cook", "C. Gleeson-Cook", "Clementine"],
        "email": "clementine.gc@university.edu",
        "unit_track": "data_science",
    },
    {
        "canonical_name": "Nico Napoli",
        "aliases": ["N. Napoli", "Nico"],
        "email": "nico.napoli@university.edu",
        "unit_track": "data_science",
    },
    {
        "canonical_name": "Renee Wong",
        "aliases": ["Renée Wong", "R. Wong", "Renee"],
        "email": "renee.wong@university.edu",
        "unit_track": "anatomy_histology",
    },
    {
        "canonical_name": "Ruby Yang",
        "aliases": ["R. Yang", "Ruby"],
        "email": "ruby.yang@university.edu",
        "unit_track": "anatomy_histology",
    },
]

CRITERIA = {
    "data_science": [
        "Technical Implementation",
        "Data Wrangling",
        "Communication",
        "Collaboration",
        "Reproducibility",
    ],
    "anatomy_histology": [
        "Knowledge Application",
        "Practical Skills",
        "Team Contribution",
        "Scientific Communication",
        "Professionalism",
    ],
}

DEMO_USERS = [
    {
        "email": "professor@university.edu",
        "full_name": "Professor Chen",
        "role": "professor",
        "password": "professor123",
        "student_id": None,
    },
    {
        "email": "admin@university.edu",
        "full_name": "Faculty Admin",
        "role": "admin",
        "password": "admin123",
        "student_id": None,
    },
    {
        "email": "timothy.he@university.edu",
        "full_name": "Timothy He",
        "role": "student",
        "password": "student123",
        "student_id": "S1001",
    },
    {
        "email": "clementine.gc@university.edu",
        "full_name": "Clementine Gleeson-Cook",
        "role": "student",
        "password": "student123",
        "student_id": "S1002",
    },
    {
        "email": "nico.napoli@university.edu",
        "full_name": "Nico Napoli",
        "role": "student",
        "password": "student123",
        "student_id": "S1003",
    },
    {
        "email": "renee.wong@university.edu",
        "full_name": "Renee Wong",
        "role": "student",
        "password": "student123",
        "student_id": "S1004",
    },
    {
        "email": "ruby.yang@university.edu",
        "full_name": "Ruby Yang",
        "role": "student",
        "password": "student123",
        "student_id": "S1005",
    },
]


def alias_lookup() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for member in ROSTER:
        mapping[member["canonical_name"].casefold()] = member["canonical_name"]
        for alias in member["aliases"]:
            mapping[alias.casefold()] = member["canonical_name"]
    return mapping
