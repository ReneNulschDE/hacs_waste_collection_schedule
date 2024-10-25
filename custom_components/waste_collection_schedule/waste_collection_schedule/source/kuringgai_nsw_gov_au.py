import datetime
import json
import re

import requests
from bs4 import BeautifulSoup
from requests.utils import requote_uri
from waste_collection_schedule import Collection

TITLE = "Ku-ring-gai Council"
DESCRIPTION = "Source for Ku-ring-gai Council waste collection."
URL = "https://www.krg.nsw.gov.au"
TEST_CASES = {
    "randomHouse": {
        "post_code": 2070,
        "suburb": "LINDFIELD",
        "street_name": "Wolseley Road",
        "street_number": 42,
    },
    "randomAppartment": {
        "post_code": "2074",
        "suburb": "WARRAWEE",
        "street_name": "Cherry Street",
        "street_number": "4/9",
    },
    "randomMultiunit": {
        "post_code": 2075,
        "suburb": "ST IVES",
        "street_name": "Kitchener Street",
        "street_number": "99/2-8",
    },
    "1 Latona St": {
        "post_code": "2073",
        "suburb": "PYMBLE",
        "street_name": "Latona Street",
        "street_number": 1,
    },
    "1A Latona St": {
        "post_code": "2073",
        "suburb": "PYMBLE",
        "street_name": "Latona Street",
        "street_number": "1A",
    },
}


API_URLS = {
    "session": "https://www.krg.nsw.gov.au",
    "search": "https://www.krg.nsw.gov.au/api/v1/myarea/search?keywords={}",
    "schedule": "https://www.krg.nsw.gov.au/ocapi/Public/myarea/wasteservices?geolocationid={}&ocsvclang=en-AU",
}

HEADERS = {
    "user-agent": "Mozilla/5.0",
}

ICON_MAP = {
    "General Waste": "mdi:trash-can",
    "Recycling": "mdi:recycle",
    "Green Waste": "mdi:leaf",
}


class Source:
    def __init__(
        self,
        post_code: str | int,
        suburb: str,
        street_name: str,
        street_number: str | int,
    ):
        self.post_code = str(post_code)
        self.suburb = suburb.upper()
        self.street_name = street_name
        self.street_number = str(street_number)

    def fetch(self):
        locationId = 0

        # 'collection' api call seems to require an ASP.Net_sessionID, so obtain the relevant cookie
        s = requests.Session()
        q = requote_uri(str(API_URLS["session"]))
        s.get(q, headers=HEADERS)

        # Do initial address search
        address = f"{self.street_number} {self.street_name}, {self.suburb} NSW {self.post_code}"
        q = requote_uri(str(API_URLS["search"]).format(address))
        r1 = s.get(q, headers=HEADERS)
        data = json.loads(r1.text)["Items"]

        expected_address_regexp = re.compile(
            r"{}\s+{}\s+{}[,\s]+NSW[,\s]+{}".format(
                re.escape(self.street_number),
                re.escape(self.street_name),
                re.escape(self.suburb),
                re.escape(self.post_code),
            ),
            re.IGNORECASE,
        )

        # Find the geolocation for the address
        for item in data:
            if expected_address_regexp.match(item["AddressSingleLine"]):
                locationId = item["Id"]

        if locationId == 0:
            raise ValueError("Address not found")

        # Retrieve the upcoming collections for location
        q = requote_uri(str(API_URLS["schedule"]).format(locationId))
        r2 = s.get(q, headers=HEADERS)
        data = json.loads(r2.text)
        responseContent = data["responseContent"]

        soup = BeautifulSoup(responseContent, "html.parser")
        services = soup.find_all("article")

        entries = []

        for item in services:
            waste_type = item.find("h3").text
            date = datetime.datetime.strptime(
                item.find("div", {"class": "next-service"}).text.strip(), "%a %d/%m/%Y"
            ).date()
            entries.append(
                Collection(
                    date=date,
                    t=waste_type,
                    icon=ICON_MAP.get(waste_type),
                )
            )

        return entries
