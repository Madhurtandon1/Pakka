"""Bengali (bn), Odia (od) and Telugu (te) for the merchant journey.

Every string here is a first draft written for the demo and MUST be checked by a native speaker
before real use (each line is marked "needs native review"). Messages stay pre-written: nothing is
generated or translated live. Placeholders ({lender}, {amount}, ...) are identical to the English.
Sarvam supports all three for voice (Bulbul), speech-to-text (Saaras) and translation.
"""

NEW_LANGS = ("bn", "od", "te")
LANG_NAMES = {"en": "English", "hi": "हिंदी", "bn": "বাংলা", "od": "ଓଡ଼ିଆ", "te": "తెలుగు"}  # language names in their own script: needs native review

# ---- the only thing the Soundbox may say (checked by G5: no digits, no money or loan words)
SOUNDBOX_CUE = {
    "bn": "আপনার Paytm for Business অ্যাপে একটি জরুরি বার্তা আছে।",  # BN: needs native review
    "od": "ଆପଣଙ୍କ Paytm for Business ଆପରେ ଏକ ଜରୁରୀ ବାର୍ତ୍ତା ଅଛି।",  # OD: needs native review
    "te": "మీ Paytm for Business యాప్‌లో ఒక ముఖ్యమైన సందేశం ఉంది.",  # TE: needs native review
}

PENAL_NOTE = {
    "bn": "চার্জ আপনার লোনের Key Fact Statement অনুযায়ী",  # BN: needs native review
    "od": "ଚାର୍ଜ ଆପଣଙ୍କ ଲୋନର Key Fact Statement ଅନୁସାରେ",  # OD: needs native review
    "te": "ఛార్జీలు మీ లోన్ Key Fact Statement ప్రకారం",  # TE: needs native review
}
CHARGES_NOTE = {
    "bn": "চার্জ আপনার লোন চুক্তি অনুযায়ী।",  # BN: needs native review
    "od": "ଚାର୍ଜ ଆପଣଙ୍କ ଲୋନ ଚୁକ୍ତି ଅନୁସାରେ।",  # OD: needs native review
    "te": "ఛార్జీలు మీ లోన్ ఒప్పందం ప్రకారం.",  # TE: needs native review
}
MONTHS = {
    "bn": ["জানুয়ারি", "ফেব্রুয়ারি", "মার্চ", "এপ্রিল", "মে", "জুন", "জুলাই", "আগস্ট", "সেপ্টেম্বর", "অক্টোবর", "নভেম্বর", "ডিসেম্বর"],  # BN: needs native review
    "od": ["ଜାନୁଆରୀ", "ଫେବୃଆରୀ", "ମାର୍ଚ୍ଚ", "ଅପ୍ରେଲ", "ମେ", "ଜୁନ", "ଜୁଲାଇ", "ଅଗଷ୍ଟ", "ସେପ୍ଟେମ୍ବର", "ଅକ୍ଟୋବର", "ନଭେମ୍ବର", "ଡିସେମ୍ବର"],  # OD: needs native review
    "te": ["జనవరి", "ఫిబ్రవరి", "మార్చి", "ఏప్రిల్", "మే", "జూన్", "జూలై", "ఆగస్టు", "సెప్టెంబర్", "అక్టోబర్", "నవంబర్", "డిసెంబర్"],  # TE: needs native review
}
REQUEST_NAMES = {
    "route_lower_deduction_request": {
        "bn": "রোজকার কাটা টাকা কমানো",  # BN: needs native review
        "od": "ଦୈନିକ କଟା କମାଇବା",  # OD: needs native review
        "te": "రోజువారీ కోత తగ్గించడం",  # TE: needs native review
    },
    "route_reschedule_request": {
        "bn": "নতুন পরিশোধের তারিখ",  # BN: needs native review
        "od": "ନୂଆ ପରିଶୋଧ ତାରିଖ",  # OD: needs native review
        "te": "కొత్త చెల్లింపు తేదీ",  # TE: needs native review
    },
    "route_skip_request": {
        "bn": "এক দিনের টাকার জন্য সময়",  # BN: needs native review
        "od": "ଗୋଟିଏ ଦିନର ଟଙ୍କା ପାଇଁ ସମୟ",  # OD: needs native review
        "te": "ఒక రోజు మొత్తానికి సమయం",  # TE: needs native review
    },
}

