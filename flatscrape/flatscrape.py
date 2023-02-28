from scraper import WgGesuchtScraper, EbayScraper
from messenger import Messenger
from DataStorage import SearchParameters
import util
import advert
import json
import os
import datetime as dt
import logging
import threading
import time

ID_EBAY, ID_WG_SHARE, ID_WG_NOSHARE = 0,1,2
# For testing (non-lambda deployment)
PERSISTANCY_FILE_LOCAL = "exploredIds.json"

def ebay(exploredOfferIDs, messenger, searchParameters):
    scraper = EbayScraper(exploredOfferIDs)
    for searchURL in searchParameters.ebayUrls:
        offers = scraper.scrape_search_page(searchURL)
        for offer in offers:
            if not offer.price:
                # Will get it next time... (some weird load problem with ebay, idc...)
                continue
            if not advert.filter_advert(offer, searchParameters):
                continue
            advert.set_distances(offer, searchParameters.poiDistances, searchParameters.city)
            advert.set_routes(offer, searchParameters.poiRoutes)
            if (language := searchParameters.translate):
                advert.translate_advert(offer, language)
            print("[flatscrape] handling advert ebay")
            messenger.handle_advert(offer)
    return True



def wggesucht(exploredOfferIDs, messenger, searchParameters, flatshare=True):
    scraper = WgGesuchtScraper(exploredOfferIDs)
    for searchURL in searchParameters.wggesuchtFlatUrls:
        offers = scraper.scrape_search_page(searchURL)
        for offer in offers:
            if not advert.filter_advert(offer, searchParameters):
                continue
            offer.flatType.set("Individual Apartment")
            advert.set_distances(offer, searchParameters.poiDistances, searchParameters.city)
            advert.set_routes(offer, searchParameters.poiRoutes)
            if (language := searchParameters.translate):
                advert.translate_advert(offer, language)
            messenger.handle_advert(offer)
    if not flatshare:
        return True
    for searchURL in searchParameters.wggesuchtWGUrls:
        offers = scraper.scrape_search_page(searchURL)
        for offer in offers:
            if not advert.filter_advert(offer, searchParameters):
                continue
            offer.flatType.set("Shared Flat (WG)")
            advert.set_distances(offer, searchParameters.poiDistances, searchParameters.city)
            advert.set_routes(offer, searchParameters.poiRoutes)
            if (language := searchParameters.translate):
                advert.translate_advert(offer, language)
            messenger.handle_advert(offer)
    return True




# These functions are not used in lambda (the lambda function uses s3 for persistency)
def get_seen_offers():
    if not PERSISTANCY_FILE_LOCAL in os.listdir():
        return {"ebay": [], "wggesucht": []}
    with open(PERSISTANCY_FILE_LOCAL, "r") as jsonfile:
        return json.load(jsonfile)

def dump_seen_offers(seenOffers):
    with open(PERSISTANCY_FILE_LOCAL, "w") as jsonfile:
        json.dump(seenOffers, jsonfile)


    
    
def main(awsEvent, read_offer_method=get_seen_offers, write_offer_method=dump_seen_offers, runIds = [ID_EBAY, ID_WG_SHARE, ID_WG_NOSHARE]):
    seenOffers = read_offer_method()
    searchParameters = SearchParameters(awsEvent)
    messenger = Messenger(awsEvent.get("TELEGRAM_BOT_TOKEN"), awsEvent.get("TELEGRAM_USER_IDS"))
    allThreads = [threading.Thread(target=ebay, args=(seenOffers["ebay"], messenger, searchParameters,)),
                  threading.Thread(target=wggesucht, args=(seenOffers["wggesucht"], messenger, searchParameters,)),
                  threading.Thread(target=wggesucht, args=(seenOffers["wggesucht"], messenger, searchParameters, False))]
    if ID_WG_SHARE in runIds and ID_WG_NOSHARE in runIds:
        runIds.remove(ID_WG_NOSHARE)
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
