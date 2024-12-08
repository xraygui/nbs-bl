from IPython.utils.coloransi import TermColors as color
import sys
import re
from select import select


def _strip_ansi(text):
    """
    Remove ANSI escape sequences from text.

    Parameters
    ----------
    text : str
        Text containing ANSI escape sequences

    Returns
    -------
    str
        Text with ANSI sequences removed
    """
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


def _ansilen(text):
    """
    Get visible length of text containing ANSI escape sequences.

    Parameters
    ----------
    text : str
        Text containing ANSI escape sequences

    Returns
    -------
    int
        Visual length of text
    """
    return len(_strip_ansi(text))


def _wrap_text(text, width, subsequent_indent=""):
    """
    Wrap text while preserving ANSI escape sequences.

    Parameters
    ----------
    text : str
        Text to wrap
    width : int
        Maximum line width
    subsequent_indent : str
        Indentation for lines after the first

    Returns
    -------
    str
        Wrapped text with preserved ANSI sequences
    """
    words = text.split()
    lines = []
    current_line = []
    current_length = 0

    for word in words:
        word_length = _ansilen(word)
        if current_length + word_length + (1 if current_line else 0) <= width:
            current_line.append(word)
            current_length += word_length + (1 if current_line else 0)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
            current_length = word_length

    if current_line:
        lines.append(" ".join(current_line))

    # Add indentation to subsequent lines
    if subsequent_indent and len(lines) > 1:
        lines[1:] = [subsequent_indent + line for line in lines[1:]]

    return "\n".join(lines)


def colored(text, tint="white", attrs=[]):
    """
    A simple wrapper around IPython's interface to TermColors
    """
    tint = tint.lower()
    if "dark" in tint:
        tint = "Dark" + tint[4:].capitalize()
    elif "light" in tint:
        tint = "Light" + tint[5:].capitalize()
    elif "blink" in tint:
        tint = "Blink" + tint[5:].capitalize()
    elif "no" in tint:
        tint = "Normal"
    else:
        tint = tint.capitalize()
    return "{0}{1}{2}".format(getattr(color, tint), str(text), color.Normal)


def read_input(message, default, timeout, secs):
    print(message)
    rlist, _, _ = select([sys.stdin], [], [], secs)
    if rlist:
        s = sys.stdin.readline()
        if ord(s[0]) == 13 or ord(s[0]) == 10:
            return default
        else:
            return s.rstrip(chr(10) + chr(13))
    else:
        return timeout


def run_report(thisfile):
    """
    Noisily proclaim to be importing a file of python code.
    """
    print(colored("Importing %s ..." % thisfile.split("/")[-1], "lightcyan"))


def boxed_text(title, text, tint, width=75, shrink=False):
    """
    Put text in a lovely unicode block element box.

    Parameters
    ----------
    title : str
        Title to display at top of box
    text : str or list
        Text content to display in box
    tint : str
        Color to use for box borders
    width : int
        Maximum width of box
    shrink : bool
        Whether to shrink box to content width
    """
    if isinstance(text, str):
        textlines = text.splitlines()
    else:
        textlines = text

    if shrink:
        width = min(width, max((_ansilen(line) for line in textlines)))

    remainder = width - 5 - len(title)
    ul = "\u250C"
    ur = "\u2510"
    ll = "\u2514"
    lr = "\u2518"
    bar = "\u2500"
    strut = "\u2502"

    print("")
    print(colored("".join([ul, bar * 3, " ", title, " ", bar * remainder, ur]), tint))

    for line1 in textlines:
        lines = _wrap_text(line1, width, subsequent_indent=" " * 26)
        for line in lines.splitlines():
            line = line.rstrip()
            add = " " * (width - _ansilen(line))
            print("".join([colored(strut, tint), line, add, colored(strut, tint)]))

    print(colored("".join([ll, bar * width, lr]), tint))


def error_msg(text):
    return colored(text, "lightred")


def warning_msg(text):
    return colored(text, "yellow")


def url_msg(text):
    return text


def bold_msg(text):
    return colored(text, "white")


def verbosebold_msg(text):
    return colored(text, "lightcyan")


def list_msg(text):
    return colored(text, "cyan")


def disconnected_msg(text):
    return colored(text, "purple")


def info_msg(text):
    return colored(text, "brown")


def whisper(text):
    return colored(text, "darkgray")
