import datetime as dt
import threading
import time
import telegram

# Distance limit, at which point offers become less interesting. This is not
# a hard filter, only to determine the priority of a message.
INDIVIDUAL_DIST_LIMIT = 6

class Messenger(object):
    """Send messages via telegram"""
    def __init__(self, teleBotToken, teleUserIds, translate=None):
        self.teleBotToken = teleBotToken
        self.teleUserIds = teleUserIds
        self.joiner = ""
        self.individualMessagesQueue = []
        self.bulkMessageQueue = []
        self.individualMessageLock = threading.Lock()
        self.bulkMessageLock = threading.Lock()
        self.sendTimes = []
        self.translate = translate

    def handle_advert(self, advert):
        individual = self.should_send_individually(advert)
        self.add_to_queue(advert, individual=individual)    

    def should_send_individually(self, advert):
        if advert.title and "tausch" in advert.title.get().lower():
            return False
        if advert.distances and \
                all(map(lambda d: d > INDIVIDUAL_DIST_LIMIT, advert.distances.get().values())):
            return False
        # if many messages are queued and it is wg, it is low priority
        if len(self.individualMessagesQueue) > 9 and advert.flatType and \
                advert.flatType.get().lower() in ["wg", "wohngemeinschaft"]:
            return False
        return True

    def add_to_queue(self, msg, individual=True):
        print(f"[interpreter] adding to queue {individual=}")
        queue = self.individualMessagesQueue if individual else self.bulkMessageQueue
        lock = self.individualMessageLock if individual else self.bulkMessageLock
        lock.acquire()
        print("[interpreter] Lock acquired")
        queue.append(msg)
        lock.release()
        print("[interpreter] Lock released")
        return True

    def send_message(self, msg):
        #print("[interpreter] \n----MESSAGE:-------\n" + msg)
        self._send_message_telegram(msg)
        self.sendTimes.append(time.time())


    def _send_message_telegram(self, msg):
        try:
            for teleUserId in self.teleUserIds:
                telegram.Bot(self.teleBotToken).send_message(teleUserId, msg[:3500],\
                    disable_notification=True)
        except ValueError as e:
            print("Error sending message: ", e)
            

    def wait_until_message_can_be_sent(self):
        """Wait until all of:
            1. no more than ten messages sent in last minute
            2. at least 3 seconds have passed since last message
        """
        while len(list(filter(lambda t: t >= time.time() - 60, self.sendTimes))) >= 10:
            time.sleep(0.1)
        if len(self.sendTimes) > 0:
            time.sleep(max(self.sendTimes[-1] - time.time() + 3, 0))
        return True

    def create_bulk_message(self):
        sendList = []
        while len(self.bulkMessageQueue) > 0:
            if len(self.joiner.join(
                list(map(str, sendList)) +\
                    [str(self.bulkMessageQueue[0])])) < 3500:
                sendList.append(self.bulkMessageQueue.pop(0))
            else:
                break
        return sendList

    def check_queue(self):
        return len(self.individualMessagesQueue) + len(self.bulkMessageQueue) > 0

    def handle_queue(self):
        if self.individualMessagesQueue or\
                self.bulkMessageQueue:
            self.wait_until_message_can_be_sent()
            sendList = []
            if len(self.individualMessagesQueue) > 0:
                self.individualMessageLock.acquire()
                sendList = [self.individualMessagesQueue.pop(0)]
                self.individualMessageLock.release()
            elif len(self.bulkMessageQueue) > 0:
                self.bulkMessageLock.acquire()
                sendList = self.create_bulk_message()
                self.bulkMessageLock.release()
            if sendList:
                print("[interpreter] sending message")
                msg = self.joiner.join(list(map(str, sendList)))
                self.send_message(msg)
                handledIds = {"ebay": [], "wggesucht": []}
                for ad in sendList:
                    if ad.website and "ebay" in ad.website.get():
                        site = "ebay"
                    elif ad.website and "gesucht" in ad.website.get():
                        site = "wggesucht"
                    else:
                        site = ""
                    handledIds[site].append(ad.adid.get())
                    #print(f"[interpreter] handled id {ad.adid.get()} for {site}")
                #print(f"[interpreter] returning {handledIds}")
                return handledIds
        return None
