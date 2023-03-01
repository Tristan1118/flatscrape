import datetime as dt
import geopy
import geopy.distance
import util

class DataField():
    """ Typed dictionary entry I guess """
    def __init__(self, expectedTypes=[object]):
        self.expectedTypes = expectedTypes
        self.isset = False
        self.val = None
    def __bool__(self):
        return self.isset
    def set(self, val):
        if not any(map(lambda t: isinstance(val, t), self.expectedTypes)):
            raise TypeError(f"Type {type(val)} not supported for data "+\
                            f"field: expected any of {self.expectedTypes}.")
        self.val = val
        self.isset = True
    def get(self):
        if not self.isset:
            raise AttributeError(f"Cannot get unitialized data field value.")
        return self.val


        

def DataStorageClass(classname, dataTypes):
    """ An abomination, because I was bored """
    class DataStorage():
        def __init__(self):
            self.__dict__.update({t: DataField(dataTypes[t]) for t in dataTypes.keys()})
        def __getattr__(self, name):
            if not name in self.__dict__:
                raise ValueError(f"Field `{name}` cannot be stored.")
            return self.__dict__[name]
    DataStorage.__name__ = classname
    DataStorage.__qualname__ = classname
    return DataStorage


class SearchParameters():
    """ Glorified dictionary, generated from aws event"""
    def __init__(self, awsEvent):
        self.maxPrice = 9999999
        self.minSize = 0
        self.moveInLower = dt.datetime(1900,1,1)
        self.moveInUpper = dt.datetime(3000,1,1)
        self.moveOutLower = dt.datetime(1900,1,1)
        self.moveOutUpper = dt.datetime(3000,1,1)
        self.wggesuchtFlatUrls = []
        self.wggesuchtWGUrls = []
        self.ebayUrls = []
        self.city = "Berlin"
        self.poiDistances = {}
        self.poiRoutes = []
        self.translate = None
        self.parse_aws_event(awsEvent)

    def parse_aws_event(self, awsEvent):
        self.maxPrice = awsEvent.get("maxPrice", self.maxPrice)
        self.minSize = awsEvent.get("minSize", self.minSize)
        self.moveInLower = util.parse_german_date(awsEvent.get("moveInLower", "01.01.1900"))
        self.moveInUpper = util.parse_german_date(awsEvent.get("moveInUpper", "01.01.3000"))
        self.moveOutLower = util.parse_german_date(awsEvent.get("moveOutLower", "01.01.1900"))
        self.moveOutUpper = util.parse_german_date(awsEvent.get("moveOutUpper", "01.01.3000"))
        self.wggesuchtFlatUrls = awsEvent.get("wggesuchtUrls", {"Flat": self.wggesuchtFlatUrls}).get("Flat")
        self.wggesuchtWGUrls = awsEvent.get("wggesuchtUrls", {"WG": self.wggesuchtWGUrls}).get("WG")
        self.ebayUrls = awsEvent.get("ebayUrls", self.ebayUrls)
        self.city = awsEvent.get("city")
        self.poiDistances = {poi: geopy.Nominatim(user_agent="flatscrape").geocode(address).point\
            for (poi, address) in awsEvent.get("POI_DISTANCES", {}).items()}
        self.poiRoutes = awsEvent.get("POI_ROUTES", self.poiRoutes)
        self.translate = awsEvent.get("LANG", None)
        return True


    