"""Ordered runtime stage: 02_speech. Run through pipeline.py only."""


# ---- Source section 25 ----
import re


# ============================================================
# ENGLISH DIGIT WORDS
# ============================================================

DIGIT_WORDS = {
    '0': 'zero',
    '1': 'one',
    '2': 'two',
    '3': 'three',
    '4': 'four',
    '5': 'fyeve',
    '6': 'six',
    '7': 'sevven',
    '8': 'ait',
    '9': 'nine'
}

PHONE_DIGIT_WORDS = DIGIT_WORDS.copy()


# ============================================================
# ENGLISH NUMBER WORDS
# ============================================================

NUMBER_WORDS = {
    0: "zero",
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    5: "fyeve",
    6: "six",
    7: "sevven",
    8: "ait",
    9: "nine",

    10: "ten",
    11: "eleven",
    12: "twelve",
    13: "thirteen",
    14: "fourteen",
    15: "fifteen",
    16: "sixteen",
    17: "seventeen",
    18: "eighteen",
    19: "nineteen",

    20: "twenty",
    30: "thirty",
    40: "forty",
    50: "fifty",
    60: "sixty",
    70: "seventy",
    80: "eighty",
    90: "ninety"
}


def number_to_words(n):

    n = int(n)

    if n < 100:

        if n in NUMBER_WORDS:
            return NUMBER_WORDS[n]

        tens = (n // 10) * 10
        ones = n % 10

        return NUMBER_WORDS[tens] + " " + NUMBER_WORDS[ones]

    if n < 1000:

        hundreds = n // 100
        remainder = n % 100

        result = NUMBER_WORDS[hundreds] + " hundred"

        if remainder:
            result += " and " + number_to_words(remainder)

        return result

    if n < 100000:

        thousands = n // 1000
        remainder = n % 1000

        result = number_to_words(thousands) + " thousand"

        if remainder:
            result += " " + number_to_words(remainder)

        return result

    return " ".join(DIGIT_WORDS[d] for d in str(n))


# ============================================================
# TAMIL DIGITS
# ============================================================

TAMIL_DIGITS = {
    '0': 'பூஜ்ஜியம்',
    '1': 'ஒன்று',
    '2': 'இரண்டு',
    '3': 'மூன்று',
    '4': 'நான்கு',
    '5': 'ஐந்து',
    '6': 'ஆறு',
    '7': 'ஏழு',
    '8': 'எட்டு',
    '9': 'ஒன்பது'
}


# ============================================================
# TAMIL NUMBERS
# ============================================================

TAMIL_NUMBERS = {

    0: 'பூஜ்ஜியம்',
    1: 'ஒன்று',
    2: 'இரண்டு',
    3: 'மூன்று',
    4: 'நான்கு',
    5: 'ஐந்து',
    6: 'ஆறு',
    7: 'ஏழு',
    8: 'எட்டு',
    9: 'ஒன்பது',

    10: 'பத்து',
    11: 'பதினொன்று',
    12: 'பன்னிரண்டு',
    13: 'பதின்மூன்று',
    14: 'பதினான்கு',
    15: 'பதினைந்து',
    16: 'பதினாறு',
    17: 'பதினேழு',
    18: 'பதினெட்டு',
    19: 'பத்தொன்பது',

    20: 'இருபது',
    30: 'முப்பது',
    40: 'நாற்பது',
    50: 'ஐம்பது',
    60: 'அறுபது',
    70: 'எழுபது',
    80: 'எண்பது',
    90: 'தொண்ணூறு'
}


# ============================================================
# TAMIL HUNDREDS
# ============================================================

TAMIL_HUNDREDS = {
    1: 'நூறு',
    2: 'இருநூறு',
    3: 'முந்நூறு',
    4: 'நானூறு',
    5: 'ஐந்நூறு',
    6: 'அறுநூறு',
    7: 'எழுநூறு',
    8: 'எண்ணூறு',
    9: 'தொள்ளாயிரம்'
}


def tamil_number_to_words(n):

    n = int(n)

    if n < 0:
        return 'மைனஸ் ' + tamil_number_to_words(abs(n))

    if n in TAMIL_NUMBERS:
        return TAMIL_NUMBERS[n]

    if 20 < n < 30:
        return 'இருபத்தி ' + TAMIL_NUMBERS[n % 10]

    if 30 < n < 40:
        return 'முப்பத்தி ' + TAMIL_NUMBERS[n % 10]

    if 40 < n < 50:
        return 'நாற்பத்தி ' + TAMIL_NUMBERS[n % 10]

    if 50 < n < 60:
        return 'ஐம்பத்தி ' + TAMIL_NUMBERS[n % 10]

    if 60 < n < 70:
        return 'அறுபத்தி ' + TAMIL_NUMBERS[n % 10]

    if 70 < n < 80:
        return 'எழுபத்தி ' + TAMIL_NUMBERS[n % 10]

    if 80 < n < 90:
        return 'எண்பத்தி ' + TAMIL_NUMBERS[n % 10]

    if 90 < n < 100:
        return 'தொண்ணூற்று ' + TAMIL_NUMBERS[n % 10]

    if n < 1000:

        hundreds = n // 100
        remainder = n % 100

        hundred_word = TAMIL_HUNDREDS[hundreds]

        if not remainder:
            return hundred_word

        if hundred_word.endswith('நூறு'):
            hundred_word = hundred_word.replace(
                'நூறு',
                'நூற்று'
            )

        elif hundred_word == 'தொள்ளாயிரம்':
            hundred_word = 'தொள்ளாயிரத்து'

        return hundred_word + ' ' + tamil_number_to_words(remainder)

    if n < 100000:

        thousands = n // 1000
        remainder = n % 1000

        thousand_word = tamil_number_to_words(thousands)

        if remainder:
            return (
                thousand_word
                + ' ஆயிரத்து '
                + tamil_number_to_words(remainder)
            )

        return thousand_word + ' ஆயிரம்'

    return ' '.join(TAMIL_DIGITS[d] for d in str(n))



# ============================================================
# TAMIL HUNDRED LINKER NORMALIZATION
# ============================================================

def normalize_written_tamil_hundreds(text):
    """
    Correct already-written Tamil number phrases.

    Examples:
        நானூறு                      -> நானூறு
        நானூறு ஐம்பது              -> நானூற்று ஐம்பது
        நானூறு அறுபது              -> நானூற்று அறுபது
        அறுநூறு ஐம்பது             -> அறுநூற்று ஐம்பது
        அறுநூறு அறுபது             -> அறுநூற்று அறுபது

    The linker form is used only when a non-zero remainder follows.
    """

    # Any valid Tamil number word that can follow a hundred.
    remainder = (
        r'(?:'
        r'ஒன்று|இரண்டு|மூன்று|நான்கு|ஐந்து|ஆறு|ஏழு|எட்டு|ஒன்பது|'
        r'பத்து|பதினொன்று|பன்னிரண்டு|பதின்மூன்று|பதினான்கு|'
        r'பதினைந்து|பதினாறு|பதினேழு|பதினெட்டு|பத்தொன்பது|'
        r'இருபது|இருபத்தி(?:\s+\S+)?|'
        r'முப்பது|முப்பத்தி(?:\s+\S+)?|'
        r'நாற்பது|நாற்பத்தி(?:\s+\S+)?|'
        r'ஐம்பது|ஐம்பத்தி(?:\s+\S+)?|'
        r'அறுபது|அறுபத்தி(?:\s+\S+)?|'
        r'எழுபது|எழுபத்தி(?:\s+\S+)?|'
        r'எண்பது|எண்பத்தி(?:\s+\S+)?|'
        r'தொண்ணூறு|தொண்ணூற்று(?:\s+\S+)?'
        r')'
    )

    linker_map = {
        'நூறு': 'நூற்று',
        'இருநூறு': 'இருநூற்று',
        'முந்நூறு': 'முந்நூற்று',
        'நானூறு': 'நானூற்று',
        'ஐந்நூறு': 'ஐந்நூற்று',
        'அறுநூறு': 'அறுநூற்று',
        'எழுநூறு': 'எழுநூற்று',
        'எண்ணூறு': 'எண்ணூற்று',
        'தொள்ளாயிரம்': 'தொள்ளாயிரத்து',
    }

    hundred_pattern = (
        r'(?<![\u0B80-\u0BFF])'
        r'(நூறு|இருநூறு|முந்நூறு|நானூறு|ஐந்நூறு|'
        r'அறுநூறு|எழுநூறு|எண்ணூறு|தொள்ளாயிரம்)'
        r'(?=\s+' + remainder + r')'
    )

    return re.sub(
        hundred_pattern,
        lambda m: linker_map[m.group(1)],
        text
    )


# ============================================================
# TAMIL ORDINALS
# ============================================================

TAMIL_ORDINALS = {
    1: 'முதலாவது',
    2: 'இரண்டாவது',
    3: 'மூன்றாவது',
    4: 'நான்காவது',
    5: 'ஐந்தாவது',
    6: 'ஆறாவது',
    7: 'ஏழாவது',
    8: 'எட்டாவது',
    9: 'ஒன்பதாவது',
    10: 'பத்தாவது',
    11: 'பதினொன்றாவது',
    12: 'பன்னிரண்டாவது',
    13: 'பதின்மூன்றாவது',
    14: 'பதினான்காவது',
    15: 'பதினைந்தாவது',
    16: 'பதினாறாவது',
    17: 'பதினேழாவது',
    18: 'பதினெட்டாவது',
    19: 'பத்தொன்பதாவது',
    20: 'இருபதாவது',
    30: 'முப்பதாவது',
    40: 'நாற்பதாவது',
    50: 'ஐம்பதாவது',
    60: 'அறுபதாவது',
    70: 'எழுபதாவது',
    80: 'எண்பதாவது',
    90: 'தொண்ணூறாவது'
}


def tamil_ordinal_to_words(n):

    n = int(n)

    if n in TAMIL_ORDINALS:
        return TAMIL_ORDINALS[n]

    if 20 < n < 30:

        ones = n % 10

        if ones == 1:
            return 'இருபத்தொன்றாவது'

        return 'இருபத்தி' + tamil_number_to_words(ones) + 'வது'

    if 30 < n < 40:

        ones = n % 10

        if ones == 1:
            return 'முப்பத்தொன்றாவது'

        return 'முப்பத்தி' + tamil_number_to_words(ones) + 'வது'

    if 40 < n < 50:

        ones = n % 10

        if ones == 1:
            return 'நாற்பத்தொன்றாவது'

        return 'நாற்பத்தி' + tamil_number_to_words(ones) + 'வது'

    if 50 < n < 60:

        ones = n % 10

        if ones == 1:
            return 'ஐம்பத்தொன்றாவது'

        return 'ஐம்பத்தி' + tamil_number_to_words(ones) + 'வது'

    if 60 < n < 70:

        ones = n % 10

        if ones == 1:
            return 'அறுபத்தொன்றாவது'

        return 'அறுபத்தி' + tamil_number_to_words(ones) + 'வது'

    if 70 < n < 80:

        ones = n % 10

        if ones == 1:
            return 'எழுபத்தொன்றாவது'

        return 'எழுபத்தி' + tamil_number_to_words(ones) + 'வது'

    if 80 < n < 90:

        ones = n % 10

        if ones == 1:
            return 'எண்பத்தொன்றாவது'

        return 'எண்பத்தி' + tamil_number_to_words(ones) + 'வது'

    if 90 < n < 100:

        ones = n % 10

        if ones == 1:
            return 'தொண்ணூற்றொன்றாவது'

        return 'தொண்ணூற்று' + tamil_number_to_words(ones) + 'வது'

    return tamil_number_to_words(n) + 'வது'


# ============================================================
# TAMIL TIME
# ============================================================

def tamil_time_words(hour, minute, ampm=None):

    hour = int(hour)
    minute = int(minute)

    parts = []

    if ampm:

        ampm = ampm.lower()

        if ampm == 'am':
            parts.append('காலை')

        elif ampm == 'pm':
            parts.append('மாலை')

    parts.append(tamil_number_to_words(hour))

    if minute == 0:
        parts.append('மணிக்கு')

    else:
        parts.append(tamil_number_to_words(minute))
        parts.append('மணிக்கு')

    return ' '.join(parts)


# ============================================================
# TAMIL CONVERSATIONAL DATES
# ============================================================

TAMIL_MONTHS = {
    1: 'ஜனவரி',
    2: 'பிப்ரவரி',
    3: 'மார்ச்',
    4: 'ஏப்ரல்',
    5: 'மே',
    6: 'ஜூன்',
    7: 'ஜூலை',
    8: 'ஆகஸ்ட்',
    9: 'செப்டம்பர்',
    10: 'அக்டோபர்',
    11: 'நவம்பர்',
    12: 'டிசம்பர்',
}


def tamil_year_to_words(year):
    """2026 -> இரண்டாயிரத்து இருபத்தாறு"""
    year = int(year)

    if 2000 <= year < 2100:
        remainder = year - 2000
        if remainder == 0:
            return 'இரண்டாயிரம்'

        conversational_20s = {
            21: 'இருபத்தொன்று',
            22: 'இருபத்திரண்டு',
            23: 'இருபத்திமூன்று',
            24: 'இருபத்திநான்கு',
            25: 'இருபத்தைந்து',
            26: 'இருபத்தாறு',
            27: 'இருபத்தேழு',
            28: 'இருபத்தெட்டு',
            29: 'இருபத்தொன்பது',
        }

        remainder_words = conversational_20s.get(
            remainder,
            tamil_number_to_words(remainder)
        )

        return 'இரண்டாயிரத்து ' + remainder_words

    return tamil_number_to_words(year)


def normalize_conversational_dates(text, has_tamil_script):
    """
    In Tamil/mixed Tamil conversation:
      12/09/2026 -> செப்டம்பர் பன்னிரண்டு, இரண்டாயிரத்து இருபத்தாறு
      18-09-2026 -> செப்டம்பர் பதினெட்டு, இரண்டாயிரத்து இருபத்தாறு
    """
    if not has_tamil_script:
        return text

    def repl(match):
        day = int(match.group(1))
        month = int(match.group(2))
        year = int(match.group(3))

        if not (1 <= day <= 31) or not (1 <= month <= 12):
            return match.group(0)

        return (
            TAMIL_MONTHS[month]
            + ' '
            + tamil_number_to_words(day)
            + ', '
            + tamil_year_to_words(year)
        )

    return re.sub(
        r'(?<!\d)(\d{1,2})[/-](\d{1,2})[/-](\d{4})(?!\d)',
        repl,
        text
    )


# ============================================================
# TAMIL / MIXED TIME NORMALIZATION
# ============================================================

def normalize_tamil_mixed_times(text, has_tamil_script):
    """
    Critical behavior:

      காலை 6:30 AMக்கு -> காலை ஆறு முப்பது மணிக்கு
      காலை 6:30 AM     -> காலை ஆறு முப்பது
      6:30 AMக்கு       -> காலை ஆறு முப்பது மணிக்கு
      6:30 AM           -> காலை ஆறு முப்பது
      6:30 PM           -> மாலை ஆறு முப்பது

    An already-written Tamil daypart always wins. AM/PM never causes a
    duplicate காலை/மாலை.
    """
    if not has_tamil_script:
        return text

    daypart_pattern = r'(காலை|மதியம்|மாலை|இரவு)'

    def spoken_clock(hour, minute):
        parts = [tamil_number_to_words(int(hour))]
        minute = int(minute)
        if minute:
            parts.append(tamil_number_to_words(minute))
        return ' '.join(parts)

    # 1) Existing Tamil daypart + HH:MM + AM/PM.
    # Process FIRST to prevent "காலை காலை ...".
    def existing_daypart_ampm(match):
        daypart = match.group(1)
        spoken = spoken_clock(match.group(2), match.group(3))
        suffix = match.group(5)
        return daypart + ' ' + spoken + (' மணிக்கு' if suffix else '')

    text = re.sub(
        daypart_pattern
        + r'\s*(\d{1,2}):(\d{2})\s*(AM|PM)(-?க்கு)?(?![A-Za-z])',
        existing_daypart_ampm,
        text,
        flags=re.IGNORECASE
    )

    # 2) Existing Tamil daypart + HH:MM, no AM/PM.
    def existing_daypart_time(match):
        daypart = match.group(1)
        spoken = spoken_clock(match.group(2), match.group(3))
        suffix = match.group(4)
        return daypart + ' ' + spoken + (' மணிக்கு' if suffix else '')

    text = re.sub(
        daypart_pattern + r'\s*(\d{1,2}):(\d{2})(-?க்கு)?',
        existing_daypart_time,
        text
    )

    # 3) HH:MM + AM/PM where Tamil daypart was not already written.
    def ampm_without_daypart(match):
        hour = int(match.group(1))
        minute = int(match.group(2))
        ampm = match.group(3).upper()
        suffix = match.group(4)
        daypart = 'காலை' if ampm == 'AM' else 'மாலை'
        spoken = spoken_clock(hour, minute)
        return daypart + ' ' + spoken + (' மணிக்கு' if suffix else '')

    text = re.sub(
        r'(?<![\d:])(\d{1,2}):(\d{2})\s*(AM|PM)(-?க்கு)?(?![A-Za-z])(?![A-Za-z])',
        ampm_without_daypart,
        text,
        flags=re.IGNORECASE
    )

    # 4) Existing daypart + hour only.
    def daypart_hour(match):
        daypart = match.group(1)
        hour = tamil_number_to_words(int(match.group(2)))
        explicit_mani = match.group(3)
        suffix = match.group(4)
        return daypart + ' ' + hour + (' மணிக்கு' if (explicit_mani or suffix) else '')

    text = re.sub(
        daypart_pattern
        + r'\s+(\d{1,2})(\s*மணி(?:க்கு)?)?(-?க்கு)?(?=\s|[.,!?]|$)',
        daypart_hour,
        text
    )

    return text


# ============================================================
# EARLY CONTEXTUAL CURRENCY / PAISE NORMALIZATION
# ============================================================

def normalize_currency_early(text, has_tamil_script):
    """Normalize currency before generic RS acronym and general numbers."""

    def amount_words(raw):
        value = int(raw.replace(',', ''))
        if has_tamil_script:
            return tamil_number_to_words(value)
        return number_to_words(value)

    def paise_words(raw):
        value = int(raw)
        if has_tamil_script:
            return tamil_number_to_words(value) + ' பைசா'
        return number_to_words(value) + ' paise'

    # 450 rupees.50 -> four hundred and fifty rupees, fifty paise
    def decimal_rupees(match):
        whole = amount_words(match.group(1))
        paise = paise_words(match.group(2))
        if has_tamil_script:
            return whole + ' ரூபாய், ' + paise
        return whole + ' rupees, ' + paise

    text = re.sub(
        r'(?<!\d)([\d,]+)\s+rupees?\.(\d{1,2})(?!\d)',
        decimal_rupees,
        text,
        flags=re.IGNORECASE
    )

    # ₹725 / Rs 725 / Rs.725 / INR 725
    def prefixed_currency(match):
        spoken = amount_words(match.group(1))
        return spoken + (' ரூபாய்' if has_tamil_script else ' rupees')

    text = re.sub(r'₹\s*([\d,]+)', prefixed_currency, text)
    text = re.sub(
        r'\b(?:Rs\.?|INR)\s*([\d,]+)',
        prefixed_currency,
        text,
        flags=re.IGNORECASE
    )

    # 450 rupees (numeric amount followed by unit).
    def suffixed_currency(match):
        spoken = amount_words(match.group(1))
        return spoken + (' ரூபாய்' if has_tamil_script else ' rupees')

    text = re.sub(
        r'(?<!\d)([\d,]+)\s+rupees?\b',
        suffixed_currency,
        text,
        flags=re.IGNORECASE
    )

    return text


# ============================================================
# PRE-SPELLED BOOKING / OTP DIGIT PROTECTION
# ============================================================

def normalize_prespelled_identifier_digits(text):
    """
    Handles TTS-ready prefixes where raw digits are still attached/present:

      booking eye dee is see ay bee48291
      -> booking eye dee is see ay bee four eight two nine one

      o tee pee is 4821
      -> o tee pee is four eight two one
    """

    digit_seq = lambda value: ' '.join(DIGIT_WORDS[d] for d in value)

    # Digits immediately after a pre-spelled letter word in booking context.
    def booking_digits(match):
        return match.group(1) + ' ' + digit_seq(match.group(2))

    text = re.sub(
        r'((?:booking|book ing)\s+eye\s+dee\b.{0,80}?' \
        r'(?:ay|bee|see|dee|ee|eff|gee|aitch|eye|jay|kay|el|em|en|oh|pee|cue|ar|ess|tee|you|vee|double\s+you|ex|why|zee))'
        r'(?<!\s)(\d{2,10})\b',
        booking_digits,
        text,
        flags=re.IGNORECASE
    )

    # Booking context with a plain contiguous numeric tail.
    def booking_plain_digits(match):
        return match.group(1) + digit_seq(match.group(2))

    text = re.sub(
        r'((?:booking|book ing)\s+eye\s+dee\b[^\d]{0,100}?)(\d{2,10})\b',
        booking_plain_digits,
        text,
        flags=re.IGNORECASE
    )

    # Pre-spelled OTP + digits.
    def otp_digits(match):
        return match.group(1) + digit_seq(match.group(2))

    text = re.sub(
        r'((?:OTP|o\s+tee\s+pee)\b[^\d]{0,100}?)(\d{3,8})\b',
        otp_digits,
        text,
        flags=re.IGNORECASE
    )

    return text


# ============================================================
# TANGLISH WORDS
# ============================================================

TANGLISH_WORDS = {

    'ungal': 'உங்கள்',
    'unga': 'உங்க',
    'ungala': 'உங்களை',
    'ungalukku': 'உங்களுக்கு',
    'ungaloda': 'உங்களோட',

    'en': 'என்',
    'ennoda': 'என்னோட',
    'enakku': 'எனக்கு',

    'namma': 'நம்ம',
    'namba': 'நம்ம',
    'neenga': 'நீங்க',
    'nee': 'நீ',

    'avan': 'அவன்',
    'aval': 'அவள்',
    'avanga': 'அவங்க',

    'varum': 'வரும்',
    'varuthu': 'வருது',
    'varudhu': 'வருது',
    'vandhudum': 'வந்துடும்',
    'vandhu': 'வந்து',
    'vanga': 'வாங்க',
    'vaanga': 'வாங்க',

    'pogum': 'போகும்',
    'poguthu': 'போகுது',
    'poga': 'போக',
    'poitu': 'போயிட்டு',

    'irukku': 'இருக்கு',
    'iruku': 'இருக்கு',
    'irukkum': 'இருக்கும்',

    'illa': 'இல்ல',
    'illai': 'இல்லை',
    'illaya': 'இல்லையா',

    'inga': 'இங்க',
    'ingae': 'இங்கே',
    'inge': 'இங்கே',

    'anga': 'அங்க',
    'ange': 'அங்கே',

    'aagum': 'ஆகும்',
    'aakum': 'ஆகும்',

    'maniku': 'மணிக்கு',
    'manikku': 'மணிக்கு',
    'mani': 'மணி',

    'kaalai': 'காலை',
    'kalai': 'காலை',

    'mathiyam': 'மதியம்',
    'madhiyam': 'மதியம்',

    'maalai': 'மாலை',
    'malai': 'மாலை',

    'iravu': 'இரவு',

    'cab': 'cab',
    'taxi': 'taxi',
    'driver': 'driver',
    'ride': 'ride',
    'booking': 'booking',
    'pickup': 'pickup',
    'drop': 'drop',

    'vandhuten': 'வந்துட்டேன்',
    'vandhutaen': 'வந்துட்டேன்',
    'vandhachu': 'வந்தாச்சு',

    # --------------------------------------------------------
    # ADDED: EXTRA TANGLISH FORMS FOR CLEARER TTS
    # Existing normalization rules are otherwise unchanged.
    # --------------------------------------------------------
    'vandhutaara': 'வந்துட்டாரா',
    'vandhuttara': 'வந்துட்டாரா',
    'vandhutara': 'வந்துட்டாரா',
    'vandhutaaraa': 'வந்துட்டாரா',

    'vandhutaaru': 'வந்துட்டாரு',
    'vandhuttaru': 'வந்துட்டாரு',
    'vandhutaar': 'வந்துட்டார்',

    'vandhutaanga': 'வந்துட்டாங்க',
    'vandhuttanga': 'வந்துட்டாங்க',

    'varuvaaru': 'வருவாரு',
    'varuvaru': 'வருவாரு',
    'varuvaanga': 'வருவாங்க',

    'irundhu': 'இருந்து',

    'pannuvaaru': 'பண்ணுவாரு',
    'pannuvaar': 'பண்ணுவார்',
    'pannuvanga': 'பண்ணுவாங்க',

    'pannirukku': 'பண்ணிருக்கு',
    'pannirukkum': 'பண்ணிருக்கும்',

    'aagirukku': 'ஆகிருக்கு',
    'agirukku': 'ஆகிருக்கு',

    'tholaivil': 'தொலைவில்',
    'ulladhu': 'உள்ளது',
    'ulla': 'உள்ள',

    'kilambiten': 'கிளம்பிட்டேன்',
    'kilambitten': 'கிளம்பிட்டேன்',
    'kilambunga': 'கிளம்புங்க',

    'left': 'left',
    'right': 'right',

    'pakkam': 'பக்கம்',
    'pakkathula': 'பக்கத்துல',
    'munnadi': 'முன்னாடி',
    'pinnadi': 'பின்னாடி',

    'please': 'please',
    'nandri': 'நன்றி',
    'thanks': 'thanks',
    'sari': 'சரி',
    'seri': 'சரி',
    'ok': 'okay'
}


def normalize_tanglish_words(text):

    words = sorted(
        TANGLISH_WORDS.keys(),
        key=len,
        reverse=True
    )

    for word in words:

        tamil_word = TANGLISH_WORDS[word]

        pattern = (
            r'(?<![A-Za-z])'
            + re.escape(word)
            + r'(?![A-Za-z])'
        )

        text = re.sub(
            pattern,
            tamil_word,
            text,
            flags=re.IGNORECASE
        )

    return text


# ============================================================
# ACRONYM / LETTER PRONUNCIATION
# ============================================================

LETTER_WORDS = {

    'A': 'yeh',
    'B': 'bee',
    'C': 'see',
    'D': 'dee',
    'E': 'ee',
    'F': 'eff',
    'G': 'gee',
    'H': 'aitch',
    'I': 'ஐ',
    'J': 'jay',
    'K': 'kay',
    'L': 'el',
    'M': 'em',
    'N': 'en',
    'O': 'oh',
    'P': 'pee',
    'Q': 'cue',
    'R': 'ar',
    'S': 'ess',
    'T': 'tee',
    'U': 'you',
    'V': 'vee',
    'W': 'double you',
    'X': 'ex',
    'Y': 'why',
    'Z': 'zee'
}


# Important abbreviations.
# These are handled before ordinary word/number normalization.

ACRONYM_WORDS = {

    'AC': 'ay see',
    'AR': 'ay ar',
    'ID': 'eye dee',
    'OTP': 'o tee pee',
    'UPI': 'you pee eye',
    'TN': 'tee en',
    'TNSTC': 'tee en ess tee see',
    'MTC': 'em tee see',
    'GPS': 'gee pee ess',
    'ETA': 'ee tee ay',
    'ETD': 'ee tee dee',
    'PIN': 'pee eye en',
    'OMR': 'oh em ar',
    'ECR': 'ee see ar',
    'VR': 'vee ar',
    'BX': 'bee ex',
    'RS': 'rupees',
    'KM': 'கிலோமீட்டர்',
    'PM': 'pee em',
    'AM': 'ay em'
}


def spell_letters(value):

    return ' '.join(
        LETTER_WORDS[ch]
        for ch in value.upper()
        if ch in LETTER_WORDS
    )


# ============================================================
# PROTECTED ALPHANUMERIC IDENTIFIERS
#
# TN-09-CF-6723
# TN09BX4587
# TN 09 BX 4587
# ============================================================

def vehicle_or_plate_replacement(match):

    value = match.group(0)

    # Logical Indian vehicle registration groups:
    # TN09BX4587 / TN-09-CF-6723 / TN 09 BX 4587
    # -> [TN] [09] [BX/CF] [4587]
    m = re.fullmatch(
        r'([A-Za-z]{2})[-\s]?(\d{2})[-\s]?([A-Za-z]{1,3})[-\s]?(\d{4})',
        value.strip()
    )

    if not m:
        # Fallback: keep existing character/digit-wise behavior.
        parts = re.findall(r'[A-Za-z]+|\d+', value)
        spoken_parts = []
        for part in parts:
            if part.isalpha():
                spoken_parts.append(spell_letters(part))
            else:
                spoken_parts.append(' '.join(DIGIT_WORDS[d] for d in part))
        return ', '.join(spoken_parts) + ', '

    state, district, letters, serial = m.groups()

    return (
        spell_letters(state)
        + ', '
        + ' '.join(DIGIT_WORDS[d] for d in district)
        + ', '
        + spell_letters(letters)
        + ', '
        + ' '.join(DIGIT_WORDS[d] for d in serial)
        + ', '
    )


def normalize_vehicle_numbers(text):

    # Hyphenated / spaced vehicle numbers.
    #
    # TN-09-CF-6723
    # TN 09 CF 6723
    # TN09CF6723

    pattern = (
        r'(?<![A-Za-z0-9])'
        r'[A-Za-z]{2}'
        r'(?:[-\s]?\d{2})'
        r'(?:[-\s]?[A-Za-z]{1,3})'
        r'(?:[-\s]?\d{4})'
        r'(?![A-Za-z0-9])'
    )

    return re.sub(
        pattern,
        vehicle_or_plate_replacement,
        text
    )


# ============================================================
# PHONE NUMBERS
# ============================================================

def phone_number_replacement(match):

    number = re.sub(r'\D', '', match.group(0))

    if re.search(r'[\u0B80-\u0BFF]', match.group(0)):
        return ' '.join(TAMIL_DIGITS[d] for d in number)

    return ' '.join(PHONE_DIGIT_WORDS[d] for d in number)


def normalize_phone_numbers(text, is_tamil, is_tanglish=False):

    def standalone_phone_replacement(match):
        spoken = phone_number_replacement(match)
        return ', ' + spoken + ', '

    text = re.sub(
        r'(?<!\d)\d{10}(?!\d)',
        standalone_phone_replacement,
        text
    )

    tamil_phone_context = (
        r'((?:ஃபோன்|போன்|phone)\s*'
        r'(?:நம்பர்|number)\s*)'
        r'(\d[\d\s-]*\d)'
        r'(-?க்கு|க்கு)?'
    )

    def tamil_phone_context_replacement(match):

        prefix = match.group(1)
        digits = re.sub(r'\D', '', match.group(2))
        suffix = match.group(3) or ''

        if not (3 <= len(digits) <= 15):
            return match.group(0)

        digit_words = ' '.join(
            PHONE_DIGIT_WORDS[d]
            for d in digits
        )

        result = prefix.rstrip() + ', ' + digit_words

        if suffix:
            result += ', ' + suffix.lstrip('-')

        return result

    text = re.sub(
        tamil_phone_context,
        tamil_phone_context_replacement,
        text,
        flags=re.IGNORECASE
    )

    return text


# ============================================================
# BOOKING IDS / ALPHANUMERIC CODES
#
# SEE TN-09-CF-6723
# booking ID CBA48291
# CBA48291
# ============================================================

def booking_id_replacement(match):

    value = match.group(0)
    parts = re.findall(r'[A-Za-z]+|\d+', value)

    spoken_parts = []

    for part in parts:
        if part.isalpha():
            spoken_parts.append(spell_letters(part))
        else:
            spoken_parts.append(
                ' '.join(DIGIT_WORDS[d] for d in part)
            )

    # CBA48291 -> see bee ay, four eight two nine one
    return ', '.join(spoken_parts) + ', '


def normalize_booking_ids(text):

    # Alphanumeric booking code.
    #
    # CBA48291
    # ABC12345
    #
    # Do this before general numbers.

    text = re.sub(
        r'(?<![A-Za-z0-9])'
        r'(?=[A-Za-z]*\d)'
        r'[A-Za-z]{2,8}\d{2,10}'
        r'(?![A-Za-z0-9])',
        booking_id_replacement,
        text
    )

    return text


# ============================================================
# GENERIC SHORT ABBREVIATIONS
#
# Transportation/location names may contain abbreviations that are
# not known in advance, for example:
#   ARக்கு       -> ay arக்கு
#   RK Convention Center -> ar kay Convention Center
#   VR Mall     -> vee ar Mall
#
# Only 2-3 letter tokens written in ALL CAPS are treated as generic
# abbreviations. This is deliberately case-sensitive so normal words
# such as "The" are never changed.
# ============================================================

def normalize_generic_short_abbreviations(text):

    def replace_abbreviation(match):
        return spell_letters(match.group(1))

    # Allow a Tamil grammatical suffix immediately after the abbreviation.
    # The suffix is left untouched.
    text = re.sub(
        r'(?<![A-Za-z])([A-Z]{2,3})(?=(?:க்கு|களுக்கு|லிருந்து|ல|ல்|ஐ|இல்|உடன்)|\b)',
        replace_abbreviation,
        text
    )

    return text


# ============================================================
# ACRONYMS
# ============================================================

def normalize_acronyms(text):

    # Longest first.

    words = sorted(
        ACRONYM_WORDS.keys(),
        key=len,
        reverse=True
    )

    for acronym in words:

        replacement = ACRONYM_WORDS[acronym]

        # Acronym as a standalone word.
        text = re.sub(
            r'(?<![A-Za-z])'
            + re.escape(acronym)
            + r'(?![A-Za-z])',
            replacement,
            text
        )

    # Single-letter T before location names:
    #
    # T Nagar -> tee Nagar
    # T. Nagar -> tee Nagar
    #
    text = re.sub(
        r'(?<![A-Za-z])T\.?(?=\s+[A-Za-z])',
        'tee',
        text
    )

    # Other standalone single letters.

    def single_letter(match):

        return LETTER_WORDS[
            match.group(1).upper()
        ]

    text = re.sub(
        r'(?<![A-Za-z])([A-Za-z])\.(?=\s|$)',
        single_letter,
        text
    )

    return text


# ============================================================
# PAUSE AFTER ACRONYMS BEFORE TAMIL SUFFIXES
#
# ARக்கு -> ar, க்கு
# UPIல -> you pee eye, ல
# ACல -> ay see, ல
# ============================================================

def add_acronym_pause_before_tamil_suffix(text):

    acronym_sounds = (
        r'(?:'
        r'oh em ar|'
        r'ee see ar|'
        r'vee ar|'
        r'ay ar|'
        r'ay see|'
        r'you pee eye|'
        r'o tee pee|'
        r'tee en|'
        r'em tee see|'
        r'gee pee ess|'
        r'ee tee ay|'
        r'ee tee dee|'
        r'ar|'
        r'ay|'
        r'bee|'
        r'cee|'
        r'see|'
        r'dee|'
        r'pee|'
        r'eye|'
        r'em|'
        r'en|'
        r'oh|'
        r'cue|'
        r'zee'
        r')'
    )

    # Insert a pause before Tamil suffixes.

    text = re.sub(
        r'(?<![A-Za-z])(' + acronym_sounds + r')'
        r'(?=(?:க்கு|களுக்கு|லிருந்து|ல|ல்|ஐ|இல்|உடன்))',
        r'\1, ',
        text,
        flags=re.IGNORECASE
    )

    return text



# ============================================================
# SPACED IDENTIFIER LETTERS
# ============================================================

def normalize_spaced_identifier_letters(text):
    """
    Handle already separated identifier letters inside critical contexts:

      booking ID is C B A four eight two one
        -> booking ID is see bee ay four eight two one

      vehicle number T N zero nine C F ...
        -> vehicle number tee en zero nine see eff ...
    """

    context_pattern = re.compile(
        r'\b(?:booking\s+(?:ID|eye\s+dee)|vehicle(?:\s+number)?|booking\s+number)\b'
        r'[^.!?]*',
        flags=re.IGNORECASE
    )

    def normalize_context(match):
        segment = match.group(0)

        # Convert only standalone UPPERCASE letters. Do not touch ordinary
        # words or the English pronoun "I" outside these ID contexts.
        return re.sub(
            r'(?<![A-Za-z])([A-HJ-Z])(?=\s|[,;:]|$)',
            lambda m: LETTER_WORDS[m.group(1)],
            segment
        )

    return context_pattern.sub(normalize_context, text)


# ============================================================
# MAIN NORMALIZATION
# ============================================================

def normalize_taxi_text(text):

    text = text.strip()

    has_tamil_script = bool(
        re.search(r'[\u0B80-\u0BFF]', text)
    )

    lower_text = text.lower()

    tanglish_detected = any(
        re.search(
            r'(?<![A-Za-z])'
            + re.escape(word)
            + r'(?![A-Za-z])',
            lower_text
        )
        for word in TANGLISH_WORDS
        if len(word) >= 3
        and TANGLISH_WORDS[word] != word
        and re.search(
            r'[\u0B80-\u0BFF]',
            TANGLISH_WORDS[word]
        )
    )

    is_tanglish = (
        not has_tamil_script
        and tanglish_detected
    )

    is_tamil = (
        has_tamil_script
        or is_tanglish
    )

    # ========================================================
    # CRITICAL EARLY NORMALIZATION
    # Dates, mixed Tamil times, currency and pre-spelled IDs must
    # be consumed before generic acronyms and general numbers.
    # ========================================================

    text = normalize_conversational_dates(text, has_tamil_script)
    text = normalize_tamil_mixed_times(text, has_tamil_script)
    text = normalize_currency_early(text, has_tamil_script)
    text = normalize_prespelled_identifier_digits(text)

    # ========================================================
    # TANGLISH
    # ========================================================

    if is_tamil:
        text = normalize_tanglish_words(text)
        text = text.replace('டாக்ஸி', 'taksi')

    # Booking ID label boundary BEFORE acronym/pronunciation expansion.
    # Existing downstream mappings are preserved; only the comma survives.
    text = re.sub(
        r'\b(Booking\s+ID)\b\s*,?\s*',
        r'\1, ',
        text,
        flags=re.IGNORECASE
    )

    # ========================================================
    # PROTECT / NORMALIZE VEHICLE NUMBERS FIRST
    # ========================================================

    text = normalize_vehicle_numbers(text)

    # ========================================================
    # PHONE NUMBERS
    # ========================================================

    text = normalize_phone_numbers(
        text,
        is_tamil,
        is_tanglish
    )

    # ========================================================
    # BOOKING IDS
    # ========================================================

    text = normalize_booking_ids(text)
    text = normalize_spaced_identifier_letters(text)

    # ========================================================
    # OTP
    # ========================================================

    def otp_replacement(match):

        prefix = match.group(1)
        digits = match.group(2)

        if has_tamil_script:

            digit_words = ' '.join(
                TAMIL_DIGITS[d]
                for d in digits
            )

        else:

            digit_words = ' '.join(
                DIGIT_WORDS[d]
                for d in digits
            )

        return prefix + digit_words

    text = re.sub(
        r'(\bOTP\b[^0-9]{0,100}?)(\d{4})\b',
        otp_replacement,
        text,
        flags=re.IGNORECASE
    )

    # OTP itself.

    text = re.sub(
        r'\bOTP\b',
        'o tee pee',
        text,
        flags=re.IGNORECASE
    )

    # ========================================================
    # TIME
    # ========================================================

    if has_tamil_script:

        def tamil_time_ampm(match):

            hour = int(match.group(1))
            minute = int(match.group(2))
            ampm = match.group(3)

            return tamil_time_words(
                hour,
                minute,
                ampm
            )

        text = re.sub(
            r'(?<!\d)(\d{1,2}):(\d{2})\s*'
            r'(AM|PM)(?:-?க்கு)?'
            r'(?=\s|[.,!?]|$)',
            tamil_time_ampm,
            text,
            flags=re.IGNORECASE
        )

        def tamil_plain_time(match):

            return tamil_time_words(
                int(match.group(1)),
                int(match.group(2))
            )

        text = re.sub(
            r'\b(\d{1,2}):(\d{2})\b(?:\s*மணிக்கு)?',
            tamil_plain_time,
            text
        )

        text = re.sub(
            r'(\d{1,2})\s*மணிக்கு'
            r'(?=\s|[.,!?]|$)',
            lambda m:
                tamil_number_to_words(
                    int(m.group(1))
                ) + ' மணிக்கு',
            text
        )

        text = re.sub(
            r'(\d{1,2})\s*மணி'
            r'(?=\s|[.,!?]|$)',
            lambda m:
                tamil_number_to_words(
                    int(m.group(1))
                ) + ' மணிக்கு',
            text
        )

        text = re.sub(
            r'(\d{1,2})\s+வரும்'
            r'(?=\s|[.,!?]|$)',
            lambda m:
                tamil_number_to_words(
                    int(m.group(1))
                ) + ' மணிக்கு வரும்',
            text
        )

    else:

        def english_time(match):

            hour = int(match.group(1))
            minute = int(match.group(2))
            ampm = match.group(3).lower()

            if ampm == 'pm':
                ampm_word = 'pee em'
            else:
                ampm_word = 'ay em'

            return (
                number_to_words(hour)
                + ' '
                + number_to_words(minute)
                + ', '
                + ampm_word
            )

        text = re.sub(
            r'\b(\d{1,2}):(\d{2})\s*'
            r'(AM|PM)\b',
            english_time,
            text,
            flags=re.IGNORECASE
        )

        text = re.sub(
            r'\b(\d{1,2}):(\d{2})\b',
            lambda m:
                number_to_words(int(m.group(1)))
                + ' '
                + number_to_words(int(m.group(2))),
            text
        )


    # ========================================================
    # ATTACHED AM / PM IN TANGLISH
    # ========================================================
    # AMku / PMku must be pronounced as separate letters.
    # AMku -> ay em, ku
    # PMku -> pee em, ku

    text = re.sub(
        r'\bAM(?=[- ]?ku\b)',
        'ay em,',
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r'\bPM(?=[- ]?ku\b)',
        'pee em,',
        text,
        flags=re.IGNORECASE
    )

    # ========================================================
    # GENERIC SHORT ABBREVIATIONS
    # ========================================================

    text = normalize_generic_short_abbreviations(text)

    # ========================================================
    # ACRONYMS
    # ========================================================

    text = normalize_acronyms(text)

    # Semantic boundary after structured labels/acronyms.
    text = re.sub(
        r'\b(o\s+tee\s+pee)\b(?!\s*,)',
        r'\1,',
        text,
        flags=re.IGNORECASE
    )

    # ========================================================
    # TRANSPORT ACRONYM SEMANTIC BOUNDARIES
    # ========================================================

    # Add one short prosodic boundary after the fully expanded acronym.
    # Never put commas between the individual spoken letters.
    _transport_acronym_sounds = (
        r'(?:'
        r'ee tee ay|'        # ETA
        r'gee pee ess|'      # GPS
        r'you pee eye|'      # UPI
        r'oh em ar|'         # OMR
        r'ee see ar|'        # ECR
        r'see em bee tee|'   # CMBT, if mapped this way upstream
        r'em tee see|'       # MTC
        r'ay see|'           # AC
        r'ess you vee'       # SUV, if mapped letter-wise
        r')'
    )

    text = re.sub(
        r'(?<![A-Za-z])(' + _transport_acronym_sounds + r')(?![A-Za-z,])',
        r'\1,',
        text,
        flags=re.IGNORECASE
    )


    # ========================================================
    # ENGLISH SEVEN
    # ========================================================

    if not is_tamil:

        text = re.sub(
            r'\bseven\b',
            'sevven',
            text,
            flags=re.IGNORECASE
        )

    # ========================================================
    # ID
    # ========================================================

    if is_tamil:

        text = re.sub(
            r'\bID\b',
            'ஐ டீ',
            text,
            flags=re.IGNORECASE
        )

    else:

        text = re.sub(
            r'\bID\b',
            'eye dee',
            text,
            flags=re.IGNORECASE
        )

    # ========================================================
    # RUPEES / RS
    # ========================================================

    def rupee_replacement(match):

        amount = match.group(1).replace(',', '')
        value = int(amount)

        if has_tamil_script:

            return (
                tamil_number_to_words(value)
                + ' ரூபாய்'
            )

        return (
            number_to_words(value)
            + ' rupees'
        )

    # ₹725

    text = re.sub(
        r'₹\s*([\d,]+)',
        rupee_replacement,
        text
    )

    # Rs 725 / Rs.725

    text = re.sub(
        r'\bRs\.?\s*([\d,]+)',
        rupee_replacement,
        text,
        flags=re.IGNORECASE
    )

    # ========================================================
    # PAISE
    #
    # fifty paise
    # 50 paise
    # ========================================================

    def paise_replacement(match):

        value = int(match.group(1))

        if has_tamil_script:

            return (
                tamil_number_to_words(value)
                + ' பைசா'
            )

        return (
            number_to_words(value)
            + ' paise'
        )

    text = re.sub(
        r'\b(\d+)\s+paise\b',
        paise_replacement,
        text,
        flags=re.IGNORECASE
    )

    # English:
    #
    # "four hundred and fifty rupees.fifty"
    #
    # -> four hundred and fifty rupees, fifty paise

    text = re.sub(
        r'\brupees\.(\w+)\b',
        r'rupees, \1 paise',
        text,
        flags=re.IGNORECASE
    )

    # ========================================================
    # KILOMETERS
    # ========================================================

    def kilometer_replacement(match):

        value = int(match.group(1))

        if has_tamil_script:

            return (
                tamil_number_to_words(value)
                + '\u00A0கிலோமீட்டர்'
            )

        return (
            number_to_words(value)
            + ' கிலோமீட்டர்'
        )

    text = re.sub(
        r'\b(\d+)\s+kilometers?\b',
        kilometer_replacement,
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r'\b(\d+)\s+kilomeeters?\b',
        kilometer_replacement,
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r'\b(\d+)\s+kilometres?\b',
        kilometer_replacement,
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r'\b(\d+)\s+kilomeetres?\b',
        kilometer_replacement,
        text,
        flags=re.IGNORECASE
    )

    # ========================================================
    # MINUTES
    # ========================================================

    def minutes_replacement(match):

        value = int(match.group(1))

        if has_tamil_script:

            return (
                tamil_number_to_words(value)
                + ' நிமிடத்தில்'
            )

        return (
            number_to_words(value)
            + ' minits'
        )

    text = re.sub(
        r'\b(\d+)\s+minutes?\b',
        minutes_replacement,
        text,
        flags=re.IGNORECASE
    )

    # ========================================================
    # CHENNAI CENTRAL
    # ========================================================

    text = re.sub(
        r'\bChennai\s+Central(?=-|[\s.,!?]|$)',
        'சென்னை சென்ட்ரல்',
        text,
        flags=re.IGNORECASE
    )

    # ========================================================
    # TAMIL ORDINALS
    # ========================================================

    if has_tamil_script:

        text = re.sub(
            r'(\d+)(வது|ஆம்|ஆவது)'
            r'(?=\s|[.,!?]|$)',
            lambda m:
                tamil_ordinal_to_words(
                    int(m.group(1))
                ),
            text
        )

    # ========================================================
    # GENERAL NUMBERS
    #
    # IMPORTANT:
    # This is deliberately near the END.
    #
    # Vehicle numbers, phone numbers, OTPs and booking IDs
    # have already been converted character-by-character.
    # ========================================================

    def general_number_replacement(match):

        value = int(match.group(0))

        if has_tamil_script:
            return tamil_number_to_words(value)

        return number_to_words(value)

    text = re.sub(
        r'\b\d+\b',
        general_number_replacement,
        text
    )

    # ========================================================
    # FINAL SEVEN
    # ========================================================

    if not is_tamil:

        text = re.sub(
            r'\bseven\b',
            'sevven',
            text,
            flags=re.IGNORECASE
        )

    # ========================================================
    # PRONUNCIATION FIXES
    # ========================================================

    # NOTIFY

    text = re.sub(
        r'\bnotify\b',
        'noe tih fy',
        text,
        flags=re.IGNORECASE
    )

    # AIR (standalone)

    text = re.sub(
        r'\bair\b',
        'air',
        text,
        flags=re.IGNORECASE
    )

    # VELACHERY
    # Keep the Chennai place name from being stretched as "Velaachery".

    # Keep Velachery intact; DhVaani pronounces it naturally.
    # No replacement is applied here.

    # ARRIVE

    text = re.sub(
        r'\barriving\b',
        'uh riving',
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r'\barrived\b',
        'uh rived',
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r'\barrives\b',
        'ar rives',
        text,
        flags=re.IGNORECASE
    )

    # ARRIVE
    # Keep natural pronunciation when 'arrive' is sentence-final.
    # Use the hardcoded pronunciation only when more speech follows.
    #
    # Examples:
    #   How long will the driver take to arrive?
    #       -> arrive
    #
    #   The driver will arrive in five minutes.
    #       -> uh rive
    text = re.sub(
        r'\barrive\b(?=\s+\S)',
        'uh rive',
        text,
        flags=re.IGNORECASE
    )

    # ARRIVAL

    text = re.sub(
        r'\barrival\b',
        'arriival',
        text,
        flags=re.IGNORECASE
    )

    # AIRPORT

    text = re.sub(
        r'\bairport\b',
        'yerport',
        text,
        flags=re.IGNORECASE
    )

    # PAISE
    # Keep the standard word "paise" for clear TTS pronunciation.

    # BOOKING

    if not is_tamil:
        text = re.sub(
            r'\bbooking\b',
            'booking',
            text,
            flags=re.IGNORECASE
        )

    # CAB
    # Requested DhVaani pronunciation: cab -> kab in all languages.

    text = re.sub(
        r'\b(?:cab|kaab)\b',
        'cab',
        text,
        flags=re.IGNORECASE
    )

    # ROUTE

    if not is_tamil:
        text = re.sub(
            r'\broute\b',
            'root',
            text,
            flags=re.IGNORECASE
        )

    # MINUTES

    text = re.sub(
        r'\bminutes?\b',
        'minits',
        text,
        flags=re.IGNORECASE
    )

    # TOTAL

    text = re.sub(
        r'\btotals\b',
        'toe tals',
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r'\btotal\b',
        'toe tal',
        text,
        flags=re.IGNORECASE
    )

    # FINAL

    text = re.sub(
        r'\bfinal\b',
        'fye nal',
        text,
        flags=re.IGNORECASE
    )

    # FARE
    # Requested DhVaani pronunciation: fare -> fair in all languages.

    text = re.sub(
        r'\bfares\b',
        'fairs',
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r'\bfare\b',
        'fair',
        text,
        flags=re.IGNORECASE
    )

    # ========================================================
    # PHONE / NUMBER WORDS
    # ========================================================

    if has_tamil_script:

        text = re.sub(
            r'\bphone\b',
            'ஃபோன்',
            text,
            flags=re.IGNORECASE
        )

        text = re.sub(
            r'\bnumber\b',
            'நம்பர்',
            text,
            flags=re.IGNORECASE
        )

    # ========================================================
    # TAMIL KM JOIN
    # ========================================================

    if has_tamil_script:

        tamil_number_pattern = (
            r'(பூஜ்ஜியம்|ஒன்று|இரண்டு|மூன்று|'
            r'நான்கு|ஐந்து|ஆறு|ஏழு|எட்டு|ஒன்பது|'
            r'பத்து|பதினொன்று|பன்னிரண்டு|பதின்மூன்று|'
            r'பதினான்கு|பதினைந்து|பதினாறு|பதினேழு|'
            r'பதினெட்டு|பத்தொன்பது|இருபது|முப்பது|'
            r'நாற்பது|ஐம்பது|அறுபது|எழுபது|எண்பது|'
            r'தொண்ணூறு|இருபத்தி\s+\w+|முப்பத்தி\s+\w+|'
            r'நாற்பத்தி\s+\w+|ஐம்பத்தி\s+\w+|'
            r'அறுபத்தி\s+\w+|எழுபத்தி\s+\w+|'
            r'எண்பத்தி\s+\w+|தொண்ணூற்று\s+\w+|'
            r'நூறு|இருநூறு|முந்நூறு|நானூறு|'
            r'ஐந்நூறு|அறுநூறு|எழுநூறு|எண்ணூறு|'
            r'தொள்ளாயிரம்|ஆறு\s+நூற்று\s+\w+)'
        )

        text = re.sub(
            '('
            + tamil_number_pattern
            + r')\s+'
            + r'(கிலோமீட்டர்|கிலோமீட்டர்கள்)\b',
            lambda m: m.group(1) + '\u00A0' + m.group(2),
            text
        )

    # ========================================================
    # RUPEE PACING
    # ========================================================

    if has_tamil_script:

        text = re.sub(
            r'(ரூபாய்)(?=\s|[.!?,]|$)',
            r'\1,',
            text
        )

    else:

        text = re.sub(
            r'(rupees)\b(?!\s*,)',
            r'\1,',
            text,
            flags=re.IGNORECASE
        )

    text = re.sub(
        r',([.!?])',
        r'\1',
        text
    )

    # ========================================================
    # OTP PACING
    # ========================================================

    digit_words_english = (
        r'(?:zero|one|two|three|four|five|'
        r'sevven|eight|nine)'
    )

    text = re.sub(
        r'(o tee pee\s+'
        + digit_words_english
        + r'(?:\s+'
        + digit_words_english
        + r'){3})',
        r'\1,',
        text,
        flags=re.IGNORECASE
    )

    # ========================================================
    # ACRONYM PAUSE
    # ========================================================

    text = add_acronym_pause_before_tamil_suffix(text)

    # ========================================================
    # FINAL TANGLISH NORMALIZATION
    # ========================================================

    # Tanglish words were already normalized near the beginning.
    # Do not run that dictionary again after acronym expansion because
    # spoken acronym pieces such as "en" in "tee en" must remain English.

    # ========================================================
    # NATURAL ENTITY PACING
    # ========================================================
    # Do NOT insert commas after every digit or letter.
    # Use punctuation only at meaningful boundaries.

    _eng_digit = r'(?:zero|one|two|three|four|five|six|sevven|eight|nine)'
    _eng_letter = (
        r'(?:ay|bee|see|dee|ee|eff|gee|aitch|eye|jay|kay|el|em|en|oh|'
        r'pee|cue|ar|ess|tee|you|vee|double\s+you|ex|why|zee)'
    )
    _tamil_suffix = (
        r'(?:க்காக|க்கான|க்கு|களுக்கு|லிருந்து|இருந்து|ல|ல்|இல்|ஐ|உடன்)'
    )

    text = re.sub(
        r'\b(phone\s+number)\b\s*,?\s*',
        r'\1, ',
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r'(ஃபோன்\s+நம்பர்|போன்\s+நம்பர்)\s*,?\s*',
        r'\1, ',
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r'\b(book\s+ing|booking)\s*,?\s*(eye\s+dee)\b\s*,?\s*(?:is\s+)?',
        r'\1 eye dee, ',
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r'\b(o\s+tee\s+pee)\b\s*,?\s*(?:is\s+)?',
        r'\1, ',
        text,
        flags=re.IGNORECASE
    )

    # One boundary before an attached Tamil suffix.
    text = re.sub(
        r'\b(' + _eng_digit + r'|' + _eng_letter + r')\s*'
        r'(' + _tamil_suffix + r')',
        r'\1, \2',
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(r'\s*,\s*', ', ', text)
    text = re.sub(r'(?:,\s*){2,}', ', ', text)

    # ========================================================
    # WRITTEN TAMIL HUNDRED LINKERS
    # ========================================================

    text = normalize_written_tamil_hundreds(text)

    # ========================================================
    # STRUCTURED ENTITY PROSODY CLEANUP
    # ========================================================

    # If a standalone spoken phone sequence follows a normal word,
    # ensure the word and complete phone entity are separated naturally.
    _digit_word = r'(?:zero|one|two|three|four|five|six|sevven|eight|nine)'
    _phone_spoken = r'(?:' + _digit_word + r'\s+){9}' + _digit_word

    # Normalize commas surrounding complete 10-digit phone entities.
    text = re.sub(
        r'\s*,?\s*(' + _phone_spoken + r')\s*,?\s*',
        r', \1, ',
        text,
        flags=re.IGNORECASE
    )

    # Avoid a leading comma if the sentence starts with the phone entity.
    text = re.sub(r'^\s*,\s*', '', text)

    # Narrow location boundary:
    # "at Velachery is ..." -> "at Velachery, is ..."
    # Do NOT split "Velachery and Guindy Metro".
    text = re.sub(
        r'\b(Velachery)\s+(?=is\b)',
        r'\1, ',
        text,
        flags=re.IGNORECASE
    )

    # Keep only one comma at semantic boundaries.
    text = re.sub(r'\s+,', ',', text)
    text = re.sub(r',\s*,+', ',', text)
    text = re.sub(r'(?:,\s*){2,}', ', ', text)

    # No comma directly before sentence-ending punctuation.
    text = re.sub(r',\s*([.!?])', r'\1', text)

    # Normal comma spacing.
    text = re.sub(r',(?=\S)', ', ', text)
    text = re.sub(r'\s{2,}', ' ', text)

    # ========================================================
    # FINAL CLEANUP
    # ========================================================

    # --------------------------------------------------------
    # STRICT REQUESTED DHVAANI PRONUNCIATION CORRECTIONS
    # --------------------------------------------------------

    # Tanglish andru -> Tamil அன்று
    text = re.sub(
        r'\bandru\b',
        'அன்று',
        text,
        flags=re.IGNORECASE
    )

    # taxi / டாஸ்சி -> taksi
    text = re.sub(
        r'\btaxi\b',
        'taksi',
        text,
        flags=re.IGNORECASE
    )
    text = text.replace('டாஸ்சி', 'taksi')

    # cab must always be kab
    text = re.sub(
        r'\b(?:cab|kaab)\b',
        'cab',
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
       r'\bkms?\b',
      'கிலோமீட்டர்',
       text,
       flags=re.IGNORECASE
   )

    # fare must always be fair
    text = re.sub(
        r'\bfare\b',
        'fair',
        text,
        flags=re.IGNORECASE
    )

    # Chennai Central must always use the Tamil pronunciation form.
    text = re.sub(
        r'\b(?:Chennai\s+Central|Cennei\s+Sentrel)\b',
        'சென்னை சென்ட்ரல்',
        text,
        flags=re.IGNORECASE
    )

    # Global DhVaani pronunciation fixes for standalone number words.
    text = re.sub(r'\bfive\b', 'fyeve', text, flags=re.IGNORECASE)
    text = re.sub(r'\beight\b', 'ait', text, flags=re.IGNORECASE)

    text = re.sub(r',\s*,+', ',', text)

    text = re.sub(
        r'[ \t]+',
        ' ',
        text
    ).strip()

    return text


# ============================================================
# ENTITY-AWARE CHUNKER
# ============================================================
# CHUNKING FIX
# The normalizer intentionally inserts commas for DhVaani prosody.  Those
# commas are NOT treated as automatic audio boundaries here.  Structured and
# semantic entities are detected first, then ordinary chunk sizing is applied
# around them.  A protected entity may exceed max_words rather than being
# split internally.


def _clean_chunk_text(value):
    value = re.sub(r'\s*,\s*', ', ', value)
    value = re.sub(r'\s+([.!?])', r'\1', value)
    value = re.sub(r'\s{2,}', ' ', value)
    return value.strip(' ,')


# TIME ENTITY PROTECTION / DATE ENTITY PROTECTION / NUMBER ENTITY PROTECTION
_ENG_NUMBER_ATOM = (
    r'(?:zero|one|two|three|four|fyeve|five|six|sevven|seven|ait|eight|nine|'
    r'ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|'
    r'nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|'
    r'hundred|thousand|and)'
)
_ENG_NUMBER_PHRASE = r'(?:' + _ENG_NUMBER_ATOM + r')(?:\s+' + _ENG_NUMBER_ATOM + r')*'
_ENG_DIGIT_WORD = r'(?:zero|one|two|three|four|fyeve|five|six|sevven|seven|ait|eight|nine)'
_ENG_DIGIT_SEQUENCE = r'(?:' + _ENG_DIGIT_WORD + r')(?:\s+' + _ENG_DIGIT_WORD + r'){2,14}'
_ENG_LETTER_WORD = (
    r'(?:ay|bee|see|dee|ee|eff|gee|aitch|eye|jay|kay|el|em|en|oh|pee|cue|ar|'
    r'ess|tee|you|vee|double\s+you|ex|why|zee)'
)
_ENG_ACRONYM = r'(?:' + _ENG_LETTER_WORD + r')(?:\s+' + _ENG_LETTER_WORD + r')+'
_TAMIL_SUFFIX = r'(?:க்காக|க்கான|க்கு|களுக்கு|லிருந்து|இருந்து|ல|ல்|இல்|ஐ|உடன்)'
_TANGLISH_SUFFIX = r'(?:ku|kku|la)'

_TAMIL_NUMBER_WORD = (
    r'(?:பூஜ்ஜியம்|ஒன்று|இரண்டு|மூன்று|நான்கு|ஐந்து|ஆறு|ஏழு|எட்டு|ஒன்பது|'
    r'பத்து|பதினொன்று|பன்னிரண்டு|பதின்மூன்று|பதினான்கு|பதினைந்து|பதினாறு|'
    r'பதினேழு|பதினெட்டு|பத்தொன்பது|இருபது|இருபத்தி|முப்பது|முப்பத்தி|'
    r'நாற்பது|நாற்பத்தி|ஐம்பது|ஐம்பத்தி|அறுபது|அறுபத்தி|எழுபது|எழுபத்தி|'
    r'எண்பது|எண்பத்தி|தொண்ணூறு|தொண்ணூற்று|நூறு|நூற்று|இருநூறு|இருநூற்று|'
    r'முந்நூறு|முந்நூற்று|நானூறு|நானூற்று|ஐந்நூறு|ஐந்நூற்று|அறுநூறு|'
    r'அறுநூற்று|எழுநூறு|எழுநூற்று|எண்ணூறு|எண்ணூற்று|தொள்ளாயிரம்|'
    r'தொள்ளாயிரத்து|ஆயிரம்|ஆயிரத்து)'
)
_TAMIL_NUMBER_PHRASE = r'(?:' + _TAMIL_NUMBER_WORD + r')(?:\s+' + _TAMIL_NUMBER_WORD + r')*'

_MONTH = (
    r'(?:January|February|March|April|May|June|July|August|September|October|'
    r'November|December|ஜனவரி|பிப்ரவரி|மார்ச்|ஏப்ரல்|மே|ஜூன்|ஜூலை|ஆகஸ்ட்|'
    r'செப்டம்பர்|அக்டோபர்|நவம்பர்|டிசம்பர்)'
)


def _protected_entity_patterns():
    """Priority-ordered normalized-text entities that must stay intact."""
    return [
        # DATE ENTITY PROTECTION
        r'\b' + _MONTH + r'\s+' + _ENG_NUMBER_PHRASE + r'\s*,\s*' + _ENG_NUMBER_PHRASE + r'\b',
        _MONTH + r'\s+' + _TAMIL_NUMBER_PHRASE + r'\s*,\s*' + _TAMIL_NUMBER_PHRASE,

        # TIME ENTITY PROTECTION
        # hour + minute + AM/PM, including the prosody comma before suffix.
        r'\b' + _ENG_NUMBER_PHRASE + r'\s+(?:ay\s+em|pee\s+em)(?:\s*,\s*(?:ku|kku|' + _TAMIL_SUFFIX + r'))?\b',
        r'(?:காலை|மதியம்|மாலை|இரவு)\s+(?:' + _TAMIL_NUMBER_PHRASE + r'|' + _ENG_NUMBER_PHRASE + r')'
        r'(?:\s+(?:ay\s+em|pee\s+em))?(?:\s*,\s*(?:ku|kku|' + _TAMIL_SUFFIX + r'))?',

        # CURRENCY / PAISE ENTITY PROTECTION
        r'\b' + _ENG_NUMBER_PHRASE + r'\s+rupees\b(?:\s*,\s*' + _ENG_NUMBER_PHRASE + r'\s+paise\b)?',
        r'\b' + _ENG_NUMBER_PHRASE + r'\s+paise\b',
        _TAMIL_NUMBER_PHRASE + r'\s+ரூபாய்\b',
        _TAMIL_NUMBER_PHRASE + r'\s+பைசா\b',

        # MINUTES / DISTANCE ENTITY PROTECTION
        r'\b' + _ENG_NUMBER_PHRASE + r'\s+minits\b(?:[- ]?(?:la|ku|kku))?',
        r'\b' + _ENG_NUMBER_PHRASE + r'\s+kil\s+uh\s+meters?\b(?:[- ]?(?:la|ku|kku))?',
        _TAMIL_NUMBER_PHRASE + r'(?:\u00a0|\s+)கிலோமீட்டர்(?:கள்)?(?:' + _TAMIL_SUFFIX + r')?',
        _TAMIL_NUMBER_PHRASE + r'\s+நிமிட(?:ம்|த்தில்|ங்கள்)?(?:' + _TAMIL_SUFFIX + r')?',

        # OTP ENTITY PROTECTION: label + complete digit sequence.
        r'\b(?:o\s+tee\s+pee)\s*,?\s*(?:is\s+)?' + _ENG_DIGIT_SEQUENCE + r'\b',

        # PHONE ENTITY PROTECTION: preserve the complete spoken digit sequence
        # with its nearby phone-number label when present.
        r'\b(?:phone\s+number)\s*,?\s*(?:is\s*,?\s*)?' + _ENG_DIGIT_SEQUENCE + r'\b',
        r'(?:ஃபோன்|போன்)\s+நம்பர்\s*,?\s*' + _ENG_DIGIT_SEQUENCE + r'\b',

        # VEHICLE REGISTRATION ENTITY PROTECTION after existing normalizer:
        # tee en, zero nine, ay bee, six ait six six
        r'\b' + _ENG_ACRONYM + r'\s*,\s*(?:' + _ENG_DIGIT_WORD + r')(?:\s+' + _ENG_DIGIT_WORD + r'){1,2}'
        + r'\s*,\s*' + _ENG_ACRONYM + r'\s*,\s*(?:' + _ENG_DIGIT_WORD + r')(?:\s+' + _ENG_DIGIT_WORD + r'){3,5}\b',

        # BOOKING ID ENTITY PROTECTION: expanded letters + expanded digits.
        r'\b(?:bouking|booking|book\s+ing)\s+(?:eye\s+dee|ஐ\s+டீ)\s*,?\s*(?:is\s+)?'
        + _ENG_ACRONYM + r'\s*,?\s*' + _ENG_DIGIT_SEQUENCE + r'\b',
        r'\b' + _ENG_ACRONYM + r'\s*,\s*' + _ENG_DIGIT_SEQUENCE + r'\b',

        # ACRONYM + TAMIL/Tanglish suffix, including AM/PM suffix forms.
        r'\b' + _ENG_ACRONYM + r'\s*,\s*(?:' + _TAMIL_SUFFIX + r'|' + _TANGLISH_SUFFIX + r')(?=\s|[.,!?]|$)',

        # Complete standalone digit sequences used by identifiers.
        r'\b' + _ENG_DIGIT_SEQUENCE + r'\b',

        # Acronyms must never be split internally.
        r'\b' + _ENG_ACRONYM + r'\b',

        # General spoken numerical phrases are protected last, so larger
        # structured entities above always win first.
        r'\b' + _ENG_NUMBER_PHRASE + r'\b',
        _TAMIL_NUMBER_PHRASE,
    ]


def _collect_protected_spans(text):
    """Return non-overlapping protected spans using entity priority."""
    spans = []

    def overlaps(start, end):
        return any(start < old_end and end > old_start for old_start, old_end in spans)

    for pattern in _protected_entity_patterns():
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            if not overlaps(match.start(), match.end()):
                spans.append((match.start(), match.end()))

    spans.sort()
    return spans


def _entity_aware_units(text):
    """Tokenize text while keeping every protected semantic entity atomic."""
    spans = _collect_protected_spans(text)
    units = []
    cursor = 0

    for start, end in spans:
        if cursor < start:
            units.extend(re.findall(r'\S+', text[cursor:start]))
        units.append(text[start:end].strip())
        cursor = end

    if cursor < len(text):
        units.extend(re.findall(r'\S+', text[cursor:]))

    # Keep sentence punctuation attached to the preceding unit.  Prosody
    # commas inside protected entities have already been preserved above.
    compact = []
    for unit in units:
        if re.fullmatch(r'[.!?]+', unit) and compact:
            compact[-1] += unit
        else:
            compact.append(unit)

    return [unit for unit in compact if unit]


def chunk_normalized_text(text, max_words=7):
    """Semantic/entity-aware chunking; never split a protected entity."""
    text = _clean_chunk_text(text)
    if not text:
        return []

    units = _entity_aware_units(text)
    chunks = []
    current = []
    current_words = 0

    def flush():
        nonlocal current, current_words
        if current:
            chunks.append(_clean_chunk_text(' '.join(current)))
            current = []
            current_words = 0

    for unit in units:
        unit = unit.strip()
        if not unit:
            continue

        words = len(re.findall(r'\S+', unit))
        lower = unit.lower().strip(' ,')

        if current and re.search(r'[.!?]$', current[-1]):
            flush()

        # Prosodic boundary for conjunction + following cab/taxi action.
        # This is semantic behavior, not a hard-coded full sentence.
        if current and lower in {'kab', 'taksi'} and current[-1].strip().lower() in {'மற்றும்', 'and'}:
            flush()

        # Apply normal chunk size only BETWEEN units.  A protected unit is
        # atomic, so if it is itself longer than max_words it is still kept.
        if current and current_words + words > max_words:
            flush()

        current.append(unit)
        current_words += words

        if re.search(r'[.!?]$', unit):
            flush()

    flush()
    return chunks


def normalize_and_chunk(text, max_words=7):
    normalized = normalize_taxi_text(text)
    return normalized, chunk_normalized_text(normalized, max_words=max_words)


# ============================================================
# TEST CASES
# ============================================================


# ---- Source section 27 ----
import re
import time

TAMIL_CHAR_RE = re.compile(r"[\u0B80-\u0BFF]")






def call_smart_chunker(
    text,
    language=None
):
    text = str(text).strip()

    if not text:
        return []

    function_names = [
        "smart_chunk_text_v4",
        "smart_chunk_text_v8",
        "smart_chunk_text_v7",
        "smart_chunk_text_v6",
        "smart_chunk_text_v5",
    ]

    fn = None

    for name in function_names:
        candidate = globals().get(name)

        if callable(candidate):
            fn = candidate
            break

    if fn is None:
        return [text]

    try:
        raw_chunks = fn(
            text,
            language=language
        )

    except TypeError:
        raw_chunks = fn(text)

    if raw_chunks is None:
        return [text]

    if isinstance(raw_chunks, str):
        raw_chunks = [raw_chunks]

    chunks = [
        _clean_chunk(chunk)
        for chunk in raw_chunks
        if str(chunk).strip()
    ]

    return chunks or [text]






# ============================================================
# MAIN REQUEST PREPARATION
# ============================================================



print("✓ prepare_movio_request is now defined")


# ---- Source section 29 ----
# ============================================================
# CELL 9 — MOVIO SEMANTIC MICRO-CHUNKER V6
# English + Tamil + Tanglish + entity-aware
#
# IMPORTANT:
# - This is NOT "first N words" chunking.
# - Candidate boundaries are scored for linguistic completeness.
# - Word-count windows only limit the search space for latency.
# - Entity spans are protected so IDs/phone/OTP/vehicle values are not split.
# ============================================================

TAMIL_CHAR_RE = re.compile(r"[\u0B80-\u0BFF]")

EN_WEAK_END = {
    "a", "an", "the", "to", "at", "in", "on", "for", "from", "with",
    "and", "or", "but", "is", "are", "was", "were", "be", "been", "being",
    "will", "would", "shall", "should", "can", "could", "may", "might", "must",
    "your", "my", "our", "their", "his", "her", "this", "that", "these", "those",
    "of", "by", "as", "if", "when", "while", "because", "than"
}

EN_WEAK_START = {"and", "or", "but", "of", "because", "than", "a", "an", "the", "my", "your", "our", "this", "that"}

# Tamil words that are poor phrase endings when standing alone.
TA_WEAK_END = {
    "ஒரு", "இந்த", "அந்த", "என்", "உன்", "உங்கள்", "எங்கள்", "மற்றும்", "அல்லது",
    "என்று", "என", "மிக", "ரொம்ப", "உடனே"
}

# Common Tamil finite/imperative/auxiliary endings. These are strong safe boundaries.
TA_STRONG_ENDINGS = (
    "வேண்டும்", "வேண்டாம்", "முடியும்", "முடியுமா", "முடியாது",
    "இருக்கிறது", "இருக்கிறேன்", "இருக்கிறோம்", "இருக்கிறான்", "இருக்கிறாள்",
    "இருக்கா", "இருக்குமா", "வரும்", "வருமா", "வரவில்லை", "வந்தது", "வந்துவிட்டது",
    "செல்லுங்கள்", "சொல்லுங்கள்", "அனுப்புங்கள்", "இறக்குங்கள்", "நிறுத்துங்கள்",
    "தொடங்குங்கள்", "பண்ணுங்க", "பண்ணணும்", "கிடைக்குமா", "ஆகும்", "ஆகுமா",
    "செய்யுங்கள்", "செய்யணும்", "செய்ய வேண்டும்", "காத்திருக்கிறேன்"
)

# Words/suffixes that usually form a meaningful dependent phrase and can be cut after
# when enough material has accumulated.
TA_PHRASE_ENDINGS = (
    "க்கு", "இல்", "ல", "ல்", "இருந்து", "வரை", "உடன்", "பற்றி", "பிறகு", "முன்",
    "கழித்து", "போது", "என்றால்", "னால்", "ஆக", "மட்டும்", "தான்", "ஐ", "தை", "த்தை", "னை", "னு"
)

# Tanglish / code-mixed phrase cues.
TG_STRONG_WORDS = {
    "pannunga", "pannanum", "venum", "vendam", "varuma", "varum", "irukka",
    "irukku", "kidaikkuma", "sollunga", "anupunga", "check", "confirm", "cancel"
}

VALUE_WORDS = {
    "zero", "one", "two", "three", "four", "five", "fyeve", "six", "seven", "sevven",
    "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
    "sixteen", "seventeen", "eighteen", "nineteen", "twenty", "thirty", "forty",
    "fifty", "sixty", "seventy", "eighty", "ninety", "hundred", "thousand",
    "a", "ay", "aayy", "b", "bee", "c", "cee", "d", "dee", "e", "ee", "f", "eff",
    "g", "gee", "h", "aitch", "i", "eye", "j", "jay", "k", "kay", "l", "el",
    "m", "em", "n", "en", "o", "oh", "p", "pee", "q", "cue", "r", "ar", "s",
    "ess", "t", "tee", "u", "you", "v", "vee", "w", "double-u", "x", "ex",
    "y", "why", "z", "zee", "zed",
    "பூஜ்ஜியம்", "ஒன்று", "இரண்டு", "மூன்று", "நான்கு", "ஐந்து", "ஆறு", "ஏழு",
    "எட்டு", "ஒன்பது", "பத்து", "இருபது", "முப்பது", "நாற்பது", "ஐம்பது",
    "அறுபது", "எழுபது", "எண்பது", "தொண்ணூறு"
}

ENTITY_PREFIXES = [
    ["otp", "is"], ["your", "otp", "is"], ["o", "tee", "pee", "is"],
    ["your", "o", "tee", "pee", "is"], ["booking", "id", "is"],
    ["booking", "i", "d", "is"], ["your", "booking", "id", "is"],
    ["phone", "number"], ["phone", "number", "is"], ["your", "phone", "number"],
    ["vehicle", "number"], ["vehicle", "number", "is"],
    ["driver", "vehicle", "number"], ["registration", "number"],
    ["gate"], ["platform"], ["terminal"], ["route"]
]


def clean_token(token):
    return str(token).strip(".,!?;:()[]{}\"'").lower()


def _contains_tamil(token):
    return bool(TAMIL_CHAR_RE.search(str(token)))


def _starts_phrase(tokens, pos, phrase):
    probe = [clean_token(x) for x in tokens[pos:pos + len(phrase)]]
    return probe == phrase


def find_protected_spans(tokens):
    """Half-open token spans that must never be cut internally."""
    spans = []
    n = len(tokens)

    for i in range(n):
        for phrase in ENTITY_PREFIXES:
            if not _starts_phrase(tokens, i, phrase):
                continue
            j = i + len(phrase)
            value_start = j
            while j < n:
                t = clean_token(tokens[j])
                raw = str(tokens[j]).strip(".,!?;:")
                if (
                    t in VALUE_WORDS
                    or bool(re.fullmatch(r"\d+", t))
                    or bool(re.fullmatch(r"[A-Za-z0-9-]+", raw)) and any(ch.isdigit() for ch in raw)
                ):
                    j += 1
                else:
                    break
            if j > value_start:
                spans.append((i, j))
            break

    raw_entity_re = re.compile(
        r"^(?:[A-Za-z]{2}[- ]?\d{2}[- ]?[A-Za-z]{1,3}[- ]?\d{4}|"
        r"\+?\d[\d -]{3,}\d|[A-Za-z]{2,8}\d{3,})$"
    )
    for i, tok in enumerate(tokens):
        probe = str(tok).strip(".,!?;:")
        if raw_entity_re.fullmatch(probe):
            spans.append((i, i + 1))

    spans = sorted(spans)
    merged = []
    for a, b in spans:
        if not merged or a > merged[-1][1]:
            merged.append([a, b])
        else:
            merged[-1][1] = max(merged[-1][1], b)
    return [(a, b) for a, b in merged]


def cut_inside_protected(cut_pos, spans):
    return any(a < cut_pos < b for a, b in spans)


def _tamil_boundary_bonus(previous, next_token):
    prev = clean_token(previous)
    nxt = clean_token(next_token) if next_token else ""
    bonus = 0

    if any(prev.endswith(x) for x in TA_STRONG_ENDINGS):
        bonus += 26
    elif any(prev.endswith(x) for x in TA_PHRASE_ENDINGS):
        bonus += 9

    # Tamil verbal morphology often ends with these suffixes.
    if re.search(r"(?:ங்கள்|ங்க|ணும்|வேண்டும்|லாம்|மா|து|து\?|றேன்|றோம்|றார்|றது)$", prev):
        bonus += 12

    if prev in TA_WEAK_END:
        bonus -= 24

    # Avoid cutting before attached/continuing Tamil particles where possible.
    if nxt in {"க்கு", "ல்", "இல்", "உடன்", "மற்றும்", "ஆனால்"}:
        bonus -= 12

    # In Tamil/Tanglish, a boundary before a new action phrase is often natural.
    if nxt in {"check", "book", "cancel", "confirm", "call", "இன்னும்", "உடனே", "பிறகு", "அடுத்து"}:
        bonus += 18

    return bonus


def _english_boundary_bonus(previous, next_token):
    prev = clean_token(previous)
    nxt = clean_token(next_token) if next_token else ""
    bonus = 0

    if prev in EN_WEAK_END:
        bonus -= 24
    if nxt in EN_WEAK_START:
        bonus -= 24

    # Cutting immediately after an imperative/transitive verb before its object
    # (e.g. "Please send | a cab") is semantically poor.
    if prev in {"send", "take", "share", "ask", "need", "want", "have", "find", "notify", "stop"} and nxt in {"a", "an", "the", "my", "your", "me", "him", "her", "driver", "cab", "kaab"}:
        bonus -= 32

    # Prefer a phrase boundary before prepositional/adverbial continuation,
    # provided the previous side is already meaningful.
    if nxt in {"to", "at", "in", "on", "from", "with", "near", "after", "before", "when"}:
        bonus += 8

    # Common complete verbal forms are safe phrase endings.
    if prev in {
        "arrive", "arrives", "arrived", "cancel", "cancelled", "confirmed", "available",
        "wait", "waiting", "come", "coming", "send", "stop", "call", "change", "refund"
    }:
        bonus += 8
    return bonus


def semantic_boundary_score(tokens, cut_pos, start, target, spans):
    if cut_pos <= start or cut_pos > len(tokens) or cut_inside_protected(cut_pos, spans):
        return -100000

    previous = tokens[cut_pos - 1]
    next_token = tokens[cut_pos] if cut_pos < len(tokens) else ""
    length = cut_pos - start

    # Latency preference: near target, but semantics can override it.
    score = 30 - 4 * abs(length - target)

    if re.search(r"[.!?]$", previous):
        score += 40
    elif re.search(r"[,;:]$", previous):
        score += 20

    if _contains_tamil(previous) or _contains_tamil(next_token):
        score += _tamil_boundary_bonus(previous, next_token)
    else:
        score += _english_boundary_bonus(previous, next_token)

    # Tanglish cue even if tokens themselves are Latin.
    if clean_token(previous) in TG_STRONG_WORDS:
        score += 14

    remaining = len(tokens) - cut_pos
    if 0 < remaining < 2:
        score -= 30

    return score


def _merge_tiny_tail(chunks):
    if len(chunks) >= 2 and len(chunks[-1].split()) == 1:
        chunks[-2] = (chunks[-2].rstrip() + " " + chunks[-1].lstrip()).strip()
        chunks.pop()
    return chunks


def smart_chunk_text_v6(text):
    text = re.sub(r"\s+", " ", str(text)).strip()
    if not text:
        return []

    # ========================================================
    # CURRENCY SEMANTIC ATOMICITY
    # ========================================================
    # Keep the complete amount predicate together.  This prevents:
    #   "அறுநூற்று ஐம்பது" | "ரூபாய் ஆகும்"
    # and produces:
    #   "உங்கள் கட்டணம்" | "அறுநூற்று ஐம்பது ரூபாய் ஆகும்."
    #
    # This is semantic chunking, not a fixed word-count split.
    currency_match = re.match(
        r"^(.*?கட்டணம்)\s+(.+?ரூபாய்\s+(?:ஆகும்|ஆகுமா|இருக்கும்)[.!?]?)$",
        text,
        flags=re.IGNORECASE,
    )
    if currency_match:
        subject_phrase = currency_match.group(1).strip()
        amount_phrase = currency_match.group(2).strip()
        if subject_phrase and amount_phrase:
            return [subject_phrase, amount_phrase]

    tokens = text.split()
    if len(tokens) <= KEEP_WHOLE_IF_WORDS_LE:
        return [text]

    spans = find_protected_spans(tokens)
    chunks = []
    start = 0
    chunk_no = 0

    while start < len(tokens):
        remaining = len(tokens) - start

        # Whole tail is preferred only when it is already compact.
        if chunk_no > 0 and remaining <= NEXT_MAX_WORDS:
            chunks.append(" ".join(tokens[start:]))
            break

        if chunk_no == 0:
            min_words, target, max_words = FIRST_MIN_WORDS, FIRST_TARGET_WORDS, FIRST_MAX_WORDS
        else:
            min_words, target, max_words = NEXT_MIN_WORDS, NEXT_TARGET_WORDS, NEXT_MAX_WORDS

        if remaining <= max_words and chunk_no == 0:
            # Even short first sentences are considered for a semantic micro-boundary.
            # This fixes the old Tamil behavior where <=6 words were always kept whole.
            pass

        lo = min(len(tokens), start + min_words)
        hi = min(len(tokens), start + max_words)

        # For the first chunk of a sentence longer than 3 tokens, do not let the
        # trivial full-sentence endpoint win merely because it has punctuation.
        # We require a real semantic micro-boundary for TTFA.
        if chunk_no == 0 and remaining > 3:
            hi = min(hi, len(tokens) - 1)

        # If the full remaining sentence is <=3 words, keep it whole.
        if remaining <= 3:
            chunks.append(" ".join(tokens[start:]))
            break

        candidates = [c for c in range(lo, hi + 1) if not cut_inside_protected(c, spans)]
        if not candidates:
            c = hi
            while c < len(tokens) and cut_inside_protected(c, spans):
                c += 1
            candidates = [min(c, len(tokens))]

        best_cut = max(
            candidates,
            key=lambda c: semantic_boundary_score(tokens, c, start, target, spans),
        )

        # Do not split at the very end; that is just the whole sentence.
        if best_cut >= len(tokens):
            chunks.append(" ".join(tokens[start:]))
            break

        chunks.append(" ".join(tokens[start:best_cut]))
        start = best_cut
        chunk_no += 1

    chunks = _merge_tiny_tail(chunks)
    return [c.strip() for c in chunks if c.strip()]


# Backward-compatible alias: every existing benchmark/streaming cell now uses V6.
smart_chunk_text_v4 = smart_chunk_text_v6


def validate_chunk_plan(text, chunks):
    original = " ".join(str(text).split())
    rebuilt = " ".join(" ".join(chunks).split())
    warnings_list = []

    if rebuilt != original:
        warnings_list.append("TEXT_CHANGED")
    if not chunks:
        return ["EMPTY_CHUNKS"]

    for i, chunk in enumerate(chunks[:-1]):
        words = chunk.split()
        if not words:
            continue
        end = clean_token(words[-1])
        if end in EN_WEAK_END or end in TA_WEAK_END:
            warnings_list.append(f"WEAK_END_C{i+1}:{words[-1]}")

    for i, chunk in enumerate(chunks[1:], start=2):
        words = chunk.split()
        if words and clean_token(words[0]) in EN_WEAK_START:
            warnings_list.append(f"WEAK_START_C{i}:{words[0]}")

    return warnings_list


# Smoke tests for all three language families.
SEMANTIC_CHUNK_SMOKE = [
    ("ENGLISH", "Please send a cab to my current pickup location."),
    ("ENGLISH", "Please notify me when the cab arrives."),
    ("TAMIL", "எனக்கு விமான நிலையத்துக்கு உடனே செல்ல வேண்டும்."),
    ("TAMIL", "என் பயணத்தை இன்னும் பத்து நிமிடம் கழித்து தொடங்குங்கள்."),
    ("TANGLISH", "Pickup location correctஆ இருக்கானு check பண்ணுங்க."),
    ("TANGLISH", "எனக்கு ஒரு cab book பண்ணணும்."),
    ("TAMIL", "உங்கள் கட்டணம் அறுநூற்று ஐம்பது ரூபாய் ஆகும்."),
]

print("Semantic Micro-Chunker V6 ready ✓")
for lang, sample in SEMANTIC_CHUNK_SMOKE:
    print(f"{lang:8s} -> {smart_chunk_text_v6(sample)}")


# ---- Source section 31 ----

# ============================================================
# SEMANTIC GUARD V7 — prevent incomplete / entity-breaking C1
# ============================================================
# This wraps V6 without deleting the existing implementation.

_ORIGINAL_SMART_CHUNK_TEXT_V6 = smart_chunk_text_v6

EN_HARD_BAD_END = {
    "a", "an", "the", "to", "at", "in", "on", "for", "from", "with",
    "and", "or", "but", "of", "my", "your", "his", "her", "our", "their",
    "this", "that", "these", "those", "is", "are", "was", "were",
    "will", "would", "can", "could", "should", "may", "might", "must"
}

# Multi-token names/units that must remain contiguous.
SEMANTIC_ATOMIC_PHRASES = [
    ("தி", "நகர்"),
    ("t", "nagar"),
    ("chennai", "central"),
    ("twelve", "kilometers"),
    ("twelve", "kilometres"),
    ("different", "kaab"),
    ("different", "cab"),
]


def _token_clean_v7(x):
    return str(x).strip(".,!?;:()[]{}\"'").lower()


def _cut_breaks_atomic_phrase(tokens, cut):
    clean = [_token_clean_v7(t) for t in tokens]
    for phrase in SEMANTIC_ATOMIC_PHRASES:
        m = len(phrase)
        for i in range(0, len(clean) - m + 1):
            if tuple(clean[i:i+m]) == phrase and i < cut < i + m:
                return True
    return False


def _first_chunk_is_incomplete(chunk):
    words = chunk.split()
    if not words:
        return True
    return _token_clean_v7(words[-1]) in EN_HARD_BAD_END


def smart_chunk_text_v7(text):
    text = re.sub(r"\s+", " ", str(text)).strip()
    if not text:
        return []

    tokens = text.split()

    # Explicit natural taxi phrases where V6's latency preference can cut badly.
    clean = [_token_clean_v7(t) for t in tokens]

    # Preserve "தி நகர்" as one location phrase:
    # "நான்" | "தி நகரில் காத்திருக்கிறேன்."
    if len(tokens) >= 4 and clean[:3] == ["நான்", "தி", "நகரில்"]:
        return [tokens[0], " ".join(tokens[1:])]

    # Natural English request:
    # "I need" | "a different cab."
    if len(tokens) >= 5 and clean[:4] in (
        ["i", "need", "a", "different"],
        ["i", "need", "another", "cab"],
        ["i", "need", "another", "kaab"],
    ):
        return [" ".join(tokens[:2]), " ".join(tokens[2:])]

    chunks = _ORIGINAL_SMART_CHUNK_TEXT_V6(text)
    if len(chunks) <= 1:
        return chunks

    # Repair a first chunk ending in a determiner/preposition/auxiliary.
    if _first_chunk_is_incomplete(chunks[0]):
        all_tokens = text.split()
        candidate_cuts = []
        for cut in range(FIRST_MIN_WORDS, min(FIRST_MAX_WORDS, len(all_tokens)-1) + 1):
            if _cut_breaks_atomic_phrase(all_tokens, cut):
                continue
            left = " ".join(all_tokens[:cut])
            right = " ".join(all_tokens[cut:])
            if not _first_chunk_is_incomplete(left) and len(right.split()) >= 2:
                candidate_cuts.append((abs(cut - FIRST_TARGET_WORDS), cut, left, right))

        if candidate_cuts:
            _, cut, left, right = min(candidate_cuts)
            repaired_tail = _ORIGINAL_SMART_CHUNK_TEXT_V6(right)
            chunks = [left] + repaired_tail

    # Final atomic-phrase check across every boundary.
    all_tokens = text.split()
    rebuilt = []
    cursor = 0
    for chunk in chunks:
        n = len(chunk.split())
        cut = cursor + n
        if rebuilt and _cut_breaks_atomic_phrase(all_tokens, cursor):
            rebuilt[-1] = rebuilt[-1] + " " + chunk
        else:
            rebuilt.append(chunk)
        cursor = cut

    return [c.strip() for c in rebuilt if c.strip()]


# Backward-compatible aliases used throughout the notebook.
smart_chunk_text_v6 = smart_chunk_text_v7
smart_chunk_text_v4 = smart_chunk_text_v7

print("✓ Semantic Guard V7 active")
for _x in [
    "நான் தி நகரில் காத்திருக்கிறேன்.",
    "I need a different kaab.",
    "The route is twelve kilometers.",
]:
    print(_x, "->", smart_chunk_text_v7(_x))


# ---- Source section 35 ----
# ============================================================
# MOVIO — TANGLISH CLARITY + SLIGHTLY FASTER SPEECH FIX
#
# Add this AFTER your existing normalizer definitions.
# Then rerun prepare_movio_request + synthesis cells.
# ============================================================

import re


# ============================================================
# 1. EXTRA TANGLISH WORD NORMALIZATION
# ============================================================

EXTRA_TANGLISH_WORDS = {

    # Arrival / coming
    "vandhutaara": "வந்துட்டாரா",
    "vandhuttara": "வந்துட்டாரா",
    "vandhutara": "வந்துட்டாரா",
    "vandhutaaraa": "வந்துட்டாரா",

    "vandhutaaru": "வந்துட்டாரு",
    "vandhuttaru": "வந்துட்டாரு",
    "vandhutaar": "வந்துட்டார்",

    "vandhutaanga": "வந்துட்டாங்க",
    "vandhuttanga": "வந்துட்டாங்க",

    "vandhuten": "வந்துட்டேன்",
    "vandhutaen": "வந்துட்டேன்",

    "vandhachu": "வந்தாச்சு",

    "varuvaaru": "வருவாரு",
    "varuvaru": "வருவாரு",
    "varuvaanga": "வருவாங்க",

    "varum": "வரும்",
    "varudhu": "வருது",
    "varuthu": "வருது",

    # Location
    "inga": "இங்க",
    "inge": "இங்கே",
    "ingae": "இங்கே",

    "anga": "அங்க",
    "ange": "அங்கே",

    # Waiting
    "wait": "வெயிட்",

    # Pickup / drop conversational forms
    "pickup": "பிக்கப்",
    "drop": "டிராப்",

    # General speech
    "irukku": "இருக்கு",
    "iruku": "இருக்கு",
    "irukkum": "இருக்கும்",

    "pannuvaaru": "பண்ணுவாரு",
    "pannuvaar": "பண்ணுவார்",
    "pannuvanga": "பண்ணுவாங்க",

    "pannirukku": "பண்ணிருக்கு",
    "pannirukkum": "பண்ணிருக்கும்",

    "aagirukku": "ஆகிருக்கு",
    "agirukku": "ஆகிருக்கு",

    "ready": "ரெடி",
}


def normalize_extra_tanglish(text):
    """
    Converts remaining common Tanglish tokens into Tamil script.

    Important because Tamil reference routing works better when
    a Tanglish sentence is mostly Tamil script rather than:
        driver இங்க vandhutaara?

    Better:
        driver இங்க வந்துட்டாரா?
    """

    out = str(text)

    words = sorted(
        EXTRA_TANGLISH_WORDS.keys(),
        key=len,
        reverse=True
    )

    for word in words:

        replacement = EXTRA_TANGLISH_WORDS[word]

        out = re.sub(
            r'(?<![A-Za-z])'
            + re.escape(word)
            + r'(?![A-Za-z])',
            replacement,
            out,
            flags=re.IGNORECASE
        )

    return out


# ============================================================
# 2. FINAL TEXT CLEANUP
# ============================================================

def tanglish_clarity_postprocess(text, group="ENTITY"):

    out = str(text).strip()

    if not out:
        return out

    group = str(group).upper().strip()

    # Apply extra conversion mainly for Tamil/Tanglish routes.
    if group in ("TAMIL", "TANGLISH", "ENTITY"):

        out = normalize_extra_tanglish(
            out
        )

    # Fix duplicated suffixes.
    out = re.sub(
        r'நிமிடத்தில்\s*-\s*ல்',
        'நிமிடத்தில்',
        out
    )

    out = re.sub(
        r'மணிக்கு\s*-\s*க்கு',
        'மணிக்கு',
        out
    )

    # Clean spacing.
    out = re.sub(
        r'\s+',
        ' ',
        out
    ).strip()

    return out


print("✓ Extra Tanglish clarity normalization ready")


# ---- Source section 37 ----
import re
import time


# ============================================================
# 1. BASIC CLEANING FOR CHUNKS ONLY
# ============================================================

def _clean_chunk(text):
    """
    Clean whitespace around an already-normalized chunk.
    DOES NOT modify pronunciation or normalization.
    """

    text = str(text)

    text = text.replace(
        "\u00A0",
        " "
    )

    text = re.sub(
        r"[ \t]+",
        " ",
        text
    )

    text = re.sub(
        r"\s+([,.!?])",
        r"\1",
        text
    )

    return text.strip()


# ============================================================
# 2. LANGUAGE / REFERENCE ROUTING
# ============================================================

TAMIL_CHAR_RE = re.compile(
    r"[\u0B80-\u0BFF]"
)


def route_reference_clean(
    normalized_text,
    group="ENTITY"
):
    """
    Decide which DhVaani reference voice to use.

    ENGLISH  -> English reference
    TAMIL    -> Tamil reference
    TANGLISH -> Tamil reference
    ENTITY   -> based on Tamil characters
    """

    text = str(
        normalized_text
    )

    group = str(
        group
    ).upper().strip()

    if group == "ENGLISH":
        return "ENGLISH"

    if group in (
        "TAMIL",
        "TANGLISH"
    ):
        return "TAMIL"

    if TAMIL_CHAR_RE.search(text):
        return "TAMIL"

    return "ENGLISH"

# ============================================================
# 3. ENTITY-PROTECTED SEMANTIC CHUNKER
# ============================================================

import re


# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

# Sentences at or below this size remain one chunk.
SEMANTIC_SINGLE_CHUNK_WORDS = 7

# A chunk shorter than this is merged with a neighbouring chunk.
SEMANTIC_MIN_CHUNK_WORDS = 3

# This is a soft limit only.
# The chunker will NEVER cut an entity just to satisfy this limit.
SEMANTIC_SOFT_MAX_WORDS = 12


# ------------------------------------------------------------
# Entity vocabulary
# ------------------------------------------------------------

ENGLISH_DIGIT_WORDS = (
    r"zero|one|two|three|four|five|fyeve|six|"
    r"seven|sevven|eight|ait|nine"
)

ENGLISH_NUMBER_WORDS = (
    ENGLISH_DIGIT_WORDS
    + r"|ten|eleven|twelve|thirteen|fourteen|fifteen|"
      r"sixteen|seventeen|eighteen|nineteen|"
      r"twenty|thirty|forty|fifty|sixty|seventy|"
      r"eighty|ninety|hundred|thousand|lakh|million|and"
)

TAMIL_NUMBER_WORDS = (
    r"பூஜ்ஜியம்|ஒன்று|இரண்டு|மூன்று|நான்கு|ஐந்து|"
    r"ஆறு|ஏழு|எட்டு|ஒன்பது|பத்து|பதினொன்று|"
    r"பன்னிரண்டு|பதின்மூன்று|பதினான்கு|பதினைந்து|"
    r"பதினாறு|பதினேழு|பதினெட்டு|பத்தொன்பது|"
    r"இருபது|இருபத்தி|இருபத்தொன்று|இருபத்திரண்டு|"
    r"இருபத்திமூன்று|இருபத்திநான்கு|இருபத்தைந்து|"
    r"இருபத்தாறு|இருபத்தேழு|இருபத்தெட்டு|"
    r"இருபத்தொன்பது|முப்பது|முப்பத்தி|நாற்பது|"
    r"நாற்பத்தி|ஐம்பது|ஐம்பத்தி|அறுபது|அறுபத்தி|"
    r"எழுபது|எழுபத்தி|எண்பது|எண்பத்தி|"
    r"தொண்ணூறு|தொண்ணூற்று|நூறு|நூற்று|"
    r"இருநூறு|இருநூற்று|முந்நூறு|முந்நூற்று|"
    r"நானூறு|நானூற்று|ஐந்நூறு|ஐந்நூற்று|"
    r"அறுநூறு|அறுநூற்று|எழுநூறு|எழுநூற்று|"
    r"எண்ணூறு|எண்ணூற்று|ஆயிரம்|ஆயிரத்து|"
    r"இரண்டாயிரம்|இரண்டாயிரத்து"
)

ENGLISH_MONTHS = (
    r"January|February|March|April|May|June|July|"
    r"August|September|October|November|December"
)

TAMIL_MONTHS= (
    r"ஜனவரி|பிப்ரவரி|மார்ச்|ஏப்ரல்|மே|ஜூன்|"
    r"ஜூலை|ஆகஸ்ட்|செப்டம்பர்|அக்டோபர்|"
    r"நவம்பர்|டிசம்பர்"
)


# ------------------------------------------------------------
# Entity patterns
# ------------------------------------------------------------

ENTITY_PATTERNS = [

    # --------------------------------------------------------
    # Raw numeric date:
    # 31/08/2026, 31-08-2026
    # --------------------------------------------------------
    re.compile(
        r"(?<!\d)\d{1,2}[/-]\d{1,2}[/-]\d{4}(?!\d)",
        re.IGNORECASE
    ),

    # --------------------------------------------------------
    # Raw time:
    # 7:30, 7:30 PM, 7:30 PMக்கு
    # --------------------------------------------------------
    re.compile(
        r"(?<!\d)\d{1,2}:\d{2}"
        r"(?:\s*[AP]\.?M\.?)?"
        r"(?:-?க்கு)?",
        re.IGNORECASE
    ),

    # --------------------------------------------------------
    # Raw currency and distance
    # --------------------------------------------------------
    re.compile(
        r"(?:₹|Rs\.?|INR)\s*\d[\d,]*(?:\.\d+)?",
        re.IGNORECASE
    ),

    re.compile(
        r"\d+(?:\.\d+)?\s*"
        r"(?:km|kms|kilometres?|kilometers?|கிலோமீட்டர்)",
        re.IGNORECASE
    ),

    # --------------------------------------------------------
    # Raw phone numbers
    # --------------------------------------------------------
    re.compile(
        r"(?<!\w)"
        r"(?:\+?\d{1,3}[\s-]?)?"
        r"(?:\d[\s-]?){10,12}"
        r"(?!\w)"
    ),

    # --------------------------------------------------------
    # Raw booking/vehicle IDs:
    # TN45AB1234, TN-09-AB-1234
    # --------------------------------------------------------
    re.compile(
        r"\b[A-Z]{2}[\s-]?\d{1,2}[\s-]?"
        r"[A-Z]{1,3}[\s-]?\d{3,4}\b",
        re.IGNORECASE
    ),

    # --------------------------------------------------------
    # Spoken OTP:
    # o tee pee, four ait two one
    # --------------------------------------------------------
    re.compile(
        rf"\b(?:o\s+tee\s+pee|OTP)"
        rf"\s*,?\s*(?:{ENGLISH_DIGIT_WORDS})"
        rf"(?:[\s,]+(?:{ENGLISH_DIGIT_WORDS})){{3,7}}",
        re.IGNORECASE
    ),

    # --------------------------------------------------------
    # Spoken phone number:
    # phone number, nine ait ... zero
    # --------------------------------------------------------
    re.compile(
        rf"\b(?:phone\s+number|mobile\s+number)"
        rf"\s*(?:is)?\s*,?\s*"
        rf"(?:{ENGLISH_DIGIT_WORDS})"
        rf"(?:[\s,]+(?:{ENGLISH_DIGIT_WORDS})){{7,14}}",
        re.IGNORECASE
    ),

    # --------------------------------------------------------
    # Spoken booking ID:
    # booking aiyy dee, tee en, four fyeve...
    # Protected until the next safe clause.
    # --------------------------------------------------------
    re.compile(
        r"\bbooking\s+"
        r"(?:a[iy]+(?:y+)?\s+dee|eye\s+dee|ID)"
        r"(?:\s+is)?\s*,?\s*"
        r".+?"
        r"(?="
        r",?\s+(?:and|but)\s+|"
        r"\s+மற்றும்\s+|"
        r"\s+ready\b|"
        r"\s+ஆக\b|"
        r"[.!?]|$"
        r")",
        re.IGNORECASE
    ),

    # --------------------------------------------------------
    # English spoken dates:
    # December twenty fyeve, two thousand twenty six
    # --------------------------------------------------------
    re.compile(
        rf"\b(?:{ENGLISH_MONTHS})\s+"
        rf"(?:{ENGLISH_NUMBER_WORDS})(?:[-\s]+"
        rf"(?:{ENGLISH_NUMBER_WORDS})){{0,3}}"
        rf"\s*,?\s*"
        rf"(?:two\s+thousand|twenty\s+twenty)"
        rf"(?:[-\s]+(?:{ENGLISH_NUMBER_WORDS})){{1,3}}",
        re.IGNORECASE
    ),

    # --------------------------------------------------------
    # Numeric-order spoken date:
    # twenty fyeve-twelve-two thousand twenty six
    # --------------------------------------------------------
    re.compile(
        rf"\b(?:{ENGLISH_NUMBER_WORDS})"
        rf"(?:\s+(?:{ENGLISH_NUMBER_WORDS}))?"
        rf"[-/](?:{ENGLISH_NUMBER_WORDS})"
        rf"(?:\s+(?:{ENGLISH_NUMBER_WORDS}))?"
        rf"[-/](?:two\s+thousand)"
        rf"(?:\s+(?:{ENGLISH_NUMBER_WORDS})){{1,3}}",
        re.IGNORECASE
    ),

    # --------------------------------------------------------
    # Tamil spoken dates
    # --------------------------------------------------------
    re.compile(
        rf"(?:{TAMIL_MONTHS})\s+"
        rf"(?:{TAMIL_NUMBER_WORDS})(?:\s+(?:{TAMIL_NUMBER_WORDS})){{0,3}}"
        rf"\s*,?\s*"
        rf"(?:{TAMIL_NUMBER_WORDS})(?:\s+(?:{TAMIL_NUMBER_WORDS})){{1,5}}"
        rf"(?:\s+அன்று|\s+anru)?",
        re.IGNORECASE
    ),

    # --------------------------------------------------------
    # English spoken time:
    # six thirty, pee em
    # fyeve forty fyeve ay em, ku
    # --------------------------------------------------------
    re.compile(
        rf"(?:(?:morning|evening|காலை|மதியம்|மாலை|இரவு)\s+)?"
        rf"(?:{ENGLISH_NUMBER_WORDS})"
        rf"(?:\s+(?:{ENGLISH_NUMBER_WORDS})){{0,2}}"
        rf"\s*,?\s*"
        rf"(?:ay|pee)\s+em"
        rf"(?:\s*,?\s*(?:ku|க்கு))?",
        re.IGNORECASE
    ),

    # --------------------------------------------------------
    # Tamil spoken time:
    # காலை ஐந்து நாற்பத்தி ஐந்து மணிக்கு
    # மாலை ஆறு பதினைந்து மணிக்கு
    # --------------------------------------------------------
    re.compile(
        rf"(?:(?:காலை|மதியம்|மாலை|இரவு)\s+)?"
        rf"(?:{TAMIL_NUMBER_WORDS})"
        rf"(?:\s+(?:{TAMIL_NUMBER_WORDS})){{0,4}}"
        rf"\s+மணிக்கு",
        re.IGNORECASE
    ),

    # --------------------------------------------------------
    # English spoken fare/amount
    # --------------------------------------------------------
    re.compile(
        rf"\b(?:fare|fair|amount|total)"
        rf"(?:\s+is)?\s+"
        rf"(?:{ENGLISH_NUMBER_WORDS})"
        rf"(?:\s+(?:{ENGLISH_NUMBER_WORDS})){{0,8}}"
        rf"\s+(?:rupees?|INR)",
        re.IGNORECASE
    ),

    # Amount without fare label
    re.compile(
        rf"\b(?:{ENGLISH_NUMBER_WORDS})"
        rf"(?:\s+(?:{ENGLISH_NUMBER_WORDS})){{0,8}}"
        rf"\s+(?:rupees?|paise)\b",
        re.IGNORECASE
    ),

    # --------------------------------------------------------
    # Tamil spoken fare/amount
    # --------------------------------------------------------
    re.compile(
        rf"(?:fair|fare|amount|தொகை)?\s*"
        rf"(?:{TAMIL_NUMBER_WORDS})"
        rf"(?:\s+(?:{TAMIL_NUMBER_WORDS})){{0,6}}"
        rf"\s+(?:ரூபாய்|பைசா)",
        re.IGNORECASE
    ),

    # --------------------------------------------------------
    # Distance and duration
    # --------------------------------------------------------
    re.compile(
        rf"(?:{ENGLISH_NUMBER_WORDS}|{TAMIL_NUMBER_WORDS})"
        rf"(?:\s+(?:{ENGLISH_NUMBER_WORDS}|{TAMIL_NUMBER_WORDS})){{0,4}}"
        rf"\s+(?:"
        rf"kilometres?|kilometers?|km|kms|கிலோமீட்டர்|"
        rf"minutes?|minits?|hours?|நிமிடம்|நிமிடத்தில்|மணி"
        rf")(?:-ல்|-இல்|ல்)?",
        re.IGNORECASE
    ),
]


# ------------------------------------------------------------
# Protect and restore entities
# ------------------------------------------------------------

def _protect_semantic_entities(text):
    """
    Replace every detected entity with one indivisible placeholder.

    Returns:
        protected_text, entity_map
    """

    protected_text = str(text)
    entity_map = {}
    entity_index = 0

    for pattern in ENTITY_PATTERNS:

        def replace_entity(match):
            nonlocal entity_index

            entity = match.group(0).strip()

            if not entity:
                return match.group(0)

            placeholder = f"ENTITYTOKEN{entity_index}X"
            entity_map[placeholder] = entity
            entity_index += 1

            return placeholder

        protected_text = pattern.sub(
            replace_entity,
            protected_text
        )

    return protected_text, entity_map


def _restore_semantic_entities(text, entity_map):
    restored = str(text)

    for placeholder, entity in entity_map.items():
        restored = restored.replace(
            placeholder,
            entity
        )

    return _clean_chunk(restored)


# ------------------------------------------------------------
# Safe clause splitting
# ------------------------------------------------------------

def _split_at_safe_boundaries(protected_text):
    """
    Split only at genuine clause boundaries.

    Important:
    - A normal comma is NOT treated as a split point because dates,
      times, OTPs and IDs contain commas.
    - Protected ENTITYTOKEN values cannot be split.
    """

    text = _clean_chunk(protected_text)

    if not text:
        return []

    # Strong sentence boundaries.
    sentence_parts = re.split(
        r"(?<=[.!?])\s+",
        text
    )

    result = []

    for sentence in sentence_parts:

        sentence = sentence.strip()

        if not sentence:
            continue

        # Safe English clause boundary:
        # "... rupees, and your driver ..."
        sentence = re.sub(
            r",\s+(and|but)\s+",
            r"||| \1 ",
            sentence,
            flags=re.IGNORECASE
        )

        # Safe Tamil/Tanglish clause boundary:
        # "... ரூபாய் மற்றும் destination ..."
        sentence = re.sub(
            r"\s+(மற்றும்|ஆனால்)\s+",
            r" ||| \1 ",
            sentence
        )

        # Semicolon and colon can be used as safe boundaries.
        sentence = re.sub(
            r"\s*[;:]\s+",
            " ||| ",
            sentence
        )

        parts = [
            part.strip()
            for part in sentence.split("|||")
            if part.strip()
        ]

        result.extend(parts)

    return result


# ------------------------------------------------------------
# Meaningfulness correction
# ------------------------------------------------------------

def _merge_incomplete_chunks(chunks):
    """
    Prevent chunks such as:
        ['மாலை', 'ஆறு பதினைந்து மணிக்கு ...']
        ['Your destination is', 'nine kilometres away']
        ['The driver is currently', 'two kilometres away']

    A short or syntactically incomplete chunk is joined to its
    neighbouring chunk.
    """

    chunks = [
        _clean_chunk(chunk)
        for chunk in chunks
        if _clean_chunk(chunk)
    ]

    if len(chunks) <= 1:
        return chunks

    incomplete_endings = re.compile(
        r"\b(?:"
        r"is|are|was|were|for|at|on|in|from|to|with|"
        r"currently|approximately|scheduled|"
        r"your|my|the|a|an|"
        r"உங்கள்|உங்க|உங்களோட|என்|ஒரு|"
        r"காலை|மதியம்|மாலை|இரவு|"
        r"மற்றும்|ஆனால்"
        r")\s*[,.]?$",
        re.IGNORECASE
    )

    merged = []
    index = 0

    while index < len(chunks):

        current = chunks[index]
        current_words = current.split()

        should_join_next = (
            index + 1 < len(chunks)
            and (
                len(current_words) < SEMANTIC_MIN_CHUNK_WORDS
                or incomplete_endings.search(current)
            )
        )

        if should_join_next:
            current = _clean_chunk(
                current + " " + chunks[index + 1]
            )
            index += 2
        else:
            merged.append(current)
            index += 1
            continue

        merged.append(current)

    # If the last chunk is extremely short, attach it backwards.
    if (
        len(merged) >= 2
        and len(merged[-1].split()) < SEMANTIC_MIN_CHUNK_WORDS
    ):
        merged[-2] = _clean_chunk(
            merged[-2] + " " + merged[-1]
        )
        merged.pop()

    return merged

# ------------------------------------------------------------
# Soft splitting for long semantic clauses
# ------------------------------------------------------------

def _soft_split_long_chunks(chunks):
    """
    Split long chunks that contain no explicit clause boundary.

    IMPORTANT:
    - This operates while entities are still protected as ENTITYTOKEN...
    - Therefore OTP/date/time/phone/booking-ID entities remain indivisible.
    - Uses SEMANTIC_SOFT_MAX_WORDS as a soft maximum.
    - Avoids tiny final chunks.
    """

    result = []

    for chunk in chunks:

        chunk = _clean_chunk(chunk)

        if not chunk:
            continue

        words = chunk.split()

        # Already short enough
        if len(words) <= SEMANTIC_SOFT_MAX_WORDS:
            result.append(chunk)
            continue

        start = 0

        while start < len(words):

            remaining = len(words) - start

            # Keep the remaining words together if they fit.
            if remaining <= SEMANTIC_SOFT_MAX_WORDS:
                piece = " ".join(words[start:])
                result.append(
                    _clean_chunk(piece)
                )
                break

            # Normal soft cut
            end = start + SEMANTIC_SOFT_MAX_WORDS

            # ------------------------------------------------
            # Prefer a linguistically useful boundary
            # near the desired cut.
            # ------------------------------------------------

            preferred_words = {
                # English
                "and",
                "but",
                "then",
                "because",
                "while",
                "after",
                "before",
                "from",
                "at",

                # Tamil
                "மற்றும்",
                "ஆனால்",
                "பிறகு",
                "வரை",
                "இருந்து",
                "அன்று",
                "மணிக்கு",

                # Tanglish
                "matrum",
                "aanaal",
                "apram",
                "appuram",
                "irundhu",
                "varaikkum",
            }

            search_start = max(
                start + SEMANTIC_MIN_CHUNK_WORDS,
                end - 4
            )

            best_cut = None

            for i in range(
                end - 1,
                search_start - 1,
                -1
            ):

                clean_word = (
                    words[i]
                    .strip(" ,.!?")
                    .lower()
                )

                if clean_word in preferred_words:
                    # Keep boundary word with C1
                    best_cut = i + 1
                    break

            if best_cut is not None:
                end = best_cut

            # ------------------------------------------------
            # Don't leave a tiny final chunk
            # ------------------------------------------------

            remaining_after = len(words) - end

            if (
                remaining_after > 0
                and
                remaining_after < SEMANTIC_MIN_CHUNK_WORDS
            ):
                end = len(words)

            piece = " ".join(
                words[start:end]
            )

            piece = _clean_chunk(piece)

            if piece:
                result.append(piece)

            start = end

    return result
# ------------------------------------------------------------
# Final semantic chunker
# ------------------------------------------------------------

def entity_protected_semantic_chunks(text, language=None):
    """
    Entity-safe semantic chunking for English, Tamil and Tanglish.

    Processing order:
        1. Clean normalized text.
        2. Protect complete entities.
        3. Split only at safe clause boundaries.
        4. Merge incomplete phrases.
        5. Restore protected entities.

    No word-count-based hard splitting is used.
    """

    text = _clean_chunk(text)

    if not text:
        return []

    # Short sentences remain intact.
    if len(text.split()) <= SEMANTIC_SINGLE_CHUNK_WORDS:
        return [text]

    protected_text, entity_map = _protect_semantic_entities(
        text
    )

    protected_chunks = _split_at_safe_boundaries(
        protected_text
    )

    protected_chunks = _merge_incomplete_chunks(
        protected_chunks
    )

    chunks = [
        _restore_semantic_entities(chunk, entity_map)
        for chunk in protected_chunks
    ]

    chunks = [
        chunk
        for chunk in chunks
        if chunk
    ]

    if not chunks:
        return [text]

    return chunks


# ============================================================
# 4. TAMIL / TANGLISH / ENTITY CHUNKING
# ============================================================

def safe_semantic_chunks(text, language=None):
    return entity_protected_semantic_chunks(
        text,
        language=language
    )


# ============================================================
# 5. ENGLISH CHUNKING
# ============================================================



print("✓ Entity-protected semantic chunker loaded")
print("✓ Time/date/amount/distance/phone/OTP/ID protection enabled")
print("✓ Word-count-based internal entity splitting disabled")


# ============================================================
# 5. ENGLISH CHUNKING
# ============================================================

def english_safe_chunks(
    text
):
    """
    English semantic chunking.

    Uses the same smart chunker but keeps very short
    English sentences as a single chunk.
    """

    text = _clean_chunk(
        text
    )

    if not text:

        return []

    # --------------------------------------------------------
    # Read your existing config if available
    # --------------------------------------------------------

    single_chunk_limit = globals().get(
        "ENGLISH_SINGLE_CHUNK_WORDS",
        10
    )

    min_chunk_words = globals().get(
        "ENGLISH_MIN_CHUNK_WORDS",
        4
    )

    words = text.split()

    # --------------------------------------------------------
    # Short English sentence -> keep whole
    # --------------------------------------------------------

    if len(words) <= single_chunk_limit:

        return [
            text
        ]

    chunks = call_smart_chunker(
        text,
        language="ENGLISH"
    )

    if not chunks:

        return [
            text
        ]

    # --------------------------------------------------------
    # Avoid extremely tiny English chunks
    # --------------------------------------------------------

    merged = []

    for chunk in chunks:

        chunk = _clean_chunk(
            chunk
        )

        if not chunk:
            continue

        if (
            merged
            and len(
                chunk.split()
            ) < min_chunk_words
        ):

            merged[-1] = _clean_chunk(
                merged[-1]
                + " "
                + chunk
            )

        else:

            merged.append(
                chunk
            )

    # --------------------------------------------------------
    # Don't leave C1 as a 1–2 word fragment
    # --------------------------------------------------------

    if (
        len(merged) >= 2
        and
        len(
            merged[0].split()
        ) < min_chunk_words
    ):

        merged[1] = _clean_chunk(
            merged[0]
            + " "
            + merged[1]
        )

        merged = merged[1:]

    if not merged:

        return [
            text
        ]

    return merged


# ============================================================
# 6. MAIN REQUEST PREPARATION
# ============================================================

def prepare_movio_request(
    raw_text,
    group="ENTITY"
):
    """
    Main preprocessing function before DhVaani.

    IMPORTANT:
    normalize_taxi_text() is the ONLY normalization function
    used here.
    """

    # --------------------------------------------------------
    # INPUT
    # --------------------------------------------------------

    raw = str(
        raw_text
    ).strip()

    group = str(
        group
    ).upper().strip()

    if not raw:

        raise ValueError(
            "raw_text is empty"
        )

    # ========================================================
    # NORMALIZATION
    # ========================================================
    #
    # YOUR NORMALIZATION ONLY.
    #
    # DO NOT ADD:
    #
    # cleanup_normalized_text(...)
    #
    # tanglish_clarity_postprocess(...)
    #
    # ========================================================

    t0 = time.perf_counter()

    normalized = normalize_taxi_text(
        raw
    )

    normalize_ms = (
        time.perf_counter()
        - t0
    ) * 1000.0


    # ========================================================
    # ROUTING
    # ========================================================

    t1 = time.perf_counter()

    route = route_reference_clean(
        normalized,
        group
    )

    routing_ms = (
        time.perf_counter()
        - t1
    ) * 1000.0


    # ========================================================
    # CHUNKING
    # ========================================================

    t2 = time.perf_counter()

    if route == "ENGLISH":

        chunks = english_safe_chunks(
            normalized
        )

    else:

        chunks = safe_semantic_chunks(
            normalized,
            language=group
        )

    # --------------------------------------------------------
    # Safety fallback
    # --------------------------------------------------------

    if not chunks:

        chunks = [
            normalized
        ]

    # --------------------------------------------------------
    # Whitespace cleaning ONLY
    # --------------------------------------------------------

    final_chunks = []

    for chunk in chunks:

        chunk = _clean_chunk(
            chunk
        )

        if chunk:

            final_chunks.append(
                chunk
            )

    if not final_chunks:

        final_chunks = [
            normalized
        ]

    chunk_ms = (
        time.perf_counter()
        - t2
    ) * 1000.0


    # ========================================================
    # OUTPUT
    # ========================================================

    return {

        "raw":
            raw,

        "group":
            group,

        "normalized":
            normalized,

        "route":
            route,

        "chunks":
            final_chunks,

        "normalize_ms":
            normalize_ms,

        "routing_ms":
            routing_ms,

        "chunk_ms":
            chunk_ms,
    }


# ============================================================
# 7. QUALITY / LATENCY SETTINGS
# ============================================================

FIRST_CHUNK_NUM_STEP = 3

REST_CHUNK_NUM_STEP = 4


# Slightly faster natural playback
ENGLISH_SPEED = 1.12

TAMIL_SPEED = 1.12

TANGLISH_SPEED = 1.12


# Keep FP32 while checking pronunciation quality
USE_FP16_SAMPLE = False


# ============================================================
# 8. SHORTER FIRST CHUNK
# ============================================================

FIRST_MIN_WORDS = 2

FIRST_TARGET_WORDS = 2

FIRST_MAX_WORDS = 3


NEXT_MIN_WORDS = 3

NEXT_TARGET_WORDS = 5

NEXT_MAX_WORDS = 8


KEEP_WHOLE_IF_WORDS_LE = 4


ENGLISH_SINGLE_CHUNK_WORDS = 10

ENGLISH_MIN_CHUNK_WORDS = 4


# ============================================================
# 9. CHECK ACTIVE FUNCTION
# ============================================================

print("=" * 80)

print(
    "✓ FINAL prepare_movio_request loaded"
)

print(
    "✓ normalize_taxi_text is the ONLY normalizer"
)

print(
    "✓ cleanup_normalized_text NOT used"
)

print(
    "✓ tanglish_clarity_postprocess NOT used"
)

print(
    "✓ FIRST_CHUNK_NUM_STEP =",
    FIRST_CHUNK_NUM_STEP
)

print(
    "✓ REST_CHUNK_NUM_STEP =",
    REST_CHUNK_NUM_STEP
)

print(
    "✓ ENGLISH_SPEED =",
    ENGLISH_SPEED
)

print(
    "✓ TAMIL_SPEED =",
    TAMIL_SPEED
)

print(
    "✓ TANGLISH_SPEED =",
    TANGLISH_SPEED
)

print("=" * 80)


# ============================================================
# 10. VERIFY THERE IS NO OLD CLEANUP
# ============================================================

_function_names = (
    prepare_movio_request
    .__code__
    .co_names
)

assert (
    "cleanup_normalized_text"
    not in _function_names
), "OLD cleanup_normalized_text is still active!"

assert (
    "tanglish_clarity_postprocess"
    not in _function_names
), "OLD tanglish_clarity_postprocess is still active!"

assert (
    "normalize_taxi_text"
    in _function_names
), "normalize_taxi_text is missing!"

print(
    "✓ FUNCTION CHECK PASSED"
)


# ---- Source section 39 ----
# Your ORIGINAL Google Drive reference recordings; never default sample voice.
REFERENCE_ENGLISH_TEXT="Hello your cab booking has been confirmed and the driver will arrive in ten minutes."
REFERENCE_TAMIL_TEXT="நான் சென்னை சென்ட்ரல் செல்ல வேண்டும்."
ENGLISH_PROMPT_CACHE = prepare_prompt_cache(
    REFERENCE_ENGLISH,
    REFERENCE_ENGLISH_TEXT,
)

TAMIL_PROMPT_CACHE = prepare_prompt_cache(
    REFERENCE_TAMIL,
    REFERENCE_TAMIL_TEXT,
)

print("\n✓ English prompt cached")
print("✓ Tamil prompt cached")
print("✓ Prompt features remain on GPU")


# ---- Source section 41 ----
import importlib
import inspect

helper_names = (
    "chunk_tokens_punctuation",
    "batchify_tokens",
    "cross_fade_concat",
)

found = {}

for module_name in (
    "zipvoice.utils.infer",
    "zipvoice.bin.infer_zipvoice",
):
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as error:
        if error.name and (
            module_name == error.name
            or module_name.startswith(error.name + ".")
        ):
            continue
        raise

    for name in helper_names:
        function = getattr(module, name, None)
        if callable(function):
            found.setdefault(name, function)

    if len(found) == len(helper_names):
        break

missing = [name for name in helper_names if name not in found]
assert not missing, f"Backend helpers not found: {missing}"

globals().update(found)


vocoder = rt['vocoder']

@torch.inference_mode()
def synthesize_cached(
    text,
    cache,
    num_step=3,
    speed=1.07,
    seed=666,
    guidance_scale=1.0,
    t_shift=0.5,
    max_duration=100,
):

    torch.manual_seed(seed)

    # ----------------------------------------
    # NEW TEXT ONLY
    # ----------------------------------------

    text = add_punctuation(text)

    tokens_str = (
        tokenizer.texts_to_tokens(
            [text]
        )[0]
    )

    # Same calculation used by DhVaani
    token_duration = (
        cache["duration"]
        /
        (
            len(cache["tokens_str"])
            * speed
        )
    )

    max_tokens = int(
        (25 - cache["duration"])
        /
        token_duration
    )

    chunked_tokens_str = (
        chunk_tokens_punctuation(
            tokens_str,
            max_tokens=max_tokens,
        )
    )

    chunked_tokens = (
        tokenizer.tokens_to_token_ids(
            chunked_tokens_str
        )
    )

    tokens_batches, chunked_index = (
        batchify_tokens(
            chunked_tokens,
            max_duration,
            cache["duration"],
            token_duration,
        )
    )

    chunked_features = []

    # ----------------------------------------
    # MODEL
    # ----------------------------------------

    for batch_tokens in tokens_batches:

        batch_size = len(
            batch_tokens
        )

        batch_prompt_tokens = (
            cache["tokens"]
            * batch_size
        )

        batch_prompt_features = (
            cache["features"].expand(
                batch_size,
                -1,
                -1,
            )
        )

        batch_prompt_features_lens = (
            torch.full(
                (batch_size,),
                cache["features"].size(1),
                device=DEVICE,
                dtype=torch.long,
            )
        )

        (
            pred_features,
            pred_features_lens,
            _,
            _,
        ) = model.model.sample(
            tokens=batch_tokens,
            prompt_tokens=batch_prompt_tokens,
            prompt_features=batch_prompt_features,
            prompt_features_lens=(
                batch_prompt_features_lens
            ),
            speed=speed,
            t_shift=t_shift,
            duration="predict",
            num_step=num_step,
            guidance_scale=guidance_scale,
        )

        pred_features = (
            pred_features.permute(
                0,
                2,
                1,
            )
            / FEAT_SCALE
        )

        chunked_features.append(
            (
                pred_features,
                pred_features_lens,
            )
        )

    # ----------------------------------------
    # VOCODER
    # ----------------------------------------

    chunked_wavs = []

    for (
        pred_features,
        pred_features_lens
    ) in chunked_features:

        for i in range(
            pred_features.size(0)
        ):

            length = int(
                pred_features_lens[i]
            )

            wav = vocoder.decode(
                pred_features[
                    i:i+1,
                    :,
                    :length,
                ]
            )

            wav = (
                wav
                .squeeze(1)
                .clamp(-1, 1)
            )

            if (
                cache["rms"]
                < TARGET_RMS
            ):

                wav = (
                    wav
                    * cache["rms"]
                    / TARGET_RMS
                )

            chunked_wavs.append(
                wav
            )

    # ----------------------------------------
    # ORDER + JOIN
    # ----------------------------------------

    indexed = list(
        zip(
            chunked_index,
            chunked_wavs,
        )
    )

    indexed.sort(
        key=lambda x: x[0]
    )

    ordered_wavs = [
        wav
        for _, wav in indexed
    ]

    final_wav = cross_fade_concat(
        ordered_wavs,
        fade_duration=0.1,
        sample_rate=SAMPLING_RATE,
    )

    final_wav = remove_silence(
        final_wav,
        SAMPLING_RATE,
        only_edge=True,
        trail_sil=80,
    )

    # IMPORTANT:
    # no temporary WAV
    # no torchaudio.save()
    # no sf.read()
    # no os.remove()

    return (
        final_wav
        .detach()
        .float()
        .cpu()
        .squeeze()
        .numpy()
    )


# ---- Source section 43 ----
# ============================================================
# MOVIO — FP16 CACHED SYNTHESIS FOR AUDIO QUALITY TEST
# ============================================================

import torch
import numpy as np
from IPython.display import Audio, display

@torch.inference_mode()
def synthesize_cached_fp16(
    text,
    cache,
    num_step=3,
    speed=1.07,
    seed=666,
    guidance_scale=1.0,
    t_shift=0.5,
    max_duration=100,
):
    torch.manual_seed(seed)

    text = add_punctuation(text)

    tokens_str = tokenizer.texts_to_tokens([text])[0]

    token_duration = (
        cache["duration"]
        / (
            len(cache["tokens_str"])
            * speed
        )
    )

    max_tokens = int(
        (25 - cache["duration"])
        / token_duration
    )

    chunked_tokens_str = chunk_tokens_punctuation(
        tokens_str,
        max_tokens=max_tokens,
    )

    chunked_tokens = tokenizer.tokens_to_token_ids(
        chunked_tokens_str
    )

    tokens_batches, chunked_index = batchify_tokens(
        chunked_tokens,
        max_duration,
        cache["duration"],
        token_duration,
    )

    chunked_features = []

    for batch_tokens in tokens_batches:

        batch_size = len(batch_tokens)

        batch_prompt_tokens = (
            cache["tokens"]
            * batch_size
        )

        batch_prompt_features = (
            cache["features"]
            .expand(
                batch_size,
                -1,
                -1,
            )
            .contiguous()
        )

        batch_prompt_features_lens = torch.full(
            (batch_size,),
            cache["features"].size(1),
            device=DEVICE,
            dtype=torch.long,
        )

        # ====================================================
        # FP16 ONLY FOR MODEL INFERENCE
        # ====================================================

        with torch.autocast(
            device_type="cuda",
            dtype=torch.float16,
        ):
            (
                pred_features,
                pred_features_lens,
                _,
                _,
            ) = model.model.sample(
                tokens=batch_tokens,
                prompt_tokens=batch_prompt_tokens,
                prompt_features=batch_prompt_features,
                prompt_features_lens=batch_prompt_features_lens,
                speed=speed,
                t_shift=t_shift,
                duration="predict",
                num_step=num_step,
                guidance_scale=guidance_scale,
            )

        # Return features to FP32 for vocoder safety
        pred_features = (
            pred_features
            .float()
            .permute(0, 2, 1)
            / FEAT_SCALE
        )

        chunked_features.append(
            (
                pred_features,
                pred_features_lens,
            )
        )

    chunked_wavs = []

    for (
        pred_features,
        pred_features_lens
    ) in chunked_features:

        for i in range(
            pred_features.size(0)
        ):

            length = int(
                pred_features_lens[i]
            )

            # Keep vocoder in its existing precision
            wav = vocoder.decode(
                pred_features[
                    i:i+1,
                    :,
                    :length,
                ]
            )

            wav = (
                wav
                .squeeze(1)
                .clamp(-1, 1)
            )

            if cache["rms"] < TARGET_RMS:
                wav = (
                    wav
                    * cache["rms"]
                    / TARGET_RMS
                )

            chunked_wavs.append(
                wav
            )

    indexed = list(
        zip(
            chunked_index,
            chunked_wavs,
        )
    )

    indexed.sort(
        key=lambda x: x[0]
    )

    ordered_wavs = [
        wav
        for _, wav in indexed
    ]

    final_wav = cross_fade_concat(
        ordered_wavs,
        fade_duration=0.1,
        sample_rate=SAMPLING_RATE,
    )

    final_wav = remove_silence(
        final_wav,
        SAMPLING_RATE,
        only_edge=True,
        trail_sil=80,
    )

    return (
        final_wav
        .detach()
        .float()
        .cpu()
        .squeeze()
        .numpy()
    )


# ---- Source section 51 ----
def route_speed(route, group):
    if route == "TAMIL":
        return TANGLISH_SPEED if str(group).upper()=="TANGLISH" else TAMIL_SPEED
    return ENGLISH_SPEED

def production_synthesize(text, route, group, step, use_fp16=None):
    if use_fp16 is None:
        use_fp16 = USE_FP16_SAMPLE

    cache = ENGLISH_PROMPT_CACHE if route=="ENGLISH" else TAMIL_PROMPT_CACHE
    speed = route_speed(route, group)

    if use_fp16:
        return synthesize_cached_fp16(
            text=text, cache=cache, num_step=step,
            speed=speed, seed=SEED
        )

    return synthesize_cached(
        text=text, cache=cache, num_step=step,
        speed=speed, seed=SEED
    )

print("✓ Production synthesis uses cached in-memory path only")
print("✓ Step 2 is not used")
# ============================================================
# SMOOTH AUDIO JOINING
# Prevent chunk boundary artifacts
# ============================================================

import numpy as np

def smooth_join_audio(
    chunks,
    sr=24000,
    fade_ms=30
):

    if len(chunks) == 1:
        return np.asarray(
            chunks[0],
            dtype=np.float32
        )

    output = np.asarray(
        chunks[0],
        dtype=np.float32
    )

    fade_samples = int(
        sr * fade_ms / 1000
    )

    for chunk in chunks[1:]:

        chunk = np.asarray(
            chunk,
            dtype=np.float32
        )

        n = min(
            fade_samples,
            len(output),
            len(chunk)
        )

        if n == 0:
            output = np.concatenate(
                [output, chunk]
            )
            continue

        fade_out = np.linspace(
            1.0,
            0.0,
            n
        )

        fade_in = np.linspace(
            0.0,
            1.0,
            n
        )

        overlap = (
            output[-n:] * fade_out
            +
            chunk[:n] * fade_in
        )

        output = np.concatenate(
            [
                output[:-n],
                overlap,
                chunk[n:]
            ]
        )

    return output.astype(np.float32)


print("✓ Smooth chunk joining enabled")


# ---- Source section 53 ----
# ============================================================
# LATENCY OPTIMIZATION — TRUE C1 MICRO-BATCH INFERENCE
# Configuration is retained: same prompt, same speed, same steps.
# ============================================================

BATCH_WINDOW_MS = 2.0
MAX_BATCH_SIZE = 2

# Length bucketing avoids making a tiny C1 wait for a much longer
# acoustic sequence in the same padded batch.
def _target_token_count(text):
    clean = add_punctuation(str(text))
    return len(tokenizer.texts_to_tokens([clean])[0])

def _length_bucket(token_count):
    if token_count <= 16:
        return "S"
    if token_count <= 32:
        return "M"
    if token_count <= 64:
        return "L"
    return "XL"


@torch.inference_mode()
def synthesize_c1_batch(
    texts,
    route,
    group,
    step=FIRST_CHUNK_NUM_STEP,
    use_fp16=None,
):
    """
    Generate several independent C1 utterances in ONE model.sample() call.

    This does NOT reduce num_step or speech quality.
    It removes the old one-request-at-a-time GPU serialization.

    All texts in this call must share:
      - route/reference cache
      - speed
      - generation step
    """

    if not texts:
        return []

    if use_fp16 is None:
        use_fp16 = USE_FP16_SAMPLE

    texts = [str(x) for x in texts]
    cache = ENGLISH_PROMPT_CACHE if route == "ENGLISH" else TAMIL_PROMPT_CACHE
    speed = route_speed(route, group)
    batch_size = len(texts)

    torch.manual_seed(SEED)

    clean_texts = [add_punctuation(x) for x in texts]

    # Tokenize ALL requests together.
    target_tokens_str = tokenizer.texts_to_tokens(clean_texts)
    target_tokens = tokenizer.tokens_to_token_ids(target_tokens_str)

    # Repeat fixed prompt conditioning without recomputing it.
    prompt_tokens = cache["tokens"] * batch_size

    prompt_features = (
        cache["features"]
        .expand(batch_size, -1, -1)
        .contiguous()
    )

    prompt_features_lens = torch.full(
        (batch_size,),
        cache["features"].size(1),
        device=DEVICE,
        dtype=torch.long,
    )

    def _sample():
        return model.model.sample(
            tokens=target_tokens,
            prompt_tokens=prompt_tokens,
            prompt_features=prompt_features,
            prompt_features_lens=prompt_features_lens,
            speed=speed,
            t_shift=0.5,
            duration="predict",
            num_step=int(step),
            guidance_scale=1.0,
        )

    # FP16 remains quality-gated exactly as in the clean notebook.
    if bool(use_fp16):
        with torch.autocast(
            device_type="cuda",
            dtype=torch.float16,
        ):
            pred_features, pred_features_lens, _, _ = _sample()
    else:
        pred_features, pred_features_lens, _, _ = _sample()

    # Vocoder stays FP32 / existing precision.
    pred_features = (
        pred_features
        .float()
        .permute(0, 2, 1)
        / FEAT_SCALE
    )

    results = []

    # Decode individually so each predicted length is respected exactly.
    # model.sample() is the dominant cost; this loop is normally small.
    for i in range(batch_size):
        length = int(pred_features_lens[i].item())

        wav = vocoder.decode(
            pred_features[i:i+1, :, :length]
        )

        wav = wav.squeeze(1).clamp(-1, 1)

        if cache["rms"] < TARGET_RMS:
            wav = wav * cache["rms"] / TARGET_RMS

        wav = remove_silence(
            wav,
            SAMPLING_RATE,
            only_edge=True,
            trail_sil=80,
        )

        results.append(
            wav.detach().float().cpu().squeeze().numpy()
        )

    return results


print("✓ Batched C1 model.sample() ready")
print("Batch window :", BATCH_WINDOW_MS, "ms")
print("Max batch    :", MAX_BATCH_SIZE)
print("C1 step      :", FIRST_CHUNK_NUM_STEP, "(configured sampling steps)")

# ============================================================
# ROUTE-AWARE + LENGTH-BUCKETED MICRO-BATCH SCHEDULER
# ============================================================

@dataclass(order=True)
class MovioBatchJob:
    sort_key: tuple
    seq: int
    created_at: float = field(compare=False)
    kind: str = field(compare=False)
    route: str = field(compare=False)
    group: str = field(compare=False)
    text: str = field(compare=False)
    step: int = field(compare=False)
    speed: float = field(compare=False)
    token_count: int = field(compare=False)
    bucket: str = field(compare=False)

    done: threading.Event = field(compare=False, default_factory=threading.Event)
    waveform: object = field(compare=False, default=None)
    error: object = field(compare=False, default=None)

    queue_wait_ms: float = field(compare=False, default=np.nan)
    service_ms: float = field(compare=False, default=np.nan)
    batch_size: int = field(compare=False, default=1)
    batch_id: int = field(compare=False, default=-1)


class MovioMicroBatchScheduler:
    def __init__(
        self,
        queue_limit=ADMISSION_QUEUE_LIMIT,
        batch_window_ms=BATCH_WINDOW_MS,
        max_batch_size=MAX_BATCH_SIZE,
    ):
        self.queue_limit = int(queue_limit)
        self.batch_window_ms = float(batch_window_ms)
        self.max_batch_size = int(max_batch_size)

        self.cv = threading.Condition()
        self.heap = []
        self.seq = 0
        self.batch_seq = 0
        self.running = False
        self.worker = None

    def start(self):
        if self.running:
            return
        self.running = True
        self.worker = threading.Thread(
            target=self._loop,
            daemon=True,
        )
        self.worker.start()

    def stop(self):
        with self.cv:
            self.running = False
            self.cv.notify_all()
        if self.worker is not None:
            self.worker.join(timeout=5)

    def submit(self, kind, route, group, text, step):
        now = time.perf_counter()
        priority = (
            FIRST_AUDIO_PRIORITY
            if kind == "C1"
            else CONTINUATION_PRIORITY
        )

        speed = route_speed(route, group)
        token_count = _target_token_count(text)
        bucket = _length_bucket(token_count)

        with self.cv:
            if len(self.heap) >= self.queue_limit:
                raise RuntimeError("Admission queue full")

            self.seq += 1

            # C1 first, then oldest request.
            job = MovioBatchJob(
                sort_key=(priority, now, self.seq),
                seq=self.seq,
                created_at=now,
                kind=kind,
                route=route,
                group=str(group).upper(),
                text=str(text),
                step=int(step),
                speed=float(speed),
                token_count=int(token_count),
                bucket=bucket,
            )

            heapq.heappush(self.heap, job)
            self.cv.notify_all()

        return job

    @staticmethod
    def _compatible(a, b):
        # Same conditioning + same generation policy.
        return (
            a.kind == b.kind
            and a.route == b.route
            and a.step == b.step
            and abs(a.speed - b.speed) < 1e-9
            and a.bucket == b.bucket
        )

    def _collect_compatible_locked(self, first):
        batch = [first]

        # Give simultaneous arrivals a tiny window to join.
        deadline = (
            time.perf_counter()
            + self.batch_window_ms / 1000.0
        )

        while len(batch) < self.max_batch_size:
            compatible_index = None

            for i, candidate in enumerate(self.heap):
                if self._compatible(first, candidate):
                    compatible_index = i
                    break

            if compatible_index is not None:
                candidate = self.heap.pop(compatible_index)
                heapq.heapify(self.heap)
                batch.append(candidate)
                continue

            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                break

            self.cv.wait(timeout=remaining)

        return batch

    def _loop(self):
        while True:
            with self.cv:
                while self.running and not self.heap:
                    self.cv.wait(timeout=0.1)

                if not self.running and not self.heap:
                    break

                if not self.heap:
                    continue

                first = heapq.heappop(self.heap)
                batch = self._collect_compatible_locked(first)

            self.batch_seq += 1
            batch_id = self.batch_seq

            service_start = time.perf_counter()

            for j in batch:
                j.queue_wait_ms = (
                    service_start - j.created_at
                ) * 1000.0
                j.batch_size = len(batch)
                j.batch_id = batch_id

            try:
                # C1 uses true batched model.sample().
                if first.kind == "C1":
                    waveforms = synthesize_c1_batch(
                        texts=[j.text for j in batch],
                        route=first.route,
                        group=first.group,
                        step=first.step,
                        use_fp16=USE_FP16_SAMPLE,
                    )

                    torch.cuda.synchronize()

                    service_ms = (
                        time.perf_counter() - service_start
                    ) * 1000.0

                    for j, wav in zip(batch, waveforms):
                        j.waveform = wav
                        j.service_ms = service_ms

                else:
                    # Continuations remain lower priority.
                    # Keep quality path unchanged.
                    for j in batch:
                        t0 = time.perf_counter()
                        j.waveform = production_synthesize(
                            j.text,
                            j.route,
                            j.group,
                            j.step,
                        )
                        torch.cuda.synchronize()
                        j.service_ms = (
                            time.perf_counter() - t0
                        ) * 1000.0

            except Exception as e:
                for j in batch:
                    j.error = e

            finally:
                for j in batch:
                    j.done.set()


# Replace old scalar scheduler safely.
if "SCHEDULER" in globals():
    try:
        SCHEDULER.stop()
    except Exception:
        pass

SCHEDULER = MovioMicroBatchScheduler()
SCHEDULER.start()

print("✓ Route-aware micro-batch scheduler started")
print("✓ C1 requests can share one model.sample()")
print("✓ Length bucketing enabled")
print("✓ C1 quality step unchanged:", FIRST_CHUNK_NUM_STEP)
def movio_stream_response(raw_text,group="ENTITY"):
    request_start=time.perf_counter()
    p=prepare_movio_request(raw_text,group)

    route=p["route"]
    chunks=p["chunks"]

    c1=SCHEDULER.submit(
        "C1",route,group,chunks[0],FIRST_CHUNK_NUM_STEP
    )
    c1.done.wait()
    if c1.error:
        raise c1.error

    ttfa_ms=(time.perf_counter()-request_start)*1000

    # Pre-submit C2 BEFORE yielding C1.
    next_job=None
    if len(chunks)>1:
        next_job=SCHEDULER.submit(
            "CONT",route,group,chunks[1],REST_CHUNK_NUM_STEP
        )

    yield {
        "chunk_index":1,
        "chunk_text":chunks[0],
        "audio":np.asarray(c1.waveform,dtype=np.float32),
        "sample_rate":SAMPLING_RATE,
        "route":route,
        "normalized":p["normalized"],
        "ttfa_ms":ttfa_ms,
        "queue_ms":c1.queue_wait_ms,
        "service_ms":c1.service_ms
    }

    for idx in range(1,len(chunks)):
        current=next_job
        current.done.wait()
        if current.error:
            raise current.error

        following=None
        if idx+1<len(chunks):
            following=SCHEDULER.submit(
                "CONT",route,group,chunks[idx+1],REST_CHUNK_NUM_STEP
            )

        yield {
            "chunk_index":idx+1,
            "chunk_text":chunks[idx],
            "audio":np.asarray(current.waveform,dtype=np.float32),
            "sample_rate":SAMPLING_RATE,
            "route":route,
            "normalized":p["normalized"],
            "ttfa_ms":ttfa_ms,
            "queue_ms":current.queue_wait_ms,
            "service_ms":current.service_ms
        }
        next_job=following

print("✓ Streaming path ready")
