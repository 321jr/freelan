from enum import Enum
from datetime import datetime

from . import (
    native,
    ffi,
)


class LogLevel(Enum):
    fatal = native.FREELAN_LOG_LEVEL_FATAL
    error = native.FREELAN_LOG_LEVEL_ERROR
    warning = native.FREELAN_LOG_LEVEL_WARNING
    important = native.FREELAN_LOG_LEVEL_IMPORTANT
    information = native.FREELAN_LOG_LEVEL_INFORMATION
    debug = native.FREELAN_LOG_LEVEL_DEBUG
    trace = native.FREELAN_LOG_LEVEL_TRACE


def utc_datetime_to_utc_timestamp(dt):
    """
    Converts an UTC datetime to an UTC timestamp.

    :param dt: The datetime instance to convert. Must be UTC.
    :returns: An UTC timestamp.
    """
    return (dt - datetime(1970, 1, 1)).total_seconds()


def utc_timestamp_to_utc_datetime(ts):
    """
    Converts an UTC timestamp to an UTC datetime.

    :param ts: The timestamp to convert. Must be UTC.
    :returns: An UTC datetime.
    """
    return datetime.utcfromtimestamp(ts)


def log_attach(entry, key, value):
    """
    Attach a value to a native log entry.

    :param key: The key. Must be a string.
    :param value: The value. Can be either a string, an integer, a float or a
    boolean value. Otherwise a TypeError is raised.

    .. note: Unicode strings are UTF-8 encoded for both keys and values.
    """
    if isinstance(key, unicode):
        key = key.encode('utf-8')

    if not isinstance(key, str):
        raise TypeError("key must be a string")

    if isinstance(value, unicode):
        value = value.encode('utf-8')

    if isinstance(value, str):
        # We must create a store a new const char* value so that the references
        # remains valid until entry expires. The safest way to achieve that is
        # to attach the string-owning object to entry itself.
        str_value = ffi.new("const char[]", value)
        entry.owned_pointers.append(str_value)
        native.freelan_log_attach(entry, key, native.FREELAN_LOG_PAYLOAD_TYPE_STRING, {'as_string': str_value})
    elif isinstance(value, bool):
        native.freelan_log_attach(entry, key, native.FREELAN_LOG_PAYLOAD_TYPE_BOOLEAN, {'as_boolean': value})
    elif isinstance(value, int):
        native.freelan_log_attach(entry, key, native.FREELAN_LOG_PAYLOAD_TYPE_INTEGER, {'as_integer': value})
    elif isinstance(value, float):
        native.freelan_log_attach(entry, key, native.FREELAN_LOG_PAYLOAD_TYPE_FLOAT, {'as_float': value})
    else:
        raise TypeError("value must be either a string, an integer, a float or a boolean value")


def log(level, timestamp, domain, code, payload=None, file=None, line=0):
    """
    Writes a log entry.

    :param level: The log level.
    :param timestamp: The timestamp attached to this log entry.
    :param domain: The log domain, as a string.
    :param code: The log entry code. A code only has meaning for a given
    domain.
    :payload: A dictionary of payload values. Keys must be string and values
    must be either strings, integers, floats or boolean values.
    :param file: The file associated to the log entry. If null, ``line`` is
    ignored.
    :param line: The line associated to the log entry.
    :returns: True if the log entry was handled. A falsy return value can
    indicate that no logging callback was set or that the current log level
    does not allow the log entry to be written.
    """
    if file is None:
        file = ffi.NULL
        line = 0

    if not payload:
        return native.freelan_log(
            level,
            timestamp,
            domain,
            code,
            0,
            ffi.NULL,
            file,
            line,
        ) != 0
    else:
        entry = native.freelan_log_start(
            level,
            timestamp,
            domain,
            code,
            ffi.NULL if not file else file,
            line if file else 0,
        )

        # This list is used to store native pointers so that they don't expire
        # until entry is deleted.
        entry.owned_pointers = []

        try:
            for key, value in payload.iteritems():
                log_attach(entry, key, value)
        finally:
            return native.freelan_log_complete(entry) != 0


CALLBACKS = {}


def set_logging_function(func):
    """
    Set the logging function.

    :param func: The logging function to call whenever a log entry is emitted.
    If `None`, no logging function is set.
    """
    CALLBACKS['logging_function'] = func

    if func is None:
        native.freelan_set_logging_callback(ffi.NULL)
    else:
        native.freelan_set_logging_callback(c_logging_callback)


def from_native_payload(payload):
    """
    Return a tuple (key, value) from a native log payload.

    :param payload: The native payload to read.
    :returns: A tuple (key, value).
    """
    key = ffi.string(payload.key)

    if payload.type == native.FREELAN_LOG_PAYLOAD_TYPE_STRING:
        value = ffi.string(payload.value['as_string']).decode('utf-8')
    elif payload.type == native.FREELAN_LOG_PAYLOAD_TYPE_INTEGER:
        value = payload.value['as_integer']
    elif payload.type == native.FREELAN_LOG_PAYLOAD_TYPE_FLOAT:
        value = payload.value['as_float']
    elif payload.type == native.FREELAN_LOG_PAYLOAD_TYPE_BOOLEAN:
        value = payload.value['as_boolean'] != 0
    else:
        value = None

    return key, value


def logging_callback(level, timestamp, domain, code, payload_size, payload, file, line):
    """
    The default logging callback.

    This callback acts as a translator from the C world to the Python realm.

    You should not need to call it directly.
    """
    logging_function = CALLBACKS.get('logging_function')

    if logging_function:
        return 1 if logging_function(
            level=LogLevel(level),
            timestamp=utc_timestamp_to_utc_datetime(timestamp),
            domain=ffi.string(domain),
            code=ffi.string(code),
            payload={
                key: value
                for key, value in (
                    from_native_payload(payload[i])
                    for i in xrange(payload_size)
                )
            },
            file=ffi.string(file) if file != ffi.NULL else None,
            line=line if file != ffi.NULL else 0,
        ) else 0

    return 0

c_logging_callback = ffi.callback(
    "int (FreeLANLogLevel, FreeLANTimestamp, char *, char *, size_t, "
    "struct FreeLANLogPayload *, char *, unsigned int)",
)(logging_callback)
