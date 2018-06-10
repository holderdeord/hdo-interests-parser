#!/usr/bin/python3
# -*- coding: utf-8 -*-
import argparse
import re
import requests
import tempfile
import shutil
import subprocess

from collections import OrderedDict
from datetime import datetime
from pathlib import Path

from utils import write_csv, write_json, file_checksum, is_int


class InterestParser:
    """
        Fetch, parse and archive representative interests from stortinget.no.

        https://www.stortinget.no/no/Stortinget-og-demokratiet/Representantene/Okonomiske-interesser/
    """
    REP_URL = 'https://www.stortinget.no/globalassets/pdf/verv_oekonomiske_interesser_register/verv_ok_interesser.pdf'
    PDF_DIR = Path('pdfs')
    DATA_DIR = Path('data')

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

    def download_new_pdf(self, url, path: Path):
        """ Download new file, if checksum changed then overwrite if not do nothing"""
        if not self.PDF_DIR.exists():
            self.PDF_DIR.mkdir()

        r = requests.get(url, stream=True)
        with tempfile.NamedTemporaryFile('wb', delete=False) as f:
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

    def clean_text(self, text):
        """Clean static headings, page breaks and line numbers"""
        text = text.replace('Regjeringsmedlemmer', '').replace('Vararepresentanter', '')
        page_break_and_line_number_re = re.compile(r'\s+_______________\s+\d*\n?', re.MULTILINE)
        return page_break_and_line_number_re.sub('', text)

    padded_newlines_pattern = re.compile(r'\n\s{2,}', re.MULTILINE)

    def clean_category_text(self, line):
        """Cleanup table data as much as we can"""
        # category lables
        cleaned = self.INTEREST_CAT_RES.sub('', line.strip()).strip()
        # newlines followed by more than 1 consecutive space
        cleaned = self.padded_newlines_pattern.sub('\n', cleaned)
        # hyphenated words
        cleaned = cleaned.replace('-\n', '')
        return cleaned

    def pdf_to_text(self, file_path):
        p = subprocess.Popen(['pdftotext', '-nopgbrk', '-layout', file_path, '-'], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        out, err = p.communicate()

        return out.decode('utf-8')

    def parse_representative_data(self, document_text, last_rep, rep=None):
        """Parse meta data, positions and interest table"""
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
        if rep_text.strip() == self.NO_REP_TEXT:
            rep_data[self.NO_REP_TEXT] = True
            return rep_data

        # Split the representative section text by category id followed by a dot
        new_category_pattern = re.compile(r'^(\d{1,2})\.\s', re.MULTILINE)

        rep_data['by_category'] = self.parse_categories(new_category_pattern, rep_text)

        return rep_data

    def parse_categories(self, new_category_pattern, rep_text):
        cats = {}
        cat_id = None
        for line in new_category_pattern.split(rep_text):
            if line == '':
                continue  # skip empty strings

            elif is_int(line):
                cat_id = line  # this is the category id
            else:
                cat_text = self.clean_category_text(line)
                if cat_id == '1':  # No reg interests
                    cat_text = True
                elif self.INTEREST_CAT_RES_NO_PAD.findall(cat_text) or cat_text == '':
                    continue
                cats[self.INTEREST_CATS[cat_id]] = cat_text

        return cats

    def parse_pdf_text(self, text):
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

            data[last_rep.group('rep_number')] = self.parse_representative_data(text, last_rep, rep=rep)
            last_rep = rep

        data[last_rep.group('rep_number')] = self.parse_representative_data(text, last_rep)

        return data

    def flatten_data(self, data):
        flattened = []
        for k, r in data.items():
            cats = r.pop('by_category', {})
            flat = r
            for ck, cv in cats.items():
                flat[ck] = cv

            flattened.append(flat)

        return flattened

    def last_updated_date(self, text):
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

    def fetch_latest_and_parse(self):
        pdf_path = self.PDF_DIR.joinpath('interests-latest.pdf')
        is_updated = self.download_new_pdf(self.REP_URL, pdf_path)
        if not is_updated:
            print("Did nothing, latest PDF already downloaded and parsed")
            exit(0)

        self.parse_and_save(pdf_path)

    def parse_and_save(self, pdf_path, archive_pdf=True, seen=None):
        pdf_text = self.pdf_to_text(pdf_path)
        pdf_text = self.clean_text(pdf_text)
        last_updated = self.last_updated_date(pdf_text)
        last_updated_str = last_updated.strftime('%Y-%m-%d')

        if seen and last_updated_str in seen:
            print("Skipping already parsed '{}'".format(pdf_path))
            return

        if archive_pdf:
            archive_path = self.PDF_DIR.joinpath('interests-{}.pdf'.format(last_updated_str))
            shutil.copy(pdf_path, archive_path)

        res = self.parse_pdf_text(pdf_text)
        res = self.flatten_data(res)

        field_names = ['rep_number', 'first_name', 'last_name', 'party'] + list(self.INTEREST_CATS.values()) + [self.NO_REP_TEXT]
        csv_path = self.DATA_DIR.joinpath('interests-{}.csv'.format(last_updated_str))
        write_csv(csv_path, res, field_names)

        json_path = self.DATA_DIR.joinpath('interests-{}.json'.format(last_updated_str))
        write_json(json_path, res)

        return last_updated_str

    def parse_existing(self):
        seen = []
        for pdf in self.PDF_DIR.glob('*.pdf'):
            last_updated_str = self.parse_and_save(pdf, archive_pdf=False, seen=seen)

            if last_updated_str is not None:
                seen.append(last_updated_str)


def get_arguments():
    desc = InterestParser.__doc__
    p = argparse.ArgumentParser(description=desc)
    p.add_argument('--parse-existing', action='store_true', default=False,
                   help='Reparse existing PDFs')

    return p.parse_args()


if __name__ == '__main__':
    parser = InterestParser()
    args = get_arguments()
    if args.parse_existing:
        parser.parse_existing()
    else:
        parser.fetch_latest_and_parse()
