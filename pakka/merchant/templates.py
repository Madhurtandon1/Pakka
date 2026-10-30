"""Reviewed, static templates. No generated text reaches the merchant.

Every amount in a message is a lender ledger figure passed in as a placeholder.
"""
from datetime import date, datetime

SOUNDBOX_CUE = {
    "en": "You have an important message in your Paytm for Business app.",
    "hi": "Paytm for Business app mein aapke liye ek zaroori sandesh hai.",
}

TEMPLATES = {
    "T_SB_CUE": SOUNDBOX_CUE,
    "T_SHORTFALL": {
        "en": "Today's sales weren't enough for your daily loan payment to {lender}. "
              "Short today: {shortfall}. Total due now: {overdue}, unpaid since {oldest}. "
              "{penal_note}. You can pay now, pay later, ask {lender} for a lower daily deduction "
              "or a new date, or ask for a call.",
        "hi": "आज की बिक्री से {lender} की आपकी रोज़ की किस्त पूरी नहीं कटी। "
              "आज की कमी: {shortfall}। अभी कुल बकाया: {overdue}, {oldest} से। "
              "{penal_note}। आप अभी भर सकते हैं, बाद में भर सकते हैं, {lender} से कम कटौती या "
              "नई तारीख माँग सकते हैं, या कॉल माँग सकते हैं।",
    },
    "T_ARREARS": {
        "en": "You're behind on your daily loan payments to {lender}. Total due now: {overdue}, unpaid since {oldest}. "
              "{penal_note}. You can pay now, pay later, ask {lender} for a lower daily deduction "
              "or a new date, or ask for a call.",
        "hi": "{lender} की आपकी रोज़ की किस्तें पीछे चल रही हैं। अभी कुल बकाया: {overdue}, {oldest} से। "
              "{penal_note}। आप अभी भर सकते हैं, बाद में भर सकते हैं, {lender} से कम कटौती या "
              "नई तारीख माँग सकते हैं, या कॉल माँग सकते हैं।",
    },
    "T_DIP_RISK": {
        "en": "Your sales over the last {window} days averaged {avg} a day, close to your daily "
              "loan payment of {edi} to {lender}. Nothing is late yet. If a slow stretch is coming, "
              "you can ask {lender} for a lower daily deduction, or ask for a call.",
        "hi": "पिछले {window} दिनों में आपकी औसत रोज़ की बिक्री {avg} रही, जो {lender} की रोज़ की "
              "किस्त {edi} के करीब है। अभी कुछ बकाया नहीं है। अगर आगे धंधा धीमा रहने वाला है, तो "
              "आप {lender} से कम कटौती माँग सकते हैं, या कॉल माँग सकते हैं।",
    },
    "T_PAY_LINK": {
        "en": "Pay {amount} directly to {lender}: {link}. The money goes to {lender}'s account.",
        "hi": "{amount} सीधे {lender} को भरें: {link}। पैसा {lender} के खाते में जाएगा।",
    },
    "T_PAY_CHOICE": {
        "en": "You can pay just today's shortfall of {short_amount}: {short_link}\n"
              "Or pay the total due of {amount}: {link}\nBoth go directly to {lender}'s account.",
        "hi": "आप सिर्फ़ आज की कमी {short_amount} भर सकते हैं: {short_link}\n"
              "या पूरा बकाया {amount} भरें: {link}\nदोनों सीधे {lender} के खाते में जाते हैं।",
    },
    "T_REMINDER_SET": {
        "en": "Okay. I'll remind you at {time} on {date}. When you're ready, pay {lender} here: {link}",
        "hi": "ठीक है। मैं आपको {date} को {time} बजे याद दिलाऊँगा। जब तैयार हों, {lender} को यहाँ भरें: {link}",
    },
    "T_REQ_ROUTED": {
        "en": "Your request for {request} has been sent to {lender}. They will decide and inform you. "
              "Until then, your current schedule stays the same.",
        "hi": "{request} का आपका अनुरोध {lender} को भेज दिया गया है। फ़ैसला वही करेंगे और आपको बताएँगे। "
              "तब तक आपका मौजूदा शेड्यूल वैसा ही रहेगा।",
    },
    "T_CALLBACK": {
        "en": "Someone from {lender} will call you at {time} on {date}.",
        "hi": "{lender} से कोई आपको {date} को {time} बजे कॉल करेगा।",
    },
    "T_HANDOFF": {
        "en": "A person from {lender} will contact you. They'll see this conversation, so you won't need "
              "to repeat yourself. Grievance officer: {officer}. You can also ask for free debt counselling.",
        "hi": "{lender} से एक व्यक्ति आपसे संपर्क करेगा। उन्हें यह बातचीत दिखेगी, आपको कुछ दोहराना नहीं पड़ेगा। "
              "शिकायत अधिकारी: {officer}। आप मुफ़्त कर्ज़ परामर्श (debt counselling) भी माँग सकते हैं।",
    },
    "T_CURED": {
        "en": "Thank you. Your instalments with {lender} are up to date.",
        "hi": "धन्यवाद। {lender} की आपकी किस्तें अब पूरी हैं।",
    },
    "T_REPEAT_OFFER": {
        "en": "You can view offers from lenders on the offers screen. Compare them before choosing.",
        "hi": "आप ऑफ़र स्क्रीन पर अलग-अलग लोन देने वालों के ऑफ़र देख सकते हैं। चुनने से पहले तुलना करें।",
    },
}

REQUEST_NAMES = {
    "route_lower_deduction_request": {"en": "a lower daily deduction", "hi": "कम रोज़ाना कटौती"},
    "route_reschedule_request": {"en": "a new repayment date", "hi": "नई भुगतान तारीख"},
}

OPTIONS = {
    "T_SHORTFALL": ["pay_today", "pay_later", "lower_deduction", "reschedule", "callback", "already_paid"],
    "T_ARREARS": ["pay_today", "pay_later", "lower_deduction", "reschedule", "callback", "already_paid"],
    "T_DIP_RISK": ["lower_deduction", "callback"],
    "T_PAY_LINK": ["already_paid", "callback"],
    "T_PAY_CHOICE": ["already_paid", "callback"],
    "T_REMINDER_SET": ["pay_today", "callback"],
}


def rupees(paise: int) -> str:
    """Indian digit grouping: 10000000 paise -> ₹1,00,000."""
    r, p = divmod(int(paise), 100)
    s = str(r)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        s = ",".join(([head] if head else []) + groups) + "," + tail
    return f"₹{s}" + (f".{p:02d}" if p else "")


HI_MONTHS = ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"]


def fmt_date(d: date | datetime, lang: str = "en") -> str:
    return f"{d.day} {HI_MONTHS[d.month - 1]}" if lang == "hi" else f"{d.day} {d:%b}"


def render(template_id: str, lang: str, **values) -> str:
    return TEMPLATES[template_id][lang].format(**values)


def render_both(template_id: str, values_by_lang: dict[str, dict]) -> tuple[str, str]:
    return tuple(render(template_id, lang, **values_by_lang[lang]) for lang in ("en", "hi"))
