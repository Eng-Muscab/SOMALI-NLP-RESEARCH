"""Canonical Somali function-word (stop-word) list for Experiment 2.

This is the single source of truth for the 483 words that Experiment 2
("stopwords removed") strips before training, evaluation, and every figure or
dashboard view that claims to show Experiment 2 vocabulary.  Removing them
deletes 47.8% of all tokens in the corpus.

Provenance — the list is the union of three documented sources, not a hand-pick:

  A. A manually compiled inventory, `paper/Stopwrods.xlsx` (297 rows, 284 unique).
  B. The previous project list of 253 words.
  C. Paradigm closure: every inflected form of a grammatical root occurring at
     least 100 times in the corpus, plus the spelling variants A and B both
     missed (`laba` vs `labo`, `sano` vs `sanad`, `dhanka` vs `dhan`).

C is what makes the list defensible. A and B each covered only part of a verb
paradigm — A has `yahay` but not `tahay`; B has `karo` and `karaan` but not
`karto`, `karaa`, `karta`, `kartaa`. The worked removal example in
`Stopwrods.xlsx` strips `ahaan`, which appears on neither A nor B. A list of
words somebody chose cannot be defended; a rule that was applied can.

Neither A nor B is used alone: A omits 138 words B has (`dadka`, `dalka`,
`magaalada`, `markii`, `marka`, `qaar`, `badan`, the numerals), so replacing
rather than merging would put those words straight back into the word cloud.

Keep this module dependency-free (standard library only) so the FastAPI backend
can import it without pulling in matplotlib / sklearn.

Any code that filters stop words — training scripts, paper figures, or the web
platform — must import from here.  Do not re-declare a local list: a second,
smaller copy in the web backend is exactly what let words such as `ayaa`,
`wuxuu`, `markii`, and `iyadoo` keep showing up in the Experiment 2 word cloud
even though the trained Experiment 2 splits contain none of them.

Rebuild:  python paper/build_stopword_list.py
"""

from __future__ import annotations

import re

__all__ = ["SOMALI_FUNCTION_WORDS", "STOPWORD_COUNT", "remove_function_words"]

# fmt: off
SOMALI_FUNCTION_WORDS: frozenset[str] = frozenset("""
    a aad aadana aaday aadbaa aadbay aadka aadna
    aan aanad aanan aanay aaney aannu aanu aay
    aaynu adiga adigu adinka afar ah aha ahaa
    ahaado ahaan ahaanba ahaatee ahaato ahaayeen ahan ahay
    ahayd ahayeen ahayn ahaynna ahayo aheyn ahi ahna
    ama amase amma anaan aniga anigu annaga annagaa
    annagu awgeed awgii ay aya ayaa ayaad ayaana
    ayay ayayna ayee ayey ayna aynu aysan ayuu
    baa baad baan baannu badan bal balse bay
    beey bil bisha bishii caadiga dabadeed dabcan dad
    dadka dal dalka dambe dambeyn darteed dartii dhamaan
    dhammaan dhammaantood dhan dhanka dhawaad dhowr dib dibadda
    doon doona doonaa doonaan doonayaa doonayo doonin doono
    doonto e ee eey eeyga gabi gobol gobolka
    goor goorma goorta gudaha guud ha haa haatan
    hadaan hadana hadda haddaba haddana hadday haddii hadduu
    hadii haka haku hal halkaasoo halkee halkii hase
    haseyeeshee hasii hasoo hoos hor hore horeba horey
    horeyn horta idiin idiinku idin idinka idinkaa idinku
    iga igu ii iigu iima iimaanu ila ilaa
    illaa imisa immisa in ina inaa inaad inaan
    inaana inaanay inaaney inaanu inaga inan inay inaysan
    iney inkasta inkastoo innoo inoo inta intaa intaas
    intaasna intaasoo intaysan intii intiisa inuu inuusan is
    isaga isagaa isagoo isagu iska iskaba iskeed isku
    iskugu isla islaa islamarkaana isoo isu isugu iwm
    iyada iyadaa iyadoo iyadu iyaga iyagaa iyagu iyo
    jir jira jiraan jiray jireen jiri jirin jiro
    jirta jirtay jirto ka kaa kaan kaas kaasi
    kaasoo kaddib kaddibna kadib kadibna kaga kahor kala
    kalana kale kaleba kalena kaliya kama kamid kamida
    kan kana kani kara karaa karaan karay karin
    karno karo karta kartaa karto kasii kasoo kasta
    kastaba kee keliya kii kor ku kugu kula
    kulasoo kule kuma kuna kusii kusoo kuu kuugu
    kuwa kuwaan kuwaanna kuwaas kuwaasi kuwaasoo kuwan kuwee
    kuwii kuwo la laakiin laakin laba labo laga
    lagala lagama lagu laguma laguna lahaa lahaayeen lahayd
    lahayn lakiin lakin lala lama lamana lasoo lee
    leedahay leeyahay leeyihiin leh lix lkn loo looga
    loogu looguna loona ma maadaama maaha maahan maalin
    maalinta magaalada magaalo malaha mana mar mararka marka
    markaa markaan markaana markaas markay markii markiiba markuu
    maxaa maxaad maxaan maxad maxay maxayse maya mid
    midba midka midna mise misee miyuu mooyee muxuu
    naga nagala nagu naloo noo nooga noqdaan noqday
    noqdo noqon noqonaya noqotay nugul oo qaar qaarkood
    qiyaastii qof qofka runtii sabab sababta saddex sagaal
    sanad sanadka sanadkii sannadkii sano shan si sida
    sidaa sidaan sidaas sidan sidee sideed sideen sidii
    sidoo sii soo ta taas taasi taasoo tahay
    tan tani tankale tee toban todoba u uga
    ugu ula uma una unbuu usoo uu uugu
    uun uuna uusan waa waad waan waana waase
    waayahay waaye waayo wada wadan wadanka walba walbo
    wali waliba walina waqti waqtiga wax waxa waxaa
    waxaad waxaan waxaana waxaanay waxaanu waxaas waxaasna waxan
    waxana waxasoo waxay waxayna waxba waxey waxii waxuu
    way weeyaan weli wey wixii wuu wuxi wuxu
    wuxuu wuxuuna xataa xitaa yaa yaan yahay yar
    yeelay yeeshee yihiin
""".split())
# fmt: on

STOPWORD_COUNT = len(SOMALI_FUNCTION_WORDS)

# The paper quotes this number; a mismatch means the list drifted from the
# trained Experiment 2 splits and every figure would have to be regenerated.
assert STOPWORD_COUNT == 483, f"expected 483 function words, found {STOPWORD_COUNT}"

_TOKEN_RE = re.compile(r"\b\w+\b")


def remove_function_words(text: str) -> str:
    """Lower-case `text` and drop every one of the 483 Somali function words."""
    tokens = _TOKEN_RE.findall(str(text).lower())
    return " ".join(token for token in tokens if token not in SOMALI_FUNCTION_WORDS)
