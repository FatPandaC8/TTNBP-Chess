from datetime import datetime


def now():
    return datetime.now()


def timestamp():
    return now().strftime("%Y%m%d_%H%M%S")


def iso_timestamp():
    return now().isoformat()


def utc_iso():
    return datetime.utcnow().isoformat() + "Z"
