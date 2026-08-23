import logging

logger = logging.getLogger("feg_fpl")


def escape_markdown(text: str) -> str:
    """
    Escapes Telegram legacy Markdown (v1) special characters in user-supplied strings
    such as names, usernames, team names, and bank details to prevent Markdown entity parsing crashes.
    """
    if not text:
        return ""
    text_str = str(text)
    # Characters that break Telegram legacy Markdown: _ * ` [
    for char in ["_", "*", "`", "["]:
        text_str = text_str.replace(char, f"\\{char}")
    return text_str


async def safe_send_markdown(target_msg, text: str, reply_markup=None):
    """
    Safely sends a Telegram message formatted in Markdown. If Telegram throws a Markdown
    parsing entity error, it catches it and falls back to clean plain text.
    """
    try:
        await target_msg.reply_text(text=text, reply_markup=reply_markup, parse_mode="Markdown")
    except Exception as err:
        logger.warning(f"Markdown rendering error: {err}. Falling back to plain text.")
        plain_text = text.replace("**", "").replace("`", "").replace("\\", "")
        await target_msg.reply_text(text=plain_text, reply_markup=reply_markup)
