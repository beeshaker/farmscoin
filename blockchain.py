from functools import reduce
import hashlib as hl
import json
import requests

from wallet import Wallet

from helpers.util import hash_block
from helpers.verification import Verification
from block import Block
from transaction import Transaction
MINING_REWARD = 10


class Blockchain:
    def __init__(self, hosting_node, node_id):
        genesis_block = Block(0, '', [], 69, 0)
        self.__chain = [genesis_block]
        self.__open_transactions = []        
        self.hosting_node = hosting_node
        self.__node_peers = set()
        self.node_id = node_id
        self.resolve_conflict = False
        self.load_data()
       


    def get_open_transactions(self):
        return self.__open_transactions[:]




    @property
    def chain(self):
        return self.__chain[:]




    @chain.setter
    def chain(self,  vall):
        self.__chain = vall




    def load_data(self):
        try:
            with open('blockchain-{}.txt'.format(self.node_id), mode='r') as filef:
                file_content = filef.readlines()
                blockchain = json.loads(file_content[0][:-1])
                updated_blockchain = []

                for block in blockchain:
                    converted_tx = [Transaction(tx['sender'], tx['recipient'], tx['signature'], tx['amount']) for tx in block['transactions']]
                    updated_block = Block( block['index'], block['previous_hash'], converted_tx, block['proof'], block['timestamp'])
                    updated_blockchain.append(updated_block)

                self.chain = updated_blockchain

                open_transactions = json.loads(file_content[1][:-1])
                updated_transactions = []

                for tx in open_transactions:
                    updated_transaction = Transaction(tx['sender'], tx['recipient'], tx['signature'], tx['amount'])
                    updated_transactions.append(updated_transaction)

                self.__open_transactions = updated_transactions
                node_peers = json.loads(file_content[2])
                self.__node_peers =set(node_peers)

        except (IOError, IndexError):
            pass
        finally:
            print('Clean up')






    def save_data(self):
        try:
            with open('blockchain-{}.txt'.format(self.node_id), mode='w') as filef:
                saveable_chain = [block.__dict__ for block in [Block(block_el.index, block_el.previous_hash, [tx.__dict__ for tx in block_el.transactions], block_el.proof, block_el.timestamp) for block_el in self.__chain]]
                filef.write(json.dumps(saveable_chain))
                filef.write('\n')
                save_tx = [tx.__dict__ for tx in self.__open_transactions]
                filef.write(json.dumps(save_tx))
                filef.write('\n')
                filef.write(json.dumps(list(self.__node_peers)))
        except IOError:
            print('Saving failed!')    



    def remove_node(self,node):

        self.__node_peers.discard(node)
        self.save_data()



    def get_node_peer(self):
        return list(self.__node_peers)



    def add_node_peer(self,node):

        self.__node_peers.add(node)
        self.save_data()



    


    def proof_of_work(self):

        last_block = self.__chain[-1]

        last_hash = hash_block(last_block)
        proofowork = 0
        verifier = Verification()
        while not verifier.valid_proof(self.__open_transactions, last_hash, proofowork):
            proofowork += 1
        return proofowork

        

    def get_balance(self, sender=None):

        if sender == None:
            if self.hosting_node == None:
                return None
            participant = self.hosting_node
        else:
            participant = sender
        tx_sender = [[tx.amount for tx in block.transactions if tx.sender == participant] for block in self.__chain]        
        open_tx_sender = [tx.amount for tx in self.__open_transactions if tx.sender == participant]
        tx_sender.append(open_tx_sender)
        print(tx_sender)
        amount_sent = reduce(lambda tx_sum, tx_amt: tx_sum + sum(tx_amt) if len(tx_amt) > 0 else tx_sum + 0, tx_sender, 0)
        tx_recipient = [[tx.amount for tx in block.transactions if tx.recipient == participant] for block in self.__chain]
        amount_received = reduce(lambda tx_sum, tx_amt: tx_sum + sum(tx_amt) if len(tx_amt) > 0 else tx_sum + 0, tx_recipient, 0)

        return amount_received - amount_sent



    def get_last_blockchain_value(self):

        if len(self.__chain) < 1:
            return None
        return self.__chain[-1]



    def add_transaction(self, recipient, sender, signature, amount=1.0,is_receiving = False):

        if self.hosting_node == None:
            return False      
        transaction = Transaction(sender, recipient, signature, amount) 

        if Verification.verify_transaction(transaction, self.get_balance):
            self.__open_transactions.append(transaction)
            self.save_data()
            if not is_receiving:
                for node in self.__node_peers:
                    url = 'http://{}/broadcast-transaction'.format(node)
                    try:
                        response = requests.post(url,json={'sender': sender, 'recipient': recipient, 'amount': amount, 'signature': signature})
                        if response.status_code == 400 or response.status_code == 500:
                            print ('failed transaction needs to be checked')
                            return False
                    except requests.exceptions.ConnectionError:
                        continue
            return True
        return False




    def resolve(self):

        longest_chain = self.chain
        replace_local = False
        for node in self.__node_peers:
            url = 'http://{}/chain'.format(node)
            try:
                response = requests.get(url)
                node_chain = response.json()
                node_chain = [Block(block['index'], block['previous_hash'], [Transaction(tx['sender'], tx['recipient'], tx['signature'], tx['amount']) for tx in block['transactions']], block['proof'], block['timestamp']) for block in node_chain]
                node_chain_length = len(node_chain)
                local_chain_length = len(longest_chain)

                if node_chain_length > local_chain_length and Verification.verify_chain(node_chain):
                    longest_chain = node_chain
                    replace_local = True
            except requests.exceptions.ConnectionError:
                continue
        self.resolve_conflicts = False
        self.chain = longest_chain

        if replace_local:
            self.__open_transactions = []
        self.save_data()
        return replace_local




    def add_block(self, block):
        
        transactions = [Transaction(tx['sender'], tx['recipient'], tx['signature'], tx['amount']) for tx in block['transactions']]
        valid_proof= Verification.valid_proof(transactions[:-1], block['previous_hash'], block['proof'])
        hash_check = hash_block(self.chain[-1]) == block['previous_hash']

        if not valid_proof or not hash_check:
            return False

        converted_block = Block(block['index'], block['previous_hash'],transactions,block['proof'],block['timestamp'])
        self.__chain.append(converted_block)
        stored_trans = self.__open_transactions[:]
        for incoming_tx in block['transactions']:
            for open_tx in stored_trans:
                if open_tx.sender == incoming_tx['sender'] and open_tx.recipient == incoming_tx['recipient'] and open_tx.signature == incoming_tx['signature']:
                    try:
                        self.__open_transactions.remove(open_tx)
                    except ValueError:
                        print(' already removed')
        self.save_data()
        return True

    def mine_block(self):

        if self.hosting_node == None:
            return None
        last_block = self.__chain[-1]
        hashed_block = hash_block(last_block)
        proof = self.proof_of_work()
        reward_transaction = Transaction('MINING', self.hosting_node,'', MINING_REWARD)
        copied_transactions = self.__open_transactions[:]

        for tx in  copied_transactions:
            if not Wallet.verify_trans(tx):
                return None

        copied_transactions.append(reward_transaction)
        block = Block(len(self.__chain), hashed_block, copied_transactions, proof)        

        self.__chain.append(block)
        self.__open_transactions = []        
        self.save_data()
        for node in self.__node_peers:
            url = 'http://{}/broadcast-block'.format(node)
            converted_block = block.__dict__.copy()
            converted_block['transactions'] = [tx.__dict__ for tx in converted_block['transactions']]
            try:
                responses = requests.post(url,json = {'block': converted_block }) 
                if responses.status_code == 400 or responses.status_code == 500:
                    print ('block failed, needs to be resolved')
                if responses.status_code == 409:
                    self.resolve_conflict = True
            except requests.exceptions.ConnectionError:
                continue
        return block
