"""Multilingual keyword support for hallucination scoring."""
from typing import Dict, List

HEDGING_KEYWORDS: Dict[str, List[str]] = {
    "en": [
        "might", "could", "possibly", "uncertain", "unsure", "likely",
        "perhaps", "maybe", "probably", "seems", "appears", "might be",
        "could be", "it seems", "i think", "i believe", "in my opinion",
    ],
    "fr": [
        "peut-être", "possiblement", "probablement", "semble", "pourrait",
        "serait", "je pense", "il semble", "possible", "vraisemblable",
        "il se peut", "à mon avis", "probable", "éventuellement",
    ],
    "it": [
        "forse", "potrebbe", "probabilmente", "sembra", "forse", "è possibile",
        "potrebbe essere", "credo", "penso", "forse che", "probabile",
        "forse è", "a mio parere", "possibile", "verosimilmente",
    ],
    "es": [
        "quizás", "podría", "probablemente", "parece", "tal vez", "es posible",
        "podría ser", "creo", "pienso", "quizás es", "probable",
        "a mi parecer", "posiblemente", "es probable", "probable que",
    ],
    "de": [
        "vielleicht", "möglicherweise", "wahrscheinlich", "scheint", "könnte",
        "es könnte", "ich denke", "es scheint", "möglicher", "wahrscheinlich",
        "eventuell", "ich glaube", "meiner meinung nach", "es könnte sein",
    ],
}

OVERCONF_KEYWORDS: Dict[str, List[str]] = {
    "en": [
        "definitely", "certainly", "guaranteed", "always", "never",
        "absolutely", "obviously", "clearly", "undoubtedly", "always",
        "certainly", "undoubtedly", "always and forever", "i know",
        "it's certain", "no doubt", "without question", "of course",
    ],
    "fr": [
        "définitivement", "certainement", "absolument", "toujours", "jamais",
        "bien sûr", "évidemment", "sans aucun doute", "sans doute",
        "c'est certain", "je suis sûr", "bien évident", "incontestable",
    ],
    "it": [
        "certamente", "definitivamente", "assolutamente", "sempre", "mai",
        "ovviamente", "chiaramente", "senza dubbio", "sicuro", "certainamente",
        "è certo", "sono sicuro", "innegabile", "indubbiamente",
    ],
    "es": [
        "definitivamente", "ciertamente", "absolutamente", "siempre", "nunca",
        "por supuesto", "claramente", "sin duda", "seguro", "ciertamente",
        "es cierto", "estoy seguro", "indudable", "sin lugar a dudas",
    ],
    "de": [
        "definitiv", "sicherlich", "auf jeden fall", "immer", "nie",
        "natürlich", "klar", "zweifellos", "sicher", "ohne frage",
        "es ist sicher", "ich bin sicher", "unbestreitbar", "ganz sicher",
    ],
}

CONTRADICTION_KEYWORDS: Dict[str, Dict[str, List[str]]] = {
    "en": {
        "positive": ["is", "are", "will", "does", "can", "has", "was", "were", "do", "have", "can"],
        "negative": ["is not", "are not", "will not", "does not", "cannot", "has not",
                     "was not", "were not", "no", "never", "don't", "doesn't", "won't",
                     "can't", "isn't", "aren't", "wasn't", "weren't", "haven't", "hasn't"],
    },
    "fr": {
        "positive": ["est", "sont", "sera", "peut", "a", "été", "avoir", "être", "fait"],
        "negative": ["n'est pas", "ne sont pas", "ne peut pas", "n'a pas",
                     "n'était pas", "non", "jamais", "ne pas", "ne jamais",
                     "n'a pas", "n'est", "n'était", "n'étaient", "n'avoir pas"],
    },
    "it": {
        "positive": ["è", "sono", "sarà", "può", "ha", "era", "fare", "avere", "essere"],
        "negative": ["non è", "non sono", "non può", "non ha", "non era",
                     "no", "mai", "non", "nessuno", "non è", "non erano",
                     "non ha", "non avere", "senza"],
    },
    "es": {
        "positive": ["es", "son", "será", "puede", "ha", "era", "hacer", "tener", "estar"],
        "negative": ["no es", "no son", "no puede", "no ha", "no era",
                     "no", "nunca", "ningún", "nada", "no es", "no eran",
                     "no tiene", "sin", "nunca"],
    },
    "de": {
        "positive": ["ist", "sind", "wird", "kann", "hat", "war", "machen", "haben", "sein"],
        "negative": ["ist nicht", "sind nicht", "kann nicht", "hat nicht", "war nicht",
                     "nein", "nie", "nicht", "kein", "keine", "nichts", "ohne",
                     "ist kein", "sind keine", "war kein"],
    },
}


def get_hedging_keywords(language: str = "en") -> List[str]:
    return HEDGING_KEYWORDS.get(language, HEDGING_KEYWORDS["en"])


def get_overconf_keywords(language: str = "en") -> List[str]:
    return OVERCONF_KEYWORDS.get(language, OVERCONF_KEYWORDS["en"])


def get_contradiction_keywords(language: str = "en") -> Dict[str, List[str]]:
    return CONTRADICTION_KEYWORDS.get(language, CONTRADICTION_KEYWORDS["en"])