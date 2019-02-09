from telegram.ext import Updater
from mongo_connector import MongoConnector
from configparser import ConfigParser

cp = ConfigParser()
cp.optionxform = str
cp.read('config.ini')

db = MongoConnector()
db.connect(cp['DATABASE']['Address'], cp['DATABASE']['Name'])
telegram_bot_token = cp['TELEGRAM']['SecretKey']
monitoring_collection = cp['DATABASE']['MonitoringCollection']


def main():
    message = "Due to maintenance work, the bot was temporarily unavailable. \n" \
              "We apologize for this. The bot is now up and running again. If you encounter any bugs, please report them to us at Discord. \
               Have a nice weekend."
    updater = Updater(telegram_bot_token)
    dispatcher = updater.dispatcher

    id_list = []
    success, monitors = db.find(monitoring_collection, {}, many=True)

    if success:
        for monitor in monitors:
            if not monitor["telegram_id"] in id_list:
                id_list.append(monitor["telegram_id"])

    for id in id_list:
        try:
            updater.bot.send_message(id, message)

        except Exception as e:
            print("User blocked bot by id:", id)


    exit()

if __name__ == '__main__':
    main()