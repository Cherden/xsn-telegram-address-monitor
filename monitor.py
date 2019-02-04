from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from mongo_connector import MongoConnector
from configparser import ConfigParser
from bson.objectid import ObjectId
import threading
import time
import requests
import logging
import datetime
import re

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

cp = ConfigParser()
cp.optionxform = str
cp.read('config.ini')

db = MongoConnector()
db.connect(cp['DATABASE']['Address'], cp['DATABASE']['Name'])

monitoring_collection = cp['DATABASE']['MonitoringCollection']

CRAWLER_SLEEP_TIME = 60 * 30

NEW_TRANSACTION_MESSAGE_TEMPLATE = 'New transaction for "{}" ({}): {} XSN'
telegram_bot_token = cp['TELEGRAM']['SecretKey']

EXPLORER_BASE_URL = 'localhost:9000'

DATE_FORMAT = '%d/%m/%Y %H:%M:%S'
ADD_ADDRESS_MESSAGE = 'Enter address for '
ADD_NAME_MESSAGE = 'Enter monitor name'
STATISTICS_MESSAGE_TEMPLATE = 'This bot monitors {} addresses from {} users!'

last_checked = datetime.datetime.utcnow()

bot_statistics = {
    'monitor_amount': 0,
    'users': []
}


def initialize_statistics():
    success, monitors = db.find(monitoring_collection, {}, many=True)
    if success:
        bot_statistics['monitor_amount'] = len(monitors)
        for monitor in monitors:
            if monitor['telegram_id'] not in bot_statistics['users']:
                bot_statistics['users'].append(monitor['telegram_id'])


def timestamp_to_date(timestamp):
    return str(datetime.datetime.utcfromtimestamp(timestamp).strftime(DATE_FORMAT))


def create_new_monitor(address):
    url = EXPLORER_BASE_URL + '/api/addresses/{}'.format(address)
    ret_json = requests.get(url).json()

    # Address Format invalid or available funds on address = 0
    if ("errors" in ret_json) or ret_json['available'] == 0:
        return {}, False

    balance = ret_json['available']

    url = EXPLORER_BASE_URL + '/api/addresses/{}/transactions'.format(address)
    transactions_json = requests.get(url).json()

    total_transactions = transactions_json['total']
    last_transaction = 0
    if total_transactions != 0 and transactions_json['data']:
        last_transaction = int(transactions_json['data'][0]['time'])

    new_monitor = {
        'name': '',
        'address': address,
        'telegram_id': 0,
        'balance': balance,
        'total_transactions': total_transactions,
        'last_transaction': last_transaction
    }

    return new_monitor, True


class RewardCrawler(threading.Thread):
    def __init__(self, bot):
        threading.Thread.__init__(self)
        self.db = MongoConnector()
        self.db.connect(cp['DATABASE']['Address'], cp['DATABASE']['Name'])
        self.collection = cp['DATABASE']['MonitoringCollection']

        self.telegram_bot = bot

        self.running = True

        print('Reward crawler started')

    def terminate(self):
        self.running = False

    def run(self):
        while self.running:
            success, result = self.db.find(self.collection, {}, many=True)
            if not success:
                continue

            for entry in result:
                address = entry['address']
                url = EXPLORER_BASE_URL + '/api/addresses/{}/transactions'.format(address)
                info_json = requests.get(url).json()

                total_transactions = entry['total_transactions']
                new_transactions = min(info_json['total'] - total_transactions, len(info_json['data']))
                if new_transactions > 0:
                    for i in range(new_transactions):
                        data = info_json['data'][i]

                        timestamp = int(data['time'])
                        received = round(data['received'] - data['sent'], 7)

                        entry['balance'] += received
                        if entry['last_transaction'] < timestamp:
                            entry['last_transaction'] = timestamp

                        message = NEW_TRANSACTION_MESSAGE_TEMPLATE.format(entry['name'],
                                                                          timestamp_to_date(timestamp),
                                                                          float(received))
                        self.telegram_bot.send_message(chat_id=entry['telegram_id'], text=message)

                    entry['total_transactions'] = info_json['total']

                db.update(self.collection, {'_id': entry['_id']}, entry)
                time.sleep(0.1)

            global last_checked
            last_checked = datetime.datetime.utcnow()
            time.sleep(CRAWLER_SLEEP_TIME)


