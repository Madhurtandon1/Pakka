"""Reviewed messages for the loan document steps (PAN, Aadhaar OTP, selfie, bank, auto-pay).

Plain language, no generated text, never "rejected". Messages that depend on the cause are keyed
by (action, code); the rest by action. Every Hindi string here is marked for a native speaker
to check before real use.
"""

TEMPLATES = {
    "explain_pan_issue": {
        "en": "There's a problem with your PAN. Let's sort it out.",
        "hi": "आपके PAN में एक दिक्कत है। चलिए इसे ठीक करते हैं।",  # HI: needs native review
    },
    "guide_pan_aadhaar_link": {
        "en": "Your PAN needs to be linked to your Aadhaar. You can do it on the Income Tax e-filing website under 'Link Aadhaar'. It takes a few minutes, and your application stays saved.",
        "hi": "आपका PAN आपके आधार से लिंक होना ज़रूरी है। आप इसे इनकम टैक्स ई-फ़ाइलिंग वेबसाइट पर 'Link Aadhaar' में कर सकते हैं। इसमें कुछ मिनट लगते हैं, और आपका आवेदन सेव रहेगा।",  # HI: needs native review
    },
    "resend_otp_tips": {
        "en": "The OTP didn't arrive. Check that your phone has signal, wait a minute and tap 'Resend OTP'. You can also verify with DigiLocker instead.",
        "hi": "OTP नहीं आया। देख लीजिए फ़ोन में नेटवर्क है, एक मिनट रुकिए और 'OTP दोबारा भेजें' दबाइए। आप DigiLocker से भी पहचान की पुष्टि कर सकते हैं।",  # HI: needs native review
    },
    "switch_to_digilocker": {
        "en": "Let's verify with DigiLocker instead. Your Aadhaar details come straight from DigiLocker, so there's nothing to type.",
        "hi": "चलिए DigiLocker से पुष्टि करते हैं। आपकी आधार जानकारी सीधे DigiLocker से आएगी, कुछ टाइप नहीं करना पड़ेगा।",  # HI: needs native review
    },
    "offline_aadhaar_xml": {
        "en": "Another way: download your offline Aadhaar file (a ZIP) from the UIDAI website and upload it here with its share code.",
        "hi": "एक और तरीका: UIDAI वेबसाइट से अपनी ऑफ़लाइन आधार फ़ाइल (ZIP) डाउनलोड करें और उसके शेयर कोड के साथ यहाँ अपलोड करें।",  # HI: needs native review
    },
    "face_match_tips": {
        "en": "Your selfie didn't match the photo on your ID. Face the camera in good light, without glasses or a mask, and try again.",
        "hi": "आपकी सेल्फ़ी ID की फ़ोटो से मेल नहीं खाई। अच्छी रोशनी में, बिना चश्मे या मास्क के, कैमरे की तरफ़ देखकर दोबारा कोशिश कीजिए।",  # HI: needs native review
    },
    "guided_selfie_retake": {
        "en": "Let's retake the selfie together: keep your face inside the circle and hold still for two seconds.",
        "hi": "चलिए साथ में सेल्फ़ी दोबारा लेते हैं: चेहरा गोले के अंदर रखिए और दो सेकंड स्थिर रहिए।",  # HI: needs native review
    },
    "explain_bank_issue": {
        "en": "We couldn't confirm your bank account. Let's check the details.",
        "hi": "हम आपके बैंक खाते की पुष्टि नहीं कर पाए। चलिए जानकारी जाँचते हैं।",  # HI: needs native review
    },
    "reenter_bank_details": {
        "en": "Please type your account number and IFSC again. You'll find the IFSC on your cheque book or passbook.",
        "hi": "कृपया अपना खाता नंबर और IFSC दोबारा लिखिए। IFSC आपकी चेकबुक या पासबुक पर मिलेगा।",  # HI: needs native review
    },
    "try_another_account": {
        "en": "You can add a different savings account in your own name instead.",
        "hi": "आप इसकी जगह अपने नाम का कोई दूसरा बचत खाता जोड़ सकते हैं।",  # HI: needs native review
    },
    "explain_mandate_issue": {
        "en": "Auto-pay couldn't be set up. Auto-pay takes your EMI on the due date, so you never miss one.",
        "hi": "ऑटो-पे सेट नहीं हो पाया। ऑटो-पे तय तारीख पर आपकी EMI काट लेता है, ताकि कोई EMI न छूटे।",  # HI: needs native review
    },
    "switch_mandate_method": {
        "en": "Let's switch the auto-pay method. Pick net banking, a debit card or UPI AutoPay below. Most banks support at least one.",
        "hi": "चलिए ऑटो-पे का तरीका बदलते हैं। नीचे नेट बैंकिंग, डेबिट कार्ड या UPI AutoPay चुनिए। ज़्यादातर बैंक इनमें से कम से कम एक सपोर्ट करते हैं।",  # HI: needs native review
    },
    "try_another_bank": {
        "en": "You can set up auto-pay from another bank account in your name.",
        "hi": "आप अपने नाम के किसी दूसरे बैंक खाते से ऑटो-पे सेट कर सकते हैं।",  # HI: needs native review
    },
}

