import re
import time
import logging

import click
from prompt_toolkit.formatted_text import FormattedText

from iredis.exceptions import InvalidArguments


logger = logging.getLogger(__name__)

_last_timer = time.time()
_timer_counter = 0
logger.debug(f"[timer] start on {_last_timer}")


def timer(title):
    global _last_timer
    global _timer_counter

    now = time.time()
    tick = now - _last_timer
    logger.debug(f"[timer{_timer_counter:2}] {tick:.8f} -> {title}")

    _last_timer = now
    _timer_counter += 1


def nativestr(x):
    return x if isinstance(x, str) else x.decode("utf-8", "replace")


def literal_bytes(b):
    if isinstance(b, bytes):
        return str(b)[2:-1]
    return b


def _valide_token(words):
    token = "".join(words).strip()
    if token:
        yield token


def _strip_quote_args(s):
    """
    Given string s, split it into args.(Like bash paring)
    Handle with all quote cases.

    Raise ``InvalidArguments`` if quotes not match

    :return: args list.
    """
    sperator = re.compile(r"\s")
    word = []
    in_quote = None
    pre_back_slash = False
    for char in s:
        if in_quote:
            # close quote
            if char == in_quote:
                if not pre_back_slash:
                    yield from _valide_token(word)
                    word = []
                    in_quote = None
                else:
                    # previous char is \ , merge with current "
                    word[-1] = char
            else:
                word.append(char)
        # not in quote
        else:
            # sperator
            if sperator.match(char):
                if word:
                    yield from _valide_token(word)
                    word = []
                else:
                    word.append(char)
            # open quotes
            elif char in ["'", '"']:
                in_quote = char
            else:
                word.append(char)
        if char == "\\" and not pre_back_slash:
            pre_back_slash = True
        else:
            pre_back_slash = False

    if word:
        yield from _valide_token(word)
    # quote not close
    if in_quote:
        raise InvalidArguments()


def split_command_args(command, all_commands):
    """
    Split Redis command text into command and args.

    :param command: redis command string, with args
    :param all_commands: full redis commands list
    """
    command = command.lstrip()
    upper_raw_command = command.upper()
    for command_name in all_commands:
        if upper_raw_command.startswith(command_name):
            l = len(command_name)
            input_command = command[:l]
            input_args = command[l:]
            break
    else:
        raise InvalidArguments(r"`{command} is not a valide Redis Command")

    args = list(_strip_quote_args(input_args))

    logger.debug(f"[Parsed comamnd name] {input_command}")
    logger.debug(f"[Parsed comamnd args] {args}")
    return input_command, args


type_convert = {"posix time": "time"}


def parse_argument_to_formatted_text(name, _type, is_option):
    result = []
    if isinstance(name, str):
        _type = type_convert.get(_type, _type)
        result.append((f"class:bottom-toolbar.{_type}", " " + name))
    elif isinstance(name, list):
        for inner_name, inner_type in zip(name, _type):
            inner_type = type_convert.get(inner_type, inner_type)
            if is_option:
                result.append(
                    (f"class:bottom-toolbar.{inner_type}", f" [{inner_name}]")
                )
            else:
                result.append((f"class:bottom-toolbar.{inner_type}", f" {inner_name}"))
    else:
        raise Exception()
    return result


def command_syntax(command, command_info):
    """
    Get command syntax based on redis-doc/commands.json

    :param command: Command name in uppercase
    :param command_info: dict loaded from commands.json, only for
        this command.
    """
    comamnd_group = command_info["group"]
    bottoms = [
        ("class:bottom-toolbar.group", f"({comamnd_group}) "),
        ("class:bottom-toolbar.command", f"{command}"),
    ]  # final display FormattedText

    command_args = []
    if command_info.get("arguments"):
        for argument in command_info["arguments"]:
            if argument.get("command"):
                # command [
                bottoms.append(
                    (f"class:bottom-toolbar.command", " [" + argument["command"])
                )
                if argument.get("enum"):
                    enums = "|".join(argument["enum"])
                    bottoms.append((f"class:bottom-toolbar.const", f" [{enums}]"))
                elif argument.get("name"):
                    bottoms.extend(
                        parse_argument_to_formatted_text(
                            argument["name"], argument["type"], argument.get("optional")
                        )
                    )
                # ]
                bottoms.append((f"class:bottom-toolbar.command", "]"))
            elif argument.get("enum"):
                enums = "|".join(argument["enum"])
                bottoms.append((f"class:bottom-toolbar.const", f" [{enums}]"))

            else:
                bottoms.extend(
                    parse_argument_to_formatted_text(
                        argument["name"], argument["type"], argument.get("optional")
                    )
                )
    if "since" in command_info:
        since = command_info["since"]
        bottoms.append(
            ("class:bottom-toolbar.since", f"   since: {since}"),
        )
    if "complexity" in command_info:
        complexity = command_info["complexity"]
        bottoms.append(
            ("class:bottom-toolbar.complexity", f" complexity:{complexity}"),
        )

    return FormattedText(bottoms)


def print_version(ctx, param, value):
    import iredis
    if not value or ctx.resilient_parsing:
        return
    click.echo(f'iredis {iredis.__version__}')
    ctx.exit()
