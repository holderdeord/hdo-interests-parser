""" Ref: https://www.stortinget.no/no/Stortinget-og-demokratiet/Representantene/Okonomiske-interesser/"""
import argparse
import csv
import hashlib
import json
import os
import re
import requests
import tempfile
import shutil
import subprocess

from collections import OrderedDict
from datetime import datetime
from pathlib import Path

REP_URL = 'https://www.stortinget.no/globalassets/pdf/verv_oekonomiske_interesser_register/verv_ok_interesser.pdf'

NO_REP_TEXT = 'Ingen registrerte opplysninger'

INTEREST_CAT_RES = [
    r'Har ingen registreringsplik-?\n?tige interesser',
    r'Styreverv m\.?v\.',
    r'Selvstendig næring',
    r'Lønnet stilling m\.?v\.',
    r'Tidligere arbeidsgiver',
    r'Framtidig arbeidsgiver',
    r'Økonomisk støtte',
    r'Eiendom i næring',
    r'Aksjer m\.?v\.',
    r'Utenlandsreiser',
    r'Gaver',
]
INTEREST_CAT_RES_NO_PAD = re.compile(r'|'.join(INTEREST_CAT_RES))
INTEREST_CAT_RES = re.compile(r'\s\s|'.join(INTEREST_CAT_RES))

INTEREST_CATS = OrderedDict({
    '1': 'Har ingen registreringspliktige interesser',
    '2': 'Styreverv mv.',
    '3': 'Selvstendig næring',
    '4': 'Lønnet stilling mv.',
    '5': 'Tidligere arbeidsgiver',
    '6': 'Framtidig arbeidsgiver',
    '7': 'Økonomisk støtte',
    '8': 'Eiendom i næring',
    '9': 'Aksjer mv.',
    '10': 'Utenlandsreiser',
    '11': 'Gaver',
})


def _checksum(filename):
    buf_size = 128 * 1024  # 128kb chunks

    sha1 = hashlib.sha1()

    with open(filename, 'rb') as f:
        while True:
            data = f.read(buf_size)
            if not data:
                break
            sha1.update(data)

    return sha1.hexdigest()


def download_new(url, path):
    """ Download new file, if checksum changed then overwrite if not do nothing"""
    if not os.path.exists('out'):
        os.mkdir('out')

    r = requests.get(url, stream=True)
    with tempfile.NamedTemporaryFile('wb', delete=False) as f:
        for chunk in r.iter_content(chunk_size=4096):
            if chunk:
                f.write(chunk)

    if os.path.exists(path) and _checksum(f.name) == _checksum(path):
        os.remove(f.name)
        return False

    # Move/overwrite
    shutil.move(f.name, path)

    return True


def _is_int(text):
    try:
        int(text)
        return True
    except ValueError:
        return False


def clean_text(text):
    """Clean static headings, page breaks and line numbers"""
    text = text.replace('Regjeringsmedlemmer', '').replace('Vararepresentanter', '')
    page_break_and_line_number_re = re.compile(r'\s+_______________\s+\d*\n?', re.MULTILINE)
    return page_break_and_line_number_re.sub('', text)


padded_newlines_pattern = re.compile(r'\n\s{2,}', re.MULTILINE)


def clean_category_text(line):
    """Cleanup table data as much as we can"""
    # category lables
    cleaned = INTEREST_CAT_RES.sub('', line.strip()).strip()
    # newlines followed by more than 1 consecutive space
    cleaned = padded_newlines_pattern.sub('\n', cleaned)
    # hyphenated words
    cleaned = cleaned.replace('-\n', '')
    return cleaned


