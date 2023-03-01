import datetime as dt
import json
import logging
import os
import threading
import time
from advert import filter_advert, set_distances, set_routes, translate_advert
from DataStorage import SearchParameters
from messenger import Messenger
from scraper import WgGesuchtScraper, EbayScraper

ALL_RUN_IDS = [ID_EBAY, ID_WG_SHARE, ID_WG_NOSHARE] = 0,1,2
# For testing (non-lambda deployment)
PERSISTANCY_FILE_LOCAL = "exploredIds.json"

def ebay(exploredOfferIDs, messenger, searchParameters):
    """ Handle ebay search URLs """
    scraper = EbayScraper(exploredOfferIDs)
    for searchURL in searchParameters.ebayUrls:
        scrapedAdverts = scraper.scrape_search_page(searchURL)
        for advert in scrapedAdverts:
            if not advert.price:
                # Some weird load/captcha problem with ebay
                continue
            if not filter_advert(advert, searchParameters):
                continue
            set_distances(advert,\
                searchParameters.poiDistances,\
                searchParameters.city)
            set_routes(advert, searchParameters.poiRoutes)
            if (language := searchParameters.translate):
                translate_advert(advert, language)
            print("[flatscrape] handling advert ebay")
            messenger.handle_advert(advert)
    return True

def wggesucht(exploredOfferIDs, messenger, searchParameters, flatshare=True):
    """ Handle wggesucht search URLs """
    scraper = WgGesuchtScraper(exploredOfferIDs)
    for searchURL in searchParameters.wggesuchtFlatUrls:
        scrapedAdverts = scraper.scrape_search_page(searchURL)
        for advert in scrapedAdverts:
            if not filter_advert(advert, searchParameters):
                continue
            advert.flatType.set("Individual Apartment")
            set_distances(advert,\
                searchParameters.poiDistances,\
                searchParameters.city)
            set_routes(advert, searchParameters.poiRoutes)
            if (language := searchParameters.translate):
                translate_advert(advert, language)
            messenger.handle_advert(advert)
    if not flatshare:
        return True
    for searchURL in searchParameters.wggesuchtWGUrls:
        scrapedAdverts = scraper.scrape_search_page(searchURL)
        for advert in scrapedAdverts:
            if not filter_advert(advert, searchParameters):
                continue
            advert.flatType.set("Shared Flat (WG)")
            set_distances(advert,\
                searchParameters.poiDistances,\
                searchParameters.city)
            set_routes(advert, searchParameters.poiRoutes)
            if (language := searchParameters.translate):
                translate_advert(advert, language)
            messenger.handle_advert(advert)
    return True

# These functions are not used in lambda (uses s3 for persistency)
def get_seen_offers():
    if not PERSISTANCY_FILE_LOCAL in os.listdir():
        return {"ebay": [], "wggesucht": []}
    with open(PERSISTANCY_FILE_LOCAL, "r") as jsonfile:
        return json.load(jsonfile)

def dump_seen_offers(seenOffers):
    with open(PERSISTANCY_FILE_LOCAL, "w") as jsonfile:
        json.dump(seenOffers, jsonfile)
 
def main(awsEvent,\
        read_offer_method=get_seen_offers,\
        write_offer_method=dump_seen_offers,\
        runIds = [ID_EBAY, ID_WG_SHARE, ID_WG_NOSHARE]):
    seenOffers = read_offer_method()
    searchParameters = SearchParameters(awsEvent)
    messenger = Messenger(awsEvent.get("TELEGRAM_BOT_TOKEN"),\
        awsEvent.get("TELEGRAM_USER_IDS"))
    # Build thread list. First, generate list of all threads, then remove
    # those that are not to be started.
    if ID_WG_SHARE in runIds and ID_WG_NOSHARE in runIds:
        runIds.remove(ID_WG_NOSHARE)
    allThreads = [None for _ in ALL_RUN_IDS]
    allThreads[ID_EBAY] = threading.Thread(\
        target=ebay,\
        args=(seenOffers["ebay"], messenger, searchParameters,))
    allThreads[ID_WG_SHARE] = threading.Thread(\
        target=wggesucht,\
        args=(seenOffers["wggesucht"], messenger, searchParameters,))
    allThreads[ID_WG_NOSHARE] = threading.Thread(\
        target=wggesucht,\
        args=(seenOffers["wggesucht"], messenger, searchParameters, False))
    scrapeThreads = [allThreads[i] for i in runIds]
    for t in scrapeThreads:
        t.start()
    while any(map(lambda t: t.is_alive(), scrapeThreads)) or messenger.check_queue():
        handledIds = messenger.handle_queue()
        if handledIds:
            print(f"[flatscrape] Handled the ids: {handledIds}")
            seenOffers["ebay"] += handledIds["ebay"]
            seenOffers["wggesucht"] += handledIds["wggesucht"]
            print(f"[flatscrape] current offers: {seenOffers}")
    print(f"[flatscrape] writing {seenOffers}")
    write_offer_method(seenOffers)

if __name__ == '__main__':
    # test case
    import sys
    with open(sys.argv[1], "r") as f:
        awsEvent = json.load(f)
    print(awsEvent)
    main(awsEvent)
