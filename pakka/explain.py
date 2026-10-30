STEP_NAMES = {
    "en": {"basic": "basic details", "kyc": "KYC", "offer": "loan offer", "bank": "bank details", "review": "review"},
    "hi": {"basic": "बुनियादी जानकारी", "kyc": "KYC", "offer": "लोन ऑफ़र", "bank": "बैंक विवरण", "review": "रिव्यू"},
}

PHOTO_REASONS = {
    "en": {
        "IMG_CROPPED": "a corner of the card was cut off",
        "IMG_BLUR": "the photo was blurry",
        "IMG_GLARE": "there was glare on the card",
        "NOT_AADHAAR": "it didn't look like an Aadhaar card",
        "AADHAAR_BACK": "it showed the back of the card, and we need the front",
        "AADHAAR_UNREADABLE": "the Aadhaar number couldn't be read clearly",
    },
    "hi": {
        "IMG_CROPPED": "कार्ड का एक कोना कट जाने",
        "IMG_BLUR": "फ़ोटो धुंधली होने",
        "IMG_GLARE": "कार्ड पर चमक होने",
        "NOT_AADHAAR": "आधार कार्ड जैसी न दिखने",
        "AADHAAR_BACK": "कार्ड का पिछला हिस्सा होने (हमें सामने वाला हिस्सा चाहिए)",
        "AADHAAR_UNREADABLE": "आधार नंबर साफ़ न पढ़ा जा सकने",
    },
}

KFS_TERMS = {
    "apr": {
        "en": "APR (Annual Percentage Rate): the yearly cost of the loan, interest and fees together, as a percentage.",
        "hi": "APR (सालाना प्रतिशत दर): ब्याज और शुल्क मिलाकर लोन की सालाना कुल लागत, प्रतिशत में।",
    },
    "emi": {
        "en": "EMI: the fixed amount you pay every month until the loan is repaid.",
        "hi": "EMI: हर महीने चुकाई जाने वाली तय रकम, जब तक लोन पूरा न हो जाए।",
    },
    "processing_fee": {
        "en": "Processing fee: a one-time charge for processing your loan. It is counted in the APR.",
        "hi": "प्रोसेसिंग शुल्क: लोन प्रोसेस करने के लिए एक बार लगने वाला शुल्क। यह APR में गिना जाता है।",
    },
    "cooling_off": {
        "en": "Cooling-off period: a window after you take the loan when you can return it without a penalty. You pay only for the days used and any disclosed processing fee.",
        "hi": "कूलिंग-ऑफ़ अवधि: लोन लेने के बाद का समय जिसमें आप बिना जुर्माने के लोन लौटा सकते हैं। सिर्फ़ इस्तेमाल किए गए दिनों का खर्च और बताया गया प्रोसेसिंग शुल्क लगता है।",
    },
    "penal_charges": {
        "en": "Penal charges: extra charges if you miss or delay an EMI.",
        "hi": "पेनल चार्ज: EMI चूकने या देर से भरने पर लगने वाला अतिरिक्त शुल्क।",
    },
    "foreclosure": {
        "en": "Foreclosure: paying off the whole loan early. Some loans charge for this, and the KFS says if yours does.",
        "hi": "फ़ोरक्लोज़र: पूरा लोन समय से पहले चुका देना। कुछ लोन में इसका शुल्क लगता है, और KFS में लिखा होता है।",
    },
}

TEMPLATES = {
    "guided_recapture": {
        "en": "Your Aadhaar photo didn't go through because {reason}. Let's retake it together: keep all four corners of the card inside the frame.",
        "hi": "आपकी आधार फ़ोटो {reason} की वजह से नहीं गई। चलिए साथ में दोबारा लेते हैं: कार्ड के चारों कोने फ्रेम के अंदर रखिए।",
    },
    "convert_file": {
        "en": "That file type isn't accepted here. Please upload a photo of the front of your Aadhaar card (JPG or PNG). If you have the e-Aadhaar PDF, a screenshot of it works too.",
        "hi": "यह फ़ाइल टाइप यहाँ स्वीकार नहीं होता। कृपया अपने आधार कार्ड के सामने वाले हिस्से की फ़ोटो (JPG या PNG) अपलोड करें। अगर आपके पास ई-आधार PDF है, तो उसका स्क्रीनशॉट भी चलेगा।",
    },
    "retry_liveness_tips": {
        "en": "The face check didn't pass. Sit in good light, take off your glasses and hold the phone at eye level, then try once more.",
        "hi": "चेहरे की जाँच पूरी नहीं हुई। अच्छी रोशनी में बैठिए, चश्मा उतारिए और फ़ोन आँखों के सामने रखिए, फिर एक बार और कोशिश कीजिए।",
    },
    "switch_to_video_kyc": {
        "en": "Let's try video KYC instead. An agent will verify you on a short video call.",
        "hi": "चलिए वीडियो KYC से करते हैं। एक एजेंट छोटी वीडियो कॉल पर आपकी पहचान की पुष्टि करेगा।",
    },
    "digilocker_setup_help": {
        "en": "You don't have a DigiLocker account yet. You can create one with your Aadhaar number and an OTP. Want me to walk you through it?",
        "hi": "आपका DigiLocker खाता अभी नहीं है। इसे आधार नंबर और OTP से बनाया जा सकता है। क्या मैं आपको स्टेप बताऊँ?",
    },
    "explain_kfs": {
        "en": "Before you accept, here's what the key terms in your Key Fact Statement mean:",
        "hi": "स्वीकार करने से पहले, आपके Key Fact Statement के ज़रूरी शब्दों का मतलब:",
    },
    "send_resume_link": {
        "en": "Your application is saved at the {step} step. Here's a link to pick up where you left off.",
        "hi": "आपका आवेदन {step} वाले स्टेप पर सेव है। जहाँ छोड़ा था, वहीं से शुरू करने के लिए यह लिंक है।",
    },
    "schedule_callback": {
        "en": "Would you like a call from our team at a time that suits you?",
        "hi": "क्या आप अपनी सुविधा के समय पर हमारी टीम से कॉल चाहेंगे?",
    },
    "human_handoff": {
        "en": "I'm connecting you to someone from our team. They'll see everything so far, so you won't have to repeat yourself.",
        "hi": "मैं आपको हमारी टीम के एक व्यक्ति से जोड़ रहा हूँ। उन्हें अब तक की पूरी जानकारी दिखेगी, आपको कुछ दोहराना नहीं पड़ेगा।",
    },
}

GENERIC_REASON = {"en": "the photo couldn't be read", "hi": "फ़ोटो पढ़ी न जा सकने"}


def explain(action: str, lang: str = "en", step: str | None = None, code: str | None = None) -> str:
    lang = lang if lang in ("en", "hi") else "en"
    text = TEMPLATES[action][lang]
    reason = PHOTO_REASONS[lang].get(code or "", GENERIC_REASON[lang])
    text = text.format(reason=reason, step=STEP_NAMES[lang].get(step or "", step or ""))
    if action == "explain_kfs":
        text += "\n" + "\n".join(f"• {t[lang]}" for t in KFS_TERMS.values())
    return text


def kfs_term(term: str, lang: str = "en") -> str | None:
    entry = KFS_TERMS.get(term.lower())
    return entry[lang if lang in ("en", "hi") else "en"] if entry else None
