import pymongo


class MongoConnector:
    connector = None
    db = None

    logger = None
    retries = 0

    def __init__(self, retries=3):
        self.retries = retries

    @staticmethod
    def filter_object_id(data):
        if type(data) is list:
            return_data = []
            for element in data:
                if '_id' in element:
                    del element['_id']
                return_data.append(element)
            return return_data
        elif type(data) is dict:
            if '_id' in data:
                del data['_id']
            return data

    def connect(self, address, db_name):

        self.connector = self.__mongo_wrapper(pymongo.MongoClient, address)
        if self.connector == -1:
            return False

        self.db = self.connector[db_name]

        return True

    def find(self, collection, criteria, many=False):
        if many:
            data = self.__mongo_wrapper(self.db[collection].find, criteria)

            if (not type(data) is list) and data is None:
                return False, {}
            else:
                return_data = []
                for element in data:
                    return_data.append(element)
                return True, return_data
        else:
            data = self.__mongo_wrapper(self.db[collection].find_one, criteria)

            if (not type(data) is dict) and data is None:
                return False, {}
            else:
                return True, data

    def insert(self, collection, data):
        if type(data) is list:
            self.__mongo_wrapper(self.db[collection].insert_many, data)
        elif type(data) is dict:
            self.__mongo_wrapper(self.db[collection].insert, data)
        else:
            print('insert:: datatype neither list nor dict')

    def update(self, collection, criteria, updated_data, many=False):
        data = {'$set': updated_data}
        if many:
            self.__mongo_wrapper(self.db[collection].update_many, criteria, data)
        else:
            self.__mongo_wrapper(self.db[collection].update_one, criteria, data)

    def delete(self, collection, criteria, many=False):
        if many:
            self.__mongo_wrapper(self.db[collection].delete_many, criteria)
        else:
            self.__mongo_wrapper(self.db[collection].delete_one, criteria)

    def __mongo_wrapper(self, func, *args):
        for i in range(3):
            try:
                return func(*args)
            except Exception as e:
                print(e)
                continue

        print('failed to execute database operation for {}'.format(func.__name__))
        return -1
