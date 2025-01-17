import logging
import re

from PySubtitleGPT.Options import Options
from PySubtitleGPT.Helpers import MergeTranslations
from PySubtitleGPT.SubtitleLine import SubtitleLine
from PySubtitleGPT.ChatGPTTranslation import ChatGPTTranslation
from PySubtitleGPT.SubtitleError import LineTooLongError, NoTranslationError, TooManyNewlinesError, UnmatchedLinesError, UntranslatedLinesError

#template = re.compile(r"<translation\s+start='(?P<start>[\d:,]+)'\s+end='(?P<end>[\d:,]+)'>(?P<body>[\s\S]*?)<\/translation>", re.MULTILINE)
template = re.compile(r"<translation\s+start='(?P<start>[\d:,]+)'\s+end='(?P<end>[\d:,]+)'>[\s\r\n]*(?P<body>[\s\S]*?)<\/translation>", re.MULTILINE)

#TODO: update fallback patterns with start and end groups
fallback_patterns = [
    re.compile(r"<translation\s+number='(?P<number>.+?)'\s+start='(?P<start>[\d:,]+)'\s+end='(?P<end>[\d:,]+)'>\s*(?P<body>.*?)\s*<\/translation>", re.MULTILINE),
    re.compile(r'<translation\s*line=(\d+)\s*>(?:")?(.*?)(?:")?\s*(?:" /)?</translation>', re.MULTILINE),
    re.compile(r'<original\s*line=(\d+)\s*>(?:")?(.*?)(?:")?\s*(?:" /)?</original>', re.MULTILINE),
    re.compile(r'<line\s*number=(\d+).+?translation=(?:")?(.*?)(?:")?\s*(?:" /)?>', re.MULTILINE),
    re.compile(r'<line number=(\d+)>(?:")?(.*?)(?:")?</line>', re.MULTILINE),
    re.compile(r'(\d+)[:.]\s*"(.+?)"',  re.MULTILINE),
    re.compile(r'(?:^|\n|\\n)(\d+)[:.]\s*(.+?)(?:$|\n|\\n)', re.MULTILINE),
    ]


class ChatGPTTranslationParser:
    """
    Extract translated subtitles from a ChatGPT completion 
    """
    def __init__(self, options):
        self.options = options
        self.text = None
        self.translations = {}
        self.translated = []

    def ProcessChatGPTResponse(self, translation : ChatGPTTranslation):
        """
        Extract lines from a batched translation, using the
        pre-defined pattern to match each line, or a list of fallbacks
        if the match fails.
        """
        self.text = translation.text if isinstance(translation, ChatGPTTranslation) else str(translation) 

        if not self.text:
            raise ValueError("No translated text provided")

        matches = self.FindMatches(self.text)

        logging.debug(f"Matches: {str(matches)}")

        subs = [SubtitleLine.FromDictionary(match) for match in matches]
        self.translations = { 
            sub.key: sub for sub in subs 
            }
        
        if not self.translations:
            return None

        self.translated = MergeTranslations(self.translated, self.translations.values())
        
        return self.translated

    def FindMatches(self, text):
        """
        re.findall has some very unhelpful behaviour, so we use finditer instead.
        """
        return [{ 
            'number': match.groupdict().get('number'),
            'start': match.group('start'), 
            'end': match.group('end'), 
            'body': match.group('body')
            } for match in template.finditer(text)]

    def MatchTranslations(self, originals):
        """
        Match lines in the translation with the original subtitles
        """
        if not originals:
            raise ValueError("Original subtitles not provided")
        
        unmatched = []

        for item in originals:
            translation = self.translations.get(item.key)
            if translation:
                translation.number = item.number
                item.translation = translation.text
            else:
                item.translation = None
                unmatched.append(item)

        if unmatched:
            self.TryFuzzyMatches(unmatched)

        self.translated = MergeTranslations(self.translated, self.translations.values())

        return self.translated, unmatched

    def TryFuzzyMatches(self, unmatched):
        """
        Try to match translations to their source lines using heuristics
        """
        possible_matches = []
        for item in unmatched:
            for translation in self.translations.values():
                # This is not very convincing logic but let's try it
                if translation.start <= item.start and translation.end >= item.end:
                    possible_matches.append((item, translation))

        if possible_matches:
            for item, translation in possible_matches:
                logging.warn(f"Only found fuzzy match for line {item.number} in translations")
                item.translation = f"#Fuzzy: {translation.text}"
                #unmatched.remove(item)

    def ValidateTranslations(self):
        """
        Check if the translation seems at least plausible
        """
        if not self.translated:
            raise NoTranslationError(f"Failed to extract any translations from {self.text}", self.text)
        
        max_characters = self.options.get('max_characters')
        max_newlines = self.options.get('max_newlines')

        no_number = []
        too_long = []
        too_many_newlines = []

        for line in self.translated:
            if not line.number:
                no_number.append(line)

            if len(line.text) > max_characters:
                too_long.append(line)

            if line.text.count('\n') > max_newlines:
                too_many_newlines.append(line)

        if no_number:
            raise UnmatchedLinesError(f"{len(no_number)} translations could not be matched with a source line")

        if too_long:
            raise LineTooLongError(f"One or more lines exceeded {max_characters} characters", too_long)

        if too_many_newlines:
            raise TooManyNewlinesError(f"One or more lines contain more than {max_newlines} newlines", too_many_newlines)