# ---- every merchant message (same placeholders as English)
TEMPLATES = {
    "T_SB_CUE": SOUNDBOX_CUE,
    "T_SHORTFALL": {
        "bn": "আজকের বিক্রি থেকে {lender}-এর রোজকার কিস্তি পুরো কাটা যায়নি। আজ কম: {shortfall}। এখন মোট বাকি: {overdue}, {oldest} থেকে। {penal_note}। আপনি এখন দিতে পারেন, পরে দিতে পারেন, {lender}-এর কাছে কম কাটা বা নতুন তারিখ চাইতে পারেন, বা কল চাইতে পারেন।",  # BN: needs native review
        "od": "ଆଜିର ବିକ୍ରିରୁ {lender}ର ଦୈନିକ କିସ୍ତି ପୂରା କଟିନାହିଁ। ଆଜି କମ୍: {shortfall}। ବର୍ତ୍ତମାନ ମୋଟ ବାକି: {overdue}, {oldest}ରୁ। {penal_note}। ଆପଣ ଏବେ ଦେଇପାରିବେ, ପରେ ଦେଇପାରିବେ, {lender}ଙ୍କୁ କମ୍ କଟା ବା ନୂଆ ତାରିଖ ମାଗିପାରିବେ, କିମ୍ବା କଲ୍ ମାଗିପାରିବେ।",  # OD: needs native review
        "te": "ఈరోజు అమ్మకాల నుండి {lender}కి మీ రోజువారీ వాయిదా పూర్తిగా కట్ కాలేదు. ఈరోజు తక్కువ: {shortfall}. ఇప్పుడు మొత్తం బాకీ: {overdue}, {oldest} నుండి. {penal_note}. మీరు ఇప్పుడు కట్టవచ్చు, తర్వాత కట్టవచ్చు, {lender}ని తక్కువ కోత లేదా కొత్త తేదీ అడగవచ్చు, లేదా కాల్ అడగవచ్చు.",  # TE: needs native review
    },
    "T_ARREARS": {
        "bn": "{lender}-এর আপনার রোজকার কিস্তি পিছিয়ে আছে। এখন মোট বাকি: {overdue}, {oldest} থেকে। {penal_note}। আপনি এখন দিতে পারেন, পরে দিতে পারেন, {lender}-এর কাছে কম কাটা বা নতুন তারিখ চাইতে পারেন, বা কল চাইতে পারেন।",  # BN: needs native review
        "od": "{lender}ର ଆପଣଙ୍କ ଦୈନିକ କିସ୍ତି ପଛରେ ଅଛି। ବର୍ତ୍ତମାନ ମୋଟ ବାକି: {overdue}, {oldest}ରୁ। {penal_note}। ଆପଣ ଏବେ ଦେଇପାରିବେ, ପରେ ଦେଇପାରିବେ, {lender}ଙ୍କୁ କମ୍ କଟା ବା ନୂଆ ତାରିଖ ମାଗିପାରିବେ, କିମ୍ବା କଲ୍ ମାଗିପାରିବେ।",  # OD: needs native review
        "te": "{lender}కి మీ రోజువారీ వాయిదాలు వెనుకబడి ఉన్నాయి. ఇప్పుడు మొత్తం బాకీ: {overdue}, {oldest} నుండి. {penal_note}. మీరు ఇప్పుడు కట్టవచ్చు, తర్వాత కట్టవచ్చు, {lender}ని తక్కువ కోత లేదా కొత్త తేదీ అడగవచ్చు, లేదా కాల్ అడగవచ్చు.",  # TE: needs native review
    },
    "T_DIP_RISK": {
        "bn": "গত {window} দিনে আপনার গড় রোজকার বিক্রি {avg}, যা {lender}-এর রোজকার কিস্তি {edi}-এর কাছাকাছি। এখনও কিছু বাকি নেই। সামনে মন্দা আসলে {lender}-এর কাছে কম কাটা চাইতে পারেন, বা কল চাইতে পারেন।",  # BN: needs native review
        "od": "ଗତ {window} ଦିନରେ ଆପଣଙ୍କ ହାରାହାରି ଦୈନିକ ବିକ୍ରି {avg}, ଯାହା {lender}ର ଦୈନିକ କିସ୍ତି {edi} ପାଖାପାଖି। ଏପର୍ଯ୍ୟନ୍ତ କିଛି ବାକି ନାହିଁ। ଆଗକୁ ବେପାର ଧୀମା ହେଲେ {lender}ଙ୍କୁ କମ୍ କଟା ମାଗିପାରିବେ, କିମ୍ବା କଲ୍ ମାଗିପାରିବେ।",  # OD: needs native review
        "te": "గత {window} రోజుల్లో మీ సగటు రోజువారీ అమ్మకాలు {avg}, ఇది {lender}కి రోజువారీ వాయిదా {edi}కి దగ్గరగా ఉంది. ఇంకా ఏమీ బాకీ లేదు. ముందు వ్యాపారం నెమ్మదిగా ఉంటే {lender}ని తక్కువ కోత అడగవచ్చు, లేదా కాల్ అడగవచ్చు.",  # TE: needs native review
    },
    "T_PAY_LINK": {
        "bn": "সরাসরি {lender}-কে {amount} দিন: {link}। টাকা {lender}-এর অ্যাকাউন্টে যাবে।",  # BN: needs native review
        "od": "ସିଧାସଳଖ {lender}ଙ୍କୁ {amount} ଦିଅନ୍ତୁ: {link}। ଟଙ୍କା {lender}ଙ୍କ ଆକାଉଣ୍ଟକୁ ଯିବ।",  # OD: needs native review
        "te": "నేరుగా {lender}కి {amount} కట్టండి: {link}. డబ్బు {lender} ఖాతాకు వెళ్తుంది.",  # TE: needs native review
    },
    "T_PAY_CHOICE": {
        "bn": "শুধু আজকের কম {short_amount} দিতে পারেন: {short_link}\nঅথবা মোট বাকি {amount} দিন: {link}\nদুটোই সরাসরি {lender}-এর অ্যাকাউন্টে যায়।",  # BN: needs native review
        "od": "କେବଳ ଆଜିର କମ୍ {short_amount} ଦେଇପାରିବେ: {short_link}\nକିମ୍ବା ମୋଟ ବାକି {amount} ଦିଅନ୍ତୁ: {link}\nଦୁଇଟି ସିଧାସଳଖ {lender}ଙ୍କ ଆକାଉଣ୍ଟକୁ ଯାଏ।",  # OD: needs native review
        "te": "ఈరోజు తక్కువైన {short_amount} మాత్రమే కట్టవచ్చు: {short_link}\nలేదా మొత్తం బాకీ {amount} కట్టండి: {link}\nరెండూ నేరుగా {lender} ఖాతాకు వెళ్తాయి.",  # TE: needs native review
    },
    "T_REMINDER_SET": {
        "bn": "ঠিক আছে। {date} তারিখে {time}-এ মনে করিয়ে দেব। তৈরি হলে এখানে {lender}-কে দিন: {link}",  # BN: needs native review
        "od": "ଠିକ୍ ଅଛି। {date}ରେ {time}ରେ ମନେ ପକାଇଦେବି। ପ୍ରସ୍ତୁତ ହେଲେ ଏଠାରେ {lender}ଙ୍କୁ ଦିଅନ୍ତୁ: {link}",  # OD: needs native review
        "te": "సరే. {date}న {time}కి మీకు గుర్తు చేస్తాను. సిద్ధమైనప్పుడు ఇక్కడ {lender}కి కట్టండి: {link}",  # TE: needs native review
    },
    "T_REQ_ROUTED": {
        "bn": "{request}-এর জন্য আপনার অনুরোধ {lender}-কে পাঠানো হয়েছে। সিদ্ধান্ত তারাই নেবে এবং আপনাকে জানাবে। ততদিন আপনার এখনকার সময়সূচি একই থাকবে।",  # BN: needs native review
        "od": "{request} ପାଇଁ ଆପଣଙ୍କ ଅନୁରୋଧ {lender}ଙ୍କୁ ପଠାଯାଇଛି। ସେମାନେ ନିଷ୍ପତ୍ତି ନେଇ ଆପଣଙ୍କୁ ଜଣାଇବେ। ସେ ପର୍ଯ୍ୟନ୍ତ ଆପଣଙ୍କ ବର୍ତ୍ତମାନର ସୂଚୀ ସମାନ ରହିବ।",  # OD: needs native review
        "te": "{request} కోసం మీ అభ్యర్థన {lender}కి పంపబడింది. వారే నిర్ణయించి మీకు తెలియజేస్తారు. అప్పటి వరకు మీ ప్రస్తుత షెడ్యూల్ అలాగే ఉంటుంది.",  # TE: needs native review
    },
    "T_CALLBACK": {
        "bn": "{lender} থেকে কেউ {date} তারিখে {time}-এ আপনাকে ফোন করবে।",  # BN: needs native review
        "od": "{lender}ରୁ କେହି {date}ରେ {time}ରେ ଆପଣଙ୍କୁ ଫୋନ୍ କରିବେ।",  # OD: needs native review
        "te": "{lender} నుండి ఎవరైనా {date}న {time}కి మీకు ఫోన్ చేస్తారు.",  # TE: needs native review
    },
    "T_HANDOFF": {
        "bn": "{lender} থেকে একজন মানুষ আপনার সঙ্গে যোগাযোগ করবেন। তিনি এই কথোপকথন দেখতে পাবেন, তাই আবার বলতে হবে না। অভিযোগ আধিকারিক: {officer}। আপনি বিনামূল্যে ঋণ পরামর্শও চাইতে পারেন।",  # BN: needs native review
        "od": "{lender}ରୁ ଜଣେ ବ୍ୟକ୍ତି ଆପଣଙ୍କ ସହ ଯୋଗାଯୋଗ କରିବେ। ସେ ଏହି କଥାବାର୍ତ୍ତା ଦେଖିପାରିବେ, ତେଣୁ ପୁଣି କହିବାକୁ ପଡ଼ିବ ନାହିଁ। ଅଭିଯୋଗ ଅଧିକାରୀ: {officer}। ଆପଣ ମାଗଣା ଋଣ ପରାମର୍ଶ ମଧ୍ୟ ମାଗିପାରିବେ।",  # OD: needs native review
        "te": "{lender} నుండి ఒక వ్యక్తి మిమ్మల్ని సంప్రదిస్తారు. వారు ఈ సంభాషణ చూస్తారు, కాబట్టి మళ్ళీ చెప్పనక్కర్లేదు. ఫిర్యాదుల అధికారి: {officer}. మీరు ఉచిత రుణ సలహా కూడా అడగవచ్చు.",  # TE: needs native review
    },
    "T_CURED": {
        "bn": "ধন্যবাদ। {lender}-এর আপনার কিস্তি এখন পুরো জমা আছে।",  # BN: needs native review
        "od": "ଧନ୍ୟବାଦ। {lender}ର ଆପଣଙ୍କ କିସ୍ତି ଏବେ ପୂରା ଅଛି।",  # OD: needs native review
        "te": "ధన్యవాదాలు. {lender}కి మీ వాయిదాలు ఇప్పుడు పూర్తిగా కట్టబడ్డాయి.",  # TE: needs native review
    },
    "T_SKIP_ACK": {
        "bn": "ঠিক আছে। আপনার লোনদাতার প্ল্যান অনুযায়ী আজকের টাকা কালকের বিক্রি থেকে কাটা হবে। {charges_note} পারলে এখন কিছুটা দিন: {link}",  # BN: needs native review
        "od": "ଠିକ୍ ଅଛି। ଆପଣଙ୍କ ଋଣଦାତାଙ୍କ ପ୍ଲାନ ଅନୁସାରେ ଆଜିର ଟଙ୍କା କାଲିର ବିକ୍ରିରୁ କଟାଯିବ। {charges_note} ପାରିଲେ ଏବେ କିଛି ଦିଅନ୍ତୁ: {link}",  # OD: needs native review
        "te": "సరే. మీ రుణదాత ప్లాన్ ప్రకారం ఈరోజు మొత్తం రేపటి అమ్మకాల నుండి తీసుకోబడుతుంది. {charges_note} వీలైతే ఇప్పుడు కొంత కట్టండి: {link}",  # TE: needs native review
    },
    "T_SKIP_NOTHING_DUE": {
        "bn": "{lender}-এর আজকের কিস্তি আজকের বিক্রি থেকে কাটা হয়ে গেছে, তাই কিছু বাকি নেই। যেদিন বিক্রি কম হবে, সেদিন জানাবেন।",  # BN: needs native review
        "od": "{lender}ର ଆଜିର କିସ୍ତି ଆଜିର ବିକ୍ରିରୁ କଟିସାରିଛି, ତେଣୁ କିଛି ବାକି ନାହିଁ। ଯେଉଁଦିନ ବିକ୍ରି କମ୍ ହେବ, ସେହିଦିନ ଜଣାନ୍ତୁ।",  # OD: needs native review
        "te": "{lender}కి ఈరోజు వాయిదా ఈరోజు అమ్మకాల నుండి కట్ అయింది, కాబట్టి ఏమీ బాకీ లేదు. అమ్మకాలు తక్కువైన రోజే మాకు చెప్పండి.",  # TE: needs native review
    },
    "T_SKIP_ROUTED": {
        "bn": "আপনার অনুরোধ {lender}-কে পাঠানো হয়েছে। সিদ্ধান্ত তারাই নেবে এবং জানাবে। ততদিন আপনার এখনকার সময়সূচি একই থাকবে।",  # BN: needs native review
        "od": "ଆପଣଙ୍କ ଅନୁରୋଧ {lender}ଙ୍କୁ ପଠାଯାଇଛି। ସେମାନେ ନିଷ୍ପତ୍ତି ନେଇ ଜଣାଇବେ। ସେ ପର୍ଯ୍ୟନ୍ତ ଆପଣଙ୍କ ବର୍ତ୍ତମାନର ସୂଚୀ ସମାନ ରହିବ।",  # OD: needs native review
        "te": "మీ అభ్యర్థన {lender}కి పంపబడింది. వారే నిర్ణయించి తెలియజేస్తారు. అప్పటి వరకు మీ ప్రస్తుత షెడ్యూల్ అలాగే ఉంటుంది.",  # TE: needs native review
    },
    "T_SKIP_CALLBACK": {
        "bn": "সব ঠিক আছে তো? {lender} থেকে একজন মানুষ এটা পরিকল্পনা করতে সাহায্য করতে পারেন। নিচে কলের সময় বেছে নিন।",  # BN: needs native review
        "od": "ସବୁ ଠିକ୍ ଅଛି ତ? {lender}ରୁ ଜଣେ ବ୍ୟକ୍ତି ଏହା ଯୋଜନା କରିବାରେ ସାହାଯ୍ୟ କରିପାରିବେ। ତଳେ କଲ୍ ସମୟ ବାଛନ୍ତୁ।",  # OD: needs native review
        "te": "అంతా బాగానే ఉందా? {lender} నుండి ఒక వ్యక్తి దీన్ని ప్లాన్ చేయడంలో సహాయం చేయగలరు. కింద కాల్ సమయం ఎంచుకోండి.",  # TE: needs native review
    },
    "T_CALLBACK_BOOKED": {
        "bn": "বুক হয়ে গেছে। {lender} থেকে কেউ {date} তারিখে {time}-এ ফোন করবে। সেই সময় আমরা মনে করিয়ে দেব।",  # BN: needs native review
        "od": "ବୁକ୍ ହୋଇଗଲା। {lender}ରୁ କେହି {date}ରେ {time}ରେ ଫୋନ୍ କରିବେ। ସେହି ସମୟରେ ଆମେ ମନେ ପକାଇଦେବୁ।",  # OD: needs native review
        "te": "బుక్ అయింది. {lender} నుండి ఎవరైనా {date}న {time}కి ఫోన్ చేస్తారు. ఆ సమయానికి మేము గుర్తు చేస్తాం.",  # TE: needs native review
    },
    "T_REPEAT_OFFER": {
        "bn": "অফার স্ক্রিনে বিভিন্ন লোনদাতার অফার দেখতে পারেন। বেছে নেওয়ার আগে তুলনা করুন।",  # BN: needs native review
        "od": "ଅଫର ସ୍କ୍ରିନରେ ବିଭିନ୍ନ ଋଣଦାତାଙ୍କ ଅଫର ଦେଖିପାରିବେ। ବାଛିବା ପୂର୍ବରୁ ତୁଳନା କରନ୍ତୁ।",  # OD: needs native review
        "te": "ఆఫర్ల స్క్రీన్‌లో వివిధ రుణదాతల ఆఫర్లు చూడవచ్చు. ఎంచుకునే ముందు పోల్చి చూడండి.",  # TE: needs native review
    },
    "T_PAYMENT_RECEIVED": {
        "bn": "{lender} আপনার কাছ থেকে {amount} পেয়েছে। এখন মোট বাকি: {overdue}।",  # BN: needs native review
        "od": "{lender} ଆପଣଙ୍କ ଠାରୁ {amount} ପାଇଛନ୍ତି। ବର୍ତ୍ତମାନ ମୋଟ ବାକି: {overdue}।",  # OD: needs native review
        "te": "{lender}కి మీ నుండి {amount} అందింది. ఇప్పుడు మొత్తం బాకీ: {overdue}.",  # TE: needs native review
    },
    "T_PAYMENT_ALL_CLEAR": {
        "bn": "{lender} আপনার কাছ থেকে {amount} পেয়েছে। এখন আর কিছু বাকি নেই। ধন্যবাদ।",  # BN: needs native review
        "od": "{lender} ଆପଣଙ୍କ ଠାରୁ {amount} ପାଇଛନ୍ତି। ଏବେ ଆଉ କିଛି ବାକି ନାହିଁ। ଧନ୍ୟବାଦ।",  # OD: needs native review
        "te": "{lender}కి మీ నుండి {amount} అందింది. ఇప్పుడు ఏమీ బాకీ లేదు. ధన్యవాదాలు.",  # TE: needs native review
    },
    "T_RECALL_PENDING_REQUEST": {
        "bn": "গতবার আপনি চেয়েছিলেন: {request}। এটা এখনও {lender}-এর সিদ্ধান্তের অপেক্ষায়।",  # BN: needs native review
        "od": "ଗତ ଥର ଆପଣ ମାଗିଥିଲେ: {request}। ଏହା ଏବେବି {lender}ଙ୍କ ନିଷ୍ପତ୍ତି ଅପେକ୍ଷାରେ।",  # OD: needs native review
        "te": "గతసారి మీరు అడిగారు: {request}. అది ఇంకా {lender} నిర్ణయం కోసం ఎదురుచూస్తోంది.",  # TE: needs native review
    },
    "T_RECALL_PAID": {
        "bn": "গতবার আপনি বলেছিলেন পরের দিন দেবেন, আর দিয়েছিলেনও। ধন্যবাদ।",  # BN: needs native review
        "od": "ଗତ ଥର ଆପଣ କହିଥିଲେ ପରଦିନ ଦେବେ, ଆଉ ଦେଇଥିଲେ। ଧନ୍ୟବାଦ।",  # OD: needs native review
        "te": "గతసారి మీరు మరుసటి రోజు కడతానన్నారు, కట్టారు కూడా. ధన్యవాదాలు.",  # TE: needs native review
    },
}

