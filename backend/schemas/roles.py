from enum import StrEnum


class Role(StrEnum):
    """The three account tiers, in ascending order of privilege.

    USER can chat. ADMIN can additionally manage USER/ADMIN accounts.
    SUPER_ADMIN can manage every account, including granting SUPER_ADMIN.
    """

    USER = "USER"
    ADMIN = "ADMIN"
    SUPER_ADMIN = "SUPER_ADMIN"