# Cause-specific wording for the "explain" actions.
CODE_TEMPLATES = {
    ("explain_pan_issue", "PAN_FORMAT"): {
        "en": "The PAN number doesn't look right. It should be 5 letters, 4 numbers, then 1 letter, like ABCDE1234F.",
        "hi": "PAN नंबर सही नहीं लग रहा। इसमें पहले 5 अक्षर, फिर 4 अंक, फिर 1 अक्षर होता है, जैसे ABCDE1234F।",  # HI: needs native review
    },
    ("explain_pan_issue", "PAN_NOT_LINKED"): {
        "en": "Your PAN isn't linked to your Aadhaar yet. The lender needs them linked before it can continue.",
        "hi": "आपका PAN अभी आपके आधार से लिंक नहीं है। आगे बढ़ने के लिए दोनों का लिंक होना ज़रूरी है।",  # HI: needs native review
    },
    ("explain_pan_issue", "NAME_MISMATCH"): {
        "en": "The name on your PAN and your Aadhaar don't match. A person will help you fix this.",
        "hi": "आपके PAN और आधार पर नाम मेल नहीं खाते। एक व्यक्ति इसे ठीक करने में आपकी मदद करेगा।",  # HI: needs native review
    },
    ("explain_bank_issue", "IFSC_FORMAT"): {
        "en": "The IFSC doesn't look right. It has 11 characters: 4 letters, then 0, then 6 letters or numbers, like SBIN0001234.",
        "hi": "IFSC सही नहीं लग रहा। इसमें 11 अक्षर होते हैं: 4 अक्षर, फिर 0, फिर 6 अक्षर या अंक, जैसे SBIN0001234।",  # HI: needs native review
    },
    ("explain_bank_issue", "ACCOUNT_NAME_MISMATCH"): {
        "en": "The name on this bank account doesn't match your PAN. The loan can only go to an account in your own name.",
        "hi": "इस बैंक खाते का नाम आपके PAN से मेल नहीं खाता। लोन सिर्फ़ आपके अपने नाम वाले खाते में जा सकता है।",  # HI: needs native review
    },
    ("explain_bank_issue", "PENNY_DROP_FAILED"): {
        "en": "We sent ₹1 to check your account, but it didn't go through. The account may be closed or the details may be wrong.",
        "hi": "खाता जाँचने के लिए हमने ₹1 भेजा, पर वह नहीं पहुँचा। हो सकता है खाता बंद हो या जानकारी गलत हो।",  # HI: needs native review
    },
    ("explain_mandate_issue", "MANDATE_BANK_UNSUPPORTED"): {
        "en": "Your bank doesn't support this auto-pay method. You can try net banking, a debit card or UPI AutoPay.",
        "hi": "आपका बैंक यह ऑटो-पे तरीका सपोर्ट नहीं करता। आप नेट बैंकिंग, डेबिट कार्ड या UPI AutoPay आज़मा सकते हैं।",  # HI: needs native review
    },
    ("explain_mandate_issue", "MANDATE_OTP_TIMEOUT"): {
        "en": "The bank's OTP for auto-pay timed out. Keep the bank page open and enter the OTP within a few minutes.",
        "hi": "ऑटो-पे के लिए बैंक का OTP समय पर नहीं डाला गया। बैंक का पेज खुला रखिए और कुछ मिनट के अंदर OTP डालिए।",  # HI: needs native review
    },
    ("explain_mandate_issue", "NO_DEBIT_CARD"): {
        "en": "Debit card auto-pay needs a debit card for this account. You can use net banking or UPI AutoPay instead.",
        "hi": "डेबिट कार्ड से ऑटो-पे के लिए इस खाते का डेबिट कार्ड चाहिए। आप नेट बैंकिंग या UPI AutoPay इस्तेमाल कर सकते हैं।",  # HI: needs native review
    },
}

STEP_NAMES = {
    "en": {"pan": "PAN", "selfie": "selfie", "mandate": "auto-pay setup"},
    "hi": {"pan": "PAN", "selfie": "सेल्फ़ी", "mandate": "ऑटो-पे सेटअप"},  # HI: needs native review
}