# ---- what each quick-reply button says (the classifier must understand these: tested)
SAY = {
    "bn": {"pay_today": "এখনই দিয়ে দেব", "pay_later": "কাল দিয়ে দেব", "skip_today": "আজ দিতে পারব না, কাল কেটে নিন",
           "lower_deduction": "একটু কম কাটুন", "reschedule": "তারিখ বদলে দিন", "callback": "আমাকে ফোন করুন",
           "already_paid": "আমি আগেই দিয়ে দিয়েছি"},  # BN: needs native review
    "od": {"pay_today": "ଏବେ ଦେଇଦେବି", "pay_later": "କାଲି ଦେଇଦେବି", "skip_today": "ଆଜି ଦେଇପାରିବି ନାହିଁ, କାଲି କାଟିନିଅନ୍ତୁ",
           "lower_deduction": "ଟିକେ କମ୍ କାଟନ୍ତୁ", "reschedule": "ତାରିଖ ବଦଳାନ୍ତୁ", "callback": "ମୋତେ ଫୋନ୍ କରନ୍ତୁ",
           "already_paid": "ମୁଁ ଆଗରୁ ଦେଇସାରିଛି"},  # OD: needs native review
    "te": {"pay_today": "ఇప్పుడే కడతాను", "pay_later": "రేపు కడతాను", "skip_today": "ఈరోజు కట్టలేను, రేపు కట్ చేసుకోండి",
           "lower_deduction": "కొంచెం తక్కువ కట్ చేయండి", "reschedule": "తేదీ మార్చండి", "callback": "నాకు ఫోన్ చేయండి",
           "already_paid": "నేను ఇప్పటికే కట్టేశాను"},  # TE: needs native review
}

