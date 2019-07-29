"""GF Pipeline updater.

Update the GF Pipeline sheet based on changes made to the issues and
prs in google/fonts.

Users are still able to hand modify the pipeline doc because it is
never overwritten. The script will only append or remove rows.

You will need to include a sheets_creds.json file in the same dir
as this script. This is the credentials file for Google Sheets.
You can generate this file by following:
https://gspread.readthedocs.io/en/latest/oauth2.html

This script should be run every 5 mins using a crontab.

For the time being, this script is run from GF Regression. Ask
Marc Foley m.foley.88 at gmail.com for more info.
"""
import gspread
import re
import requests
import os
import time
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
from contextlib import contextmanager
import tempfile
import shutil
import hashlib
from zipfile import ZipFile
from fontTools.ttLib import TTFont
import logging


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


__all__ = [
    "PIPELINE_SHEET",
    "SHEETS_CREDS",
    "SCOPE",
    "get_github_data",
    "github_open_prs",
    "github_closed_prs",
    "github_family_requests",
    "github_merged_prs",
    "github_closed_family_requests",
    "get_families_in_production",
    "append_to_sheet",
    "remove_from_sheet",
]


SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

HEADERS = {"Authorization": "token %s" % os.environ["GH_TOKEN"]}

PIPELINE_SHEET = "Pipeline of Google Fonts [Shared Externally]"

GH_REPO = "google/fonts"
GH_URL = "https://api.github.com/repos/{}".format(GH_REPO)

CWD = os.path.dirname(__file__)
SHEETS_CREDS = os.path.join(CWD, "sheets_creds.json")


def get_github_data(since=None):
    results = []
    if since:
        r = requests.get(
            GH_URL + "/issues?state=all&since={}".format(since), headers=HEADERS
        )
    else:
        r = requests.get(GH_URL + "/issues?state=all", headers=HEADERS)
    # if paginated results
    if "link" in r.headers:
        end = re.search(r'(?<=page=)([0-9]{1,10})\>\; rel=\"last\"', r.headers['Link']).group(1)
        pages = [i for i in range(1, int(end) + 1)]
        if since:
            pages_urls = [
                "https://api.github.com/repositories/30675533/issues?state=all&page={}&since={}".format(
                    i, since
                )
                for i in pages
            ]
        else:
            pages_urls = [
                "https://api.github.com/repositories/30675533/issues?state=all&page={}".format(
                    i
                )
                for i in pages
            ]
        for url in pages_urls:
            logger.debug("get_github_data: Requesting {}".format(url))
            r_s = requests.get(url, headers=HEADERS)
            for item in r_s.json():
                results.append(item)
    else:
        for item in r.json():
            results.append(item)
    return results


def github_open_prs(items):
    results = []
    for item in items:
        if "pull_request" in item and item["state"] == "open":
            results.append(item)
    return results


def github_closed_prs(items):
    results = []
    for item in items:
        if "pull_request" in item and item["closed_at"]:
            results.append(item)
    return results


def github_merged_prs(items):
    results = []
    for item in items:
        if "pull_request" in item and item["closed_at"]:
            url = "https://api.github.com/repos/google/fonts/pulls/{}".format(
                item["number"]
            )
            print(url)
            r = requests.get(url, headers=HEADERS)
            if "merged_at" in r.json():
                results.append(item)
    return results


def github_family_requests(items):
    results = []
    for item in items:
        if isinstance(item, str):
            continue
        if (
            "add" in item["title"].lower()
            and "added" not in item["title"].lower()
            and item["state"] == "open"
        ):
            results.append(item)
    return results


def github_closed_family_requests(items):
    results = []
    for item in items:
        if isinstance(item, str):
            continue
        if (
            "add" in item["title"].lower()
            and "added" not in item["title"].lower()
            and item["state"] == "closed"
        ):
            results.append(item)
    return results


def append_to_sheet(page, items):
    seen = page.col_values(2)
    for item in items[::-1]:
        if item["html_url"] in seen:
            continue
        # throttled due to api rate limiting
        # https://developers.google.com/pipeline_docs/api/limits
        time.sleep(2)  # api request only allows 6o per min
        page.insert_row([item["title"], item["html_url"]], index=2)


def remove_from_sheet(page, items):
    for item in items:
        time.sleep(2)
        _remove_row(page, item)


def _remove_row(page, item):
    index = None
    column = page.col_values(2)
    for idx, url in enumerate(column):
        if url == item["html_url"]:
            index = idx + 1
    if index:
        page.delete_row(index)


def download_file(url, dst=None):
    """Download a file from a url"""
    request = requests.get(url, stream=True)
    with open(dst, "wb") as downloaded_file:
        shutil.copyfileobj(request.raw, downloaded_file)
    return dst


@contextmanager
def get_pr_files(pr_id, dst=None):
    urls = []
    pr_url = "{}/pulls/{}/files".format(GH_URL, pr_id)
    r = requests.get(pr_url, headers=HEADERS)
    for item in r.json():
        urls.append(item["raw_url"])

    d = tempfile.mkdtemp() if not dst else dst
    for url in urls:
        dst_path = os.path.join(d, os.path.basename(url))
        download_file(url, dst_path)
    yield [os.path.join(d, f) for f in os.listdir(d)]
    shutil.rmtree(d)


@contextmanager
def get_gf_family(family_name):
    """Download a collection of font families from Google Fonts"""
    results = []
    url = "https://fonts.google.com/download?family={}".format(
        family_name.replace(" ", "%20")
    )
    has_family = True if requests.get(url).status_code == 200 else False
    if not has_family:
        yield None
    else:
        d = tempfile.mkdtemp()
        dst = os.path.join(d, family_name + ".zip")
        family_zip = download_file(url, dst)
        out_path = os.path.join(d, "out")
        with ZipFile(family_zip) as zipp:
            zipp.extractall(out_path)
        yield [os.path.join(out_path, f) for f in os.listdir(out_path)]
        shutil.rmtree(d)


def _family_name(ttfont):
    typo_name = ttfont["name"].getName(16, 3, 1, 1033)
    name = ttfont["name"].getName(1, 3, 1, 1033)
    return typo_name.toUnicode() if typo_name else name.toUnicode()


def pr_in_production(pr_id):
    """Return True if fonts in pr are being served on fonts.google.com"""
    print("Getting PR in prod {}".format(pr_id))
    try:
        with get_pr_files(pr_id) as pr_files:
            pr_ttfonts = [TTFont(f) for f in pr_files if f.endswith(".ttf")]
            if not pr_ttfonts:
                return False
            family_name = _family_name(pr_ttfonts[0])
            with get_gf_family(family_name) as gf_files:
                if not gf_files:
                    return False
                gf_ttfonts = [TTFont(f) for f in gf_files if f.endswith(".ttf")]
                if gf_ttfonts[0]["head"].fontRevision >= pr_ttfonts[0]["head"].fontRevision:
                    return True
    except:
        pass
    return False


def get_families_in_production(items):
    results = []
    for item in items:
        pr_id = item["number"]
        if pr_in_production(pr_id):
            results.append(item)
    return results

