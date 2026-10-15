"""Zero-shot label descriptions. These are roles, not names of people or offices."""

LABELS = {
    "judge": "Name of a judge, magistrate, or justice in this text",
    "plaintiff": "Name of a plaintiff, petitioner, or appellant in this text",
    "defendant": "Name of a defendant, respondent, or appellee in this text",
    "attorney_for_plaintiff": "Name of a lawyer who represents the plaintiff or petitioner",
    "attorney_for_defendant": "Name of a lawyer who represents the defendant or respondent",
    "attorney": "Name of a lawyer or counsel whose client side is not stated",
    "law_firm": "Name of a law firm or legal office",
    "email": "An email address",
    "phone": "A telephone number",
    "address": "A street, postal, or mailing address",
}

PERSON_LABELS = {
    "judge",
    "attorney",
    "attorney_for_plaintiff",
    "attorney_for_defendant",
}

LABEL_TO_TYPE = {
    "judge": ("judge", "judge", ""),
    "plaintiff": ("party", "plaintiff", "plaintiff"),
    "defendant": ("party", "defendant", "defendant"),
    "attorney_for_plaintiff": ("counsel", "attorney", "plaintiff"),
    "attorney_for_defendant": ("counsel", "attorney", "defendant"),
    "attorney": ("counsel", "attorney", ""),
    "law_firm": ("firm", "firm", ""),
}

CONTACT_LABELS = {"email", "phone", "address", "law_firm"}
