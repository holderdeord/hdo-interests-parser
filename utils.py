# -*- coding: utf-8 -*-
import csv
import hashlib
import json
import tempfile
from pathlib import Path
from subprocess import Popen, PIPE

import requests
import xmltodict

MONTHS_NB = {
    "januar": "01",
    "februar": "02",
    "mars": "03",
    "april": "04",
    "mai": "05",
    "juni": "06",
    "juli": "07",
    "august": "08",
    "september": "09",
    "oktober": "10",
    "november": "11",
    "desember": "12",
}


def file_checksum(path: Path):
    buf_size = 128 * 1024  # 128kb chunks

    sha1 = hashlib.sha1()

    with path.open("rb") as f:
        while True:
            data = f.read(buf_size)
            if not data:
                break
            sha1.update(data)

    return sha1.hexdigest()


def is_int(text):
    try:
        int(text)
        return True
    except ValueError:
        return False


def write_json(path: Path, data):
    with path.open("w+") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def write_csv(path: Path, data, field_names):
    with path.open("w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=field_names)
        writer.writeheader()
        writer.writerows(data)


def pdf_to_xml_dict(file_path):
    """ Transform pdf into a python dictionary containing PDF data"""
    p = Popen(["pdftohtml", "-i", "-xml", "-stdout", file_path], stdout=PIPE, stderr=PIPE)
    out, err = p.communicate()

    return xmltodict.parse(out.decode("utf-8"))


def pdf_to_text(file_path):
    p = Popen(["pdftotext", "-nopgbrk", "-layout", file_path, "-"], stdout=PIPE, stderr=PIPE)
    out, err = p.communicate()

    return out.decode("utf-8")


def download(url, path: Path):
    """ Download new file, if checksum changed then overwrite if not do nothing"""

    r = requests.get(url, stream=True)
    with tempfile.NamedTemporaryFile("wb", delete=False) as f:
        for chunk in r.iter_content(chunk_size=4096):
            if chunk:
                f.write(chunk)

    tmp_file_path = Path(f.name)

    if path.exists() and file_checksum(tmp_file_path) == file_checksum(path):
        tmp_file_path.unlink()
        return False

    # Move/overwrite
    tmp_file_path.rename(path)

    return True
