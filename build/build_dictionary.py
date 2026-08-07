"""
Apex Words — lug'at bazasini yig'uvchi skript.

Ikkita ro'yxat hosil qiladi:
  data/wordlist_core.txt  — TANISH so'zlar. Puzzle'ning yechim so'zlari shundan olinadi.
  data/wordlist_full.txt  — KENGROQ ro'yxat. Bonus (+1) so'zlar shu bo'yicha tekshiriladi.

Manbalar (ikkalasi ham ochiq va bepul):
  * wordfreq    — so'zning ishlatilish chastotasi (zipf shkalasi).  "Bu so'z oddiymi?"
  * NLTK words  — Unix lug'ati, ~234k yozuv.                        "Bu so'z bormi?"

So'z ro'yxatga tushishi uchun uchala shartni bajarishi kerak:
  1. NLTK lug'atida bor
  2. chastotasi bo'sag'adan yuqori
  3. KO'PLIK yoki ZAMON shakli EMAS  <-- pastdagi izohga qarang

NEGA ko'plik va zamon shakllari chiqarib tashlanadi
---------------------------------------------------
Bu o'yin lug'at o'rgatadi. 'cats -> mushuklar', 'played -> o'ynadi' kabi shakllar
yangi so'z o'rgatmaydi, faqat ro'yxatni shishiradi va bir xil so'z ikki marta
uchraydi. Shuning uchun faqat lug'aviy asos shakl qoldiriladi:
    cat, play, note, stone   ->  bor
    cats, played, playing, notes, stones  ->  yo'q

Buni suffiks qoidalari (is_inflected) va noto'g'ri fe'llar ro'yxati
(IRREGULAR_FORMS) amalga oshiradi. Qoidaga tasodifan tushib qoladigan haqiqiy
asos so'zlar KEEP_ANYWAY ro'yxatida himoyalangan ('news', 'morning', 'yes'...).

Qiyoslash darajalari (-er/-est) va ravishlar (-ly) TEGILMAYDI — ular ko'plik ham,
zamon ham emas: 'bigger', 'quickly' o'yinda qoladi.

Ishga tushirish:
    python build/build_dictionary.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
NLTK_DIR = ROOT / "build" / "nltk_data"

# --- Sozlamalar -------------------------------------------------------------

MIN_LEN = 3
MAX_LEN = 9

# zipf shkalasi: 7 = "the", 4 = 10 000 so'zda bir marta, 3 = 100 000 da bir, 2 = millionda bir.
# Bo'sag'a o'lchov bilan tanlandi. 12 bosqich uchun 3000 ta yaroqli baza
# so'z kerak; har bo'sag'ada nechta chiqishi sanab ko'rilgan:
#     3.80 -> 2956 (yetmaydi)   3.60 -> 3873   3.40 -> 4987
# 3.60 tanlandi: zaxira yetarli va so'zlar hali ham tanish qoladi
# (taxminan eng ko'p ishlatiladigan 5300 so'z).
CORE_ZIPF = 3.60   # yechim so'zlari uchun — o'rtacha o'quvchi taniydigan daraja
# Bonus bo'sag'asi ATAYLAB core'ga yaqin. 2.60 da ro'yxatga 'aam', 'dak', 'goran'
# kabi minglab chet tili tokeni va qisqartma tushib qolgan edi — o'yinchi ularni
# tasodifan yasab +1 olardi va tarjima oynasida ma'nosiz so'z ko'rardi.
# 3.05 da bonus so'zlar haqiqiy, o'rgatishga arziydigan so'zlar bo'lib qoladi
# va shu bilan birga bonus mexanikasi yetarlicha tez-tez ishlaydi.
FULL_ZIPF = 3.05

# Bonus ro'yxatida ham ko'plik/zamon shakllari bo'lmasin.
# True qilinsa, o'yinchi 'CATS' yozganda +1 bonus oladi (lekin so'z o'rgatilmaydi).
ALLOW_INFLECTED_BONUS = False

VOWELS = set("aeiou")

# Tarkibida shular bo'lgan so'zlar o'yinga kiritilmaydi (ta'limiy bot, yosh auditoriya).
BLOCKLIST = {
    "anal", "anus", "arse", "ass", "balls", "bastard", "bitch", "bloody", "bollocks",
    "boner", "boob", "boobs", "booty", "bugger", "bukkake", "butt", "clit", "cock",
    "coon", "crap", "cum", "cunt", "dago", "damn", "dick", "dildo", "dyke", "erotic",
    "fag", "faggot", "fart", "fuck", "fucked", "fucker", "fucking", "gay", "gook",
    "hell", "hoe", "homo", "horny", "incest", "jizz", "kike", "lust", "milf",
    "nazi", "negro", "nigga", "nigger", "nipple", "orgasm", "orgy", "penis", "piss",
    "poop", "porn", "prick", "pube", "pussy", "queer", "rape", "rapist", "retard",
    "scrotum", "semen", "sex", "sexy", "shit", "shitty", "slut", "smut", "sperm",
    "spic", "tit", "tits", "titty", "turd", "twat", "vagina", "viagra",
    "wank", "whore", "wop", "hooker", "booker", "pimp", "stripper",
}

# Chastotasi yuqori, lekin so'z emas: qisqartma, sleng, internet tokenlari.
MANUAL_DROP = {
    "http", "https", "www", "com", "org", "net", "html", "php", "url", "api",
    "lol", "lmao", "omg", "wtf", "idk", "btw", "asap", "faq", "diy",
    "pdf", "jpg", "png", "gif", "mp3", "mp4", "usb", "gps", "sms",
    "nan", "nil", "aaa", "abc", "xyz", "etc", "vol", "pls", "thx", "yea", "yep",
    "iso", "prog", "admin", "config", "init", "src", "img", "temp",
    "min", "max", "avg", "std", "misc", "num", "obj", "str", "int", "var",
    "gonna", "wanna", "gotta", "aint", "dont", "cant", "wont", "isnt", "didnt",
    "ive", "youre", "theyre", "hes", "shes", "thats", "whats", "lets",
    # hafta kunlari / oylar qisqartmasi.
    # DIQQAT: 'sun', 'may', 'march', 'wed' ATAYLAB yo'q — ular haqiqiy so'z.
    "mon", "tue", "tues", "thu", "thur", "thurs", "fri", "sat",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct",
    "nov", "dec",
    # vaqt mintaqalari, o'lchov va idoraviy qisqartmalar
    "ist", "est", "gmt", "utc", "cet", "pst",
    "qty", "amt", "dept", "govt", "univ", "inc", "ltd", "corp", "assn", "bros",
    # lotin bo'laklari, chet tili tokenlari va shevalar
    "sic", "viz", "ibid", "ser", "che", "mir", "sie", "fra", "aer", "rea",
    "ria", "alb", "bal", "ber", "deb", "reb", "sher", "chee", "cee", "aru",
    "ras", "sai", "sar", "lod", "loy", "youd", "mino", "nep", "ust", "feu",
    "wot", "sri", "tch", "ure", "hep", "nee", "bis", "bobo", "cate", "dor",
    "tou", "shay", "kip", "ino", "sur",
    # yechim so'zlari qo'lda ko'rib chiqilganda topilgan qolgan axlat:
    # prefiks/suffikslar, qisqartmalar, chet so'zlar, sleng
    "mal", "ons", "tha", "ness", "bae", "lan", "das", "dis", "cha", "tri",
    "dang", "dos", "holt", "mil", "quo", "alt", "poly", "spec", "amino",
    "bon", "gal", "circa", "chi", "til", "hao", "wah", "wha", "ers", "ast",
    "sla", "tal", "aes", "ase", "bas", "bes", "sab", "gra", "sao", "siva",
    "mem", "mim", "shi", "ala", "aly", "awa", "lys", "saa", "gon", "gor",
    "gros", "nog", "ons", "ary", "yar", "hei", "het", "cit", "hist", "ich",
    "bel", "tur", "yer", "ret", "roi", "ova", "mam", "pol",
    # prefiks/suffikslar va Yunon harflari — so'z emas
    "ing", "neo", "non", "semi", "anti", "phi", "chi", "psi", "eta", "rho",
    "pac", "sen", "col", "cos", "tor", "sec", "ref", "prof", "rep", "pic",
    # arxaik olmoshlar va undov so'zlar — ta'limiy qiymati yo'q
    "tho", "thee", "thou", "thy", "thine", "hath", "doth", "aha", "ugh",
    "heck", "aye", "yea", "lo", "alas",
    # sleng, arxaik va noaniq so'zlar (qo'lda ko'rib chiqishda topilgan)
    "sup", "wan", "dell", "rue", "pee", "dope", "tee", "bot", "dub", "gig",
    "con", "pac", "boo", "din", "nun", "tar", "bra",
    # bonus ro'yxatini qo'lda ko'rib chiqishda topilgan axlat:
    # chet tili tokenlari, ismlar, qisqartmalar, arxaizmlar
    "aba", "abu", "aga", "ama", "amin", "amor", "ani", "anon", "bac", "bah",
    "berg", "bom", "bora", "cho", "chun", "coli", "cor", "crore", "dade",
    "dae", "dah", "dak", "dal", "dar", "daw", "desi", "dey", "div", "dod",
    "ere", "eyre", "fam", "fei", "foo", "fro", "gage", "gan", "ger", "git",
    "goa", "haw", "howe", "hoy", "ide", "ism", "kan", "lac", "lai", "lam",
    "lat", "lim", "lis", "mage", "mali", "mana", "mani", "mas", "mau", "mig",
    "mor", "mot", "mou", "naw", "nye", "oda", "obi", "peed", "pom", "pubic",
    "rah", "rel", "roc", "sha", "sho", "slain", "slew", "soc", "soho", "tae",
    "tai", "taj", "tat", "tau", "tay", "tele", "toro", "toto", "tra", "tron",
    "tum", "vis", "wen", "wight", "wis", "yah", "yan", "yee", "zac", "alp",
    "carr", "fiat", "apa", "bain", "bose", "dum", "hah", "hud", "lux",
    "napa", "pap", "pow", "soma",

    # --- Atoqli otlar, brendlar, joy nomlari ---
    # Bular chastota bo'yicha o'tib ketadi (matnlarda ko'p uchraydi), lekin
    # o'quv o'yinida ularning o'rni yo'q: o'yinchi lug'at emas, ism o'rganadi.
    "aka", "alba", "alfa", "apache", "ascot", "bafta", "bali", "bangkok",
    "borg", "bundy", "cisco", "draper", "excel", "fuji", "gable", "harper",
    "hasan", "huron", "kemp", "kraft", "levant", "massa", "montana", "muir",
    "nash", "pau", "pell", "portman", "prius", "rohan", "romero", "ryder",
    "singh", "taft", "timor", "tonga", "ulster", "chang", "cheng", "kang",
    "liang", "meng", "ming", "ling", "ting", "tung",

    # --- Sleng, qisqartma va chala shakllar ---
    "biz", "blah", "bop", "boomer", "brill", "coz", "dada", "demi", "dev",
    "diss", "duff", "dun", "gator", "glam", "grad", "playa", "prob", "quot",
    "wiz", "zee", "shiv", "skit", "stoke", "topper", "repost",

    # --- Boshqa tillardan kirib qolgan bo'laklar ---
    "bien", "blanc", "blanco", "mater", "pax", "salle", "sera", "uva",
}

# Brown korpusi qamrab olmaydigan joy nomlari, brendlar va boshqa atoqli otlar.
# DIQQAT: 'apple', 'turkey', 'orange' bu yerda ATAYLAB yo'q — ular oddiy so'z.
PLACES_AND_BRANDS = {
    "russia", "china", "india", "japan", "korea", "brazil", "canada", "mexico",
    "france", "spain", "italy", "poland", "egypt", "kenya", "chile", "peru",
    "cuba", "iran", "iraq", "syria", "libya", "sudan", "ghana", "nepal",
    "yemen", "asia", "africa", "europe", "america", "arctic", "pacific",
    "texas", "paris", "london", "tokyo", "berlin", "madrid", "moscow", "dubai",
    "rome", "vienna", "athens", "cairo", "delhi", "boston", "denver", "miami",
    "google", "amazon", "tesla", "toyota", "honda", "nokia", "sony", "hulu",
    "netflix", "reddit", "twitter", "yahoo", "adobe", "intel", "nvidia",
    "milo", "bilbo", "dylan", "elvis", "monte", "polk", "dewey", "bowie",
    "laker", "chico", "arjun", "sind", "rus", "covid",
    "surrey", "mormon", "homer", "pagan", "mecca", "eden", "sahara",
    "malik", "manila", "guinea", "alumni", "borneo", "congo", "malta",
    "indy", "aussie", "brit", "yank", "kiwi",
}

# Olmoshlar va artikllar — TO'RGA tushmasin, faqat BONUS bo'lsin.
#
# 'ITS', 'HIM', 'HIS' kabi so'zlar grammatik yordamchi so'zlar: ularni katakka
# qo'yish yangi lug'at o'rgatmaydi va o'yin zerikarli ko'rinadi. Lekin o'yinchi
# ularni tasodifan yasab qolsa "bunday so'z yo'q" deyish ham noto'g'ri.
# Shuning uchun core'dan chiqariladi, full'da qoladi -> topilsa +1 bonus.
BONUS_ONLY = {
    "i", "me", "my", "mine", "myself",
    "you", "your", "yours", "yourself", "yourselves",
    "he", "him", "his", "himself",
    "she", "her", "hers", "herself",
    "it", "its", "itself",
    "we", "us", "our", "ours", "ourselves",
    "they", "them", "their", "theirs", "themselves",
    "who", "whom", "whose",
    "the", "an", "a",
}

# Ko'plik/zamon qoidalariga TASODIFAN tushib qoladigan haqiqiy asos so'zlar.
# Masalan: 'news' -> 'new' (asos so'z), 'morning' -> 'morn' (asos so'z),
# lekin 'news' va 'morning' ko'plik/zamon shakli emas.
KEEP_ANYWAY = {
    # -s bilan tugaydigan, lekin ko'plik bo'lmagan so'zlar.
    # DIQQAT: 'was' va 'has' bu yerda YO'Q — ular 'be'/'have' ning zamon shakli,
    # ularni IRREGULAR_FORMS chiqarib tashlaydi.
    "yes", "his", "its", "gas", "bus", "news", "lens", "plus",
    "thus", "always", "perhaps", "species", "series", "basis", "cosmos",
    "campus", "focus", "virus", "bonus", "chaos", "canvas", "atlas", "citrus",
    "minus", "census", "tennis", "circus", "chorus", "genius", "radius",
    "status", "surplus", "hers", "yours", "ours",
    # -ing bilan tugaydigan, lekin fe'l shakli bo'lmagan so'zlar
    "morning", "evening", "ceiling", "during", "willing", "building", "meeting",
    "string", "spring", "ring", "king", "wing", "sing", "thing", "bring",
    "nothing", "something", "anything", "everything", "shilling", "sterling",
    # -ed bilan tugaydigan, lekin o'tgan zamon bo'lmagan so'zlar
    "wicked", "sacred", "hundred", "hatred", "naked", "indeed", "speed", "breed",
    "greed", "creed", "tweed", "shred",
}

# Suffiks qoidalari ushlolmaydigan noto'g'ri (irregular) fe'l va ot shakllari.
# DIQQAT: 'saw', 'left', 'felt', 'found', 'read', 'set', 'put' kabilar mustaqil
# so'z sifatida ham keng ishlatilgani uchun ATAYLAB kiritilmagan.
IRREGULAR_FORMS = {
    # to be / to have / to do
    "was", "were", "been", "being", "am", "are", "is", "had", "having",
    "does", "doing", "done", "did",
    # eng ko'p uchraydigan noto'g'ri fe'llar
    "went", "gone", "took", "taken", "came", "seen", "knew", "known",
    "gave", "given", "became", "begun", "began", "written", "wrote",
    "spoke", "spoken", "chose", "chosen", "broke", "broken", "drove", "driven",
    "ate", "eaten", "flew", "flown", "threw", "thrown", "grew", "grown",
    "blew", "blown", "drew", "drawn", "swam", "swum", "drank", "drunk",
    "sang", "sung", "rang", "rung", "sank", "sunk", "rose", "risen",
    "fallen", "forgot", "forgotten", "forgave", "hidden", "hid", "bitten",
    "ridden", "rode", "shaken", "shook", "stolen", "stole", "swore", "sworn",
    "torn", "tore", "worn", "wore", "woke", "woken", "beaten", "bent",
    "brought", "bought", "caught", "taught", "sought", "fought", "sold",
    "told", "slept", "swept", "wept", "crept", "kept", "dealt", "meant",
    "dreamt", "burnt", "learnt", "spelt", "built", "sent", "spent", "lent",
    "understood", "stood", "heard", "held", "lost", "made", "paid", "laid",
    "said", "sat", "met", "won", "shot", "hung", "dug", "stuck", "struck",
    # noto'g'ri ko'plik shakllari
    "men", "women", "children", "feet", "teeth", "geese", "mice", "lice",
    "oxen", "wives", "knives", "lives", "leaves", "halves", "shelves",
    "thieves", "loaves", "calves", "wolves", "selves", "criteria", "phenomena",
    "crises", "alumni", "fungi", "cacti", "indices", "matrices", "analyses",
    # 4 harfli o'tgan zamon shakllari.
    # Bularni qoida ushlolmaydi: inflection_stems() da '-ed' sharti n > 4,
    # chunki uni 4 harfga tushirsak 'feed' -> 'fee', 'seed' -> 'see',
    # 'need' -> 'nee' kabi HAQIQIY asos so'zlar noto'g'ri o'chib ketardi.
    # Shuning uchun 4 harfli o'tgan zamonlar shu yerda qo'lda sanaladi.
    "used", "aged", "bred", "fled", "bled", "sped", "tied", "died", "lied",
    "dyed", "eyed", "iced", "owed", "awed", "aced", "hued",
    # qoidadan chetda qolgan noto'g'ri shakllar.
    # 'shed', 'wed', 'bid', 'fit', 'cut', 'put' ATAYLAB yo'q — ular asos shakl ham.
    "got", "gotten", "ran", "led", "fed", "shown", "woven", "upheld", "has",
    "spun", "clung", "flung", "stung", "swung", "wrung", "slid", "frozen",
    # 5 harfli '-ing' shakllari. Qoidada shart n > 5, chunki uni pasaytirsak
    # 'bring', 'thing', 'sting', 'swing', 'cling', 'fling' kabi ASOS so'zlar
    # noto'g'ri o'chib ketardi. Shuning uchun bu beshtasi qo'lda sanaladi.
    "going", "dying", "lying", "tying", "vying",
}


def ensure_nltk():
    """NLTK korpuslarini build/nltk_data ichiga yuklaydi (repoga tushmaydi)."""
    import nltk

    NLTK_DIR.mkdir(parents=True, exist_ok=True)
    if str(NLTK_DIR) not in nltk.data.path:
        nltk.data.path.insert(0, str(NLTK_DIR))
    for pkg in ("words", "names", "brown"):
        try:
            nltk.data.find(f"corpora/{pkg}")
        except LookupError:
            print(f"  NLTK '{pkg}' yuklanmoqda...")
            nltk.download(pkg, download_dir=str(NLTK_DIR), quiet=True)


def build_proper_noun_test():
    """
    Atoqli otlarni aniqlovchi funksiya qaytaradi.

    Muammo: wordfreq hamma tokenni kichik harfda beradi, NLTK words korpusida esa
    'dan', 'lee', 'russia' kabi yozuvlar kichik harfda ham bor. Natijada ismlar
    va joy nomlari o'yinga tushib ketadi.

    Yechim — ikki signal:
      1. NLTK 'names' korpusi (7.5k ism): dan, seth, ken, lee, kim...
      2. Brown korpusida so'zning BOSH HARF bilan yozilish nisbati. Gap boshidagi
         so'zlar hisobga olinmaydi (ular baribir bosh harfli).
         'russia' -> 1.00, 'china' -> 0.91  |  'water' -> 0.02, 'house' -> 0.32

    Faqat ismlar ro'yxatiga tayanib bo'lmaydi: 'may' ham ism, ham modal fe'l.
    Shuning uchun Brown nisbati ustun turadi — 'may' nisbati 0.07, demak saqlanadi.
    """
    from collections import Counter
    from nltk.corpus import brown, names

    first_names = {n.lower() for n in names.words()}

    cap, low = Counter(), Counter()
    for sent in brown.sents():
        for i, tok in enumerate(sent):
            if i == 0 or not tok.isalpha():
                continue          # gap boshi tashlanadi — u har doim bosh harfli
            if tok[0].isupper():
                cap[tok.lower()] += 1
            else:
                low[tok.lower()] += 1

    def is_proper(w: str) -> bool:
        if w in PLACES_AND_BRANDS:
            return True
        n = cap[w] + low[w]
        ratio = cap[w] / n if n >= 3 else None
        if w in first_names:
            # Ism, lekin oddiy so'z ham bo'lishi mumkin ('may', 'rose', 'will').
            # Brown ko'rsatkichi hal qiladi; ma'lumot bo'lmasa — ism deb bilamiz.
            return ratio is None or ratio >= 0.50
        return ratio is not None and ratio >= 0.85

    return is_proper


def inflection_stems(w: str):
    """
    Agar w ko'plik yoki zamon shakli bo'lsa, uning ehtimoliy asos shakllarini
    qaytaradi. Faqat KO'PLIK va ZAMON qo'shimchalari tekshiriladi —
    -er/-est/-ly/-ness ga tegilmaydi.
    """
    n = len(w)

    # --- Ko'plik / III shaxs birlik ---
    if w.endswith("ies") and n > 4:
        yield w[:-3] + "y"                    # tries  -> try
    if w.endswith(("ses", "xes", "zes", "ches", "shes")) and n > 4:
        yield w[:-2]                          # boxes  -> box
    if w.endswith("ves") and n > 4:
        yield w[:-3] + "f"                    # leaves -> leaf
        yield w[:-3] + "fe"                   # knives -> knife
    if w.endswith("s") and not w.endswith("ss") and n > 3:
        yield w[:-1]                          # cats   -> cat
        if w.endswith("es"):
            yield w[:-2]                      # wishes -> wish

    # --- O'tgan zamon ---
    if w.endswith("ied") and n > 4:
        yield w[:-3] + "y"                    # tried  -> try
    if w.endswith("ed") and n > 4:
        yield w[:-2]                          # played -> play
        yield w[:-1]                          # baked  -> bake
        if n > 5 and w[-3] == w[-4] and w[-3] not in VOWELS:
            yield w[:-3]                      # hopped -> hop

    # --- Davomiy zamon ---
    if w.endswith("ing") and n > 5:
        yield w[:-3]                          # playing -> play
        yield w[:-3] + "e"                    # baking  -> bake
        if n > 6 and w[-4] == w[-5] and w[-4] not in VOWELS:
            yield w[:-4]                      # running -> run


def main():
    print("=" * 62)
    print("Apex Words — lug'at bazasi qurilmoqda")
    print("=" * 62)

    print("\n[1/5] NLTK korpusi tekshirilmoqda...")
    ensure_nltk()

    from nltk.corpus import words as nltk_words
    from wordfreq import top_n_list, zipf_frequency

    print("[2/5] Nomzod so'zlar chastota ro'yxatidan olinmoqda...")
    candidates = top_n_list("en", 200_000)
    print(f"      {len(candidates):,} ta token")

    print("[3/5] Shakl bo'yicha filtrlanmoqda (uzunlik, faqat a-z, blocklist)...")
    shaped = []
    for w in candidates:
        if not (MIN_LEN <= len(w) <= MAX_LEN):
            continue
        if not w.isalpha() or not w.isascii():
            continue
        if not w.islower():                   # atoqli otlar, qisqartmalar
            continue
        if w in BLOCKLIST or w in MANUAL_DROP:
            continue
        if len(set(w)) == 1:                  # 'aaa', 'zzz'
            continue
        shaped.append(w)
    print(f"      {len(shaped):,} ta qoldi")

    print("[4/5] Atoqli ot aniqlagichi tayyorlanmoqda (Brown korpusi)...")
    is_proper = build_proper_noun_test()

    print("[5/6] Lug'at + ko'plik/zamon + atoqli ot filtri...")
    # DIQQAT: .lower() QILINMAYDI. NLTK words korpusida atoqli otlar bosh harf
    # bilan alohida yozuv sifatida turadi ('Mary', 'Dylan', 'Yemen'). wordfreq esa
    # hamma tokenni kichik harfda beradi, shuning uchun korpusni kichraytirsak
    # 'mary', 'elvis', 'bilbo' kabi ismlar o'yinga tushib ketadi.
    # Faqat kichik harfli yozuvlarni olamiz — bu atoqli otlarni kesib tashlaydi.
    known = {w for w in nltk_words.words() if w.islower()}
    print(f"      NLTK words korpusi: {len(known):,} yozuv (atoqli otlarsiz)")

    def is_inflected(w: str) -> bool:
        """w — boshqa so'zning ko'plik yoki zamon shaklimi?"""
        if w in KEEP_ANYWAY:
            return False
        if w in IRREGULAR_FORMS:
            return True
        # Asos shakl haqiqiy so'z bo'lsagina qo'shimcha deb hisoblaymiz:
        # 'bus' -> 'bu' so'z emas, demak 'bus' ko'plik emas.
        return any(s in known for s in inflection_stems(w))

    core, full = [], []
    dropped_infl = dropped_proper = 0
    for w in shaped:
        if w not in known:
            continue
        if is_proper(w):
            dropped_proper += 1
            continue
        if is_inflected(w):
            dropped_infl += 1
            if not ALLOW_INFLECTED_BONUS:
                continue

        z = zipf_frequency(w, "en")
        if z >= FULL_ZIPF:
            full.append(w)
            # BONUS_ONLY so'zlari full'da qoladi, lekin core'ga tushmaydi:
            # o'yinchi ularni topsa +1 oladi, ammo to'rda katak bo'lmaydi.
            # BONUS_ONLY endi ishlatilmaydi: olmoshlar ham to'liq huquqli
            # so'z sifatida qabul qilinadi (ular ham o'rganiladigan lug'at).
            if z >= CORE_ZIPF and not is_inflected(w):
                core.append(w)

    core.sort()
    full.sort()
    print(f"      atoqli ot deb chiqarildi           : {dropped_proper:,}")
    print(f"      ko'plik/zamon shakli deb chiqarildi: {dropped_infl:,}")
    print(f"      core (yechim so'zlari): {len(core):,}")
    print(f"      full (bonus uchun)    : {len(full):,}")

    print("[6/6] Fayllarga yozilmoqda...")
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "wordlist_core.txt").write_text("\n".join(core) + "\n", encoding="utf-8")
    (DATA / "wordlist_full.txt").write_text("\n".join(full) + "\n", encoding="utf-8")

    meta = {
        "core_count": len(core),
        "full_count": len(full),
        "core_zipf": CORE_ZIPF,
        "full_zipf": FULL_ZIPF,
        "inflected_excluded": not ALLOW_INFLECTED_BONUS,
        "min_len": MIN_LEN,
        "max_len": MAX_LEN,
    }
    (DATA / "wordlist_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("\n  Uzunlik taqsimoti:")
    for n in range(MIN_LEN, MAX_LEN + 1):
        c = sum(1 for w in core if len(w) == n)
        f = sum(1 for w in full if len(w) == n)
        print(f"    {n} harf: core {c:>6,}   full {f:>6,}")

    print("\n  Yozildi: data/wordlist_core.txt, data/wordlist_full.txt")
    print("\nTayyor.")


if __name__ == "__main__":
    sys.exit(main())
