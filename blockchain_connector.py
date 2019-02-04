import psycopg2


class BlockchainConnector:
    def __init__(self):
        self.db = None
        self.cursor = None

    def __del__(self):
        self.cursor.close()
        self.db.close()

    def connect(self, params):
        self.db = psycopg2.connect(host=params['host'], database=params['database'], user=params['user'], password=params['password'])
        self.cursor = self.db.cursor()

    def get_balance(self, address):
        self.cursor.execute('SELECT * FROM balances WHERE address=\'' + address + '\'')
        if self.cursor.rowcount == 0:
            return 0, False

        entry = self.cursor.fetchone()
        return float(entry[1]) - float(entry[2]), True

    def get_last_transaction(self, address):
        self.cursor.execute(
            'SELECT time FROM address_transaction_details WHERE address=\'' + address + '\' ORDER BY time DESC LIMIT (1)')
        if self.cursor.rowcount == 0:
            return 0
        else:
            return int(self.cursor.fetchone()[0])

    def get_total_transactions(self, address):
        self.cursor.execute('SELECT COUNT(*) FROM address_transaction_details WHERE address=\'' + address + '\'')
        if self.cursor.rowcount == 0:
            return 0
        else:
            return int(self.cursor.fetchone()[0])

    def get_new_transactions(self, address, last_payout):
        self.cursor.execute('SELECT sent, received, time FROM address_transaction_details WHERE address=\'' + address + '\' AND time > ' + str(last_payout))
        if self.cursor.rowcount == 0:
            return []
        else:
            return self.cursor.fetchall()
