import abc
import bs4
import datetime as dt
import logging
import re
import requests
import time
import urllib
import advert as advert_module
import util

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# This file is a mess and I hate it - these websites are not too friendly for bots.
# So some evasion/request throttling is done, which introduces
# some bad division of work (like filtering offers in the scraper, because this
# may avoid additional requests). Also, if the websites ever change (even slightly)
# all this may not work anymore (the parsing/souping has to be adapted).

MAX_REQUEST = 10

class Scraper(abc.ABC):
    """Base class for scraping offers from websites"""
    def __init__(self, exploredOfferIDs = [], maxPrice=900):
        self._requestTimes = [] # store times of requests for ddos detection
        self._exploredOfferIDs = exploredOfferIDs # seen offers, do not handle same ad twice
        self._maxPrice = maxPrice # max price in euros

    def _get_user_agent(self):
        """Get constant or random user agent to make requests."""
        return 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ' +\
            'AppleWebKit/605.1.15 (KHTML, like Gecko) ' +\
            'Version/15.4 Safari/605.1.15'

    def _make_request(self, url):
        """Wrapper for requests.get and soup parser. """

        # wait depending on number of recent requests
        now = time.time()
        relevantRequestTimes = list(
            filter(lambda t: now - t < 60, self._requestTimes))
        waitTime = min(len(relevantRequestTimes) * 0.25, 5)
        time.sleep(waitTime)

        # make request
        headers = {'User-agent': self._get_user_agent()}
        reqCount = 0
        # again, this is weird but seems to happen. 404 sometimes goes away
        while reqCount < MAX_REQUEST and \
                (resp := requests.get(url, headers=headers)).status_code == 404:
            logger.warning("Got 404")
            self._requestTimes.append(time.time())
            time.sleep(5)
        if resp.status_code != 200:
            logger.warning(f"Got response {resp.status_code}: {resp.text}")
            # parse as soup
        soup = bs4.BeautifulSoup(resp.text, 'html.parser')
        logger.debug("Parser done souping")
        return soup

    def _find_in_soup(self, soup, *args, **kwargs):
        """Wrapper for soup.find with error handling."""
        soupElement = soup.find(*args, **kwargs)
        if not soupElement:
            logger.warning(
                f"No element found with args {args} and kwargs {kwargs}")
            return ""
        return soupElement.text.strip()

    def _prefilter_offer(self, exposePrice):
        """Pre filter for offers. Note that this is often already done
        in the search url (e.g. wggesucht). The purpose of prefiltering is to
        reduce the number of requests."""
        if exposePrice > self._maxPrice:
            return False
        return True

    @abc.abstractmethod
    def scrape_search_page(self, searchURL):
        """Return list of relevant information on adverts found on the url."""
        pass

    def get_exploredOfferIds(self):
        return self._exploredOfferIDs


