import datetime as dt
import logging
import urllib
import deep_translator
import geopy
import geopy.distance
import DataStorage

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

MAX_DESCRIPTION_LEN = 1500

AdvertNoPrint = DataStorage.DataStorageClass("AdvertNoPrint",
    {
        # strings
        "adid" : [str, int],
        "url" : [str],
        "website" : [str],
        "title" : [str],
        "address" : [str],
        "flatType" : [str],
        "description" : [str],
        # integers
        "size" : [int],
        "price" : [int],
        "age" : [int],
        "rooms" : [int],
        # bools
        "furnished" : [bool, list],
        "kitchen" : [bool, list],
        "limited" : [bool],
        # dates
        "moveInDate" : [dt.datetime, str],
        "moveOutDate" : [dt.datetime, str],
        # dicts and lists
        "distances" : [dict],
        "routes" : [list]
    }
)

class Advert(AdvertNoPrint):
    """Store information from scraped advert."""
    def __str__(self):
        lines = []
        if (title := self.title):
            lines.append(title.get())
        if (flatType := self.flatType):
            lines.append(f"Type: {flatType.get()}")
        if (price := self.price):
            lines.append(f"Price: {price.get()}€")
        if (size := self.size):
            lines.append(f"Size: {size.get()}m^2")
        if (distances := self.distances):
            for dest, distance in distances.get().items():
                lines.append(f"Distance to {dest}: {round(distance, 1)}km")
        if (moveInDate := self.moveInDate):
            if type(moveInDate.get()) == dt.datetime:
                moveInText = moveInDate.get().strftime('%d.%m.%y')
            else:
                moveInText = moveInDate.get()
            lines.append(f"Move in by {moveInText}")
        if (moveOutDate := self.moveOutDate):
            if type(moveOutDate.get()) == dt.datetime:
                moveOutText = moveOutDate.get().strftime('%d.%m.%y')
            else:
                moveOutText = moveOutDate.get()
            lines.append(f"Move out by {moveOutText}")
        if (furnished := self.furnished):
            lines.append("Is furnished" if furnished.get() else "Is not furnished")
        if (kitchen := self.kitchen):
            lines.append("Has kitchen" if kitchen.get() else "No kitchen")
        if (description := self.description):
            lines.append(description.get()[:MAX_DESCRIPTION_LEN])
        if (url := self.url):
            lines.append(f"Link: {url.get()}")
        if (address := self.address):
            lines.append(f"Address: {address.get()}")
        if (routes := self.routes):
            lines += routes.get()
        return "\n\n** ".join(lines) + "\n--------\n"


def set_distances(advert, pointsOfInterestCoordinates, city):
    if not advert.address:
        return False
    start = geopy.Nominatim(user_agent="flatscrape").geocode(\
        advert.address.get() + " " + city)
    logger.debug("Got Nominatim")
    if not start:
        return False
    distances = {poi : geopy.distance.distance(loc, start.point).km\
                for (poi, loc) in pointsOfInterestCoordinates.items()}
    advert.distances.set(distances)
    return True

def set_routes(advert, pointsOfInterestRoute):
    """Generate google maps strings and store them in advert."""
    if (address := advert.address):
        routes = [f"https://www.google.com/maps/dir/" +\
                  f"{urllib.parse.quote_plus(address.get())}/" +\
                  f"{urllib.parse.quote_plus(dest)}"\
                    for dest in pointsOfInterestRoute]
        advert.routes.set(routes)
        return True
    else:
        return False

def filter_advert(advert, searchParameters):
    """Filter advert based on the search parameters."""
    if advert.price and advert.price.get() > searchParameters.maxPrice:
        return False
    if advert.size and advert.size.get() < searchParameters.minSize:
        return False
    if advert.moveInDate and\
            type(advert.moveInDate.get()) == dt.datetime and\
            advert.moveInDate.get() < searchParameters.moveInLower:
        return False
    if advert.moveInDate and\
            type(advert.moveInDate.get()) == dt.datetime and\
            advert.moveInDate.get() > searchParameters.moveInUpper:
        return False
    if advert.moveOutDate and\
            type(advert.moveOutDate.get()) == dt.datetime and\
            advert.moveOutDate.get() < searchParameters.moveOutLower:
        return False
    if advert.moveOutDate and\
            type(advert.moveOutDate.get()) == dt.datetime and\
            advert.moveOutDate.get() > searchParameters.moveOutUpper:
        return False
    return True

def translate_advert(advert, language):
    """Translate title and description."""
    if not language: return advert
    if (title := advert.title):
        translatedTitle = deep_translator.GoogleTranslator(\
            source='auto', target=language).translate(title.get())
        title.set(translatedTitle)
    if (description := advert.description):
        translatedDescription = deep_translator.GoogleTranslator(\
            source='auto', target=language).translate(description.get())
        description.set(translatedDescription[:MAX_DESCRIPTION_LEN])
