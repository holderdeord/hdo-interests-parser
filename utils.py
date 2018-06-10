# -*- coding: utf-8 -*-
import csv
import hashlib
import json
from pathlib import Path


def file_checksum(path: Path):
    buf_size = 128 * 1024  # 128kb chunks

    sha1 = hashlib.sha1()

    with path.open('rb') as f:
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
    with path.open('w+') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def write_csv(path: Path, data, field_names):
    with path.open('w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=field_names)
        writer.writeheader()
        writer.writerows(data)