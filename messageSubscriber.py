from telegram.ext import Updater, CommandHandler
from mongo_connector import MongoConnector
from configparser import ConfigParser

cp = ConfigParser()
cp.optionxform = str
cp.read('config.ini')

db = MongoConnector()
db.connect(cp['DATABASE']['Address'], cp['DATABASE']['Name'])
monitoring_collection = cp['DATABASE']['MonitoringCollection']


def main():
    # Create Updater object and attach dispatcher to it
    #updater = Updater("786032176:AAESzRUttwWGFExygdBxuu-JuzpixQQDxXw")
    #dispatcher = updater.dispatcher



    #updater.bot.send_message(433485753, 'Which monitor do you want to delete?')

    #exit()
    id_list = []
    success, monitors = db.find(monitoring_collection, {}, many=True)

    if success:
        for monitor in monitors:
            if not monitor["telegram_id"] in id_list:
                id_list.append(monitor["telegram_id"])

    print(id_list)


if __name__ == '__main__':
    main()