def get_pdf_text(file_path):
    p = subprocess.Popen(['pdftotext', '-nopgbrk', '-layout', file_path, '-'], stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    out, err = p.communicate()

    return out.decode('utf-8')


def get_representative_data(document_text, last_rep, rep=None):
    """Parse meta data, positions and economic interest table"""
    # FIXME: This is fragile stuff, will probably break often

    # Representative meta data
    last_name, first_name = last_rep.group('name').split(',')
    rep_data = {key: last_rep.group(key).strip() for key in ['rep_number', 'party']}
    rep_data.update({
        'first_name': first_name.strip(),
        'last_name': last_name.strip()
    })

    # Only look at the representatives section in the document text
    rep_text_start = last_rep.span()[1]
    rep_text_stop = rep.span()[0] if rep is not None else len(document_text)
    rep_text = document_text[rep_text_start:rep_text_stop]

    # Reps with no registered interests
    if rep_text.strip() == NO_REP_TEXT:
        rep_data[NO_REP_TEXT] = True
        return rep_data

    # Split the representative section text by category id followed by a dot
    new_category_pattern = re.compile(r'^(\d{1,2})\.\s', re.MULTILINE)

    rep_data['by_category'] = parse_categories(new_category_pattern, rep_text)

    return rep_data


def parse_categories(new_category_pattern, rep_text):
    cats = {}
    cat_id = None
    for line in new_category_pattern.split(rep_text):
        if line == '':
            continue  # skip empty strings

        elif _is_int(line):
            cat_id = line  # this is the category id
        else:
            cat_text = clean_category_text(line)
            if cat_id == '1':  # No reg interests
                cat_text = True
            elif INTEREST_CAT_RES_NO_PAD.findall(cat_text) or cat_text == '':
                continue
            cats[INTEREST_CATS[cat_id]] = cat_text

    return cats


def get_pdf_rep_data(text):
    """ Match representative name, number, party and rest up until ')\n' and use these matches as delimiters"""
    data = OrderedDict()
    rep_pattern = re.compile(
        r'(?P<name>[-\w,. ]+)\((?P<rep_number>\d+), (?P<party>\w+),([-,\w\s]+)?\)\n',
        re.MULTILINE)

    last_rep = None
    matches = rep_pattern.finditer(text)
    # Walk trough the matches
    for i, rep in enumerate(matches):
        if last_rep is None:
            last_rep = rep
            continue  # Skip first

        data[last_rep.group('rep_number')] = get_representative_data(text, last_rep, rep=rep)
        last_rep = rep

    data[last_rep.group('rep_number')] = get_representative_data(text, last_rep)

    return data


def write_csv(path, data):
    field_names = ['rep_number', 'first_name', 'last_name', 'party'] + list(INTEREST_CATS.values()) + [NO_REP_TEXT]

    with open(path, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=field_names)
        writer.writeheader()
        writer.writerows(data)


def write_json(path, data):
    with open(path, 'w+') as f:
        json.dump(data, f)


def flatten_data(data):
    flattened = []
    for k, r in data.items():
        cats = r.pop('by_category', {})
        flat = r
        for ck, cv in cats.items():
            flat[ck] = cv

        flattened.append(flat)

    return flattened


def get_last_updated(text):
    pattern = re.compile(r'Ajourført pr\. (.*)')
    months = {
        'januar': '01',
        'februar': '02',
        'mars': '03',
        'april': '04',
        'mai': '05',
        'juni': '06',
        'juli': '07',
        'august': '08',
        'september': '09',
        'oktober': '10',
        'november': '11',
        'desember': '12',
    }
    date_text = pattern.search(text).group(1).lower().replace('.', '').strip()
    for m, v in months.items():
        date_text = date_text.replace(m, v)

    # zero pad day
    if date_text[1] == ' ':
        date_text = '0' + date_text

    return datetime.strptime(date_text, '%d %m %Y').date()


def fetch_latest_and_parse():
    pdf_path = 'out/interests.pdf'
    is_updated = download_new(REP_URL, pdf_path)
    if not is_updated:
        print("Did nothing, latest PDF already downloaded and parsed")
        exit(0)

    pdf_text = get_pdf_text(pdf_path)
    pdf_text = clean_text(pdf_text)
    last_updated = get_last_updated(pdf_text)
    last_updated_str = last_updated.strftime('%Y-%m-%d')

    # Archive
    shutil.copy(pdf_path, 'out/interests-{}.pdf'.format(last_updated_str))

    res = get_pdf_rep_data(pdf_text)
    res = flatten_data(res)
    write_csv('out/interests-{}.csv'.format(last_updated_str), res)
    write_json('out/interests-{}.json'.format(last_updated_str), res)


def parse_existing():
    out = Path('out')
    pdfs = out.glob('*.pdf')
    seen = []
    for pdf in pdfs:
        pdf_text = get_pdf_text(pdf.resolve())
        pdf_text = clean_text(pdf_text)
        last_updated = get_last_updated(pdf_text)
        last_updated_str = last_updated.strftime('%Y-%m-%d')
        if last_updated_str in seen:
            print("Skipping already parsed '{}'".format(pdf.resolve()))
            continue

        seen.append(last_updated_str)

        res = get_pdf_rep_data(pdf_text)
        res = flatten_data(res)
        write_csv('out/interests-{}.csv'.format(last_updated_str), res)
        write_json('out/interests-{}.json'.format(last_updated_str), res)


def get_arguments():
    desc = 'Fetch and parse representative interests from {}'.format(REP_URL)
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument('--parse-existing', action='store_true', default=False,
                        help='Reparse existing PDFs')

    return parser.parse_args()


if __name__ == '__main__':
    args = get_arguments()
    if args.parse_existing:
        parse_existing()
    else:
        fetch_latest_and_parse()
