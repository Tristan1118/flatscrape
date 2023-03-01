import datetime as dt
import logging
import threading
import time
import telegram

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Distance limit, at which point offers become less interesting. This is not
# a hard filter, only to determine the priority of a message.
DISTANCE_LIMIT_PRIO = 6

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
        """
        Main method for outside classes. Perform all necessary steps to send
        the advert information to the end user.
        """
        individual = self.should_send_individually(advert)
        self.add_to_queue(advert, individual=individual)    

    def should_send_individually(self, advert):
        """
        Determine whether an advert should be sent in a separate or bulk
        message. The reason for bulk messaging is that there is a limit on
        the number of messages we can sent in a time frame. The decision is
        made based on attractiveness of the advert and the current demand on
        messaging.
        """
        if advert.title and "tausch" in advert.title.get().lower():
            return False
        if advert.distances and \
                all(map(lambda d: d > DISTANCE_LIMIT_PRIO, advert.distances.get().values())):
            return False
        # if many messages are queued and it is wg, it is low priority
        if len(self.individualMessagesQueue) > 9 and advert.flatType and \
                advert.flatType.get().lower() in ["wg", "wohngemeinschaft"]:
            return False
        return True

    def add_to_queue(self, msg, individual=True):
        """Thread safe queueing for asynchronous messaging."""
        logger.debug(f"Adding to queue {individual=}")
        queue = self.individualMessagesQueue if individual else self.bulkMessageQueue
        lock = self.individualMessageLock if individual else self.bulkMessageLock
        lock.acquire()
        logger.debug("Queue lock acquired")
        queue.append(msg)
        lock.release()
        logger.debug("Queue lock released")
        return True

    def send_message(self, msg):
        """Public method for sending the message via telegram."""
        self._send_message_telegram(msg)
        self.sendTimes.append(time.time())


    def _send_message_telegram(self, msg):
        """Private method for sending message. Not to be called directly."""
        try:
            for teleUserId in self.teleUserIds:
                telegram.Bot(self.teleBotToken).send_message(teleUserId, msg[:3500],\
                    disable_notification=True)
        except ValueError as e:
            logger.critical("Error sending message: ", e)
            

    def wait_until_message_can_be_sent(self):
        """
        Wait until all of:
            1. no more than ten messages sent in last minute
            2. at least 3 seconds have passed since last message
        """
        while len(list(filter(lambda t: t >= time.time() - 60, self.sendTimes))) >= 10:
            time.sleep(0.1)
        if len(self.sendTimes) > 0:
            time.sleep(max(self.sendTimes[-1] - time.time() + 3, 0))
        return True

    def create_bulk_message(self):
        """
        Pop as many messages off the bulk queue while staying within the length
        limit.
        """
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
        """Check if asynchronous messenger is finished."""
        return len(self.individualMessagesQueue) + len(self.bulkMessageQueue) > 0

    def handle_queue(self):
        """
        Generate a message from the queues and send it. Return the advert ids
        that were covered by the message.
        """
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
                logger.debug("Sending message")
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
                return handledIds
        return None
