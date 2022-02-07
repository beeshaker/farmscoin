from wallet import Wallet
from helpers.util import hash_string_256, hash_block



class Verification:

    @staticmethod
    def valid_proof( transactions, last_hash, proof):

        guess = (str([tx.to_ordered_dict() for tx in transactions]) + str(last_hash) + str(proof)).encode()
        guess_hash = hash_string_256(guess)
        return guess_hash[0:2] == '00'




    @classmethod    
    def verify_chain(clss, blockchain):

        for (index, block) in enumerate(blockchain):
            if index == 0:
                continue
            if block.previous_hash != hash_block(blockchain[index - 1]):
                return False
            if not clss.valid_proof(block.transactions[:-1], block.previous_hash, block.proof):
                print('Invalid proof')
                return False
        return True


    @staticmethod
    def verify_transaction( transaction, get_balance, check_funds=True):

        if check_funds:
            sender_balance = get_balance(transaction.sender)
            return sender_balance >= transaction.amount and Wallet.verify_trans(transaction)
        else:
            return Wallet.verify_trans(transaction)


            

    @classmethod
    def verify_transactions(clss, open_transactions, get_balance):
        return all([clss.verify_transaction(tx, get_balance, False) for tx in open_transactions])