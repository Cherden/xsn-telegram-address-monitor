# XSN Address Monitor (Telegram Bot)

This project runs a telegram bot where users can enter XSN addresses and get push notifications on transactions from or to the address. The backend (as it is now) requieres a [local blockchain explorer](https://github.com/X9Developers/block-explorer) so the bot can read new transaction from the local postgres db and then send push notifications.

## Setup

* Download the [blockchain explorer](https://github.com/X9Developers/block-explorer), install and let it sync. 
* Install the required python packages in the src folder with `pip install -r requirements.txt`
* Create a telegram bot using the [BotFather](https://telegram.me/botfather)
* Enter the database credentials and telegram secret key in the `config.ini`
* Start the bot in the src folder with `python monitor.py`


### Note: This repository was once private and initially just a hack so do not expect good code. We made it open source because we (i.e. [Simon](https://github.com/Simse92)) can not run the bot ourselves anymore and hope someone will continue it. We will also not actively develop here anymore. If you want features implemented, create a pull request and we will be happy to merge it.
