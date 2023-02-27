# flatscrape
Support project for finding an apartment.
Sends relevant information from offers on websites to your phone on a set schedule.
The offers can then manually be reviewed and contacted.

The benefit is that few offers are missed and no constant refreshment of browser windows is necessary.
Also, it can be configured so that no offer is shown multiple times, so that you never have to wonder if you already contacted one or not.

## Functionalities
* Parse adverts on several websites (e.g. ebay-kleinanzeigen and wg-gesucht) and unify the information.
* Use a Telegram Bot to send the information to yourself.
* Interface for aws lambda, so that it can be set up as a layer for a scheduled lambda function.


## Notes
* The `DataStorageClass` is funny. Not a very serious/elegant idea, but it actually works well.
* If I had spent the time just looking for a flat instead, I probably would have found one sooner.