class WgGesuchtScraper(Scraper):
    def __init__(self, *args, **kwargs):
        super(WgGesuchtScraper, self).__init__(*args, **kwargs)
        self._baseURL = 'https://www.wg-gesucht.de'

    def scrape_search_page(self, searchURL):
        """Return list of relevant information on adverts found on the url."""
        soup = self._make_request(searchURL)
        adverts = []
        for expose in soup.find_all(class_="offer_list_item"):
            exposeId = int(expose.get("data-id"))
            if exposeId in self._exploredOfferIDs:
                continue
            self._exploredOfferIDs.append(exposeId)
            advert = advert_module.Advert()
            advert.adid.set(exposeId)
            advert.title.set(self._find_in_soup(
                expose, class_="truncate_title noprint"))
            advert.website.set(self._baseURL)
            advert.url.set(urllib.parse.urljoin(self._baseURL, expose.find(
                class_="truncate_title noprint").find(href=True)["href"]))
            # sometimes weird ad pages...
            if "?" in advert.url.get():
                continue
            flatType, _, address = expose.find(
                class_="col-xs-11").text.split("|")
            advert.flatType.set(flatType.strip())
            advert.address.set(address.strip())
            priceSoup, sizeSoup = expose.find_all(class_="col-xs-3")
            advert.price.set(util.get_int_from_text(priceSoup.text))
            advert.size.set(util.get_int_from_text(sizeSoup.text))
            dateInformation = expose.find(
                class_="col-xs-5").text.replace("\n", " ")
            unlimited = re.search(r"ab\s*(?P<moveIn>[\d\.]+)", dateInformation)
            limited = re.search(
                r"(?P<moveIn>[\d\.]+)\s*-\s*(?P<moveOut>[\d\.]+)",
                dateInformation)
            if unlimited:
                advert.limited.set(False)
                advert.moveInDate.set(
                    util.parse_german_date(unlimited.group("moveIn")))
            elif limited:
                advert.limited.set(True)
                advert.moveInDate.set(
                    util.parse_german_date(limited.group("moveIn")))
                advert.moveOutDate.set(
                    util.parse_german_date(limited.group("moveOut")))
            adverts.append(advert)
        return adverts

class EbayScraper(Scraper):
    """docstring for EbayScraper"""

    def __init__(self, *args, **kwargs):
        super(EbayScraper, self).__init__(*args, **kwargs)
        self._baseURL = 'https://www.ebay-kleinanzeigen.de'

    def _extract_from_expose(self, exposeUrl):
        exposeBS = self._make_request(exposeUrl)
        advert = advert_module.Advert()
        advert.website.set(self._baseURL)
        advert.url.set(exposeUrl)
        advert.title.set(self._find_in_soup(
            exposeBS, class_="boxedarticle--title"))
        if not advert.title:
            logger.warning(f"Advert without title: {exposeUrl}")
        advert.address.set(self._find_in_soup(
            exposeBS, itemprop="locality"))
        priceText = self._find_in_soup(exposeBS, class_="boxedarticle--price")
        price = util.get_int_from_text(
            self._find_in_soup(exposeBS, class_="boxedarticle--price"))
        if (price := util.get_int_from_text(
                self._find_in_soup(exposeBS, class_="boxedarticle--price"))):
            advert.price.set(price)
        for detail in exposeBS.find_all(class_="addetailslist--detail"):
            key, val = list(map(lambda t: t.strip(),
                                detail.text.strip().split("\n")))
            if key == "Art der Unterkunft":
                advert.flatType.set(val)
            elif key.startswith("Wohnfl"):
                advert.size.set(util.get_int_from_text(val))
            elif key.startswith("Verf"):
                advert.moveInDate.set(util.parse_german_date(val))
            elif key == "Mietart":
                advert.limited.set(val == "befristet")
            elif key == "Zimmer":
                advert.rooms.set(util.get_int_from_text(val))
        kitchen = []
        for checktag in exposeBS.find_all(class_="checktag"):
            if checktag.text in ["Backofen", "Herd", "Kühlschrank", "Einbauküche"]:
                kitchen.append(checktag.text)
            if checktag.text == "Möbliert":
                advert.furnished.set(True)
        if kitchen:
            advert.kitchen.set(kitchen)
        advert.description.set(self._find_in_soup(
            exposeBS, itemprop="description"))
        return advert

    def scrape_search_page(self, searchURL):
        offerSoup = self._make_request(searchURL)
        adverts = []
        for expose in offerSoup.find_all(class_="aditem"):
            exposeId = int(expose.get("data-adid"))
            if exposeId in self._exploredOfferIDs:
                continue
            exposeUri = expose.get("data-href")
            exposeUrl = urllib.parse.urljoin(self._baseURL, exposeUri)
            advert = self._extract_from_expose(exposeUrl)
            advert.adid.set(exposeId)
            adverts.append(advert)
            self._exploredOfferIDs.append(exposeId)
        return adverts
