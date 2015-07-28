#! /Users/joao/testes/virt_env/moneybot/bin/python
# -*- coding: utf-8 -*-
import sys
from functools import reduce
from decimal import Decimal
from datetime import datetime
from time import sleep

from bitreserve import Bitreserve

from config import auth, weights


MINIMUM_TRANSACTION = Decimal('0.001')
DEBUG = False


class MoneyBot(object):

    def __init__(self, sandbox=False):
        self.normalize_weights()
        if DEBUG:
            print(self.weights)
        self.auth(sandbox)

    def normalize_weights(self):
        total = 0.0
        for value in weights.values():
            total += value
        self.weights = {}
        for key, value in weights.items():
            self.weights[key] = value / total

    def auth(self, sandbox=False):
        if sandbox:
            self.api = Bitreserve(host='api-sandbox.bitreserve.org')
        else:
            self.api = Bitreserve()
        pat = auth.get('pat', None)
        user = auth.get('user', None)
        password = auth.get('password', None)
        if pat:
            self.api.auth_pat(pat)
        elif user and password:
            self.api.auth(user, password)
            
    def update_card_information(self):
        me = self.api.get_me()
        cards = me['cards']
        self.cards = {}

        for card in cards:
            if Decimal(card['balance']) or card['currency'] in self.weights.keys():
                self.cards[card['id']] = {
                    'id': card['id'],
                    'currency': card['currency'],
                    'address': card['addresses'][0]['id'],
                    'balance': Decimal(card['normalized'][0]['balance']),
                }
                self.currency = card['normalized'][0]['currency']

        total = reduce(lambda total, card: total + card['balance'], self.cards.values(), Decimal('0.0'))
        if DEBUG:
            print('total: {}'.format(total))

        for card_id, card in self.cards.items():
            target = total * Decimal(self.weights[card['currency']])  # this assumes 1 card per currency
            if DEBUG:
                print('target: {}'.format(target))
            self.cards[card_id]['difference'] = target - card['balance']

        if DEBUG:
            print(self.cards)
            
    def calculate_next_transaction(self):
        def difference(card_id):
            return self.cards[card_id]['difference']

        potential_sources = list(filter(lambda cid: difference(cid) <= -MINIMUM_TRANSACTION, self.cards.keys()))
        potential_destinations = list(filter(lambda cid: difference(cid) >= MINIMUM_TRANSACTION, self.cards.keys()))
        
        if not (len(potential_sources) and len(potential_destinations)):
            return None, None, None

        potential_sources.sort(key=difference, reverse=True)
        potential_destinations.sort(key=difference, reverse=True)

        if self.cards[potential_sources[0]] == self.cards[potential_destinations[0]]:
            return None, None, None
        
        return (
            self.cards[potential_sources[0]],
            self.cards[potential_destinations[0]],
            min(abs(self.cards[potential_sources[0]]['difference']), abs(self.cards[potential_destinations[0]]['difference']))
        )
        
    def run(self):
        self.update_card_information()
        source, destination, amount = self.calculate_next_transaction()

        if not source:
            print('nothing to do')
            return

        print('Transfer {} {} from {} to {}.'.format(amount, self.currency, source['address'], destination['address']))

        trans = self.api.prepare_txn(source['id'], destination['address'], amount, self.currency)

        res = self.api.execute_txn(source['id'], trans)
        print(res['id'])

if __name__ == '__main__':
    scrooge = MoneyBot()
    while 1:
        scrooge.run()
        sleep(20)
