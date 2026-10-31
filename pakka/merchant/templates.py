"""Reviewed, static templates. No generated text reaches the merchant.

Every amount in a message is a lender ledger figure passed in as a placeholder.
"""
from datetime import date, datetime

from . import lang_pack as lp

LANGS = ("en", "hi") + lp.NEW_LANGS       # English, Hindi, Bengali, Odia, Telugu

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
    # "Can't pay today". Pakka explains the lender's own carry-forward; it never decides to skip a payment.
    "T_SKIP_ACK": {
        "en": "Okay. Today's amount will be collected from tomorrow's sales, as your lender's plan allows. "
              "{charges_note} Pay part now if you can: {link}",
        "hi": "ठीक है। आज की रकम कल की बिक्री से ली जाएगी, जैसा आपके लोन देने वाले का प्लान अनुमति देता है। "
              "{charges_note} हो सके तो अभी कुछ हिस्सा भर दें: {link}",  # HI: needs native review
    },
    "T_SKIP_NOTHING_DUE": {
        "en": "Today's payment to {lender} has already been taken from today's sales, so nothing is pending. "
              "If a day is slow, just tell us that day.",
        "hi": "{lender} की आज की किस्त आज की बिक्री से कट चुकी है, इसलिए कुछ बाकी नहीं है। "
              "जिस दिन धंधा धीमा हो, उसी दिन बता दीजिए।",  # HI: needs native review
    },
    "T_SKIP_ROUTED": {
        "en": "Your request has been sent to {lender}. They will decide and let you know. "
              "Until then, your current schedule stays the same.",
        "hi": "आपका अनुरोध {lender} को भेज दिया गया है। फ़ैसला वही करेंगे और आपको बताएँगे। "
              "तब तक आपका मौजूदा शेड्यूल वैसा ही रहेगा।",  # HI: needs native review
    },
    "T_SKIP_CALLBACK": {
        "en": "Is everything okay? A person from {lender} can help you plan this. Pick a time for a call below.",
        "hi": "सब ठीक है? {lender} से एक व्यक्ति इसकी योजना बनाने में आपकी मदद कर सकता है। "
              "नीचे कॉल का समय चुनिए।",  # HI: needs native review
    },
    "T_CALLBACK_BOOKED": {
        "en": "Booked. Someone from {lender} will call you at {time} on {date}. We'll remind you at that time.",
        "hi": "बुक हो गया। {lender} से कोई आपको {date} को {time} बजे कॉल करेगा। उसी समय हम आपको याद दिलाएँगे।",  # HI: needs native review
    },
    "T_REPEAT_OFFER": {
        "en": "You can view offers from lenders on the offers screen. Compare them before choosing.",
        "hi": "आप ऑफ़र स्क्रीन पर अलग-अलग लोन देने वालों के ऑफ़र देख सकते हैं। चुनने से पहले तुलना करें।",
    },
    # A payment the owner made through the pay link, confirmed with the lender's own figures.
    "T_PAYMENT_RECEIVED": {
        "en": "{lender} has received {amount} from you. Total due now: {overdue}.",
        "hi": "{lender} को आपसे {amount} मिल गए। अभी कुल बकाया: {overdue}।",  # HI: needs native review
    },
    "T_PAYMENT_ALL_CLEAR": {
        "en": "{lender} has received {amount} from you. You're all caught up. Thank you.",
        "hi": "{lender} को आपसे {amount} मिल गए। अब कुछ बकाया नहीं है। धन्यवाद।",  # HI: needs native review
    },
    # Optional recall lines filled from memory (context only; never changes the action).
    "T_RECALL_PENDING_REQUEST": {
        "en": "Last time you asked for {request}. It's still waiting for {lender}'s decision.",
        "hi": "पिछली बार आपका अनुरोध था: {request}। इस पर अभी {lender} का फ़ैसला बाकी है।",  # HI: needs native review
    },
    "T_RECALL_PAID": {
        "en": "Last time you said you'd pay the next day, and you did. Thank you.",
        "hi": "पिछली बार आपने कहा था कि अगले दिन भर देंगे, और आपने भर दिया। धन्यवाद।",  # HI: needs native review
    },
}

# Bengali, Odia and Telugu (lang_pack.py, needs native review): same ids, same placeholders.
SOUNDBOX_CUE.update(lp.SOUNDBOX_CUE)
for _tid, _texts in lp.TEMPLATES.items():
    if _tid != "T_SB_CUE":
        TEMPLATES[_tid].update(_texts)

REQUEST_NAMES = {
    "route_lower_deduction_request": {"en": "a lower daily deduction", "hi": "कम रोज़ाना कटौती"},
    "route_reschedule_request": {"en": "a new repayment date", "hi": "नई भुगतान तारीख"},
    "route_skip_request": {"en": "more time on one day's payment", "hi": "एक दिन की रकम के लिए समय"},  # HI: needs native review
}

for _action, _names in lp.REQUEST_NAMES.items():
    REQUEST_NAMES[_action].update(_names)

OPTIONS = {
    "T_SHORTFALL": ["pay_today", "pay_later", "skip_today", "lower_deduction", "reschedule", "callback", "already_paid"],
    "T_ARREARS": ["pay_today", "pay_later", "skip_today", "lower_deduction", "reschedule", "callback", "already_paid"],
    "T_SKIP_ACK": ["pay_today", "callback"],
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


# HI: needs native review (month names used in Hindi messages)
HI_MONTHS = ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"]


MONTHS = {"hi": HI_MONTHS, **lp.MONTHS}


def fmt_date(d: date | datetime, lang: str = "en") -> str:
    return f"{d.day} {MONTHS[lang][d.month - 1]}" if lang in MONTHS else f"{d.day} {d:%b}"


def render(template_id: str, lang: str, **values) -> str:
    return TEMPLATES[template_id][lang].format(**values)


def render_both(template_id: str, values_by_lang: dict[str, dict]) -> tuple[str, str]:
    return tuple(render(template_id, lang, **values_by_lang[lang]) for lang in ("en", "hi"))


def render_all(template_id: str, values_by_lang: dict[str, dict]) -> dict[str, str]:
    """The message in every supported language, from the same lender figures."""
    return {lang: render(template_id, lang, **values_by_lang[lang]) for lang in LANGS}
