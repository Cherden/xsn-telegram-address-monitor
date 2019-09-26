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
        try:
            query = 'SELECT * FROM balances WHERE address=%s'
            self.cursor.execute(query, (address,))

            if self.cursor.rowcount == 0:
                return 0, False

            entry = self.cursor.fetchone()
            return float(entry[1]) - float(entry[2]), True
        except Exception as e:
            self.db.rollback()
            print(e)

        return 0, False

    def get_last_transaction(self, address):
        try:
            query = 'SELECT time FROM address_transaction_details WHERE address=%s ORDER BY time DESC LIMIT (1)'
            self.cursor.execute(query, (address,))
            if self.cursor.rowcount == 0:
                return 0
            else:
                return int(self.cursor.fetchone()[0])
        except Exception as e:
            self.db.rollback()
            print(e)

        return 0

    def get_total_transactions(self, address):
        try:
            query = 'SELECT COUNT(*) FROM address_transaction_details WHERE address=%s'
            self.cursor.execute(query, (address,))
            if self.cursor.rowcount == 0:
                return 0
            else:
                return int(self.cursor.fetchone()[0])
        except Exception as e:
            self.db.rollback()
            print(e)
        return 0

    def get_new_transactions(self, address, last_payout):
        try:
            query = 'SELECT sent, received, time FROM address_transaction_details WHERE address=%s AND time > ' + str(
                last_payout)
            self.cursor.execute(query, (address,))
            if self.cursor.rowcount == 0:
                return []
            else:
                return self.cursor.fetchall()
        except Exception as e:
            self.db.rollback()
            print(e)
        return []
