import argparse
from datetime import date

from bs4 import BeautifulSoup

import requests
from tqdm import tqdm

from settings import PDF_DIR
from utils import MONTHS_NB, download

PDF_LIST_URL = "https://www.stortinget.no/no/Stortinget-og-demokratiet/Representantene/Okonomiske-interesser/register-for-stortingsrepresentantenes-verv-og-okonomiske-interesser-for-stortingsperioden-20172021/"


def scrape(verbose=False, dry_run=False):
    """ Scrape it til' you make it"""
    # Fetch PDF URLs
    res = requests.get(PDF_LIST_URL)
    soup = BeautifulSoup(res.text, "html.parser")
    pdfs_to_download = []
    for link in soup.find_all("a"):
        url = link.get("href")
        if url[-3:] != "pdf":
            continue

        # parse date
        stripped_date = link.text.replace("Register per ", "").strip()
        day = int(stripped_date.split(".")[0])
        month = int(MONTHS_NB.get(stripped_date.split(" ")[1].strip()))
        year = int(stripped_date[-4:])
        iso_date = date(year=year, month=month, day=day).isoformat()
        if not url.startswith("https://"):
            url = f"https://www.stortinget.no{url}"
        file_name = PDF_DIR.joinpath(f"interests-{iso_date}.pdf")
        pdfs_to_download.append({"url": url, "file_name": file_name})

    print(f"Found {len(pdfs_to_download)} pdfs to download...")
    if verbose:
        for pdf in pdfs_to_download:
            print(pdf["url"])

    if dry_run:
        return

    # Download
    skipped = []
    new = []
    for pdf in tqdm(pdfs_to_download, desc="pdfs"):
        if not download(pdf["url"], pdf["file_name"]):
            skipped.append(pdf["file_name"])
        else:
            new.append(pdf["file_name"])

    print("DONE")
    print(f"NEW: {len(new)}")
    print(f"EXISTING: {len(skipped)}")


def parse_cli_args():
    p = argparse.ArgumentParser(description="Scrape representative interest PDFs")
    p.add_argument("--verbose", action="store_true", default=False, help="Verbose output")
    p.add_argument("--dry-run", action="store_true", default=False, help="Don't download PDFs")

    return vars(p.parse_args())


if __name__ == "__main__":
    args = parse_cli_args()
    scrape(**args)
