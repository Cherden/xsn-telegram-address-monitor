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

telegram_message_template = 'New transaction {}: {0:.4f} XSN'
telegram_bot_token = cp['TELEGRAM']['SecretKey']

add_message_text = 'Enter address for '
add_name_message_text = 'Enter monitor name'

last_checked = datetime.datetime.utcnow()


def create_payout_info(address):
    url = 'https://xsnexplorer.io/api/addresses/{}/transactions'.format(address)
    info_json = requests.get(url).json()
    payout_info = {
        'total_transactions': info_json['total'],
        'total_payout': 0,
        'payouts': []
    }

    return payout_info


def check_monitor_address(address):
    url = 'https://xsnexplorer.io/api/addresses/{}'.format(address)
    ret_json = requests.get(url).json()

    # Address Format invalid or available funds on address = 0
    if ("errors" in ret_json) or ret_json['available'] == 0:
        return 0, False
    else:
        return ret_json['available'], True


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
                url = 'https://xsnexplorer.io/api/addresses/{}/transactions'.format(address)
                info_json = requests.get(url).json()

                total_transactions = entry['payout_info']['total_transactions']
                new_transactions = min(info_json['total'] - total_transactions, len(info_json['data']))
                if new_transactions > 0:
                    for i in range(new_transactions):
                        data = info_json['data'][i]
                        new_payout = {'blockhash': data['blockhash'],
                                      'time': data['time'],
                                      'received': data['received']}
                        entry['payout_info']['payouts'].append(new_payout)

                        received = round(data['received'] - data['sent'], 7)
                        entry['payout_info']['total_payout'] = entry['payout_info']['total_payout'] + received
                        entry['balance'] += received

                        message = telegram_message_template.format(entry['name'], float(received))
                        self.telegram_bot.send_message(chat_id=entry['telegram_id'], text=message)

                    entry['payout_info']['total_transactions'] = info_json['total']

                db.update(self.collection, {'_id': entry['_id']}, entry)
                time.sleep(0.1)

            global last_checked
            last_checked = datetime.datetime.utcnow()
            time.sleep(CRAWLER_SLEEP_TIME)


def menu(bot, update):
    query = update.callback_query

    if format(query.data) == 'add':
        bot.send_message(query.message.chat_id, add_name_message_text, reply_markup=ForceReply())
    elif format(query.data) == 'list':
        monitor_list = get_monitors(query.message.chat_id)
        print_status(bot, query.message.chat_id, monitor_list)
    elif format(query.data) == 'delete':
        delete_confirmation_message(bot, query.message.chat_id)
    elif 'del_monitor_' in format(query.data):
        monitor_id = format(query.data).replace('del_monitor_', '')
        db.delete(monitoring_collection, {'_id': ObjectId(monitor_id)})

        bot.send_message(query.message.chat_id, 'Monitor deleted!')


def print_status(bot, chat_id, monitor_list):
    message = "Status of your XSN Address monitors: \n"
    for monitor in monitor_list:
        message += '\n'
        message += str(monitor['name'])
        message += ' (' + monitor['address'] + '):'
        message += '\nBalance: '
        message += str(monitor['balance']) + ' XSN'
        message += '\nLast transaction: '
        if len(monitor['payout_info']['payouts']) == 0:
            message += 'Never'
        else:
            message += str(datetime.datetime.utcfromtimestamp(int(monitor['payout_info']['payouts'][-1]['time'])).strftime('%B %d %Y - %H:%M:%S'))
        message += '\nLast checked: '
        message += str(last_checked.strftime('%B %d %Y - %H:%M:%S'))
        message += '\n'

    bot.send_message(chat_id, message)


def message_handler(bot, update):
    if update.message.reply_to_message is None:
        return

    if update.message.reply_to_message.text == add_name_message_text:
        # Call add method
        update.message.reply_text(add_message_text + '"' + update.message.text + '"', reply_markup=ForceReply())

    if add_message_text in update.message.reply_to_message.text:
        message = update.message.reply_to_message.text
        if message.count('"') != 2:
            update.message.reply_text('Invalid character in monitor name.')
            return

        name = re.search('.*"(.*)".*', message).group(1)
        address = update.message.text
        balance, success = check_monitor_address(address)
        if not success:
            update.message.reply_text("Invalid Address.")
            return

        update.message.reply_text('Added monitor "' + name + '" for address ' + address)
        add_monitor(update.message['chat']['id'], address, name, balance)


def start(bot, update):
    message = "XSN Address Monitoring Menu:"

    keyboard = [[InlineKeyboardButton("Add monitor", callback_data='add')],
                [InlineKeyboardButton("My monitors", callback_data='list')],
                [InlineKeyboardButton("Delete monitor", callback_data='delete')]]

    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text(message, reply_markup=reply_markup)


def add_monitor(chat_id, address, name, balance):
    new_monitor = {
        'name': name,
        'address': address,
        'telegram_id': chat_id,
        'balance': balance,
        'payout_info': create_payout_info(address)
    }

    db.insert(monitoring_collection, new_monitor)


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