# ---- offline keyword lists. Distress words come first, so a hard time is caught even with AI off.
KEYWORDS = {
    "hardship": [
        # Bengali  (BN: needs native review)
        "অসুস্থ", "অসুখ", "হাসপাতাল", "মারা গেছে", "মারা গেছেন", "মৃত্যু", "বন্যা", "দোকান বন্ধ", "বিয়ে",
        "টাকা নেই", "বিক্রি নেই", "বিক্রি হয়নি", "ক্ষতি", "দুর্ঘটনা", "আগুন", "ঝড়", "শ্রাদ্ধ",
        # Odia  (OD: needs native review)
        "ଅସୁସ୍ଥ", "ଦେହ ଖରାପ", "ଡାକ୍ତରଖାନା", "ହସ୍ପିଟାଲ", "ମୃତ୍ୟୁ", "ମରିଗଲେ", "ବନ୍ୟା", "ଦୋକାନ ବନ୍ଦ", "ବାହାଘର",
        "ଟଙ୍କା ନାହିଁ", "ବିକ୍ରି ନାହିଁ", "କ୍ଷତି", "ଦୁର୍ଘଟଣା", "ନିଆଁ", "ବାତ୍ୟା",
        # Telugu  (TE: needs native review)
        "ఆరోగ్యం బాగాలేదు", "జబ్బు", "ఆసుపత్రి", "హాస్పిటల్", "చనిపోయారు", "మరణం", "వరద", "షాపు మూసి",
        "దుకాణం మూసి", "పెళ్లి", "డబ్బులు లేవు", "అమ్మకాలు లేవు", "నష్టం", "ప్రమాదం", "మంటలు", "తుఫాను",
    ],
    "dispute": [
        "ভুল", "দুবার কেটেছে", "বেশি কেটেছে",  # BN: needs native review
        "ଭୁଲ", "ଦୁଇଥର କଟିଛି", "ଅଧିକ କଟିଛି",  # OD: needs native review
        "తప్పు", "రెండుసార్లు కట్", "ఎక్కువ కట్",  # TE: needs native review
    ],
    "already_paid": [
        "আগেই দিয়ে", "দিয়ে দিয়েছি", "পেমেন্ট করে দিয়েছি", "জমা দিয়েছি",  # BN: needs native review
        "ଆଗରୁ ଦେଇସାରିଛି", "ଦେଇସାରିଛି", "ପେମେଣ୍ଟ କରିସାରିଛି",  # OD: needs native review
        "ఇప్పటికే కట్టేశాను", "కట్టేశాను", "చెల్లించాను", "కట్టాను",  # TE: needs native review
    ],
    "request_lower_deduction": ["কম কাটুন", "কম কাটো", "କମ୍ କାଟନ୍ତୁ", "తక్కువ కట్"],  # BN/OD/TE: needs native review
    "request_reschedule": ["তারিখ বদল", "ତାରିଖ ବଦଳ", "తేదీ మార్చ"],  # BN/OD/TE: needs native review
    "request_callback": ["ফোন করুন", "কল করুন", "কথা বলতে চাই", "ଫୋନ୍ କରନ୍ତୁ", "କଲ୍ କରନ୍ତୁ",
                         "ఫోన్ చేయండి", "కాల్ చేయండి", "మాట్లాడాలి"],  # BN/OD/TE: needs native review
    "will_pay_later": ["কাল", "পরশু", "পরে", "କାଲି", "ପରେ", "రేపు", "తర్వాత"],  # BN/OD/TE: needs native review
    "will_pay_today": ["আজ", "এখনই", "এখন", "ଆଜି", "ଏବେ", "ఈరోజు", "ఇవాళ", "ఇప్పుడే", "ఇప్పుడు"],  # BN/OD/TE: needs native review
}
PAY_VERBS = ["দেব", "দিয়ে দেব", "দিচ্ছি", "পেমেন্ট করব", "জমা দেব",  # BN: needs native review
             "ଦେବି", "ଦେଇଦେବି", "ପେମେଣ୍ଟ କରିବି", "ଜମା କରିବି",  # OD: needs native review
             "కడతాను", "ఇస్తాను", "చెల్లిస్తాను", "కట్టేస్తాను"]  # TE: needs native review
