def make_referral_link(bot_username: str, user_id: int) -> str:
    return f"https://t.me/{bot_username}?start=ref_{user_id}"


def parse_referral(start_param: str) -> int | None:
    if start_param and start_param.startswith("ref_"):
        try:
            return int(start_param[4:])
        except ValueError:
            pass
    return None