def menu(bot, update):
    query = update.callback_query
    chat_id = query.message.chat_id

    if format(query.data) == 'add':
        bot.send_message(chat_id, ADD_NAME_MESSAGE, reply_markup=ForceReply())
    elif format(query.data) == 'list':
        monitor_list = get_monitors(chat_id)

        if not monitor_list:
            bot.send_message(chat_id, 'You don\'t have any monitors active.')
        else:
            print_status(bot, chat_id, monitor_list)
    elif format(query.data) == 'stats':
        monitor_amount = bot_statistics['monitor_amount']
        user_amount = len(bot_statistics['users'])

        bot.send_message(chat_id, STATISTICS_MESSAGE_TEMPLATE.format(monitor_amount, user_amount))
    elif format(query.data) == 'delete':
        delete_confirmation_message(bot, chat_id)
    elif 'del_monitor_' in format(query.data):
        monitor_id = format(query.data).replace('del_monitor_', '')
        db.delete(monitoring_collection, {'_id': ObjectId(monitor_id)})

        bot.send_message(chat_id, 'Monitor deleted!')

    query.answer()


def print_status(bot, chat_id, monitor_list):
    message = "Status of your XSN Address monitors:\n"
    message += 'Last checked: ' + str(last_checked.strftime(DATE_FORMAT)) + '\n'
    for monitor in monitor_list:
        message += '\n'
        message += str(monitor['name']) + ' (' + monitor['address'] + '):\n'
        message += 'Balance: ' + str(monitor['balance']) + ' XSN\n'
        message += 'Total transactions: ' + str(monitor['total_transactions']) + '\n'
        message += 'Last transaction: '
        if monitor['last_transaction'] == 0:
            message += 'Never'
        else:
            message += timestamp_to_date(monitor['last_transaction'])
        message += '\n'

    bot.send_message(chat_id, message)


def message_handler(bot, update):
    del bot

    if update.message.reply_to_message is None:
        return

    if update.message.reply_to_message.text == ADD_NAME_MESSAGE:
        # Call add method
        update.message.reply_text(ADD_ADDRESS_MESSAGE + '"' + update.message.text + '"', reply_markup=ForceReply())

    if ADD_ADDRESS_MESSAGE in update.message.reply_to_message.text:
        message = update.message.reply_to_message.text
        if message.count('"') != 2:
            update.message.reply_text('Invalid character in monitor name.')
            return

        name = re.search('.*"(.*)".*', message).group(1)
        address = update.message.text

        new_monitor, success = create_new_monitor(address)
        if not success:
            update.message.reply_text("Invalid Address.")
            return

        new_monitor['name'] = name
        new_monitor['telegram_id'] = update.message['chat']['id']

        update.message.reply_text('Added monitor "' + name + '" for address ' + address)
        db.insert(monitoring_collection, new_monitor)

        # update statistics
        bot_statistics['monitor_amount'] += 1
        if new_monitor['telegram_id'] not in bot_statistics['users']:
            bot_statistics['users'].append(new_monitor['telegram_id'])


def start(bot, update):
    del bot

    message = "XSN Address Monitoring Menu:"

    keyboard = [[InlineKeyboardButton("Add monitor", callback_data='add')],
                [InlineKeyboardButton("My monitors", callback_data='list')],
                [InlineKeyboardButton("Bot statistics", callback_data='stats')],
                [InlineKeyboardButton("Delete monitor", callback_data='delete')]]

    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text(message, reply_markup=reply_markup)


def delete_confirmation_message(bot, chat_id):
    keyboard = []

    monitors = get_monitors(chat_id)
    for monitor in monitors:
        button_name = monitor['name'] + ' (' + monitor['address'] + ')'
        new_item = [InlineKeyboardButton(button_name,
                                         callback_data='del_monitor_' + str(monitor['_id']))]
        keyboard.append(new_item)

    reply_markup = InlineKeyboardMarkup(keyboard)

    bot.send_message(chat_id, 'Which monitor do you want to delete?',
                     reply_markup=reply_markup)


def get_monitors(tele_id):
    success, result = db.find(monitoring_collection, {'telegram_id': tele_id}, many=True)

    if not success:
        logger.warning('get_monitors caused error "%s"', success)

    return result


def main():
    # Create Updater object and attach dispatcher to it
    updater = Updater(telegram_bot_token)
    dispatcher = updater.dispatcher
    print("Bot started")

    crawler = RewardCrawler(updater.bot)
    crawler.start()

    # Initialize statistics
    initialize_statistics()

    # Add command handler to dispatcher
    start_handler = CommandHandler('start', start)
    dispatcher.add_handler(CallbackQueryHandler(menu))
    dispatcher.add_handler(start_handler)

    # on noncommand i.e message - echo the message on Telegram
    dispatcher.add_handler(MessageHandler(Filters.text, message_handler))

    # Start the bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C
    updater.idle()
    crawler.terminate()


if __name__ == '__main__':
    main()