NEGATIONS = ["না", "নেই", "ନାହିଁ", "ନା", "లేదు", "లేవు", "కాదు", "కట్టలేను", "ఇవ్వలేను", "చెల్లించలేను"]  # needs native review
MONEY_WORDS = ["টাকা", "বিক্রি", "ব্যবসা", "ଟଙ୍କା", "ବିକ୍ରି", "ବ୍ୟବସାୟ", "డబ్బు", "అమ్మకాలు", "వ్యాపారం"]  # needs native review
# "Can't pay today": today-words, deduct/take words, and can't-pay forms
TODAY_WORDS = ["আজ", "ଆଜି", "ఈరోజు", "ఇవాళ"]  # needs native review
DEDUCT_WORDS = ["কেটে নিন", "কেটে নেবেন", "কাটবেন", "କାଟିନିଅନ୍ତୁ", "କାଟନ୍ତୁ", "కట్ చేసుకోండి", "తీసుకోండి"]  # needs native review
CANT_PAY = ["দিতে পারব না", "দিতে পারবো না", "ଦେଇପାରିବି ନାହିଁ", "କରିପାରିବି ନାହିଁ", "కట్టలేను", "ఇవ్వలేను", "చెల్లించలేను"]  # needs native review
LATER_TIME = ["কাল", "পরে", "କାଲି", "ପରେ", "రేపు", "తర్వాత"]  # needs native review
