"""
Apex Words — inglizcha-o'zbekcha tarjimalar (manba fayl).

Bu yerdagi UZ lug'ati qo'lda tuzilgan va ko'rib chiqilgan. Avtomatik tarjima
(Google va h.k.) bitta so'z uchun kontekstni bilmaydi va 'bat' ni doim
"ko'rshapalak" deb tarjima qiladi, holbuki o'yinda u "tayoq" ham bo'lishi mumkin.
Shuning uchun ko'p ma'noli so'zlarda ikkala ma'no ham nuqta-vergul bilan
yoziladi:  "BAT": "ko'rshapalak; tayoq".

Fe'llar '-moq' bilan, otlar asos shaklda beriladi.

Ishga tushirish (web_app/data/dict.json ni yangilaydi):
    python build/translations.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

UZ = {
# --- A ---
"ABOUT": "haqida", "ACE": "as (karta); zo'r", "ACID": "kislota", "ACNE": "husnbuzar",
"ACROSS": "bo'ylab, narigi tomonda", "ACT": "harakat qilmoq; parda", "ACTUAL": "haqiqiy",
"ADD": "qo'shmoq", "ADDICT": "qaram odam", "ADJUST": "moslashtirmoq", "AFFORD": "qurbi yetmoq",
"AFRAID": "qo'rqqan", "AGE": "yosh", "AGENDA": "kun tartibi", "AGO": "ilgari",
"AGONY": "azob", "AID": "yordam", "AIM": "maqsad", "AIR": "havo", "ALL": "hamma",
"ALLY": "ittifoqchi", "ALSO": "ham", "ALTAR": "mehrob", "AMEN": "omin",
"AMEND": "tuzatmoq", "AMONG": "orasida", "AND": "va", "ANIMAL": "hayvon",
"ANT": "chumoli", "ANTHEM": "madhiya", "ANY": "har qanday", "ANYONE": "har kim",
"ANYWAY": "baribir", "ARC": "yoy", "ARCH": "ravoq", "AREA": "hudud",
"ARK": "kema (Nuh kemasi)", "ARM": "qo'l", "ARMY": "armiya", "ART": "san'at",
"ASH": "kul", "ASK": "so'ramoq", "ASYLUM": "boshpana", "ATOM": "atom",
"ATTACH": "biriktirmoq", "AUTO": "avtomobil", "AVOID": "qochmoq", "AWARD": "mukofot",
"AWAY": "uzoqda", "AWE": "hayrat", "AWFUL": "dahshatli",
# --- B ---
"BACK": "orqa", "BACON": "bekon", "BAD": "yomon", "BAG": "sumka", "BAIT": "yem",
"BALL": "to'p", "BAMBOO": "bambuk", "BAN": "taqiqlamoq", "BAND": "guruh",
"BANG": "gurs etmoq", "BANK": "bank; qirg'oq", "BAR": "bar; panjara", "BASS": "bas",
"BAT": "ko'rshapalak; tayoq", "BEACH": "plyaj", "BEAM": "nur; to'sin", "BED": "karavot",
"BEE": "asalari", "BEER": "pivo", "BEHOLD": "ko'rmoq", "BELL": "qo'ng'iroq",
"BELLY": "qorin", "BELT": "kamar", "BEST": "eng yaxshi", "BET": "garov",
"BETTER": "yaxshiroq", "BID": "taklif qilmoq", "BIN": "chelak", "BIRD": "qush",
"BIRTH": "tug'ilish", "BIT": "ozgina", "BLACK": "qora", "BLANK": "bo'sh",
"BLINK": "ko'z qismoq", "BLOOD": "qon", "BLOOM": "gullamoq", "BOAT": "qayiq",
"BODY": "tana", "BOLD": "dadil", "BOLT": "murvat", "BOMB": "bomba",
"BOMBER": "bombardimonchi", "BOND": "bog'lanish", "BONE": "suyak", "BOOM": "portlash; o'sish",
"BORDER": "chegara", "BORE": "zeriktirmoq", "BOTH": "ikkalasi", "BOTHER": "bezovta qilmoq",
"BOUNTY": "mukofot", "BOUT": "olishuv; xuruj", "BOW": "ta'zim; kamon", "BOX": "quti",
"BOXER": "bokschi", "BOY": "o'g'il bola", "BRASS": "jez", "BRIEF": "qisqa",
"BUFF": "ishqalamoq; ishqiboz", "BUFFER": "bufer", "BUILD": "qurmoq", "BUS": "avtobus",
"BUT": "lekin", "BUY": "sotib olmoq", "BYE": "xayr",
# --- C ---
"CAB": "taksi", "CABIN": "kabina; kulba", "CAGE": "qafas", "CALL": "chaqirmoq",
"CALM": "tinch", "CAMP": "lager", "CAN": "-a olmoq; banka", "CANDY": "konfet",
"CANE": "hassa", "CANON": "qonun-qoida", "CANYON": "kanyon", "CAP": "qalpoq",
"CAR": "mashina", "CARD": "karta", "CASE": "holat; quti", "CASH": "naqd pul",
"CAST": "tashlamoq; aktyorlar", "CAT": "mushuk", "CATCH": "ushlamoq",
"CAVITY": "bo'shliq; kariyes", "CEMENT": "sement", "CENSUS": "aholi ro'yxati",
"CENT": "sent", "CHAIN": "zanjir", "CHASE": "quvmoq", "CHAT": "suhbatlashmoq",
"CHEESY": "siyqa; pishloqli", "CHEST": "ko'krak; sandiq", "CHIN": "iyak",
"CHOKE": "bo'g'moq", "CHOOSE": "tanlamoq", "CITE": "iqtibos keltirmoq", "CITY": "shahar",
"CLAIM": "da'vo qilmoq", "CLAN": "urug'", "CLASS": "sinf", "CLASSY": "nafis",
"CLAY": "loy", "CLERGY": "ruhoniylar", "CLIMAX": "cho'qqi", "CLIP": "qisqich",
"CLOTH": "mato", "CLUB": "klub; to'qmoq", "COAL": "ko'mir", "COAT": "palto",
"COD": "treska", "COIL": "g'altak", "COIN": "tanga", "COKE": "kola; koks",
"COLA": "kola", "COLD": "sovuq", "COLON": "yo'g'on ichak; ikki nuqta",
"COLONY": "mustamlaka", "COLT": "toy", "CONSUL": "konsul", "COOL": "salqin",
"COP": "politsiyachi", "COPE": "eplamoq", "COPY": "nusxa", "CORE": "o'zak",
"CORK": "probka", "CORTEX": "po'stloq", "COST": "narx", "COTTON": "paxta",
"COUNT": "sanamoq", "COUNTY": "okrug", "COUP": "to'ntarish", "COURT": "sud; kort",
"COVE": "qo'ltiq", "COVER": "qoplamoq", "COW": "sigir", "COWBOY": "kovboy",
"CRAZY": "jinni", "CREEP": "sudralmoq", "CRIME": "jinoyat", "CRISP": "qarsildoq",
"CROSS": "xoch; kesib o'tmoq", "CRY": "yig'lamoq", "CUE": "ishora", "CULT": "kult",
"CUP": "piyola", "CUT": "kesmoq", "CUTE": "yoqimtoy",
# --- D ---
"DAM": "to'g'on", "DAMAGE": "zarar", "DANCE": "raqs", "DATE": "sana; xurmo",
"DAWN": "tong", "DAY": "kun", "DEAD": "o'lik", "DEATH": "o'lim", "DEBT": "qarz",
"DECADE": "o'n yillik", "DECAY": "chirimoq", "DECIDE": "qaror qilmoq", "DEED": "amal",
"DEEP": "chuqur", "DEEPLY": "chuqur (ravish)", "DEER": "kiyik", "DEGREE": "daraja",
"DEN": "in", "DEPLOY": "joylashtirmoq", "DICE": "zar", "DIE": "o'lmoq",
"DIG": "qazmoq", "DIM": "xira", "DIRT": "kir", "DIRTY": "iflos",
"DODGE": "chetlab o'tmoq", "DOG": "it", "DONOR": "donor", "DOOR": "eshik",
"DOSE": "doza", "DOT": "nuqta", "DOWN": "pastga", "DRAMA": "drama",
"DRAW": "chizmoq", "DRILL": "parma", "DRY": "quruq", "DUE": "muddati kelgan",
"DUO": "duet", "DUST": "chang", "DWELL": "yashamoq", "DYE": "bo'yoq",
# --- E ---
"EACH": "har biri", "EAR": "quloq", "EASE": "yengillik", "EASY": "oson",
"EAT": "yemoq", "ECHO": "aks-sado", "EDGE": "chekka", "EGG": "tuxum", "EGO": "ego",
"EIGHT": "sakkiz", "EIGHTY": "sakson", "ELDER": "kattaroq", "ELF": "elf",
"ELSE": "boshqa", "EMPTY": "bo'sh", "END": "oxir", "ENERGY": "energiya",
"ENGAGE": "jalb qilmoq", "ENJOY": "zavqlanmoq", "ENVY": "hasad", "EPIC": "epik",
"EQUITY": "tenglik; ulush", "ERA": "davr", "ERROR": "xato", "ESSAY": "insho",
"ESTEEM": "hurmat", "EVEN": "hatto; tekis", "EVENLY": "tekis", "EVER": "hech qachon",
"EVERY": "har", "EXCEPT": "dan tashqari", "EXCUSE": "bahona", "EXEMPT": "ozod",
"EXODUS": "ommaviy ko'chish", "EXPECT": "kutmoq", "EYE": "ko'z",
# --- F ---
"FAIR": "adolatli; yarmarka", "FAIRY": "pari", "FALL": "yiqilmoq; kuz",
"FAN": "muxlis; ventilyator", "FANCY": "hashamatli", "FAR": "uzoq", "FARM": "ferma",
"FAT": "semiz; yog'", "FAULT": "ayb", "FAVOR": "iltifot", "FEE": "to'lov",
"FEST": "festival", "FEVER": "isitma", "FIBER": "tola", "FIERCE": "shiddatli",
"FIERY": "olovli", "FIG": "anjir", "FIGHT": "jang", "FILM": "film",
"FILTHY": "juda iflos", "FIN": "suzgich", "FINE": "yaxshi; jarima", "FINISH": "tugatmoq",
"FIRE": "olov", "FIRM": "firma; qat'iy", "FIRMLY": "qat'iy", "FISH": "baliq",
"FIST": "musht", "FIT": "mos kelmoq", "FIVE": "besh", "FLAT": "tekis; kvartira",
"FLAVOR": "ta'm", "FLAW": "nuqson", "FLESH": "go'sht", "FLOAT": "suzmoq",
"FLOOD": "toshqin", "FLOOR": "pol", "FLORAL": "gulli", "FLU": "gripp",
"FLY": "uchmoq; pashsha", "FOG": "tuman", "FOIL": "folga", "FOLD": "buklamoq",
"FONT": "shrift", "FOOD": "ovqat", "FOOL": "ahmoq", "FOR": "uchun",
"FORBID": "taqiqlamoq", "FORCE": "kuch", "FORM": "shakl", "FORMER": "avvalgi",
"FORT": "qal'a", "FORTH": "oldinga", "FORUM": "forum", "FOSSIL": "qazilma qoldiq",
"FOUR": "to'rt", "FREE": "erkin; bepul", "FRESH": "yangi", "FROG": "qurbaqa",
"FROM": "dan", "FRONT": "old", "FRY": "qovurmoq", "FULL": "to'la", "FULLY": "to'liq",
"FUR": "mo'yna", "FUSE": "saqlagich", "FUTURE": "kelajak",
# --- G ---
"GAG": "hazil; og'zini bog'lamoq", "GAME": "o'yin", "GANG": "to'da", "GAP": "bo'shliq",
"GAS": "gaz", "GAUGE": "o'lchagich", "GEL": "gel", "GEM": "qimmatbaho tosh",
"GENRE": "janr", "GET": "olmoq", "GHETTO": "getto", "GIFT": "sovg'a",
"GIN": "jin (ichimlik)", "GIRL": "qiz", "GLUE": "yelim", "GOAT": "echki",
"GREED": "ochko'zlik", "GREEN": "yashil", "GREET": "salomlashmoq", "GREY": "kulrang",
"GRIEF": "qayg'u", "GRILL": "panjara; qovurmoq", "GRIN": "tirjaymoq", "GROUP": "guruh",
"GROW": "o'smoq", "GROWTH": "o'sish", "GUIDE": "yo'lboshchi", "GUILT": "aybdorlik",
"GUILTY": "aybdor", "GUN": "qurol", "GUT": "ichak", "GUY": "yigit", "GYM": "sport zali",
# --- H ---
"HAIR": "soch", "HAIRY": "junli", "HALL": "zal", "HAM": "vetchina", "HAND": "qo'l",
"HANDY": "qulay", "HAT": "shlyapa", "HATE": "yomon ko'rmoq", "HAUL": "sudramoq",
"HAVE": "ega bo'lmoq", "HAY": "pichan", "HEAD": "bosh", "HEAT": "issiqlik",
"HEAVY": "og'ir", "HEIR": "meros oluvchi", "HEN": "tovuq", "HER": "uning (ayol)",
"HERD": "poda", "HERE": "bu yerda", "HEREIN": "shu yerda", "HERO": "qahramon",
"HERS": "uniki (ayol)", "HEY": "hey", "HIGH": "baland", "HIGHER": "balandroq",
"HILL": "tepalik", "HIM": "unga (erkak)", "HIRE": "yollamoq", "HIS": "uning (erkak)",
"HIT": "urmoq", "HOCKEY": "xokkey", "HOG": "cho'chqa", "HOLD": "ushlamoq",
"HOLE": "teshik", "HOLY": "muqaddas", "HOME": "uy", "HOSE": "shlang",
"HOST": "mezbon", "HOT": "issiq", "HOTEL": "mehmonxona", "HOUR": "soat",
"HOURLY": "soatlik", "HOW": "qanday", "HUG": "quchoqlamoq", "HUM": "ming'irlamoq",
"HUMAN": "inson", "HUMOR": "hazil", "HUMOUR": "hazil", "HUNGRY": "och",
"HUT": "kulba", "HYBRID": "duragay", "HYPER": "o'ta faol",
# --- I ---
"ICE": "muz", "ICON": "belgi; ikona", "ICONIC": "mashhur", "ILL": "kasal",
"IMAGE": "tasvir", "IMPLY": "nazarda tutmoq", "IMPOSE": "majburlamoq", "INCH": "dyuym",
"INK": "siyoh", "INN": "mehmonxona", "INSANE": "aqldan ozgan", "INSIST": "turib olmoq",
"INTO": "ichiga", "ION": "ion", "IRON": "temir; dazmol", "IRONY": "kinoya",
"ISLE": "orol", "ITEM": "buyum", "ITS": "uning",
# --- J ---
"JAM": "murabbo; tiqilinch", "JAR": "banka", "JERK": "beadab; siltamoq", "JET": "reaktiv",
"JOB": "ish", "JOCKEY": "chavandoz", "JOKE": "hazil", "JOKER": "hazilkash; joker",
"JOY": "quvonch", "JUMP": "sakramoq", "JUMPER": "kofta", "JUNGLE": "o'rmon",
"JUST": "faqat; adolatli",
# --- K ---
"KEEP": "saqlamoq", "KEEPER": "qorovul", "KEY": "kalit", "KILL": "o'ldirmoq",
"KILLER": "qotil", "KITE": "varrak", "KNIFE": "pichoq", "KNOT": "tugun",
"KNOW": "bilmoq",
# --- L ---
"LAB": "laboratoriya", "LACK": "yetishmaslik", "LAD": "o'smir", "LAG": "kechikish",
"LAND": "yer", "LAP": "tizza; aylana", "LAST": "oxirgi", "LAUGH": "kulmoq",
"LAUNCH": "ishga tushirmoq", "LAW": "qonun", "LAY": "yotqizmoq", "LAYOUT": "joylashuv",
"LEG": "oyoq", "LEMON": "limon", "LEND": "qarz bermoq", "LENGTH": "uzunlik",
"LENS": "linza", "LESS": "kamroq", "LESSER": "kichikroq", "LET": "ruxsat bermoq",
"LETTER": "xat; harf", "LEVY": "soliq solmoq", "LIAR": "yolg'onchi", "LID": "qopqoq",
"LIE": "yolg'on; yotmoq", "LIFT": "ko'tarmoq", "LIGHT": "yorug'lik; yengil",
"LIKE": "yoqmoq; kabi", "LIKELY": "ehtimol", "LINE": "chiziq", "LINK": "bog'lanish",
"LION": "sher", "LIP": "lab", "LIST": "ro'yxat", "LIT": "yoritilgan",
"LOAD": "yuk", "LOAN": "qarz", "LOCAL": "mahalliy", "LOG": "yog'och; jurnal",
"LOGIC": "mantiq", "LONE": "yolg'iz", "LONELY": "yolg'iz", "LOOP": "halqa",
"LOOSE": "bo'sh", "LORE": "rivoyatlar", "LOSE": "yo'qotmoq", "LOSS": "yo'qotish",
"LOT": "ko'p", "LOTUS": "lotus", "LOUD": "baland ovozli", "LOVE": "sevgi",
"LOW": "past", "LUNCH": "tushlik", "LUNG": "o'pka", "LUSH": "serob",
# --- M ---
"MAD": "jinni; g'azablangan", "MAIL": "pochta", "MAIN": "asosiy", "MAJOR": "asosiy; mayor",
"MALL": "savdo markazi", "MAN": "erkak", "MANGO": "mango", "MANLY": "mardona",
"MANY": "ko'p", "MAP": "xarita", "MARK": "belgi", "MARRY": "turmush qurmoq",
"MAT": "gilamcha", "MAY": "-sa bo'ladi; may", "MAYBE": "balki", "MEAN": "anglatmoq; qo'pol",
"MEET": "uchrashmoq", "MEMO": "eslatma", "MEMOIR": "xotira", "MERE": "shunchaki",
"MERELY": "shunchaki", "MESH": "to'r", "MESS": "tartibsizlik", "MESSY": "tartibsiz",
"MID": "o'rta", "MIGHT": "balki; qudrat", "MIGHTY": "qudratli", "MINUS": "minus",
"MISERY": "azob", "MIST": "tuman", "MIX": "aralashtirmoq", "MOB": "olomon",
"MOIST": "nam", "MOLE": "ko'rsichqon; xol", "MONEY": "pul", "MONK": "rohib",
"MONKEY": "maymun", "MONTH": "oy", "MORE": "ko'proq", "MOST": "eng ko'p",
"MOSTLY": "asosan", "MOTHER": "ona", "MOTOR": "dvigatel", "MOTTO": "shior",
"MOUTH": "og'iz", "MOVE": "harakatlanmoq", "MUM": "oyi", "MUSE": "ilhom",
"MUSEUM": "muzey", "MUST": "kerak", "MYSELF": "o'zim", "MYSTIC": "sirli",
"MYTH": "afsona",
# --- N ---
"NAIL": "mix; tirnoq", "NAKED": "yalang'och", "NAME": "ism", "NAP": "mudroq",
"NEED": "kerak bo'lmoq", "NEEDLE": "igna", "NEON": "neon", "NERVE": "asab",
"NEST": "uya", "NEVER": "hech qachon", "NEW": "yangi", "NEWS": "yangiliklar",
"NEXUS": "bog'lanish nuqtasi", "NICE": "yaxshi", "NICELY": "chiroyli", "NINE": "to'qqiz",
"NOBLE": "olijanob", "NOBODY": "hech kim", "NOD": "bosh irg'amoq", "NODE": "tugun",
"NONE": "hech biri", "NOON": "tush payti", "NOPE": "yo'q", "NOR": "ham emas",
"NOSE": "burun", "NOT": "emas", "NOTCH": "o'yiq", "NOTE": "eslatma; nota",
"NOVEL": "roman; yangi", "NOW": "hozir", "NUT": "yong'oq",
# --- O ---
"OATH": "qasam", "OBJECT": "buyum; e'tiroz bildirmoq", "OCCUPY": "egallamoq",
"ODD": "g'alati; toq", "OFF": "o'chirilgan", "OFFER": "taklif", "OFFSET": "qoplamoq",
"OFTEN": "tez-tez", "OIL": "moy; neft", "OLD": "eski", "ONE": "bir",
"ONION": "piyoz", "ONLY": "faqat", "ONTO": "ustiga", "OPEN": "ochmoq",
"OPT": "tanlamoq", "ORAL": "og'zaki", "ORDER": "buyurtma; tartib", "ORE": "ma'dan",
"ORGAN": "a'zo; organ", "OTHER": "boshqa", "OUR": "bizning", "OURS": "bizniki",
"OUT": "tashqarida", "OUTER": "tashqi", "OUTLET": "rozetka; do'kon", "OUTPUT": "natija",
"OVAL": "oval", "OVEN": "pech", "OVER": "ustida; tugagan", "OWE": "qarzdor bo'lmoq",
"OWL": "boyo'g'li", "OWN": "o'z", "OWNER": "egasi",
# --- P ---
"PAD": "yostiqcha", "PAGE": "sahifa", "PAL": "do'st", "PAN": "tova", "PANDA": "panda",
"PAR": "me'yor", "PEEK": "mo'ralamoq", "PEEL": "po'st tashlamoq", "PEER": "tengdosh",
"PEN": "ruchka", "PEOPLE": "odamlar", "PEPPER": "qalampir", "PER": "har biriga",
"PET": "uy hayvoni", "PETTY": "arzimas", "PICK": "tanlamoq", "PICKUP": "olib ketish",
"PIE": "pirog", "PINT": "pinta", "PIT": "chuqur", "POEM": "she'r", "POINT": "nuqta",
"POLE": "ustun; qutb", "POLO": "polo", "POOL": "hovuz", "POOR": "kambag'al",
"POORLY": "yomon", "POP": "pop; portlamoq", "POSE": "poza", "POT": "qozon",
"POUR": "quymoq", "PREP": "tayyorlanmoq", "PREY": "o'lja", "PRO": "professional",
"PROOF": "dalil", "PROP": "tayanch", "PUB": "pab", "PUBLIC": "ommaviy",
"PUCK": "shayba", "PUP": "kuchukcha", "PURE": "sof", "PUT": "qo'ymoq",
# --- Q ---
"QUEST": "izlanish", "QUIET": "jim", "QUIT": "tashlab ketmoq", "QUITE": "ancha",
# --- R ---
"RACIAL": "irqiy", "RAG": "latta", "RAID": "bosqin", "RAIL": "relüs; temiryo'l",
"RAIN": "yomg'ir", "RAINY": "yomg'irli", "RALLY": "miting", "RANCH": "ranchо",
"RAP": "rep", "RAT": "kalamush", "RAW": "xom", "REBEL": "isyonchi", "RED": "qizil",
"REEL": "g'altak", "REFORM": "islohot", "REGRET": "afsuslanmoq", "RELY": "ishonmoq",
"REMOVE": "olib tashlamoq", "RENDER": "taqdim etmoq", "REPLY": "javob",
"RESIN": "smola", "REVIEW": "sharh", "RIB": "qovurg'a", "RICE": "guruch",
"RID": "qutulmoq", "RIG": "uskuna", "RIM": "gardish", "RING": "uzuk; jiringlamoq",
"RIP": "yirtmoq", "RISE": "ko'tarilmoq", "RISK": "xavf", "ROAD": "yo'l",
"ROCK": "tosh; rok", "ROCKY": "toshloq", "ROLE": "rol", "ROLL": "dumalamoq",
"ROLLER": "g'altak", "ROOF": "tom", "ROOM": "xona", "ROOT": "ildiz",
"ROT": "chirimoq", "ROUTE": "yo'nalish", "ROW": "qator", "RUB": "ishqalamoq",
"RUG": "gilam", "RUIN": "vayron qilmoq", "RUM": "rom", "RUN": "yugurmoq",
# --- S ---
"SACK": "qop", "SAD": "xafa", "SAFARI": "safari", "SAIL": "yelkan", "SAKE": "xotirjamlik uchun",
"SALMON": "losos", "SALON": "salon", "SALT": "tuz", "SAND": "qum", "SANDY": "qumli",
"SANE": "aqli raso", "SAVIOR": "najotkor", "SAW": "arra", "SAY": "aytmoq",
"SCAN": "skanerlamoq", "SCAR": "chandiq", "SCENIC": "manzarali", "SCENT": "hid",
"SCHEME": "sxema", "SCOPE": "qamrov", "SCORE": "hisob", "SCORER": "gol urgan",
"SCOUT": "skaut", "SEA": "dengiz", "SEASON": "fasl", "SEE": "ko'rmoq", "SEED": "urug'",
"SEEM": "ko'rinmoq", "SELF": "o'z", "SELL": "sotmoq", "SELLER": "sotuvchi",
"SEND": "yubormoq", "SEQUEL": "davomi", "SERVE": "xizmat qilmoq", "SERVER": "server",
"SET": "o'rnatmoq; to'plam", "SEVERE": "og'ir", "SHALL": "-adi (kelasi zamon)",
"SHE": "u (ayol)", "SHEEP": "qo'y", "SHEER": "sof; tik", "SHEET": "varaq; choyshab",
"SHELF": "javon", "SHIFT": "smena; siljish", "SHIN": "boldir", "SHIRT": "ko'ylak",
"SHOE": "tufli", "SHOOT": "otmoq", "SHORT": "qisqa", "SHOULD": "kerak",
"SHOVE": "turtmoq", "SHOW": "ko'rsatmoq", "SHUT": "yopmoq", "SHY": "uyatchan",
"SIGH": "xo'rsinmoq", "SIGHT": "ko'rish", "SIMPLY": "oddiygina", "SIN": "gunoh",
"SINCE": "beri", "SIP": "yutmoq", "SIR": "janob", "SIT": "o'tirmoq", "SITE": "joy; sayt",
"SIX": "olti", "SIXTH": "oltinchi", "SIXTY": "oltmish", "SKETCH": "eskiz",
"SKI": "chang'i", "SKY": "osmon", "SLACK": "bo'sh", "SLAM": "qarsillatib yopmoq",
"SLEEP": "uxlamoq", "SLICE": "bo'lak", "SLIP": "sirpanmoq", "SLOT": "uyacha",
"SLOW": "sekin", "SLOWLY": "sekin", "SMALL": "kichik", "SMOOTH": "silliq",
"SNACK": "yengil taom", "SNAIL": "shilliqqurt", "SNOW": "qor", "SOCCER": "futbol",
"SOFT": "yumshoq", "SOIL": "tuproq", "SOLE": "yagona; tovon", "SOLO": "yakka",
"SOLVE": "yechmoq", "SOME": "ba'zi", "SON": "o'g'il", "SORE": "og'riyotgan",
"SORT": "tur; saralamoq", "SOUL": "ruh", "SOUP": "sho'rva", "SOUR": "nordon",
"SOY": "soya", "SPEECH": "nutq", "SPEED": "tezlik", "SPEND": "sarflamoq",
"SPOUSE": "turmush o'rtog'i", "SPY": "josus", "STALL": "do'kon; to'xtab qolmoq",
"STAR": "yulduz", "START": "boshlamoq", "STEM": "poya", "STIFF": "qattiq",
"STILL": "hali ham; tinch", "STIR": "aralashtirmoq", "STITCH": "chok",
"STORM": "bo'ron", "STRICT": "qattiqqo'l", "STUD": "zirh; ayg'ir", "STYLE": "uslub",
"SUB": "suvosti kemasi; o'rinbosar", "SUE": "sudga bermoq", "SUGAR": "shakar",
"SUIT": "kostyum; mos kelmoq", "SUITE": "lyuks", "SUM": "yig'indi", "SUMMON": "chaqirmoq",
"SUN": "quyosh", "SURE": "albatta", "SWAY": "tebranmoq", "SWEEP": "supurmoq",
"SWITCH": "kalit; almashtirmoq", "SYSTEM": "tizim",
# --- T ---
"TAG": "yorliq", "TAIL": "dum", "TAKE": "olmoq", "TALL": "baland bo'yli",
"TALLY": "hisob", "TAN": "qoraymoq", "TEA": "choy", "TEAM": "jamoa", "TEEN": "o'smir",
"TEN": "o'n", "TENT": "chodir", "TERM": "muddat; atama", "TERROR": "dahshat",
"THAN": "dan (qiyos)", "THAT": "u; anavi", "THE": "aniq artikl", "THEM": "ularga",
"THEME": "mavzu", "THEN": "keyin", "THEORY": "nazariya", "THERE": "u yerda",
"THESE": "bular", "THESIS": "dissertatsiya", "THEY": "ular", "THIEF": "o'g'ri",
"THIRD": "uchinchi", "THIS": "bu", "THOSE": "ular", "THREE": "uch",
"THRILL": "hayajon", "THROW": "tashlamoq", "THUS": "shunday qilib", "TICK": "kana; belgi",
"TICKET": "chipta", "TIE": "bog'lamoq; galstuk", "TILL": "gacha", "TIME": "vaqt",
"TIN": "qalay; banka", "TIP": "maslahat; uchi", "TODAY": "bugun", "TOE": "oyoq barmog'i",
"TOMATO": "pomidor", "TON": "tonna", "TONE": "ohang", "TOO": "juda; ham",
"TOOL": "asbob", "TOP": "yuqori", "TOUR": "sayohat", "TOW": "sudramoq",
"TOWN": "shaharcha", "TOY": "o'yinchoq", "TREE": "daraxt", "TREK": "sayohat",
"TRICK": "hiyla", "TRICKY": "chalkash", "TRUE": "rost", "TRUNK": "tana; bagaj",
"TRY": "urinmoq", "TUB": "vanna", "TUNE": "kuy", "TUNNEL": "tunnel",
"TURBO": "turbo", "TURF": "chim", "TURKEY": "kurka", "TURN": "burilmoq",
"TWEET": "tvit; chug'urlamoq", "TWELVE": "o'n ikki", "TWENTY": "yigirma",
"TWIST": "burmoq", "TWITCH": "uchmoq (mushak)", "TWO": "ikki", "TYPE": "tur; yozmoq",
# --- U ---
"UGLY": "xunuk", "ULTRA": "o'ta", "UNLESS": "agar bo'lmasa", "UNLIKE": "farqli o'laroq",
"UNSEEN": "ko'rinmas", "UNTO": "ga", "URINE": "siydik", "USE": "ishlatmoq",
"USER": "foydalanuvchi", "UTMOST": "eng yuqori",
# --- V ---
"VACANT": "bo'sh", "VAPOR": "bug'", "VENOM": "zahar", "VERIFY": "tekshirmoq",
"VERSE": "she'r bandi", "VERSUS": "qarshi", "VERY": "juda", "VET": "veterinar",
"VIA": "orqali", "VICE": "illat; vitse-", "VIEW": "manzara", "VIEWER": "tomoshabin",
"VILLA": "villa", "VIRGIN": "bokira; toza", "VISA": "viza", "VITAL": "hayotiy muhim",
"VOCAL": "ovozli", "VOICE": "ovoz", "VOID": "bo'shliq; bekor", "VOYAGE": "dengiz sayohati",
# --- W ---
"WAGE": "ish haqi", "WALL": "devor", "WAR": "urush", "WARD": "palata",
"WASH": "yuvmoq", "WAY": "yo'l", "WED": "turmush qurmoq", "WEE": "kichkina",
"WEEK": "hafta", "WEEKLY": "haftalik", "WEIGH": "tortmoq", "WEIGHT": "og'irlik",
"WELL": "yaxshi; quduq", "WET": "ho'l", "WHAT": "nima", "WHEAT": "bug'doy",
"WHEN": "qachon", "WHERE": "qayerda", "WHILST": "bir vaqtda", "WHISKY": "viski",
"WHITE": "oq", "WHO": "kim", "WHOA": "voy", "WHOLE": "butun", "WHOLLY": "butunlay",
"WHOM": "kimga", "WHY": "nega", "WIDE": "keng", "WIDTH": "kenglik", "WILD": "yovvoyi",
"WILDLY": "yovvoyicha", "WILL": "iroda; -adi", "WILLOW": "tol", "WIN": "yutmoq",
"WIND": "shamol", "WINE": "vino", "WIRE": "sim", "WISE": "dono", "WISELY": "donolik bilan",
"WISH": "istamoq", "WIT": "zukkolik", "WITCH": "jodugar", "WITH": "bilan",
"WOMAN": "ayol", "WOO": "ko'nglini ovlamoq", "WOOD": "yog'och", "WOODEN": "yog'ochdan",
"WORK": "ish", "WORKER": "ishchi", "WORTH": "qiymat", "WORTHY": "munosib",
"WOW": "voy", "YARD": "hovli", "YARN": "ip", "YEAH": "ha", "YEAR": "yil",
"YELL": "baqirmoq", "YELLOW": "sariq", "YEN": "iyena", "YES": "ha", "YET": "hali",
"YOGA": "yoga", "YOU": "sen", "YOUNG": "yosh", "YOUR": "sening", "YOURS": "seniki",
"ZERO": "nol", "ZONE": "hudud",

# --- Qo'shimcha yechim so'zlari (generator qayta tanlagandan keyin qo'shilgan) ---
"ABOARD": "bortda", "ABROAD": "chet elda", "BEG": "yolvormoq", "BIG": "katta",
"BIGGER": "kattaroq", "BOARD": "taxta; kengash", "BOOT": "etik", "BOOTH": "kabina",
"BORROW": "qarz olmoq", "BROAD": "keng", "BROW": "qosh", "BUN": "bulochka",
"BUNKER": "boshpana", "BURN": "yonmoq", "CLONE": "nusxa", "COFFIN": "tobut",
"CONE": "konus", "COUPON": "kupon", "DRAFT": "qoralama", "DRINK": "ichmoq",
"ELDEST": "eng katta", "ELECT": "saylamoq", "ENTER": "kirmoq", "EXPERT": "mutaxassis",
"EXTENT": "darajasi", "GENTLE": "muloyim", "INDEED": "haqiqatan", "INDEX": "ko'rsatkich",
"INSIDE": "ichida", "KIND": "mehribon; tur", "KINDLY": "iltimos; mehribonlik bilan",
"LABOR": "mehnat", "LURE": "jalb qilmoq", "MELT": "erimoq", "METER": "metr; hisoblagich",
"MIND": "aql", "NEPHEW": "jiyan (o'g'il)", "NEXT": "keyingi", "NOUN": "ot (so'z turkumi)",
"ONCE": "bir marta", "OUNCE": "untsiya", "PIECE": "bo'lak", "PLEDGE": "va'da",
"PLUS": "qo'shuv", "PREFER": "afzal ko'rmoq", "PULP": "yumshoq massa", "PULSE": "puls",
"PUN": "so'z o'yini", "REFER": "murojaat qilmoq", "REFUGE": "boshpana", "RENT": "ijara",
"RUDE": "qo'pol", "RULE": "qoida", "SELECT": "tanlamoq", "SETTLE": "joylashmoq",
"SIDE": "tomon", "SPREE": "aysh-ishrat", "STEEL": "po'lat", "SUPPLY": "ta'minot",
"SURVEY": "so'rov", "SWEET": "shirin", "TEMPLE": "ibodatxona; chakka", "TEST": "sinov",
"TEXT": "matn", "TRAIT": "xususiyat", "TRAUMA": "jarohat", "TURTLE": "toshbaqa",
"UNION": "ittifoq", "UPON": "ustida", "URGE": "undamoq", "UTTER": "mutlaq; aytmoq",
"WANT": "xohlamoq", "WARN": "ogohlantirmoq",

# --- Bonus so'zlar (to'rda katak yo'q, topilsa +1 ochko) ---
"ACHE": "og'riq", "AFAR": "uzoqdan", "AFT": "kema orqasi", "AHEM": "kekirdak qirish",
"AIRY": "shabadali", "ALOFT": "yuqorida", "ALTO": "alt (ovoz)", "ALUM": "achchiqtosh",
"ANNOY": "bezovta qilmoq", "ANTE": "boshlang'ich garov", "APE": "maymun",
"ARIA": "ariya", "ARID": "qurg'oqchil", "AVID": "ishtiyoqmand", "BARD": "shoir",
"BEET": "lavlagi", "BERTH": "yotoq joy (kemada)", "BOA": "boa iloni",
"BOAR": "yovvoyi cho'chqa", "BONY": "suyakdor", "BOON": "ne'mat", "BRIG": "hibsxona (kemada)",
"BROTH": "bulon", "BUNK": "qavatli karavot", "CAD": "past odam", "CHAI": "choy",
"CHAR": "kuydirmoq", "CLAM": "chig'anoq", "CLOT": "quyqa", "COO": "gurillamoq",
"COOP": "katak", "COT": "bolalar karavoti", "COY": "tortinchoq", "CUB": "bolasi (hayvon)",
"CYST": "kista", "DAB": "yengil surtmoq", "DAFT": "aqlsiz", "DANK": "zax",
"DART": "dart; otilmoq", "DEW": "shudring", "DINE": "ovqatlanmoq", "DIVA": "diva",
"DOLE": "nafaqa", "EEL": "ilonbaliq", "ELK": "bug'u", "ELM": "qayrag'och",
"EMIR": "amir", "EMIT": "chiqarmoq", "EMU": "emu", "ERR": "xato qilmoq",
"ETHER": "efir", "ETHOS": "ruh, e'tiqod", "EXERT": "sarflamoq (kuch)", "FAD": "o'tkinchi moda",
"FILTH": "ifloslik", "FIR": "qarag'ay", "FLOSS": "tish ipi", "FOB": "brelok",
"FOE": "dushman", "FORE": "old", "FRAT": "talabalar birodarligi", "FRAY": "to'qnashuv",
"GENT": "janob", "GILT": "zarhal", "GIST": "mohiyat", "GLEE": "quvonch",
"GROAN": "ingramoq", "HEM": "etak (kiyim)", "HISS": "vishillamoq", "HOBO": "darbadar",
"HOWL": "uvillamoq", "ICY": "muzli", "IMP": "shayton bola", "IRE": "g'azab",
"ITCH": "qichishish", "JUG": "ko'za", "KEEL": "kil (kema)", "KILN": "pech (kulolchilik)",
"LACY": "to'rli", "LAIR": "uya, in", "LAMA": "lama", "LASH": "qamchi urmoq",
"LASS": "qizcha", "LAX": "sust", "LEDGE": "tokcha", "LEI": "gul gulchambar",
"LEST": "bo'lmasin deb", "LIEN": "garov huquqi", "LIEU": "o'rniga", "LOAF": "non bo'lagi",
"LOBE": "bo'lak (quloq)", "LOCH": "ko'l (Shotlandiya)", "LOFT": "chordoq",
"LOO": "hojatxona", "LOOT": "o'lja", "LOWLY": "kamtar", "LUG": "sudramoq",
"MANE": "yol (ot)", "MANIA": "maniya", "MATE": "sherik", "MATH": "matematika",
"MEAT": "go'sht", "MELON": "qovun", "MEND": "tuzatmoq", "MIME": "pantomima",
"MISTY": "tumanli", "MITE": "kana", "MOAN": "ingramoq", "MOAT": "handaq",
"MOO": "mo'ramoq", "MOOR": "botqoqlik", "MOOT": "bahsli", "MOP": "latta (tozalash)",
"MOTH": "kuya", "MOVER": "ko'chiruvchi", "MOW": "o'rmoq", "NAB": "ushlab olmoq",
"NAG": "ming'irlamoq", "NAY": "yo'q", "NEAT": "ozoda", "NIB": "qalam uchi",
"NIP": "chimchilamoq", "NIT": "sirka (bit)", "NOIR": "qora janr", "NUKE": "yadro qurol",
"ODE": "qasida", "ODOR": "hid", "OFT": "tez-tez", "OMEN": "alomat",
"OMIT": "tushirib qoldirmoq", "OPUS": "asar", "ORB": "shar", "PEA": "no'xat",
"PEG": "qoziq", "PERK": "imtiyoz", "PERM": "kimyoviy jingalak", "PEW": "o'rindiq (cherkov)",
"PHEW": "uf", "PIN": "to'g'nog'ich", "PINTO": "olacha ot", "PLOY": "hiyla",
"PLY": "qavat; qatnamoq", "POSSE": "guruh", "PRY": "qistirmoq; qiziqmoq",
"PUG": "mops (it)", "PUTT": "yengil zarba (golf)", "RAFT": "sol", "REDO": "qayta qilmoq",
"REIN": "jilov", "RIFE": "keng tarqalgan", "RINK": "muz maydoni", "RINSE": "chaymoq",
"ROAM": "kezmoq", "ROBE": "xalat", "ROE": "ikra", "ROSY": "pushti",
"ROUT": "tor-mor qilmoq", "ROWER": "eshkakchi", "RUMP": "dumba", "RUSE": "hiyla",
"RUT": "iz (g'ildirak)", "RYE": "javdar", "SAG": "egilmoq", "SECT": "mazhab",
"SEVER": "uzmoq", "SEW": "tikmoq", "SINE": "sinus", "SIRE": "ota (hayvon)",
"SIREN": "sirena", "SLAY": "o'ldirmoq", "SLED": "chana", "SLIT": "tirqish",
"SLUM": "qashshoq mahalla", "SLY": "ayyor", "SOAR": "ko'tarilmoq", "SOD": "chim",
"STEW": "qovurdoq", "STOUT": "baquvvat", "TACT": "nazokat", "TAME": "qo'lga o'rgatilgan",
"TART": "nordon; tort", "THAW": "erimoq", "TIC": "tik (asabiy)", "TIDY": "ozoda",
"TOAD": "qurbaqa", "TOT": "kichkintoy", "TOTE": "sumka; ko'tarmoq", "TOUT": "maqtamoq",
"TRAM": "tramvay", "TSAR": "podsho", "TUG": "tortmoq", "TYRE": "shina",
"URN": "kosa, urna", "VALOR": "jasorat", "VAT": "katta idish", "VIAL": "shishacha",
"VIE": "raqobatlashmoq", "WAD": "tugun", "WEEP": "yig'lamoq", "WEIR": "to'g'on",
"WHISK": "ko'pirtirgich", "WIG": "parik", "WILT": "so'lmoq", "WOE": "qayg'u",
"YELP": "vangillamoq", "YOKE": "bo'yinturuq",
"ALBUM": "albom", "BUM": "daydi", "LAMB": "qo'zichoq", "BALM": "malham",
"SOW": "ekmoq; urg'ochi cho'chqa",

# --- Olmoshlar bonusga o'tgach qo'shilgan yechim so'zlari ---
"ALLOW": "ruxsat bermoq", "ALLOY": "qotishma", "APT": "mos; moyil", "ATTIC": "chordoq",
"BARN": "omborxona", "CROP": "hosil", "DOLL": "qo'g'irchoq", "DROWN": "cho'kmoq",
"DULL": "zerikarli; xira", "EAST": "sharq", "FACT": "dalil", "FIX": "tuzatmoq",
"FLUX": "oqim", "FUN": "qiziqarli", "GOLD": "oltin", "HAPPEN": "sodir bo'lmoq",
"HARM": "zarar", "HATCH": "lyuk; tuxumdan chiqmoq", "HEAP": "uyum",
"HOLLOW": "kavak, ichi bo'sh", "HONEY": "asal", "HOP": "sakramoq", "HOPE": "umid",
"HOUSE": "uy", "INFLUX": "kirib kelish oqimi", "LIME": "laym", "LOUDLY": "baland ovozda",
"LOYAL": "sodiq", "MANOR": "qo'rg'on", "MILE": "mil", "MUD": "loy", "NORM": "me'yor",
"OBEY": "itoat qilmoq", "OFFEND": "xafa qilmoq", "OPTION": "variant", "PHONE": "telefon",
"RETIRE": "nafaqaga chiqmoq", "RITE": "marosim", "SAVE": "saqlamoq", "SEAT": "o'rindiq",
"SHAKE": "silkitmoq", "SHAVE": "soqol olmoq", "SHINY": "yaltiroq", "SOBER": "hushyor",
"SODIUM": "natriy", "STATE": "davlat; holat", "STATIC": "o'zgarmas", "STINT": "muddat",
"TAP": "jo'mrak; ohista urmoq", "TASTE": "ta'm", "THIRST": "chanqoq", "TIER": "qavat",
"TIRE": "charchamoq; shina", "TRENCH": "xandaq", "WAIST": "bel", "WAIT": "kutmoq",
"WEAPON": "qurol", "WOOL": "jun", "WORD": "so'z", "YOUTH": "yoshlik",

# --- Yangi bonus so'zlar ---
"ANEW": "qaytadan", "BRAN": "kepak", "DULY": "tegishlicha", "FEND": "himoyalanmoq",
"HONE": "charxlamoq", "HUE": "rang tusi", "LIMP": "oqsamoq", "MORN": "tong",
"NEWT": "suvsar (salamandra)", "PANE": "oyna bo'lagi", "PAW": "panja",
"PAWN": "piyoda (shaxmat)", "PEP": "g'ayrat", "POTION": "sehrli ichimlik",
"SLIMY": "shilimshiq", "SOB": "yig'lamoq", "SWAT": "shapatilab urmoq",
"TINT": "rang tusi", "VASE": "vaza",

# --- Olmoshlar (endi faqat bonus, lekin tarjimasi kerak) ---
"ITS": "uning", "HIS": "uning (erkak)", "HIM": "unga (erkak)", "HER": "uning (ayol)",
"HERS": "uniki (ayol)", "SHE": "u (ayol)", "THEY": "ular", "THEM": "ularga",
"THEIR": "ularning", "OUR": "bizning", "OURS": "bizniki", "YOU": "sen",
"YOUR": "sening", "YOURS": "seniki", "WHO": "kim", "WHOM": "kimga",
"WHOSE": "kimning", "THE": "aniq artikl", "MINE": "meniki", "MYSELF": "o'zim",
"BATH": "vanna", "CARRY": "olib yurmoq", "FAITH": "ishonch, e'tiqod",

# --- Avtomatik tarjima BOSHQA TILDA qaytargan so'zlar ---
#
# Google ba'zan o'zbekcha o'rniga turkcha yoki ruscha beradi. Ko'zga
# tashlanmaydi: "ranchо" ichidagi 'о' — kirill harfi, lotinchasidan
# farq qilmaydi. Shuning uchun ular audit_translations.py bilan
# topiladi va shu yerda qo'lda tuzatiladi.
"BUST": "byust; kasodga uchramoq", "CLICHE": "klishe",
"EMERY": "nayzak (jilvirlash toshi)", "HINGE": "sharnir; ilgak",
"LUMEN": "lyumen", "PLUSH": "plyush", "RAIL": "rels; temiryo'l",
"SAGE": "donishmand; adaqoq (o't)", "TWILIGHT": "shom; g'ira-shira",
"RANCH": "rancho (chorvachilik fermasi)",

# --- Tarjimasiz qolgan haqiqiy so'zlar ---
#
# Bularni Google tarjima qila olmay, inglizchasini qaytargan. O'yinchi
# bunday so'zni topsa ma'nosini bilmaydi — ya'ni o'yin o'z vazifasini
# bajarmaydi. Xalqaro so'zlar (radio, atom, vitamin) ataylab
# tegilmagan: ular o'zbekchada ham xuddi shunday.
"ADO": "ovora-sarson", "AEGIS": "homiylik", "ALE": "el (pivo turi)",
"ALOE": "aloe (sabur)", "AMBER": "qahrabo", "ARBOR": "so'ri; o'q",
"ASP": "ilon (zaharli)", "ASPEN": "tog'terak", "ASTRAL": "yulduzli",
"BARKER": "jarchi", "BAY": "qo'ltiq", "BAYOU": "botqoq irmoq",
"BEAGLE": "bigl (ov iti)", "BELLE": "go'zal qiz", "BEN": "cho'qqi",
"BERRY": "reza meva", "BLOB": "tomchi; dog'", "BOB": "tebranmoq",
"BOD": "gavda", "BONG": "gulduros ovoz", "BRAT": "tarbiyasiz bola",
"BURR": "tikanak", "BUTLER": "xizmatkor boshlig'i", "CHALET": "tog' uyi",
"CHAD": "qog'oz parchasi", "CHI": "chi (yunon harfi)", "CHOP": "chopmoq",
"DOE": "urg'ochi kiyik", "DONG": "jaranglamoq", "DRAKE": "erkak o'rdak",
"DUNK": "botirmoq", "ELF": "elf (afsonaviy mavjudot)", "EMU": "emu (qush)",
"FEAT": "jasorat", "FLAK": "zenit o'ti; tanqid", "FLOP": "muvaffaqiyatsizlik",
"FOLIO": "varaq", "FORD": "kechuv", "FORTE": "kuchli tomon",
"GAL": "qiz", "GALA": "tantana", "GEEK": "qiziquvchan bilimdon",
"GLEN": "tor vodiy", "GONG": "gong", "GOO": "yopishqoq modda",
"GRUB": "qurt; ovqat", "HACK": "buzmoq; chopmoq", "HANK": "kalava",
"HART": "erkak bug'u", "HASH": "maydalangan taom", "HOLLY": "xushtaka (o'simlik)",
"HUFF": "xafa bo'lmoq", "HULK": "bahaybat", "JAB": "sanchmoq",
"JAY": "zog'cha", "JIVE": "jayv (raqs)", "KEG": "bochka",
"KOI": "koi (baliq)", "LAGER": "lager (pivo)", "LAIRD": "yer egasi",
"LAM": "qochmoq", "LAMA": "lama (rohib)", "LARK": "to'rg'ay",
"LEA": "o'tloq", "LIMBO": "noaniq holat", "LOCO": "aqldan ozgan",
"MANTIS": "bug'doyiq", "MAR": "buzmoq", "MART": "bozor",
"MASH": "ezmoq", "MASON": "g'isht teruvchi", "MEAD": "asal sharobi",
"MESA": "yassi tepalik", "MINION": "quyi xizmatkor", "MITT": "qo'lqop",
"NAAN": "non", "NAVE": "ibodatxona o'rtasi", "OGRE": "odamxo'r dev",
"OPAL": "opal (qimmatbaho tosh)", "OTTER": "qunduz", "PARRY": "qaytarmoq",
"PASTOR": "ruhoniy", "PECK": "cho'qimoq", "PERCH": "qo'nmoq; olabug'a",
"PIKE": "cho'rtan baliq", "PING": "jiringlamoq", "PIP": "urug'",
"PIPER": "naychi", "PLAID": "katakli mato", "PLAT": "chizma",
"POD": "qo'zoq", "PORTER": "yuk tashuvchi", "PUNT": "qayiq; tepmoq",
"RAD": "zo'r", "RAJ": "hukmronlik", "RAJA": "roja (hukmdor)",
"ROACH": "suvarak", "ROBIN": "qizilto'sh", "ROUGE": "upa-elik",
"ROWAN": "chetan", "RUE": "afsuslanmoq", "RUFF": "burma yoqa",
"SARI": "sari (hind kiyimi)", "SCRUM": "to'polon", "SEXTON": "cherkov qorovuli",
"SHAH": "shoh", "SKID": "sirg'anmoq", "SLASH": "kesmoq",
"SLING": "osma bog'ich", "SNOOP": "poylamoq", "SOL": "quyosh",
"SPRITE": "parichehra", "STIGMA": "tamg'a", "STOKE": "olovni kuchaytirmoq",
"STUB": "qoldiq", "TAB": "yorliq", "TAM": "yassi qalpoq",
"TANG": "o'tkir ta'm", "TENDON": "pay", "TINDER": "chaqmoqtosh po'stlog'i",
"TOME": "yirik kitob", "TONER": "toner; teri suyuqligi", "TOR": "qoyali tepa",
"TROLL": "trol (afsonaviy)", "TROPE": "ko'chma ma'no", "TRUSS": "ferma; bog'lam",
"TUNDRA": "tundra", "VALE": "vodiy", "VALET": "xizmatkor",
"WAN": "rangpar", "WREN": "chittak", "YAK": "yak (qo'tos)",
"YIN": "in (falsafada)", "YANG": "yan (falsafada)", "ZIG": "burilish",
"PIA": "yumshoq parda", "PRIMA": "birinchi", "PROTO": "dastlabki",
"SILVA": "o'rmon", "SURREY": "yengil arava", "TOD": "tulki",
"TREY": "uchlik", "TAROT": "taro (folbin kartalari)", "RUDD": "qizilqanot baliq",

# --- Egalik qo'shimchasi bilan qolgan otlar ---
#
# Google so'zni gap ichidagidek tarjima qiladi va uchinchi shaxs egalik
# qo'shimchasini qo'shib yuboradi: "havzasi", "tugmasi", "belgisi".
# Lug'atda so'z BOSH SHAKLDA turishi kerak — o'yinchi uni shu holda
# o'rganadi. audit_translations.py shu naqshni topadi.
"ACADEMY": "akademiya", "BASIN": "havza", "BIOGRAPHY": "biografiya",
"BUTTON": "tugma", "CONTENT": "mazmun", "EXTENT": "daraja; hajm",
"FLAGSHIP": "flagman", "FOUNDER": "asoschi", "FUNCTION": "funksiya; vazifa",
"GRANDSON": "nabira", "HORNET": "eshakari", "LOVER": "sevgili",
"MISTRESS": "beka; ma'shuqa", "MIXTURE": "aralashma", "NUCLEI": "yadrolar",
"TINGLING": "jimirlash",
"PALETTE": "palitra", "PATRON": "homiy", "PEAK": "cho'qqi",
"RATE": "daraja; narx", "RECORDER": "yozib oluvchi qurilma",
"SIGN": "belgi", "SPECIES": "tur; turlar", "SPONSOR": "homiy",
"SUCCESSOR": "voris", "SURNAME": "familiya", "TECHNIQUE": "texnika; uslub",
"TORSO": "gavda", "TURNOVER": "aylanma", "WIFE": "xotin",

# --- Ma'nosi noto'g'ri berilgan so'zlar ---
#
# Bular namunani qo'lda ko'zdan kechirganda topildi: tarjima o'zbekcha,
# lekin ma'no boshqa. Mashina tarjimasi eng ko'p shu yerda adashadi —
# bir necha ma'noli so'zning noto'g'ri ma'nosini tanlaydi.
"GUST": "shamol epkini",          # "shamol" emas: bu KESKIN esish
"STUD": "qadama; ayg'ir",         # "zirh" (sovut) mutlaqo boshqa narsa
"CAROL": "bayram qo'shig'i",      # "kerol" — tarjima emas, transliteratsiya
"DENTAL": "tishga oid",           # "stomatologiya" — ot, bu esa sifat

# --- Ko'plik va zamon shakllari ---
#
# Bular endi bonus sifatida qabul qilinadi (ALLOW_INFLECTED_BONUS),
# lekin avtomatik tarjimon ularning bir qismiga javob qaytarmadi.
# Tarjimasiz so'z o'yinchiga ma'nosini ko'rsatmaydi — shuning uchun
# qo'lda yozildi. Qavs ichida asos shakl: o'yinchi bog'lanishni ko'rsin.
"ARCHES": "kamarlar", "AVERTED": "oldini oldi", "BACKED": "qo'llab-quvvatladi",
"BASES": "asoslar", "BLEED": "qon ketmoq", "BONDED": "bog'landi",
"BRAINS": "miyalar", "BRED": "yetishtirdi (breed)", "DOGS": "itlar",
"DOING": "qilish", "DONE": "bajarilgan", "DRAWN": "chizilgan (draw)",
"LED": "boshlab bordi (lead)", "NEEDS": "ehtiyojlar",
"NOSED": "burunli", "OPTICS": "optika", "PANTS": "shim",
"QUITS": "tark etadi", "RAVING": "alahlash", "THROWN": "tashlangan (throw)",

# --- Lug'at kengaygandan keyin topilgan nuqsonlar ---
#
# Turkcha qaytganlar (Google o'zbekcha o'rniga turkcha beradi):
"BREAM": "tangabaliq", "CELIAC": "tseliakiya (kasallik)",
"EAVES": "tom chekkasi", "FRYER": "qovurgich", "PANTY": "ichki ishton",
"SEEP": "sizib chiqmoq", "WART": "so'gal", "WINCH": "chig'ir",
# Umuman tarjima qilinmay, inglizchasi qolganlar:
"FARROW": "cho'chqa bolalamoq", "HEW": "chopmoq", "MAW": "og'iz; oshqozon",
"MEW": "miyovlamoq", "TWIT": "ahmoq; mazax qilmoq",
"WOLD": "yalang tepalik", "WORT": "shira (pivo suyuqligi)",
"YAW": "yon tomonga burilish", "YEW": "tis daraxti",
"MEWS": "otxona ko'chasi", "STRAPS": "tasmalar",
}


def main():
    out = ROOT / "web_app" / "data" / "dict.json"
    out.parent.mkdir(parents=True, exist_ok=True)

    # Mavjud faylni yo'qotmaymiz — ustiga qo'shamiz (bonus tarjimalari alohida
    # qo'shilishi mumkin).
    existing = {}
    if out.exists():
        try:
            existing = json.loads(out.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}

    # Avtomatik tarjimalar (autotranslate.py) — QO'LDA yozilganidan PASTROQ
    # ustuvorlikda. Shu tartib muhim: avtomatika xato tarjima berishi mumkin
    # ("bat" -> ko'rshapalak yoki tayoq), qo'lda tuzatilgani esa doim yutadi.
    auto = {}
    auto_path = ROOT / "data" / "uz_auto.json"
    if auto_path.exists():
        try:
            auto = json.loads(auto_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            auto = {}

    merged = {**existing, **auto, **UZ}

    # Faqat HOZIRGI puzzlelarda uchraydigan so'zlar qoldiriladi.
    #
    # Ilgari fayl faqat o'sardi: eski yozuvlar hech qachon o'chmasdi.
    # Natijada lug'atdan chiqarilgan so'zlar (atoqli otlar, sleng)
    # dict.json da qolib ketgan va tekshiruvda qayta chiqib turgan edi.
    # Bundan tashqari o'yinchi keraksiz kilobaytlarni yuklab olardi.
    used = set()
    for f in sorted((ROOT / "data" / "puzzles").glob("stage_*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        for lvl in data["levels"]:
            for p in lvl["puzzles"]:
                used.update(p["words"])
                used.update(p.get("bonus", []))

    dropped = len(merged) - len(used & set(merged))
    merged = {k: v for k, v in sorted(merged.items()) if k in used}

    # TUTUQ BELGISI BIR XIL BO'LSIN.
    #
    # Manbalar har xil: qo'lda yozilgani oddiy apostrof (') ishlatadi,
    # Google esa ba'zan ' yoki ʻ qaytaradi. Ko'zga farqi bilinmaydi,
    # lekin bu ayni bir harf uch xil kodlanishi demak. Shu yerda
    # bir xillashtiriladi va boshqa ajralib keta olmaydi.
    fix = str.maketrans({"‘": "'", "’": "'", "ʻ": "'",
                         "´": "'", "`": "'"})
    merged = {k: v.translate(fix).strip() for k, v in merged.items()}
    out.write_text(json.dumps(merged, ensure_ascii=False, indent=0), encoding="utf-8")

    # data/ ichiga ham nusxa (manba sifatida)
    (ROOT / "data" / "dict.json").write_text(
        json.dumps(merged, ensure_ascii=False, indent=0), encoding="utf-8")

    print(f"Qo'lda yozilgan : {len(UZ):,} so'z")
    print(f"Avtomatik       : {len(auto):,} so'z")
    print(f"Ishlatilmagani tozalandi: {dropped:,}")
    print(f"dict.json ga yozildi: {len(merged):,} so'z")
    return 0


if __name__ == "__main__":
    sys.exit(main())
